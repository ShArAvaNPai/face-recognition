"""Student Management Module: registration, profiles, department/class, roll number."""
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from extensions import db
from models import Student, Mark, Fee
from blueprints.decorators import staff_required

students_bp = Blueprint("students", __name__, url_prefix="/students")


from models import Student, Mark, Fee, ROLE_HOD, ROLE_STUDENT

@students_bp.route("/")
@login_required
@staff_required
def list_students():
    q = request.args.get("q", "").strip()
    dept_filter = request.args.get("dept", "").strip()
    year_filter = request.args.get("year", "").strip() or request.args.get("class_name", "").strip()

    if current_user.role == ROLE_HOD and current_user.department:
        dept_filter = current_user.department

    query = Student.query
    if current_user.role == ROLE_HOD and current_user.department:
        query = query.filter(Student.department == current_user.department)
    elif dept_filter:
        query = query.filter(Student.department == dept_filter)

    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(Student.name.ilike(like),
                   Student.roll_number.ilike(like),
                   Student.department.ilike(like),
                   Student.class_name.ilike(like))
        )
    if year_filter:
        if year_filter in ["1st Year", "1"]:
            query = query.filter(Student.class_name.ilike("%1st Year%"))
        elif year_filter in ["2nd Year", "2"]:
            query = query.filter(Student.class_name.ilike("%2nd Year%"))
        else:
            query = query.filter(Student.class_name == year_filter)

    students = query.order_by(Student.roll_number).all()

    if current_user.role == ROLE_HOD and current_user.department:
        all_depts = [current_user.department]
    else:
        all_depts = sorted(set(s.department for s in Student.query.all() if s.department))
    all_years = ["1st Year", "2nd Year"]

    return render_template(
        "students/list.html",
        students=students, q=q,
        dept_filter=dept_filter, class_filter=year_filter,
        all_depts=all_depts, all_years=all_years
    )


@students_bp.route("/new", methods=["GET", "POST"])
@login_required
@staff_required
def create_student():
    if request.method == "POST":
        roll = request.form.get("roll_number", "").strip()
        name = request.form.get("name", "").strip()
        dept = request.form.get("department", "").strip()
        if current_user.role == ROLE_HOD and current_user.department:
            dept = current_user.department

        if not roll or not name:
            flash("Roll number and name are required.", "danger")
        elif Student.query.filter_by(roll_number=roll).first():
            flash("A student with that roll number already exists.", "danger")
        else:
            student = Student(
                roll_number=roll,
                name=name,
                department=dept or "MCA",
                class_name=request.form.get("class_name", "").strip(),
            )
            db.session.add(student)
            db.session.commit()
            flash(f"Student {name} added to {student.department}.", "success")
            return redirect(url_for("students.list_students"))
    return render_template("students/form.html", student=None)


@students_bp.route("/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
@staff_required
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    if current_user.role == ROLE_HOD and current_user.department:
        if student.department and student.department != current_user.department:
            flash(f"Access Denied: {current_user.department} HOD can only edit students in {current_user.department}.", "danger")
            return redirect(url_for("students.list_students"))

    if request.method == "POST":
        roll = request.form.get("roll_number", "").strip()
        dept = request.form.get("department", "").strip()
        if current_user.role == ROLE_HOD and current_user.department:
            dept = current_user.department

        existing = Student.query.filter_by(roll_number=roll).first()
        if existing and existing.id != student.id:
            flash("Another student already uses that roll number.", "danger")
        else:
            student.roll_number = roll or student.roll_number
            student.name = request.form.get("name", "").strip() or student.name
            student.department = dept or student.department
            student.class_name = request.form.get("class_name", "").strip()
            db.session.commit()
            flash("Student profile updated.", "success")
            return redirect(url_for("students.list_students"))
    return render_template("students/form.html", student=student)


@students_bp.route("/<int:student_id>/delete", methods=["POST"])
@login_required
@staff_required
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    if current_user.role == ROLE_HOD and current_user.department:
        if student.department and student.department != current_user.department:
            flash(f"Access Denied: {current_user.department} HOD can only delete students in {current_user.department}.", "danger")
            return redirect(url_for("students.list_students"))

    db.session.delete(student)
    db.session.commit()
    flash("Student deleted.", "info")
    return redirect(url_for("students.list_students"))

@students_bp.route("/my_marks")
@login_required
def my_marks():
    if not current_user.is_student:
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.index"))
    
    student_id = current_user.student_id
    student = current_user.student
    all_marks = Mark.query.filter_by(student_id=student_id).all()
    
    # Filter to student's department subjects only
    marks_list = [
        m for m in all_marks
        if not student.department or not m.subject or m.subject.department == student.department
    ]
    
    exam_names = []
    for m in marks_list:
        if m.exam_name and m.exam_name not in exam_names:
            exam_names.append(m.exam_name)
            
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

    for s_id, s_data in subjects_matrix.items():
        if s_data['total_max'] > 0:
            s_data['percentage'] = round((s_data['total_obtained'] / s_data['total_max']) * 100, 1)
        else:
            s_data['percentage'] = 0.0

    return render_template(
        "students/marks.html",
        marks=marks_list,
        exam_names=exam_names,
        subjects_matrix=subjects_matrix.values()
    )

@students_bp.route("/my_fees")
@login_required
def my_fees():
    if not current_user.is_student:
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.index"))
    fees_list = Fee.query.filter_by(student_id=current_user.student_id).all()
    return render_template("students/fees.html", fees=fees_list)

