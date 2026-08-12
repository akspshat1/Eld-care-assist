"""音声感情モニター / Voice Mood Monitor -- browser UI.

Recording happens in the browser (Web Audio API -> WAV), so no microphone
library is needed on the Python side. The server decodes, resamples to 16 kHz
and runs the Japanese speech-emotion model.

    python run.py          # starts this and opens your browser
"""

import io
import csv
import os
import threading
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

import voice_engine
from voice_engine import VoiceEngine, NoSpeech, load_audio, label_ja, label_en
from mood_store import MoodStore
import charts

HERE = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Voice Mood Monitor")
store = MoodStore()

_engine = None
_engine_lock = threading.Lock()
_engine_error = None


def get_engine():
    """Load the model on first use -- it is large, so not at import time."""
    global _engine, _engine_error
    with _engine_lock:
        if _engine is None and _engine_error is None:
            try:
                _engine = VoiceEngine()
            except Exception as e:            # noqa: BLE001 - surfaced to the UI
                _engine_error = str(e)
        if _engine_error:
            raise RuntimeError(_engine_error)
        return _engine


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(HERE, "static", "index.html"), encoding="utf-8") as fh:
        return HTMLResponse(fh.read())


@app.get("/api/health")
def api_health():
    return JSONResponse({
        "model_ready": _engine is not None,
        "model_error": _engine_error,
        "emotions": [{"code": c, "ja": label_ja(c), "en": label_en(c),
                      "color": voice_engine.COLORS[c]}
                     for c in voice_engine.EMOTIONS],
    })


@app.post("/api/warmup")
def api_warmup():
    try:
        get_engine()
        return JSONResponse({"ok": True})
    except Exception as e:                    # noqa: BLE001
        return JSONResponse({"ok": False, "message": str(e)}, status_code=500)


@app.post("/api/analyze")
async def api_analyze(request: Request, log: int = 1, source: str = "live"):
    """Analyse a recorded or uploaded clip.

    The audio arrives as raw bytes in the request body -- WAV from the
    recorder, or whatever file the user picked on the upload tab.
    """
    raw = await request.body()
    if not raw:
        return JSONResponse({"ok": False,
                             "message": "音声が届きませんでした / No audio received."},
                            status_code=400)

    try:
        engine = get_engine()
    except Exception as e:                    # noqa: BLE001
        return JSONResponse({"ok": False, "message": str(e)}, status_code=500)

    try:
        wav = load_audio(bytes(raw))
    except Exception:                         # noqa: BLE001
        return JSONResponse(
            {"ok": False,
             "message": ("この音声ファイルを読み込めませんでした。WAV / MP3 / FLAC / OGG "
                         "をお使いください。 / Could not read that audio file.")},
            status_code=400)

    try:
        result = engine.analyze(wav)
    except NoSpeech as e:
        # Silence is not an emotion -- report it and log nothing.
        return JSONResponse({"ok": True, "speech": False, "message": str(e)})

    overall = result["overall"]
    logged = 0
    if log:
        # Log each window so a long recording contributes several readings.
        now = datetime.now().timestamp()
        span = result["duration"]
        for w in result["windows"]:
            ts = now - (span - w["start"])    # place each window in real time
            store.log(w["emotion"], w["confidence"], w["valence"],
                      source=source, ts=ts)
            logged += 1

    return JSONResponse({
        "ok": True, "speech": True,
        "overall": overall,
        "windows": result["windows"],
        "duration": result["duration"],
        "logged": logged,
        "alert": store.check_alert(),
    })


@app.get("/api/days")
def api_days():
    return JSONResponse({"days": store.days()})


@app.get("/api/summary")
def api_summary(day: str = ""):
    day = day or datetime.now().strftime("%Y-%m-%d")
    s = store.summary(day)
    if not s:
        return JSONResponse({"day": day, "empty": True})
    out = {k: v for k, v in s.items() if k != "rows"}
    out["empty"] = False
    out["alert"] = (store.check_alert()
                    if day == datetime.now().strftime("%Y-%m-%d") else None)
    return JSONResponse(out)


@app.get("/api/chart")
def api_chart(day: str = "", lang: str = "en", _t: float = 0):
    day = day or datetime.now().strftime("%Y-%m-%d")
    png = charts.render_png(store.summary(day), lang=lang)
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "no-store"})


@app.get("/api/export")
def api_export(day: str = ""):
    day = day or datetime.now().strftime("%Y-%m-%d")
    buf = io.StringIO()
    csv.writer(buf).writerows(store.export_csv_rows(day))
    # BOM so Excel on a Japanese system opens the UTF-8 correctly.
    return Response(
        content="﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="voice_{day}.csv"'})


def serve(host="127.0.0.1", port=8001):
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    print("Open http://127.0.0.1:8001 in your browser")
    serve()
