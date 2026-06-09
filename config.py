"""Application configuration."""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Change this in production / set via environment variable.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-in-production")

    # SQLite database stored next to the project.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "attendance.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Where downloaded ONNX models live.
    MODELS_DIR = os.path.join(BASE_DIR, "models")
    YUNET_PATH = os.path.join(MODELS_DIR, "face_detection_yunet_2023mar.onnx")
    SFACE_PATH = os.path.join(MODELS_DIR, "face_recognition_sface_2021dec.onnx")

    # SFace cosine-similarity threshold. Higher = stricter. 0.363 is the
    # OpenCV-recommended default for the SFace model.
    FACE_MATCH_THRESHOLD = float(os.environ.get("FACE_MATCH_THRESHOLD", "0.363"))

    # Default admin account created on first run.
    DEFAULT_ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
