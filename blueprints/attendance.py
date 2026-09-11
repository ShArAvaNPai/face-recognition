"""Attendance Management + Face Recognition Module.

- Faculty creates subjects and starts attendance sessions.
- Webcam frames are recognized against stored face samples (multi-face,
  duplicate-prevented) and present students are marked automatically.
- Manual correction and history viewing included.
"""
from datetime import date, datetime

from flask import (Blueprint, render_template, redirect, url_for, request,
                   flash, jsonify)
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import (User, Subject, AttendanceSession, Attendance, Student,
                    ROLE_ADMIN, ROLE_FACULTY, TimetableSlot, TimetableClaim, Notification)
from face_engine import engine, feature_from_bytes
from blueprints.decorators import staff_required
from blueprints.imaging import decode_data_url

attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")


# -- Subjects ----------------------------------------------------------------
@attendance_bp.route("/subjects", methods=["GET", "POST"])
@login_required
@staff_required
def subjects():
    if request.method == "POST":
        action = request.form.get("action", "add")
        if action == "assign_faculty":
            if current_user.role not in [ROLE_ADMIN, "director", "hod"]:
                flash("Only administrators or department heads can reassign subject lecturers.", "danger")
                return redirect(url_for("attendance.subjects"))
            subject_id = request.form.get("subject_id", type=int)
            faculty_id = request.form.get("faculty_id", type=int)
            subject = Subject.query.get(subject_id)
            if subject:
                if faculty_id:
                    lecturer = User.query.filter_by(id=faculty_id, role=ROLE_FACULTY).first()
                    if lecturer:
                        subject.faculty_id = lecturer.id
                        db.session.commit()
                        flash(f"Subject '{subject.name}' assigned to {lecturer.username}.", "success")
                    else:
                        flash("Selected lecturer not found.", "danger")
                else:
                    subject.faculty_id = None
                    db.session.commit()
                    flash(f"Subject '{subject.name}' unassigned.", "info")
            return redirect(url_for("attendance.subjects"))

        code = request.form.get("code", "").strip()
        name = request.form.get("name", "").strip()
        faculty_id = request.form.get("faculty_id", type=int)
        
        # If admin/director/hod picks a lecturer, use it; otherwise default to current_user
        assigned_faculty_id = current_user.id
        if current_user.role in [ROLE_ADMIN, "director", "hod"]:
            if faculty_id:
                assigned_faculty_id = faculty_id
            else:
                assigned_faculty_id = None

        if not code or not name:
            flash("Subject code and name are required.", "danger")
        elif Subject.query.filter_by(code=code).first():
            flash("A subject with that code already exists.", "danger")
        else:
            db.session.add(Subject(code=code, name=name, faculty_id=assigned_faculty_id))
            db.session.commit()
            flash(f"Subject {name} created.", "success")
        return redirect(url_for("attendance.subjects"))

    lecturers = User.query.filter_by(role=ROLE_FACULTY).order_by(User.username).all()
    return render_template("attendance/subjects.html",
                           subjects=Subject.query.order_by(Subject.code).all(),
                           lecturers=lecturers)


# -- Sessions ----------------------------------------------------------------
@attendance_bp.route("/")
@login_required
@staff_required
def index():
    sessions = (AttendanceSession.query
                .order_by(AttendanceSession.session_date.desc(),
                          AttendanceSession.id.desc())
                .all())
    return render_template("attendance/index.html", sessions=sessions)


@attendance_bp.route("/new", methods=["GET", "POST"])
@login_required
@staff_required
def new_session():
    from blueprints.dashboard import is_faculty_absent
    subjects_list = Subject.query.order_by(Subject.code).all()
    available_classes = sorted(list(set([c[0] for c in db.session.query(Student.class_name).distinct().all() if c[0]] + [d[0] for d in db.session.query(Student.department).distinct().all() if d[0]])))
    
    if request.method == "POST":
        session_date = request.form.get("session_date") or date.today().isoformat()
        try:
            sd = date.fromisoformat(session_date)
        except ValueError:
            sd = date.today()

        if is_faculty_absent(current_user.id, sd):
            flash(f"You cannot start class attendance for {sd} because you are on leave / marked absent on that date.", "danger")
            return redirect(url_for("dashboard.index"))

        subject_id = request.form.get("subject_id", type=int)
        class_name = request.form.get("class_name", "").strip()
        takeover_confirmed = request.form.get("takeover_confirmed") == "true"
        
        if not subject_id or not Subject.query.get(subject_id):
            flash("Please select a valid subject.", "danger")
            return redirect(url_for("attendance.new_session"))
            
        # Handle takeover logic if confirmed
        if takeover_confirmed:
            slot_id = request.form.get("takeover_slot_id", type=int)
            if slot_id:
                slot = TimetableSlot.query.get(slot_id)
                if slot and slot.subject and slot.subject.faculty_id:
                    # Create claim
                    claim = TimetableClaim(
                        slot_id=slot.id,
                        claim_date=sd,
                        claimed_by_id=current_user.id,
                        subject_id=subject_id,
                        status="pending"
                    )
                    db.session.add(claim)
                    db.session.flush()
                    # Notify
                    notif = Notification(
                        user_id=slot.subject.faculty_id,
                        message=f"{current_user.username} has taken your class '{slot.subject.name}' at {slot.slot_time} on {sd}.",
                        claim_id=claim.id
                    )
                    db.session.add(notif)
                    flash(f"Class takeover requested. {slot.subject.faculty.username} has been notified.", "info")

        s = AttendanceSession(
            subject_id=subject_id,
            faculty_id=current_user.id,
            class_name=class_name,
            session_date=sd,
        )
        db.session.add(s)
        db.session.commit()
        flash("Attendance session started.", "success")
        return redirect(url_for("attendance.take", session_id=s.id))

    if is_faculty_absent(current_user.id, date.today()):
        flash("You are currently on leave / marked absent today and cannot start class attendance sessions.", "danger")
        return redirect(url_for("dashboard.index"))
        
    if not subjects_list:
        flash("Create a subject first.", "warning")
        return redirect(url_for("attendance.subjects"))
        
    # Auto-assign logic based on current time
    now = datetime.now()
    current_day = now.strftime("%A")
    current_hour = now.hour
    current_time_slot = None
    
    if 9 <= current_hour < 10: current_time_slot = "09:00 - 10:00"
    elif 10 <= current_hour < 11: current_time_slot = "10:00 - 11:00"
    elif 11 <= current_hour < 12: current_time_slot = "11:00 - 12:00"
    elif 13 <= current_hour < 14: current_time_slot = "13:00 - 14:00"
    elif 14 <= current_hour < 15: current_time_slot = "14:00 - 15:00"
    elif 15 <= current_hour < 16: current_time_slot = "15:00 - 16:00"
    
    auto_slot = None
    if current_time_slot:
        # Prefer the current user's slot first
        auto_slot = TimetableSlot.query.join(Subject).filter(
            TimetableSlot.day_of_week == current_day,
            TimetableSlot.slot_time == current_time_slot,
            Subject.faculty_id == current_user.id
        ).first()
        
        # If not found, get any slot at this time (could be someone else's)
        if not auto_slot:
            dept = current_user.department or "MCA"
            auto_slot = TimetableSlot.query.filter_by(
                department=dept,
                day_of_week=current_day,
                slot_time=current_time_slot
            ).first()

    return render_template("attendance/new_session.html",
                           subjects=subjects_list, classes=available_classes, 
                           today=date.today().isoformat(),
                           auto_slot=auto_slot, current_user_id=current_user.id)


@attendance_bp.route("/<int:session_id>/take", methods=["GET", "POST"])
@login_required
@staff_required
def take(session_id):
    session = AttendanceSession.query.get_or_404(session_id)
    from blueprints.dashboard import is_faculty_absent
    if session.faculty_id == current_user.id and is_faculty_absent(current_user.id, session.session_date):
        flash("You cannot take attendance for this session because you are on leave / marked absent on that date.", "danger")
        return redirect(url_for("dashboard.index"))
    
    if request.method == "POST" and "update_class" in request.form:
        new_class = request.form.get("class_name", "").strip()
        session.class_name = new_class
        db.session.commit()
        flash(f"Session class updated to '{new_class or 'All Classes'}'.", "info")
        return redirect(url_for("attendance.take", session_id=session.id))
        
    req_class = request.args.get("class_name")
    if req_class is not None and req_class != session.class_name:
        session.class_name = req_class
        db.session.commit()

    present_ids = {a.student_id for a in session.records if a.status == "present"}
    
    query = Student.query
    if session.class_name:
        query = query.filter(or_(Student.class_name == session.class_name, Student.department == session.class_name))
    elif current_user.role == "hod" and current_user.department:
        query = query.filter_by(department=current_user.department)

    students = query.order_by(Student.roll_number).all()
    available_classes = sorted(list(set([c[0] for c in db.session.query(Student.class_name).distinct().all() if c[0]] + [d[0] for d in db.session.query(Student.department).distinct().all() if d[0]])))

    return render_template("attendance/take.html", session=session,
                           students=students, present_ids=present_ids,
                           available_classes=available_classes,
                           engine_ready=engine.available)


def _load_candidates():
    """Return list of (student_id, feature_vector) for all stored samples."""
    candidates = []
    students = Student.query.all()
    for s in students:
        for sample in s.face_samples:
            candidates.append((s.id, feature_from_bytes(sample.feature)))
    return candidates


def _mark_present(session_id, student_id, method="face"):
    """Insert a present record; ignore if already marked (duplicate prevention)."""
    existing = Attendance.query.filter_by(
        session_id=session_id, student_id=student_id).first()
    if existing:
        if existing.status != "present":
            existing.status = "present"
            existing.method = method
            db.session.commit()
        return False  # already counted
    rec = Attendance(session_id=session_id, student_id=student_id,
                     status="present", method=method)
    db.session.add(rec)
    try:
        db.session.commit()
        return True
    except IntegrityError:
        db.session.rollback()
        return False


@attendance_bp.route("/<int:session_id>/recognize", methods=["POST"])
@login_required
@staff_required
def recognize(session_id):
    """AJAX: recognize all faces in a webcam frame and mark them present."""
    AttendanceSession.query.get_or_404(session_id)
    if not engine.available:
        return jsonify(success=False, message="Face models not installed.", marked=[])

    image = decode_data_url(request.json.get("image") if request.is_json else None)
    if image is None:
        return jsonify(success=False, message="Could not read frame.", marked=[])

    candidates = _load_candidates()
    if not candidates:
        return jsonify(success=False,
                       message="No registered faces yet.", marked=[])

    detections = engine.extract_features(image)
    marked, seen = [], set()
    faces_found = len(detections)
    for bbox, feat in detections:
        student_id, score = engine.match(feat, candidates)
        if student_id is None or student_id in seen:
            continue
        seen.add(student_id)
        newly = _mark_present(session_id, student_id, method="face")
        student = Student.query.get(student_id)
        marked.append({
            "student_id": student_id,
            "roll_number": student.roll_number,
            "name": student.name,
            "score": round(float(score), 3),
            "newly_marked": newly,
            "bbox": bbox,
        })
    return jsonify(success=True, faces_found=faces_found,
                   recognized=len(marked), marked=marked)


@attendance_bp.route("/<int:session_id>/toggle", methods=["POST"])
@login_required
@staff_required
def toggle(session_id):
    """Manual attendance correction (mark/unmark a student)."""
    AttendanceSession.query.get_or_404(session_id)
    student_id = request.form.get("student_id", type=int)
    present = request.form.get("present") == "1"
    student = Student.query.get_or_404(student_id)
    if present:
        _mark_present(session_id, student_id, method="manual")
        flash(f"Marked {student.name} present.", "success")
    else:
        rec = Attendance.query.filter_by(
            session_id=session_id, student_id=student_id).first()
        if rec:
            db.session.delete(rec)
            db.session.commit()
        flash(f"Unmarked {student.name}.", "info")
    return redirect(url_for("attendance.take", session_id=session_id))


@attendance_bp.route("/<int:session_id>/history")
@login_required
@staff_required
def history(session_id):
    session = AttendanceSession.query.get_or_404(session_id)
    present_ids = {a.student_id for a in session.records if a.status == "present"}
    query = Student.query
    if session.class_name:
        query = query.filter(or_(Student.class_name == session.class_name, Student.department == session.class_name))
    elif current_user.role == "hod" and current_user.department:
        query = query.filter_by(department=current_user.department)
    students = query.order_by(Student.roll_number).all()
    return render_template("attendance/history.html", session=session,
                           students=students, present_ids=present_ids)
