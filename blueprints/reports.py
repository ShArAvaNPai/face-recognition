"""Report Generation Module: attendance %, per-student history, CSV export."""
import csv
import io

from flask import (Blueprint, render_template, request, Response, abort)
from flask_login import login_required, current_user

from models import (Student, Subject, AttendanceSession, Attendance,
                    ROLE_STUDENT)
from blueprints.decorators import staff_required

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


def _student_stats(subject_id=None):
    """Compute (total_sessions, present_count, percentage) per student.

    If subject_id is given, restrict to that subject's sessions.
    """
    session_query = AttendanceSession.query
    if subject_id:
        session_query = session_query.filter_by(subject_id=subject_id)
    total_sessions = session_query.count()
    session_ids = [s.id for s in session_query.all()]

    rows = []
    for student in Student.query.order_by(Student.roll_number).all():
        if session_ids:
            present = Attendance.query.filter(
                Attendance.student_id == student.id,
                Attendance.session_id.in_(session_ids),
                Attendance.status == "present",
            ).count()
        else:
            present = 0
        pct = round(100.0 * present / total_sessions, 1) if total_sessions else 0.0
        rows.append({
            "student": student,
            "present": present,
            "total": total_sessions,
            "percentage": pct,
        })
    return total_sessions, rows


@reports_bp.route("/")
@login_required
@staff_required
def index():
    subject_id = request.args.get("subject_id", type=int)
    total_sessions, rows = _student_stats(subject_id)
    return render_template("reports/index.html",
                           subjects=Subject.query.order_by(Subject.code).all(),
                           selected_subject=subject_id,
                           total_sessions=total_sessions, rows=rows)


@reports_bp.route("/export.csv")
@login_required
@staff_required
def export_csv():
    subject_id = request.args.get("subject_id", type=int)
    total_sessions, rows = _student_stats(subject_id)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Roll Number", "Name", "Department", "Class",
                     "Sessions Attended", "Total Sessions", "Percentage"])
    for r in rows:
        s = r["student"]
        writer.writerow([s.roll_number, s.name, s.department, s.class_name,
                         r["present"], r["total"], r["percentage"]])

    filename = "attendance_report"
    if subject_id:
        subj = Subject.query.get(subject_id)
        if subj:
            filename += f"_{subj.code}"
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}.csv"},
    )


@reports_bp.route("/student/<int:student_id>")
@login_required
def student_detail(student_id):
    """Per-student attendance history. Students may only see their own."""
    student = Student.query.get_or_404(student_id)
    if current_user.role == ROLE_STUDENT and current_user.student_id != student.id:
        abort(403)

    records = (Attendance.query
               .filter_by(student_id=student.id)
               .join(AttendanceSession)
               .order_by(AttendanceSession.session_date.desc())
               .all())
    total_sessions = AttendanceSession.query.count()
    present = sum(1 for r in records if r.status == "present")
    pct = round(100.0 * present / total_sessions, 1) if total_sessions else 0.0
    return render_template("reports/student.html", student=student,
                           records=records, present=present,
                           total_sessions=total_sessions, percentage=pct)
