"""Smart Attendance System using Face Recognition — Flask application.

Core modules implemented:
  1. User Authentication (register/login/logout, roles, sessions, passwords)
  2. Student Management (profiles, dept/class, roll numbers)
  3. Face Registration (webcam capture / upload -> SFace encoding)
  4. Face Recognition (real-time, multi-face, duplicate prevention)
  5. Attendance Management (auto marking, subjects, sessions, correction, history)
  6. Report Generation (percentages, per-student history, CSV export)
     + role-aware Dashboard.

Run:
    python download_models.py     # once, to fetch the face models
    python app.py
"""
from flask import Flask, render_template, send_from_directory
from flask_login import current_user

from config import Config
from extensions import db, login_manager, mail
from models import User, ROLE_ADMIN


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from blueprints.auth import auth_bp
    from blueprints.dashboard import dashboard_bp
    from blueprints.students import students_bp
    from blueprints.faces import faces_bp
    from blueprints.attendance import attendance_bp
    from blueprints.reports import reports_bp
    from blueprints.admin import admin_bp
    from blueprints.director import director_bp
    from blueprints.faculty import faculty_bp
    from blueprints.parents import parents_bp
    from blueprints.academic_calendar import calendar_bp
    from blueprints.marks import marks_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(faces_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(director_bp)
    app.register_blueprint(faculty_bp)
    app.register_blueprint(parents_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(marks_bp)

    @app.route('/sw.js')
    def service_worker():
        return send_from_directory('static', 'sw.js', mimetype='application/javascript')

    @app.route('/manifest.json')
    def manifest():
        return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

    @app.context_processor
    def inject_global_data():
        if current_user.is_authenticated:
            from models import Notification
            notifs = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(Notification.created_at.desc()).all()
            return {"user_notifications": notifs, "unread_notifications_count": len(notifs)}
        return {"user_notifications": [], "unread_notifications_count": 0}

    # Error pages
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403,
                               message="You don't have permission to view this page."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404,
                               message="Page not found."), 404

    with app.app_context():
        db.create_all()
        from sqlalchemy import inspect, text
        try:
            inspector = inspect(db.engine)
            
            # Migrate users table
            user_cols = [c['name'] for c in inspector.get_columns('users')]
            if 'department' not in user_cols:
                db.session.execute(text("ALTER TABLE users ADD COLUMN department VARCHAR(80) DEFAULT ''"))
                db.session.commit()
                
            # Migrate timetable_slots table
            if inspector.has_table('timetable_slots'):
                tt_cols = [c['name'] for c in inspector.get_columns('timetable_slots')]
                if 'department' not in tt_cols:
                    db.session.execute(text("ALTER TABLE timetable_slots ADD COLUMN department VARCHAR(80) DEFAULT ''"))
                    db.session.commit()
                    
            # Migrate subjects table
            if inspector.has_table('subjects'):
                subj_cols = [c['name'] for c in inspector.get_columns('subjects')]
                if 'department' not in subj_cols:
                    db.session.execute(text("ALTER TABLE subjects ADD COLUMN department VARCHAR(80) DEFAULT 'MCA'"))
                    db.session.commit()

            # Ensure subjects department values are populated based on code/faculty
            from models import Subject, User
            all_subjs = Subject.query.all()
            for s in all_subjs:
                if not s.department or s.department == 'MCA':
                    if s.code.upper().startswith('MBA') or (s.faculty and s.faculty.department == 'MBA'):
                        s.department = 'MBA'
                    elif s.code.upper().startswith('MCA') or (s.faculty and s.faculty.department == 'MCA'):
                        s.department = 'MCA'
            db.session.commit()

            # Migrate medical_certificates table
            if inspector.has_table('medical_certificates'):
                med_cols = [c['name'] for c in inspector.get_columns('medical_certificates')]
                if 'start_date' not in med_cols:
                    db.session.execute(text("ALTER TABLE medical_certificates ADD COLUMN start_date DATE"))
                    db.session.commit()
                if 'end_date' not in med_cols:

                    db.session.execute(text("ALTER TABLE medical_certificates ADD COLUMN end_date DATE"))
                    db.session.commit()

            # Migrate timetable_claims table
            if inspector.has_table('timetable_claims'):
                claim_cols = [c['name'] for c in inspector.get_columns('timetable_claims')]
                if 'status' not in claim_cols:
                    db.session.execute(text("ALTER TABLE timetable_claims ADD COLUMN status VARCHAR(20) DEFAULT 'approved'"))
                    db.session.commit()
                if 'reported_to_id' not in claim_cols:
                    db.session.execute(text("ALTER TABLE timetable_claims ADD COLUMN reported_to_id INTEGER"))
                    db.session.commit()
                if 'created_at' not in claim_cols:
                    db.session.execute(text("ALTER TABLE timetable_claims ADD COLUMN created_at DATETIME"))
                    db.session.commit()

        except Exception as ex:
            print(f"[migration] Note on schema check: {ex}")
        _seed_admin(app)

    return app


def _seed_admin(app):
    """Create a default admin account on first run."""
    username = app.config["DEFAULT_ADMIN_USERNAME"]
    if not User.query.filter_by(username=username).first():
        admin = User(username=username,
                     email=f"{username}@example.com",
                     role=ROLE_ADMIN)
        admin.set_password(app.config["DEFAULT_ADMIN_PASSWORD"])
        db.session.add(admin)
        db.session.commit()
        print(f"[seed] Created default admin '{username}' "
              f"(password: {app.config['DEFAULT_ADMIN_PASSWORD']}).")


app = create_app()


if __name__ == "__main__":
    # threaded=True so face recognition requests don't block the UI.
    # host="0.0.0.0" allows devices on the same Wi-Fi network (phones/tablets) to connect.
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
