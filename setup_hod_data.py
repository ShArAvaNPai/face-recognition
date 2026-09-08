from app import app
from extensions import db
from models import User, Student, Subject, FaceSample, ROLE_HOD, ROLE_FACULTY, ROLE_DIRECTOR

def setup():
    with app.app_context():
        print("Initial face samples count:", FaceSample.query.count())
        
        # 1. Create or update MCA HOD
        mca_hod = User.query.filter_by(username="mca_hod").first()
        if not mca_hod:
            mca_hod = User(username="mca_hod", email="mca_hod@example.com", role=ROLE_HOD, department="MCA")
            mca_hod.set_password("mca12345")
            db.session.add(mca_hod)
            print("Created MCA HOD: mca_hod")
        else:
            mca_hod.role = ROLE_HOD
            mca_hod.department = "MCA"
            print("Updated MCA HOD: mca_hod")

        # 2. Create or update MBA HOD
        mba_hod = User.query.filter_by(username="mba_hod").first()
        if not mba_hod:
            mba_hod = User(username="mba_hod", email="mba_hod@example.com", role=ROLE_HOD, department="MBA")
            mba_hod.set_password("mba12345")
            db.session.add(mba_hod)
            print("Created MBA HOD: mba_hod")
        else:
            mba_hod.role = ROLE_HOD
            mba_hod.department = "MBA"
            print("Updated MBA HOD: mba_hod")

        # 3. Update existing MCA faculty users
        for uname in ["prof_smith", "prof_jones", "prof_davis"]:
            u = User.query.filter_by(username=uname).first()
            if u:
                u.department = "MCA"

        # 4. Create/update MBA faculty users if needed
        mba_facs = [
            ("prof_mehta", "mehta@example.com", "mehta123", "mgt201", "Management Principles"),
            ("prof_iyer",  "iyer@example.com",  "iyer123",  "mkt201", "Marketing Strategy"),
            ("prof_bose",  "bose@example.com",  "bose123",  "fin201", "Financial Management"),
        ]
        for uname, email, pwd, code, name in mba_facs:
            u = User.query.filter_by(username=uname).first()
            if not u:
                u = User(username=uname, email=email, role=ROLE_FACULTY, department="MBA")
                u.set_password(pwd)
                db.session.add(u)
                db.session.flush()
                print(f"Created MBA faculty: {uname}")
            else:
                u.department = "MBA"
            
            subj = Subject.query.filter_by(code=code).first()
            if not subj:
                subj = Subject(code=code, name=name, faculty_id=u.id)
                db.session.add(subj)

        # 5. Ensure students have a department (divide evenly between MCA and MBA if blank)
        students = Student.query.all()
        for idx, st in enumerate(students):
            if not st.department:
                st.department = "MCA" if idx % 2 == 0 else "MBA"

        db.session.commit()
        print("Final face samples count:", FaceSample.query.count())
        print("HOD setup completed safely without removing any face samples or data!")

if __name__ == "__main__":
    setup()
