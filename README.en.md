*[日本語](README.md)*

# Conversation × Automated Care-Record AI for Elder Care Facilities

An app where an AI chatbot converses with residents and automatically turns
the conversation into care records and handoff reports for the next
caregiver.

## Features

1. **Conversation** — Chat with a resident persona via text or voice input.
   Each conversation's mood, summary, and notable points are extracted by
   the AI and saved to the DB.
2. **Handoff report generation** — Aggregates a day's conversation logs into
   a report for the next caregiver.
3. **Voice Reminders** — Offline text-to-speech voice reminders for
   medication, hydration, exercise, etc.

## Tech stack

- Python 3.11+ / Streamlit
- LLM: GroqCloud API (`groq` SDK, model: `llama-3.3-70b-versatile`)
- Speech-to-text: GroqCloud Whisper API (`whisper-large-v3-turbo`) via
  `st.audio_input`
- DB: SQLite (`sqlite3`)
- Text-to-speech: pyttsx3 (offline)
- Reminder scheduling: `schedule`

The LLM, TTS, and DB are each called through a thin wrapper under `core/`,
so swapping any of them later does not require touching feature code.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# open .env and set GROQ_API_KEY
```

## Run

```bash
streamlit run app.py
```

On startup, the app shows whether the DB tables were created and whether
`GROQ_API_KEY` was loaded successfully.

## Directory structure

```
Eld-care-assist/
├── app.py                       # Streamlit entry point (setup check)
├── config.py                    # .env loading and shared settings
├── core/                        # Swappable tech-stack foundation
│   ├── database.py                # SQLite connection, tables, CRUD
│   ├── llm_client.py               # LLM (Groq) call wrapper
│   └── tts_client.py                # TTS (pyttsx3) call wrapper
├── features/                    # Feature logic (UI-independent)
│   ├── conversation.py             # Persona prompt building + AI replies
│   ├── extraction.py                # Mood/summary/notable-points extraction
│   ├── report.py                     # Handoff report generation
│   └── reminders.py                   # Reminder scheduling
├── personas/personas.json       # Resident persona definitions
├── pages/                       # Streamlit pages, one per feature
│   ├── 1_会話.py                     (Conversation)
│   ├── 2_申し送りレポート.py           (Handoff report)
│   └── 3_リマインダー.py               (Reminders)
└── data/                        # SQLite DB file (not committed to Git)
```

## Development steps (all implemented)

1. Scaffolding (directory layout, requirements.txt, .env handling, SQLite
   table design)
2. Conversation feature (chat UI + DB storage)
3. Automatic extraction from conversation logs (mood, summary, notable
   points)
4. Handoff report generation
5. Voice Reminders
