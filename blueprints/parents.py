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
    marks_list = Mark.query.filter_by(student_id=student.id).all() if student else []

    # Extract distinct exam names in chronological/appearance order
    exam_names = []
    for m in marks_list:
        if m.exam_name and m.exam_name not in exam_names:
            exam_names.append(m.exam_name)

    # Group by subject (Subject as Row, Exams as Columns)
    subjects_matrix = {}
    for m in marks_list:
        if m.subject_id not in subjects_matrix:
            subjects_matrix[m.subject_id] = {
                'subject': m.subject,
                'exams': {},
                'total_obtained': 0.0,
                'total_max': 0.0
            }
        subjects_matrix[m.subject_id]['exams'][m.exam_name] = m
        subjects_matrix[m.subject_id]['total_obtained'] += m.marks_obtained
        subjects_matrix[m.subject_id]['total_max'] += m.total_marks

    # Compute overall percentage per subject
    for s_id, s_data in subjects_matrix.items():
        if s_data['total_max'] > 0:
            s_data['percentage'] = round((s_data['total_obtained'] / s_data['total_max']) * 100, 1)
        else:
            s_data['percentage'] = 0.0

    return render_template(
        "parents/marks.html",
        student=student,
        marks=marks_list,
        exam_names=exam_names,
        subjects_matrix=subjects_matrix.values()
    )

@parents_bp.route("/attendance")
@login_required
@parent_required
def attendance():
    student = Student.query.get(current_user.student_id)
    raw_records = Attendance.query.filter_by(student_id=student.id).order_by(Attendance.marked_at.desc()).all() if student else []
    records = [
        r for r in raw_records
        if not student or not student.department or not r.session.subject or not r.session.subject.department or r.session.subject.department == student.department
    ]



    # Subject-wise attendance breakdown (Subjects as rows)
    subjects_map = {}
    for r in records:
        subj = r.session.subject
        if subj.id not in subjects_map:
            subjects_map[subj.id] = {
                'subject': subj,
                'total': 0,
                'present': 0,
                'absent': 0,
                'excused': 0
            }
        subjects_map[subj.id]['total'] += 1
        if r.status == 'present':
            subjects_map[subj.id]['present'] += 1
        elif r.status == 'excused':
            subjects_map[subj.id]['excused'] += 1
            subjects_map[subj.id]['present'] += 1
        else:
            subjects_map[subj.id]['absent'] += 1

    for s_id, s_data in subjects_map.items():
        s_data['percentage'] = round((s_data['present'] / s_data['total']) * 100, 1) if s_data['total'] > 0 else 0.0

    return render_template(
        "parents/attendance.html",
        student=student,
        records=records,
        subject_attendance=list(subjects_map.values())
    )

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
