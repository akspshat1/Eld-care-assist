"""SQLite storage + daily aggregation for voice mood readings.

Privacy by design: only emotion labels and timestamps are written to disk.
No audio is ever saved.
"""

import os
import csv
import sqlite3
import threading
from datetime import datetime, timedelta

from voice_engine import EMOTIONS, VALENCE, NEGATIVE, label_ja, label_en

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "voice_log.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS voice_samples (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         REAL NOT NULL,
    day        TEXT NOT NULL,
    emotion    TEXT NOT NULL,
    confidence REAL NOT NULL,
    valence    REAL NOT NULL,
    source     TEXT NOT NULL DEFAULT 'live',
    person     TEXT NOT NULL DEFAULT 'resident'
);
CREATE INDEX IF NOT EXISTS idx_day    ON voice_samples(day);
CREATE INDEX IF NOT EXISTS idx_day_ts ON voice_samples(day, ts);
"""


class MoodStore:
    def __init__(self, db_path=DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def log(self, emotion, confidence, valence, source="live",
            person="resident", ts=None):
        ts = ts or datetime.now().timestamp()
        day = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        with self._lock:
            self._conn.execute(
                "INSERT INTO voice_samples (ts, day, emotion, confidence, valence,"
                " source, person) VALUES (?,?,?,?,?,?,?)",
                (ts, day, emotion, float(confidence), float(valence), source, person),
            )
            self._conn.commit()

    def days(self):
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT day FROM voice_samples ORDER BY day DESC").fetchall()
        return [r[0] for r in rows]

    def samples(self, day):
        with self._lock:
            return self._conn.execute(
                "SELECT ts, emotion, confidence, valence, source FROM voice_samples"
                " WHERE day=? ORDER BY ts", (day,)).fetchall()

    def recent(self, minutes=60):
        cutoff = (datetime.now() - timedelta(minutes=minutes)).timestamp()
        with self._lock:
            return self._conn.execute(
                "SELECT ts, emotion, confidence, valence, source FROM voice_samples"
                " WHERE ts>=? ORDER BY ts", (cutoff,)).fetchall()

    def summary(self, day):
        rows = self.samples(day)
        if not rows:
            return None

        counts = {e: 0 for e in EMOTIONS}
        for _, emotion, _, _, _ in rows:
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
            "dominant_ja": label_ja(dominant),
            "dominant_en": label_en(dominant),
            "mean_valence": mean_valence,
            "wellbeing": round(50 + 50 * mean_valence),
            "negative_pct": 100.0 * negative / n,
            "first_seen": datetime.fromtimestamp(rows[0][0]).strftime("%H:%M"),
            "last_seen": datetime.fromtimestamp(rows[-1][0]).strftime("%H:%M"),
            "rows": rows,
        }

    def check_alert(self, minutes=60, threshold_pct=40.0, min_samples=6):
        """Sustained-distress check.

        Voice readings arrive far less often than camera frames, so the window
        is wider and the sample floor lower than in the face monitor -- but it
        still refuses to speak up on one or two clips.
        """
        rows = self.recent(minutes)
        if len(rows) < min_samples:
            return None
        negative = sum(1 for r in rows if r[1] in NEGATIVE)
        pct = 100.0 * negative / len(rows)
        if pct < threshold_pct:
            return None
        worst = {}
        for _, emotion, _, _, _ in rows:
            if emotion in NEGATIVE:
                worst[emotion] = worst.get(emotion, 0) + 1
        top = max(worst, key=worst.get)
        return {
            "pct": pct,
            "minutes": minutes,
            "emotion": top,
            "message_ja": (f"過去{minutes}分のうち{pct:.0f}%が「{label_ja(top)}」でした。"
                           f"様子を確認してください。"),
            "message_en": (f"{label_en(top)} in {pct:.0f}% of the last {minutes} "
                           f"minutes - may be worth checking in."),
        }

    def export_csv_rows(self, day):
        rows = self.samples(day)
        out = [["timestamp", "time", "emotion", "emotion_ja", "confidence",
                "valence", "source"]]
        for ts, emotion, conf, val, source in rows:
            out.append([
                f"{ts:.3f}",
                datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"),
                emotion, label_ja(emotion), f"{conf:.2f}", f"{val:.4f}", source,
            ])
        return out

    def export_csv(self, day, path):
        rows = self.export_csv_rows(day)
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            csv.writer(fh).writerows(rows)
        return len(rows) - 1

    def close(self):
        with self._lock:
            self._conn.close()
