"""Face detection + emotion recognition, CPU-only.

Detector : YuNet  (OpenCV Zoo, 232 KB ONNX)  ~20 ms/frame
Classifier: FER+  (ONNX Model Zoo, 35 MB)    ~4 ms/face

FER+ expects a 64x64 grayscale face crop with raw 0-255 pixel values
(no mean/std normalisation) -- this matches the model zoo reference
preprocessing for emotion-ferplus-8.
"""

import os
import numpy as np
import cv2
import onnxruntime as ort

EMOTIONS = [
    "neutral", "happiness", "surprise", "sadness",
    "anger", "disgust", "fear", "contempt",
]

# Emotional valence, -1 (distressed) .. +1 (content). Used for the
# daily wellbeing score so a caregiver gets one number to glance at.
VALENCE = {
    "happiness": 1.0,
    "surprise": 0.2,
    "neutral": 0.0,
    "contempt": -0.4,
    "disgust": -0.7,
    "sadness": -0.8,
    "fear": -0.8,
    "anger": -0.9,
}

# Emotions that count as "distress" for the check-in alert.
NEGATIVE = {"sadness", "anger", "fear", "disgust", "contempt"}

# BGR colours for the on-screen box.
COLORS = {
    "happiness": (80, 200, 80),
    "surprise": (200, 180, 60),
    "neutral": (170, 170, 170),
    "contempt": (120, 120, 220),
    "disgust": (100, 140, 200),
    "sadness": (220, 150, 90),
    "fear": (200, 120, 200),
    "anger": (80, 80, 230),
}

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
DETECTOR_FILE = "face_detection_yunet_2023mar.onnx"
EMOTION_FILE = "emotion-ferplus-8.onnx"


def softmax(x):
    e = np.exp(x - np.max(x))
    return e / e.sum()


class Face:
    """One detected face and its (smoothed) emotion reading."""

    def __init__(self, box, det_score, probs):
        self.x, self.y, self.w, self.h = box
        self.det_score = det_score
        self.probs = probs
        idx = int(np.argmax(probs))
        self.emotion = EMOTIONS[idx]
        self.confidence = float(probs[idx])
        self.valence = float(np.dot(probs, [VALENCE[e] for e in EMOTIONS]))


class EmotionEngine:
    def __init__(self, models_dir=MODELS_DIR, det_threshold=0.7, smoothing=0.65):
        self.models_dir = models_dir
        det_path = os.path.join(models_dir, DETECTOR_FILE)
        emo_path = os.path.join(models_dir, EMOTION_FILE)
        for p in (det_path, emo_path):
            if not os.path.exists(p):
                raise FileNotFoundError(
                    f"Missing model: {p}\nRun:  python download_models.py"
                )

        self.detector = cv2.FaceDetectorYN.create(
            det_path, "", (320, 320), det_threshold, 0.3, 5000
        )

        # Pin to 2 threads: keeps a laptop CPU responsive while still fast.
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(
            emo_path, sess_options=opts, providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name

        self.smoothing = smoothing
        self._ema = None          # rolling probability vector
        self._input_size = None

    def _classify(self, bgr_crop):
        gray = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA)
        blob = small.astype(np.float32).reshape(1, 1, 64, 64)
        logits = self.session.run(None, {self.input_name: blob})[0][0]
        return softmax(logits)

    def process(self, frame):
        """Returns (faces, primary) -- primary is the largest face or None."""
        h, w = frame.shape[:2]
        if self._input_size != (w, h):
            self.detector.setInputSize((w, h))
            self._input_size = (w, h)

        _, dets = self.detector.detect(frame)
        if dets is None or len(dets) == 0:
            self._ema = None      # reset smoothing when the person leaves
            return [], None

        faces = []
        for d in dets:
            x, y, bw, bh = [int(v) for v in d[:4]]
            # FER2013-style framing: pad the tight box out a little.
            pad = int(0.12 * max(bw, bh))
            x0, y0 = max(0, x - pad), max(0, y - pad)
            x1, y1 = min(w, x + bw + pad), min(h, y + bh + pad)
            if x1 - x0 < 20 or y1 - y0 < 20:
                continue
            probs = self._classify(frame[y0:y1, x0:x1])
            faces.append(Face((x0, y0, x1 - x0, y1 - y0), float(d[-1]), probs))

        if not faces:
            return [], None

        # Track the largest face -- the person being monitored.
        primary = max(faces, key=lambda f: f.w * f.h)

        # Exponential moving average stops a single blurred frame from
        # flipping the reading. This is what actually gets logged.
        if self._ema is None:
            self._ema = primary.probs.copy()
        else:
            a = self.smoothing
            self._ema = a * self._ema + (1 - a) * primary.probs

        smoothed = Face((primary.x, primary.y, primary.w, primary.h),
                        primary.det_score, self._ema)
        return faces, smoothed

    @staticmethod
    def draw(frame, faces, primary=None):
        for f in faces:
            is_primary = (
                primary is not None and abs(f.x - primary.x) < 5 and abs(f.y - primary.y) < 5
            )
            label_face = primary if is_primary else f
            color = COLORS.get(label_face.emotion, (200, 200, 200))
            thick = 3 if is_primary else 1
            cv2.rectangle(frame, (f.x, f.y), (f.x + f.w, f.y + f.h), color, thick)
            if is_primary:
                text = f"{label_face.emotion}  {label_face.confidence * 100:.0f}%"
                (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                ty = max(th + 8, f.y - 8)
                cv2.rectangle(frame, (f.x, ty - th - 8),
                              (f.x + tw + 10, ty + 4), color, -1)
                cv2.putText(frame, text, (f.x + 5, ty - 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
        return frame
