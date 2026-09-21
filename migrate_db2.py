import sqlite3
import os

def migrate():
    db_path = os.path.join(os.path.dirname(__file__), "attendance.db")
    print(f"Connecting to database at {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Add casual_leaves_balance to users
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN casual_leaves_balance INTEGER DEFAULT 15")
        print("Added casual_leaves_balance to users.")
    except sqlite3.OperationalError as e:
        print(f"Column casual_leaves_balance in users: {e}")

    # Add profile_image_path to users
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN profile_image_path VARCHAR(255)")
        print("Added profile_image_path to users.")
    except sqlite3.OperationalError as e:
        print(f"Column profile_image_path in users: {e}")

    # Add profile_image_path to students
    try:
        cursor.execute("ALTER TABLE students ADD COLUMN profile_image_path VARCHAR(255)")
        print("Added profile_image_path to students.")
    except sqlite3.OperationalError as e:
        print(f"Column profile_image_path in students: {e}")

    # Add reassign_to_id to leave_applications
    try:
        cursor.execute("ALTER TABLE leave_applications ADD COLUMN reassign_to_id INTEGER REFERENCES users(id)")
        print("Added reassign_to_id to leave_applications.")
    except sqlite3.OperationalError as e:
        print(f"Column reassign_to_id in leave_applications: {e}")

    conn.commit()
    conn.close()
    print("Migration completed.")

if __name__ == "__main__":
    migrate()
