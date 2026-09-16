"""Marks Management Blueprint: assigning and managing student marks for faculty, HOD, and director."""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import Mark, Subject, Student, User, ROLE_ADMIN, ROLE_FACULTY, ROLE_DIRECTOR, ROLE_HOD, Notification
from blueprints.decorators import staff_required

marks_bp = Blueprint("marks", __name__, url_prefix="/marks")


def get_authorized_subjects():
    """Retrieve subjects that the current user has permission to manage marks for."""
    if current_user.role == ROLE_FACULTY:
        return Subject.query.filter_by(faculty_id=current_user.id).order_by(Subject.code).all()
    elif current_user.role == ROLE_DIRECTOR:
        # Director can view all or research/assigned subjects
        subjects = Subject.query.filter(
            (Subject.code.ilike("%research%")) | (Subject.name.ilike("%research%")) | (Subject.faculty_id == current_user.id)
        ).order_by(Subject.code).all()
        if not subjects:
            subjects = Subject.query.order_by(Subject.code).all()
        return subjects
    elif current_user.role == ROLE_HOD and current_user.department:
        subjects = Subject.query.filter(
            (Subject.faculty_id == current_user.id) |
            (Subject.code.ilike(f"{current_user.department}%")) |
            (Subject.faculty.has(User.department == current_user.department))
        ).order_by(Subject.code).all()
        if not subjects:
            subjects = Subject.query.order_by(Subject.code).all()
        return subjects
    else:
        # Admin or fallback
        return Subject.query.order_by(Subject.code).all()


@marks_bp.route("/", methods=["GET"])
@login_required
@staff_required
def index():
    subjects = get_authorized_subjects()
    subject_id_raw = request.args.get("subject_id", "")
    subject_id = int(subject_id_raw) if subject_id_raw and subject_id_raw.isdigit() else None
    class_filter = request.args.get("class_name", "").strip()
    exam_filter = request.args.get("exam_name", "").strip()

    selected_subject = Subject.query.get(subject_id) if subject_id else None

    # If faculty, ensure they can only view their own assigned subject
    if current_user.role == ROLE_FACULTY:
        auth_ids = {s.id for s in subjects}
        if selected_subject and selected_subject.id not in auth_ids:
            flash("You are not authorized to view marks for this subject.", "danger")
            return redirect(url_for("marks.index"))
        if not selected_subject and subjects:
            selected_subject = subjects[0]

    # Query marks list
    marks_query = Mark.query
    if selected_subject:
        marks_query = marks_query.filter_by(subject_id=selected_subject.id)
    elif current_user.role != ROLE_ADMIN:
        # For HOD/director, filter by authorized subjects if none explicitly chosen
        auth_subject_ids = [s.id for s in subjects]
        if auth_subject_ids:
            marks_query = marks_query.filter(Mark.subject_id.in_(auth_subject_ids))
        else:
            marks_query = marks_query.filter(Mark.id == -1)

    if exam_filter:
        marks_query = marks_query.filter(Mark.exam_name.ilike(f"%{exam_filter}%"))
    if class_filter:
        marks_query = marks_query.join(Student).filter(
            (Student.class_name == class_filter) | (Student.department == class_filter)
        )

    marks_list = marks_query.order_by(Mark.created_at.desc()).all()

    # Classes available for filtering
    available_classes = sorted(list(set(
        [c[0] for c in db.session.query(Student.class_name).distinct().all() if c[0]] +
        [d[0] for d in db.session.query(Student.department).distinct().all() if d[0]]
    )))

    # Build Student Matrix (Each student is a Row, Each Exam is a Column)
    students_in_marks = {}
    exam_names_set = []
    
    for m in marks_list:
        # If all subjects are selected, we need to disambiguate the exam name
        exam_key = m.exam_name if selected_subject else f"{m.subject.code}: {m.exam_name}"
        if exam_key not in exam_names_set:
            exam_names_set.append(exam_key)
        if m.student_id not in students_in_marks:
            students_in_marks[m.student_id] = {
                "student": m.student,
                "exams": {},
                "total_obtained": 0.0,
                "total_max": 0.0,
                "marks_count": 0,
                "remarks": []
            }
        students_in_marks[m.student_id]["exams"][exam_key] = m
        students_in_marks[m.student_id]["total_obtained"] += m.marks_obtained
        students_in_marks[m.student_id]["total_max"] += m.total_marks
        students_in_marks[m.student_id]["marks_count"] += 1
        if m.remarks and m.remarks not in students_in_marks[m.student_id]["remarks"]:
            students_in_marks[m.student_id]["remarks"].append(m.remarks)

    # Sort exam names logically if possible
    known_exam_order = ["Internal Assessment 1", "Assignment 1", "Mid Term Examination", "Final Exam"]
    
    def get_sort_key(ex_name):
        base_name = ex_name.split(": ")[-1] if ": " in ex_name else ex_name
        return known_exam_order.index(base_name) if base_name in known_exam_order else 99

    sorted_exam_names = sorted(exam_names_set, key=get_sort_key)

    marks_matrix = []
    for s_id, s_data in students_in_marks.items():
        total_obt = round(s_data["total_obtained"], 1)
        total_m = round(s_data["total_max"], 1)
        pct = round((total_obt / total_m * 100), 1) if total_m > 0 else 0.0
        marks_matrix.append({
            "student": s_data["student"],
            "exams": s_data["exams"],
            "total_obtained": total_obt,
            "total_max": total_m,
            "percentage": pct,
            "remarks": ", ".join(s_data["remarks"]) if s_data["remarks"] else ""
        })

    # Sort students by roll number
    marks_matrix.sort(key=lambda x: str(x["student"].roll_number))

    return render_template(
        "marks/index.html",
        subjects=subjects,
        selected_subject=selected_subject,
        marks=marks_list,
        marks_matrix=marks_matrix,
        exam_names=sorted_exam_names,
        classes=available_classes,
        class_filter=class_filter,
        exam_filter=exam_filter
    )


STANDARD_EXAMS = [
    "Internal Assessment 1",
    "Internal Assessment 2",
    "Mid Term Examination",
    "Assignment 1",
    "Assignment 2",
    "Lab Internal Assessment",
    "Lab Model Practical Exam",
    "Lab Record & Viva",
    "Semester End Examination",
    "Final Exam"
]


def get_exam_choices():
    """Retrieve union of standard exam names and any custom exam names already in the DB."""
    db_exams = [r[0] for r in db.session.query(Mark.exam_name).distinct().all() if r[0]]
    # Keep order: standard exams first, then any extra unique exams from DB
    seen = set()
    choices = []
    for e in STANDARD_EXAMS:
        if e not in seen:
            seen.add(e)
            choices.append(e)
    for e in db_exams:
        if e not in seen:
            seen.add(e)
            choices.append(e)
    return choices


@marks_bp.route("/assign", methods=["GET", "POST"])
@login_required
@staff_required
def assign():
    if current_user.role == ROLE_ADMIN:
        flash("Administrators can only review, edit, or remove existing student marks. Marks assignment is handled by Course Lecturers, HODs, and Directors.", "warning")
        return redirect(url_for("marks.index"))

    subjects = get_authorized_subjects()
    subject_id = request.args.get("subject_id", type=int) or request.form.get("subject_id", type=int)
    class_filter = request.args.get("class_name", "").strip() or request.form.get("class_name", "").strip()

    if not subject_id and subjects:
        subject_id = subjects[0].id

    selected_subject = Subject.query.get(subject_id) if subject_id else None

    # Restrict faculty to their authorized subjects
    auth_ids = {s.id for s in subjects}
    if current_user.role == ROLE_FACULTY:
        if not selected_subject or selected_subject.id not in auth_ids:
            flash("You can only enter marks for your own assigned subjects.", "danger")
            return redirect(url_for("marks.index"))
    elif selected_subject and selected_subject.id not in auth_ids and current_user.role != ROLE_ADMIN:
        flash("You are not authorized to enter marks for this subject.", "danger")
        return redirect(url_for("marks.index"))

    # Available classes
    available_classes = sorted(list(set(
        [c[0] for c in db.session.query(Student.class_name).distinct().all() if c[0]] +
        [d[0] for d in db.session.query(Student.department).distinct().all() if d[0]]
    )))

    # Query students based on class_filter
    students_query = Student.query
    if class_filter:
        students_query = students_query.filter(
            (Student.class_name == class_filter) | (Student.department == class_filter)
        )
    elif selected_subject and current_user.role == ROLE_HOD and current_user.department:
        students_query = students_query.filter(
            (Student.department == current_user.department) | (Student.class_name == current_user.department)
        )
    students = students_query.order_by(Student.roll_number).all()
    exam_choices = get_exam_choices()

    if request.method == "POST" and "submit_marks" in request.form:
        custom_exam = request.form.get("custom_exam_name", "").strip()
        selected_exam = request.form.get("exam_name", "").strip()
        exam_name = custom_exam if custom_exam else selected_exam

        try:
            total_marks = float(request.form.get("total_marks", 100))
            if total_marks <= 0:
                flash("Total / Max marks must be greater than 0.", "danger")
                return redirect(url_for("marks.assign", subject_id=subject_id, class_name=class_filter))
        except (ValueError, TypeError):
            total_marks = 100.0

        if not selected_subject:
            flash("Please select a valid subject.", "danger")
            return redirect(url_for("marks.assign", subject_id=subject_id, class_name=class_filter))

        if not exam_name:
            flash("Please select or enter an Exam Name.", "danger")
            return redirect(url_for("marks.assign", subject_id=subject_id, class_name=class_filter))

        # Check if any student marks exceed maximum marks
        for student in students:
            raw_val = request.form.get(f"marks_{student.id}", "").strip()
            if raw_val != "":
                try:
                    obtained_val = float(raw_val)
                    if obtained_val < 0:
                        flash(f"Marks obtained cannot be negative (Student: {student.name} - {student.roll_number}).", "danger")
                        return redirect(url_for("marks.assign", subject_id=subject_id, class_name=class_filter))
                    if obtained_val > total_marks:
                        flash(f"Marks obtained ({obtained_val}) cannot exceed maximum marks ({total_marks}) for {student.name} ({student.roll_number})!", "danger")
                        return redirect(url_for("marks.assign", subject_id=subject_id, class_name=class_filter))
                except ValueError:
                    flash(f"Invalid marks entered for {student.name}.", "danger")
                    return redirect(url_for("marks.assign", subject_id=subject_id, class_name=class_filter))

        saved_count = 0
        for student in students:
            obtained_key = f"marks_{student.id}"
            remarks_key = f"remarks_{student.id}"
            
            raw_val = request.form.get(obtained_key, "").strip()
            remarks_val = request.form.get(remarks_key, "").strip()

            if raw_val != "":
                try:
                    obtained_val = float(raw_val)
                except ValueError:
                    continue

                # Check if mark record already exists for this student, subject, and exam_name
                existing_mark = Mark.query.filter_by(
                    student_id=student.id,
                    subject_id=selected_subject.id,
                    exam_name=exam_name
                ).first()

                if existing_mark:
                    existing_mark.marks_obtained = obtained_val
                    existing_mark.total_marks = total_marks
                    existing_mark.remarks = remarks_val
                else:
                    new_mark = Mark(
                        student_id=student.id,
                        subject_id=selected_subject.id,
                        exam_name=exam_name,
                        marks_obtained=obtained_val,
                        total_marks=total_marks,
                        remarks=remarks_val
                    )
                    db.session.add(new_mark)

                # Send in-app notification to student account if user exists
                if student.user:
                    db.session.add(Notification(
                        user_id=student.user.id,
                        message=f"Marks Updated: {selected_subject.name} - {exam_name}: {obtained_val}/{total_marks}"
                    ))

                saved_count += 1

        db.session.commit()
        flash(f"Successfully recorded marks for {saved_count} student(s) in {selected_subject.name} ({exam_name}).", "success")
        return redirect(url_for("marks.index", subject_id=selected_subject.id))

    return render_template(
        "marks/assign.html",
        subjects=subjects,
        selected_subject=selected_subject,
        students=students,
        classes=available_classes,
        class_filter=class_filter,
        exam_choices=exam_choices
    )


@marks_bp.route("/<int:mark_id>/edit", methods=["GET", "POST"])
@login_required
@staff_required
def edit(mark_id):
    mark = Mark.query.get_or_404(mark_id)

    # Restrict permissions: faculty can only edit marks of their own subject
    if current_user.role == ROLE_FACULTY and mark.subject.faculty_id != current_user.id:
        flash("You can only edit marks for your own assigned subject.", "danger")
        return redirect(url_for("marks.index"))
    elif current_user.role == ROLE_HOD and current_user.department:
        auth_subject_ids = {s.id for s in get_authorized_subjects()}
        if mark.subject_id not in auth_subject_ids:
            flash("You can only edit marks for subjects in your department.", "danger")
            return redirect(url_for("marks.index"))

    exam_choices = get_exam_choices()

    if request.method == "POST":
        try:
            obt = float(request.form.get("marks_obtained", mark.marks_obtained))
            tot = float(request.form.get("total_marks", mark.total_marks))
        except ValueError:
            flash("Invalid marks values entered.", "danger")
            return redirect(url_for("marks.edit", mark_id=mark.id))

        if tot <= 0:
            flash("Total marks must be greater than 0.", "danger")
            return redirect(url_for("marks.edit", mark_id=mark.id))

        if obt < 0:
            flash("Marks obtained cannot be negative.", "danger")
            return redirect(url_for("marks.edit", mark_id=mark.id))

        if obt > tot:
            flash(f"Marks obtained ({obt}) cannot exceed maximum total marks ({tot})!", "danger")
            return redirect(url_for("marks.edit", mark_id=mark.id))

        custom_exam = request.form.get("custom_exam_name", "").strip()
        selected_exam = request.form.get("exam_name", "").strip()
        exam_name = custom_exam if custom_exam else selected_exam
        if not exam_name:
            exam_name = mark.exam_name

        mark.marks_obtained = obt
        mark.total_marks = tot
        mark.exam_name = exam_name
        mark.remarks = request.form.get("remarks", "").strip()
        db.session.commit()
        flash("Mark record updated successfully.", "success")
        return redirect(url_for("marks.index", subject_id=mark.subject_id))

    return render_template("marks/edit.html", mark=mark, exam_choices=exam_choices)


@marks_bp.route("/<int:mark_id>/delete", methods=["POST"])
@login_required
@staff_required
def delete(mark_id):
    mark = Mark.query.get_or_404(mark_id)

    # Restrict permissions: faculty can only delete marks of their own subject
    if current_user.role == ROLE_FACULTY and mark.subject.faculty_id != current_user.id:
        flash("You can only delete marks for your own assigned subject.", "danger")
        return redirect(url_for("marks.index"))
    elif current_user.role == ROLE_HOD and current_user.department:
        auth_subject_ids = {s.id for s in get_authorized_subjects()}
        if mark.subject_id not in auth_subject_ids:
            flash("You can only delete marks for subjects in your department.", "danger")
            return redirect(url_for("marks.index"))

    subject_id = mark.subject_id
    db.session.delete(mark)
    db.session.commit()
    flash("Mark record deleted.", "info")
    return redirect(url_for("marks.index", subject_id=subject_id))
