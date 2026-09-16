"""Admin Blueprint: user management, creating accounts."""
from datetime import date, datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from extensions import db
from models import (User, Student, ROLES, ROLE_ADMIN, ROLE_STUDENT, ROLE_FACULTY,
                    ROLE_DIRECTOR, ROLE_HOD, ROLE_PARENT, Subject, TimetableSlot, Fee)
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


@admin_bp.route("/users/import", methods=["POST"])
@login_required
@admin_required
def import_users():
    import csv
    import io
    
    if 'csv_file' not in request.files:
        flash("No file uploaded.", "danger")
        return redirect(url_for("admin.list_users"))
        
    file = request.files['csv_file']
    if file.filename == '':
        flash("No file selected.", "danger")
        return redirect(url_for("admin.list_users"))
        
    if not file.filename.endswith('.csv'):
        flash("Please upload a CSV file.", "danger")
        return redirect(url_for("admin.list_users"))
        
    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        
        # Expected columns: username, email, password, role, department, roll_number, name, class_name
        imported_count = 0
        for row in csv_input:
            username = row.get("username", "").strip()
            email = row.get("email", "").strip()
            if not username or not email:
                continue
                
            if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
                continue
                
            role = row.get("role", ROLE_STUDENT).strip()
            if role not in ROLES:
                role = ROLE_STUDENT
                
            dept = row.get("department", "").strip()
            user = User(username=username, email=email, role=role, department=dept)
            user.set_password(row.get("password", "password123"))
            
            if role == ROLE_STUDENT:
                roll = row.get("roll_number", "").strip()
                name = row.get("name", "").strip() or username
                class_name = row.get("class_name", "").strip()
                if roll and not Student.query.filter_by(roll_number=roll).first():
                    student = Student(roll_number=roll, name=name, department=dept, class_name=class_name)
                    db.session.add(student)
                    db.session.flush()
                    user.student_id = student.id
                    
            db.session.add(user)
            imported_count += 1
            
        db.session.commit()
        flash(f"Successfully imported {imported_count} users.", "success")
    except Exception as e:
        flash(f"Error processing CSV: {str(e)}", "danger")
        
    return redirect(url_for("admin.list_users"))

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

    if current_user.role == 'hod' and current_user.department:
        department = current_user.department
        dept_subjs = Subject.query.filter(
            Subject.code.ilike(f"{department}%") |
            Subject.faculty.has(User.department == department)
        ).order_by(Subject.code).all()
        subjects = dept_subjs if dept_subjs else Subject.query.order_by(Subject.code).all()
    else:
        department = request.args.get("dept", "MCA")
        all_subjs = Subject.query.order_by(Subject.code).all()
        dept_subjs = [s for s in all_subjs if (s.faculty and s.faculty.department == department) or s.code.upper().startswith(department.upper())]
        other_subjs = [s for s in all_subjs if s not in dept_subjs]
        subjects = dept_subjs + other_subjs

    year = request.args.get("year", type=int) or 1
    if year not in [1, 2]:
        year = 1

    if request.method == "POST":
        action = request.form.get("action")
        # Ensure we keep the selected department and year in the URL after POST
        if current_user.role == 'hod' and current_user.department:
            department = current_user.department
        else:
            department = request.form.get("dept", department)
        year = request.form.get("year", type=int) or year
        if year not in [1, 2]:
            year = 1

        if action == "create":
            day = request.form.get("day_of_week", "").strip()
            time = request.form.get("slot_time", "").strip()
            subject_id = request.form.get("subject_id", type=int)
            if day not in DAYS:
                flash("Invalid day selected.", "danger")
            elif time not in TIMES:
                flash("Invalid time slot selected.", "danger")
            else:
                existing = TimetableSlot.query.filter_by(department=department, year=year, day_of_week=day, slot_time=time).first()
                if existing:
                    # Update subject
                    existing.subject_id = subject_id if subject_id else None
                    db.session.commit()
                    flash(f"Updated {day} {time} slot for {department} Year {year}.", "success")
                else:
                    slot = TimetableSlot(department=department, year=year, day_of_week=day, slot_time=time, subject_id=subject_id if subject_id else None)
                    db.session.add(slot)
                    db.session.commit()
                    flash(f"Created slot: {day} {time} for {department} Year {year}.", "success")
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
        return redirect(url_for("admin.manage_timetable", dept=department, year=year))

    # Build grid for display
    grid = {}
    for day in DAYS:
        grid[day] = {}
        for time in TIMES:
            slot = TimetableSlot.query.filter_by(department=department, year=year, day_of_week=day, slot_time=time).first()
            grid[day][time] = slot

    return render_template("admin/manage_timetable.html",
                           grid=grid, days=DAYS, times=TIMES, subjects=subjects, department=department, year=year)


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

                # Manage subject assignments for faculty members
                if user.role == ROLE_FACULTY:
                    selected_subject_ids = request.form.getlist("subject_ids", type=int)
                    # Unassign subjects previously assigned to this user that are no longer checked
                    for subj in Subject.query.filter_by(faculty_id=user.id).all():
                        if subj.id not in selected_subject_ids:
                            subj.faculty_id = None
                    # Assign selected subjects to this user
                    for subj_id in selected_subject_ids:
                        subj = Subject.query.get(subj_id)
                        if subj:
                            subj.faculty_id = user.id

                db.session.commit()
                flash(f"User '{user.username}' updated successfully.", "success")
                return redirect(url_for("admin.list_users"))

    all_subjects = Subject.query.order_by(Subject.code).all()
    return render_template("admin/edit_user.html", user=user, roles=ROLES, all_subjects=all_subjects)


@admin_bp.route("/parents", methods=["GET"])
@login_required
@admin_required
def manage_parents():
    """Parent account & mail management for low attendance and class absence alerts."""
    dept_filter = request.args.get("dept", "").strip()
    search_query = request.args.get("q", "").strip()
    attendance_filter = request.args.get("att_filter", "").strip()  # 'low' (< threshold) or ''
    raw_thresh = request.args.get("threshold", "").strip()
    try:
        threshold = float(raw_thresh) if raw_thresh else 75.0
    except (ValueError, TypeError):
        threshold = 75.0


    query = Student.query
    if dept_filter:
        query = query.filter(Student.department.ilike(dept_filter))
    if search_query:
        query = query.filter(
            (Student.name.ilike(f"%{search_query}%")) |
            (Student.roll_number.ilike(f"%{search_query}%"))
        )

    all_students = query.order_by(Student.roll_number).all()
    
    students_data = []
    total_parents_configured = 0
    low_attendance_count = 0

    for s in all_students:
        stats = s.attendance_stats
        parent = s.parent_user
        has_parent_email = bool(parent and parent.email)
        if has_parent_email:
            total_parents_configured += 1
            
        is_low = stats["percent"] < threshold if stats["total"] > 0 else False
        if is_low:
            low_attendance_count += 1

        if attendance_filter == "low" and not is_low:
            continue

        students_data.append({
            "student": s,
            "parent": parent,
            "parent_email": parent.email if parent else None,
            "stats": stats,
            "is_low": is_low
        })

    departments = sorted(list(set([d[0] for d in db.session.query(Student.department).distinct().all() if d[0]])))

    return render_template(
        "admin/parents.html",
        students_data=students_data,
        departments=departments,
        selected_dept=dept_filter,
        search_query=search_query,
        attendance_filter=attendance_filter,
        threshold=int(threshold),
        total_students=len(all_students),
        total_parents_configured=total_parents_configured,
        low_attendance_count=low_attendance_count
    )


@admin_bp.route("/parents/update", methods=["POST"])
@login_required
@admin_required
def update_parent_account():
    """Create or update a parent account and email address for a student."""
    student_id = request.form.get("student_id", type=int)
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    student = Student.query.get_or_404(student_id)
    if not email:
        flash("Email address is required.", "danger")
        return redirect(url_for("admin.manage_parents"))

    parent_user = User.query.filter_by(role=ROLE_PARENT, student_id=student.id).first()
    if not parent_user:
        default_username = f"parent_{student.roll_number}"
        existing = User.query.filter_by(username=default_username).first()
        if existing and existing.role != ROLE_PARENT:
            default_username = f"parent_s_{student.id}"

        email_existing = User.query.filter(User.email == email).first()
        if email_existing and email_existing.student_id != student.id:
            flash(f"Email '{email}' is already registered to another user.", "danger")
            return redirect(url_for("admin.manage_parents"))

        parent_user = User(
            username=default_username,
            email=email,
            role=ROLE_PARENT,
            department=student.department,
            student_id=student.id
        )
        parent_user.set_password(password if password else f"parent_{student.roll_number}")
        db.session.add(parent_user)
        flash(f"Created parent account for {student.name} with email '{email}'.", "success")
    else:
        email_existing = User.query.filter(User.email == email, User.id != parent_user.id).first()
        if email_existing:
            flash(f"Email '{email}' is already registered to another user.", "danger")
            return redirect(url_for("admin.manage_parents"))

        parent_user.email = email
        if password:
            parent_user.set_password(password)
        flash(f"Updated parent email to '{email}' for {student.name}.", "success")

    db.session.commit()
    return redirect(url_for("admin.manage_parents"))


@admin_bp.route("/parents/send-mail", methods=["POST"])
@login_required
@admin_required
def send_parent_mail():
    """Send emails to parents of low attendance or absent students."""
    from utils.email import send_email, generate_low_attendance_html, generate_absence_html, generate_custom_parent_html

    mail_type = request.form.get("mail_type", "low_attendance")  # 'low_attendance', 'absence', 'custom'
    target_scope = request.form.get("target_scope", "selected")  # 'selected', 'all_low', 'all'
    student_ids = request.form.getlist("student_ids", type=int)
    raw_thresh = request.form.get("threshold", "").strip()
    try:
        threshold = float(raw_thresh) if raw_thresh else 75.0
    except (ValueError, TypeError):
        threshold = 75.0

    custom_subject = request.form.get("subject", "").strip()
    custom_note = request.form.get("message_body", "").strip()

    if target_scope == "all_low":
        all_st = Student.query.all()
        target_students = [s for s in all_st if (s.attendance_stats["total"] > 0 and s.attendance_stats["percent"] < threshold)]
    elif target_scope == "all":
        target_students = Student.query.all()
    else:
        target_students = Student.query.filter(Student.id.in_(student_ids)).all() if student_ids else []

    if not target_students:
        flash("No students selected for sending email.", "warning")
        return redirect(url_for("admin.manage_parents"))

    sent_count = 0
    missing_email_count = 0

    for s in target_students:
        parent_email = s.parent_email
        if not parent_email:
            missing_email_count += 1
            continue

        stats = s.attendance_stats

        if mail_type == "low_attendance":
            subj = custom_subject or f"Low Attendance Notice: {s.name} ({s.roll_number}) - {stats['percent']}%"
            text_body = (
                f"Dear Parent,\n\n"
                f"This is an official warning regarding the attendance of your child {s.name} ({s.roll_number}).\n"
                f"Current Attendance: {stats['percent']}% ({stats['present']}/{stats['total']} classes attended).\n"
                f"Minimum required attendance is {int(threshold)}%.\n\n"
                f"{custom_note}\n\n"
                f"Regards,\nSmart Attendance System Administration"
            )
            html_body = generate_low_attendance_html(
                student_name=s.name,
                roll_number=s.roll_number,
                department=s.department,
                attendance_pct=stats["percent"],
                present_count=stats["present"],
                total_count=stats["total"],
                custom_note=custom_note
            )
            send_email(subj, [parent_email], text_body, html_body)
            sent_count += 1

        elif mail_type == "absence":
            subj = custom_subject or f"Absence Alert: {s.name} ({s.roll_number})"
            session_date = request.form.get("session_date") or date.today().isoformat()
            subject_name = request.form.get("subject_name", "Scheduled Lecture")
            text_body = (
                f"Dear Parent,\n\n"
                f"Your child {s.name} ({s.roll_number}) was marked ABSENT for {subject_name} on {session_date}.\n\n"
                f"{custom_note}\n\n"
                f"Regards,\nSmart Attendance System Administration"
            )
            html_body = generate_absence_html(
                student_name=s.name,
                roll_number=s.roll_number,
                department=s.department,
                subject_name=subject_name,
                session_date=session_date,
                custom_note=custom_note
            )
            send_email(subj, [parent_email], text_body, html_body)
            sent_count += 1

        elif mail_type == "custom":
            subj = custom_subject or "Important Notice from Smart Attendance Administration"
            text_body = f"Dear Parent of {s.name} ({s.roll_number}),\n\n{custom_note}\n\nRegards,\nSmart Attendance Administration"
            html_body = generate_custom_parent_html(
                student_name=s.name,
                roll_number=s.roll_number,
                subject_heading=subj,
                body_message=custom_note
            )
            send_email(subj, [parent_email], text_body, html_body)
            sent_count += 1

    msg = f"Sent {sent_count} parent notification email(s) successfully."
    if missing_email_count > 0:
        msg += f" Note: {missing_email_count} student(s) do not have a registered parent email."

    flash(msg, "success" if sent_count > 0 else "warning")
    return redirect(url_for("admin.manage_parents"))


@admin_bp.route("/fees", methods=["GET", "POST"])
@login_required
@admin_required
def manage_fees():
    """Admin feed and manage student fees with automatic receipt generation."""
    if request.method == "POST":
        student_id = request.form.get("student_id", type=int)
        fee_type = request.form.get("fee_type", "").strip()
        amount_raw = request.form.get("amount_due", "").strip()
        due_date_raw = request.form.get("due_date", "").strip()
        status = request.form.get("status", "Paid").strip()

        if not student_id or not fee_type or not amount_raw or not due_date_raw:
            flash("All fee fields (Student, Fee Type, Amount, Due Date) are required.", "danger")
            return redirect(url_for("admin.manage_fees"))

        try:
            amount_due = float(amount_raw)
        except ValueError:
            flash("Invalid amount entered.", "danger")
            return redirect(url_for("admin.manage_fees"))

        try:
            due_date = datetime.strptime(due_date_raw, "%Y-%m-%d").date()
        except ValueError:
            due_date = date.today()

        payment_method = request.form.get("payment_method", "Cash").strip()
        payment_reference = request.form.get("payment_reference", "").strip()

        student = Student.query.get(student_id)
        if not student:
            flash("Student not found.", "danger")
            return redirect(url_for("admin.manage_fees"))

        new_fee = Fee(
            student_id=student.id,
            fee_type=fee_type,
            amount_due=amount_due,
            due_date=due_date,
            status=status,
            payment_method=payment_method,
            payment_reference=payment_reference,
            paid_date=date.today() if status == "Paid" else None
        )
        db.session.add(new_fee)
        db.session.flush() # get new_fee.id

        # Automatically assign generated official receipt path
        new_fee.receipt_path = url_for("admin.view_fee_receipt", fee_id=new_fee.id)
        db.session.commit()

        flash(f"Fee of ₹{amount_due:,.2f} recorded for {student.name} ({student.roll_number}). Official receipt #{new_fee.id} automatically generated!", "success")
        return redirect(url_for("admin.manage_fees"))

    # GET
    dept_filter = request.args.get("dept", "").strip()
    status_filter = request.args.get("status", "").strip()
    fee_type_filter = request.args.get("fee_type", "").strip()
    search_query = request.args.get("q", "").strip()

    fees_query = Fee.query.join(Student)
    if dept_filter:
        fees_query = fees_query.filter(Student.department.ilike(dept_filter))
    if status_filter:
        fees_query = fees_query.filter(Fee.status == status_filter)
    if fee_type_filter:
        fees_query = fees_query.filter(Fee.fee_type == fee_type_filter)
    if search_query:
        fees_query = fees_query.filter(
            (Student.name.ilike(f"%{search_query}%")) |
            (Student.roll_number.ilike(f"%{search_query}%")) |
            (Fee.fee_type.ilike(f"%{search_query}%"))
        )

    all_fees = fees_query.order_by(Fee.id.desc()).all()
    all_students = Student.query.order_by(Student.department, Student.roll_number).all()

    # Distinct fee types for the dropdown filter
    distinct_fee_types = [
        r[0] for r in Fee.query.with_entities(Fee.fee_type).distinct().order_by(Fee.fee_type).all()
        if r[0]
    ]

    total_amount = sum(f.amount_due for f in all_fees)
    paid_amount = sum(f.amount_due for f in all_fees if f.status == "Paid")
    pending_amount = sum(f.amount_due for f in all_fees if f.status == "Pending")

    return render_template(
        "admin/fees.html",
        fees=all_fees,
        students=all_students,
        total_amount=total_amount,
        paid_amount=paid_amount,
        pending_amount=pending_amount,
        dept_filter=dept_filter,
        status_filter=status_filter,
        fee_type_filter=fee_type_filter,
        distinct_fee_types=distinct_fee_types,
        search_query=search_query,
        today_date=date.today()
    )


@admin_bp.route("/fees/<int:fee_id>/status", methods=["POST"])
@login_required
@admin_required
def update_fee_status(fee_id):
    """Approve pending bill or update fee status with payment method and reference."""
    fee = Fee.query.get_or_404(fee_id)
    new_status = request.form.get("status", "Paid").strip()
    payment_method = request.form.get("payment_method", "").strip()
    payment_reference = request.form.get("payment_reference", "").strip()
    paid_date_raw = request.form.get("paid_date", "").strip()

    if new_status in ["Paid", "Pending", "Verification"]:
        fee.status = new_status
        if new_status == "Paid":
            if payment_method:
                fee.payment_method = payment_method
            if payment_reference:
                fee.payment_reference = payment_reference
            if paid_date_raw:
                try:
                    fee.paid_date = datetime.strptime(paid_date_raw, "%Y-%m-%d").date()
                except ValueError:
                    fee.paid_date = date.today()
            else:
                fee.paid_date = date.today()
        db.session.commit()
        flash(f"Fee #{fee.id} for {fee.student.name if fee.student else 'Student'} marked as '{new_status}' via {fee.payment_method or 'Cash'}. Receipt updated!", "success")
    else:
        flash("Invalid status selected.", "danger")
    return redirect(url_for("admin.manage_fees"))


@admin_bp.route("/fees/<int:fee_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_fee(fee_id):
    fee = Fee.query.get_or_404(fee_id)
    student_name = fee.student.name if fee.student else "Student"
    db.session.delete(fee)
    db.session.commit()
    flash(f"Fee record for {student_name} deleted successfully.", "info")
    return redirect(url_for("admin.manage_fees"))


@admin_bp.route("/fees/<int:fee_id>/receipt", methods=["GET"])
@login_required
def view_fee_receipt(fee_id):
    """View / Print / Download official formatted automated fee receipt."""
    fee = Fee.query.get_or_404(fee_id)

    # Permission check: admin, director, hod, faculty, the student themselves, or the parent
    can_view = False
    if current_user.role in [ROLE_ADMIN, ROLE_DIRECTOR, ROLE_HOD, ROLE_FACULTY]:
        can_view = True
    elif current_user.role == ROLE_STUDENT and current_user.student_id == fee.student_id:
        can_view = True
    elif current_user.role == ROLE_PARENT and current_user.student_id == fee.student_id:
        can_view = True

    if not can_view:
        flash("You are not authorized to view this fee receipt.", "danger")
        return redirect(url_for("dashboard.index"))

    return render_template("admin/fee_receipt.html", fee=fee, student=fee.student)



