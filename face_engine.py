"""Face detection (YuNet) + recognition (SFace) using OpenCV only.

No TensorFlow / dlib required. Works on Python 3.14 with opencv-python.

Model files are expected under the models/ directory; run download_models.py
once to fetch them.
"""
import os
import threading

import cv2
import numpy as np

from config import Config


class FaceEngine:
    """Thread-safe wrapper around OpenCV's YuNet detector and SFace recognizer."""

    def __init__(self, yunet_path=None, sface_path=None, threshold=None):
        self.yunet_path = yunet_path or Config.YUNET_PATH
        self.sface_path = sface_path or Config.SFACE_PATH
        self.threshold = threshold if threshold is not None else Config.FACE_MATCH_THRESHOLD
        self._lock = threading.Lock()
        self._detector = None
        self._recognizer = None

    # -- lazy model loading -------------------------------------------------
    @property
    def available(self):
        return os.path.exists(self.yunet_path) and os.path.exists(self.sface_path)

    def _ensure_loaded(self):
        if self._detector is not None and self._recognizer is not None:
            return
        if not self.available:
            raise FileNotFoundError(
                "Face model files not found. Run:  python download_models.py"
            )
        # input size is updated per-frame via setInputSize before detect().
        self._detector = cv2.FaceDetectorYN.create(
            self.yunet_path, "", (320, 320), 0.9, 0.3, 5000
        )
        self._recognizer = cv2.FaceRecognizerSF.create(self.sface_path, "")

    # -- core operations ----------------------------------------------------
    def detect(self, image_bgr):
        """Return the raw YuNet face rows (Nx15) for an image."""
        self._ensure_loaded()
        h, w = image_bgr.shape[:2]
        self._detector.setInputSize((w, h))
        _, faces = self._detector.detect(image_bgr)
        if faces is None:
            return np.empty((0, 15), dtype=np.float32)
        return faces

    def feature_for_face(self, image_bgr, face_row):
        """Align+crop one detected face and return its 128-d float32 feature."""
        self._ensure_loaded()
        aligned = self._recognizer.alignCrop(image_bgr, face_row)
        feat = self._recognizer.feature(aligned)
        return np.array(feat, dtype=np.float32).flatten()

    def extract_features(self, image_bgr):
        """Detect all faces in an image and return list of (bbox, feature).

        bbox is (x, y, w, h) ints; feature is a 128-d float32 vector.
        """
        with self._lock:
            faces = self.detect(image_bgr)
            results = []
            for row in faces:
                x, y, fw, fh = row[0:4].astype(int)
                feat = self.feature_for_face(image_bgr, row)
                results.append(((int(x), int(y), int(fw), int(fh)), feat))
            return results

    def best_single_feature(self, image_bgr):
        """For face registration: return the feature of the largest face, or None."""
        with self._lock:
            faces = self.detect(image_bgr)
            if len(faces) == 0:
                return None
            # pick the largest face by area (w * h)
            areas = faces[:, 2] * faces[:, 3]
            idx = int(np.argmax(areas))
            return self.feature_for_face(image_bgr, faces[idx])

    def cosine_similarity(self, feat_a, feat_b):
        """Cosine similarity between two stored feature vectors.

        Uses the same normalization OpenCV's match() uses, but works on plain
        numpy arrays (so we can compare against features loaded from the DB).
        """
        a = np.asarray(feat_a, dtype=np.float32).flatten()
        b = np.asarray(feat_b, dtype=np.float32).flatten()
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    def match(self, probe_feature, candidates):
        """Match a probe feature against candidate (id, feature) pairs.

        Returns (best_id, best_score) if best_score >= threshold, else (None, best_score).
        candidates: iterable of (key, feature_vector).
        """
        best_id, best_score = None, -1.0
        for key, feat in candidates:
            score = self.cosine_similarity(probe_feature, feat)
            if score > best_score:
                best_score, best_id = score, key
        if best_score >= self.threshold:
            return best_id, best_score
        return None, best_score


# Helpers for storing/loading features in the database -----------------------
def feature_to_bytes(feature):
    return np.asarray(feature, dtype=np.float32).tobytes()


def feature_from_bytes(buf):
    return np.frombuffer(buf, dtype=np.float32)


# Singleton used across the app.
engine = FaceEngine()
