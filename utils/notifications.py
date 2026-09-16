"""In-app notification helpers — replaces email for parent alerts."""
from extensions import db
from models import Notification, ROLE_PARENT


def notify_parent(student, title, message, category="general", action_url=None):
    """Create an in-app Notification for the parent linked to *student*.

    If the student has no linked parent account the call is a no-op.
    Returns the created Notification object or None.
    """
    parent_user = student.parent_user
    if not parent_user:
        return None

    notif = Notification(
        user_id=parent_user.id,
        title=title,
        message=message,
        category=category,
        action_url=action_url,
        is_read=False,
    )
    db.session.add(notif)
    return notif


def notify_parent_absence(student, subject_name, session_date, custom_note=""):
    """Notify parent that their child was absent for a class."""
    title = "Absence Alert - " + subject_name
    msg = (
        student.name + " (" + student.roll_number + ") was marked ABSENT "
        "for " + subject_name + " on " + str(session_date) + "."
    )
    if custom_note:
        msg += "\n\nNote: " + custom_note
    return notify_parent(student, title, msg, category="absence")


def notify_parent_low_attendance(student, attendance_pct, present, total, threshold=75, custom_note=""):
    """Notify parent that their child has low attendance."""
    title = "Low Attendance Warning - " + student.name
    msg = (
        student.name + " (" + student.roll_number + ") has " + str(attendance_pct) + "% attendance "
        "(" + str(present) + "/" + str(total) + " classes attended). "
        "Minimum required: " + str(int(threshold)) + "%."
    )
    if custom_note:
        msg += "\n\nAdmin Note: " + custom_note
    return notify_parent(student, title, msg, category="attendance")


def notify_parent_custom(student, subject_heading, body_message):
    """Send a custom message to a student's parent."""
    return notify_parent(student, subject_heading, body_message, category="general")