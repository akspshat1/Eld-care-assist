"""Family dashboard -- how is grandma doing, at a glance.

Read-only over the care and medication data, plus contact management. Contacts
are written into the shared care database so the resident's conversation app
can act on them ("call my grandson").

    python run.py
"""

import os
import io
import csv
import json
from datetime import date

import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import config
import sources

HERE = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Family Dashboard")
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")),
          name="static")


def _err(message, status=400):
    return JSONResponse({"ok": False, "message": message}, status_code=status)


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(HERE, "static", "index.html"), encoding="utf-8") as fh:
        return HTMLResponse(fh.read())


@app.get("/api/health")
def api_health():
    st = sources.status()
    return JSONResponse({
        "ok": True, "sources": st,
        "message": None if st["care_db"] else
        "No care data yet. Run eld_care_assist and do a check-in first.",
    })


@app.get("/api/residents")
def api_residents():
    if not config.care_db_exists():
        return JSONResponse({"residents": []})
    return JSONResponse({"residents": sources.care().residents()})


@app.get("/api/overview")
def api_overview(resident_id: int, days: int = 14):
    if not config.care_db_exists():
        return _err("No care database yet. Run eld_care_assist first.", 404)
    data = sources.overview(resident_id, days)
    if data is None:
        return _err("Unknown resident.", 404)
    return JSONResponse({"ok": True, **data})


@app.get("/api/timeline")
def api_timeline(resident_id: int, days: int = 14):
    if not config.care_db_exists():
        return _err("No care database yet.", 404)
    return JSONResponse({"ok": True, "days": sources.timeline(resident_id, days)})


# -------------------------------------------------------------- contacts --

@app.get("/api/contacts")
def api_contacts(resident_id: int | None = None):
    if not config.care_db_exists():
        return JSONResponse({"contacts": []})
    return JSONResponse({"contacts": sources.care().contacts(resident_id)})


@app.post("/api/contacts")
async def api_add_contact(request: Request):
    body = await request.json()
    name = (body.get("name") or "").strip()
    phone = (body.get("phone") or "").strip()
    if not name:
        return _err("A name is required.")
    if not phone:
        return _err("A phone number is required.")
    cid = sources.care().add_contact(
        name=name, phone=phone,
        relationship=(body.get("relationship") or "").strip(),
        resident_id=body.get("resident_id"),
        email=(body.get("email") or "").strip(),
        is_primary=bool(body.get("is_primary")),
        notes=(body.get("notes") or "").strip())
    return JSONResponse({"ok": True, "id": cid})


@app.patch("/api/contacts/{contact_id}")
async def api_update_contact(contact_id: int, request: Request):
    body = await request.json()
    ok = sources.care().update_contact(contact_id, body)
    return JSONResponse({"ok": ok})


@app.delete("/api/contacts/{contact_id}")
def api_delete_contact(contact_id: int):
    sources.care().delete_contact(contact_id)
    return JSONResponse({"ok": True})


@app.post("/api/contacts/{contact_id}/call")
def api_log_call(contact_id: int, resident_id: int | None = None):
    """Record a call started from the dashboard."""
    st = sources.care()
    if st.contact(contact_id) is None:
        return _err("Unknown contact.")
    st.log_call(contact_id, resident_id, "dashboard")
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------- digest --

DIGEST_SYSTEM = """You write a short, warm update for a family member about
their elderly relative, from care records.

Write as if speaking to their grandson or daughter -- plain, kind, specific.
2-4 sentences. Lead with how the person actually is.

Rules:
- Only use what is in the input. Invent nothing.
- Never diagnose, never give medical or medication advice.
- If something needs attention, say so plainly and suggest they phone or visit.
- If all is well, say so warmly and briefly. Do not manufacture concern."""


@app.get("/api/digest")
def api_digest(resident_id: int, lang: str = "en"):
    """A couple of sentences a family member can read in five seconds."""
    if not config.groq_ready():
        return _err("No Groq API key set, so the written update is unavailable.")
    data = sources.overview(resident_id)
    if data is None:
        return _err("Unknown resident.", 404)

    lines = [f"Resident: {data['resident']['name']}"]
    latest = data["latest"]
    if latest:
        lines.append(f"Last check-in {latest['day']} {latest['time']}: "
                     f"wellbeing {latest['wellbeing']}/100. {latest['summary']}")
        if latest["concerns"]:
            lines.append("Concerns noted: " + "; ".join(latest["concerns"]))
    else:
        lines.append("No check-ins recorded yet.")
    if data["trend"]:
        lines.append("Recent wellbeing scores: "
                     + ", ".join(f"{d['day']}={d['score']}" for d in data["trend"][-7:]))
    med = data["medication"]
    if med:
        lines.append(f"Medicines today: {med['today']['taken']} of "
                     f"{med['today']['total']} taken, {med['today']['missed']} missed.")
        if med["missed_today"]:
            lines.append("Missed: " + ", ".join(
                f"{m['name']} at {m['slot']}" for m in med["missed_today"]))
    for a in data["alerts"]:
        lines.append(f"Alert ({a['level']}): {a['text']}")

    lang_line = ("Write the update in Japanese." if lang == "ja"
                 else "Write the update in English.")
    try:
        r = requests.post(
            f"{config.GROQ_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
            json={"model": config.TEXT_MODEL, "temperature": 0.4,
                  "max_tokens": 350,
                  "messages": [{"role": "system", "content": DIGEST_SYSTEM},
                               {"role": "user",
                                "content": lang_line + "\n\n" + "\n".join(lines)}]},
            timeout=config.TIMEOUT_SEC)
        if r.status_code >= 400:
            detail = ""
            try:
                detail = r.json().get("error", {}).get("message", "")
            except Exception:                 # noqa: BLE001
                detail = r.text[:200]
            return _err(f"Groq error {r.status_code}: {detail}")
        text = r.json()["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        return _err(f"Could not reach Groq: {e}")

    return JSONResponse({"ok": True, "digest": text.strip()})


@app.get("/api/export")
def api_export(resident_id: int, days: int = 30):
    rows = [["day", "wellbeing", "check-ins", "concerns",
             "medicines taken", "medicines total", "missed"]]
    for d in sources.timeline(resident_id, days):
        m = d["medication"] or {}
        rows.append([d["day"], d["wellbeing"] if d["wellbeing"] is not None else "",
                     d["checkins"], "; ".join(d["concerns"]),
                     m.get("taken", ""), m.get("total", ""), m.get("missed", "")])
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return Response(
        content="﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="family_report.csv"'})


def serve(host="127.0.0.1", port=8300):
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    print("Open http://127.0.0.1:8300")
    serve()
