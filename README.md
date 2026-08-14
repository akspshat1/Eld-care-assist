# Elder Care Assistant

*[日本語版](README.jp.md)*

An AI companion for an elderly person living alone — and a dashboard for the
people who worry about them.

It holds a spoken conversation, runs a daily condition check-in by voice, reads
mood from the face and from the *sound* of the voice, manages medication and
keeps asking until it's taken, and — the part that matters — **notices when
something is wrong and tells a real person within seconds.**

Everything runs in a browser. Everything works in English and Japanese.

**AI powered by [OrcaRouter](https://orcarouter.ai).**

```bash
pip install -r eld_care_assist/requirements.txt
cp .env.example .env          # add your API keys
python run.py
```

Opens <http://127.0.0.1:8100>.

---

## Why

An 82-year-old lives alone. Their daughter is two hours away. A carer visits
twice a week.

Between those visits, nobody knows whether they slept, whether they ate,
whether they took the tablets, or whether they've spoken to another human being
since Tuesday. The daughter finds out something was wrong when it has already
become an emergency.

This fills that gap. It talks to them every day — because they'll *talk*, even
when they won't tap through a form — and turns those conversations into
something a family member can read in thirty seconds.

---

## Three ways to use it

| Mode | Who | What they get |
|---|---|---|
| **Resident** | the elderly person | Big buttons, warm colours, no jargon. Talk, check-in, medicines. Never locked. |
| **Care team** | family, carers, nurses | Everything above plus scores, trends, alerts, the report, contacts. **PIN protected.** |
| **Hello Robo** | someone who can't or won't use a screen | No screen at all. It sits on the sideboard and listens for its name. |

The resident's own screens are *deliberately* never locked. A forgotten PIN
must never stand between someone and their medication schedule.

---

## Just say it

Say **"Hello Robo"** and it wakes up. Then:

| Say this | It does this |
|---|---|
| *"What medicine do I take today?"* | Reads out today's doses and when they're due |
| *"I've taken my tablets"* | Marks the dose taken. Nothing to press. |
| *"Let's do my check-in"* | Runs the whole daily check-in as a conversation |
| *"Call my daughter"* | Places the call to the contact named "daughter" |
| *"Call Kenji"* | Places the call to Kenji |
| *"My chest hurts"* | **Urgent alert to family, within seconds** |
| *"Help me"* | **Urgent alert to family, within seconds** |
| *"I'm feeling lonely today"* | Just talks with them |
| *"Goodnight"* | Goes back to sleep |

It falls asleep on its own after a stretch of quiet, so it's never listening
*at* someone for longer than they asked for.

---

## Features

### Daily check-in — by voice

The core routine. Six questions — **sleep, appetite, pain, energy, spirits,
loneliness** — plus "anything worrying you?".

Press **🎙 Answer by talking** and it becomes an actual conversation. It asks
one question, listens, acknowledges the answer, asks the next. No buttons, no
"press to record", no waiting for a beep, and a slow speaker never gets cut off
mid-sentence.

At the end, the answers appear filled into the form, so a carer can see — and
correct — exactly what was understood. Tapping the answers instead always
works too.

Optionally it then takes a **photo** and records the resident's **own words**.
All of it becomes:

- a **wellbeing score out of 100**
- a plain-language summary
- specific concerns
- simple, non-medical suggestions

### Companion conversation

Loneliness is the condition nobody codes for. This is a conversation with no
task attached — the AI speaks first, waits, replies, and stops talking the
instant the person starts.

Type it, tap the mic for one turn, or press **🎙 Hands-free conversation** and
simply talk.

Spoken turns are kept, so their emotional tone can be looked at later. "Save
conversation record" writes a mood / summary / notable-points note into the
handover.

### Mood from face and voice

Two things are read, both on the laptop itself:

- **The face** — neutral, happy, sad, angry, surprised, afraid, disgusted, contemptuous
- **The voice** — angry, joyful, neutral, sad, from the *tone*, not the words

The point isn't the labels. It's that **what someone says and how they sound
often disagree.** "I'm fine" in a flat, tired voice is the single most useful
signal in elderly care, and it's exactly what a text-only chatbot throws away.

### Medication

**Adding a prescription:** photograph it, or paste the text. It's read
automatically — drug, dose, times, duration — including awkward real-world
phrasing like *"twice daily for 7 days, then once daily for 3 weeks"*. Japanese
prescriptions work too.

**Taking it:** the app announces it out loud at the right time, in the chosen
language:

> *"It's time for Amlodipine, 5 milligrams. Please say 'taken' when you've had it."*

Say **"taken"** and it's recorded, without touching anything.

If there's no answer it repeats every 5 minutes, **at most 5 times**. Thirty
minutes past the due time it stops asking and marks the dose missed — because a
device that nags forever gets unplugged, and a missed dose that's quietly
recorded is more useful than one that's endlessly re-asked.

Missed doses show up on the family dashboard.

### Urgent alerts

Every conversation, in every mode, is watched for **20 kinds of trouble** as it
happens:

**Urgent** — chest pain, breathing difficulty, stroke signs, falls, head
injury, bleeding, choking, severe dizziness, severe pain, numbness, sudden
vision loss, overdose, self-harm, calls for help.

**Concern** — not eating, not sleeping, worsening pain, very low mood, fever,
vomiting.

When one fires, a message reaches a real person **within seconds** — Discord,
Slack, email, or SMS — with the resident's name, what they actually said, the
time, and how serious it is. Urgent alerts are red and ping the channel;
concerns are amber.

It doesn't cry wolf: *"my chest doesn't hurt"* and *"no, I'm not dizzy"* raise
nothing.

Alerts are always recorded and shown in the app. If no destination is set up,
the app says so plainly rather than pretending something was sent.

### Guardian mode

Always-on listening for a cry for help.

While asleep it holds on to nothing. Everything heard is checked and
**immediately discarded** — nothing stored, nothing sent, nothing logged —
unless someone calls for help, at which point the full alert goes out.

This is the answer to *"what if they fall and can't reach the tablet?"*

### Family dashboard

The thirty-second answer to *"how is mum today?"* — its own app, and a tab
inside the main one.

- **How they've been** — wellbeing over 14 days, with the alert thresholds drawn
  on the chart so you can see *why* something was flagged
- **What needs attention** — low scores, missed doses, unusual quiet
- **Timeline** — check-ins, conversations, medication and alerts in order
- **Digest** — a short written summary a family member will actually read
- **Contacts** — add family and carers with phone and email. They become both
  the people alerts go to and the people the resident can call by voice.

You choose the thresholds: what counts as a low score, how many hours of
silence is unusual, how many missed doses before someone is told.

### Handover report

The day written up under **How they have been / Worth watching / Needs
attention** — the shape a carer's shift note actually takes. Pulls in
check-ins, conversations, medication and alerts. Exports to CSV.

### It remembers

The assistant remembers across conversations — that a knee has been hurting,
that a grandson is visiting Sunday — so the resident doesn't have to
reintroduce their own life every morning.

Kept deliberately small, so it stays cheap and never drifts.

### Bilingual, all the way down

English and Japanese, switched by one toggle — and it isn't just the labels:

- the interface
- the language the AI **replies** in
- the language your speech is **transcribed** in
- spoken medicine reminders
- check-in questions and summaries
- alert messages

### Privacy and security

Health data about a vulnerable person deserves better than a demo's usual
treatment.

- **Voice recordings are encrypted** where they're stored
- **Clinical views are PIN-gated** — enforced by the server, not just hidden in
  the page, and the screen blurs behind the lock so nothing can be read through it
- **Sessions expire** after 8 hours
- **Recordings auto-delete** after 30 days by default
- **Access to health records is logged**
- **Every secret lives in one gitignored file.** Nothing in the code, nothing in git.

### Demo clock

An adjustable clock, bottom-right — type a time or nudge it by the hour.

Every timestamp, day boundary, due dose and medicine reminder follows it, so
you can demonstrate an evening medication reminder at 10am. Reset puts it back
to real time.

---

## Setup

### 1. Install

```bash
pip install -r eld_care_assist/requirements.txt
```

Python 3.10+. Use the same interpreter you'll run `run.py` with.

### 2. Add your keys

```bash
cp .env.example .env
```

`.env.example` lists everything with comments. It's gitignored, so keys are
never committed.

### 3. Download the mood models (optional)

```bash
cd Face_rec  && python download_models.py
cd voice_rec && python download_models.py
```

Without these everything else still works; the mood features just say the model
is missing.

### 4. Run

```bash
python run.py                # main app + family dashboard, opens the browser
python run.py --all          # also the three standalone apps
python run.py --only care    # just one: care|family|face|voice|meds
python run.py --check        # verify setup without starting anything
python run.py --list         # apps and ports
```

`--check` tells you exactly what's missing before anything starts.

| App | Port | Started by default |
|---|---|---|
| Elder Care Assistant | 8100 | ✅ |
| Family Dashboard | 8300 | ✅ |
| Face mood (standalone) | 8000 | `--all` |
| Voice mood (standalone) | 8001 | `--all` |
| Medication manager (standalone) | 8002 | `--all` |

---

## Configuration

All in `.env` at the repo root, shared by every app. See `.env.example` for the
full list — the ones you're most likely to want:

| Setting | Default | What it does |
|---|---|---|
| `ORCAROUTER_API_KEY` | — | Powers the AI |
| `CARE_PIN` | *unset* | PIN for the care team views. Unset = nothing locked |
| `ALERT_WEBHOOK_URL` | — | Where urgent alerts go — Discord or Slack |
| `SMTP_*` | — | Send alerts by email instead |
| `TWILIO_*` | — | Send alerts by SMS |
| `AUDIO_RETENTION_DAYS` | `30` | Delete recordings after N days (0 = keep) |
| `FAM_LOW_WELLBEING` | `40` | Score at or below this raises a concern |
| `FAM_QUIET_HOURS` | `36` | Hours of silence before the family is told |
| `FAM_MISSED_DOSES` | `2` | Missed doses in a row before the family is told |

Setting up Discord alerts takes about a minute: Server Settings → Integrations
→ Webhooks → New Webhook → Copy URL → paste into `ALERT_WEBHOOK_URL`. There's a
**Send test alert** button in the app.

---

## Layout

```
Hackathon/
├── run.py                  launches everything
├── .env.example
│
├── eld_care_assist/        ★ the main app — port 8100
├── fam_dashboard/          family dashboard — port 8300
├── Face_rec/               face mood — port 8000
├── voice_rec/              voice mood — port 8001
├── med_mgmt/               medication manager — port 8002
└── Converse_2way/          voice conversation
```

Each folder also runs on its own.

---

## Troubleshooting

**Hands-free voice doesn't hear me** — allow the microphone and check the tab
isn't muted. Click a button on the page first; browsers won't start audio
without one.

**Japanese text appears but isn't spoken** — the OS has no Japanese voice
installed. Windows: Settings → Time & Language → Speech → Manage voices → add
Japanese.

**Something's missing at startup** — run `python run.py --check`. It prints
exactly what's absent and the command to fix it.

**UI looks stale after an update** — hard-refresh with `Ctrl+F5`.

**Port already in use** — `run.py` refuses to half-start. Stop the other
process, or use `--only`.
