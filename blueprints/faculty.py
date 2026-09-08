"""Faculty Blueprint: applying for leaves."""
from datetime import date
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user

from extensions import db
from models import LeaveApplication, FacultyAttendanceSession, FacultyAttendance, User, ROLE_FACULTY, MedicalCertificate, Attendance, AttendanceSession, Subject
from blueprints.decorators import roles_required
from face_engine import engine, feature_from_bytes
from blueprints.imaging import decode_data_url

faculty_bp = Blueprint("faculty", __name__, url_prefix="/faculty")

@faculty_bp.route("/leaves", methods=["GET", "POST"])
@login_required
@roles_required(ROLE_FACULTY)
def leaves():
    if request.method == "POST":
        start_date_str = request.form.get("start_date")
        end_date_str = request.form.get("end_date")
        reason = request.form.get("reason", "").strip()
        
        try:
            start_date = date.fromisoformat(start_date_str)
            end_date = date.fromisoformat(end_date_str)
            
            if start_date > end_date:
                flash("End date must be after start date.", "danger")
            elif not reason:
                flash("Reason is required.", "danger")
            else:
                leave = LeaveApplication(
                    user_id=current_user.id,
                    start_date=start_date,
                    end_date=end_date,
                    reason=reason
                )
                db.session.add(leave)
                db.session.commit()
                flash("Leave application submitted successfully.", "success")
                return redirect(url_for("faculty.leaves"))
        except (ValueError, TypeError):
            flash("Invalid dates provided.", "danger")
            
    # GET: show leave history
    my_leaves = LeaveApplication.query.filter_by(user_id=current_user.id).order_by(LeaveApplication.created_at.desc()).all()
    return render_template("faculty/leaves.html", leaves=my_leaves, today=date.today().isoformat())

# --- Daily Face Attendance ---

@faculty_bp.route("/face-attendance")
@login_required
@roles_required(ROLE_FACULTY)
def face_attendance():
    today = date.today()
    # Find if marked today
    session = FacultyAttendanceSession.query.filter_by(session_date=today).first()
    is_present = False
    if session:
        att = FacultyAttendance.query.filter_by(session_id=session.id, faculty_id=current_user.id).first()
        if att and att.status == "present":
            is_present = True
            
    return render_template("faculty/face_attendance.html", 
                           today=today, is_present=is_present, engine_ready=engine.available)

@faculty_bp.route("/face-attendance/recognize", methods=["POST"])
@login_required
@roles_required(ROLE_FACULTY)
def face_attendance_recognize():
    if not engine.available:
        return jsonify(success=False, message="Face models not installed.")
        
    image = decode_data_url(request.json.get("image") if request.is_json else None)
    if image is None:
        return jsonify(success=False, message="Could not read frame.")
        
    # Get current user samples
    candidates = []
    for sample in current_user.face_samples:
        candidates.append((current_user.id, feature_from_bytes(sample.feature)))
        
    if not candidates:
        return jsonify(success=False, message="You have no registered face samples.")
        
    detections = engine.extract_features(image)
    for bbox, feat in detections:
        faculty_id, score = engine.match(feat, candidates)
        if faculty_id == current_user.id:
            # Match found! Mark present.
            today = date.today()
            session = FacultyAttendanceSession.query.filter_by(session_date=today).first()
            if not session:
                session = FacultyAttendanceSession(taken_by_id=current_user.id, session_date=today)
                db.session.add(session)
                db.session.commit()
                
            existing = FacultyAttendance.query.filter_by(session_id=session.id, faculty_id=current_user.id).first()
            if not existing:
                rec = FacultyAttendance(session_id=session.id, faculty_id=current_user.id, status="present")
                db.session.add(rec)
                db.session.commit()
            elif existing.status != "present":
                existing.status = "present"
                db.session.commit()
                
            return jsonify(success=True, message="Face matched! Marked present for today.")
            
    return jsonify(success=False, message="Face not recognized as you.")

# --- Student Medical Certificates ---

@faculty_bp.route("/medical-certificates")
@login_required
@roles_required(ROLE_FACULTY)
def medical_certificates():
    # Show all uploaded certificates
    certificates = MedicalCertificate.query.order_by(MedicalCertificate.upload_date.desc()).all()
    # Find sessions belonging to this lecturer
    my_sessions = AttendanceSession.query.filter_by(faculty_id=current_user.id).order_by(AttendanceSession.session_date.desc()).limit(20).all()
    return render_template("faculty/medical_certificates.html", certificates=certificates, my_sessions=my_sessions)

@faculty_bp.route("/medical-certificates/download/<int:cert_id>")
@login_required
def download_certificate(cert_id):
    if current_user.role not in ['admin', 'faculty', 'director', 'hod']:
        from flask import abort
        abort(403)
    cert = MedicalCertificate.query.get_or_404(cert_id)
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "instance/certificates")
    return send_from_directory(upload_folder, cert.file_path)

@faculty_bp.route("/medical-certificates/approve/<int:cert_id>", methods=["POST"])
@login_required
@roles_required(ROLE_FACULTY)
def approve_certificate(cert_id):
    cert = MedicalCertificate.query.get_or_404(cert_id)

    # Find all sessions belonging to this faculty in the certificate's date range
    from datetime import date as date_type
    start = cert.start_date if cert.start_date else date_type.today()
    end = cert.end_date if cert.end_date else start

    excused_count = 0
    sessions_in_range = AttendanceSession.query.filter(
        AttendanceSession.faculty_id == current_user.id,
        AttendanceSession.session_date >= start,
        AttendanceSession.session_date <= end
    ).all()

    for session in sessions_in_range:
        existing = Attendance.query.filter_by(session_id=session.id, student_id=cert.student_id).first()
        if existing:
            if existing.status != "excused":
                existing.status = "excused"
                existing.method = "medical"
                excused_count += 1
        else:
            rec = Attendance(session_id=session.id, student_id=cert.student_id, status="excused", method="medical")
            db.session.add(rec)
            excused_count += 1

    cert.status = "approved"
    db.session.commit()

    if excused_count > 0:
        flash(f"Certificate approved. Student marked as excused for {excused_count} session(s) from {start} to {end}.", "success")
    else:
        flash(f"Certificate approved (no sessions found in your classes for {start} to {end}).", "info")

    return redirect(url_for("faculty.medical_certificates"))

