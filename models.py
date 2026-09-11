"""Database models for the Smart Attendance System (core modules)."""
from datetime import datetime, date

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db

# Roles
ROLE_ADMIN = "admin"
ROLE_FACULTY = "faculty"
ROLE_STUDENT = "student"
ROLE_DIRECTOR = "director"
ROLE_HOD = "hod"
ROLE_PARENT = "parent"
ROLES = (ROLE_ADMIN, ROLE_FACULTY, ROLE_STUDENT, ROLE_DIRECTOR, ROLE_HOD, ROLE_PARENT)


class User(UserMixin, db.Model):
    """Authentication account. A student user is linked to a Student row."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_STUDENT)
    department = db.Column(db.String(80), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Only set for student accounts.
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=True)
    student = db.relationship("Student", backref=db.backref("user", uselist=False))

    face_samples = db.relationship(
        "FaceSample", backref="user", cascade="all, delete-orphan"
    )

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    @property
    def is_faculty(self):
        return self.role == ROLE_FACULTY

    @property
    def is_student(self):
        return self.role == ROLE_STUDENT

    @property
    def is_director(self):
        return self.role == ROLE_DIRECTOR

    @property
    def is_hod(self):
        return self.role == ROLE_HOD

    @property
    def is_parent(self):
        return self.role == ROLE_PARENT

    @property
    def has_face(self):
        return len(self.face_samples) > 0

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Student(db.Model):
    """Student record / profile."""
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    roll_number = db.Column(db.String(40), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(80), default="")
    class_name = db.Column(db.String(80), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    face_samples = db.relationship(
        "FaceSample", backref="student", cascade="all, delete-orphan"
    )
    attendance_records = db.relationship(
        "Attendance", backref="student", cascade="all, delete-orphan"
    )

    @property
    def has_face(self):
        return len(self.face_samples) > 0

    def __repr__(self):
        return f"<Student {self.roll_number} {self.name}>"


class FaceSample(db.Model):
    """One stored 128-d SFace feature vector for a student or lecturer.

    Multiple samples per student or lecturer improve recognition accuracy.
    The feature is stored as raw float32 bytes.
    """
    __tablename__ = "face_samples"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    feature = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Subject(db.Model):
    """A subject taught by faculty."""
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    faculty = db.relationship("User", foreign_keys=[faculty_id])

    sessions = db.relationship(
        "AttendanceSession", backref="subject", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Subject {self.code} {self.name}>"


class AttendanceSession(db.Model):
    """An attendance-taking session for a subject on a given date/class."""
    __tablename__ = "sessions"

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    faculty = db.relationship("User", foreign_keys=[faculty_id])
    class_name = db.Column(db.String(80), default="")
    session_date = db.Column(db.Date, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    records = db.relationship(
        "Attendance", backref="session", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Session {self.id} subj={self.subject_id} {self.session_date}>"


class Attendance(db.Model):
    """A single attendance record: one student in one session."""
    __tablename__ = "attendance"
    __table_args__ = (
        db.UniqueConstraint("session_id", "student_id", name="uq_session_student"),
    )

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    status = db.Column(db.String(10), default="present")  # present / absent
    method = db.Column(db.String(10), default="face")      # face / manual
    marked_at = db.Column(db.DateTime, default=datetime.utcnow)


class FacultyAttendanceSession(db.Model):
    """An attendance-taking session for faculty on a given date."""
    __tablename__ = "faculty_sessions"

    id = db.Column(db.Integer, primary_key=True)
    taken_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    taken_by = db.relationship("User", foreign_keys=[taken_by_id])
    session_date = db.Column(db.Date, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    records = db.relationship(
        "FacultyAttendance", backref="session", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<FacultySession {self.id} {self.session_date}>"


class FacultyAttendance(db.Model):
    """A single attendance record: one faculty in one session."""
    __tablename__ = "faculty_attendance"
    __table_args__ = (
        db.UniqueConstraint("session_id", "faculty_id", name="uq_fsession_faculty"),
    )

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("faculty_sessions.id"), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    faculty = db.relationship("User", foreign_keys=[faculty_id])
    status = db.Column(db.String(10), default="present")  # present / absent
    marked_at = db.Column(db.DateTime, default=datetime.utcnow)


class LeaveApplication(db.Model):
    """A leave application submitted by a faculty member."""
    __tablename__ = "leave_applications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User", backref=db.backref("leaves", lazy=True))
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="pending")  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<LeaveApplication {self.id} {self.user_id} {self.status}>"


class MedicalCertificate(db.Model):
    """A medical certificate uploaded by a student."""
    __tablename__ = "medical_certificates"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    student = db.relationship("Student", backref=db.backref("certificates", lazy=True))
    file_path = db.Column(db.String(255), nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default="uploaded")
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    end_date = db.Column(db.Date, nullable=False, default=date.today)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<MedicalCertificate {self.id} {self.student_id}>"


class TimetableSlot(db.Model):
    """A recurring weekly timetable slot."""
    __tablename__ = "timetable_slots"

    id = db.Column(db.Integer, primary_key=True)
    department = db.Column(db.String(80), nullable=True)    # e.g. "MCA", "MBA"
    day_of_week = db.Column(db.String(20), nullable=False)  # e.g. "Monday", "Tuesday", etc.
    slot_time = db.Column(db.String(50), nullable=False)    # e.g. "09:00 - 10:00"
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=True)
    subject = db.relationship("Subject", backref=db.backref("slots", lazy=True))

    def __repr__(self):
        return f"<TimetableSlot {self.day_of_week} {self.slot_time} subj={self.subject_id}>"


class TimetableClaim(db.Model):
    """An override claim on a specific timetable slot for a specific date."""
    __tablename__ = "timetable_claims"
    __table_args__ = (
        db.UniqueConstraint("slot_id", "claim_date", name="uq_slot_date_claim"),
    )

    id = db.Column(db.Integer, primary_key=True)
    slot_id = db.Column(db.Integer, db.ForeignKey("timetable_slots.id"), nullable=False)
    slot = db.relationship("TimetableSlot", backref=db.backref("claims", lazy=True))
    claim_date = db.Column(db.Date, nullable=False)
    claimed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    claimed_by = db.relationship("User", foreign_keys=[claimed_by_id])
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=True)
    subject = db.relationship("Subject", foreign_keys=[subject_id])
    status = db.Column(db.String(20), default="approved") # approved, pending, reported
    reported_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<TimetableClaim slot={self.slot_id} date={self.claim_date} claimed_by={self.claimed_by_id}>"


class Mark(db.Model):
    """Student marks for a specific subject and exam."""
    __tablename__ = "marks"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    student = db.relationship("Student", backref=db.backref("marks", lazy=True))
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    subject = db.relationship("Subject", backref=db.backref("marks", lazy=True))
    exam_name = db.Column(db.String(100), nullable=False)
    marks_obtained = db.Column(db.Float, nullable=False)
    total_marks = db.Column(db.Float, nullable=False)
    remarks = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Mark {self.student_id} {self.subject_id} {self.marks_obtained}/{self.total_marks}>"


class Fee(db.Model):
    """Student fee records."""
    __tablename__ = "fees"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    student = db.relationship("Student", backref=db.backref("fees", lazy=True))
    fee_type = db.Column(db.String(100), nullable=False)
    amount_due = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default="Pending") # Pending, Paid, Verification
    receipt_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Fee {self.student_id} {self.fee_type} {self.status}>"


class Notification(db.Model):
    """Notification for takeover requests, reports, etc."""
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("notifications", cascade="all, delete-orphan"))
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    action_url = db.Column(db.String(255), nullable=True)
    claim_id = db.Column(db.Integer, db.ForeignKey("timetable_claims.id", ondelete="CASCADE"), nullable=True)
    claim = db.relationship("TimetableClaim", backref=db.backref("notifications", cascade="all, delete-orphan"))

    def __repr__(self):
        return f"<Notification {self.id} for user={self.user_id}>"


class AcademicCalendarEvent(db.Model):
    """Academic calendar events including public holidays, exam schedules, and academic milestones."""
    __tablename__ = "academic_calendar_events"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=False)  # 'holiday', 'exam', 'academic'
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    department = db.Column(db.String(80), default="All")  # 'All', 'MCA', 'MBA'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AcademicCalendarEvent {self.title} ({self.category}) {self.start_date}>"
