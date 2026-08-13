# Family Dashboard

For the grandson who wants to know how grandma is doing without phoning the
care home. One page: how she is today, what needs attention, and the numbers to
call.

```bash
python run.py
```

Opens <http://127.0.0.1:8300>.

```bash
python run.py --check       # verify setup without starting
python run.py --port 8400   # different port
```

Ports across the repo: Face_rec 8000, voice_rec 8001, med_mgmt 8002,
eld_care_assist 8100, this 8300 — all can run at once.

## What it shows

**How they are** — a wellbeing ring with a plain-English verdict ("Doing well",
"A bit low"), when they last checked in, a written update in a sentence or two,
and a 14-day bar chart so a slow decline is visible at a glance.

**Needs your attention** — the short list, or a green "Nothing needs your
attention right now." Alerts are raised for:

| Alert | When |
|---|---|
| 🚨 Symptom | A check-in reported chest pain, breathlessness, a fall or dizziness |
| ⚠ Wellbeing | Last check-in scored under 40/100 |
| ⚠ Trend | The week's average has drifted down by more than 15 points |
| ⚠ Quiet | No check-in for 36 hours |
| 🚨/⚠ Medication | Doses missed today |

Thresholds are in `config.py` (`FAM_LOW_WELLBEING`, `FAM_QUIET_HOURS`,
`FAM_MISSED_DOSES`) and can be overridden from `.env`.

**History** — day by day: wellbeing, check-ins, medicines taken/missed, notes.
CSV export.

**Contacts** — names, relationships and numbers, with a 📞 Call button that
opens the phone's dialler. Calls started from here or from a conversation are
logged so the family can see when someone last spoke to her.

## Contacts and "call my grandson"

Contacts are stored in **eld_care_assist's** database, not a separate one, so
the resident's conversation app sees the same list. During a conversation she
can simply say:

> "I'd like to call my grandson."
> "Can you ring Kenji for me?"

and the app offers a big green **Call now** button.

Matching is done on names *and* relationships, locally first (instant, works
offline), falling back to the model only for indirect phrasing. It is
deliberately conservative — tested to fire on "call my grandson" and "ring
Kenji", and *not* on "I miss Kenji so much" or "no need to call anyone".

**The app never dials by itself.** It hands the browser a `tel:` link and a
person taps it. On a phone or tablet that opens the dialler with the number
ready; on a desktop it opens whatever handles `tel:`, which may be nothing.
There is no telephony provider wired in — adding Twilio or similar would be the
next step if you want calls placed from the app itself.

## Where the data comes from

This app is a reader. It opens the databases where they already live, so it is
never stale and nothing is duplicated:

| Data | Source |
|---|---|
| Check-ins, mood, conversations, contacts | `../eld_care_assist/data/care.db` |
| Medication schedule and dose log | `../med_mgmt/data/medications.db` |

It only writes contacts and the call log. If a database is missing the
dashboard still loads and says which app to run first.

## Setup

The written update uses Groq, from the shared `.env` at the repo root:

```
GROQ_API_KEY=gsk_your_key_here
```

Everything else — scores, alerts, history, contacts — works without a key. The
update section simply stays empty.

## Honest limits

- **Nothing here is a diagnosis.** It summarises check-ins the resident did
  themselves plus the medication record. Mood readings from a photo or voice
  are weak signals shown as observations.
- **Alerts are computed from thresholds, not judgement.** A quiet day can look
  like a bad one, and a genuinely bad day can pass under them. Treat the
  dashboard as a prompt to phone, not a verdict.
- **"Missed" medication means not marked as taken.** If nobody presses the
  button, doses show as missed whether or not they were swallowed.
- The dashboard reads local files, so it only works on the machine (or network
  share) holding them. There is no cloud sync.

## Files

| File | Purpose |
|---|---|
| `run.py` | Launcher — deps, source check, server, browser |
| `server.py` | FastAPI: overview, timeline, contacts, digest, export |
| `sources.py` | Reads the care and medication databases; builds the alerts |
| `config.py` | Paths, thresholds, shared `.env` |
| `static/` | The dashboard front end |
