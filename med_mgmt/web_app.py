"""Medication Manager -- browser UI.

Upload a prescription (photo or text), an AI reads it into a draft schedule,
a human confirms it, and the app then reminds at each dose time.

    python run.py          # starts this and opens your browser
"""

import os
import io
import csv
from datetime import datetime, date

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

import groq_client
import extractor
from med_store import MedStore

HERE = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Medication Manager")
store = MedStore()


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(HERE, "static", "index.html"), encoding="utf-8") as fh:
        return HTMLResponse(fh.read())


@app.get("/api/health")
def api_health():
    cfg = groq_client.config
    return JSONResponse({
        "groq_ready": groq_client.ready(),
        "message": None if groq_client.ready() else groq_client.missing_key_message(),
        "text_model": cfg.GROQ_TEXT_MODEL,
        "vision_model": cfg.GROQ_VISION_MODEL,
        "config_path": os.path.join(cfg.ROOT, "config.py"),
        "env_path": cfg.ENV_PATH,
        "env_exists": os.path.exists(cfg.ENV_PATH),
    })


@app.get("/api/models")
def api_models():
    """What the key can actually use -- for when a default model ID 404s."""
    try:
        return JSONResponse({"ok": True, "models": groq_client.list_models()})
    except groq_client.GroqError as e:
        return JSONResponse({"ok": False, "message": str(e)}, status_code=400)


# ------------------------------------------------------------- extraction --

@app.post("/api/extract/text")
async def api_extract_text(request: Request):
    body = await request.json()
    try:
        draft = extractor.from_text(body.get("text", ""))
    except groq_client.GroqError as e:
        return JSONResponse({"ok": False, "message": str(e)}, status_code=400)
    return JSONResponse({"ok": True, **draft})


@app.post("/api/extract/image")
async def api_extract_image(request: Request):
    raw = await request.body()
    if not raw:
        return JSONResponse({"ok": False, "message": "No image received."},
                            status_code=400)
    mime = request.headers.get("content-type") or "image/jpeg"
    if not mime.startswith("image/"):
        mime = "image/jpeg"
    try:
        draft = extractor.from_image(bytes(raw), mime=mime)
    except groq_client.GroqError as e:
        return JSONResponse({"ok": False, "message": str(e)}, status_code=400)
    return JSONResponse({"ok": True, **draft})


# ------------------------------------------------------------ medications --

@app.get("/api/medications")
def api_medications():
    return JSONResponse({"medications": store.all_meds()})


@app.post("/api/medications")
async def api_add(request: Request):
    """Save reviewed medications. Only ever called after human confirmation."""
    body = await request.json()
    meds = body.get("medications")
    if not isinstance(meds, list) or not meds:
        return JSONResponse({"ok": False, "message": "Nothing to save."},
                            status_code=400)
    ids = []
    for m in meds:
        if not m.get("name"):
            continue
        ids.append(store.add(m))
    return JSONResponse({"ok": True, "saved": len(ids), "ids": ids})


@app.patch("/api/medications/{med_id}")
async def api_update(med_id: int, request: Request):
    body = await request.json()
    ok = store.update(med_id, body)
    return JSONResponse({"ok": ok})


@app.delete("/api/medications/{med_id}")
def api_delete(med_id: int):
    store.delete(med_id)
    return JSONResponse({"ok": True})


# ----------------------------------------------------------------- doses --

@app.get("/api/today")
def api_today(day: str = ""):
    day = day or date.today().isoformat()
    summary = store.day_summary(day)
    summary["as_needed"] = store.as_needed_meds(day)
    return JSONResponse(summary)


@app.get("/api/due")
def api_due():
    """Polled by the browser to drive reminders."""
    nxt = store.next_dose()
    return JSONResponse({
        "now": datetime.now().strftime("%H:%M"),
        "due": store.due_now(),
        "next": nxt,
    })


@app.post("/api/dose")
async def api_dose(request: Request):
    body = await request.json()
    med_id, day, slot = body.get("med_id"), body.get("day"), body.get("slot")
    status = body.get("status")
    if med_id is None or not day or not slot:
        return JSONResponse({"ok": False, "message": "Missing dose details."},
                            status_code=400)
    try:
        if status == "undo":
            store.unmark(int(med_id), day, slot)
        else:
            store.mark(int(med_id), day, slot, status)
    except ValueError as e:
        return JSONResponse({"ok": False, "message": str(e)}, status_code=400)
    return JSONResponse({"ok": True})


@app.post("/api/prn/{med_id}")
def api_prn(med_id: int):
    store.log_prn(med_id)
    return JSONResponse({"ok": True})


# --------------------------------------------------------------- history --

@app.get("/api/history")
def api_history(days: int = 14):
    return JSONResponse({"history": store.history(min(max(days, 1), 90))})


@app.get("/api/export")
def api_export(days: int = 30):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["day", "time", "medication", "strength", "dose", "status"])
    for d in store.history(min(max(days, 1), 365)):
        for dose in d["doses"]:
            w.writerow([d["day"], dose["slot"], dose["name"],
                        dose["strength"] or "", dose["dose_amount"] or "",
                        dose["status"]])
    return Response(
        content="﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="medications.csv"'})


def serve(host="127.0.0.1", port=8002):
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    print("Open http://127.0.0.1:8002 in your browser")
    serve()
