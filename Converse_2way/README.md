*[日本語](README.jp.md)*

# Conversation × Automated Care-Record AI for Elder Care Facilities

An app where an AI chatbot converses with residents and automatically turns
the conversation into care records and handoff reports for the next
caregiver.

## Features

1. **Conversation** — Chat with a resident persona via text, recorded voice
   input, or a hands-free, button-free voice call (Next.js UI only). Each
   conversation's mood, summary, and notable points are extracted by the AI
   and saved to the DB.
2. **Handoff report generation** — Aggregates a day's conversation logs into
   a report for the next caregiver.
3. **Voice Reminders** — Voice reminders for medication, hydration, exercise,
   etc.

## UI options

There are two frontends, sharing the same SQLite DB and Python backend logic:

- **Next.js** (`web/`) + **FastAPI** (`api/`) — the primary UI. Voice input
  (mic recording) and voice output (spoken replies / reminders) run in the
  browser, so it works even when the frontend and backend are on different
  machines. The conversation page also has a hands-free voice call mode
  (WebRTC, no button presses per turn) built on Pipecat.
- **Streamlit** (`app.py`, `pages/`) — kept as a simpler single-process
  fallback. Voice output here uses offline TTS (pyttsx3) running on the same
  machine as the server.

## Tech stack

- Python 3.11+ backend logic, shared by both UIs
- LLM: GroqCloud API (`groq` SDK, model: `openai/gpt-oss-120b`)
- Speech-to-text: GroqCloud Whisper API (`whisper-large-v3-turbo`)
- DB: [ChromaDB](https://www.trychroma.com/) (`chromadb`, local persistent
  client), chosen so conversation history can later be used for RAG-style
  semantic search
- Text-to-speech (Streamlit only): pyttsx3 (offline)
- Reminder scheduling (Streamlit only): `schedule`
- API: FastAPI + uvicorn
- Frontend: Next.js (TypeScript, App Router, Tailwind CSS), using the
  browser's `MediaRecorder` for mic input and `speechSynthesis` for voice
  output
- Hands-free voice call (Next.js only): [Pipecat](https://github.com/pipecat-ai/pipecat)
  (`pipecat-ai`), using its `SmallWebRTCTransport` for a direct
  browser↔backend WebRTC connection (no third-party cloud account needed),
  Silero VAD for turn detection, and Groq for both STT and the LLM reply —
  no separate TTS provider; the finalized text is sent to the browser over
  the WebRTC data channel and spoken there with `speechSynthesis`, same as
  the rest of the app

The LLM, TTS, and DB are each called through a thin wrapper under `core/`,
so swapping any of them later does not require touching feature code.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# open .env and set GROQ_API_KEY

cd web
npm install
cp .env.local.example .env.local
# edit NEXT_PUBLIC_API_BASE_URL if the backend runs on a different host
```

## Run

**Next.js + FastAPI** (primary):

```bash
# terminal 1, from the project root
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# terminal 2
cd web
npm run dev
```

Open `http://localhost:3000`. If the frontend is opened from a non-localhost
address, browsers block microphone access (recorded voice input and the
hands-free voice call both need it) unless the page is served over HTTPS
(voice output via `speechSynthesis` is unaffected). The hands-free call is
also plain peer-to-peer WebRTC, so it needs the frontend and backend to be
reachable on the same network (no TURN server is set up for NAT traversal
across separate networks).

On its first use, the hands-free call downloads the Silero VAD model
(small, local, one-time). The DB (ChromaDB) also downloads a local
embedding model (~80MB, one-time) the first time the app starts.

**Streamlit** (fallback):

```bash
streamlit run app.py
```

## Directory structure

```
Eld-care-assist/
├── app.py                       # Streamlit entry point (setup check)
├── config.py                    # .env loading and shared settings
├── core/                        # Swappable tech-stack foundation
│   ├── database.py                # ChromaDB collections, CRUD
│   ├── llm_client.py               # LLM (Groq) + Whisper call wrapper
│   ├── tts_client.py                # TTS (pyttsx3) call wrapper, Streamlit only
│   └── voice_pipeline.py            # Pipecat hands-free voice call pipeline
├── features/                    # Feature logic (UI-independent)
│   ├── conversation.py             # Persona prompt building + AI replies
│   ├── extraction.py                # Mood/summary/notable-points extraction
│   ├── report.py                     # Handoff report generation
│   └── reminders.py                   # Reminder scheduling, Streamlit only
├── personas/personas.json       # Resident persona definitions
├── api/                          # FastAPI backend for the Next.js frontend
│   └── main.py
├── web/                          # Next.js frontend
│   ├── lib/api.ts                  # fetch helpers
│   ├── lib/webrtc.ts                # Hands-free call: WebRTC signaling + data channel
│   └── app/
│       ├── conversation/page.tsx
│       ├── reports/page.tsx
│       └── reminders/page.tsx
├── pages/                       # Streamlit pages, one per feature
│   ├── 1_会話.py                     (Conversation)
│   ├── 2_申し送りレポート.py           (Handoff report)
│   └── 3_リマインダー.py               (Reminders)
└── data/                        # ChromaDB persistent store (not committed to Git)
```

## Development steps (all implemented)

1. Scaffolding (directory layout, requirements.txt, .env handling, SQLite
   table design)
2. Conversation feature (chat UI + DB storage)
3. Automatic extraction from conversation logs (mood, summary, notable
   points)
4. Handoff report generation
5. Voice Reminders
6. Voice input (Groq Whisper) and new-persona creation, added to the
   Streamlit UI
7. Next.js + FastAPI UI, added alongside Streamlit: conversation (text +
   voice input, spoken replies), handoff reports, and polling-based voice
   reminders
8. Hands-free voice call for the conversation feature (Pipecat +
   `SmallWebRTCTransport`, Groq STT/LLM, browser `speechSynthesis` for
   output over a WebRTC data channel), added alongside the existing
   text/recorded-voice flow
9. Migrated the DB from SQLite to ChromaDB (`core/database.py` rewritten,
   same public function signatures — no other file needed to change),
   to prepare for future RAG-style search over conversation history
