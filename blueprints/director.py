"""Director Blueprint: managing faculty attendance and leaves."""
from datetime import date
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import (FacultyAttendanceSession, FacultyAttendance, LeaveApplication,
                    User, ROLE_FACULTY, Student, ROLE_STUDENT, Subject)
from blueprints.reports import _student_stats
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
    if current_user.role == 'hod' and current_user.department:
        faculties = User.query.filter_by(role=ROLE_FACULTY, department=current_user.department).order_by(User.username).all()
    else:
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
    if current_user.role == 'hod' and current_user.department:
        faculties = User.query.filter_by(role=ROLE_FACULTY, department=current_user.department).all()
    else:
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

from blueprints.decorators import hod_required

@director_bp.route("/leaves")
@login_required
@hod_required
def leaves_index():
    if current_user.role == 'hod':
        # HOD only reviews faculty in their department, NOT their own leave requests
        if current_user.department:
            leaves = (LeaveApplication.query
                      .join(User)
                      .filter(User.department == current_user.department,
                              User.role == ROLE_FACULTY,
                              User.id != current_user.id)
                      .order_by(LeaveApplication.created_at.desc())
                      .all())
        else:
            leaves = (LeaveApplication.query
                      .join(User)
                      .filter(User.role == ROLE_FACULTY,
                              User.id != current_user.id)
                      .order_by(LeaveApplication.created_at.desc())
                      .all())
    else:
        # Director and Admin review all leaves (including HOD leaves submitted to Director)
        leaves = LeaveApplication.query.join(User).order_by(LeaveApplication.created_at.desc()).all()
    return render_template("director/leaves.html", leaves=leaves)

@director_bp.route("/leaves/<int:leave_id>/update", methods=["POST"])
@login_required
@hod_required
def update_leave(leave_id):
    leave = LeaveApplication.query.get_or_404(leave_id)
    
    # Check permissions: HOD cannot approve their own leave or non-faculty leaves
    if current_user.role == 'hod':
        if leave.user_id == current_user.id:
            flash("HOD cannot approve their own leave. HOD leave must be approved by the Director.", "danger")
            return redirect(url_for("director.leaves_index"))
        if leave.user.role != ROLE_FACULTY:
            flash("HOD can only review faculty leave applications.", "danger")
            return redirect(url_for("director.leaves_index"))
        if current_user.department and leave.user.department != current_user.department:
            flash("You can only review leaves for faculty in your department.", "danger")
            return redirect(url_for("director.leaves_index"))

    action = request.form.get("action")
    if action in ["approved", "rejected"]:
        leave.status = action
        
        # 1. Notify the faculty who applied
        from models import Notification
        db.session.add(Notification(
            user_id=leave.user_id,
            message=f"Leave Application {action.upper()}: Your leave application from {leave.start_date} to {leave.end_date} has been {action} by {current_user.username}."
        ))

        # 2. If approved, notify students in their department
        if action == "approved" and leave.user.department:
            dept_students = User.query.filter_by(role=ROLE_STUDENT, department=leave.user.department).all()
            for st in dept_students:
                db.session.add(Notification(
                    user_id=st.id,
                    message=f"Faculty Notice: {leave.user.username} is on approved leave from {leave.start_date} to {leave.end_date}. Classes will be taken by substitutes."
                ))

        db.session.commit()
        applicant_type = "HOD" if leave.user.role == 'hod' else "Faculty"
        flash(f"Leave application for {applicant_type} {leave.user.username} {action}. Notification sent.", "success")
    return redirect(url_for("director.leaves_index"))

# --- Director Roster Views ---

@director_bp.route("/lecturers")
@login_required
@director_required
def lecturers_index():
    if current_user.role == 'hod' and current_user.department:
        lecturers = User.query.filter_by(role=ROLE_FACULTY, department=current_user.department).order_by(User.username).all()
    else:
        lecturers = User.query.filter_by(role=ROLE_FACULTY).order_by(User.username).all()
    total_sessions = FacultyAttendanceSession.query.count()
    
    rows = []
    for lec in lecturers:
        if total_sessions > 0:
            present = FacultyAttendance.query.filter_by(faculty_id=lec.id, status="present").count()
            pct = round(100.0 * present / total_sessions, 1)
        else:
            present = 0
            pct = 0.0
        rows.append({
            "lecturer": lec,
            "present": present,
            "total": total_sessions,
            "percentage": pct,
            "subjects": Subject.query.filter_by(faculty_id=lec.id).all()
        })
    return render_template("director/lecturers.html", rows=rows)

@director_bp.route("/students")
@login_required
@director_required
def students_index():
    q          = request.args.get("q", "").strip()
    dept_filter  = request.args.get("dept", "").strip()
    year_filter  = request.args.get("year", "").strip() or request.args.get("class_name", "").strip()

    if current_user.role == 'hod' and current_user.department:
        dept_filter = current_user.department

    total_sessions, rows = _student_stats()

    # Apply filters to the already-computed rows
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in r["student"].name.lower()
                                or ql in r["student"].roll_number.lower()]
    if dept_filter:
        rows = [r for r in rows if r["student"].department == dept_filter]
    if year_filter:
        if year_filter in ["1st Year", "1"]:
            rows = [r for r in rows if "1st Year" in (r["student"].class_name or "")]
        elif year_filter in ["2nd Year", "2"]:
            rows = [r for r in rows if "2nd Year" in (r["student"].class_name or "")]
        else:
            rows = [r for r in rows if r["student"].class_name == year_filter]

    # Distinct values for dropdowns
    from models import Student
    if current_user.role == 'hod' and current_user.department:
        all_depts = [current_user.department]
    else:
        all_depts = sorted(set(s.department for s in Student.query.all() if s.department))
    all_years = ["1st Year", "2nd Year"]

    return render_template(
        "director/students.html",
        rows=rows, total_sessions=total_sessions,
        q=q, dept_filter=dept_filter, class_filter=year_filter,
        all_depts=all_depts, all_years=all_years
    )
