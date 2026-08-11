"""SQLite access layer.

All raw SQL lives here so feature modules never talk to sqlite3 directly.
Swapping SQLite for another database later only requires changing this file.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

from config import DB_PATH

# Table design:
# - residents: the persona (elderly resident) definitions
# - conversations: one row per conversation session with a resident
# - messages: every single utterance (user or assistant) inside a conversation
# - extractions: AI-extracted mood / summary / notable points for a conversation
# - reminders: scheduled voice reminders per resident
SCHEMA = """
CREATE TABLE IF NOT EXISTS residents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    personality TEXT,
    favorite_topics TEXT
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resident_id INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    FOREIGN KEY (resident_id) REFERENCES residents(id)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    mood TEXT,
    summary TEXT,
    notable_points TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resident_id INTEGER NOT NULL,
    time TEXT NOT NULL,
    content TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (resident_id) REFERENCES residents(id)
);
"""


def get_connection():
    """Open a SQLite connection, creating the data/ folder on first run."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they do not exist yet. Safe to call every startup."""
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate(conn)
    conn.close()


def _migrate(conn):
    """Add columns to already-existing tables that predate them."""
    columns = [row[1] for row in conn.execute("PRAGMA table_info(reminders)")]
    if "last_fired_at" not in columns:
        conn.execute("ALTER TABLE reminders ADD COLUMN last_fired_at TEXT")
        conn.commit()


def list_tables():
    """Return table names currently in the DB. Used to verify setup worked."""
    conn = get_connection()
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables


def seed_residents_from_personas(personas):
    """Insert resident personas into the DB if not already present (matched by id)."""
    conn = get_connection()
    for p in personas:
        topics = p["favorite_topics"]
        topics_text = "、".join(topics) if isinstance(topics, list) else topics
        conn.execute(
            "INSERT OR IGNORE INTO residents (id, name, personality, favorite_topics) "
            "VALUES (?, ?, ?, ?)",
            (p["id"], p["name"], p["personality"], topics_text),
        )
    conn.commit()
    conn.close()


def add_resident(name, personality, favorite_topics):
    """Add a new resident persona, created by the caregiver at runtime."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO residents (name, personality, favorite_topics) VALUES (?, ?, ?)",
        (name, personality, favorite_topics),
    )
    conn.commit()
    conn.close()


def get_residents():
    """Return all residents as a list of dicts."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT id, name, personality, favorite_topics FROM residents ORDER BY id"
    )
    residents = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return residents


def get_resident(resident_id):
    """Return a single resident, or None if it doesn't exist."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT id, name, personality, favorite_topics FROM residents WHERE id = ?",
        (resident_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def create_conversation(resident_id):
    """Start a new conversation session for a resident and return its id."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO conversations (resident_id, started_at) VALUES (?, ?)",
        (resident_id, datetime.now().isoformat()),
    )
    conn.commit()
    conversation_id = cursor.lastrowid
    conn.close()
    return conversation_id


def get_conversation(conversation_id):
    """Return a single conversation's row, or None if it doesn't exist."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT id, resident_id, started_at FROM conversations WHERE id = ?",
        (conversation_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def add_message(conversation_id, role, content):
    """Save one message (user or assistant) to a conversation."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (conversation_id, role, content, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_messages(conversation_id):
    """Return all messages for a conversation, oldest first."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY id",
        (conversation_id,),
    )
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return messages


def save_extraction(conversation_id, mood, summary, notable_points):
    """Save the AI-extracted mood / summary / notable points for a conversation."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO extractions (conversation_id, mood, summary, notable_points, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (conversation_id, mood, summary, notable_points, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_extraction(conversation_id):
    """Return the latest extraction for a conversation, or None if not extracted yet."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT mood, summary, notable_points, created_at FROM extractions "
        "WHERE conversation_id = ? ORDER BY id DESC LIMIT 1",
        (conversation_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_daily_records(date_str, resident_id=None):
    """Return each conversation's resident name + latest extraction for the
    given date (YYYY-MM-DD), optionally filtered to one resident. Only
    conversations that already have an extraction are included."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    query = (
        "SELECT c.id AS conversation_id, c.resident_id, c.started_at, "
        "r.name AS resident_name, e.mood, e.summary, e.notable_points "
        "FROM conversations c "
        "JOIN residents r ON r.id = c.resident_id "
        "JOIN extractions e ON e.id = ("
        "   SELECT id FROM extractions WHERE conversation_id = c.id ORDER BY id DESC LIMIT 1"
        ") "
        "WHERE c.started_at LIKE ?"
    )
    params = [f"{date_str}%"]
    if resident_id is not None:
        query += " AND c.resident_id = ?"
        params.append(resident_id)
    query += " ORDER BY c.started_at"

    cursor = conn.execute(query, params)
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return records


def add_reminder(resident_id, time_str, content):
    """Add a new voice reminder for a resident. time_str is "HH:MM"."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO reminders (resident_id, time, content, is_active) VALUES (?, ?, ?, 1)",
        (resident_id, time_str, content),
    )
    conn.commit()
    conn.close()


def get_reminders(resident_id=None):
    """Return all reminders (active and inactive), optionally for one resident."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    query = (
        "SELECT r.id, r.resident_id, r.time, r.content, r.is_active, "
        "res.name AS resident_name "
        "FROM reminders r JOIN residents res ON res.id = r.resident_id"
    )
    params = []
    if resident_id is not None:
        query += " WHERE r.resident_id = ?"
        params.append(resident_id)
    query += " ORDER BY r.time"

    cursor = conn.execute(query, params)
    reminders = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return reminders


def get_active_reminders():
    """Return only active reminders, for the background scheduler to use."""
    return [r for r in get_reminders() if r["is_active"]]


def get_due_reminders():
    """Return active reminders whose time has passed today and that have not
    already fired today. Used by the frontend's polling loop."""
    now = datetime.now()
    today = now.date().isoformat()
    current_hm = now.strftime("%H:%M")

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT r.id, r.resident_id, r.time, r.content, res.name AS resident_name "
        "FROM reminders r JOIN residents res ON res.id = r.resident_id "
        "WHERE r.is_active = 1 AND r.time <= ? "
        "AND (r.last_fired_at IS NULL OR r.last_fired_at != ?)",
        (current_hm, today),
    )
    reminders = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return reminders


def mark_reminder_fired(reminder_id):
    """Record that a reminder has fired today, so it isn't repeated."""
    conn = get_connection()
    conn.execute(
        "UPDATE reminders SET last_fired_at = ? WHERE id = ?",
        (datetime.now().date().isoformat(), reminder_id),
    )
    conn.commit()
    conn.close()


def set_reminder_active(reminder_id, is_active):
    """Enable or disable a reminder without deleting it."""
    conn = get_connection()
    conn.execute(
        "UPDATE reminders SET is_active = ? WHERE id = ?", (int(is_active), reminder_id)
    )
    conn.commit()
    conn.close()


def delete_reminder(reminder_id):
    """Permanently remove a reminder."""
    conn = get_connection()
    conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    # Manual check: run `python -m core.database` from the project root.
    init_db()
    print("Tables created:", list_tables())
