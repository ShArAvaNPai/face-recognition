"""Student Management Module: registration, profiles, department/class, roll number."""
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required

from extensions import db
from models import Student
from blueprints.decorators import staff_required

students_bp = Blueprint("students", __name__, url_prefix="/students")


@students_bp.route("/")
@login_required
@staff_required
def list_students():
    q = request.args.get("q", "").strip()
    query = Student.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(Student.name.ilike(like),
                   Student.roll_number.ilike(like),
                   Student.department.ilike(like),
                   Student.class_name.ilike(like))
        )
    students = query.order_by(Student.roll_number).all()
    return render_template("students/list.html", students=students, q=q)


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
