"""Student Management Module: registration, profiles, department/class, roll number."""
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from extensions import db
from models import Student, Mark, Fee
from blueprints.decorators import staff_required

students_bp = Blueprint("students", __name__, url_prefix="/students")


@students_bp.route("/")
@login_required
@staff_required
def list_students():
    q = request.args.get("q", "").strip()
    dept_filter = request.args.get("dept", "").strip()
    class_filter = request.args.get("class_name", "").strip()

    query = Student.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(Student.name.ilike(like),
                   Student.roll_number.ilike(like),
                   Student.department.ilike(like),
                   Student.class_name.ilike(like))
        )
    if dept_filter:
        query = query.filter(Student.department == dept_filter)
    if class_filter:
        query = query.filter(Student.class_name == class_filter)

    students = query.order_by(Student.roll_number).all()

    # Distinct values for filter dropdowns
    all_depts = sorted(set(s.department for s in Student.query.all() if s.department))
    all_classes = sorted(set(s.class_name for s in Student.query.all() if s.class_name))

    return render_template(
        "students/list.html",
        students=students, q=q,
        dept_filter=dept_filter, class_filter=class_filter,
        all_depts=all_depts, all_classes=all_classes
    )



@students_bp.route("/new", methods=["GET", "POST"])
@login_required
@staff_required
def create_student():
    if request.method == "POST":
        roll = request.form.get("roll_number", "").strip()
        name = request.form.get("name", "").strip()
        if not roll or not name:
            flash("Roll number and name are required.", "danger")
        elif Student.query.filter_by(roll_number=roll).first():
            flash("A student with that roll number already exists.", "danger")
        else:
            student = Student(
                roll_number=roll,
                name=name,
                department=request.form.get("department", "").strip(),
                class_name=request.form.get("class_name", "").strip(),
            )
            db.session.add(student)
            db.session.commit()
            flash(f"Student {name} added.", "success")
            return redirect(url_for("students.list_students"))
    return render_template("students/form.html", student=None)


@students_bp.route("/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
@staff_required
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    if request.method == "POST":
        roll = request.form.get("roll_number", "").strip()
        existing = Student.query.filter_by(roll_number=roll).first()
        if existing and existing.id != student.id:
            flash("Another student already uses that roll number.", "danger")
        else:
            student.roll_number = roll or student.roll_number
            student.name = request.form.get("name", "").strip() or student.name
            student.department = request.form.get("department", "").strip()
            student.class_name = request.form.get("class_name", "").strip()
            db.session.commit()
            flash("Student updated.", "success")
            return redirect(url_for("students.list_students"))
    return render_template("students/form.html", student=student)


@students_bp.route("/<int:student_id>/delete", methods=["POST"])
@login_required
@staff_required
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
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
    marks_list = Mark.query.filter_by(student_id=current_user.student_id).all()
    return render_template("students/marks.html", marks=marks_list)

@students_bp.route("/my_fees")
@login_required
def my_fees():
    if not current_user.is_student:
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.index"))
    fees_list = Fee.query.filter_by(student_id=current_user.student_id).all()
    return render_template("students/fees.html", fees=fees_list)
