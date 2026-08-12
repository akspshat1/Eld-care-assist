"""ChromaDB access layer.

All Chroma calls live here so feature modules never talk to chromadb
directly. Swapping the DB again later only requires changing this file.
Every function keeps the exact same name, signature, and return shape as
the previous SQLite implementation, so no caller needed to change.

Design notes (see the migration plan for the full rationale):
- Chroma document IDs must be strings, but callers still get/pass plain
  ints, so ids are stringified only at the Chroma call boundary.
- There is no AUTOINCREMENT, so integer ids are generated via a small
  "counters" collection (_next_id below). This is a simple read-modify-
  write, not atomic - fine for this single-process app, same trust level
  SQLite had here.
- Chroma metadata can't store None, so the "not fired yet" state for
  reminders uses "" instead of NULL.
- Chroma's `where` has no SQL LIKE equivalent, so conversations also store
  a `started_date` (just the date part) for exact-match filtering by day.
- Every collection stores a meaningful `documents` string (message content,
  extraction summary, persona bio, ...) so a future RAG feature can search
  over them without any schema change.
"""
from datetime import datetime

import chromadb

from config import CHROMA_PATH

_client = chromadb.PersistentClient(path=CHROMA_PATH)

COLLECTION_NAMES = [
    "residents",
    "conversations",
    "messages",
    "extractions",
    "reminders",
    "counters",
]


def get_connection():
    """Return the shared Chroma client (kept for parity with the old API)."""
    return _client


def init_db():
    """Create all collections if they do not exist yet. Safe to call every startup."""
    for name in COLLECTION_NAMES:
        _client.get_or_create_collection(name)


def list_tables():
    """Return collection names currently in the DB. Used to verify setup worked."""
    return [c.name for c in _client.list_collections()]


def _collection(name):
    return _client.get_or_create_collection(name)


def _next_id(counter_name):
    """Generate the next sequential integer id for a collection."""
    counters = _collection("counters")
    existing = counters.get(ids=[counter_name])
    if existing["ids"]:
        value = existing["metadatas"][0]["value"] + 1
        counters.update(ids=[counter_name], metadatas=[{"value": value}])
    else:
        value = 1
        counters.add(ids=[counter_name], documents=["counter"], metadatas=[{"value": value}])
    return value


def _bump_counter(counter_name, at_least):
    """Make sure future _next_id() calls start above at_least.

    Used after seeding residents with personas.json's fixed ids, so a
    later add_resident() doesn't reuse one of them.
    """
    counters = _collection("counters")
    existing = counters.get(ids=[counter_name])
    if existing["ids"]:
        if existing["metadatas"][0]["value"] < at_least:
            counters.update(ids=[counter_name], metadatas=[{"value": at_least}])
    else:
        counters.add(ids=[counter_name], documents=["counter"], metadatas=[{"value": at_least}])


def _resident_from_metadata(meta):
    return {
        "id": meta["id"],
        "name": meta["name"],
        "personality": meta["personality"],
        "favorite_topics": meta["favorite_topics"],
    }


def seed_residents_from_personas(personas):
    """Insert resident personas into the DB if not already present (matched by id)."""
    residents = _collection("residents")
    max_id = 0
    for p in personas:
        topics = p["favorite_topics"]
        topics_text = "、".join(topics) if isinstance(topics, list) else topics
        rid = p["id"]
        max_id = max(max_id, rid)
        if residents.get(ids=[str(rid)])["ids"]:
            continue
        residents.add(
            ids=[str(rid)],
            documents=[f"{p['name']} — {p['personality']}"],
            metadatas=[
                {
                    "id": rid,
                    "name": p["name"],
                    "personality": p["personality"],
                    "favorite_topics": topics_text,
                }
            ],
        )
    if max_id:
        _bump_counter("residents", max_id)


def add_resident(name, personality, favorite_topics):
    """Add a new resident persona, created by the caregiver at runtime."""
    rid = _next_id("residents")
    _collection("residents").add(
        ids=[str(rid)],
        documents=[f"{name} — {personality}"],
        metadatas=[
            {
                "id": rid,
                "name": name,
                "personality": personality,
                "favorite_topics": favorite_topics,
            }
        ],
    )


def get_residents():
    """Return all residents as a list of dicts."""
    result = _collection("residents").get()
    residents = [_resident_from_metadata(m) for m in result["metadatas"]]
    residents.sort(key=lambda r: r["id"])
    return residents


def get_resident(resident_id):
    """Return a single resident, or None if it doesn't exist."""
    result = _collection("residents").get(ids=[str(resident_id)])
    if not result["ids"]:
        return None
    return _resident_from_metadata(result["metadatas"][0])


def create_conversation(resident_id):
    """Start a new conversation session for a resident and return its id."""
    cid = _next_id("conversations")
    started_at = datetime.now().isoformat()
    _collection("conversations").add(
        ids=[str(cid)],
        documents=[f"conversation {cid} with resident {resident_id}"],
        metadatas=[
            {
                "id": cid,
                "resident_id": resident_id,
                "started_at": started_at,
                "started_date": started_at[:10],
            }
        ],
    )
    return cid


def get_conversation(conversation_id):
    """Return a single conversation's row, or None if it doesn't exist."""
    result = _collection("conversations").get(ids=[str(conversation_id)])
    if not result["ids"]:
        return None
    meta = result["metadatas"][0]
    return {"id": meta["id"], "resident_id": meta["resident_id"], "started_at": meta["started_at"]}


def add_message(conversation_id, role, content):
    """Save one message (user or assistant) to a conversation."""
    mid = _next_id("messages")
    _collection("messages").add(
        ids=[str(mid)],
        documents=[content],
        metadatas=[
            {
                "id": mid,
                "conversation_id": conversation_id,
                "role": role,
                "created_at": datetime.now().isoformat(),
            }
        ],
    )


def get_messages(conversation_id):
    """Return all messages for a conversation, oldest first."""
    result = _collection("messages").get(where={"conversation_id": conversation_id})
    rows = [
        {"id": meta["id"], "role": meta["role"], "content": doc, "created_at": meta["created_at"]}
        for meta, doc in zip(result["metadatas"], result["documents"])
    ]
    rows.sort(key=lambda r: r["id"])
    for row in rows:
        del row["id"]
    return rows


def save_extraction(conversation_id, mood, summary, notable_points):
    """Save the AI-extracted mood / summary / notable points for a conversation."""
    eid = _next_id("extractions")
    _collection("extractions").add(
        ids=[str(eid)],
        documents=[summary],
        metadatas=[
            {
                "id": eid,
                "conversation_id": conversation_id,
                "mood": mood,
                "notable_points": notable_points,
                "created_at": datetime.now().isoformat(),
            }
        ],
    )


def get_extraction(conversation_id):
    """Return the latest extraction for a conversation, or None if not extracted yet."""
    result = _collection("extractions").get(where={"conversation_id": conversation_id})
    if not result["ids"]:
        return None
    rows = [
        {
            "id": meta["id"],
            "mood": meta["mood"],
            "summary": doc,
            "notable_points": meta["notable_points"],
            "created_at": meta["created_at"],
        }
        for meta, doc in zip(result["metadatas"], result["documents"])
    ]
    rows.sort(key=lambda r: r["id"], reverse=True)
    latest = rows[0]
    del latest["id"]
    return latest


def get_daily_records(date_str, resident_id=None):
    """Return each conversation's resident name + latest extraction for the
    given date (YYYY-MM-DD), optionally filtered to one resident. Only
    conversations that already have an extraction are included."""
    if resident_id is not None:
        where = {"$and": [{"started_date": date_str}, {"resident_id": resident_id}]}
    else:
        where = {"started_date": date_str}

    conversations = _collection("conversations").get(where=where)

    resident_cache = {}
    records = []
    for meta in conversations["metadatas"]:
        extraction = get_extraction(meta["id"])
        if extraction is None:
            continue
        rid = meta["resident_id"]
        if rid not in resident_cache:
            resident_cache[rid] = get_resident(rid)
        resident = resident_cache[rid]
        records.append(
            {
                "conversation_id": meta["id"],
                "resident_id": rid,
                "started_at": meta["started_at"],
                "resident_name": resident["name"] if resident else None,
                "mood": extraction["mood"],
                "summary": extraction["summary"],
                "notable_points": extraction["notable_points"],
            }
        )
    records.sort(key=lambda r: r["started_at"])
    return records


def add_reminder(resident_id, time_str, content):
    """Add a new voice reminder for a resident. time_str is "HH:MM"."""
    rid = _next_id("reminders")
    _collection("reminders").add(
        ids=[str(rid)],
        documents=[content],
        metadatas=[
            {
                "id": rid,
                "resident_id": resident_id,
                "time": time_str,
                "content": content,
                "is_active": True,
                "last_fired_at": "",
            }
        ],
    )


def get_reminders(resident_id=None):
    """Return all reminders (active and inactive), optionally for one resident."""
    where = {"resident_id": resident_id} if resident_id is not None else None
    result = _collection("reminders").get(where=where)

    resident_cache = {}
    reminders = []
    for meta in result["metadatas"]:
        rid = meta["resident_id"]
        if rid not in resident_cache:
            resident_cache[rid] = get_resident(rid)
        resident = resident_cache[rid]
        reminders.append(
            {
                "id": meta["id"],
                "resident_id": rid,
                "time": meta["time"],
                "content": meta["content"],
                "is_active": int(meta["is_active"]),
                "resident_name": resident["name"] if resident else None,
            }
        )
    reminders.sort(key=lambda r: r["time"])
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

    result = _collection("reminders").get(where={"is_active": True})

    resident_cache = {}
    due = []
    for meta in result["metadatas"]:
        if meta["time"] > current_hm:
            continue
        if meta.get("last_fired_at") == today:
            continue
        rid = meta["resident_id"]
        if rid not in resident_cache:
            resident_cache[rid] = get_resident(rid)
        resident = resident_cache[rid]
        due.append(
            {
                "id": meta["id"],
                "resident_id": rid,
                "time": meta["time"],
                "content": meta["content"],
                "resident_name": resident["name"] if resident else None,
            }
        )
    return due


def mark_reminder_fired(reminder_id):
    """Record that a reminder has fired today, so it isn't repeated."""
    _collection("reminders").update(
        ids=[str(reminder_id)],
        metadatas=[{"last_fired_at": datetime.now().date().isoformat()}],
    )


def set_reminder_active(reminder_id, is_active):
    """Enable or disable a reminder without deleting it."""
    _collection("reminders").update(
        ids=[str(reminder_id)], metadatas=[{"is_active": bool(is_active)}]
    )


def delete_reminder(reminder_id):
    """Permanently remove a reminder."""
    _collection("reminders").delete(ids=[str(reminder_id)])


if __name__ == "__main__":
    # Manual check: run `python -m core.database` from the project root.
    init_db()
    print("Tables created:", list_tables())
