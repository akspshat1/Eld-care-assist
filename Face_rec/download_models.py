"""Fetch the two pretrained models (run once, ~35 MB total).

  YuNet  - face detection, OpenCV Zoo        (232 KB)
  FER+   - emotion classification, ONNX Zoo   (35 MB)

Both are permissively licensed pretrained models; nothing is trained here.
"""

import os
import sys
import urllib.request

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")

MODELS = {
    "face_detection_yunet_2023mar.onnx":
        "https://github.com/opencv/opencv_zoo/raw/main/models/"
        "face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "emotion-ferplus-8.onnx":
        "https://github.com/onnx/models/raw/main/validated/vision/"
        "body_analysis/emotion_ferplus/model/emotion-ferplus-8.onnx",
}


def _progress(count, block_size, total):
    if total <= 0:
        return
    pct = min(100, count * block_size * 100 // total)
    sys.stdout.write(f"\r    {pct:3d}%")
    sys.stdout.flush()


def main():
    os.makedirs(MODELS_DIR, exist_ok=True)
    for name, url in MODELS.items():
        dest = os.path.join(MODELS_DIR, name)
        if os.path.exists(dest) and os.path.getsize(dest) > 100_000:
            print(f"[skip] {name} already present")
            continue
        print(f"[get ] {name}")
        urllib.request.urlretrieve(url, dest, _progress)
        print(f"\r    done ({os.path.getsize(dest) / 1e6:.1f} MB)")
    print("\nModels ready. Start the app with:  python app.py")


if __name__ == "__main__":
    main()
