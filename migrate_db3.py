import sqlite3
import os

def migrate():
    db_path = os.path.join(os.path.dirname(__file__), "attendance.db")
    print(f"Connecting to database at {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Add image_path to face_samples
    try:
        cursor.execute("ALTER TABLE face_samples ADD COLUMN image_path VARCHAR(255)")
        print("Added image_path to face_samples.")
    except sqlite3.OperationalError as e:
        print(f"Column image_path in face_samples: {e}")

    conn.commit()
    conn.close()
    print("Migration completed.")

if __name__ == "__main__":
    migrate()
