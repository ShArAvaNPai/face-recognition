from app import app
from extensions import db
from models import Subject, TimetableSlot, User

with app.app_context():
    # Fix lect subject code to 'pds'
    lect = User.query.filter_by(username='lect').first()
    if lect:
        s = Subject.query.filter_by(faculty_id=lect.id).first()
        if s and s.code != 'pds':
            s.code = 'pds'
            s.name = 'Programming & DS'
            db.session.commit()
            print('Fixed subject code to pds for lect')

    # Rebuild timetable with correct subject references
    subjects = {s.code: s for s in Subject.query.all()}
    print('Available codes:', list(subjects.keys()))
    
    # Clear and rebuild
    TimetableSlot.query.delete()
    db.session.commit()
    
    schedule = {
        'Monday':    {'09:00 - 10:00': 'pds', '10:00 - 11:00': 'research'},
        'Tuesday':   {'09:00 - 10:00': 'research', '10:00 - 11:00': 'pds'},
        'Wednesday': {'09:00 - 10:00': 'pds', '11:00 - 12:00': 'research'},
        'Thursday':  {'10:00 - 11:00': 'pds', '14:00 - 15:00': 'research'},
        'Friday':    {'09:00 - 10:00': 'research', '13:00 - 14:00': 'pds'},
    }
    hours = ['09:00 - 10:00','10:00 - 11:00','11:00 - 12:00','13:00 - 14:00','14:00 - 15:00','15:00 - 16:00']
    days = ['Monday','Tuesday','Wednesday','Thursday','Friday']
    
    for day in days:
        for hr in hours:
            code = schedule.get(day, {}).get(hr)
            subj = subjects.get(code) if code else None
            slot = TimetableSlot(day_of_week=day, slot_time=hr, subject_id=subj.id if subj else None)
            db.session.add(slot)
    db.session.commit()
    print('Timetable reseeded successfully.')
    
    # Verify
    for s in TimetableSlot.query.filter(TimetableSlot.subject_id != None).all():
        fac = s.subject.faculty.username if s.subject.faculty else 'None'
        print(f'  {s.day_of_week} {s.slot_time}: {s.subject.name} ({fac})')
