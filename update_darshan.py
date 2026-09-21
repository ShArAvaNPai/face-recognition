import sqlite3
import os
from werkzeug.security import generate_password_hash

def update_darshan_phone():
    db_path = os.path.join(os.path.dirname(__file__), "attendance.db")
    print(f"Connecting to database at {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Find Darshan
    cursor.execute("SELECT id, name, roll_number FROM students WHERE name LIKE '%Darshan%'")
    results = cursor.fetchall()

    if not results:
        print("No student named Darshan found.")
        return
    
    for row in results:
        student_id, name, roll_number = row
        print(f"Found student: {name} (Roll: {roll_number}, ID: {student_id})")
        
        # Check if parent user exists
        cursor.execute("SELECT id FROM users WHERE role='parent' AND student_id=?", (student_id,))
        parent_user = cursor.fetchone()

        new_phone = "+91 74837 98467"
        
        if parent_user:
            parent_id = parent_user[0]
            cursor.execute("UPDATE users SET phone=? WHERE id=?", (new_phone, parent_id))
            print(f"Updated existing parent account (ID: {parent_id}) with phone {new_phone}")
        else:
            username = f"parent_{roll_number.lower()}"
            email = f"{username}@example.com"
            pw_hash = generate_password_hash("password")
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, role, phone, student_id)
                VALUES (?, ?, ?, 'parent', ?, ?)
            """, (username, email, pw_hash, new_phone, student_id))
            print(f"Created new parent account for {name} with phone {new_phone}")
    
    conn.commit()
    conn.close()
    print("Database updated.")

if __name__ == "__main__":
    update_darshan_phone()
