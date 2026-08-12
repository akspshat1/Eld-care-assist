# Elderly Mood Monitor

Face emotion recognition in your browser, tracking an elderly person's mood
through the day. Runs entirely on CPU — no GPU, no cloud, no account.

Measured: **17 ms/frame (~59 fps)** at 640×480.

## Run it

```bash
python run.py
```

That checks dependencies, downloads the models on first run, starts the server
and opens your browser at <http://127.0.0.1:8000>.

```bash
python run.py --check       # verify setup without starting
python run.py --port 8080   # different port
```

> Use Python on your own OS (PowerShell on Windows). Running it through WSL
> bash uses a separate Linux Python that has none of the packages installed,
> and cannot reach your webcam.

## Tabs

- **Live Monitor** — webcam view with the face boxed, current mood in large
  text, Start/Stop. Logs a reading every 5 seconds (adjustable).
- **Upload Photo** — drag in a JPG/PNG to analyse a single photo, with a
  confidence breakdown. Optionally record the result in today's log.
- **Today** — mood through the day, wellbeing score out of 100, dominant mood,
  and a check-in alert on sustained distress.
- **History** — any previous day, plus CSV export.

## Models (pretrained, downloaded — nothing is trained here)

| Job | Model | Size | Speed |
|---|---|---|---|
| Face detection | YuNet (OpenCV Zoo) | 232 KB | ~20 ms |
| Emotion | FER+ (ONNX Model Zoo) | 35 MB | ~4 ms |

FER+ returns 8 emotions: neutral, happiness, surprise, sadness, anger,
disgust, fear, contempt. Verified against the FER+ reference test tensors —
output matches bit-for-bit (max abs diff 0.0).

## How the daily numbers work

Each emotion carries a **valence** from −1 (distressed) to +1 (content):
happiness +1.0, surprise +0.2, neutral 0.0, contempt −0.4, disgust −0.7,
sadness/fear −0.8, anger −0.9.

- **Wellbeing score** = `50 + 50 × mean valence`, so 50 is emotionally neutral.
- **Check-in alert** fires when negative emotions exceed 40% of the last 30
  minutes, and only after at least 12 readings — one frown never triggers it.

Live readings are smoothed with an exponential moving average, so a single
blurred or mid-blink frame cannot flip the logged mood.

## Privacy

Only emotion labels and timestamps are written to disk (`data/mood_log.db`).
**No images or video are ever saved**, uploaded photos are analysed in memory
and discarded, and nothing leaves this computer.

## Files

| File | Purpose |
|---|---|
| `run.py` | Launcher — deps, models, server, browser |
| `web_app.py` | FastAPI server: video stream, JSON API, photo upload |
| `static/index.html` | The whole front end |
| `emotion_engine.py` | Face detection + emotion classification |
| `mood_store.py` | SQLite logging, daily summaries, alerts, CSV |
| `charts.py` | Chart rendering |
| `download_models.py` | Fetches the two models |

## Honest limits

Facial-expression models read *expressions*, not feelings. Accuracy drops with
poor lighting, side angles, glasses, and faces much older than the training set
(FER+ skews younger). Treat the trend across a day as the signal — not any
single reading — and use it to prompt a human check-in, never as a clinical
judgement.
