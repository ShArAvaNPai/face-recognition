"""Dashboard: a role-aware landing page with quick stats."""
import os
from datetime import date, timedelta
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user

from models import (Student, Subject, AttendanceSession, Attendance, User,
                    FaceSample, MedicalCertificate, ROLE_STUDENT, TimetableSlot,
                    TimetableClaim, LeaveApplication, FacultyAttendanceSession,
                    FacultyAttendance)

dashboard_bp = Blueprint("dashboard", __name__)


def is_faculty_absent(faculty_id, check_date):
    if not faculty_id:
        return False
    # 1. Check approved or pending leaves
    leave = LeaveApplication.query.filter(
        LeaveApplication.user_id == faculty_id,
        LeaveApplication.status.in_(['approved', 'pending']),
        LeaveApplication.start_date <= check_date,
        LeaveApplication.end_date >= check_date
    ).first()
    if leave:
        return True
    # 2. Check if marked absent in faculty attendance session
    sessions = FacultyAttendanceSession.query.filter_by(session_date=check_date).all()
    for s in sessions:
        att = FacultyAttendance.query.filter_by(session_id=s.id, faculty_id=faculty_id).first()
        if att and att.status == 'absent':
            return True
    return False


def get_week_dates(ref_date):
    weekday = ref_date.weekday()
    if weekday >= 5:  # Saturday or Sunday
        # Snap to the upcoming Monday
        monday = ref_date + timedelta(days=7 - weekday)
    else:
        monday = ref_date - timedelta(days=weekday)
    return {
        'Monday': monday,
        'Tuesday': monday + timedelta(days=1),
        'Wednesday': monday + timedelta(days=2),
        'Thursday': monday + timedelta(days=3),
        'Friday': monday + timedelta(days=4)
    }


@dashboard_bp.route("/")
@login_required
def index():
    if current_user.role == "parent":
        return redirect(url_for("parents.dashboard"))
    if current_user.role == ROLE_STUDENT:
        return _student_dashboard()
    return _staff_dashboard()


def _staff_dashboard():
    # Date handling
    date_param = request.args.get("date")
    try:
        ref_date = date.fromisoformat(date_param) if date_param else date.today()
    except ValueError:
        ref_date = date.today()
        
    week_dates = get_week_dates(ref_date)
    monday = week_dates['Monday']
    
    # Navigation dates relative to the week's Monday
    prev_week_date = (monday - timedelta(days=7)).isoformat()
    next_week_date = (monday + timedelta(days=7)).isoformat()
    
    # Subjects of current user for the claim form dropdown
    my_subjects = []
    all_subjects = []
    if current_user.role in ['director', 'hod']:
        my_subjects = Subject.query.filter_by(code="research").all()
        if not my_subjects:
            my_subjects = Subject.query.filter_by(faculty_id=current_user.id).all()
    elif current_user.role == 'admin':
        all_subjects = Subject.query.filter(Subject.faculty_id != None).all()
    else:
        my_subjects = Subject.query.filter_by(faculty_id=current_user.id).all()

    stats = {
        "students": Student.query.count(),
        "faces": FaceSample.query.count(),
        "subjects": Subject.query.count(),
        "sessions": AttendanceSession.query.count(),
        "users": User.query.count(),
    }
    recent_sessions = (AttendanceSession.query
                       .order_by(AttendanceSession.id.desc())
                       .limit(5).all())
                       
    # Construct timetable grid
    slot_times = ["09:00 - 10:00", "10:00 - 11:00", "11:00 - 12:00", "13:00 - 14:00", "14:00 - 15:00", "15:00 - 16:00"]
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    grid = []
    
    dept = current_user.department or request.args.get("dept") or "MCA"
    department_faculty = User.query.filter(User.role.in_(['faculty', 'hod']), (User.department == dept) | (User.department == '')).order_by(User.username).all()

    for time_str in slot_times:
        row = {"time": time_str, "days": {}}
        for day in days:
            slot = TimetableSlot.query.filter_by(department=dept, day_of_week=day, slot_time=time_str).first()
            cell = {
                "slot": slot,
                "subject": None,
                "faculty": None,
                "is_empty": True,
                "is_absent": False,
                "is_claimed": False,
                "claimable": False,
                "can_release": False,
                "claim_id": None,
                "cell_date": week_dates[day].isoformat()
            }
            if slot:
                cell_date = week_dates[day]
                default_faculty_id = slot.subject.faculty_id if slot.subject else None
                is_absent = is_faculty_absent(default_faculty_id, cell_date)
                cell["is_absent"] = is_absent
                
                # Check for claim
                claim = TimetableClaim.query.filter_by(slot_id=slot.id, claim_date=cell_date).first()
                if claim:
                    cell["is_claimed"] = True
                    cell["subject"] = claim.subject
                    cell["faculty"] = claim.claimed_by
                    cell["is_empty"] = False
                    cell["can_release"] = (claim.claimed_by_id == current_user.id or current_user.role in ['admin', 'hod', 'director'])
                    cell["claim_id"] = claim.id
                else:
                    if is_absent or slot.subject is None:
                        cell["is_empty"] = True
                        cell["claimable"] = (current_user.role != ROLE_STUDENT and current_user.id != default_faculty_id)
                    else:
                        cell["subject"] = slot.subject
                        cell["faculty"] = slot.subject.faculty if slot.subject else None
                        cell["is_empty"] = (slot.subject is None)
                        cell["claimable"] = (current_user.role in ['hod', 'director', 'admin'])
            row["days"][day] = cell
        grid.append(row)
        
    return render_template("dashboard/staff.html", stats=stats,
                           recent_sessions=recent_sessions,
                           timetable_grid=grid,
                           timetable_days=days,
                           week_dates=week_dates,
                           prev_week_date=prev_week_date,
                           next_week_date=next_week_date,
                           my_subjects=my_subjects,
                           all_subjects=all_subjects,
                           department_faculty=department_faculty,
                           current_date_str=ref_date.isoformat())


@dashboard_bp.route("/timetable/claim", methods=["POST"])
@login_required
def claim_slot():
    if current_user.role == ROLE_STUDENT:
        flash("Students cannot claim timetable slots.", "danger")
        return redirect(url_for("dashboard.index"))
    slot_id = request.form.get("slot_id", type=int)
    claim_date_str = request.form.get("claim_date")
    subject_id = request.form.get("subject_id", type=int)
    assignee_id = request.form.get("assignee_id", type=int)
    
    try:
        claim_date = date.fromisoformat(claim_date_str)
    except (ValueError, TypeError):
        flash("Invalid claim date.", "danger")
        return redirect(url_for("dashboard.index"))
        
    slot = TimetableSlot.query.get_or_404(slot_id)
    
    # Verify default lecturer is absent, unless HOD/Director/Admin is reassigning an emergency slot
    default_faculty_id = slot.subject.faculty_id if slot.subject else None
    if slot.subject and not is_faculty_absent(default_faculty_id, claim_date):
        if current_user.role not in ['hod', 'director', 'admin']:
            flash("Cannot claim slot: Default lecturer is not absent.", "danger")
            return redirect(url_for("dashboard.index", date=claim_date_str))
        
    # Check if already claimed
    existing = TimetableClaim.query.filter_by(slot_id=slot.id, claim_date=claim_date).first()
    if existing:
        if current_user.role in ['hod', 'director', 'admin']:
            db.session.delete(existing)
            db.session.flush()
        else:
            flash("Slot is already claimed.", "danger")
            return redirect(url_for("dashboard.index", date=claim_date_str))
        
    # Determine target faculty (assignee)
    if current_user.role in ['hod', 'director', 'admin'] and assignee_id:
        claimed_by_id = assignee_id
    elif current_user.role == 'admin' and subject_id:
        sub = Subject.query.get(subject_id)
        claimed_by_id = sub.faculty_id if sub and sub.faculty_id else current_user.id
    else:
        claimed_by_id = current_user.id

    # Determine subject
    subject = None
    if subject_id:
        subject = Subject.query.get(subject_id)
    elif current_user.role in ['director', 'hod']:
        subject = Subject.query.filter_by(code="research").first()
        if not subject:
            subject = Subject.query.filter_by(faculty_id=claimed_by_id).first()
    elif current_user.role in ['faculty', 'admin']:
        subject = Subject.query.filter_by(faculty_id=claimed_by_id).first()
        
    if not subject and slot.subject:
        subject = slot.subject

    claim = TimetableClaim(
        slot_id=slot.id,
        claim_date=claim_date,
        claimed_by_id=claimed_by_id,
        subject_id=subject.id if subject else None
    )
    db.session.add(claim)
    
    assigned_user = User.query.get(claimed_by_id)
    assignee_name = assigned_user.username if assigned_user else 'faculty'

    if subject:
        # Create attendance session for substitute lecturer
        session = AttendanceSession.query.filter_by(
            subject_id=subject.id,
            faculty_id=claimed_by_id,
            session_date=claim_date
        ).first()
        if not session:
            session = AttendanceSession(
                subject_id=subject.id,
                faculty_id=claimed_by_id,
                session_date=claim_date,
                class_name=slot.department or ""
            )
            db.session.add(session)
        db.session.commit()
        
        flash(f"Slot reassigned to {assignee_name} for {claim_date}. Attendance session created.", "success")
        if claimed_by_id == current_user.id:
            return redirect(url_for("attendance.take", session_id=session.id))
        else:
            return redirect(url_for("dashboard.index", date=claim_date_str))
    else:
        db.session.commit()
        flash(f"Slot reassigned to {assignee_name} for {claim_date}.", "success")
        return redirect(url_for("dashboard.index", date=claim_date_str))


@dashboard_bp.route("/timetable/release/<int:claim_id>", methods=["POST"])
@login_required
def release_slot(claim_id):
    claim = TimetableClaim.query.get_or_404(claim_id)
    if claim.claimed_by_id != current_user.id and current_user.role not in ['admin', 'hod', 'director']:
        flash("You cannot release this claim.", "danger")
        return redirect(url_for("dashboard.index"))
        
    claim_date_str = claim.claim_date.isoformat()
    db.session.delete(claim)
    db.session.commit()
    flash("Slot re-assignment released. Reverted to default schedule.", "info")
    return redirect(url_for("dashboard.index", date=claim_date_str))



def _student_dashboard():
    student = current_user.student
    dept = (student.department if student else current_user.department) or "MCA"
    present = total = pct = 0
    subject_stats = []
    
    if student:
        # Filter subjects belonging to student's department
        subjects = Subject.query.filter(Subject.code.ilike(f"{dept}%")).all()
        if not subjects:
            subjects = Subject.query.all()

        subj_ids = [s.id for s in subjects]
        total = AttendanceSession.query.filter(AttendanceSession.subject_id.in_(subj_ids)).count() if subj_ids else 0

        present = Attendance.query.join(AttendanceSession).filter(
            Attendance.student_id == student.id,
            AttendanceSession.subject_id.in_(subj_ids),
            Attendance.status.in_(["present", "excused"])
        ).count() if subj_ids else 0

        pct = round(100.0 * present / total, 1) if total else 0.0

        # Calculate subject-wise attendance for department subjects
        for subj in subjects:
            subj_total = AttendanceSession.query.filter_by(subject_id=subj.id).count()
            if subj_total > 0:
                subj_present = Attendance.query.join(AttendanceSession).filter(
                    Attendance.student_id == student.id,
                    AttendanceSession.subject_id == subj.id,
                    Attendance.status.in_(["present", "excused"])
                ).count()
                subj_pct = round(100.0 * subj_present / subj_total, 1)
                subject_stats.append({
                    "subject": subj,
                    "present": subj_present,
                    "total": subj_total,
                    "percentage": subj_pct
                })

    # Build student's timetable based on their department (MCA / MBA)
    DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    TIMES = [
        "09:00 - 10:00", "10:00 - 11:00", "11:00 - 12:00",
        "13:00 - 14:00", "14:00 - 15:00", "15:00 - 16:00"
    ]

    timetable_grid = []
    for time_slot in TIMES:
        row = {"time": time_slot, "days": {}}
        for day in DAYS:
            slot = TimetableSlot.query.filter_by(department=dept, day_of_week=day, slot_time=time_slot).first()
            row["days"][day] = slot
        timetable_grid.append(row)

    return render_template("dashboard/student.html", student=student,
                           present=present, total=total, percentage=pct,
                           subject_stats=subject_stats,
                           timetable_grid=timetable_grid,
                           timetable_days=DAYS)


@dashboard_bp.route("/upload-certificate", methods=["POST"])
@login_required
def upload_certificate():
    if current_user.role != ROLE_STUDENT or not current_user.student:
        flash("Only students can upload medical certificates.", "danger")
        return redirect(url_for("dashboard.index"))
        
    if "certificate" not in request.files:
        flash("No file part.", "danger")
        return redirect(url_for("dashboard.index"))
        
    file = request.files["certificate"]
    if file.filename == "":
        flash("No selected file.", "danger")
        return redirect(url_for("dashboard.index"))
        
    if file:
        filename = secure_filename(f"{current_user.username}_{file.filename}")
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "instance/certificates")
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        
        file.save(file_path)
        
        reason = request.form.get("reason", "").strip()
        start_date_str = request.form.get("start_date", "")
        end_date_str = request.form.get("end_date", "")
        today = date.today()
        try:
            start_date = date.fromisoformat(start_date_str) if start_date_str else today
            end_date = date.fromisoformat(end_date_str) if end_date_str else today
        except ValueError:
            start_date = end_date = today
        cert = MedicalCertificate(
            student_id=current_user.student.id,
            file_path=filename,
            reason=reason,
            start_date=start_date,
            end_date=end_date
        )
        from extensions import db
        db.session.add(cert)
        db.session.commit()
        
        flash("Medical certificate uploaded successfully.", "success")
        
    return redirect(url_for("dashboard.index"))
