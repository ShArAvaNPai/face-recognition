"""Download the OpenCV Zoo ONNX models needed for face detection + recognition.

Run once:  python download_models.py

Note: opencv_zoo stores these models with Git LFS, so the actual binaries live
on media.githubusercontent.com, not raw.githubusercontent.com (which only
returns a tiny LFS pointer file).
"""
import os
import ssl
import sys
import urllib.request

from config import Config

# Minimum plausible size (bytes) — guards against saving LFS pointers / error pages.
MIN_SIZE = 50 * 1024  # 50 KB

MODELS = {
    Config.YUNET_PATH: [
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
        "face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "https://github.com/opencv/opencv_zoo/raw/main/models/"
        "face_detection_yunet/face_detection_yunet_2023mar.onnx",
    ],
    Config.SFACE_PATH: [
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
        "face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "https://github.com/opencv/opencv_zoo/raw/main/models/"
        "face_recognition_sface/face_recognition_sface_2021dec.onnx",
    ],
}


def _open(url):
    """Open a URL, falling back to an unverified SSL context if cert check fails."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        return urllib.request.urlopen(req, timeout=120)
    except urllib.error.URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" in str(e):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return urllib.request.urlopen(req, timeout=120, context=ctx)
        raise


def download(dest, urls):
    if os.path.exists(dest) and os.path.getsize(dest) >= MIN_SIZE:
        print(f"[skip] already present: {os.path.basename(dest)}")
        return True
    for url in urls:
        try:
            print(f"[get ] {os.path.basename(dest)}  <- {url}")
            with _open(url) as r:
                data = r.read()
            if len(data) < MIN_SIZE:
                print(f"[warn] too small ({len(data)} B) — likely an LFS pointer, trying next mirror")
                continue
            with open(dest, "wb") as f:
                f.write(data)
            print(f"[ok  ] saved {os.path.basename(dest)} ({len(data)//1024} KB)")
            return True
        except Exception as e:
            print(f"[warn] failed from this mirror: {e}")
    # remove any tiny leftover so the app doesn't try to use it
    if os.path.exists(dest) and os.path.getsize(dest) < MIN_SIZE:
        os.remove(dest)
    print(f"[ERR ] could not download {os.path.basename(dest)}")
    return False


def main():
    os.makedirs(Config.MODELS_DIR, exist_ok=True)
    ok = all(download(dest, urls) for dest, urls in MODELS.items())
    if not ok:
        print("\nSome models failed to download. If you are offline, download them "
              "manually from\n  https://github.com/opencv/opencv_zoo/tree/main/models\n"
              f"and place the .onnx files in:\n  {Config.MODELS_DIR}")
        sys.exit(1)
    print("\nAll models ready.")


if __name__ == "__main__":
    main()
