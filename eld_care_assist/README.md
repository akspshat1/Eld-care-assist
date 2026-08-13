# Elder Care Assistant

One app over everything in this repo: a daily condition check-in you can just
*talk* through, a hands-free companion conversation, face and voice emotion,
medication reminders, and an end-of-day handoff report — in one browser window,
English or Japanese.

```bash
python run.py
```

Opens <http://127.0.0.1:8100>.

```bash
python run.py --check       # verify setup without starting
python run.py --port 8200   # different port
```

The other apps use 8000–8002, so all of them can run alongside this one.

## What it does

**Today** — wellbeing score, last check-in, medicines taken, a 14-day trend
line, and one-tap access to everything else.

**Check-in** — the daily condition check. Press **🎙 Answer by talking** and it
holds an actual conversation: it asks about sleep, appetite, pain, energy,
spirits and loneliness, one question at a time, listening for each answer with
no buttons in between. When you stop, it reads the answers back out of the
transcript into the form so a caregiver can see and correct what it understood.
You can also just tap the answers instead — the buttons always work.

Then, optionally: a **photo** (facial expression) and the resident's **own
words**. All of it becomes a wellbeing score out of 100, a plain-language
summary, concerns, and simple non-medical suggestions.

**Talk** — a companion conversation. Type, tap the mic for one turn, or press
**🎙 Hands-free conversation** and simply talk: it listens, replies, and listens
again, and stops talking the moment you start. Spoken turns are kept so their
tone can be analysed afterwards (below). "Save conversation record" writes a
mood/summary/notable-points note for the handover.

**Medicines** — today's doses with taken/skip, overdue alerts, and adding a
prescription by photo or pasted text.

**Report** — the day's check-ins, conversations and medication record written
up under *How they have been / Worth watching / Needs attention*. CSV export.

## What it reuses

Nothing here reimplements what already worked:

| Piece | Comes from |
|---|---|
| Face emotion (YuNet + FER+, ONNX, CPU) | `../Face_rec` |
| Voice emotion (HuBERT, Japanese, 1.2 GB) | `../voice_rec` |
| Medication store + prescription reader | `../med_mgmt` |
| Hands-free voice pipeline (Pipecat, Silero VAD, WebRTC) | `../Converse_2way` |

The hands-free pipeline is imported **as-is** from Converse_2way; only two
hooks are redirected (`handsfree.py`), so turns land in this app's database and
the companion uses this app's persona prompt. Both the Talk tab and the spoken
check-in run on that one pipeline — the check-in just swaps in an interviewer
prompt.

## Voice emotion on conversations

Spoken turns are saved as WAV under `data/audio/<conversation_id>/`, linked to
their message. **Analyse voice tone** then runs the voice-emotion model over
them and reports the dominant tone across the conversation.

This is deliberately on demand rather than during the chat: the model is 1.2 GB
and takes seconds per clip, which would make talking feel sluggish. Doing it
afterwards also means one complete WAV per turn, which is what the model wants.

**This is the one place audio is written to disk.** Check-in photos are
analysed in memory and discarded; nothing else is stored but labels, text and
timestamps.

## Setup

The Groq API key comes from the shared `.env` at the repo root:

```
GROQ_API_KEY=gsk_your_key_here
```

Models are chosen in this app's own `config.py` (override per-app from `.env`
with `ECA_TEXT_MODEL`, `ECA_VISION_MODEL`, `ECA_WHISPER_MODEL`).

The app starts without a key or without the optional models — it says which
pieces are unavailable instead of failing at a confusing moment:

```
Groq key   : found
Face model : ready
Voice model: ready
Medicines  : ready
```

Hands-free needs `pip install "pipecat-ai[webrtc,groq,silero]"`, and the
microphone needs `localhost` or HTTPS (a browser rule, not ours).

## Two things that will bite you

**Japanese speech needs a Japanese voice installed.** `speechSynthesis` fails
*silently* when no voice matches the language — text appears, nothing is
spoken. Either install one (Settings → Time & language → 日本語 → Speech) or
open the app in Microsoft Edge, which provides online Japanese voices.

**The voice-emotion model is Japanese.** It is XLSR → Japanese ASR → JTES
(Japanese acted emotion), so on English speech it returns confident but
unvalidated answers — in testing it labelled calm English speech as sadness.
Trust it for Japanese; treat English tone readings as decorative.

## Honest limits

- **This is not diagnosis.** The check-in reports what the resident said and
  what the models observed, and flags things for a human. The prompts forbid
  naming conditions or giving medical or medication advice.
- **Urgent symptoms are caught by a hard-coded rule, not the model** — chest
  pain, breathlessness, a fall, dizziness raise the alert even if the API is
  down, rate limited, or wrong. That was deliberate: safety should not depend
  on a network call.
- **A face reading from one photo is weak evidence**, and the wellbeing score
  weights it at only 25% against what the person actually told you.
- **If the summary model fails, the check-in still saves** — the score and any
  red flags are computed locally, and a plain summary is composed from the
  answers. Losing a resident's answers to an API error would be unacceptable.
- Groq's free tier is rate limited; short waits are retried automatically.

## Files

| File | Purpose |
|---|---|
| `run.py` | Launcher — deps, feature check, server, browser |
| `server.py` | FastAPI: check-in, conversation, medicines, report |
| `checkin.py` | Questions, scoring, red flags, interview + extraction prompts |
| `handsfree.py` | Bridge to Converse_2way's Pipecat pipeline |
| `engines.py` | Lazy loaders for the sibling apps' models and stores |
| `groq_api.py` | Chat, JSON chat, vision, Whisper, rate-limit handling |
| `store.py` | SQLite: residents, check-ins, conversations, saved audio |
| `static/` | The whole front end (`app.js`, `webrtc.js`, `voice.js`) |
