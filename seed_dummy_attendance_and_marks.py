import random
from datetime import date, timedelta
from app import app
from extensions import db
from models import Student, Subject, AttendanceSession, Attendance, Mark, User, ROLE_FACULTY

def seed_data():
    with app.app_context():
        students = Student.query.all()
        if not students:
            print("No students found to seed!")
            return

        # 1. Ensure subjects exist
        subjects_data = [
            {"code": "MCA101", "name": "Python & Data Science", "dept": "MCA"},
            {"code": "MCA102", "name": "Database Management Systems", "dept": "MCA"},
            {"code": "MCA103", "name": "Web Technologies & Frameworks", "dept": "MCA"},
            {"code": "MCA104", "name": "Software Engineering & Agile", "dept": "MCA"},
            {"code": "MBA101", "name": "Financial Management", "dept": "MBA"},
            {"code": "MBA102", "name": "Marketing Strategy", "dept": "MBA"},
        ]

        faculty = User.query.filter_by(role=ROLE_FACULTY).first()
        faculty_id = faculty.id if faculty else None

        subjects = []
        for sdata in subjects_data:
            subj = Subject.query.filter_by(code=sdata["code"]).first()
            if not subj:
                subj = Subject(code=sdata["code"], name=sdata["name"], faculty_id=faculty_id)
                db.session.add(subj)
                db.session.flush()
            subjects.append(subj)

        db.session.commit()

        # 2. Create Attendance Sessions and Attendance Records
        today = date.today()
        dates = [today - timedelta(days=i) for i in range(1, 6)]
        
        session_count = 0
        attendance_count = 0

        for subj in subjects:
            for d in dates:
                # Find or create session
                sess = AttendanceSession.query.filter_by(subject_id=subj.id, session_date=d).first()
                if not sess:
                    dept_students = [st for st in students if st.department == ( "MCA" if "MCA" in subj.code else "MBA")]
                    class_name = dept_students[0].class_name if dept_students else "2nd Year MCA"
                    sess = AttendanceSession(
                        subject_id=subj.id,
                        faculty_id=faculty_id,
                        class_name=class_name,
                        session_date=d
                    )
                    db.session.add(sess)
                    db.session.flush()
                    session_count += 1

                # Add attendance records for all students matching the department/class
                target_students = [st for st in students if not st.department or ( "MCA" in subj.code and st.department == "MCA" ) or ( "MBA" in subj.code and st.department == "MBA" )]
                for st in target_students:
                    existing_att = Attendance.query.filter_by(session_id=sess.id, student_id=st.id).first()
                    if not existing_att:
                        status = "present" if random.random() > 0.15 else "absent"
                        method = "face" if status == "present" else "manual"
                        att = Attendance(
                            session_id=sess.id,
                            student_id=st.id,
                            status=status,
                            method=method
                        )
                        db.session.add(att)
                        attendance_count += 1

        # 3. Create Marks Records for All Students
        exams = [
            {"name": "Internal Assessment 1", "total": 20, "min_score": 12, "max_score": 20},
            {"name": "Assignment 1", "total": 10, "min_score": 7, "max_score": 10},
            {"name": "Mid Term Examination", "total": 50, "min_score": 30, "max_score": 48},
        ]

        marks_count = 0
        for st in students:
            dept_subjs = [sb for sb in subjects if (st.department == "MBA" and "MBA" in sb.code) or (st.department != "MBA" and "MCA" in sb.code)]
            for subj in dept_subjs:
                for exam in exams:
                    existing_mark = Mark.query.filter_by(student_id=st.id, subject_id=subj.id, exam_name=exam["name"]).first()
                    if not existing_mark:
                        score = random.randint(exam["min_score"], exam["max_score"])
                        remarks = "Excellent" if score >= exam["total"] * 0.85 else "Good"
                        m = Mark(
                            student_id=st.id,
                            subject_id=subj.id,
                            exam_name=exam["name"],
                            marks_obtained=score,
                            total_marks=exam["total"],
                            remarks=remarks
                        )
                        db.session.add(m)
                        marks_count += 1

        db.session.commit()
        print(f"Dummy data seeded: {session_count} new sessions, {attendance_count} attendance records, {marks_count} mark records.")

if __name__ == "__main__":
    seed_data()
