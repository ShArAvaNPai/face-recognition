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
    global_total = 0
    if subject_id:
        global_total = AttendanceSession.query.filter_by(subject_id=subject_id).count()
    else:
        global_total = AttendanceSession.query.count()

    rows = []
    for student in Student.query.order_by(Student.roll_number).all():
        records = student.attendance_records
        if subject_id:
            records = [r for r in records if r.session.subject_id == subject_id]
        
        total = len(records)
        present = sum(1 for r in records if r.status in ("present", "excused"))
        pct = round(100.0 * present / total, 1) if total > 0 else 0.0
        
        rows.append({
            "student": student,
            "present": present,
            "total": total,
            "percentage": pct,
        })
    return global_total, rows


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
               
    total_sessions = len(records)
    present = sum(1 for r in records if r.status in ["present", "excused"])
    pct = round(100.0 * present / total_sessions, 1) if total_sessions else 0.0

    # Subject-wise attendance breakdown (Subjects as rows)
    subjects_map = {}
    for r in records:
        subj = r.session.subject
        if subj.id not in subjects_map:
            subjects_map[subj.id] = {
                'subject': subj,
                'total': 0,
                'present': 0,
                'absent': 0,
                'excused': 0
            }
        subjects_map[subj.id]['total'] += 1
        if r.status == 'present':
            subjects_map[subj.id]['present'] += 1
        elif r.status == 'excused':
            subjects_map[subj.id]['excused'] += 1
            subjects_map[subj.id]['present'] += 1 # excused counts toward presence
        else:
            subjects_map[subj.id]['absent'] += 1

    for s_id, s_data in subjects_map.items():
        s_data['percentage'] = round((s_data['present'] / s_data['total']) * 100, 1) if s_data['total'] > 0 else 0.0

    return render_template("reports/student.html", student=student,
                           records=records, present=present,
                           total_sessions=total_sessions, percentage=pct,
                           subject_attendance=list(subjects_map.values()))
