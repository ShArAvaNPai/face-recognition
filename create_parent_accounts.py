import os
from app import app
from extensions import db
from models import Student, User, ROLE_PARENT, ROLE_STUDENT

def create_parents():
    with app.app_context():
        students = Student.query.order_by(Student.roll_number).all()
        parent_records = []
        created_count = 0
        
        for s in students:
            std_user = User.query.filter_by(student_id=s.id, role=ROLE_STUDENT).first()
            username_base = std_user.username if std_user else s.roll_number
            parent_username = f"parent_{username_base}"
            parent_password = f"parent_{s.roll_number}"
            
            p_user = User.query.filter_by(student_id=s.id, role=ROLE_PARENT).first()
            if not p_user:
                p_user = User.query.filter_by(username=parent_username).first()
                
            if not p_user:
                p_user = User(
                    username=parent_username,
                    email=f"parent_{s.roll_number}@example.com",
                    role=ROLE_PARENT,
                    department=s.department,
                    student_id=s.id
                )
                db.session.add(p_user)
                created_count += 1
            else:
                p_user.username = parent_username
                p_user.email = f"parent_{s.roll_number}@example.com"
                p_user.department = s.department
                p_user.student_id = s.id
                
            p_user.set_password(parent_password)
            
            parent_records.append({
                "username": parent_username,
                "password": parent_password,
                "student_name": s.name,
                "student_roll": s.roll_number,
                "department": s.department
            })
            
        db.session.commit()
        print(f"Created/Updated {len(parent_records)} parent accounts in database ({created_count} new).")
        
        # Update credentials.txt
        cred_path = "credentials.txt"
        if os.path.exists(cred_path):
            with open(cred_path, "r") as f:
                content = f.read()
                
            # If PARENT ACCOUNTS section exists, split and replace
            if "PARENT ACCOUNTS\n---------------" in content:
                parts = content.split("PARENT ACCOUNTS\n---------------")
                header = parts[0] + "PARENT ACCOUNTS\n---------------\n"
            else:
                header = content + "\n\nPARENT ACCOUNTS\n---------------\n"
                
            lines = []
            for prec in parent_records:
                lines.append(
                    f"Username: {prec['username']}\n"
                    f"Password: {prec['password']}\n"
                    f"Student Linked: {prec['student_name']} (Roll: {prec['student_roll']})\n"
                    f"Department: {prec['department']}\n"
                    f"Role: parent\n"
                )
                
            new_content = header + "\n".join(lines)
            with open(cred_path, "w") as f:
                f.write(new_content)
            print("Updated credentials.txt with PARENT ACCOUNTS section successfully.")

if __name__ == "__main__":
    create_parents()
