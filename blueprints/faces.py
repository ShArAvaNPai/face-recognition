"""Face Registration Module: capture/upload face samples, encode and store."""
from flask import (Blueprint, render_template, redirect, url_for, request,
                   flash, jsonify)
from flask_login import login_required

from extensions import db
from models import Student, FaceSample
from face_engine import engine, feature_to_bytes
from blueprints.decorators import staff_required
from blueprints.imaging import decode_data_url, decode_file_storage

faces_bp = Blueprint("faces", __name__, url_prefix="/faces")


@faces_bp.route("/")
@login_required
@staff_required
def index():
    students = Student.query.order_by(Student.roll_number).all()
    return render_template("faces/index.html", students=students,
                           engine_ready=engine.available)


@faces_bp.route("/<int:student_id>")
@login_required
@staff_required
def register(student_id):
    student = Student.query.get_or_404(student_id)
    return render_template("faces/register.html", student=student,
                           engine_ready=engine.available)


def _store_sample(student, image_bgr):
    """Detect the largest face, encode it, and persist a FaceSample. Returns (ok, msg)."""
    if image_bgr is None:
        return False, "Could not read the image."
    if not engine.available:
        return False, "Face models are not installed. Run download_models.py."
    feature = engine.best_single_feature(image_bgr)
    if feature is None:
        return False, "No face detected in the image. Try again with a clear, well-lit face."
    sample = FaceSample(student_id=student.id, feature=feature_to_bytes(feature))
    db.session.add(sample)
    db.session.commit()
    return True, "Face sample saved."


@faces_bp.route("/<int:student_id>/capture", methods=["POST"])
@login_required
@staff_required
def capture(student_id):
    """AJAX endpoint: receives a base64 webcam frame, stores one sample."""
    student = Student.query.get_or_404(student_id)
    image = decode_data_url(request.json.get("image") if request.is_json else None)
    ok, msg = _store_sample(student, image)
    return jsonify(success=ok, message=msg, sample_count=len(student.face_samples))


@faces_bp.route("/<int:student_id>/upload", methods=["POST"])
@login_required
@staff_required
def upload(student_id):
    """Form upload of one or more image files as face samples."""
    student = Student.query.get_or_404(student_id)
    files = request.files.getlist("images")
    saved, failed = 0, 0
    for f in files:
        image = decode_file_storage(f)
        ok, _ = _store_sample(student, image)
        saved += ok
        failed += (not ok)
    if saved:
        flash(f"Saved {saved} face sample(s).", "success")
    if failed:
        flash(f"{failed} image(s) had no detectable face.", "warning")
    if not files:
        flash("No files selected.", "warning")
    return redirect(url_for("faces.register", student_id=student.id))


@faces_bp.route("/sample/<int:sample_id>/delete", methods=["POST"])
@login_required
@staff_required
def delete_sample(sample_id):
    sample = FaceSample.query.get_or_404(sample_id)
    student_id = sample.student_id
    db.session.delete(sample)
    db.session.commit()
    flash("Face sample removed.", "info")
    return redirect(url_for("faces.register", student_id=student_id))
