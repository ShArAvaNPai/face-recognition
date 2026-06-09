"""Attendance Management + Face Recognition Module.

- Faculty creates subjects and starts attendance sessions.
- Webcam frames are recognized against stored face samples (multi-face,
  duplicate-prevented) and present students are marked automatically.
- Manual correction and history viewing included.
"""
from datetime import date

from flask import (Blueprint, render_template, redirect, url_for, request,
                   flash, jsonify)
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import (Subject, AttendanceSession, Attendance, Student,
                    ROLE_ADMIN, ROLE_FACULTY)
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
        code = request.form.get("code", "").strip()
        name = request.form.get("name", "").strip()
        if not code or not name:
            flash("Subject code and name are required.", "danger")
        elif Subject.query.filter_by(code=code).first():
            flash("A subject with that code already exists.", "danger")
        else:
            db.session.add(Subject(code=code, name=name, faculty_id=current_user.id))
            db.session.commit()
            flash(f"Subject {name} created.", "success")
        return redirect(url_for("attendance.subjects"))
    return render_template("attendance/subjects.html",
                           subjects=Subject.query.order_by(Subject.code).all())


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
    subjects_list = Subject.query.order_by(Subject.code).all()
    if request.method == "POST":
        subject_id = request.form.get("subject_id", type=int)
        if not subject_id or not Subject.query.get(subject_id):
            flash("Please select a valid subject.", "danger")
        else:
            session_date = request.form.get("session_date") or date.today().isoformat()
            try:
                sd = date.fromisoformat(session_date)
            except ValueError:
                sd = date.today()
            s = AttendanceSession(
                subject_id=subject_id,
                faculty_id=current_user.id,
                class_name=request.form.get("class_name", "").strip(),
                session_date=sd,
            )
            db.session.add(s)
            db.session.commit()
            flash("Attendance session started.", "success")
            return redirect(url_for("attendance.take", session_id=s.id))
    if not subjects_list:
        flash("Create a subject first.", "warning")
        return redirect(url_for("attendance.subjects"))
    return render_template("attendance/new_session.html",
                           subjects=subjects_list, today=date.today().isoformat())


@attendance_bp.route("/<int:session_id>/take")
@login_required
@staff_required
def take(session_id):
    session = AttendanceSession.query.get_or_404(session_id)
    present_ids = {a.student_id for a in session.records if a.status == "present"}
    students = Student.query.order_by(Student.roll_number).all()
    return render_template("attendance/take.html", session=session,
                           students=students, present_ids=present_ids,
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
    students = Student.query.order_by(Student.roll_number).all()
    return render_template("attendance/history.html", session=session,
                           students=students, present_ids=present_ids)
