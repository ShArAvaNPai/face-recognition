from datetime import date
from app import create_app
from extensions import db
from models import AcademicCalendarEvent

def seed_calendar():
    events_data = [
        # --- Public Holidays 2026-2027 ---
        {"title": "New Year's Day", "category": "holiday", "start_date": date(2026, 1, 1), "end_date": date(2026, 1, 1), "description": "National Public Holiday", "department": "All"},
        {"title": "Republic Day", "category": "holiday", "start_date": date(2026, 1, 26), "end_date": date(2026, 1, 26), "description": "National Holiday celebrating the Constitution of India", "department": "All"},
        {"title": "Maha Shivaratri", "category": "holiday", "start_date": date(2026, 2, 16), "end_date": date(2026, 2, 16), "description": "Gazetted Public Holiday", "department": "All"},
        {"title": "Holi (Festival of Colours)", "category": "holiday", "start_date": date(2026, 3, 4), "end_date": date(2026, 3, 4), "description": "Public Holiday", "department": "All"},
        {"title": "Good Friday", "category": "holiday", "start_date": date(2026, 4, 3), "end_date": date(2026, 4, 3), "description": "Public Holiday", "department": "All"},
        {"title": "Dr. B.R. Ambedkar Jayanti", "category": "holiday", "start_date": date(2026, 4, 14), "end_date": date(2026, 4, 14), "description": "Public Holiday honoring Dr. B.R. Ambedkar", "department": "All"},
        {"title": "May Day / International Workers' Day", "category": "holiday", "start_date": date(2026, 5, 1), "end_date": date(2026, 5, 1), "description": "Public Holiday", "department": "All"},
        {"title": "Bakrid / Eid al-Adha", "category": "holiday", "start_date": date(2026, 5, 27), "end_date": date(2026, 5, 27), "description": "Public Holiday", "department": "All"},
        {"title": "Independence Day", "category": "holiday", "start_date": date(2026, 8, 15), "end_date": date(2026, 8, 15), "description": "79th National Independence Day Celebration", "department": "All"},
        {"title": "Ganesh Chaturthi", "category": "holiday", "start_date": date(2026, 9, 14), "end_date": date(2026, 9, 14), "description": "State & Public Holiday", "department": "All"},
        {"title": "Gandhi Jayanti", "category": "holiday", "start_date": date(2026, 10, 2), "end_date": date(2026, 10, 2), "description": "National Holiday honoring Mahatma Gandhi", "department": "All"},
        {"title": "Maha Navami & Ayudha Puja", "category": "holiday", "start_date": date(2026, 10, 19), "end_date": date(2026, 10, 19), "description": "Festival Holiday", "department": "All"},
        {"title": "Vijayadashami (Dussehra)", "category": "holiday", "start_date": date(2026, 10, 20), "end_date": date(2026, 10, 20), "description": "Public Holiday", "department": "All"},
        {"title": "Kannada Rajyotsava", "category": "holiday", "start_date": date(2026, 11, 1), "end_date": date(2026, 11, 1), "description": "State Festival & Public Holiday", "department": "All"},
        {"title": "Deepavali / Diwali Festival", "category": "holiday", "start_date": date(2026, 11, 8), "end_date": date(2026, 11, 10), "description": "Festival of Lights Holidays", "department": "All"},
        {"title": "Christmas Day", "category": "holiday", "start_date": date(2026, 12, 25), "end_date": date(2026, 12, 25), "description": "Public Holiday", "department": "All"},

        # --- Exam Schedules ---
        {"title": "MCA Mid-Semester Internal Exams", "category": "exam", "start_date": date(2026, 10, 12), "end_date": date(2026, 10, 17), "description": "First Continuous Internal Assessment (CIA-1) for MCA 1st & 2nd Year students.", "department": "MCA"},
        {"title": "MBA Mid-Semester Internal Exams", "category": "exam", "start_date": date(2026, 10, 14), "end_date": date(2026, 10, 19), "description": "Mid-term evaluation for MBA Semester 1 & 3 courses.", "department": "MBA"},
        {"title": "Practical Lab & Project Examinations", "category": "exam", "start_date": date(2026, 11, 23), "end_date": date(2026, 11, 28), "description": "External and Internal Practical Lab Examinations and project viva.", "department": "All"},
        {"title": "Odd Semester University Final Exams", "category": "exam", "start_date": date(2026, 12, 7), "end_date": date(2026, 12, 22), "description": "Semester-end University Theory Examinations for all courses.", "department": "All"},
        {"title": "MCA Dissertation & Project Viva-Voce", "category": "exam", "start_date": date(2027, 1, 15), "end_date": date(2027, 1, 18), "description": "Final major project presentations and external viva examinations.", "department": "MCA"},
        {"title": "Even Semester Internal Assessment (IA-1)", "category": "exam", "start_date": date(2027, 3, 22), "end_date": date(2027, 3, 27), "description": "Internal Assessment Test 1 for Even Semester courses.", "department": "All"},
        {"title": "Even Semester Final Theory Examinations", "category": "exam", "start_date": date(2027, 5, 17), "end_date": date(2027, 6, 2), "description": "Annual Semester Final Examinations.", "department": "All"},

        # --- Academic Milestones & College Events ---
        {"title": "Odd Semester Academic Commencement", "category": "academic", "start_date": date(2026, 8, 3), "end_date": date(2026, 8, 3), "description": "Orientation and start of academic sessions for MCA & MBA batches.", "department": "All"},
        {"title": "Innovision 2026 - National Tech Symposium", "category": "academic", "start_date": date(2026, 9, 25), "end_date": date(2026, 9, 26), "description": "Inter-collegiate technical competitions, hackathons, and guest lectures.", "department": "MCA"},
        {"title": "Annual Inter-Department Sports Meet", "category": "academic", "start_date": date(2026, 11, 5), "end_date": date(2026, 11, 6), "description": "Track, field, indoor and outdoor athletic events.", "department": "All"},
        {"title": "Winter Vacation & Semester Break", "category": "academic", "start_date": date(2026, 12, 23), "end_date": date(2027, 1, 3), "description": "Semester break between Odd and Even semesters.", "department": "All"},
        {"title": "Even Semester Commencement", "category": "academic", "start_date": date(2027, 1, 4), "end_date": date(2027, 1, 4), "description": "Start of Even Semester classes and curriculum delivery.", "department": "All"},
        {"title": "Utsav 2027 - Annual Cultural Fest", "category": "academic", "start_date": date(2027, 4, 16), "end_date": date(2027, 4, 17), "description": "Annual college cultural fest, exhibitions, and musical performances.", "department": "All"},
    ]

    for item in events_data:
        exists = AcademicCalendarEvent.query.filter_by(title=item["title"], start_date=item["start_date"]).first()
        if not exists:
            evt = AcademicCalendarEvent(
                title=item["title"],
                category=item["category"],
                start_date=item["start_date"],
                end_date=item["end_date"],
                description=item["description"],
                department=item["department"]
            )
            db.session.add(evt)
    db.session.commit()
    print("Academic calendar events seeded successfully!")

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
        seed_calendar()
