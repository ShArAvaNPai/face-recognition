import os
from app import app
from extensions import db
from models import Student, User, FaceSample

new_students = {
    "24121": "ADARSH",
    "24122": "AKHIL GOPALA NAIK",
    "24123": "ANAGHA BHAT",
    "24124": "ANEESH BHAT",
    "24125": "ANKITHA S",
    "24126": "ANUSHA K",
    "24127": "ASHISH SANTHOSH SHETTY",
    "24128": "ASHWITHA",
    "24129": "BHARGAVI P",
    "24130": "CHANDANA G KULAL",
    "24131": "CHIRAG S KOTIAN",
    "24132": "DARSHAN KUMAR",
    "24133": "DEEKSHA S POOJARY",
    "24134": "DEEPTHIS KULAL",
    "24135": "DHANUSH P SHRIYAN",
    "24136": "DHEERAJ KUMAR",
    "24137": "DIVYASHREE",
    "24138": "KPADMAVATHI SHASTRY",
    "24139": "KEERTHAN",
    "24140": "KEERTI TIMMANNA BHAT",
    "24141": "KRITHIKA",
    "24142": "MOOLYA SRUJAN SURESH",
    "24143": "NEELANJAN V",
    "24144": "NIKHITHA",
    "24145": "NISHITHA",
    "24146": "P PRAJWAL",
    "24147": "PANKAJ VILAS BHAVE",
    "24148": "POORNIMA SHETTIGAR",
    "24149": "PRAJNA P SHETTY",
    "24150": "PRAJWAL",
    "24151": "PRANITHA",
    "24152": "PRINCETON SHANOL LEWIS",
    "24153": "RACHANA",
    "24154": "RAHUL NAYAK",
    "24155": "RASHMIR SHETTY",
    "24156": "SAMEEKSHA",
    "24157": "SANJAN",
    "24158": "SHARANYA",
    "24159": "SHETTY VISHAL SHUBHAKAR",
    "24160": "SHRAVAN PAI",
    "24161": "SHRAVYA A ACHARYA",
    "24162": "SHRI SIDDI S SHETTY",
    "24163": "SOUMYA YALLAPPA BELLI",
    "24164": "SRUJAN",
    "24165": "SUDEEP S",
}

for i in range(24166, 24172):
    new_students[str(i)] = f"Student {i}"

def update_db():
    with app.app_context():
        # 1. Delete students without face samples
        students = Student.query.all()
        deleted_count = 0
        for s in students:
            if not s.has_face:
                # delete dependent records
                from models import Fee, Mark, MedicalCertificate, Attendance
                Fee.query.filter_by(student_id=s.id).delete()
                Mark.query.filter_by(student_id=s.id).delete()
                MedicalCertificate.query.filter_by(student_id=s.id).delete()
                Attendance.query.filter_by(student_id=s.id).delete()
                
                # delete corresponding user if exists
                u = User.query.filter_by(student_id=s.id).first()
                if u:
                    db.session.delete(u)
                db.session.delete(s)
                deleted_count += 1
        
        # also delete all parent accounts since we are removing most students
        # and we don't have a strict linking in db. We can just wipe parents and let seed_data or this script recreate if needed.
        # Actually, let's delete all parent users.
        parents = User.query.filter_by(role="parent").all()
        for p in parents:
            db.session.delete(p)

        db.session.commit()
        print(f"Deleted {deleted_count} students without face samples, and {len(parents)} parent accounts.")

        # 2. Insert new students
        added_count = 0
        student_creds = []
        for roll, name in new_students.items():
            # Check if exists
            s = Student.query.filter_by(roll_number=roll).first()
            if not s:
                s = Student(
                    roll_number=roll,
                    name=name,
                    department="MCA",
                    class_name="2nd Year MCA"
                )
                db.session.add(s)
                db.session.flush() # get ID

                # Create user
                username = f"student_{roll}"
                u = User(
                    username=username,
                    email=f"{roll}@example.com",
                    role="student",
                    department="MCA",
                    student_id=s.id
                )
                password = f"pass{roll}word"
                u.set_password(password)
                db.session.add(u)
                added_count += 1
                
                student_creds.append(
                    f"Username: {username}\nPassword: {password}\nRoll Number: {roll}\nRole: student\n"
                )

        db.session.commit()
        print(f"Added {added_count} new MCA students.")

        # 3. Update credentials.txt
        cred_path = "credentials.txt"
        if os.path.exists(cred_path):
            with open(cred_path, "r") as f:
                content = f.read()
            
            # Split before STUDENT ACCOUNTS
            parts = content.split("STUDENT ACCOUNTS\n----------------\n")
            if len(parts) == 2:
                new_content = parts[0] + "STUDENT ACCOUNTS\n----------------\n"
                # Keep existing students who have face samples? Yes, let's find them
                existing_students = Student.query.all()
                for es in existing_students:
                    if es.has_face:
                        u = User.query.filter_by(student_id=es.id).first()
                        if u:
                            new_content += f"Username: {u.username}\nPassword: (unchanged)\nRoll Number: {es.roll_number}\nRole: student\n\n"
                
                # Add new students
                new_content += "\n".join(student_creds)

                # Add a dummy parent accounts section to avoid breaking anything that expects it
                new_content += "\nPARENT ACCOUNTS\n---------------\n(Parent accounts have been reset)\n"

                with open(cred_path, "w") as f:
                    f.write(new_content)
                print("Updated credentials.txt")

if __name__ == "__main__":
    update_db()
