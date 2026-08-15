# Medication Manager / 服薬管理

Upload a prescription — a photo or the text — and an AI reads it into a dose
schedule. The app then reminds you what to take and when, and tracks what was
actually taken.

Built for elderly users: large type, big buttons, English **or** Japanese.

## Run it

```bash
python run.py
```

Opens <http://127.0.0.1:8002>. Face_rec uses 8000 and voice_rec 8001, so all
three can run at once.

```bash
python run.py --check       # verify setup without starting
python run.py --port 8080   # different port
```

## Config and API key

Two separate things, on purpose:

| | Where | Why |
|---|---|---|
| **Models & settings** | `med_mgmt/config.py` | App-specific — each app needs different models |
| **API key** | `.env` at the repo root | Shared, secret, one key for everyone |

Set the key once for the whole repo:

```bash
cp .env.example .env      # at the repo root
```

```
GROQ_API_KEY=gsk_your_key_here
```

Free key: <https://console.groq.com/keys>. `config.py` reads it with a tiny
built-in parser (no `python-dotenv` dependency). Precedence: a real environment
variable beats `med_mgmt/.env`, which beats the shared root `.env`.

`.env` is gitignored; **`config.py` is committed**, since it holds no secrets —
so a teammate who clones the repo gets working settings and only needs to add
their own `.env`.

To change this app's models, edit `med_mgmt/config.py` directly, or override
per-app from `.env` with `MED_TEXT_MODEL` / `MED_VISION_MODEL`. Other apps are
unaffected either way.

The app still runs without a key — you just can't use AI reading, and the UI
says so plainly instead of failing at a confusing moment.

## Tabs

- **Today** — the day's doses, with a large "time to take" card when one is
  due, plus a beep and a browser notification. Mark **Taken**, **Skip**, or
  snooze 10 minutes. As-needed (頓服) medicines get a "log a dose" button.
- **Add Prescription** — drop in a photo or paste the text, then review.
- **My Medications** — everything saved; pause, resume, or delete.
- **History** — 14 days of adherence, plus CSV export.
- **Settings** — key status, which models are in use, notification permission,
  and a button that lists the models your key can actually reach.

## Japanese support

Japanese prescriptions are handled directly. Dosing phrases map to real clock
times:

| Japanese | Meaning | Times used |
|---|---|---|
| 朝食後 | after breakfast | 08:00 |
| 毎食後 | after every meal | 08:00, 13:00, 19:00 |
| 就寝前 | before bed | 21:00 |
| 起床時 | on waking | 07:00 |
| 食間 | between meals | 10:30, 15:30 |
| 頓服 / 頓用 | as needed | no fixed time |
| 30日分 | 30 days' supply | sets the end date |

Verified on a Japanese prescription image (処方箋 with four Rp entries): all
four extracted, with 毎食後 correctly becoming three daily doses and 頓服
correctly becoming an as-needed medicine with no scheduled time.

## How a photo is read

Photos go through **two passes**, on purpose:

1. The vision model (`qwen/qwen3.6-27b`) **transcribes** the image — that is
   all it does, and it is sent **once**.
2. The text model (`openai/gpt-oss-120b`) turns that transcription into
   the structured schedule.

Asking one vision model to do both jobs at once was measurably unreliable: on a
four-item Japanese prescription it returned two or three items across runs,
silently dropping the rest. Splitting the work fixed it — all four, every time.

The transcription is shown in the review step behind "Show the text read from
the photo", so you can see exactly what the camera picked up.

### Three settings that matter, and why

Reading a real photographed prescription went from ~13 s and an immediate rate
limit, to **2.5 s** with room for several photos a minute. Three things did it:

- **`reasoning_effort: "none"` on the vision call.** Left to think, this model
  burns thousands of tokens reasoning before it answers, and frequently never
  closes its `<think>` block at all. With reasoning off, a full prescription
  transcribes in about **250 tokens instead of thousands**.
- **A small `max_tokens` (1600).** Groq counts `max_tokens` against the
  per-minute budget as a *reservation*, not as what you actually use. A 6000
  reservation requested 6719 tokens against a free-tier limit of 8000 TPM —
  one photo consumed the entire minute.
- **No JSON mode on the transcription.** A transcription is plain text.
  Wrapping it in `json_object` only added a failure path, and that failure
  retried the whole request — re-uploading the photo. Between that and the 429
  retry, a single photo could be sent four times.

Photos are also downscaled to 1200px before sending (a 4000×3000 phone photo
becomes ~30 KB), and `<think>` blocks are stripped if a model emits them anyway.

Structured extraction still uses JSON mode, where it is reliable, and keeps a
salvage-then-retry fallback for Groq's occasional JSON validation errors.

## Nothing is saved without you

AI extraction **never** writes to the database. It produces a draft, and every
field is editable in a review screen before saving. Each medication is tagged
with the model's own confidence, and anything it was unsure about is listed so
you can check it. A medication with no usable time raises a warning rather than
being silently unschedulable.

This is deliberate. A misread dose is a real-world harm, so the confirmation
step is not optional.

## Files

| File | Purpose |
|---|---|
| `run.py` | Launcher — deps, config check, server, browser |
| `web_app.py` | FastAPI server: extraction, medications, doses, history |
| `static/index.html` | The whole front end, EN/JA |
| `extractor.py` | Prompts, two-pass photo reading, response validation |
| `groq_client.py` | Groq HTTP calls, error handling, model listing |
| `med_store.py` | SQLite: medications, dose log, schedule, adherence |
| `config.py` | This app's models and settings (reads the shared `../.env`) |

## Limits worth knowing

- **Reminders only fire while the page is open.** This is a local web app, not
  a phone app or a background service. Leave the tab open on a tablet by the
  bed, or keep the browser running. There is no SMS or push fallback.
- **Groq's free tier is rate limited** — 8000 tokens/minute on the vision
  model. That is roughly 2–3 photos back to back before you must pause about
  15 seconds. The app waits out short limits automatically and otherwise tells
  you exactly how long to wait. Typed text is far cheaper and rarely hits it.
- **Model IDs change.** If extraction fails with "model not available", open
  Settings, list the models your key can use, and update `.env`.
- **AI misreads prescriptions.** It dropped an entry in testing before the
  two-pass fix, and handwriting, glare, and creased paper all make it worse.
  Always check the draft against the original.
- This tool does not check drug interactions, does not know your allergies, and
  does not replace your doctor or pharmacist.
