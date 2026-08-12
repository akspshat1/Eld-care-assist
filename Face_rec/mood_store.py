"""SQLite storage + daily aggregation for mood readings.

Privacy by design: only emotion labels and timestamps are ever written
to disk. No images, no video, no face embeddings.
"""

import os
import csv
import sqlite3
import threading
from datetime import datetime, timedelta

from emotion_engine import EMOTIONS, VALENCE, NEGATIVE

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "mood_log.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS mood_samples (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         REAL NOT NULL,
    day        TEXT NOT NULL,
    emotion    TEXT NOT NULL,
    confidence REAL NOT NULL,
    valence    REAL NOT NULL,
    person     TEXT NOT NULL DEFAULT 'resident'
);
CREATE INDEX IF NOT EXISTS idx_day    ON mood_samples(day);
CREATE INDEX IF NOT EXISTS idx_day_ts ON mood_samples(day, ts);
"""


class MoodStore:
    def __init__(self, db_path=DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def log(self, emotion, confidence, valence, person="resident", ts=None):
        ts = ts or datetime.now().timestamp()
        day = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        with self._lock:
            self._conn.execute(
                "INSERT INTO mood_samples (ts, day, emotion, confidence, valence, person)"
                " VALUES (?,?,?,?,?,?)",
                (ts, day, emotion, float(confidence), float(valence), person),
            )
            self._conn.commit()

    def days(self):
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT day FROM mood_samples ORDER BY day DESC"
            ).fetchall()
        return [r[0] for r in rows]

    def samples(self, day):
        with self._lock:
            return self._conn.execute(
                "SELECT ts, emotion, confidence, valence FROM mood_samples"
                " WHERE day=? ORDER BY ts", (day,)
            ).fetchall()

    def recent(self, minutes=30):
        cutoff = (datetime.now() - timedelta(minutes=minutes)).timestamp()
        with self._lock:
            return self._conn.execute(
                "SELECT ts, emotion, confidence, valence FROM mood_samples"
                " WHERE ts>=? ORDER BY ts", (cutoff,)
            ).fetchall()

    def summary(self, day):
        """Everything the dashboard needs for one day."""
        rows = self.samples(day)
        if not rows:
            return None

        counts = {e: 0 for e in EMOTIONS}
        for _, emotion, _, _ in rows:
            counts[emotion] = counts.get(emotion, 0) + 1

        n = len(rows)
        mean_valence = sum(r[3] for r in rows) / n
        negative = sum(1 for r in rows if r[1] in NEGATIVE)
        dominant = max(counts, key=counts.get)

        return {
            "day": day,
            "samples": n,
            "counts": counts,
            "dominant": dominant,
            "mean_valence": mean_valence,
            # 0-100, where 50 is emotionally neutral.
            "wellbeing": round(50 + 50 * mean_valence),
            "negative_pct": 100.0 * negative / n,
            "first_seen": datetime.fromtimestamp(rows[0][0]).strftime("%H:%M"),
            "last_seen": datetime.fromtimestamp(rows[-1][0]).strftime("%H:%M"),
            "rows": rows,
        }

    def check_alert(self, minutes=30, threshold_pct=40.0, min_samples=12):
        """Sustained-distress check for the caregiver banner.

        Deliberately conservative: needs enough samples over a real window
        before it says anything, so a single frown never raises an alert.
        """
        rows = self.recent(minutes)
        if len(rows) < min_samples:
            return None
        negative = sum(1 for r in rows if r[1] in NEGATIVE)
        pct = 100.0 * negative / len(rows)
        if pct < threshold_pct:
            return None
        worst = {}
        for _, emotion, _, _ in rows:
            if emotion in NEGATIVE:
                worst[emotion] = worst.get(emotion, 0) + 1
        top = max(worst, key=worst.get)
        return {
            "pct": pct,
            "minutes": minutes,
            "emotion": top,
            "message": (
                f"Mostly {top} for {pct:.0f}% of the last {minutes} minutes "
                f"- may be worth checking in."
            ),
        }

    def export_csv(self, day, path):
        rows = self.samples(day)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["timestamp", "time", "emotion", "confidence", "valence"])
            for ts, emotion, conf, val in rows:
                w.writerow([
                    f"{ts:.3f}",
                    datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"),
                    emotion, f"{conf:.4f}", f"{val:.4f}",
                ])
        return len(rows)

    def close(self):
        with self._lock:
            self._conn.close()
