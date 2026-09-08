import sys
from datetime import date
from app import app
from extensions import db
from models import User, Subject, TimetableSlot, ROLE_DIRECTOR, ROLE_HOD, ROLE_FACULTY

def seed():
    print("Seeding timetable data for MCA and MBA...")
    
    # Standard slot hours & days
    hours = [
        "09:00 - 10:00",
        "10:00 - 11:00",
        "11:00 - 12:00",
        "13:00 - 14:00",
        "14:00 - 15:00",
        "15:00 - 16:00"
    ]
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    # Map subjects by code
    subjects = Subject.query.all()
    subj_map = {s.code: s for s in subjects}

    # Clear existing slots
    TimetableSlot.query.delete()
    db.session.commit()

    # MCA schedule
    mca_schedule = {
        "Monday": {"09:00 - 10:00": "MCA101", "11:00 - 12:00": "MCA102", "14:00 - 15:00": "MCA103"},
        "Tuesday": {"10:00 - 11:00": "MCA101", "13:00 - 14:00": "MCA104"},
        "Wednesday": {"09:00 - 10:00": "MCA102", "11:00 - 12:00": "MCA103"},
        "Thursday": {"10:00 - 11:00": "MCA103", "14:00 - 15:00": "MCA104"},
        "Friday": {"09:00 - 10:00": "MCA101", "13:00 - 14:00": "MCA102"}
    }

    # MBA schedule
    mba_schedule = {
        "Monday": {"09:00 - 10:00": "MBA101", "11:00 - 12:00": "MBA102"},
        "Tuesday": {"10:00 - 11:00": "MBA101", "14:00 - 15:00": "MBA102"},
        "Wednesday": {"09:00 - 10:00": "MBA102", "13:00 - 14:00": "MBA101"},
        "Thursday": {"11:00 - 12:00": "MBA101", "14:00 - 15:00": "MBA102"},
        "Friday": {"10:00 - 11:00": "MBA102", "13:00 - 14:00": "MBA101"}
    }

    # Populate MCA slots
    for day in days:
        for hr in hours:
            code = mca_schedule.get(day, {}).get(hr)
            subj = subj_map.get(code) if code else None
            slot = TimetableSlot(department="MCA", day_of_week=day, slot_time=hr, subject_id=subj.id if subj else None)
            db.session.add(slot)

    # Populate MBA slots
    for day in days:
        for hr in hours:
            code = mba_schedule.get(day, {}).get(hr)
            subj = subj_map.get(code) if code else None
            slot = TimetableSlot(department="MBA", day_of_week=day, slot_time=hr, subject_id=subj.id if subj else None)
            db.session.add(slot)

    db.session.commit()
    print("MCA and MBA Timetables successfully seeded!")

if __name__ == "__main__":
    with app.app_context():
        seed()
