"""Elder Care Assistant -- one app over all the pieces.

Brings together, in a single browser UI on one port:
  * Daily condition check-in  (questions + photo + optional voice)
  * Two-way conversation      (text or voice, persona-aware)
  * Face emotion              (Face_rec's ONNX pipeline)
  * Voice emotion             (voice_rec's Japanese speech model)
  * Medications               (med_mgmt's store and prescription reader)
  * Daily handoff report      (everything above, summarised for the next carer)

    python run.py
"""

import io
import os
import csv
import json
from datetime import datetime, date

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import config
import groq_api
import engines
import handsfree
import checkin as checkin_mod
from store import Store

HERE = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Elder Care Assistant")
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")),
          name="static")
store = Store()


def _err(message, status=400):
    return JSONResponse({"ok": False, "message": message}, status_code=status)


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(HERE, "static", "index.html"), encoding="utf-8") as fh:
        return HTMLResponse(fh.read())


@app.get("/api/health")
def api_health():
    st = engines.status()
    return JSONResponse({
        "ok": True,
        "features": st,
        "groq_message": None if st["groq"] else config.missing_key_message(),
        "text_model": config.TEXT_MODEL,
        "vision_model": config.VISION_MODEL,
        "voice_note": None if st["voice"] else
        "Voice emotion model not downloaded (1.2 GB). Run: cd voice_rec && python download_models.py",
        "face_note": None if st["face"] else
        "Face model not downloaded. Run: cd Face_rec && python download_models.py",
    })


# ------------------------------------------------------------- residents --

@app.get("/api/residents")
def api_residents():
    return JSONResponse({"residents": store.residents()})


@app.post("/api/residents")
async def api_add_resident(request: Request):
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        return _err("A name is required.")
    rid = store.add_resident(name, body.get("personality", ""),
                             body.get("topics", ""))
    return JSONResponse({"ok": True, "id": rid})


# -------------------------------------------------------------- check-in --

@app.get("/api/checkin/questions")
def api_questions(lang: str = "en"):
    return JSONResponse({"questions": checkin_mod.question_list(lang)})


@app.post("/api/checkin/photo")
async def api_checkin_photo(request: Request):
    """Read a face emotion from one photo. Nothing is saved to disk."""
    raw = await request.body()
    if not raw:
        return _err("No photo received.")
    if not engines.face_available():
        return _err("The face model is not downloaded. Run: cd Face_rec && "
                    "python download_models.py")

    import numpy as np
    import cv2

    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return _err("Could not read that image.")

    engine = engines.get_face_engine()
    faces, primary = engine.process(img)
    if not primary:
        return JSONResponse({"ok": True, "found": False,
                             "message": "No face found in the photo."})
    return JSONResponse({"ok": True, "found": True, "face": {
        "emotion": primary.emotion,
        "confidence": round(primary.confidence * 100, 1),
        "valence": round(primary.valence, 3),
    }})


@app.post("/api/checkin/voice")
async def api_checkin_voice(request: Request, lang: str = "en"):
    """Transcribe a spoken answer, and read its tone if the model is present."""
    raw = await request.body()
    if not raw:
        return _err("No audio received.")

    try:
        transcript = groq_api.transcribe(bytes(raw), "answer.wav", lang)
    except groq_api.GroqError as e:
        return _err(str(e))

    voice = None
    if engines.voice_available():
        try:
            ve = engines.get_voice_engine()
            vm = engines.voice_helpers()
            wav = vm.load_audio(bytes(raw))
            result = ve.analyze(wav)
            o = result["overall"]
            voice = {"emotion": o["en"], "emotion_ja": o["ja"],
                     "confidence": o["confidence"], "valence": o["valence"]}
        except Exception:                     # noqa: BLE001 - optional extra
            voice = None

    return JSONResponse({"ok": True, "transcript": transcript, "voice": voice})


@app.post("/api/checkin/voice/start")
async def api_checkin_voice_start(request: Request):
    """Begin a spoken check-in: a hands-free conversation that interviews.

    Same Pipecat pipeline as the Talk tab, with the interviewer prompt instead
    of the companion one. The answers are pulled out of the transcript
    afterwards by /api/checkin/voice/finish.
    """
    if not handsfree.available():
        return _err(handsfree.error() or "Hands-free is unavailable.", 503)

    body = await request.json()
    sdp, sdp_type = body.get("sdp"), body.get("type")
    lang = body.get("lang", "en")
    rid = body.get("resident_id")
    if not sdp or not sdp_type:
        return _err("Bad WebRTC offer.")
    resident = store.resident(rid) if rid else None
    if resident is None:
        return _err("Pick who this check-in is for.")

    cid = store.start_conversation(rid)
    handsfree.install_hooks(
        store, lambda r, l: checkin_mod.interview_prompt(r, l))

    try:
        Connection = handsfree.connection_class()
        connection = Connection()
        await connection.initialize(sdp=sdp, type=sdp_type)
        answer = connection.get_answer()
        handsfree.spawn(connection, cid, resident, lang)
    except Exception as e:                    # noqa: BLE001
        return _err(f"Could not start the spoken check-in: {e}", 500)

    return JSONResponse({"ok": True, "conversation_id": cid,
                         "sdp": answer["sdp"], "type": answer["type"]})


@app.post("/api/checkin/voice/finish")
async def api_checkin_voice_finish(request: Request):
    """Turn a finished spoken check-in into answers the form can show."""
    body = await request.json()
    cid = body.get("conversation_id")
    lang = body.get("lang", "en")
    if not cid:
        return _err("No check-in conversation.")

    messages = store.messages(cid)
    if not messages:
        return _err("Nothing was said in that check-in.")

    answers, quote = checkin_mod.answers_from_transcript(messages, lang)
    return JSONResponse({"ok": True, "answers": answers, "quote": quote,
                         "messages": messages})


@app.post("/api/checkin/answer_voice")
async def api_checkin_answer_voice(request: Request, question_id: str = "",
                                   lang: str = "en"):
    """Spoken answer to one check-in question.

    Transcribes it, then maps the words onto one of that question's options.
    Returns the raw transcript too, so the resident's own words are kept even
    when the mapping is unsure.
    """
    raw = await request.body()
    if not raw:
        return _err("No audio received.")
    question = next((q for q in checkin_mod.QUESTIONS if q["id"] == question_id), None)
    if question is None:
        return _err("Unknown question.")

    try:
        transcript = groq_api.transcribe(bytes(raw), "answer.wav", lang)
    except groq_api.GroqError as e:
        return _err(str(e))
    if not transcript:
        return JSONResponse({"ok": True, "transcript": "", "value": None,
                             "unclear": True})

    value, unclear = checkin_mod.interpret_answer(question, transcript, lang)
    return JSONResponse({"ok": True, "transcript": transcript,
                         "value": value, "unclear": unclear})


@app.post("/api/checkin/submit")
async def api_checkin_submit(request: Request):
    body = await request.json()
    resident_id = body.get("resident_id")
    answers = body.get("answers") or {}
    if not resident_id:
        return _err("Pick who this check-in is for.")
    if not answers:
        return _err("Please answer at least one question.")

    lang = body.get("lang", "en")
    face = body.get("face")
    voice = body.get("voice")
    transcript = (body.get("transcript") or "").strip()

    result = checkin_mod.build_result(answers, face, voice, transcript, lang)
    cid = store.add_checkin(resident_id, answers, face, voice, transcript, result)
    return JSONResponse({"ok": True, "id": cid, **result})


@app.get("/api/checkin/history")
def api_checkin_history(resident_id: int | None = None, day: str = "", limit: int = 30):
    return JSONResponse({
        "checkins": store.checkins(day or None, resident_id, limit),
        "trend": store.checkin_trend(resident_id, 14) if resident_id else [],
    })


# ---------------------------------------------------------- conversation --

def _system_prompt(resident, lang):
    topics = resident.get("topics") or ""
    length_en = (
        "Match the length of your reply to what was said. Greetings or short "
        "remarks get ONE short sentence. Only when they share a memory or a "
        "story do you reply with 2-3 sentences. Never more than 4. Do not end "
        "every reply with a question."
    )
    length_ja = (
        "返答の長さは相手の発言に合わせてください。あいさつや短い言葉には1文だけ、"
        "思い出や出来事を語ったときだけ2〜3文で応じ、4文以上は書かないでください。"
        "毎回質問を返さないでください。"
    )
    base = (
        f"You are a warm, patient companion talking with {resident['name']}, "
        f"a resident in an elder care home.\n"
        f"Personality: {resident.get('personality') or 'unknown'}\n"
        f"Favourite topics: {topics or 'unknown'}\n"
        "Speak naturally and kindly. If they mention feeling unwell or upset, "
        "ask gently -- never push. You are not a doctor: never diagnose and "
        "never give medical or medication advice; if health worries come up, "
        "warmly suggest telling a caregiver or nurse.\n"
    )
    return base + (("日本語で返答してください。\n" + length_ja) if lang == "ja"
                   else ("Reply in English.\n" + length_en))


def _reply(conversation_id, content, lang, audio_bytes=None):
    conv = store.conversation(conversation_id)
    if conv is None:
        return None, "Conversation not found."
    resident = store.resident(conv["resident_id"])
    if resident is None:
        return None, "Resident not found."

    msg_id = store.add_message(conversation_id, "user", content)
    if audio_bytes:
        # Keep the recording so voice emotion can be run over it later.
        store.save_audio(conversation_id, msg_id, audio_bytes)

    msgs = [{"role": "system", "content": _system_prompt(resident, lang)}]
    for m in store.messages(conversation_id):
        msgs.append({"role": m["role"], "content": m["content"]})

    try:
        reply = groq_api.chat(msgs, temperature=0.7, max_tokens=300)
    except groq_api.GroqError as e:
        return None, str(e)

    store.add_message(conversation_id, "assistant", reply)
    return reply, None


@app.post("/api/conversation/start")
async def api_conv_start(request: Request):
    body = await request.json()
    rid = body.get("resident_id")
    if not rid:
        return _err("Pick who you are talking to.")
    return JSONResponse({"ok": True, "conversation_id": store.start_conversation(rid)})


@app.get("/api/conversation/{cid}/messages")
def api_conv_messages(cid: int):
    return JSONResponse({"messages": store.messages(cid)})


@app.post("/api/conversation/{cid}/say")
async def api_conv_say(cid: int, request: Request):
    body = await request.json()
    content = (body.get("content") or "").strip()
    if not content:
        return _err("Nothing to send.")
    reply, err = _reply(cid, content, body.get("lang", "en"))
    if err:
        return _err(err)
    return JSONResponse({"ok": True, "reply": reply})


@app.post("/api/conversation/{cid}/say_audio")
async def api_conv_say_audio(cid: int, request: Request, lang: str = "en"):
    raw = await request.body()
    if not raw:
        return _err("No audio received.")
    try:
        text = groq_api.transcribe(bytes(raw), "speech.wav", lang)
    except groq_api.GroqError as e:
        return _err(str(e))
    if not text:
        return _err("Nothing was heard in that recording.")
    reply, err = _reply(cid, text, lang, audio_bytes=bytes(raw))
    if err:
        return _err(err)
    return JSONResponse({"ok": True, "transcript": text, "reply": reply,
                         "audio_saved": True})


@app.post("/api/conversation/{cid}/voice/offer")
async def api_voice_offer(cid: int, request: Request):
    """Start a hands-free call: browser sends a WebRTC offer, we answer.

    The pipeline itself is Converse_2way's, reused as-is; only its storage and
    prompt are redirected to this app.
    """
    if not handsfree.available():
        return _err(handsfree.error() or "Hands-free is unavailable.", 503)

    body = await request.json()
    sdp, sdp_type = body.get("sdp"), body.get("type")
    lang = body.get("lang", "en")
    if not sdp or not sdp_type:
        return _err("Bad WebRTC offer.")

    conv = store.conversation(cid)
    if conv is None:
        return _err("Conversation not found.")
    resident = store.resident(conv["resident_id"])
    if resident is None:
        return _err("Resident not found.")

    handsfree.install_hooks(store, _system_prompt)

    try:
        Connection = handsfree.connection_class()
        connection = Connection()
        await connection.initialize(sdp=sdp, type=sdp_type)
        answer = connection.get_answer()
        handsfree.spawn(connection, cid, resident, lang)
    except Exception as e:                    # noqa: BLE001
        return _err(f"Could not start the hands-free call: {e}", 500)

    return JSONResponse({"ok": True, "sdp": answer["sdp"], "type": answer["type"]})


@app.post("/api/conversation/{cid}/analyze_voice")
def api_conv_analyze_voice(cid: int, all_turns: bool = False):
    """Run voice emotion over the saved recordings of this conversation.

    Deliberately on demand rather than during the chat: the model is 1.2 GB
    and takes seconds per clip, which would make talking feel sluggish.
    """
    if not engines.voice_available():
        return _err("The voice emotion model is not downloaded (1.2 GB). "
                    "Run: cd voice_rec && python download_models.py")

    pending = store.messages_with_audio(cid, only_unanalyzed=not all_turns)
    if not pending:
        summary = store.conversation_voice_summary(cid)
        if summary:
            return JSONResponse({"ok": True, "analyzed": 0, "summary": summary,
                                 "message": "Everything recorded is already analysed."})
        return _err("No saved recordings in this conversation yet. Use the "
                    "microphone button when you talk.")

    try:
        engine = engines.get_voice_engine()
        vm = engines.voice_helpers()
    except Exception as e:                    # noqa: BLE001
        return _err(f"Could not load the voice model: {e}")

    done, failed = 0, 0
    for m in pending:
        path = m["audio_path"]
        if not path or not os.path.exists(path):
            failed += 1
            continue
        try:
            wav = vm.load_audio(path)
            o = engine.analyze(wav)["overall"]
            store.set_message_voice(m["id"], o["en"], o["confidence"], o["valence"])
            done += 1
        except Exception:                     # noqa: BLE001 - silence, too short, etc.
            failed += 1

    return JSONResponse({"ok": True, "analyzed": done, "skipped": failed,
                         "summary": store.conversation_voice_summary(cid)})


@app.get("/api/conversation/{cid}/voice_summary")
def api_conv_voice_summary(cid: int):
    return JSONResponse({
        "ok": True,
        "summary": store.conversation_voice_summary(cid),
        "pending": len(store.messages_with_audio(cid, only_unanalyzed=True)),
    })


EXTRACT_SYSTEM = """You turn a conversation with an elder-care resident into a
short record for the next caregiver. Report only what is in the conversation;
invent nothing. Do not diagnose or give medical advice.

Return ONLY this JSON:
{"mood": "their mood in a few words",
 "summary": "2-3 sentences on what was talked about",
 "notable_points": "anything the next caregiver should know, or 'Nothing particular'"}"""


@app.post("/api/conversation/{cid}/record")
async def api_conv_record(cid: int, lang: str = "en"):
    msgs = store.messages(cid)
    if not msgs:
        return _err("There is no conversation to record yet.")
    conv = store.conversation(cid)
    text = "\n".join(f"{m['role']}: {m['content']}" for m in msgs)
    lang_line = ("Write the values in Japanese." if lang == "ja"
                 else "Write the values in English.")
    try:
        data = groq_api.chat_json(EXTRACT_SYSTEM, f"{lang_line}\n\n{text}")
    except groq_api.GroqError as e:
        return _err(str(e))

    mood = str(data.get("mood", ""))
    summary = str(data.get("summary", ""))
    notable = str(data.get("notable_points", ""))
    store.save_conv_record(cid, conv["day"], mood, summary, notable)
    return JSONResponse({"ok": True, "mood": mood, "summary": summary,
                         "notable_points": notable})


# ---------------------------------------------------------- medications ---

@app.get("/api/medications")
def api_medications():
    return JSONResponse({"medications": engines.get_med_store().all_meds()})


@app.get("/api/medications/today")
def api_meds_today():
    ms = engines.get_med_store()
    today = date.today().isoformat()
    summary = ms.day_summary(today)
    summary["as_needed"] = ms.as_needed_meds(today)
    summary["due"] = ms.due_now()
    nxt = ms.next_dose()
    summary["next"] = nxt
    return JSONResponse(summary)


@app.post("/api/medications/dose")
async def api_meds_dose(request: Request):
    body = await request.json()
    ms = engines.get_med_store()
    try:
        if body.get("status") == "undo":
            ms.unmark(int(body["med_id"]), body["day"], body["slot"])
        else:
            ms.mark(int(body["med_id"]), body["day"], body["slot"], body["status"])
    except (KeyError, ValueError) as e:
        return _err(f"Bad dose details: {e}")
    return JSONResponse({"ok": True})


@app.post("/api/medications/extract_text")
async def api_meds_extract_text(request: Request):
    body = await request.json()
    ex = engines.get_med_extractor()
    try:
        return JSONResponse({"ok": True, **ex.from_text(body.get("text", ""))})
    except Exception as e:                    # noqa: BLE001
        return _err(str(e))


@app.post("/api/medications/extract_photo")
async def api_meds_extract_photo(request: Request):
    raw = await request.body()
    if not raw:
        return _err("No image received.")
    mime = request.headers.get("content-type") or "image/jpeg"
    ex = engines.get_med_extractor()
    try:
        return JSONResponse({"ok": True, **ex.from_image(
            bytes(raw), mime=mime if mime.startswith("image/") else "image/jpeg")})
    except Exception as e:                    # noqa: BLE001
        return _err(str(e))


@app.post("/api/medications/save")
async def api_meds_save(request: Request):
    body = await request.json()
    meds = body.get("medications")
    if not isinstance(meds, list) or not meds:
        return _err("Nothing to save.")
    ms = engines.get_med_store()
    ids = [ms.add(m) for m in meds if m.get("name")]
    return JSONResponse({"ok": True, "saved": len(ids)})


@app.delete("/api/medications/{med_id}")
def api_meds_delete(med_id: int):
    engines.get_med_store().delete(med_id)
    return JSONResponse({"ok": True})


# --------------------------------------------------------------- report ---

REPORT_SYSTEM = """You write the end-of-day handoff note for the next caregiver
in an elder care home, from the day's check-ins, conversations and medication
record.

Report only what is in the input. Never diagnose, never give medical advice,
never mention specific medications by way of recommendation. Write plainly.

Use exactly these headings, each on its own line:
[How they have been]
[Worth watching]
[Needs attention]

Under any heading with nothing to report, write "Nothing particular"."""


@app.get("/api/report")
def api_report(day: str = "", resident_id: int | None = None, lang: str = "en"):
    day = day or date.today().isoformat()
    checkins = store.checkins(day, resident_id)
    records = store.conv_records(day)
    if resident_id:
        records = [r for r in records if r["resident_id"] == resident_id]

    meds = engines.get_med_store().day_summary(day)

    if not checkins and not records and not meds["total"]:
        return JSONResponse({"ok": True, "empty": True, "day": day})

    lines = []
    for c in checkins:
        lines.append(
            f"- Check-in at {c['time']}: wellbeing {c['wellbeing']}/100. "
            f"{c['summary']} Concerns: {', '.join(c['concerns']) or 'none'}.")
    for r in records:
        lines.append(f"- Conversation: mood {r['mood']}. {r['summary']} "
                     f"Notable: {r['notable_points']}")
    if meds["total"]:
        lines.append(f"- Medication: {meds['taken']} of {meds['total']} doses "
                     f"taken, {meds['missed']} missed.")

    lang_line = ("Write the report in Japanese." if lang == "ja"
                 else "Write the report in English.")
    try:
        text = groq_api.chat(
            [{"role": "system", "content": REPORT_SYSTEM},
             {"role": "user", "content": f"{lang_line}\n\nDay: {day}\n"
              + "\n".join(lines)}],
            temperature=0.3, max_tokens=600)
    except groq_api.GroqError as e:
        return _err(str(e))

    return JSONResponse({"ok": True, "empty": False, "day": day, "report": text,
                         "checkins": len(checkins), "conversations": len(records),
                         "medication": meds})


@app.get("/api/export")
def api_export(days: int = 30):
    rows = [["day", "time", "resident", "wellbeing", "summary", "concerns"]]
    residents = {r["id"]: r["name"] for r in store.residents()}
    for c in store.checkins(limit=500):
        rows.append([c["day"], c["time"], residents.get(c["resident_id"], "?"),
                     c["wellbeing"], c["summary"], "; ".join(c["concerns"])])
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return Response(
        content="﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="care_records.csv"'})


def serve(host="127.0.0.1", port=8100):
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    print("Open http://127.0.0.1:8100")
    serve()
