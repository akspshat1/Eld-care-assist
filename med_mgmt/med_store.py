"""Medication storage and dose scheduling.

Two tables:
  medications - what to take, how much, at which clock times
  dose_log    - what actually happened to each scheduled dose

A dose is not a row until someone acts on it. The schedule for a day is
computed from the medications table, then joined against dose_log, so changing
a medication's times does not orphan history.
"""

import os
import json
import sqlite3
import threading
from datetime import datetime, date, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "medications.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS medications (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    name_en        TEXT,
    strength       TEXT,
    form           TEXT,
    dose_amount    TEXT,
    frequency_text TEXT,
    times          TEXT NOT NULL DEFAULT '[]',   -- JSON list of "HH:MM"
    timing         TEXT,
    start_date     TEXT NOT NULL,
    end_date       TEXT,
    notes          TEXT,
    active         INTEGER NOT NULL DEFAULT 1,
    created_ts     REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS dose_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    med_id       INTEGER NOT NULL,
    day          TEXT NOT NULL,
    slot         TEXT NOT NULL,                  -- "HH:MM" or "prn"
    status       TEXT NOT NULL,                  -- taken | skipped
    action_ts    REAL NOT NULL,
    FOREIGN KEY (med_id) REFERENCES medications(id)
);
CREATE INDEX IF NOT EXISTS idx_dose_day ON dose_log(day);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dose_unique
    ON dose_log(med_id, day, slot);
"""


def _row_to_med(r):
    try:
        times = json.loads(r["times"])
        if not isinstance(times, list):
            times = []
    except (json.JSONDecodeError, TypeError):
        times = []
    return {
        "id": r["id"], "name": r["name"], "name_en": r["name_en"],
        "strength": r["strength"], "form": r["form"],
        "dose_amount": r["dose_amount"], "frequency_text": r["frequency_text"],
        "times": times, "timing": r["timing"],
        "start_date": r["start_date"], "end_date": r["end_date"],
        "notes": r["notes"], "active": bool(r["active"]),
    }


class MedStore:
    def __init__(self, db_path=DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------- medications --
    def add(self, med):
        times = json.dumps(med.get("times") or [])
        start = med.get("start_date") or date.today().isoformat()

        end = med.get("end_date")
        if not end and med.get("duration_days"):
            end = (date.fromisoformat(start)
                   + timedelta(days=int(med["duration_days"]) - 1)).isoformat()

        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO medications (name, name_en, strength, form,"
                " dose_amount, frequency_text, times, timing, start_date,"
                " end_date, notes, active, created_ts)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?)",
                (med["name"], med.get("name_en"), med.get("strength"),
                 med.get("form"), med.get("dose_amount"),
                 med.get("frequency_text"), times, med.get("timing"),
                 start, end, med.get("notes"), datetime.now().timestamp()))
            self._conn.commit()
            return cur.lastrowid

    def update(self, med_id, fields):
        allowed = ("name", "name_en", "strength", "form", "dose_amount",
                   "frequency_text", "times", "timing", "start_date",
                   "end_date", "notes", "active")
        sets, vals = [], []
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k == "times":
                v = json.dumps(v or [])
            if k == "active":
                v = 1 if v else 0
            sets.append(f"{k}=?")
            vals.append(v)
        if not sets:
            return False
        vals.append(med_id)
        with self._lock:
            self._conn.execute(
                f"UPDATE medications SET {', '.join(sets)} WHERE id=?", vals)
            self._conn.commit()
        return True

    def delete(self, med_id):
        with self._lock:
            self._conn.execute("DELETE FROM dose_log WHERE med_id=?", (med_id,))
            self._conn.execute("DELETE FROM medications WHERE id=?", (med_id,))
            self._conn.commit()

    def all_meds(self, active_only=False):
        q = "SELECT * FROM medications"
        if active_only:
            q += " WHERE active=1"
        q += " ORDER BY name"
        with self._lock:
            return [_row_to_med(r) for r in self._conn.execute(q).fetchall()]

    def get(self, med_id):
        with self._lock:
            r = self._conn.execute(
                "SELECT * FROM medications WHERE id=?", (med_id,)).fetchone()
        return _row_to_med(r) if r else None

    # ------------------------------------------------------------ dosing --
    def _active_on(self, day):
        """Medications whose date range covers `day`."""
        out = []
        for m in self.all_meds(active_only=True):
            if m["start_date"] and day < m["start_date"]:
                continue
            if m["end_date"] and day > m["end_date"]:
                continue
            out.append(m)
        return out

    def schedule_for(self, day):
        """Every scheduled dose on `day`, with its current status."""
        with self._lock:
            logged = {
                (r["med_id"], r["slot"]): (r["status"], r["action_ts"])
                for r in self._conn.execute(
                    "SELECT med_id, slot, status, action_ts FROM dose_log"
                    " WHERE day=?", (day,)).fetchall()
            }

        doses = []
        for m in self._active_on(day):
            if not m["times"]:
                continue                       # as-needed: not on the timeline
            for slot in sorted(m["times"]):
                status, action_ts = logged.get((m["id"], slot), (None, None))
                doses.append({
                    "med_id": m["id"], "name": m["name"], "name_en": m["name_en"],
                    "strength": m["strength"], "dose_amount": m["dose_amount"],
                    "form": m["form"], "timing": m["timing"], "notes": m["notes"],
                    "day": day, "slot": slot,
                    "scheduled_ts": datetime.strptime(
                        f"{day} {slot}", "%Y-%m-%d %H:%M").timestamp(),
                    "status": status or "pending",
                    "action_ts": action_ts,
                })
        doses.sort(key=lambda d: (d["slot"], d["name"]))
        return doses

    def as_needed_meds(self, day=None):
        day = day or date.today().isoformat()
        return [m for m in self._active_on(day) if not m["times"]]

    def due_now(self, grace_min=1, overdue_min=60):
        """Doses that should be taken now, plus how late they are."""
        now = datetime.now()
        today = now.date().isoformat()
        due = []
        for d in self.schedule_for(today):
            if d["status"] != "pending":
                continue
            late_min = (now.timestamp() - d["scheduled_ts"]) / 60
            if late_min < grace_min - 1:
                continue                       # not yet time
            d = dict(d)
            d["late_minutes"] = int(late_min)
            d["overdue"] = late_min >= overdue_min
            due.append(d)
        return due

    def next_dose(self):
        """The next upcoming dose today, if any."""
        now = datetime.now().timestamp()
        upcoming = [d for d in self.schedule_for(date.today().isoformat())
                    if d["status"] == "pending" and d["scheduled_ts"] > now]
        return min(upcoming, key=lambda d: d["scheduled_ts"]) if upcoming else None

    def mark(self, med_id, day, slot, status):
        if status not in ("taken", "skipped"):
            raise ValueError("status must be 'taken' or 'skipped'")
        with self._lock:
            self._conn.execute(
                "INSERT INTO dose_log (med_id, day, slot, status, action_ts)"
                " VALUES (?,?,?,?,?)"
                " ON CONFLICT(med_id, day, slot)"
                " DO UPDATE SET status=excluded.status, action_ts=excluded.action_ts",
                (med_id, day, slot, status, datetime.now().timestamp()))
            self._conn.commit()

    def unmark(self, med_id, day, slot):
        with self._lock:
            self._conn.execute(
                "DELETE FROM dose_log WHERE med_id=? AND day=? AND slot=?",
                (med_id, day, slot))
            self._conn.commit()

    def log_prn(self, med_id):
        """Record an as-needed dose, stamped with the time it was taken."""
        now = datetime.now()
        with self._lock:
            self._conn.execute(
                "INSERT INTO dose_log (med_id, day, slot, status, action_ts)"
                " VALUES (?,?,?,?,?)",
                (med_id, now.date().isoformat(),
                 "prn " + now.strftime("%H:%M"), "taken", now.timestamp()))
            self._conn.commit()

    # ---------------------------------------------------------- reporting --
    def day_summary(self, day):
        doses = self.schedule_for(day)
        taken = sum(1 for d in doses if d["status"] == "taken")
        skipped = sum(1 for d in doses if d["status"] == "skipped")
        total = len(doses)

        # Pending doses in the past count as missed once the day is over.
        now = datetime.now()
        missed = 0
        for d in doses:
            if d["status"] == "pending" and d["scheduled_ts"] < now.timestamp() - 3600:
                missed += 1

        with self._lock:
            prn = self._conn.execute(
                "SELECT COUNT(*) FROM dose_log WHERE day=? AND slot LIKE 'prn%'",
                (day,)).fetchone()[0]

        return {
            "day": day, "total": total, "taken": taken, "skipped": skipped,
            "missed": missed, "pending": total - taken - skipped - missed,
            "prn_taken": prn,
            "adherence": round(100 * taken / total) if total else None,
            "doses": doses,
        }

    def history(self, days=14):
        today = date.today()
        return [self.day_summary((today - timedelta(days=i)).isoformat())
                for i in range(days)]

    def logged_days(self):
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT day FROM dose_log ORDER BY day DESC").fetchall()
        return [r[0] for r in rows]

    def close(self):
        with self._lock:
            self._conn.close()
