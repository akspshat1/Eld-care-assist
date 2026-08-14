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
import sys
import csv
import json
from datetime import datetime, date

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import config
import democlock
import groq_api
import orca_router_api
import engines
import handsfree
import family
import calls
import alerts
import memory
import security
import voicemode
import checkin as checkin_mod
from store import Store

HERE = os.path.dirname(os.path.abspath(__file__))

# How many past turns are resent with each reply.
MAX_TURNS_REPLAYED = 12

app = FastAPI(title="Elder Care Assistant")
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")),
          name="static")
store = Store()

# Demo clock: make the whole app's idea of "now" adjustable, so medicine
# reminders and day boundaries can be triggered on demand. With no offset set
# (the default) nothing behaves differently.
def _install_demo_clock():
    import store as _store_mod
    modules = [_store_mod, sys.modules[__name__]]
    try:
        engines.get_med_store()               # puts med_mgmt on sys.path
        import med_store
        modules.append(med_store)             # so "due now" follows the clock
    except Exception:                         # noqa: BLE001 - med app optional
        pass
    democlock.patch(*modules)


_install_demo_clock()


def _locked(request):
    """True when the care-team views should be refused.

    The resident's own screens never call this. Reading the token from a
    header rather than a cookie keeps it out of anything the browser sends
    automatically.
    """
    if not security.pin_required():
        return False
    return not security.valid_session(request.headers.get("X-Care-Token", ""))


def _locked_response():
    return JSONResponse({"ok": False, "locked": True,
                         "message": "Enter the care team PIN to view this."},
                        status_code=401)


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
        "handsfree_note": None if st["handsfree"] else
        (f'Hands-free voice needs pipecat. Install it into THIS interpreter:\n'
         f'    "{sys.executable}" -m pip install "pipecat-ai[webrtc,groq,silero]"'),
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
        store, lambda r, l: checkin_mod.interview_prompt(r, l),
        alert_fn=lambda cid, text: _urgent_alert(cid, text, lang))

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

    # The check-in's own red flags reach a person the same way a spoken one
    # does -- one alert path, whichever way the symptom was reported.
    alert = None
    if result.get("urgent"):
        resident = store.resident(resident_id)
        if resident:
            label = (result["concerns"] or ["an urgent symptom"])[0]
            quote = transcript or label
            alert = alerts.raise_alert(store, resident, answers.get("urgent", "urgent"),
                                       label, quote, "checkin", lang)
    return JSONResponse({"ok": True, "id": cid, "alert": alert, **result})


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
    # In a voice call the companion speaks first, so it needs to know how to
    # open without waiting to be prompted.
    opening = ("会話の最初はあなたから、短いあいさつと、"
               "答えやすい一言の質問で始めてください。\n" if lang == "ja"
               else "If you are speaking first, open with a short warm greeting "
                    "and one easy question. One or two sentences.\n")
    prompt = base + opening + (("日本語で返答してください。\n" + length_ja)
                               if lang == "ja"
                               else ("Reply in English.\n" + length_en))

    # What happened over the last few days, so the companion picks up where it
    # left off instead of meeting them afresh every time.
    recalled = memory.build(store, resident["id"], lang)
    if recalled:
        prompt += "\n\n" + recalled
    return prompt


def _reply(conversation_id, content, lang, audio_bytes=None):
    conv = store.conversation(conversation_id)
    if conv is None:
        return None, "Conversation not found.", None
    resident = store.resident(conv["resident_id"])
    if resident is None:
        return None, "Resident not found.", None

    msg_id = store.add_message(conversation_id, "user", content)
    if audio_bytes:
        # Keep the recording so voice emotion can be run over it later.
        store.save_audio(conversation_id, msg_id, audio_bytes)

    # An urgent symptom mentioned in passing is the whole point of listening.
    # Raise it before the reply is generated, so help is on its way even if
    # the language model call then fails.
    urgent = alerts.detect_urgent(content, lang)
    alert = None
    if urgent:
        alert = alerts.raise_alert(store, resident, urgent["kind"],
                                   urgent["label"], urgent["quote"],
                                   "conversation", lang,
                                   urgent.get("severity", "urgent"))

    system = _system_prompt(resident, lang)
    if urgent:
        # Tell the companion what just happened so it responds like a person
        # would, instead of carrying on about the weather.
        system += ("\n\nIMPORTANT: they have just mentioned "
                   f"{urgent['label']}. Respond warmly and calmly, take it "
                   "seriously, tell them you are letting a caregiver know "
                   "right now, and ask them to stay where they are. Do not "
                   "diagnose and do not give medical advice. Keep it to two "
                   "short sentences.")

    msgs = [{"role": "system", "content": system}]
    # Only the recent turns: a long chat would otherwise resend itself in full
    # on every reply, and older detail is already covered by memory.
    for m in store.messages(conversation_id)[-MAX_TURNS_REPLAYED:]:
        msgs.append({"role": m["role"], "content": m["content"]})

    try:
        reply = groq_api.chat(msgs, temperature=0.7, max_tokens=300)
    except groq_api.GroqError as e:
        return None, str(e), alert

    store.add_message(conversation_id, "assistant", reply)
    return reply, None, alert


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


def _urgent_alert(cid, said, lang):
    """Detect an urgent symptom in a spoken turn and raise the alert.

    Used by the hands-free paths, which do not go through _reply().
    """
    urgent = alerts.detect_urgent(said, lang)
    if not urgent:
        return None
    conv = store.conversation(cid)
    if conv is None:
        return None
    resident = store.resident(conv["resident_id"])
    if resident is None:
        return None
    return alerts.raise_alert(store, resident, urgent["kind"], urgent["label"],
                              urgent["quote"], "conversation", lang,
                              urgent.get("severity", "urgent"))


def _call_offer(cid, said, lang):
    """If the resident asked to phone someone, describe the call to offer."""
    conv = store.conversation(cid)
    if conv is None:
        return None
    contact = calls.detect(said, store.contacts(conv["resident_id"]))
    if not contact:
        return None
    return {
        "contact_id": contact["id"],
        "name": contact["name"],
        "relationship": contact.get("relationship") or "",
        "phone": contact["phone"],
        "tel": calls.tel_link(contact["phone"]),
        "say": calls.offer_text(contact, lang),
    }


@app.post("/api/conversation/{cid}/say")
async def api_conv_say(cid: int, request: Request):
    body = await request.json()
    content = (body.get("content") or "").strip()
    if not content:
        return _err("Nothing to send.")
    lang = body.get("lang", "en")
    reply, err, alert = _reply(cid, content, lang)
    if err:
        return _err(err)
    return JSONResponse({"ok": True, "reply": reply,
                         "call": _call_offer(cid, content, lang),
                         "alert": alert})


@app.post("/api/calls/{contact_id}/log")
def api_log_call(contact_id: int, resident_id: int | None = None):
    """Record that a call was started, for the family dashboard."""
    if store.contact(contact_id) is None:
        return _err("Unknown contact.")
    store.log_call(contact_id, resident_id, "conversation")
    return JSONResponse({"ok": True})


@app.get("/api/contacts")
def api_contacts(resident_id: int | None = None):
    return JSONResponse({"contacts": store.contacts(resident_id)})


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
    reply, err, alert = _reply(cid, text, lang, audio_bytes=bytes(raw))
    if err:
        return _err(err)
    return JSONResponse({"ok": True, "transcript": text, "reply": reply,
                         "audio_saved": True,
                         "call": _call_offer(cid, text, lang),
                         "alert": alert})


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

    handsfree.install_hooks(
        store, _system_prompt,
        call_offer_fn=lambda cid, text: _call_offer(cid, text, lang),
        alert_fn=lambda cid, text: _urgent_alert(cid, text, lang))

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
            # Recordings are encrypted on disk; decrypt in memory only.
            with open(path, "rb") as fh:
                raw_audio = security.decrypt_bytes(fh.read())
            wav = vm.load_audio(raw_audio)
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
        data = orca_router_api.chat_json(EXTRACT_SYSTEM, f"{lang_line}\n\n{text}")
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


"""Words that confirm a dose was taken, or clearly refuse it.

Matched locally first: the resident is standing there waiting, and a network
round-trip to decide "yes" is both slow and needless.
"""
_TAKEN_WORDS = ["taken", "took", "i have", "ive taken", "yes", "yeah", "yep",
                "done", "swallowed", "already", "finished",
                "飲んだ", "飲みました", "のんだ", "はい", "はい飲みました", "済んだ"]
_NOT_TAKEN_WORDS = ["not yet", "no", "haven't", "havent", "later", "in a minute",
                    "wait", "まだ", "いいえ", "あとで", "後で"]


@app.post("/api/medications/confirm_voice")
async def api_meds_confirm_voice(request: Request, med_id: int = 0,
                                 day: str = "", slot: str = "",
                                 lang: str = "en"):
    """Decide from a spoken reply whether a dose was taken, and mark it.

    Returns taken=True only on a clear yes. Anything ambiguous leaves the dose
    pending and the reminder keeps going -- silently marking a medicine as
    taken because someone mumbled would be the worst possible failure here.
    """
    raw = await request.body()
    if not raw:
        return _err("No audio received.")
    if not med_id or not day or not slot:
        return _err("Missing dose details.")

    try:
        text = groq_api.transcribe(bytes(raw), "reply.wav", lang)
    except groq_api.GroqError as e:
        return _err(str(e))

    said = (text or "").lower().strip()
    if not said:
        return JSONResponse({"ok": True, "transcript": "", "taken": False,
                             "unclear": True})

    refused = any(w in said for w in _NOT_TAKEN_WORDS)
    confirmed = (not refused) and any(w in said for w in _TAKEN_WORDS)

    if not confirmed and not refused:
        # Indirect phrasing ("that's done", "I've had it") -- ask the model.
        try:
            data = groq_api.chat_json(
                "Decide whether the person is saying they HAVE taken their "
                "medicine. Answer true only if they clearly confirm taking it. "
                'Return ONLY this JSON: {"taken": true or false}',
                f'They said: "{text}"', max_tokens=60)
            confirmed = bool(data.get("taken"))
        except Exception:                     # noqa: BLE001
            confirmed = False

    if confirmed:
        engines.get_med_store().mark(med_id, day, slot, "taken")

    return JSONResponse({"ok": True, "transcript": text, "taken": confirmed,
                         "unclear": not confirmed})


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
def api_report(request: Request, day: str = "", resident_id: int | None = None, lang: str = "en"):
    if _locked(request):
        return _locked_response()
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
        text = orca_router_api.chat(
            [{"role": "system", "content": REPORT_SYSTEM},
             {"role": "user", "content": f"{lang_line}\n\nDay: {day}\n"
              + "\n".join(lines)}],
            temperature=0.3, max_tokens=600)
    except groq_api.GroqError as e:
        return _err(str(e))

    return JSONResponse({"ok": True, "empty": False, "day": day, "report": text,
                         "checkins": len(checkins), "conversations": len(records),
                         "medication": meds})


# --------------------------------------------------------------- family ---

@app.get("/api/family/overview")
def api_family_overview(request: Request, resident_id: int, days: int = 14):
    if _locked(request):
        return _locked_response()
    try:
        data = family.overview(store, engines.get_med_store, resident_id, days)
    except Exception as e:                    # noqa: BLE001
        return _err(str(e), 500)
    if data is None:
        return _err("Unknown resident.", 404)
    return JSONResponse({"ok": True, **data})


@app.get("/api/family/timeline")
def api_family_timeline(request: Request, resident_id: int, days: int = 14):
    if _locked(request):
        return _locked_response()
    try:
        return JSONResponse({"ok": True, "days": family.timeline(
            store, engines.get_med_store, resident_id, days)})
    except Exception as e:                    # noqa: BLE001
        return _err(str(e), 500)


@app.get("/api/family/digest")
def api_family_digest(resident_id: int, lang: str = "en"):
    if not (orca_router_api.ready() or groq_api.ready()):
        return _err(groq_api.missing_key_message())
    try:
        data = family.overview(store, engines.get_med_store, resident_id)
        if data is None:
            return _err("Unknown resident.", 404)
        return JSONResponse({"ok": True, "digest": family.digest(data, lang)})
    except groq_api.GroqError as e:
        return _err(str(e))
    except Exception as e:                    # noqa: BLE001
        return _err(str(e), 500)


@app.post("/api/contacts")
async def api_add_contact(request: Request):
    body = await request.json()
    name = (body.get("name") or "").strip()
    phone = (body.get("phone") or "").strip()
    if not name:
        return _err("A name is required.")
    if not phone:
        return _err("A phone number is required.")
    cid = store.add_contact(
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
    return JSONResponse({"ok": store.update_contact(contact_id, body)})


@app.delete("/api/contacts/{contact_id}")
def api_delete_contact(contact_id: int):
    store.delete_contact(contact_id)
    return JSONResponse({"ok": True})


@app.post("/api/voice/say")
async def api_voice_say(request: Request, resident_id: int = 0,
                        lang: str = "en", awake: int = 0,
                        conversation_id: int = 0):
    """One utterance heard by always-on voice mode.

    Handles both states in one place so the browser only has to record and
    play: while asleep it listens for the wake word and for a cry for help;
    once awake it answers, and routes spoken commands to the same code the
    screens use.
    """
    raw = await request.body()
    if not raw or not resident_id:
        return _err("Nothing heard.")
    resident = store.resident(resident_id)
    if resident is None:
        return _err("Unknown resident.")

    try:
        heard = groq_api.transcribe(bytes(raw), "voice.wav", lang)
    except groq_api.GroqError as e:
        return JSONResponse({"ok": False, "message": str(e), "awake": bool(awake)})

    heard = (heard or "").strip()
    out = {"ok": True, "heard": heard, "awake": bool(awake), "alert": None,
           "say": "", "action": None, "conversation_id": conversation_id}
    if not heard:
        return JSONResponse(out)

    # An emergency is handled in either state, before anything else.
    urgent = alerts.detect_urgent(heard, lang)
    if urgent:
        out["alert"] = alerts.raise_alert(
            store, resident, urgent["kind"], urgent["label"], urgent["quote"],
            "guardian" if not awake else "conversation", lang,
            urgent.get("severity", "urgent"))
        store.audit("voice_alert", f"{urgent['label']}: {heard[:80]}")
        out["awake"] = True
        out["say"] = ("すぐに介護者にお伝えしました。そのままお待ちください。"
                      if lang == "ja" else
                      "I've told a caregiver right away. Please stay where you are.")
        return JSONResponse(out)

    # Asleep: only the wake word does anything.
    if not awake:
        if not voicemode.is_wake(heard):
            return JSONResponse(out)          # heard, checked, discarded
        out["awake"] = True
        remainder = voicemode.strip_wake(heard)
        if not remainder:
            out["say"] = voicemode.greeting(resident["name"].split()[0], lang)
            return JSONResponse(out)
        heard = remainder                     # "Hello Robo, call my son"

    if voicemode.is_sleep(heard):
        out["awake"] = False
        out["say"] = voicemode.going_to_sleep(lang)
        return JSONResponse(out)

    intent = voicemode.classify(heard)
    out["intent"] = intent

    if intent == "call":
        contact = calls.detect(heard, store.contacts(resident_id))
        if contact:
            out["action"] = {"type": "call", "contact_id": contact["id"],
                             "name": contact["name"],
                             "phone": contact["phone"],
                             "tel": calls.tel_link(contact["phone"])}
            out["say"] = calls.offer_text(contact, lang)
            return JSONResponse(out)

    if intent in ("medicine_query", "medicine_taken"):
        ms = engines.get_med_store()
        summary = ms.day_summary(date.today().isoformat())
        summary["due"] = ms.due_now()
        summary["next"] = ms.next_dose()
        if intent == "medicine_taken" and summary["due"]:
            d = summary["due"][0]
            ms.mark(d["med_id"], d["day"], d["slot"], "taken")
            out["say"] = voicemode.confirm_taken(d["name"], lang)
            out["action"] = {"type": "medicine_taken", "name": d["name"]}
        else:
            out["say"] = voicemode.say_medicines(summary, lang)
            out["action"] = {"type": "medicine_info"}
        return JSONResponse(out)

    if intent == "checkin":
        out["action"] = {"type": "start_checkin"}
        out["say"] = ("体調をお伺いします。昨夜はよく眠れましたか？" if lang == "ja"
                      else "Let's do your check-in. How did you sleep last night?")
        return JSONResponse(out)

    if intent == "status":
        latest = store.latest_checkin(resident_id)
        if latest and latest.get("summary"):
            out["say"] = latest["summary"]
        else:
            out["say"] = ("まだ今日の記録がありません。" if lang == "ja"
                          else "I don't have a check-in for you yet today.")
        return JSONResponse(out)

    # Ordinary conversation, with the same companion prompt the screens use.
    cid = conversation_id or store.start_conversation(resident_id)
    out["conversation_id"] = cid
    reply, err, _alert = _reply(cid, heard, lang)
    out["say"] = reply or (err or "")
    return JSONResponse(out)


@app.post("/api/guardian/listen")
async def api_guardian_listen(request: Request, resident_id: int = 0,
                              lang: str = "en"):
    """One overheard utterance from the room.

    Guardian mode is the case nobody plans for: someone on the floor who
    cannot reach a button. The browser sends only speech (its VAD gates
    silence), this transcribes it, and *only* an urgent phrase raises an alert.

    Nothing is written to disk. Ordinary conversation is transcribed in memory,
    checked, and dropped -- a room monitor that quietly recorded everything
    would be indefensible in someone's home.
    """
    raw = await request.body()
    if not raw or not resident_id:
        return _err("Nothing to check.")

    try:
        text = groq_api.transcribe(bytes(raw), "room.wav", lang)
    except groq_api.GroqError as e:
        # Never surface a rate limit as a false all-clear.
        return JSONResponse({"ok": False, "heard": "", "message": str(e)})

    said = (text or "").strip()
    if not said:
        return JSONResponse({"ok": True, "heard": "", "alert": None})

    urgent = alerts.detect_urgent(said, lang)
    if not urgent:
        # Heard, checked, discarded.
        return JSONResponse({"ok": True, "heard": said, "alert": None})

    resident = store.resident(resident_id)
    if resident is None:
        return _err("Unknown resident.")
    alert = alerts.raise_alert(store, resident, urgent["kind"], urgent["label"],
                               urgent["quote"], "guardian", lang,
                               urgent.get("severity", "urgent"))
    store.audit("guardian_alert", f"{urgent['label']}: {said[:80]}")
    return JSONResponse({"ok": True, "heard": said, "alert": alert})


@app.get("/api/security")
def api_security():
    return JSONResponse({"ok": True, **security.status()})


@app.post("/api/security/unlock")
async def api_unlock(request: Request):
    body = await request.json()
    if not security.pin_required():
        return JSONResponse({"ok": True, "token": "", "pin_required": False})
    if not security.check_pin(body.get("pin", "")):
        store.audit("unlock_failed", "wrong PIN")
        return _err("That PIN is not right.", 401)
    token = security.new_session()
    store.audit("unlock", "care view unlocked")
    return JSONResponse({"ok": True, "token": token, "pin_required": True})


@app.post("/api/security/lock")
async def api_lock(request: Request):
    security.end_session(request.headers.get("X-Care-Token", ""))
    store.audit("lock", "care view locked")
    return JSONResponse({"ok": True})


@app.get("/api/security/audit")
def api_audit(request: Request, limit: int = 40):
    if _locked(request):
        return _locked_response()
    return JSONResponse({"ok": True, "entries": store.audit_log(limit)})


@app.get("/api/alerts")
def api_alerts(resident_id: int | None = None, limit: int = 20):
    return JSONResponse({"ok": True,
                         "alerts": store.alerts(resident_id, limit),
                         "channels": alerts.channels_configured()})


@app.post("/api/alerts/{alert_id}/ack")
def api_ack_alert(alert_id: int):
    store.acknowledge_alert(alert_id)
    return JSONResponse({"ok": True})


@app.post("/api/alerts/test")
async def api_test_alert(request: Request):
    """Send a test alert, to prove the delivery path works before it matters."""
    body = await request.json()
    resident = store.resident(body.get("resident_id"))
    if resident is None:
        return _err("Pick a resident first.")
    lang = body.get("lang", "en")
    alert = alerts.raise_alert(
        store, resident, "test",
        "a test alert" if lang != "ja" else "テスト通知",
        "This is a test of the alert system." if lang != "ja"
        else "これは通知テストです。",
        "checkin", lang)
    return JSONResponse({"ok": True, "alert": alert})


@app.get("/api/demo/clock")
def api_demo_clock_get():
    return JSONResponse({"ok": True, **democlock.state()})


@app.post("/api/demo/clock")
async def api_demo_clock_set(request: Request):
    """Move the demo clock. Everything time-based follows it."""
    body = await request.json()
    if body.get("reset"):
        democlock.reset()
    elif "shift_seconds" in body:
        democlock.shift(body["shift_seconds"])
    elif "time" in body:
        try:
            hh, mm = str(body["time"]).split(":")[:2]
            democlock.set_time(int(hh), int(mm))
        except (ValueError, TypeError):
            return _err("Time must look like HH:MM.")
    else:
        return _err("Nothing to change.")
    return JSONResponse({"ok": True, **democlock.state()})


@app.get("/api/export")
def api_export(request: Request, days: int = 30):
    if _locked(request):
        return _locked_response()
    store.audit("export", f"CSV export, {days} days")
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
