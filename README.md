# Smart Attendance System using Face Recognition

A Flask web application that marks student attendance automatically using face
recognition. Built to run on **Python 3.14** with **no TensorFlow and no dlib** —
face detection and recognition use OpenCV's built-in **YuNet** + **SFace** models.

## Why OpenCV SFace instead of DeepFace?
DeepFace requires TensorFlow, and TensorFlow currently ships **no wheels for
Python 3.14** (the same reason `dlib` / `face_recognition` would not install).
OpenCV's `FaceDetectorYN` (YuNet) and `FaceRecognizerSF` (SFace) give accurate,
production-grade recognition using only `opencv-python` — which is already
installed. If you later downgrade to Python 3.11/3.12, you can swap in DeepFace
by changing only `face_engine.py`.

## Modules implemented (core)
1. **User Authentication** — registration, login/logout, role-based access
   (admin / faculty / student), hashed passwords, secure Flask sessions, password change.
2. **Student Management** — register, edit, search, delete; department, class, roll number.
3. **Face Registration** — webcam capture **and** image upload; multiple samples
   per student; each sample stored as an SFace 128-d feature vector.
4. **Face Recognition** — real-time multi-face detection & matching from the
   browser webcam, with **duplicate prevention** (one record per student/session).
5. **Attendance Management** — subjects, dated sessions, automatic + manual
   marking, attendance correction, per-session history.
6. **Report Generation** — per-student attendance %, subject filter, per-student
   history, **CSV export**. Plus a role-aware **Dashboard**.

> Modules 7–11 (classroom monitoring, notifications/SMS-email, advanced
> analytics, full admin device management) were intentionally deferred — you
> chose "core attendance only first."

## Setup (Windows PowerShell)
```powershell
# 1. install dependencies into the existing venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. download the face models (once, ~38 MB)
.\.venv\Scripts\python.exe download_models.py

# 3. run the app
.\.venv\Scripts\python.exe app.py
```
Then open http://127.0.0.1:5000

**Default admin login:** `admin` / `admin123`
(change it from the *Password* page, or via `ADMIN_USERNAME` / `ADMIN_PASSWORD` env vars).

## Typical flow
1. Log in as admin (or register a faculty account).
2. **Students → Add student** (roll number, name, department, class).
3. **Faces → Register faces** for each student — click *Start camera* and capture
   2–4 samples from slightly different angles (or upload photos).
4. **Subjects** → add a subject (e.g. `CS101`).
5. **Attendance → Start new session** → pick subject/class/date.
6. On the *Take attendance* page, *Start camera* then *Scan once* / *Start
   auto-scan* — recognized students are marked present live. Correct manually if needed.
7. **Reports** → view attendance %, filter by subject, export CSV.

## Notes
- The browser asks for camera permission. On `http://127.0.0.1` this works in
  Chrome/Edge; other hostnames may require HTTPS for `getUserMedia`.
- Recognition strictness is the SFace cosine threshold (`FACE_MATCH_THRESHOLD`,
  default `0.363`). Raise it to reduce false matches, lower it if real students
  are missed.
- The SQLite database (`attendance.db`) is created automatically on first run.

## Project layout
```
app.py              Flask app factory, blueprint registration, admin seeding
config.py           Configuration (DB path, model paths, threshold, admin seed)
extensions.py       SQLAlchemy + Flask-Login instances
models.py           User, Student, FaceSample, Subject, AttendanceSession, Attendance
face_engine.py      YuNet detection + SFace recognition (OpenCV only)
download_models.py  Fetches the ONNX models from OpenCV Zoo (Git LFS aware)
blueprints/         auth, students, faces, attendance, reports, dashboard
templates/          Jinja2 templates per module
static/style.css    Styling
models/             Downloaded .onnx model files
legacy/             Your original standalone webcam demo scripts (superseded)
```
