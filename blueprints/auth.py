"""User Authentication Module: register, login, logout, sessions, RBAC."""
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db
from models import User, Student, ROLE_STUDENT, ROLE_FACULTY, ROLES

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash(f"Welcome back, {user.username}!", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("dashboard.index"))
        flash("Invalid username or password.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Public self-registration (students/faculty). Admins are seeded/created by admin."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", ROLE_STUDENT)

        if role not in (ROLE_STUDENT, ROLE_FACULTY):
            role = ROLE_STUDENT

        error = None
        if not username or not email or not password:
            error = "All fields are required."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif User.query.filter_by(username=username).first():
            error = "That username is already taken."
        elif User.query.filter_by(email=email).first():
            error = "That email is already registered."

        if error:
            flash(error, "danger")
            return render_template("auth/register.html")

        user = User(username=username, email=email, role=role)
        user.set_password(password)

        # If registering as a student, create a linked Student profile.
        if role == ROLE_STUDENT:
            roll = request.form.get("roll_number", "").strip()
            name = request.form.get("name", "").strip() or username
            if not roll:
                flash("Roll number is required for student registration.", "danger")
                return render_template("auth/register.html")
            if Student.query.filter_by(roll_number=roll).first():
                flash("A student with that roll number already exists.", "danger")
                return render_template("auth/register.html")
            student = Student(
                roll_number=roll,
                name=name,
                department=request.form.get("department", "").strip(),
                class_name=request.form.get("class_name", "").strip(),
            )
            db.session.add(student)
            db.session.flush()  # get student.id
            user.student_id = student.id

        db.session.add(user)
        db.session.commit()
        flash("Account created. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    """Password management."""
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if not current_user.check_password(current):
            flash("Current password is incorrect.", "danger")
        elif len(new) < 6:
            flash("New password must be at least 6 characters.", "danger")
        elif new != confirm:
            flash("New passwords do not match.", "danger")
        else:
            current_user.set_password(new)
            db.session.commit()
            flash("Password updated.", "success")
            return redirect(url_for("dashboard.index"))
    return render_template("auth/change_password.html")
