# 音声感情モニター / Voice Mood Monitor

Speech emotion recognition for **elderly Japanese speakers**, tracking mood
through the day. Runs in your browser, on CPU, entirely offline once the model
is downloaded.

Companion to the face monitor in `../Face_rec` — same four tabs, same wellbeing
score, same privacy stance.

## Run it

```bash
python run.py
```

Checks dependencies, downloads the model on first run (~1.2 GB), starts the
server and opens <http://127.0.0.1:8001>.

```bash
python run.py --check       # verify setup without starting
python run.py --port 8080   # different port
```

Both apps can run at once — the face monitor uses port 8000, this one 8001.

## Tabs

- **Live Recording** — press one big button to record, watch the level meter,
  play the recording back, and get the result. Each recording is logged.
- **Upload Audio** — drop in a WAV/MP3/FLAC/OGG file.
- **Today** — mood through the day, wellbeing score, check-in alert.
- **History** — any previous day, plus CSV export (UTF-8 with BOM, so Excel on
  a Japanese system opens it correctly).

## Language

The interface is **English by default**, with an **EN / 日本語** toggle in the
top right. The choice is remembered between visits.

Switching to Japanese translates everything — tabs, buttons, results, alerts,
and the chart axis and emotion labels, which are re-rendered server-side using
an installed Japanese font (Yu Gothic / Meiryo / MS Gothic). If no such font is
present, charts fall back to English labels rather than printing empty boxes.

Emotion names always show both languages on the result (喜び *joy*), so a
Japanese-speaking resident and an English-speaking caregiver can read the same
screen.

## Model

| | |
|---|---|
| Model | `Bagus/wav2vec2-xlsr-japanese-speech-emotion-recognition` |
| Architecture | HuBERT-large (24 layers, 1024 hidden) |
| Training data | **JTES** — Japanese Twitter Emotional Speech |
| Labels | 怒り (ang) / 喜び (joy) / 中立 (neu) / 悲しみ (sad) |
| Input | 16 kHz mono; audio is resampled automatically |

Chosen specifically because it is fine-tuned on **Japanese** speech. Most
speech-emotion models are English-only (IEMOCAP/RAVDESS) and transfer poorly.

## How the daily numbers work

Each emotion carries a **valence** from −1 to +1: 喜び +1.0, 中立 0.0,
悲しみ −0.8, 怒り −0.9 — the same scale the face monitor uses, so the two
scores mean the same thing.

- **気分スコア (wellbeing)** = `50 + 50 × mean valence`; 50 is neutral.
- **Check-in alert** fires when negative emotions exceed 40% of the last 60
  minutes, and only after at least 6 readings. The window is wider than the
  face monitor's because voice readings arrive far less often.

Long recordings are split into 4-second windows, each logged as its own
reading, so one conversation contributes a small trend rather than one point.

**Silence is never logged.** Clips shorter than 0.6 s or quieter than an RMS
threshold return "音声が検出されませんでした" and write nothing — an empty room
must not become a mood reading.

## Privacy

Only emotion labels and timestamps are written to disk (`data/voice_log.db`).
**No audio is ever saved.** Recording happens in the browser, the clip is sent
to the local server in memory, analysed and discarded. Nothing leaves the
machine.

## Files

| File | Purpose |
|---|---|
| `run.py` | Launcher — deps, model, server, browser |
| `web_app.py` | FastAPI server: analysis, JSON API, CSV |
| `static/index.html` | The whole front end, EN/JA |
| `voice_engine.py` | Model loading, windowing, silence gate |
| `mood_store.py` | SQLite logging, daily summaries, alerts |
| `charts.py` | Chart rendering (uses a Japanese font when present) |
| `download_models.py` | Fetches the model |

## A bug worth knowing about

The published `config.json` declares `HubertForSequenceClassification`, but the
weights are a **wav2vec2** backbone plus a custom two-layer head
(`classifier.dense` 1024→1024, `classifier.out_proj` 1024→4) from the common
SER training scripts — not any stock transformers class.

Loading it the obvious way, with `AutoModelForAudioClassification`, **silently
discards the trained head and initialises a random one.** It does not crash; it
just returns ~25% on all four classes forever, which is exactly chance. This
was caught by checking whether predictions varied across clips with different
prosody — they moved by 3–6 points, i.e. noise.

`voice_engine.py` therefore rebuilds the architecture by hand and loads the
weights directly, and **raises** if the head fails to land. After the fix the
same clips separate by 30–60 points with confident predictions.

If you swap in a different model, keep that check. A silent chance-level
classifier is far more dangerous here than a loud error.

## Honest limits

**Read this before trusting the numbers.**

The model card reports `eval_accuracy: 1.0`. That figure is not meaningful:
its `eval_samples` (34,560) is identical to its `train_samples`, so it was
evaluated on its own training data. Treat the true accuracy as unknown and
considerably lower.

**It is a Japanese model.** The chain is XLSR-53 (multilingual) →
`wav2vec2-large-xlsr-japanese-hiragana` (Japanese ASR) → JTES (Japanese
emotion), so it is specialised toward Japanese twice over. It will run on
English audio and return confident answers, but those answers are not
validated — in local testing on English speech it labelled nearly everything
悲しみ/怒り, including cheerful content. Use a model trained for the language
you actually need.

Beyond that:

- **JTES is acted speech**, recorded by voice actors reading emotional
  sentences. Spontaneous speech from an elderly person in their home is a
  different distribution, and older voices (breathier, slower, narrower pitch
  range) are underrepresented in most corpora.
- **Four emotions is coarse.** Real mood does not partition into
  怒り/喜び/中立/悲しみ, and anything outside those four is forced into one.
- **Prosody is not feeling.** The model hears loudness, pitch and rhythm. A
  hard-of-hearing person speaking loudly can read as 怒り; a tired flat voice
  can read as 悲しみ.

Use the **trend across many readings** to prompt a human check-in. Never treat
a single clip, or the daily score alone, as a clinical judgement.
