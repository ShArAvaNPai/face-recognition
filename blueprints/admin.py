"""Admin Blueprint: user management, creating accounts."""
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required

from extensions import db
from models import User, Student, ROLES, ROLE_STUDENT, ROLE_FACULTY, ROLE_DIRECTOR
from blueprints.decorators import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/users")
@login_required
@admin_required
def list_users():
    users = User.query.order_by(User.role, User.username).all()
    return render_template("admin/list_users.html", users=users)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@admin_required
def new_user():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", ROLE_STUDENT)
        
        error = None
        if not username or not email or not password:
            error = "All fields are required."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif role not in ROLES:
            error = "Invalid role selected."
        elif User.query.filter_by(username=username).first():
            error = "That username is already taken."
        elif User.query.filter_by(email=email).first():
            error = "That email is already registered."
            
        if error:
            flash(error, "danger")
            return render_template("admin/new_user.html", roles=ROLES)
            
        user = User(username=username, email=email, role=role)
        user.set_password(password)
        
        # If registering as a student, create the linked Student profile
        if role == ROLE_STUDENT:
            roll = request.form.get("roll_number", "").strip()
            name = request.form.get("name", "").strip() or username
            if not roll:
                flash("Roll number is required for students.", "danger")
                return render_template("admin/new_user.html", roles=ROLES)
            if Student.query.filter_by(roll_number=roll).first():
                flash("Student with that roll number already exists.", "danger")
                return render_template("admin/new_user.html", roles=ROLES)
                
            student = Student(
                roll_number=roll,
                name=name,
                department=request.form.get("department", "").strip(),
                class_name=request.form.get("class_name", "").strip(),
            )
            db.session.add(student)
            db.session.flush()
            user.student_id = student.id
            
        db.session.add(user)
        db.session.commit()
        flash(f"User {username} created successfully with role {role}.", "success")
        return redirect(url_for("admin.list_users"))
        
    return render_template("admin/new_user.html", roles=ROLES)
