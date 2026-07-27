"""Director Blueprint: managing faculty attendance and leaves."""
from datetime import date
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import FacultyAttendanceSession, FacultyAttendance, LeaveApplication, User, ROLE_FACULTY
from blueprints.decorators import director_required
from face_engine import engine, feature_from_bytes
from blueprints.imaging import decode_data_url

director_bp = Blueprint("director", __name__, url_prefix="/director")

# --- Faculty Attendance ---

@director_bp.route("/faculty-attendance")
@login_required
@director_required
def faculty_attendance_index():
    sessions = FacultyAttendanceSession.query.order_by(FacultyAttendanceSession.session_date.desc()).all()
    return render_template("director/faculty_attendance.html", sessions=sessions)

@director_bp.route("/faculty-attendance/new", methods=["POST"])
@login_required
@director_required
def new_faculty_session():
    session_date = request.form.get("session_date") or date.today().isoformat()
    try:
        sd = date.fromisoformat(session_date)
    except ValueError:
        sd = date.today()
        
    s = FacultyAttendanceSession(taken_by_id=current_user.id, session_date=sd)
    db.session.add(s)
    db.session.commit()
    flash("Faculty attendance session started.", "success")
    return redirect(url_for("director.take_faculty_attendance", session_id=s.id))

@director_bp.route("/faculty-attendance/<int:session_id>/take")
@login_required
@director_required
def take_faculty_attendance(session_id):
    session = FacultyAttendanceSession.query.get_or_404(session_id)
    faculties = User.query.filter_by(role=ROLE_FACULTY).order_by(User.username).all()
    present_ids = {a.faculty_id for a in session.records if a.status == "present"}
    return render_template("director/take_faculty_attendance.html", 
                           session=session, faculties=faculties, present_ids=present_ids,
                           engine_ready=engine.available)

@director_bp.route("/faculty-attendance/<int:session_id>/toggle", methods=["POST"])
@login_required
@director_required
def toggle_faculty_attendance(session_id):
    session = FacultyAttendanceSession.query.get_or_404(session_id)
    faculty_id = request.form.get("faculty_id", type=int)
    present = request.form.get("present") == "1"
    
    faculty = User.query.get_or_404(faculty_id)
    
    if present:
        # mark present
        existing = FacultyAttendance.query.filter_by(session_id=session_id, faculty_id=faculty_id).first()
        if existing:
            existing.status = "present"
        else:
            rec = FacultyAttendance(session_id=session_id, faculty_id=faculty_id, status="present")
            db.session.add(rec)
        db.session.commit()
        flash(f"Marked {faculty.username} present.", "success")
    else:
        # unmark
        rec = FacultyAttendance.query.filter_by(session_id=session_id, faculty_id=faculty_id).first()
        if rec:
            db.session.delete(rec)
            db.session.commit()
        flash(f"Unmarked {faculty.username}.", "info")
        
    return redirect(url_for("director.take_faculty_attendance", session_id=session_id))


def _load_faculty_candidates():
    """Return list of (faculty_id, feature_vector) for all stored lecturer samples."""
    candidates = []
    faculties = User.query.filter_by(role=ROLE_FACULTY).all()
    for f in faculties:
        for sample in f.face_samples:
            candidates.append((f.id, feature_from_bytes(sample.feature)))
    return candidates


def _mark_faculty_present(session_id, faculty_id):
    """Insert a present record for faculty; ignore if already marked."""
    existing = FacultyAttendance.query.filter_by(
        session_id=session_id, faculty_id=faculty_id).first()
    if existing:
        if existing.status != "present":
            existing.status = "present"
            db.session.commit()
            return True
        return False  # already marked present
    rec = FacultyAttendance(session_id=session_id, faculty_id=faculty_id, status="present")
    db.session.add(rec)
    db.session.commit()
    return True


@director_bp.route("/faculty-attendance/<int:session_id>/recognize", methods=["POST"])
@login_required
@director_required
def recognize_faculty(session_id):
    """AJAX: recognize all faces in a webcam frame and mark them present for faculty."""
    FacultyAttendanceSession.query.get_or_404(session_id)
    if not engine.available:
        return jsonify(success=False, message="Face models not installed.", marked=[])

    image = decode_data_url(request.json.get("image") if request.is_json else None)
    if image is None:
        return jsonify(success=False, message="Could not read frame.", marked=[])

    candidates = _load_faculty_candidates()
    if not candidates:
        return jsonify(success=False, message="No registered lecturer faces yet.", marked=[])

    detections = engine.extract_features(image)
    marked, seen = [], set()
    faces_found = len(detections)
    for bbox, feat in detections:
        faculty_id, score = engine.match(feat, candidates)
        if faculty_id is None or faculty_id in seen:
            continue
        seen.add(faculty_id)
        newly = _mark_faculty_present(session_id, faculty_id)
        faculty = User.query.get(faculty_id)
        marked.append({
            "faculty_id": faculty_id,
            "username": faculty.username,
            "score": round(float(score), 3),
            "newly_marked": newly,
            "bbox": bbox,
        })
    return jsonify(success=True, faces_found=faces_found,
                   recognized=len(marked), marked=marked)

# --- Leave Applications ---

@director_bp.route("/leaves")
@login_required
@director_required
def leaves_index():
    leaves = LeaveApplication.query.order_by(LeaveApplication.created_at.desc()).all()
    return render_template("director/leaves.html", leaves=leaves)

@director_bp.route("/leaves/<int:leave_id>/update", methods=["POST"])
@login_required
@director_required
def update_leave(leave_id):
    leave = LeaveApplication.query.get_or_404(leave_id)
    action = request.form.get("action")
    if action in ["approved", "rejected"]:
        leave.status = action
        db.session.commit()
        flash(f"Leave application {action}.", "success")
    return redirect(url_for("director.leaves_index"))
