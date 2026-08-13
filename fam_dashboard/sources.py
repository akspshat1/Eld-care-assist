"""Reads the care and medication databases and turns them into what a family
member actually wants to know.

The rule throughout: say plainly how the person is, and only raise an alert
when something is worth a phone call. A dashboard that cries wolf gets ignored,
and a dashboard that stays silent through a bad week is worse than none.
"""

import os
import sys
import threading
from datetime import datetime, date, timedelta

import config

_lock = threading.Lock()
_care = None
_meds = None


def _add_path(path):
    if os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)


def care():
    """eld_care_assist's store, opened where it lives."""
    global _care
    with _lock:
        if _care is None:
            _add_path(config.CARE_DIR)
            from store import Store
            _care = Store(config.CARE_DB)
        return _care


def meds():
    """med_mgmt's medication store. None if that app was never set up."""
    global _meds
    with _lock:
        if _meds is None and config.med_db_exists():
            _add_path(config.MED_DIR)
            from med_store import MedStore
            _meds = MedStore(config.MED_DB)
        return _meds


def status():
    return {
        "care_db": config.care_db_exists(),
        "med_db": config.med_db_exists(),
        "groq": config.groq_ready(),
    }


# --------------------------------------------------------------- overview --

def _hours_since(ts):
    return (datetime.now().timestamp() - ts) / 3600


def medication_summary(days=7):
    """Adherence over the last few days, plus what was missed today."""
    ms = meds()
    if ms is None:
        return None

    today = date.today().isoformat()
    today_sum = ms.day_summary(today)
    history = ms.history(days)

    total = sum(d["total"] for d in history)
    taken = sum(d["taken"] for d in history)
    missed = sum(d["missed"] for d in history)

    missed_today = [
        {"name": d["name"], "slot": d["slot"], "strength": d["strength"]}
        for d in today_sum["doses"]
        if d["status"] == "pending"
        and d["scheduled_ts"] < datetime.now().timestamp() - 3600
    ]

    return {
        "today": {"total": today_sum["total"], "taken": today_sum["taken"],
                  "missed": today_sum["missed"],
                  "adherence": today_sum["adherence"]},
        "missed_today": missed_today,
        "next": ms.next_dose(),
        "week": {"total": total, "taken": taken, "missed": missed,
                 "adherence": round(100 * taken / total) if total else None},
        "trend": [{"day": d["day"], "adherence": d["adherence"],
                   "taken": d["taken"], "total": d["total"]}
                  for d in reversed(history)],
    }


def build_alerts(resident_id, latest, mood_trend, med):
    """The short list of things worth telling the family about."""
    alerts = []

    # 1. Anything the check-in itself flagged as urgent.
    if latest and latest.get("concerns"):
        urgent_words = ("chest", "breath", "fall", "dizz", "胸", "息", "転", "めまい")
        for c in latest["concerns"]:
            if any(w in c.lower() for w in urgent_words):
                alerts.append({"level": "urgent", "kind": "symptom", "text": c,
                               "when": f"{latest['day']} {latest['time']}"})

    # 2. Wellbeing low today.
    if latest and latest.get("wellbeing") is not None \
            and latest["wellbeing"] < config.LOW_WELLBEING:
        alerts.append({
            "level": "warn", "kind": "wellbeing",
            "text": f"Wellbeing was {latest['wellbeing']}/100 at the last check-in.",
            "when": f"{latest['day']} {latest['time']}"})

    # 3. Falling trend over several days -- easy to miss day to day.
    if len(mood_trend) >= 4:
        first = sum(d["score"] for d in mood_trend[:2]) / 2
        last = sum(d["score"] for d in mood_trend[-2:]) / 2
        if last < first - 15:
            alerts.append({
                "level": "warn", "kind": "trend",
                "text": f"Mood has been drifting down this week "
                        f"({round(first)} to {round(last)} out of 100).",
                "when": mood_trend[-1]["day"]})

    # 4. No check-in for a while.
    if latest:
        hours = _hours_since(latest["ts"])
        if hours >= config.QUIET_HOURS:
            alerts.append({
                "level": "warn", "kind": "quiet",
                "text": f"No check-in for {int(hours)} hours.",
                "when": f"{latest['day']} {latest['time']}"})
    else:
        alerts.append({"level": "info", "kind": "quiet",
                       "text": "No check-ins recorded yet.", "when": ""})

    # 5. Medicines missed.
    if med and med["missed_today"]:
        names = ", ".join(f"{m['name']} ({m['slot']})" for m in med["missed_today"])
        level = "urgent" if len(med["missed_today"]) >= config.MISSED_DOSES_ALERT else "warn"
        alerts.append({"level": level, "kind": "medication",
                       "text": f"Missed today: {names}", "when": date.today().isoformat()})

    order = {"urgent": 0, "warn": 1, "info": 2}
    alerts.sort(key=lambda a: order.get(a["level"], 3))
    return alerts


def overview(resident_id, days=14):
    """Everything the dashboard's front page needs, in one call."""
    st = care()
    resident = st.resident(resident_id)
    if resident is None:
        return None

    checkins = st.checkins(resident_id=resident_id, limit=days * 3)
    latest = checkins[0] if checkins else None
    trend = st.checkin_trend(resident_id, days)
    med = medication_summary(7)

    today = date.today().isoformat()
    today_checkins = [c for c in checkins if c["day"] == today]

    return {
        "resident": resident,
        "latest": latest,
        "today_count": len(today_checkins),
        "trend": trend,
        "medication": med,
        "alerts": build_alerts(resident_id, latest, trend, med),
        "recent": checkins[:8],
        "calls": st.recent_calls(resident_id, 8),
        "conversations": st.conv_records(today),
        "hours_since_checkin": round(_hours_since(latest["ts"]), 1) if latest else None,
    }


def timeline(resident_id, days=14):
    """Day-by-day rows: mood, check-ins, medicines."""
    st = care()
    med_store = meds()
    out = []
    for i in range(days):
        d = (date.today() - timedelta(days=i)).isoformat()
        day_checkins = st.checkins(day=d, resident_id=resident_id)
        scores = [c["wellbeing"] for c in day_checkins if c["wellbeing"] is not None]
        med_day = med_store.day_summary(d) if med_store else None
        out.append({
            "day": d,
            "checkins": len(day_checkins),
            "wellbeing": round(sum(scores) / len(scores)) if scores else None,
            "concerns": [c for ci in day_checkins for c in ci["concerns"]],
            "summary": day_checkins[0]["summary"] if day_checkins else "",
            "medication": {"taken": med_day["taken"], "total": med_day["total"],
                           "missed": med_day["missed"]} if med_day else None,
        })
    return out
