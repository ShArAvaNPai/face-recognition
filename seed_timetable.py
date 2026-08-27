import sys
from datetime import date
from app import app
from extensions import db
from models import User, Subject, TimetableSlot, ROLE_DIRECTOR, ROLE_FACULTY, ROLE_ADMIN

def seed():
    print("Seeding timetable data...")
    # Find or create Director
    director = User.query.filter_by(role=ROLE_DIRECTOR).first()
    if not director:
        director = User(username="Director", email="director@example.com", role=ROLE_DIRECTOR)
        director.set_password("director123")
        db.session.add(director)
        db.session.flush()
        print(f"Created director user: {director.username}")
    
    # Ensure director has 'Research' subject
    research_subj = Subject.query.filter_by(code="research").first()
    if not research_subj:
        research_subj = Subject(code="research", name="Research", faculty_id=director.id)
        db.session.add(research_subj)
        db.session.flush()
        print("Created Research subject for director.")
    else:
        research_subj.faculty_id = director.id
        print("Updated Research subject to be taught by director.")

    # Find faculty users
    faculty = User.query.filter_by(role=ROLE_FACULTY).all()
    if not faculty:
        # Create a faculty user if none exists
        f_user = User(username="lect", email="lect@example.com", role=ROLE_FACULTY)
        f_user.set_password("lecturer123")
        db.session.add(f_user)
        db.session.flush()
        faculty = [f_user]
        print(f"Created faculty user: {f_user.username}")

    # Ensure some faculty subjects
    subjects = Subject.query.all()
    if len(subjects) <= 1: # only Research or none
        s1 = Subject(code="pds", name="Programming & Data Structures", faculty_id=faculty[0].id)
        db.session.add(s1)
        print("Created Programming & Data Structures subject.")

    db.session.commit()

    # Re-fetch subjects
    subjects = Subject.query.all()
    subj_map = {s.code: s for s in subjects}

    # Standard slot hours
    hours = [
        "09:00 - 10:00",
        "10:00 - 11:00",
        "11:00 - 12:00",
        "13:00 - 14:00",
        "14:00 - 15:00",
        "15:00 - 16:00"
    ]
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    # Clear old slots
    TimetableSlot.query.delete()
    db.session.commit()

    # Create default schedule
    schedule = {
        "Monday": {
            "09:00 - 10:00": "pds",
            "10:00 - 11:00": "research",
            "11:00 - 12:00": "12" if "12" in subj_map else None,
        },
        "Tuesday": {
            "09:00 - 10:00": "research",
            "10:00 - 11:00": "pds",
        },
        "Wednesday": {
            "09:00 - 10:00": "pds",
            "11:00 - 12:00": "research",
        },
        "Thursday": {
            "10:00 - 11:00": "pds",
            "14:00 - 15:00": "research",
        },
        "Friday": {
            "09:00 - 10:00": "research",
            "13:00 - 14:00": "pds",
        }
    }

    for day in days:
        for hr in hours:
            code = schedule.get(day, {}).get(hr, None)
            subj = subj_map.get(code) if code else None
            slot = TimetableSlot(day_of_week=day, slot_time=hr, subject_id=subj.id if subj else None)
            db.session.add(slot)
    
    db.session.commit()
    print("Timetable successfully seeded.")

if __name__ == "__main__":
    with app.app_context():
        seed()
