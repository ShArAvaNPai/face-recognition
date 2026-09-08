"""Admin Blueprint: user management, creating accounts."""
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required

from extensions import db
from models import User, Student, ROLES, ROLE_STUDENT, ROLE_FACULTY, ROLE_DIRECTOR, Subject, TimetableSlot
from blueprints.decorators import admin_required, director_required

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
            
        dept = request.form.get("department", "").strip()
        user = User(username=username, email=email, role=role, department=dept)
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


@admin_bp.route("/timetable", methods=["GET", "POST"])
@login_required
@director_required
def manage_timetable():
    """Admin/Director page to create and delete weekly timetable slots."""
    DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    TIMES = [
        "09:00 - 10:00", "10:00 - 11:00", "11:00 - 12:00",
        "13:00 - 14:00", "14:00 - 15:00", "15:00 - 16:00"
    ]
    subjects = Subject.query.order_by(Subject.name).all()

    if current_user.role == 'hod' and current_user.department:
        department = current_user.department
    else:
        department = request.args.get("dept", "MCA")

    if request.method == "POST":
        action = request.form.get("action")
        # Ensure we keep the selected department in the URL after POST
        if current_user.role == 'hod' and current_user.department:
            department = current_user.department
        else:
            department = request.form.get("dept", department)
        if action == "create":
            day = request.form.get("day_of_week", "").strip()
            time = request.form.get("slot_time", "").strip()
            subject_id = request.form.get("subject_id", type=int)
            if day not in DAYS:
                flash("Invalid day selected.", "danger")
            elif time not in TIMES:
                flash("Invalid time slot selected.", "danger")
            else:
                existing = TimetableSlot.query.filter_by(department=department, day_of_week=day, slot_time=time).first()
                if existing:
                    # Update subject
                    existing.subject_id = subject_id if subject_id else None
                    db.session.commit()
                    flash(f"Updated {day} {time} slot for {department}.", "success")
                else:
                    slot = TimetableSlot(department=department, day_of_week=day, slot_time=time, subject_id=subject_id if subject_id else None)
                    db.session.add(slot)
                    db.session.commit()
                    flash(f"Created slot: {day} {time} for {department}.", "success")
        elif action == "delete":
            slot_id = request.form.get("slot_id", type=int)
            slot = TimetableSlot.query.get(slot_id)
            if slot:
                db.session.delete(slot)
                db.session.commit()
                flash("Slot deleted.", "info")
        elif action == "clear_subject":
            slot_id = request.form.get("slot_id", type=int)
            slot = TimetableSlot.query.get(slot_id)
            if slot:
                slot.subject_id = None
                db.session.commit()
                flash("Subject cleared from slot (slot is now free).", "info")
        return redirect(url_for("admin.manage_timetable", dept=department))

    # Build grid for display
    grid = {}
    for day in DAYS:
        grid[day] = {}
        for time in TIMES:
            slot = TimetableSlot.query.filter_by(department=department, day_of_week=day, slot_time=time).first()
            grid[day][time] = slot

    return render_template("admin/manage_timetable.html",
                           grid=grid, days=DAYS, times=TIMES, subjects=subjects, department=department)


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        new_username = request.form.get("username", "").strip()
        new_email = request.form.get("email", "").strip()
        new_password = request.form.get("password", "").strip()
        new_role = request.form.get("role", user.role)
        new_dept = request.form.get("department", "").strip()

        if not new_username or not new_email:
            flash("Username and Email are required.", "danger")
        else:
            existing = User.query.filter(User.username == new_username, User.id != user.id).first()
            if existing:
                flash("That username is already taken by another user.", "danger")
            else:
                user.username = new_username
                user.email = new_email
                user.role = new_role
                user.department = new_dept

                if new_password:
                    user.set_password(new_password)

                if user.student:
                    roll = request.form.get("roll_number", "").strip()
                    name = request.form.get("name", "").strip()
                    class_name = request.form.get("class_name", "").strip()
                    if roll:
                        user.student.roll_number = roll
                    if name:
                        user.student.name = name
                    if class_name:
                        user.student.class_name = class_name
                    user.student.department = new_dept

                db.session.commit()
                flash(f"User '{user.username}' updated successfully.", "success")
                return redirect(url_for("admin.list_users"))

    return render_template("admin/edit_user.html", user=user, roles=ROLES)

