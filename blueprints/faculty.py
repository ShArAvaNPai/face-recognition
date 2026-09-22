"""Faculty Blueprint: applying for leaves."""
from datetime import date
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user

from extensions import db
from models import (LeaveApplication, FacultyAttendanceSession, FacultyAttendance,
                    User, ROLE_FACULTY, ROLE_HOD, ROLE_DIRECTOR, MedicalCertificate,
                    Attendance, AttendanceSession, Subject, Student)
from blueprints.decorators import roles_required, hod_required
from face_engine import engine, feature_from_bytes
from blueprints.imaging import decode_data_url

faculty_bp = Blueprint("faculty", __name__, url_prefix="/faculty")

@faculty_bp.route("/leaves", methods=["GET", "POST"])
@login_required
@roles_required(ROLE_FACULTY, ROLE_HOD, ROLE_DIRECTOR)
def leaves():
    if request.method == "POST":
        start_date_str = request.form.get("start_date")
        end_date_str = request.form.get("end_date")
        reason = request.form.get("reason", "").strip()
        reassign_to_id = request.form.get("reassign_to_id")
        
        try:
            start_date = date.fromisoformat(start_date_str)
            end_date = date.fromisoformat(end_date_str)
            
            if start_date > end_date:
                flash("End date must be after start date.", "danger")
            elif not reason:
                flash("Reason is required.", "danger")
            else:
                leave_days = (end_date - start_date).days + 1
                if current_user.casual_leaves_balance < leave_days:
                    flash(f"Insufficient Casual Leaves. You have {current_user.casual_leaves_balance} but applied for {leave_days} days.", "danger")
                    return redirect(url_for("faculty.leaves"))

                leave = LeaveApplication(
                    user_id=current_user.id,
                    start_date=start_date,
                    end_date=end_date,
                    reason=reason,
                    reassign_to_id=reassign_to_id if reassign_to_id else None
                )
                db.session.add(leave)
                
                # 1. Notification to the applicant
                from models import Notification
                db.session.add(Notification(
                    user_id=current_user.id,
                    message=f"Leave Application Submitted: Your leave request from {start_date} to {end_date} has been submitted (Status: Pending)."
                ))

                # 2. Notification to HOD (if applicant is faculty)
                if current_user.role == ROLE_FACULTY and current_user.department:
                    dept_hods = User.query.filter_by(role=ROLE_HOD, department=current_user.department).all()
                    for h in dept_hods:
                        db.session.add(Notification(
                            user_id=h.id,
                            message=f"Leave Application: {current_user.username} has applied for leave from {start_date} to {end_date} (Reason: {reason})."
                        ))

                # 3. Notification to Director & Admins
                authorities = User.query.filter(User.role.in_([ROLE_DIRECTOR, 'admin'])).all()
                for auth in authorities:
                    if auth.id != current_user.id:
                        db.session.add(Notification(
                            user_id=auth.id,
                            message=f"Leave Application: {current_user.username} ({current_user.role.upper()} · {current_user.department or 'Staff'}) applied for leave from {start_date} to {end_date}."
                        ))

                if reassign_to_id:
                    reassign_user = User.query.get(reassign_to_id)
                    if reassign_user:
                        db.session.add(Notification(
                            user_id=reassign_user.id,
                            message=f"Class Reassignment Pending: {current_user.username} has requested you to substitute their classes from {start_date} to {end_date}. This is pending HOD/Director approval."
                        ))

                db.session.commit()
                if current_user.role == ROLE_HOD:
                    flash("Leave application submitted to the Director successfully. Notifications sent.", "success")
                else:
                    flash("Leave application submitted successfully. Notifications sent.", "success")
                return redirect(url_for("faculty.leaves"))
        except (ValueError, TypeError):
            flash("Invalid dates provided.", "danger")
            
    # GET: show leave history
    my_leaves = LeaveApplication.query.filter_by(user_id=current_user.id).order_by(LeaveApplication.created_at.desc()).all()
    
    # Substitute should be of the same department and include Director and HOD
    dept_filter = current_user.department
    if dept_filter:
        substitute_candidates = User.query.filter(
            User.id != current_user.id,
            db.or_(
                db.and_(User.role.in_([ROLE_FACULTY, ROLE_HOD]), User.department == dept_filter),
                User.role == ROLE_DIRECTOR
            )
        ).order_by(User.username).all()
    else:
        substitute_candidates = User.query.filter(
            User.id != current_user.id,
            User.role.in_([ROLE_FACULTY, ROLE_HOD, ROLE_DIRECTOR])
        ).order_by(User.username).all()

    return render_template("faculty/leaves.html", leaves=my_leaves, today=date.today().isoformat(), faculty_list=substitute_candidates)

# --- Daily Face Attendance ---

@faculty_bp.route("/face-attendance")
@login_required
@roles_required(ROLE_FACULTY, ROLE_HOD, ROLE_DIRECTOR)
def face_attendance():
    today = date.today()
    today_day_name = today.strftime("%A")
    from blueprints.dashboard import is_faculty_absent
    is_on_leave = is_faculty_absent(current_user.id, today)

    session = FacultyAttendanceSession.query.filter_by(session_date=today).first()
    is_present = False
    if session:
        att = FacultyAttendance.query.filter_by(session_id=session.id, faculty_id=current_user.id).first()
        if att and att.status == "present":
            is_present = True
            
    from models import TimetableSlot, TimetableClaim
    slots = TimetableSlot.query.filter_by(day_of_week=today_day_name).order_by(TimetableSlot.slot_time).all()
    today_schedule = []
    for s in slots:
        claim = TimetableClaim.query.filter_by(slot_id=s.id, claim_date=today).first()
        assigned_faculty = claim.claimed_by if claim else (s.subject.faculty if s.subject else None)
        subject_name = claim.subject.name if (claim and claim.subject) else (s.subject.name if s.subject else None)
        if assigned_faculty and assigned_faculty.id == current_user.id:
            today_schedule.append({
                "time": s.slot_time,
                "subject": subject_name or "Class",
                "code": s.subject.code if s.subject else "",
                "is_claimed": bool(claim)
            })

    return render_template("faculty/face_attendance.html", 
                           today=today, today_day_name=today_day_name, 
                           today_schedule=today_schedule,
                           is_present=is_present,
                           is_on_leave=is_on_leave,
                           engine_ready=engine.available)

@faculty_bp.route("/face-attendance/recognize", methods=["POST"])
@login_required
@roles_required(ROLE_FACULTY, ROLE_HOD, ROLE_DIRECTOR)
def face_attendance_recognize():
    from blueprints.dashboard import is_faculty_absent
    if is_faculty_absent(current_user.id, date.today()):
        return jsonify(success=False, message="You are currently on approved leave today and cannot check in.")

    if not engine.available:
        return jsonify(success=False, message="Face models not installed.")
        
    image = decode_data_url(request.json.get("image") if request.is_json else None)
    if image is None:
        return jsonify(success=False, message="Could not read frame.")
        
    candidates = []
    for sample in current_user.face_samples:
        candidates.append((current_user.id, feature_from_bytes(sample.feature)))
        
    if not candidates:
        return jsonify(success=False, message="You have no registered face samples.")
        
    detections = engine.extract_features(image)
    for bbox, feat in detections:
        faculty_id, score = engine.match(feat, candidates)
        if faculty_id == current_user.id:
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

@faculty_bp.route("/face-attendance/code", methods=["POST"])
@login_required
def face_attendance_code():
    from blueprints.dashboard import is_faculty_absent
    if is_faculty_absent(current_user.id, date.today()):
        msg = "You are currently on approved leave today and cannot check in."
        if request.is_json:
            return jsonify(success=False, message=msg)
        else:
            flash(msg, "danger")
            return redirect(url_for("dashboard.index"))

    code = request.json.get("code") if request.is_json else request.form.get("code")
    if code == "1234":
        today = date.today()
        session = FacultyAttendanceSession.query.filter_by(session_date=today).first()
        if not session:
            session = FacultyAttendanceSession(taken_by_id=current_user.id, session_date=today)
            db.session.add(session)
            db.session.flush()
            
        existing = FacultyAttendance.query.filter_by(session_id=session.id, faculty_id=current_user.id).first()
        if not existing:
            rec = FacultyAttendance(session_id=session.id, faculty_id=current_user.id, status="present")
            db.session.add(rec)
        elif existing.status != "present":
            existing.status = "present"
            
        db.session.commit()
        if request.is_json:
            return jsonify(success=True, message="Code accepted! Marked present for today.")
        else:
            flash("Code accepted! Marked present for today.", "success")
            return redirect(url_for("dashboard.index"))
            
    if request.is_json:
        return jsonify(success=False, message="Invalid code.")
    else:
        flash("Invalid code.", "danger")
        return redirect(url_for("dashboard.index"))


# --- Student Medical Certificates (HOD only) ---

@faculty_bp.route("/medical-certificates")
@login_required
@roles_required(ROLE_HOD, "admin")
def medical_certificates():
    # Only HOD (and Admin) can access student medical certificates
    if current_user.role == ROLE_HOD and current_user.department:
        certificates = (MedicalCertificate.query
                        .join(Student)
                        .filter(Student.department == current_user.department)
                        .order_by(MedicalCertificate.upload_date.desc())
                        .all())
    else:
        certificates = MedicalCertificate.query.order_by(MedicalCertificate.upload_date.desc()).all()
        
    return render_template("faculty/medical_certificates.html", certificates=certificates)

@faculty_bp.route("/medical-certificates/download/<int:cert_id>")
@login_required
def download_certificate(cert_id):
    if current_user.role not in ['admin', 'hod', 'director']:
        from flask import abort
        abort(403)
    cert = MedicalCertificate.query.get_or_404(cert_id)
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "instance/certificates")
    return send_from_directory(upload_folder, cert.file_path)

@faculty_bp.route("/medical-certificates/approve/<int:cert_id>", methods=["POST"])
@login_required
@roles_required(ROLE_HOD, "admin")
def approve_certificate(cert_id):
    cert = MedicalCertificate.query.get_or_404(cert_id)

    if current_user.role == ROLE_HOD and current_user.department:
        if cert.student.department and cert.student.department != current_user.department:
            flash("You can only approve medical certificates for students in your department.", "danger")
            return redirect(url_for("faculty.medical_certificates"))

    start = cert.start_date if cert.start_date else date.today()
    end = cert.end_date if cert.end_date else start

    excused_count = 0
    sessions_in_range = AttendanceSession.query.filter(
        AttendanceSession.session_date >= start,
        AttendanceSession.session_date <= end
    ).all()

    student_dept = cert.student.department
    student_class = cert.student.class_name

    for session in sessions_in_range:
        is_relevant = True
        if session.class_name and student_class and session.class_name != student_class and session.class_name != student_dept:
            is_relevant = False

        if is_relevant:
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
        flash(f"Certificate approved. Student {cert.student.name} marked as excused for {excused_count} session(s) from {start} to {end}.", "success")
    else:
        flash(f"Certificate approved for {cert.student.name} ({start} to {end}).", "success")

    return redirect(url_for("faculty.medical_certificates"))


