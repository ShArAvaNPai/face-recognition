"""Database models for the Smart Attendance System (core modules)."""
from datetime import datetime, date

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db

# Roles
ROLE_ADMIN = "admin"
ROLE_FACULTY = "faculty"
ROLE_STUDENT = "student"
ROLES = (ROLE_ADMIN, ROLE_FACULTY, ROLE_STUDENT)


class User(UserMixin, db.Model):
    """Authentication account. A student user is linked to a Student row."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_STUDENT)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Only set for student accounts.
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=True)
    student = db.relationship("Student", backref=db.backref("user", uselist=False))

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
    """One stored 128-d SFace feature vector for a student.

    Multiple samples per student improve recognition accuracy.
    The feature is stored as raw float32 bytes.
    """
    __tablename__ = "face_samples"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
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
