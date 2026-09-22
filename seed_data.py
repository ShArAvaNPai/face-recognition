from app import app
from extensions import db
from models import User, Student, Subject, ROLE_FACULTY, ROLE_STUDENT, ROLE_PARENT, Mark, Fee, AttendanceSession, Attendance
import random
from datetime import datetime, date, timedelta
def seed():
    print("Starting data seeding...")
    
    # 1. Add lecturers
    lecturers_info = [
        {"username": "prof_sharma", "email": "sharma@example.com", "password": "sharmapassword", "subject_code": "cs101", "subject_name": "Computer Science 101"},
        {"username": "prof_patel", "email": "patel@example.com", "password": "patelpassword", "subject_code": "math101", "subject_name": "Mathematics 101"}
    ]
    
    # Write lecturers to lecturers.txt
    with open("lecturers.txt", "w") as f:
        f.write("Lecturer Accounts:\n")
        f.write("==================\n")
        for lec in lecturers_info:
            f.write(f"Username: {lec['username']}, Password: {lec['password']}\n")
    print("Created lecturers.txt")

    for lec in lecturers_info:
        user = User.query.filter_by(username=lec["username"]).first()
        if not user:
            user = User(username=lec["username"], email=lec["email"], role=ROLE_FACULTY, department="MCA")
            user.set_password(lec["password"])
            db.session.add(user)
            db.session.flush() # get user id
            print(f"Created lecturer user: {lec['username']}")
        else:
            user.department = "MCA"
            print(f"Lecturer user {lec['username']} already exists")
            
        # Ensure subject exists for lecturer
        subj = Subject.query.filter_by(code=lec["subject_code"]).first()
        if not subj:
            subj = Subject(code=lec["subject_code"], name=lec["subject_name"], faculty_id=user.id)
            db.session.add(subj)
            print(f"Created subject: {lec['subject_name']} for {lec['username']}")
        else:
            subj.faculty_id = user.id
            print(f"Subject {lec['subject_code']} already exists, assigned to {lec['username']}")

    # 2. Add students
    departments = ["MCA", "MBA"]
    years = ["1st Year", "2nd Year"]
    first_names = ["Aarav", "Rohan", "Aditya", "Vihaan", "Arjun", "Kabir", "Sai", "Ishaan", "Ananya", "Diya", "Fatima", "Kavya", "Priya", "Sneha", "Neha", "Rahul", "Sanjay", "Amit", "Rajesh", "Dev", "Vikram", "Sunita", "Anjali", "Karan"]
    last_names = ["Sharma", "Patel", "Kumar", "Singh", "Gupta", "Mehta", "Joshi", "Rao", "Nair", "Pillai", "Iyer", "Verma", "Mishra", "Reddy", "Choudhury", "Bhatt", "Sen", "Bose", "Das", "Jadhav", "Kulkarni", "Deshmukh"]
    
    students_info = []
    for i in range(1, 101):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        username = f"student{i}_{fn.lower()}"
        dept = random.choice(departments)
        cls = random.choice(years)
        has_parent = random.random() < 0.7 # 70% chance to have a parent
        
        students_info.append({
            "username": username,
            "email": f"{username}@example.com",
            "password": f"pass{i}word",
            "roll_number": str(25000 + i),
            "name": f"{fn} {ln}",
            "dept": dept,
            "class": cls,
            "has_parent": has_parent
        })
    
    for stud in students_info:
        user = User.query.filter_by(username=stud["username"]).first()
        student = Student.query.filter_by(roll_number=stud["roll_number"]).first()
        
        if not student:
            student = Student(
                roll_number=stud["roll_number"],
                name=stud["name"],
                department=stud["dept"],
                class_name=stud["class"]
            )
            db.session.add(student)
            db.session.flush()
            print(f"Created student record: {stud['name']}")
        else:
            print(f"Student record {stud['roll_number']} already exists")
            
        if not user:
            user = User(
                username=stud["username"],
                email=stud["email"],
                role=ROLE_STUDENT,
                student_id=student.id
            )
            user.set_password(stud["password"])
            db.session.add(user)
            print(f"Created student user: {stud['username']}")
        else:
            user.student_id = student.id
            print(f"Student user {stud['username']} already exists")
            
        # Create parent user
        if stud.get("has_parent"):
            parent_username = f"parent_{stud['username']}"
            parent_user = User.query.filter_by(username=parent_username).first()
            if not parent_user:
                parent_user = User(
                    username=parent_username,
                    email=f"parent_{stud['email']}",
                    role=ROLE_PARENT,
                    student_id=student.id
                )
                parent_user.set_password(f"parent{stud['password']}")
                db.session.add(parent_user)
                print(f"Created parent user: {parent_username}")
        
    db.session.commit()
    
    # 2b. Add dummy marks, fees, and attendance (re-seed cleanly)
    print("Clearing old marks, fees, and attendance sessions...")
    Mark.query.delete()
    Fee.query.delete()
    Attendance.query.delete()
    AttendanceSession.query.delete()
    db.session.commit()

    all_students = Student.query.all()
    all_subjects = Subject.query.all()
    
    print("Generating dummy marks and fees in INR...")
    for student in all_students:
        # Dummy Marks for all subjects
        for subject in all_subjects:
            mark_mid = Mark(
                student_id=student.id,
                subject_id=subject.id,
                exam_name="Mid Term",
                marks_obtained=round(random.uniform(40, 100), 1),
                total_marks=100.0,
                remarks="Good" if random.random() > 0.5 else "Needs Improvement"
            )
            mark_final = Mark(
                student_id=student.id,
                subject_id=subject.id,
                exam_name="Final Exam",
                marks_obtained=round(random.uniform(45, 100), 1),
                total_marks=100.0,
                remarks="Excellent" if random.random() > 0.6 else ("Good" if random.random() > 0.3 else "Needs Improvement")
            )
            db.session.add(mark_mid)
            db.session.add(mark_final)
                
        # Dummy Fees in INR
        fee1 = Fee(
            student_id=student.id,
            fee_type="Tuition Fee",
            amount_due=75000.0,
            due_date=date.today() + timedelta(days=30),
            status="Pending" if random.random() > 0.3 else "Paid"
        )
        fee2 = Fee(
            student_id=student.id,
            fee_type="Bus Fee",
            amount_due=12000.0,
            due_date=date.today() - timedelta(days=10),
            status="Paid",
            receipt_path="/static/dummy_receipt.pdf"
        )
        fee3 = Fee(
            student_id=student.id,
            fee_type="Hostel Fee",
            amount_due=35000.0,
            due_date=date.today() + timedelta(days=15),
            status="Pending" if random.random() > 0.5 else "Verification",
            receipt_path="/static/dummy_receipt.pdf" if random.random() <= 0.5 else None
        )
        db.session.add(fee1)
        db.session.add(fee2)
        db.session.add(fee3)
            
    db.session.commit()

    print("Generating random attendance records...")
    today_dt = date.today()
    past_dates = []
    for i in range(20):
        d = today_dt - timedelta(days=i)
        if d.weekday() < 5:  # Monday to Friday
            past_dates.append(d)

    for subject in all_subjects:
        # Choose 8 random dates to have attendance sessions for
        chosen_dates = random.sample(past_dates, min(len(past_dates), 10))
        for d in chosen_dates:
            session = AttendanceSession(
                subject_id=subject.id,
                faculty_id=subject.faculty_id,
                class_name="Class A",
                session_date=d
            )
            db.session.add(session)
            db.session.flush()

            for student in all_students:
                status = "present" if random.random() < 0.85 else "absent"
                method = "face" if random.random() < 0.7 else "manual"
                att = Attendance(
                    session_id=session.id,
                    student_id=student.id,
                    status=status,
                    method=method,
                    marked_at=datetime.combine(d, datetime.min.time()) + timedelta(hours=9, minutes=random.randint(5, 55))
                )
                db.session.add(att)
    db.session.commit()
    # 3. Assign subjects to timetable slots — separate timetables per department
    from models import TimetableSlot

    # Clear existing timetable slots
    TimetableSlot.query.delete()
    db.session.commit()

    # Create department-specific subjects if they don't exist
    # MCA subjects
    mca_subject_defs = [
        {"username": "prof_sharma",  "code": "cs101",    "name": "Computer Science 101"},
        {"username": "prof_patel",  "code": "math101",  "name": "Mathematics 101"},
    ]
    # MBA subjects (create dedicated faculty if needed)
    mba_faculty_defs = [
        {"username": "prof_mehta",  "email": "mehta@example.com", "password": "mehta123",
         "subject_code": "mgt201", "subject_name": "Management Principles"},
        {"username": "prof_iyer",   "email": "iyer@example.com",  "password": "iyer123",
         "subject_code": "mkt201", "subject_name": "Marketing Strategy"},
        {"username": "prof_bose",   "email": "bose@example.com",  "password": "bose123",
         "subject_code": "fin201", "subject_name": "Financial Management"},
    ]
    for fac in mba_faculty_defs:
        u = User.query.filter_by(username=fac["username"]).first()
        if not u:
            u = User(username=fac["username"], email=fac["email"], role=ROLE_FACULTY, department="MBA")
            u.set_password(fac["password"])
            db.session.add(u)
            db.session.flush()
        else:
            u.department = "MBA"
        subj = Subject.query.filter_by(code=fac["subject_code"]).first()
        if not subj:
            subj = Subject(code=fac["subject_code"], name=fac["subject_name"], faculty_id=u.id)
            db.session.add(subj)
        else:
            subj.faculty_id = u.id
    db.session.commit()

    # Fetch subject objects
    mca_subjects = [Subject.query.filter_by(code=d["code"]).first() for d in mca_subject_defs if Subject.query.filter_by(code=d["code"]).first()]
    mba_subjects = [Subject.query.filter_by(code=f["subject_code"]).first() for f in mba_faculty_defs if Subject.query.filter_by(code=f["subject_code"]).first()]

    hours = ["09:00 - 10:00", "10:00 - 11:00", "11:00 - 12:00",
             "13:00 - 14:00", "14:00 - 15:00", "15:00 - 16:00"]
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    for dept, pool in [("MCA", mca_subjects), ("MBA", mba_subjects)]:
        pool_with_free = pool + [None] * max(1, len(pool) // 2)
        for day in days:
            for hr in hours:
                chosen = random.choice(pool_with_free)
                slot = TimetableSlot(
                    department=dept,
                    day_of_week=day,
                    slot_time=hr,
                    subject_id=chosen.id if chosen else None
                )
                db.session.add(slot)

    db.session.commit()
    print("Database seeding completed and timetable randomized.")

    # 4. Generate credentials.txt with login info of everyone
    print("Writing credentials of all users to credentials.txt...")
    with open("credentials.txt", "w") as f:
        f.write("==================================================\n")
        f.write("        SMART ATTENDANCE SYSTEM CREDENTIALS       \n")
        f.write("==================================================\n\n")

        f.write("ADMINISTRATOR ACCOUNT\n")
        f.write("---------------------\n")
        f.write(f"Username: admin\nPassword: admin123\nRole: admin\n\n")

        f.write("LECTURER ACCOUNTS\n")
        f.write("-----------------\n")
        for lec in lecturers_info:
            f.write(f"Username: {lec['username']}\nPassword: {lec['password']}\nRole: faculty (Subject: {lec['subject_name']})\n\n")

        f.write("STUDENT ACCOUNTS\n")
        f.write("----------------\n")
        for stud in students_info:
            f.write(f"Username: {stud['username']}\nPassword: {stud['password']}\nRoll Number: {stud['roll_number']}\nRole: student\n\n")

        f.write("PARENT ACCOUNTS\n")
        f.write("---------------\n")
        for stud in students_info:
            if stud.get("has_parent"):
                f.write(f"Username: parent_{stud['username']}\nPassword: parent{stud['password']}\nStudent Linked: {stud['name']}\nRole: parent\n\n")

    print("Created credentials.txt successfully!")

if __name__ == "__main__":
    with app.app_context():
        seed()
