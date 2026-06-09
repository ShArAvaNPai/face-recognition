"""Helpers to turn uploaded / base64 webcam images into OpenCV BGR arrays."""
import base64

import cv2
import numpy as np


def decode_data_url(data_url):
    """Decode a 'data:image/jpeg;base64,...' string into a BGR image, or None."""
    if not data_url:
        return None
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    try:
        raw = base64.b64decode(data_url)
    except Exception:
        return None
    return _decode_bytes(raw)


def decode_file_storage(file_storage):
    """Decode a Werkzeug FileStorage upload into a BGR image, or None."""
    if not file_storage:
        return None
    raw = file_storage.read()
    return _decode_bytes(raw)


def _decode_bytes(raw):
    if not raw:
        return None
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img
