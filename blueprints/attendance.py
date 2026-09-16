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
                    ROLE_ADMIN, ROLE_FACULTY, ROLE_DIRECTOR, ROLE_HOD,
                    TimetableSlot, TimetableClaim, Notification)
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
        dept = request.form.get("department", "").strip()
        year = request.form.get("year", type=int) or 1
        if year not in [1, 2]:
            year = 1
        faculty_id = request.form.get("faculty_id", type=int)
        
        if current_user.role == ROLE_HOD and current_user.department:
            dept = current_user.department
        elif not dept:
            dept = "MCA"

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
            db.session.add(Subject(code=code, name=name, department=dept, year=year, faculty_id=assigned_faculty_id))
            db.session.commit()
            flash(f"Subject {name} ({dept} - {year}{'st' if year == 1 else 'nd'} Year) created.", "success")
        return redirect(url_for("attendance.subjects", dept=dept, year=year))

    dept_filter = request.args.get("dept", "").strip()
    year_filter = request.args.get("year", type=int)

    query = Subject.query
    if current_user.role == ROLE_HOD and current_user.department:
        query = query.filter(
            (Subject.department == current_user.department) |
            (Subject.code.ilike(f"{current_user.department}%"))
        )
        lecturers = User.query.filter_by(role=ROLE_FACULTY, department=current_user.department).order_by(User.username).all()
    else:
        if dept_filter:
            query = query.filter_by(department=dept_filter)
        lecturers = User.query.filter_by(role=ROLE_FACULTY).order_by(User.username).all()

    if year_filter in [1, 2]:
        query = query.filter_by(year=year_filter)

    subjects_list = query.order_by(Subject.department, Subject.year, Subject.code).all()

    return render_template("attendance/subjects.html",
                           subjects=subjects_list,
                           lecturers=lecturers,
                           dept_filter=dept_filter,
                           year_filter=year_filter)



# -- Sessions ----------------------------------------------------------------
@attendance_bp.route("/")
@login_required
@staff_required
def index():
    sessions = (AttendanceSession.query
                .order_by(AttendanceSession.session_date.desc(),
                          AttendanceSession.id.desc())
                .all())
    return render_template("attendance/index.html", sessions=sessions, today_date=date.today())


@attendance_bp.route("/new", methods=["GET", "POST"])
@login_required
@staff_required
def new_session():
    if current_user.role == ROLE_ADMIN:
        flash("Administrators cannot conduct or start class attendance sessions.", "warning")
        return redirect(url_for("dashboard.index"))

    from blueprints.dashboard import is_faculty_absent
    
    # Filter available subjects based on user role
    if current_user.role in [ROLE_FACULTY, "faculty"]:
        subjects_list = Subject.query.filter_by(faculty_id=current_user.id).order_by(Subject.code).all()
    elif current_user.role in [ROLE_DIRECTOR, "director"]:
        # Director should only take Research
        subjects_list = Subject.query.filter(
            (Subject.code.ilike("%research%")) | (Subject.name.ilike("%research%")) | (Subject.faculty_id == current_user.id)
        ).order_by(Subject.code).all()
        if not subjects_list:
            res_sub = Subject.query.filter_by(code="research").first()
            if res_sub:
                subjects_list = [res_sub]
    elif current_user.role == "hod" and current_user.department:
        subjects_list = Subject.query.filter(
            (Subject.faculty_id == current_user.id) |
            (Subject.code.ilike(f"{current_user.department}%")) |
            (Subject.faculty.has(User.department == current_user.department))
        ).order_by(Subject.code).all()
        if not subjects_list:
            subjects_list = Subject.query.order_by(Subject.code).all()
    else:
        subjects_list = Subject.query.order_by(Subject.code).all()

    available_classes = sorted(list(set([c[0] for c in db.session.query(Student.class_name).distinct().all() if c[0]] + [d[0] for d in db.session.query(Student.department).distinct().all() if d[0]])))
    
    if request.method == "POST":
        session_date = request.form.get("session_date") or date.today().isoformat()
        try:
            sd = date.fromisoformat(session_date)
        except ValueError:
            sd = date.today()

        # Enforce current day only
        if sd != date.today():
            flash("Attendance can only be created for the current day.", "danger")
            return redirect(url_for("attendance.new_session"))

        # Enforce college hours (9:00 AM to 5:00 PM / 17:00)
        now_hour = datetime.now().hour
        if not (9 <= now_hour < 17):
            flash("Attendance can only be started during college working hours (09:00 AM – 05:00 PM).", "danger")
            return redirect(url_for("attendance.new_session"))

        if is_faculty_absent(current_user.id, sd):
            flash(f"You cannot start class attendance for {sd} because you are on leave / marked absent on that date.", "danger")
            return redirect(url_for("dashboard.index"))

        subject_id = request.form.get("subject_id", type=int)
        # Default to faculty/director's only assigned subject if not explicitly supplied
        if not subject_id and (current_user.role in [ROLE_FACULTY, ROLE_DIRECTOR, "faculty", "director"]) and len(subjects_list) == 1:
            subject_id = subjects_list[0].id

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
        if current_user.role == ROLE_FACULTY:
            flash("No subject has been assigned to you. Please contact your HOD or Admin.", "warning")
            return redirect(url_for("dashboard.index"))
        else:
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
        
        # If not found, get any slot at this time (could be someone else's) for staff/admin
        if not auto_slot and current_user.role in ['admin', 'director', 'hod']:
            dept = current_user.department or "MCA"
            auto_slot = TimetableSlot.query.filter_by(
                department=dept,
                day_of_week=current_day,
                slot_time=current_time_slot
            ).first()

    req_subject_id = request.args.get("subject_id", type=int)
    req_class_name = request.args.get("class_name", "").strip()

    return render_template("attendance/new_session.html",
                           subjects=subjects_list, classes=available_classes, 
                           today=date.today().isoformat(),
                           auto_slot=auto_slot, current_user_id=current_user.id,
                           selected_subject_id=req_subject_id,
                           selected_class_name=req_class_name)


@attendance_bp.route("/<int:session_id>/take", methods=["GET", "POST"])
@login_required
@staff_required
def take(session_id):
    if current_user.role == ROLE_ADMIN:
        flash("Administrators cannot conduct or take class attendance. You can view session history.", "warning")
        return redirect(url_for("attendance.history", session_id=session_id))

    session = AttendanceSession.query.get_or_404(session_id)
    if session.session_date != date.today():
        flash("Attendance can only be taken for the current day. Other dates are read-only.", "warning")
        return redirect(url_for("attendance.history", session_id=session.id))

    now_hour = datetime.now().hour
    if not (9 <= now_hour < 17):
        flash("Attendance can only be taken during college working hours (09:00 AM – 05:00 PM).", "warning")
        return redirect(url_for("attendance.history", session_id=session.id))

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


def _load_candidates(class_name=None):
    """Return list of (student_id, feature_vector) for stored samples of students in class_name."""
    candidates = []
    query = Student.query
    if class_name:
        query = query.filter(or_(Student.class_name == class_name, Student.department == class_name))
    students = query.all()
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
    try:
        session = AttendanceSession.query.get_or_404(session_id)
        if session.session_date != date.today():
            return jsonify(success=False, message="Attendance can only be taken on the current day.", marked=[])

        if not engine.available:
            return jsonify(success=False, message="Face models not installed.", marked=[])

        image = decode_data_url(request.json.get("image") if request.is_json else None)
        if image is None:
            return jsonify(success=False, message="Could not read frame.", marked=[])

        candidates = _load_candidates(class_name=session.class_name)
        if not candidates:
            return jsonify(success=False,
                           message=f"No registered faces for {session.class_name or 'this class'} yet.", marked=[])

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
            if student:
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
    except Exception as e:
        return jsonify(success=False, message=f"Recognition error: {str(e)}", marked=[])



@attendance_bp.route("/<int:session_id>/toggle", methods=["POST"])
@login_required
@staff_required
def toggle(session_id):
    """Manual attendance correction (mark/unmark a student)."""
    session = AttendanceSession.query.get_or_404(session_id)
    if session.session_date != date.today():
        flash("Attendance can only be modified on the current day.", "warning")
        return redirect(url_for("attendance.history", session_id=session.id))

    now_hour = datetime.now().hour
    if not (9 <= now_hour < 17):
        flash("Attendance can only be modified during college working hours (09:00 AM – 05:00 PM).", "warning")
        return redirect(url_for("attendance.history", session_id=session.id))

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


@attendance_bp.route("/<int:session_id>/finalize", methods=["POST"])
@login_required
@staff_required
def finalize_session(session_id):
    """Finalize attendance for a session and notify parents of absent students."""
    session = AttendanceSession.query.get_or_404(session_id)
    if session.session_date != date.today():
        flash("Can only finalize attendance for the current day.", "warning")
        return redirect(url_for("attendance.take", session_id=session_id))

    present_ids = {a.student_id for a in session.records if a.status == "present"}
    query = Student.query
    if session.class_name:
        query = query.filter(or_(Student.class_name == session.class_name, Student.department == session.class_name))
    elif current_user.role == "hod" and current_user.department:
        query = query.filter_by(department=current_user.department)
    students = query.all()

    from utils.notifications import notify_parent_absence

    notified_count = 0
    for s in students:
        if s.id not in present_ids:
            # Student is absent
            existing = Attendance.query.filter_by(session_id=session_id, student_id=s.id).first()
            if not existing:
                rec = Attendance(session_id=session_id, student_id=s.id, status="absent", method="manual")
                db.session.add(rec)

            if s.parent_user:
                notify_parent_absence(
                    student=s,
                    subject_name=session.subject.name,
                    session_date=session.session_date,
                )
                notified_count += 1

    db.session.commit()
    flash(f"Attendance finalized. {notified_count} parent(s) notified via notification panel.", "success")
    return redirect(url_for("attendance.history", session_id=session_id))



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
                           students=students, present_ids=present_ids,
                           today_date=date.today())
