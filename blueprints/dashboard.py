"""Dashboard: a role-aware landing page with quick stats."""
from flask import Blueprint, render_template
from flask_login import login_required, current_user

from models import (Student, Subject, AttendanceSession, Attendance, User,
                    FaceSample, ROLE_STUDENT)

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    if current_user.role == ROLE_STUDENT:
        return _student_dashboard()
    return _staff_dashboard()


def _staff_dashboard():
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
    return render_template("dashboard/staff.html", stats=stats,
                           recent_sessions=recent_sessions)


def _student_dashboard():
    student = current_user.student
    present = total = pct = 0
    if student:
        total = AttendanceSession.query.count()
        present = Attendance.query.filter_by(
            student_id=student.id, status="present").count()
        pct = round(100.0 * present / total, 1) if total else 0.0
    return render_template("dashboard/student.html", student=student,
                           present=present, total=total, percentage=pct)
