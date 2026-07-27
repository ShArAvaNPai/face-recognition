"""Face Registration Module: capture/upload face samples, encode and store."""
from flask import (Blueprint, render_template, redirect, url_for, request,
                   flash, jsonify)
from flask_login import login_required

from extensions import db
from models import Student, FaceSample, User, ROLE_FACULTY
from face_engine import engine, feature_to_bytes
from blueprints.decorators import admin_required
from blueprints.imaging import decode_data_url, decode_file_storage

faces_bp = Blueprint("faces", __name__, url_prefix="/faces")


@faces_bp.route("/")
@login_required
@admin_required
def index():
    students = Student.query.order_by(Student.roll_number).all()
    faculties = User.query.filter_by(role=ROLE_FACULTY).order_by(User.username).all()
    return render_template("faces/index.html", students=students, faculties=faculties,
                           engine_ready=engine.available)


@faces_bp.route("/student/<int:student_id>")
@login_required
@admin_required
def register(student_id):
    student = Student.query.get_or_404(student_id)
    return render_template("faces/register.html",
                           target_name=student.name,
                           target_identifier=student.roll_number,
                           face_samples=student.face_samples,
                           capture_url=url_for('faces.capture', student_id=student.id),
                           upload_url=url_for('faces.upload', student_id=student.id),
                           engine_ready=engine.available)


@faces_bp.route("/faculty/<int:user_id>")
@login_required
@admin_required
def register_faculty(user_id):
    user = User.query.filter_by(id=user_id, role=ROLE_FACULTY).first_or_404()
    return render_template("faces/register.html",
                           target_name=user.username,
                           target_identifier=user.username,
                           face_samples=user.face_samples,
                           capture_url=url_for('faces.capture_faculty', user_id=user.id),
                           upload_url=url_for('faces.upload_faculty', user_id=user.id),
                           engine_ready=engine.available)


def _store_sample(target, image_bgr, is_faculty=False):
    """Detect the largest face, encode it, and persist a FaceSample. Returns (ok, msg)."""
    if image_bgr is None:
        return False, "Could not read the image."
    if not engine.available:
        return False, "Face models are not installed. Run download_models.py."
    feature = engine.best_single_feature(image_bgr)
    if feature is None:
        return False, "No face detected in the image. Try again with a clear, well-lit face."
    
    if is_faculty:
        sample = FaceSample(user_id=target.id, feature=feature_to_bytes(feature))
    else:
        sample = FaceSample(student_id=target.id, feature=feature_to_bytes(feature))
        
    db.session.add(sample)
    db.session.commit()
    return True, "Face sample saved."


@faces_bp.route("/student/<int:student_id>/capture", methods=["POST"])
@login_required
@admin_required
def capture(student_id):
    """AJAX endpoint: receives a base64 webcam frame, stores one sample."""
    student = Student.query.get_or_404(student_id)
    image = decode_data_url(request.json.get("image") if request.is_json else None)
    ok, msg = _store_sample(student, image, is_faculty=False)
    return jsonify(success=ok, message=msg, sample_count=len(student.face_samples))


@faces_bp.route("/faculty/<int:user_id>/capture", methods=["POST"])
@login_required
@admin_required
def capture_faculty(user_id):
    """AJAX endpoint: receives a base64 webcam frame, stores one sample."""
    user = User.query.filter_by(id=user_id, role=ROLE_FACULTY).first_or_404()
    image = decode_data_url(request.json.get("image") if request.is_json else None)
    ok, msg = _store_sample(user, image, is_faculty=True)
    return jsonify(success=ok, message=msg, sample_count=len(user.face_samples))


@faces_bp.route("/student/<int:student_id>/upload", methods=["POST"])
@login_required
@admin_required
def upload(student_id):
    """Form upload of one or more image files as face samples."""
    student = Student.query.get_or_404(student_id)
    files = request.files.getlist("images")
    saved, failed = 0, 0
    for f in files:
        image = decode_file_storage(f)
        ok, _ = _store_sample(student, image, is_faculty=False)
        saved += ok
        failed += (not ok)
    if saved:
        flash(f"Saved {saved} face sample(s).", "success")
    if failed:
        flash(f"{failed} image(s) had no detectable face.", "warning")
    if not files:
        flash("No files selected.", "warning")
    return redirect(url_for("faces.register", student_id=student.id))


@faces_bp.route("/faculty/<int:user_id>/upload", methods=["POST"])
@login_required
@admin_required
def upload_faculty(user_id):
    """Form upload of one or more image files as face samples."""
    user = User.query.filter_by(id=user_id, role=ROLE_FACULTY).first_or_404()
    files = request.files.getlist("images")
    saved, failed = 0, 0
    for f in files:
        image = decode_file_storage(f)
        ok, _ = _store_sample(user, image, is_faculty=True)
        saved += ok
        failed += (not ok)
    if saved:
        flash(f"Saved {saved} face sample(s).", "success")
    if failed:
        flash(f"{failed} image(s) had no detectable face.", "warning")
    if not files:
        flash("No files selected.", "warning")
    return redirect(url_for("faces.register_faculty", user_id=user.id))


@faces_bp.route("/sample/<int:sample_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_sample(sample_id):
    sample = FaceSample.query.get_or_404(sample_id)
    student_id = sample.student_id
    user_id = sample.user_id
    db.session.delete(sample)
    db.session.commit()
    flash("Face sample removed.", "info")
    if user_id:
        return redirect(url_for("faces.register_faculty", user_id=user_id))
    return redirect(url_for("faces.register", student_id=student_id))
