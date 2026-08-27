"""Parents Module: dashboard, marks, attendance, and fees."""
import os
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db
from models import Student, Mark, Fee, Attendance, Subject, ROLE_PARENT

parents_bp = Blueprint("parents", __name__, url_prefix="/parent")

def parent_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != ROLE_PARENT:
            flash("Access denied.", "danger")
            return redirect(url_for("dashboard.index"))
        if not current_user.student_id:
            flash("No student linked to this parent account.", "danger")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)
    return decorated_function


@parents_bp.route("/dashboard")
@login_required
@parent_required
def dashboard():
    student = Student.query.get(current_user.student_id)
    # Simple summary stats
    total_fees = Fee.query.filter_by(student_id=student.id).count()
    pending_fees = Fee.query.filter_by(student_id=student.id, status="Pending").count()
    
    # Calculate attendance %
    total_classes = Attendance.query.filter_by(student_id=student.id).count()
    present_classes = Attendance.query.filter_by(student_id=student.id, status="present").count()
    att_percent = 0
    if total_classes > 0:
        att_percent = round((present_classes / total_classes) * 100, 2)
        
    recent_marks = Mark.query.filter_by(student_id=student.id).order_by(Mark.created_at.desc()).limit(3).all()
    
    return render_template("parents/dashboard.html", student=student, pending_fees=pending_fees, 
                           att_percent=att_percent, recent_marks=recent_marks)

@parents_bp.route("/marks")
@login_required
@parent_required
def marks():
    student = Student.query.get(current_user.student_id)
    marks_list = Mark.query.filter_by(student_id=student.id).all()
    return render_template("parents/marks.html", student=student, marks=marks_list)

@parents_bp.route("/attendance")
@login_required
@parent_required
def attendance():
    student = Student.query.get(current_user.student_id)
    records = Attendance.query.filter_by(student_id=student.id).order_by(Attendance.marked_at.desc()).all()
    return render_template("parents/attendance.html", student=student, records=records)

@parents_bp.route("/fees", methods=["GET", "POST"])
@login_required
@parent_required
def fees():
    student = Student.query.get(current_user.student_id)
    if request.method == "POST":
        fee_id = request.form.get("fee_id")
        fee = Fee.query.get(fee_id)
        if fee and fee.student_id == student.id:
            if "receipt" not in request.files:
                flash("No receipt file part", "danger")
                return redirect(request.url)
            file = request.files["receipt"]
            if file.filename == "":
                flash("No selected file", "danger")
                return redirect(request.url)
            if file:
                filename = secure_filename(file.filename)
                # Ensure uploads dir exists
                upload_folder = os.path.join(current_app.root_path, "static", "uploads", "receipts")
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, f"{fee.id}_{filename}")
                file.save(file_path)
                
                # Update fee
                fee.status = "Verification"
                fee.receipt_path = f"/static/uploads/receipts/{fee.id}_{filename}"
                db.session.commit()
                flash("Receipt uploaded successfully. Pending verification.", "success")
        return redirect(url_for("parents.fees"))
        
    fees_list = Fee.query.filter_by(student_id=student.id).all()
    return render_template("parents/fees.html", student=student, fees=fees_list)
