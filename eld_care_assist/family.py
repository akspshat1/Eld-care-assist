"""The Family view, reusing fam_dashboard's logic.

fam_dashboard already works out what a relative needs to know -- the alert
rules, the medication roll-up, the day-by-day timeline. Rather than write a
second copy that can drift, its `sources` module is imported and pointed at
this app's already-open store.

fam_dashboard remains runnable on its own (a relative can open just the
dashboard on their own machine); this makes the same view available inside the
main app as another tab.
"""

import os
import sys

import config
import groq_api

_sources = None
_error = None


def _load(store, med_store_getter):
    """Import fam_dashboard's sources once and hand it our open stores."""
    global _sources, _error
    if _sources is not None or _error is not None:
        return _sources

    if not os.path.isdir(config.FAM_DIR):
        _error = "fam_dashboard is not in this repo."
        return None
    if config.FAM_DIR not in sys.path:
        sys.path.append(config.FAM_DIR)      # append: our own modules win

    try:
        import sources
    except Exception as e:                    # noqa: BLE001
        _error = f"Could not load the family view: {e}"
        return None

    # Reuse the connections this app already holds rather than opening the
    # same SQLite files twice.
    sources._care = store
    try:
        sources._meds = med_store_getter()
    except Exception:                         # noqa: BLE001 - optional
        sources._meds = None

    _sources = sources
    return sources


def available(store, med_store_getter):
    return _load(store, med_store_getter) is not None


def error():
    return _error


def overview(store, med_store_getter, resident_id, days=14):
    s = _load(store, med_store_getter)
    if s is None:
        raise RuntimeError(_error)
    return s.overview(resident_id, days)


def timeline(store, med_store_getter, resident_id, days=14):
    s = _load(store, med_store_getter)
    if s is None:
        raise RuntimeError(_error)
    return s.timeline(resident_id, days)


DIGEST_SYSTEM = """You write a short, warm update for a family member about
their elderly relative, from care records.

Write as if speaking to their grandson or daughter -- plain, kind, specific.
2-4 sentences. Lead with how the person actually is.

Rules:
- Only use what is in the input. Invent nothing.
- Never diagnose, never give medical or medication advice.
- If something needs attention, say so plainly and suggest they phone or visit.
- If all is well, say so warmly and briefly. Do not manufacture concern."""


def digest(data, lang="en"):
    """A couple of sentences a relative can read in five seconds."""
    lines = [f"Resident: {data['resident']['name']}"]
    latest = data.get("latest")
    if latest:
        lines.append(f"Last check-in {latest['day']} {latest['time']}: "
                     f"wellbeing {latest['wellbeing']}/100. {latest['summary']}")
        if latest["concerns"]:
            lines.append("Concerns noted: " + "; ".join(latest["concerns"]))
    else:
        lines.append("No check-ins recorded yet.")

    if data.get("trend"):
        lines.append("Recent wellbeing scores: " + ", ".join(
            f"{d['day']}={d['score']}" for d in data["trend"][-7:]))

    med = data.get("medication")
    if med:
        lines.append(f"Medicines today: {med['today']['taken']} of "
                     f"{med['today']['total']} taken, {med['today']['missed']} missed.")
        if med["missed_today"]:
            lines.append("Missed: " + ", ".join(
                f"{m['name']} at {m['slot']}" for m in med["missed_today"]))

    for a in data.get("alerts", []):
        lines.append(f"Alert ({a['level']}): {a['text']}")

    lang_line = ("Write the update in Japanese." if lang == "ja"
                 else "Write the update in English.")
    return groq_api.chat(
        [{"role": "system", "content": DIGEST_SYSTEM},
         {"role": "user", "content": lang_line + "\n\n" + "\n".join(lines)}],
        temperature=0.4, max_tokens=350)
