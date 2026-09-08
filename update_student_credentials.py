import os
import re
from app import app
from extensions import db
from models import Student, User, ROLE_STUDENT

def clean_username(name, roll_number):
    # Convert name to lowercase, replace spaces with underscores, keep alphanumeric and underscores
    clean_name = name.lower().strip()
    clean_name = re.sub(r'[^a-z0-9\s_]', '', clean_name)
    clean_name = re.sub(r'\s+', '_', clean_name)
    if not clean_name:
        clean_name = f"student_{roll_number}"
    return clean_name

def update_credentials():
    with app.app_context():
        students = Student.query.order_by(Student.roll_number).all()
        used_usernames = set()
        
        # Keep non-student usernames reserved
        non_students = User.query.filter(User.role != ROLE_STUDENT).all()
        for u in non_students:
            used_usernames.add(u.username)
            
        student_records = []
        
        for s in students:
            base_username = clean_username(s.name, s.roll_number)
            username = base_username
            
            # Ensure unique username if collision
            counter = 1
            while username in used_usernames:
                username = f"{base_username}_{counter}"
                counter += 1
                
            used_usernames.add(username)
            
            # Find linked user or create
            u = User.query.filter_by(student_id=s.id).first()
            if not u:
                u = User.query.filter_by(username=s.roll_number).first()
            if not u:
                u = User(
                    username=username,
                    email=f"{s.roll_number}@example.com",
                    role=ROLE_STUDENT,
                    department=s.department,
                    student_id=s.id
                )
                db.session.add(u)
            else:
                u.username = username
                u.email = f"{s.roll_number}@example.com"
                u.department = s.department
                
            # Set password to roll number
            u.set_password(str(s.roll_number))
            
            student_records.append({
                "username": username,
                "password": str(s.roll_number),
                "roll": str(s.roll_number),
                "name": s.name,
                "class_name": s.class_name,
                "department": s.department
            })
            
        db.session.commit()
        print(f"Updated {len(student_records)} student accounts in database.")
        
        # Update credentials.txt
        cred_path = "credentials.txt"
        if os.path.exists(cred_path):
            with open(cred_path, "r") as f:
                content = f.read()
                
            parts = content.split("STUDENT ACCOUNTS\n----------------\n")
            header = parts[0] + "STUDENT ACCOUNTS\n----------------\n"
            
            lines = []
            for rec in student_records:
                lines.append(f"Name: {rec['name']}\nUsername: {rec['username']}\nPassword: {rec['password']}\nRoll Number: {rec['roll']}\nClass: {rec['class_name']}\nRole: student\n")
                
            new_content = header + "\n".join(lines)
            with open(cred_path, "w") as f:
                f.write(new_content)
            print("Updated credentials.txt successfully.")

if __name__ == "__main__":
    update_credentials()
