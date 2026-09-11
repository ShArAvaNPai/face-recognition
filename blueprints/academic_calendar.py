"""Academic Calendar Blueprint: view and manage public holidays, exams, and academic milestones."""
from datetime import date, datetime, timedelta
import calendar
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import AcademicCalendarEvent, ROLE_ADMIN, ROLE_DIRECTOR, ROLE_HOD

calendar_bp = Blueprint("calendar", __name__, url_prefix="/calendar")


@calendar_bp.route("/")
@login_required
def index():
    # Month/Year navigation
    today = date.today()
    try:
        year = int(request.args.get("year", today.year))
        month = int(request.args.get("month", today.month))
    except (ValueError, TypeError):
        year, month = today.year, today.month

    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1

    # Filter parameters
    cat_filter = request.args.get("category", "all")
    dept_filter = request.args.get("department", "all")

    # Fetch all events
    query = AcademicCalendarEvent.query
    if cat_filter != "all":
        query = query.filter_by(category=cat_filter)
    if dept_filter != "all":
        query = query.filter((AcademicCalendarEvent.department == dept_filter) | (AcademicCalendarEvent.department == "All"))
    
    events = query.order_by(AcademicCalendarEvent.start_date.asc()).all()

    # Build calendar month grid
    cal = calendar.Calendar(firstweekday=6) # Sunday first
    month_days = cal.monthdatescalendar(year, month)

    # Map events to days
    day_events_map = {}
    for week in month_days:
        for d in week:
            day_str = d.isoformat()
            day_events_map[day_str] = [
                e for e in events 
                if e.start_date <= d <= e.end_date
            ]

    # Quick summaries
    upcoming_holidays = [e for e in events if e.category == "holiday" and e.end_date >= today][:5]
    upcoming_exams = [e for e in events if e.category == "exam" and e.end_date >= today][:5]

    prev_month_url = url_for("calendar.index", year=year if month > 1 else year - 1, 
                             month=month - 1 if month > 1 else 12, 
                             category=cat_filter, department=dept_filter)
    next_month_url = url_for("calendar.index", year=year if month < 12 else year + 1, 
                             month=month + 1 if month < 12 else 1, 
                             category=cat_filter, department=dept_filter)

    month_name = calendar.month_name[month]

    return render_template(
        "calendar/index.html",
        events=events,
        month_days=month_days,
        day_events_map=day_events_map,
        current_year=year,
        current_month=month,
        month_name=month_name,
        today=today,
        prev_month_url=prev_month_url,
        next_month_url=next_month_url,
        cat_filter=cat_filter,
        dept_filter=dept_filter,
        upcoming_holidays=upcoming_holidays,
        upcoming_exams=upcoming_exams,
        can_manage=(current_user.role in [ROLE_ADMIN, ROLE_DIRECTOR, ROLE_HOD])
    )


@calendar_bp.route("/add", methods=["POST"])
@login_required
def add_event():
    if current_user.role not in [ROLE_ADMIN, ROLE_DIRECTOR, ROLE_HOD]:
        flash("You do not have permission to add calendar events.", "danger")
        return redirect(url_for("calendar.index"))

    title = request.form.get("title", "").strip()
    category = request.form.get("category", "holiday").strip()
    start_date_str = request.form.get("start_date", "").strip()
    end_date_str = request.form.get("end_date", "").strip() or start_date_str
    department = request.form.get("department", "All").strip()
    description = request.form.get("description", "").strip()

    if not title or not start_date_str:
        flash("Event title and start date are required.", "danger")
        return redirect(url_for("calendar.index"))

    try:
        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)
        if end_date < start_date:
            end_date = start_date
    except ValueError:
        flash("Invalid date format.", "danger")
        return redirect(url_for("calendar.index"))

    evt = AcademicCalendarEvent(
        title=title,
        category=category,
        start_date=start_date,
        end_date=end_date,
        department=department,
        description=description
    )
    db.session.add(evt)
    db.session.commit()
    flash(f"Academic event '{title}' added to the calendar successfully.", "success")
    return redirect(url_for("calendar.index", year=start_date.year, month=start_date.month))


@calendar_bp.route("/<int:event_id>/delete", methods=["POST"])
@login_required
def delete_event(event_id):
    if current_user.role not in [ROLE_ADMIN, ROLE_DIRECTOR, ROLE_HOD]:
        flash("You do not have permission to delete calendar events.", "danger")
        return redirect(url_for("calendar.index"))

    evt = AcademicCalendarEvent.query.get_or_404(event_id)
    title = evt.title
    db.session.delete(evt)
    db.session.commit()
    flash(f"Event '{title}' removed from calendar.", "info")
    return redirect(url_for("calendar.index"))
