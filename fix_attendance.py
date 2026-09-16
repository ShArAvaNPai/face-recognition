from app import create_app
from extensions import db
from models import Student, Attendance, AttendanceSession

app = create_app()

with app.app_context():
    # Make everyone present for all sessions
    Attendance.query.update({Attendance.status: 'present'})
    
    # Pick 2 students to have low attendance (e.g., student IDs 1 and 2 if they exist)
    students = Student.query.limit(2).all()
    for student in students:
        # Mark them absent for most sessions
        attendances = Attendance.query.filter_by(student_id=student.id).all()
        # Mark 80% of their attendances as absent
        for i, att in enumerate(attendances):
            if i % 5 != 0: # 80% absent
                att.status = 'absent'
    
    db.session.commit()
    print("Attendance updated: Everyone is present, except 2 students who have low attendance.")
