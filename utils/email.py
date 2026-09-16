from flask_mail import Message
from extensions import mail
from flask import current_app
import threading

def send_async_email(app, msg):
    """Send email asynchronously to avoid blocking the main thread."""
    with app.app_context():
        try:
            mail.send(msg)
            print(f"[Email] Sent to {msg.recipients}")
        except Exception as e:
            print(f"[Email Error] Failed to send email: {e}")


def send_email(subject, recipients, text_body, html_body=None):
    """
    Constructs an email and starts a background thread to send it.
    """
    msg = Message(subject,
                  sender=current_app.config['MAIL_DEFAULT_SENDER'],
                  recipients=recipients)
    msg.body = text_body
    if html_body:
        msg.html = html_body

    # Extract the actual app instance from the proxy
    app = current_app._get_current_object()
    thread = threading.Thread(target=send_async_email, args=(app, msg))
    thread.start()
    return thread


def generate_low_attendance_html(student_name, roll_number, department, attendance_pct, present_count, total_count, custom_note=""):
    absent_count = total_count - present_count
    note_html = f"<p style='margin-top:12px; font-size:14px; color:#334155;'><strong>Admin Note:</strong> {custom_note}</p>" if custom_note else ""
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; background-color: #ffffff; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
      <div style="background: linear-gradient(135deg, #4338ca, #6366f1); padding: 24px; color: #ffffff;">
        <h2 style="margin: 0; font-size: 22px; font-weight: 700;">⚠️ Low Attendance Alert Notice</h2>
        <p style="margin: 6px 0 0 0; font-size: 14px; opacity: 0.9;">Smart Attendance Management System</p>
      </div>
      <div style="padding: 24px;">
        <p style="font-size: 15px; color: #1e293b;">Dear Parent/Guardian,</p>
        <p style="font-size: 14px; color: #334155; line-height: 1.6;">
          This is an official communication regarding the attendance record of your child, <strong>{student_name}</strong> (Roll No: <strong>{roll_number}</strong>), studying in the <strong>{department or 'General'}</strong> department.
        </p>
        <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 16px; margin: 20px 0; border-radius: 6px;">
          <p style="margin: 0; color: #991b1b; font-weight: bold; font-size: 18px;">Overall Attendance: {attendance_pct}%</p>
          <p style="margin: 6px 0 0 0; color: #7f1d1d; font-size: 14px;">Classes Attended: <strong>{present_count}</strong> / <strong>{total_count}</strong> total classes (Absent: <strong>{absent_count}</strong>)</p>
        </div>
        <p style="font-size: 14px; color: #334155; line-height: 1.6;">
          Institutional policy mandates a minimum of <strong>75% attendance</strong> to be eligible for university examinations. Please advise your ward to attend all scheduled lectures regularly to improve their attendance standing.
        </p>
        {note_html}
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0 16px 0;">
        <p style="font-size: 12px; color: #94a3b8; margin: 0; text-align: center;">This is an automated notification from the Academic Administration Office.</p>
      </div>
    </div>
    """


def generate_absence_html(student_name, roll_number, department, subject_name, session_date, custom_note=""):
    note_html = f"<p style='margin-top:12px; font-size:14px; color:#334155;'><strong>Note:</strong> {custom_note}</p>" if custom_note else ""
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; background-color: #ffffff; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
      <div style="background: linear-gradient(135deg, #dc2626, #ef4444); padding: 24px; color: #ffffff;">
        <h2 style="margin: 0; font-size: 22px; font-weight: 700;">🚨 Class Absence Notice</h2>
        <p style="margin: 6px 0 0 0; font-size: 14px; opacity: 0.9;">Smart Attendance Management System</p>
      </div>
      <div style="padding: 24px;">
        <p style="font-size: 15px; color: #1e293b;">Dear Parent/Guardian,</p>
        <p style="font-size: 14px; color: #334155; line-height: 1.6;">
          We wish to inform you that your child <strong>{student_name}</strong> (Roll No: <strong>{roll_number}</strong>) was marked <span style="color:#dc2626; font-weight:bold;">ABSENT</span> for the following lecture:
        </p>
        <div style="background-color: #fff7ed; border-left: 4px solid #f97316; padding: 16px; margin: 20px 0; border-radius: 6px;">
          <p style="margin: 0; color: #9a3412; font-weight: bold; font-size: 16px;">Subject: {subject_name}</p>
          <p style="margin: 6px 0 0 0; color: #c2410c; font-size: 14px;">Date: <strong>{session_date}</strong> | Department: <strong>{department or 'General'}</strong></p>
        </div>
        <p style="font-size: 14px; color: #334155; line-height: 1.6;">
          If this absence was due to illness or approved leave, please ensure a valid medical certificate or leave request is submitted to the college administration.
        </p>
        {note_html}
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0 16px 0;">
        <p style="font-size: 12px; color: #94a3b8; margin: 0; text-align: center;">This is an official message from Smart Attendance System Administration.</p>
      </div>
    </div>
    """


def generate_custom_parent_html(student_name, roll_number, subject_heading, body_message):
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; background-color: #ffffff; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
      <div style="background: linear-gradient(135deg, #1e293b, #334155); padding: 24px; color: #ffffff;">
        <h2 style="margin: 0; font-size: 20px; font-weight: 700;">{subject_heading}</h2>
        <p style="margin: 6px 0 0 0; font-size: 14px; opacity: 0.9;">Smart Attendance Administration Notice</p>
      </div>
      <div style="padding: 24px;">
        <p style="font-size: 15px; color: #1e293b;">Dear Parent/Guardian of <strong>{student_name}</strong> ({roll_number}),</p>
        <div style="font-size: 14px; color: #334155; line-height: 1.6; white-space: pre-line; margin: 16px 0;">
          {body_message}
        </div>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0 16px 0;">
        <p style="font-size: 12px; color: #94a3b8; margin: 0; text-align: center;">Smart Attendance System • Administrative Office</p>
      </div>
    </div>
    """

