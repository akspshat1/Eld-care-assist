"""FastAPI backend for the Next.js frontend.

This is a thin HTTP layer over the existing core/ and features/ modules.
No business logic should live here that isn't already in those modules —
that keeps the Streamlit pages and this API both working off the same code.
"""
import asyncio

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection

from core.database import (
    add_message,
    add_reminder,
    add_resident,
    create_conversation,
    delete_reminder,
    get_conversation,
    get_daily_records,
    get_due_reminders,
    get_extraction,
    get_messages,
    get_reminders,
    get_resident,
    get_residents,
    init_db,
    mark_reminder_fired,
    save_extraction,
    seed_residents_from_personas,
    set_reminder_active,
)
from core.llm_client import transcribe_audio
from core.voice_pipeline import run_voice_bot
from features.conversation import build_system_prompt, get_ai_reply, load_personas
from features.extraction import extract_conversation
from features.report import generate_report

app = FastAPI(title="Eld-care-assist API")

# Wide open for the hackathon demo (frontend and backend may be on different
# machines/ports). Tighten this if the app ever leaves a demo setting.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()
seed_residents_from_personas(load_personas())


class ResidentCreate(BaseModel):
    name: str
    personality: str = ""
    favorite_topics: str = ""


class ConversationCreate(BaseModel):
    resident_id: int


class MessageCreate(BaseModel):
    content: str


class VoiceOffer(BaseModel):
    sdp: str
    type: str


class ReminderCreate(BaseModel):
    resident_id: int
    time: str
    content: str


class ReminderUpdate(BaseModel):
    is_active: bool


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/residents")
def list_residents():
    return get_residents()


@app.post("/residents")
def create_resident(resident: ResidentCreate):
    add_resident(resident.name, resident.personality, resident.favorite_topics)
    return {"status": "created"}


def _reply_to_message(conversation_id, content):
    """Save the user's message, ask the LLM for a reply (using the
    conversation's resident persona), save the reply, and return it."""
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    resident = get_resident(conversation["resident_id"])
    if resident is None:
        raise HTTPException(status_code=404, detail="resident not found")

    add_message(conversation_id, "user", content)

    system_prompt = build_system_prompt(resident)
    api_messages = [{"role": "system", "content": system_prompt}]
    for msg in get_messages(conversation_id):
        api_messages.append({"role": msg["role"], "content": msg["content"]})

    reply = get_ai_reply(api_messages)
    add_message(conversation_id, "assistant", reply)
    return reply


@app.post("/conversations")
def start_conversation(payload: ConversationCreate):
    conversation_id = create_conversation(payload.resident_id)
    return {"conversation_id": conversation_id}


@app.get("/conversations/{conversation_id}/messages")
def list_messages(conversation_id: int):
    return get_messages(conversation_id)


@app.post("/conversations/{conversation_id}/messages")
def send_text_message(conversation_id: int, payload: MessageCreate):
    reply = _reply_to_message(conversation_id, payload.content)
    return {"reply": reply}


@app.post("/conversations/{conversation_id}/messages/audio")
async def send_audio_message(conversation_id: int, file: UploadFile = File(...)):
    audio_bytes = await file.read()
    transcribed_text = transcribe_audio(audio_bytes, filename=file.filename or "audio.webm")
    reply = _reply_to_message(conversation_id, transcribed_text)
    return {"transcribed_text": transcribed_text, "reply": reply}


@app.post("/conversations/{conversation_id}/voice/offer")
async def voice_offer(conversation_id: int, payload: VoiceOffer):
    """Accept a WebRTC SDP offer from the browser and start a hands-free
    Pipecat voice session (Groq STT + Groq LLM, VAD-driven, no button
    presses) for this conversation. Returns the SDP answer."""
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    resident = get_resident(conversation["resident_id"])
    if resident is None:
        raise HTTPException(status_code=404, detail="resident not found")

    connection = SmallWebRTCConnection()
    await connection.initialize(sdp=payload.sdp, type=payload.type)
    answer = connection.get_answer()

    asyncio.create_task(run_voice_bot(connection, conversation_id, resident))

    return {"sdp": answer["sdp"], "type": answer["type"]}


@app.post("/conversations/{conversation_id}/extract")
def extract(conversation_id: int):
    messages = get_messages(conversation_id)
    if not messages:
        raise HTTPException(status_code=400, detail="no messages to extract")
    result = extract_conversation(messages)
    save_extraction(
        conversation_id, result["mood"], result["summary"], result["notable_points"]
    )
    return result


@app.get("/conversations/{conversation_id}/extraction")
def get_extraction_endpoint(conversation_id: int):
    return get_extraction(conversation_id) or {}


@app.get("/reports")
def get_reports(date: str, resident_id: int | None = None):
    """Return one handoff report per resident that has a conversation record
    on the given date (YYYY-MM-DD), optionally filtered to one resident."""
    records = get_daily_records(date, resident_id)

    records_by_resident = {}
    for rec in records:
        records_by_resident.setdefault(rec["resident_id"], []).append(rec)

    reports = []
    for rid, resident_records in records_by_resident.items():
        resident_name = resident_records[0]["resident_name"]
        report_text = generate_report(resident_name, resident_records)
        reports.append({"resident_id": rid, "resident_name": resident_name, "report": report_text})
    return reports


@app.get("/reminders")
def list_reminders():
    return get_reminders()


@app.post("/reminders")
def create_reminder(reminder: ReminderCreate):
    add_reminder(reminder.resident_id, reminder.time, reminder.content)
    return {"status": "created"}


@app.patch("/reminders/{reminder_id}")
def update_reminder(reminder_id: int, payload: ReminderUpdate):
    set_reminder_active(reminder_id, payload.is_active)
    return {"status": "updated"}


@app.delete("/reminders/{reminder_id}")
def remove_reminder(reminder_id: int):
    delete_reminder(reminder_id)
    return {"status": "deleted"}


@app.get("/reminders/due")
def list_due_reminders():
    """Return reminders that should fire now, and mark them as fired so the
    frontend's polling loop doesn't repeat them for the rest of the day."""
    due = get_due_reminders()
    for reminder in due:
        mark_reminder_fired(reminder["id"])
    return due
