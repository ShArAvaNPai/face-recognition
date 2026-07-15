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
from flask import Flask, render_template

from config import Config
from extensions import db, login_manager
from models import User, ROLE_ADMIN


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

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

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(faces_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(director_bp)
    app.register_blueprint(faculty_bp)

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
    app.run(host="127.0.0.1", port=5000, debug=True, threaded=True)
