"""Elderly Mood Monitor -- browser UI.

Python owns the webcam and runs inference; the browser is just the front end.
The video reaches the page as an MJPEG stream, everything else as JSON.

    python run.py          # starts this and opens your browser
    python web_app.py      # start the server on its own
"""

import io
import csv
import time
import threading
from datetime import datetime

import cv2
from fastapi import FastAPI, Request
from fastapi.responses import (HTMLResponse, StreamingResponse, JSONResponse,
                               Response)
import os

from emotion_engine import EmotionEngine, EMOTIONS
from mood_store import MoodStore
import charts

HERE = os.path.dirname(os.path.abspath(__file__))
FRAME_W, FRAME_H = 640, 480
STREAM_FPS = 20


class Monitor:
    """Owns the camera thread and the latest annotated frame."""

    def __init__(self):
        self.engine = EmotionEngine()
        self.store = MoodStore()
        self.lock = threading.Lock()
        self.thread = None
        self.stop_event = threading.Event()
        self.cap = None

        self.running = False
        self.frame = None            # latest annotated JPEG-able frame
        self.current = None          # latest reading dict
        self.session_samples = 0
        self.ms_per_frame = 0.0
        self.log_interval = 5.0
        self.camera_index = 0
        self.error = None

    # -- lifecycle --
    def start(self, camera_index=0, log_interval=5.0):
        if self.running:
            return True, "already running"
        backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
        cap = cv2.VideoCapture(camera_index, backend)
        if not cap.isOpened():
            cap.release()
            return False, (f"Could not open camera {camera_index}. Check that a "
                           "webcam is connected, that no other app is using it, "
                           "and that camera access is allowed in your system "
                           "privacy settings.")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)

        self.cap = cap
        self.camera_index = camera_index
        self.log_interval = float(log_interval)
        self.session_samples = 0
        self.error = None
        self.stop_event.clear()
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return True, "started"

    def stop(self):
        self.running = False
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2.0)
            self.thread = None
        if self.cap:
            self.cap.release()
            self.cap = None
        with self.lock:
            self.frame = None
            self.current = None

    def _loop(self):
        last_log = 0.0
        times = []
        while not self.stop_event.is_set():
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.01)
                continue
            frame = cv2.flip(frame, 1)

            t0 = time.time()
            faces, primary = self.engine.process(frame)
            self.engine.draw(frame, faces, primary)
            times.append((time.time() - t0) * 1000)
            if len(times) > 30:
                times.pop(0)

            now = time.time()
            if primary and now - last_log >= self.log_interval:
                self.store.log(primary.emotion, primary.confidence, primary.valence)
                last_log = now
                self.session_samples += 1

            with self.lock:
                self.frame = frame
                self.ms_per_frame = sum(times) / len(times)
                self.current = {
                    "emotion": primary.emotion if primary else None,
                    "confidence": round(primary.confidence * 100, 1) if primary else 0,
                    "faces": len(faces),
                }

    def jpeg(self):
        with self.lock:
            frame = None if self.frame is None else self.frame.copy()
        if frame is None:
            return None
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        return buf.tobytes() if ok else None

    def status(self):
        with self.lock:
            cur = dict(self.current) if self.current else None
            ms = self.ms_per_frame
        return {
            "running": self.running,
            "current": cur,
            "session_samples": self.session_samples,
            "ms_per_frame": round(ms, 1),
            "fps": round(1000 / ms, 1) if ms > 0 else 0,
            "camera_index": self.camera_index,
            "log_interval": self.log_interval,
            "error": self.error,
        }


app = FastAPI(title="Elderly Mood Monitor")
monitor = Monitor()

# Photo uploads get their own engine so they never disturb the live camera
# thread's rolling smoothing state. Built once, on first upload.
_upload_engine_inst = None
_upload_engine_lock = threading.Lock()


def _upload_engine():
    global _upload_engine_inst
    with _upload_engine_lock:
        if _upload_engine_inst is None:
            _upload_engine_inst = EmotionEngine()
        # A still photo is a one-off: no temporal smoothing should carry over.
        _upload_engine_inst._ema = None
        return _upload_engine_inst


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(HERE, "static", "index.html"), encoding="utf-8") as fh:
        return HTMLResponse(fh.read())


@app.get("/video")
def video():
    """MJPEG stream. Browsers render this directly in an <img> tag."""
    def gen():
        blank = None
        interval = 1.0 / STREAM_FPS
        while True:
            data = monitor.jpeg()
            if data is None:
                if blank is None:
                    import numpy as np
                    img = np.full((FRAME_H, FRAME_W, 3), 24, dtype=np.uint8)
                    cv2.putText(img, "Camera off", (FRAME_W // 2 - 120, FRAME_H // 2),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (150, 150, 150), 2)
                    blank = cv2.imencode(".jpg", img)[1].tobytes()
                data = blank
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n")
            time.sleep(interval)

    return StreamingResponse(
        gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/status")
def api_status():
    return JSONResponse(monitor.status())


@app.post("/api/start")
def api_start(camera: int = 0, interval: float = 5.0):
    ok, msg = monitor.start(camera, interval)
    return JSONResponse({"ok": ok, "message": msg}, status_code=200 if ok else 400)


@app.post("/api/stop")
def api_stop():
    monitor.stop()
    return JSONResponse({"ok": True})


@app.get("/api/days")
def api_days():
    return JSONResponse({"days": monitor.store.days()})


@app.get("/api/summary")
def api_summary(day: str = ""):
    day = day or datetime.now().strftime("%Y-%m-%d")
    s = monitor.store.summary(day)
    if not s:
        return JSONResponse({"day": day, "empty": True})
    out = {k: v for k, v in s.items() if k != "rows"}
    out["empty"] = False
    out["alert"] = (monitor.store.check_alert()
                    if day == datetime.now().strftime("%Y-%m-%d") else None)
    return JSONResponse(out)


@app.get("/api/chart")
def api_chart(day: str = "", _t: float = 0):
    day = day or datetime.now().strftime("%Y-%m-%d")
    png = charts.render_png(monitor.store.summary(day))
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "no-store"})


@app.get("/api/export")
def api_export(day: str = ""):
    day = day or datetime.now().strftime("%Y-%m-%d")
    rows = monitor.store.samples(day)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timestamp", "time", "emotion", "confidence", "valence"])
    for ts, emotion, conf, val in rows:
        w.writerow([f"{ts:.3f}",
                    datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"),
                    emotion, f"{conf:.4f}", f"{val:.4f}"])
    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="mood_{day}.csv"'})


@app.post("/api/analyze")
async def api_analyze(request: Request, log: int = 0):
    """Analyse an uploaded photo.

    Takes the raw image bytes as the request body -- that avoids a dependency
    on python-multipart just to accept one file.
    """
    import base64
    import numpy as np

    raw = await request.body()
    if not raw:
        return JSONResponse({"ok": False, "message": "No image received."},
                            status_code=400)

    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return JSONResponse(
            {"ok": False, "message": "Could not read that file - is it a JPG or PNG?"},
            status_code=400)

    # Keep large uploads manageable for the detector and the response size.
    h, w = img.shape[:2]
    if max(h, w) > 1280:
        scale = 1280 / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)),
                         interpolation=cv2.INTER_AREA)

    engine = _upload_engine()
    faces, primary = engine.process(img)
    if not faces:
        return JSONResponse({"ok": True, "faces": 0,
                             "message": "No face found in that photo."})

    engine.draw(img, faces, primary)
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    data_url = "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()

    results = []
    for f in sorted(faces, key=lambda f: -f.w * f.h):
        top = sorted(zip(EMOTIONS, f.probs), key=lambda kv: -kv[1])[:3]
        results.append({
            "emotion": f.emotion,
            "confidence": round(f.confidence * 100, 1),
            "valence": round(f.valence, 3),
            "top": [{"emotion": e, "pct": round(float(p) * 100, 1)} for e, p in top],
        })

    if log and primary:
        monitor.store.log(primary.emotion, primary.confidence, primary.valence)

    return JSONResponse({"ok": True, "faces": len(faces),
                         "image": data_url, "results": results,
                         "logged": bool(log)})


@app.on_event("shutdown")
def _shutdown():
    monitor.stop()


def serve(host="127.0.0.1", port=8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    print("Open http://127.0.0.1:8000 in your browser")
    serve()
