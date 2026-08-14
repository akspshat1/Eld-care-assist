"""SQLite storage for check-ins, conversations and daily records.

Privacy: check-in photos are analysed in memory and never written to disk.
Spoken conversation turns ARE kept, so their tone can be analysed later --
those recordings are encrypted at rest (see security.py) and deleted after the
retention period. Everything else stored is text: labels, transcripts and
timestamps.
"""

import os
import json
import sqlite3
import threading
from datetime import datetime, date, timedelta

import config
import security

SCHEMA = """
CREATE TABLE IF NOT EXISTS residents (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    personality TEXT,
    topics     TEXT,
    created_ts REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS checkins (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    resident_id  INTEGER NOT NULL,
    ts           REAL NOT NULL,
    day          TEXT NOT NULL,
    answers      TEXT NOT NULL,        -- JSON {question_id: value}
    face_emotion TEXT,
    face_conf    REAL,
    voice_emotion TEXT,
    voice_conf   REAL,
    transcript   TEXT,
    wellbeing    INTEGER,              -- 0-100
    summary      TEXT,
    concerns     TEXT,                 -- JSON list
    suggestions  TEXT                  -- JSON list
);
CREATE INDEX IF NOT EXISTS idx_checkin_day ON checkins(day);

CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    resident_id INTEGER NOT NULL,
    started_ts  REAL NOT NULL,
    day         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    ts              REAL NOT NULL,
    -- Spoken turns keep their audio on disk so voice emotion can be run over
    -- them later, on demand, rather than at recording time.
    audio_path      TEXT,
    voice_emotion   TEXT,
    voice_conf      REAL,
    voice_valence   REAL,
    analyzed_ts     REAL
);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id);

-- People the resident can ask to call, and who can be notified. Kept in this
-- shared database so the conversation feature and the family dashboard both
-- see the same list.
CREATE TABLE IF NOT EXISTS contacts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    resident_id  INTEGER,
    name         TEXT NOT NULL,
    relationship TEXT,
    phone        TEXT NOT NULL,
    email        TEXT,
    is_primary   INTEGER NOT NULL DEFAULT 0,
    notes        TEXT,
    created_ts   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contact_res ON contacts(resident_id);

CREATE TABLE IF NOT EXISTS call_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id  INTEGER NOT NULL,
    resident_id INTEGER,
    ts          REAL NOT NULL,
    day         TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'conversation'
);

-- Urgent alerts, and what actually happened to them. Kept even when nothing
-- could be delivered, so the record shows whether anyone was really told.
-- Who did what to the record. Health data should never be silently readable
-- or exportable without a trace.
CREATE TABLE IF NOT EXISTS audit (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      REAL NOT NULL,
    day     TEXT NOT NULL,
    action  TEXT NOT NULL,
    detail  TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_day ON audit(day);

CREATE TABLE IF NOT EXISTS alerts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    resident_id   INTEGER NOT NULL,
    ts            REAL NOT NULL,
    day           TEXT NOT NULL,
    kind          TEXT NOT NULL,
    label         TEXT NOT NULL,
    quote         TEXT,
    source        TEXT NOT NULL,         -- checkin | conversation
    subject       TEXT,
    body          TEXT,
    contact_count INTEGER NOT NULL DEFAULT 0,
    delivery      TEXT,                  -- what each channel reported
    acknowledged  INTEGER NOT NULL DEFAULT 0,
    ack_ts        REAL
);
CREATE INDEX IF NOT EXISTS idx_alert_day ON alerts(day);

CREATE TABLE IF NOT EXISTS conv_records (
    conversation_id INTEGER PRIMARY KEY,
    day             TEXT NOT NULL,
    mood            TEXT,
    summary         TEXT,
    notable_points  TEXT,
    ts              REAL NOT NULL
);
"""

DEFAULT_RESIDENTS = [
    ("Hanako Tanaka", "Cheerful and sociable; enjoys telling stories about the past.",
     "gardening, old songs, grandchildren"),
    ("Makoto Sato", "Quiet and thoughtful; prefers listening to talking.",
     "baseball, fishing, the news"),
]


def _dict(row):
    return dict(row) if row is not None else None


AUDIO_DIR = os.path.join(config.DATA_DIR, "audio")

# Columns added after the first release; existing databases get them here.
_MIGRATIONS = [
    ("messages", "audio_path", "TEXT"),
    ("messages", "voice_emotion", "TEXT"),
    ("messages", "voice_conf", "REAL"),
    ("messages", "voice_valence", "REAL"),
    ("messages", "analyzed_ts", "REAL"),
]


class Store:
    def __init__(self, db_path=None):
        db_path = db_path or config.DB_PATH
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        os.makedirs(AUDIO_DIR, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._migrate()
        self._conn.commit()
        self._seed()

    def _migrate(self):
        """Add any missing columns, so an older data/care.db keeps working."""
        for table, column, coltype in _MIGRATIONS:
            cols = {r["name"] for r in
                    self._conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if column not in cols:
                self._conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")

    def save_audio_pcm(self, conversation_id, message_id, pcm, sample_rate,
                       channels=1, sample_width=2):
        """Save raw 16-bit PCM as a WAV and attach it to a message.

        The hands-free pipeline hands over bare PCM, not a container, so the
        header is written here -- the voice-emotion model needs a real file.
        """
        import wave
        import io as _io

        buf = _io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(channels)
            w.setsampwidth(sample_width)
            w.setframerate(sample_rate or 16000)
            w.writeframes(pcm)
        return self.save_audio(conversation_id, message_id, buf.getvalue())

    def last_message_id(self, conversation_id, role="user"):
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM messages WHERE conversation_id=? AND role=?"
                " ORDER BY id DESC LIMIT 1", (conversation_id, role)).fetchone()
        return row["id"] if row else None

    def save_audio(self, conversation_id, message_id, audio_bytes, ext="wav"):
        """Write a spoken turn to disk and attach it to its message."""
        folder = os.path.join(AUDIO_DIR, str(conversation_id))
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{message_id}.{ext}")
        # Encrypted at rest: a recording of someone's voice is the most
        # sensitive thing this app keeps.
        with open(path, "wb") as fh:
            fh.write(security.encrypt_bytes(audio_bytes))
        with self._lock:
            self._conn.execute("UPDATE messages SET audio_path=? WHERE id=?",
                               (path, message_id))
            self._conn.commit()
        return path

    def _seed(self):
        with self._lock:
            n = self._conn.execute("SELECT COUNT(*) FROM residents").fetchone()[0]
            if n:
                return
            for name, personality, topics in DEFAULT_RESIDENTS:
                self._conn.execute(
                    "INSERT INTO residents (name, personality, topics, created_ts)"
                    " VALUES (?,?,?,?)",
                    (name, personality, topics, datetime.now().timestamp()))
            self._conn.commit()

    # ------------------------------------------------------------ people --
    def residents(self):
        with self._lock:
            return [_dict(r) for r in
                    self._conn.execute("SELECT * FROM residents ORDER BY id").fetchall()]

    def resident(self, rid):
        with self._lock:
            return _dict(self._conn.execute(
                "SELECT * FROM residents WHERE id=?", (rid,)).fetchone())

    def add_resident(self, name, personality="", topics=""):
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO residents (name, personality, topics, created_ts)"
                " VALUES (?,?,?,?)",
                (name, personality, topics, datetime.now().timestamp()))
            self._conn.commit()
            return cur.lastrowid

    # ---------------------------------------------------------- check-ins --
    def add_checkin(self, resident_id, answers, face, voice, transcript, result):
        ts = datetime.now().timestamp()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO checkins (resident_id, ts, day, answers, face_emotion,"
                " face_conf, voice_emotion, voice_conf, transcript, wellbeing,"
                " summary, concerns, suggestions)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (resident_id, ts, datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                 json.dumps(answers, ensure_ascii=False),
                 (face or {}).get("emotion"), (face or {}).get("confidence"),
                 (voice or {}).get("emotion"), (voice or {}).get("confidence"),
                 transcript,
                 result.get("wellbeing"), result.get("summary"),
                 json.dumps(result.get("concerns") or [], ensure_ascii=False),
                 json.dumps(result.get("suggestions") or [], ensure_ascii=False)))
            self._conn.commit()
            return cur.lastrowid

    def checkins(self, day=None, resident_id=None, limit=60):
        q = "SELECT * FROM checkins WHERE 1=1"
        args = []
        if day:
            q += " AND day=?"
            args.append(day)
        if resident_id:
            q += " AND resident_id=?"
            args.append(resident_id)
        q += " ORDER BY ts DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = [_dict(r) for r in self._conn.execute(q, args).fetchall()]
        for r in rows:
            r["answers"] = json.loads(r["answers"] or "{}")
            r["concerns"] = json.loads(r["concerns"] or "[]")
            r["suggestions"] = json.loads(r["suggestions"] or "[]")
            r["time"] = datetime.fromtimestamp(r["ts"]).strftime("%H:%M")
        return rows

    def latest_checkin(self, resident_id):
        rows = self.checkins(resident_id=resident_id, limit=1)
        return rows[0] if rows else None

    def checkin_trend(self, resident_id, days=14):
        """One wellbeing score per day, oldest first, for the trend line."""
        start = (date.today() - timedelta(days=days - 1)).isoformat()
        with self._lock:
            rows = self._conn.execute(
                "SELECT day, AVG(wellbeing) AS score, COUNT(*) AS n FROM checkins"
                " WHERE resident_id=? AND day>=? AND wellbeing IS NOT NULL"
                " GROUP BY day ORDER BY day", (resident_id, start)).fetchall()
        return [{"day": r["day"], "score": round(r["score"]), "count": r["n"]}
                for r in rows]

    # ------------------------------------------------------ conversations --
    def start_conversation(self, resident_id):
        ts = datetime.now().timestamp()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO conversations (resident_id, started_ts, day)"
                " VALUES (?,?,?)",
                (resident_id, ts, datetime.fromtimestamp(ts).strftime("%Y-%m-%d")))
            self._conn.commit()
            return cur.lastrowid

    def conversation(self, cid):
        with self._lock:
            return _dict(self._conn.execute(
                "SELECT * FROM conversations WHERE id=?", (cid,)).fetchone())

    def add_message(self, conversation_id, role, content, audio_path=None):
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO messages (conversation_id, role, content, ts,"
                " audio_path) VALUES (?,?,?,?,?)",
                (conversation_id, role, content, datetime.now().timestamp(),
                 audio_path))
            self._conn.commit()
            return cur.lastrowid

    def messages(self, conversation_id):
        with self._lock:
            rows = [_dict(r) for r in self._conn.execute(
                "SELECT id, role, content, ts, audio_path, voice_emotion,"
                " voice_conf, voice_valence FROM messages"
                " WHERE conversation_id=? ORDER BY id",
                (conversation_id,)).fetchall()]
        for r in rows:
            # The path is internal; the UI only needs to know audio exists.
            r["has_audio"] = bool(r.pop("audio_path", None))
        return rows

    def messages_with_audio(self, conversation_id=None, only_unanalyzed=True):
        """Spoken turns that still have their audio file on disk."""
        q = ("SELECT id, conversation_id, content, audio_path, voice_emotion"
             " FROM messages WHERE audio_path IS NOT NULL")
        args = []
        if conversation_id is not None:
            q += " AND conversation_id=?"
            args.append(conversation_id)
        if only_unanalyzed:
            q += " AND voice_emotion IS NULL"
        q += " ORDER BY id"
        with self._lock:
            return [_dict(r) for r in self._conn.execute(q, args).fetchall()]

    def set_message_voice(self, message_id, emotion, confidence, valence):
        with self._lock:
            self._conn.execute(
                "UPDATE messages SET voice_emotion=?, voice_conf=?,"
                " voice_valence=?, analyzed_ts=? WHERE id=?",
                (emotion, confidence, valence, datetime.now().timestamp(),
                 message_id))
            self._conn.commit()

    def conversation_voice_summary(self, conversation_id):
        """Average tone across the analysed spoken turns of one conversation."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT voice_emotion, voice_valence FROM messages"
                " WHERE conversation_id=? AND voice_emotion IS NOT NULL",
                (conversation_id,)).fetchall()
        if not rows:
            return None
        counts = {}
        for r in rows:
            counts[r["voice_emotion"]] = counts.get(r["voice_emotion"], 0) + 1
        valences = [r["voice_valence"] for r in rows if r["voice_valence"] is not None]
        return {
            "analyzed": len(rows),
            "dominant": max(counts, key=counts.get),
            "counts": counts,
            "mean_valence": round(sum(valences) / len(valences), 3) if valences else None,
        }

    def save_conv_record(self, conversation_id, day, mood, summary, notable):
        with self._lock:
            self._conn.execute(
                "INSERT INTO conv_records (conversation_id, day, mood, summary,"
                " notable_points, ts) VALUES (?,?,?,?,?,?)"
                " ON CONFLICT(conversation_id) DO UPDATE SET"
                " mood=excluded.mood, summary=excluded.summary,"
                " notable_points=excluded.notable_points, ts=excluded.ts",
                (conversation_id, day, mood, summary, notable,
                 datetime.now().timestamp()))
            self._conn.commit()

    def conv_records(self, day):
        with self._lock:
            rows = self._conn.execute(
                "SELECT r.*, c.resident_id FROM conv_records r"
                " JOIN conversations c ON c.id = r.conversation_id"
                " WHERE r.day=? ORDER BY r.ts", (day,)).fetchall()
        return [_dict(r) for r in rows]

    # --------------------------------------------------------------- audit --
    def audit(self, action, detail=""):
        ts = datetime.now().timestamp()
        with self._lock:
            self._conn.execute(
                "INSERT INTO audit (ts, day, action, detail) VALUES (?,?,?,?)",
                (ts, datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                 action, str(detail)[:300]))
            self._conn.commit()

    def audit_log(self, limit=50):
        with self._lock:
            rows = [_dict(r) for r in self._conn.execute(
                "SELECT * FROM audit ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()]
        for r in rows:
            r["time"] = datetime.fromtimestamp(r["ts"]).strftime("%H:%M")
        return rows

    # -------------------------------------------------------------- alerts --
    def now_string(self):
        """Current time as text -- follows the demo clock when one is set."""
        return datetime.now().strftime("%Y-%m-%d %H:%M")

    def add_alert(self, resident_id, kind, label, quote, source,
                  subject="", body="", contact_count=0):
        ts = datetime.now().timestamp()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO alerts (resident_id, ts, day, kind, label, quote,"
                " source, subject, body, contact_count)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (resident_id, ts,
                 datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                 kind, label, quote, source, subject, body, contact_count))
            self._conn.commit()
            return cur.lastrowid

    def set_alert_delivery(self, alert_id, delivery):
        with self._lock:
            self._conn.execute("UPDATE alerts SET delivery=? WHERE id=?",
                               (delivery, alert_id))
            self._conn.commit()

    def acknowledge_alert(self, alert_id):
        with self._lock:
            self._conn.execute(
                "UPDATE alerts SET acknowledged=1, ack_ts=? WHERE id=?",
                (datetime.now().timestamp(), alert_id))
            self._conn.commit()

    def alerts(self, resident_id=None, limit=20, unacknowledged_only=False):
        q = "SELECT * FROM alerts WHERE 1=1"
        args = []
        if resident_id:
            q += " AND resident_id=?"
            args.append(resident_id)
        if unacknowledged_only:
            q += " AND acknowledged=0"
        q += " ORDER BY ts DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = [_dict(r) for r in self._conn.execute(q, args).fetchall()]
        for r in rows:
            r["time"] = datetime.fromtimestamp(r["ts"]).strftime("%H:%M")
            r["acknowledged"] = bool(r["acknowledged"])
        return rows

    # ------------------------------------------------------------ contacts --
    def contacts(self, resident_id=None):
        """Contacts for this resident, plus any shared ones (resident_id NULL)."""
        if resident_id is None:
            q, args = "SELECT * FROM contacts", []
        else:
            q = "SELECT * FROM contacts WHERE resident_id=? OR resident_id IS NULL"
            args = [resident_id]
        q += " ORDER BY is_primary DESC, name"
        with self._lock:
            return [_dict(r) for r in self._conn.execute(q, args).fetchall()]

    def contact(self, cid):
        with self._lock:
            return _dict(self._conn.execute(
                "SELECT * FROM contacts WHERE id=?", (cid,)).fetchone())

    def add_contact(self, name, phone, relationship="", resident_id=None,
                    email="", is_primary=False, notes=""):
        # Adding the same person twice would page them twice and clutter the
        # alert; update the existing entry instead.
        for c in self.contacts(resident_id):
            same_phone = (c.get("phone") or "").strip() == (phone or "").strip()
            same_name = (c.get("name") or "").lower() == (name or "").lower()
            if same_phone or same_name:
                self.update_contact(c["id"], {
                    "name": name, "phone": phone,
                    "relationship": relationship or c.get("relationship"),
                    "email": email or c.get("email"),
                    "is_primary": is_primary or c.get("is_primary"),
                })
                return c["id"]

        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO contacts (resident_id, name, relationship, phone,"
                " email, is_primary, notes, created_ts) VALUES (?,?,?,?,?,?,?,?)",
                (resident_id, name, relationship, phone, email,
                 1 if is_primary else 0, notes, datetime.now().timestamp()))
            self._conn.commit()
            return cur.lastrowid

    def update_contact(self, cid, fields):
        allowed = ("name", "relationship", "phone", "email", "is_primary",
                   "notes", "resident_id")
        sets, vals = [], []
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k == "is_primary":
                v = 1 if v else 0
            sets.append(f"{k}=?")
            vals.append(v)
        if not sets:
            return False
        vals.append(cid)
        with self._lock:
            self._conn.execute(
                f"UPDATE contacts SET {', '.join(sets)} WHERE id=?", vals)
            self._conn.commit()
        return True

    def delete_contact(self, cid):
        with self._lock:
            self._conn.execute("DELETE FROM contacts WHERE id=?", (cid,))
            self._conn.commit()

    def log_call(self, contact_id, resident_id=None, source="conversation"):
        ts = datetime.now().timestamp()
        with self._lock:
            self._conn.execute(
                "INSERT INTO call_log (contact_id, resident_id, ts, day, source)"
                " VALUES (?,?,?,?,?)",
                (contact_id, resident_id, ts,
                 datetime.fromtimestamp(ts).strftime("%Y-%m-%d"), source))
            self._conn.commit()

    def recent_calls(self, resident_id=None, limit=20):
        q = ("SELECT l.*, c.name, c.relationship, c.phone FROM call_log l"
             " JOIN contacts c ON c.id = l.contact_id")
        args = []
        if resident_id:
            q += " WHERE l.resident_id=?"
            args.append(resident_id)
        q += " ORDER BY l.ts DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = [_dict(r) for r in self._conn.execute(q, args).fetchall()]
        for r in rows:
            r["time"] = datetime.fromtimestamp(r["ts"]).strftime("%H:%M")
        return rows

    def close(self):
        with self._lock:
            self._conn.close()
