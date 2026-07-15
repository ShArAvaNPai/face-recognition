"""Dashboard: a role-aware landing page with quick stats."""
import os
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user

from models import (Student, Subject, AttendanceSession, Attendance, User,
                    FaceSample, MedicalCertificate, ROLE_STUDENT)

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    if current_user.role == ROLE_STUDENT:
        return _student_dashboard()
    return _staff_dashboard()


def _staff_dashboard():
    stats = {
        "students": Student.query.count(),
        "faces": FaceSample.query.count(),
        "subjects": Subject.query.count(),
        "sessions": AttendanceSession.query.count(),
        "users": User.query.count(),
    }
    recent_sessions = (AttendanceSession.query
                       .order_by(AttendanceSession.id.desc())
                       .limit(5).all())
    return render_template("dashboard/staff.html", stats=stats,
                           recent_sessions=recent_sessions)


def _student_dashboard():
    student = current_user.student
    present = total = pct = 0
    if student:
        total = AttendanceSession.query.count()
        present = Attendance.query.filter_by(
            student_id=student.id, status="present").count()
        pct = round(100.0 * present / total, 1) if total else 0.0
    return render_template("dashboard/student.html", student=student,
                           present=present, total=total, percentage=pct)


@dashboard_bp.route("/upload-certificate", methods=["POST"])
@login_required
def upload_certificate():
    if current_user.role != ROLE_STUDENT or not current_user.student:
        flash("Only students can upload medical certificates.", "danger")
        return redirect(url_for("dashboard.index"))
        
    if "certificate" not in request.files:
        flash("No file part.", "danger")
        return redirect(url_for("dashboard.index"))
        
    file = request.files["certificate"]
    if file.filename == "":
        flash("No selected file.", "danger")
        return redirect(url_for("dashboard.index"))
        
    if file:
        filename = secure_filename(f"{current_user.username}_{file.filename}")
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "instance/certificates")
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        
        file.save(file_path)
        
        reason = request.form.get("reason", "").strip()
        cert = MedicalCertificate(
            student_id=current_user.student.id,
            file_path=filename,
            reason=reason
        )
        from extensions import db
        db.session.add(cert)
        db.session.commit()
        
        flash("Medical certificate uploaded successfully.", "success")
        
    return redirect(url_for("dashboard.index"))
