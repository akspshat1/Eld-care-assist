"""What the companion remembers between conversations.

Without this, every conversation starts from nothing and the resident has to
re-tell the same things -- which is exactly the opposite of what a familiar
companion should feel like.

The cost of memory is tokens on every single turn, so this is deliberately
frugal:

  * only the last few days are considered;
  * only the *notable* part of each record, not the full summary;
  * near-duplicate lines are dropped (a knee mentioned four days running is
    one fact, not four);
  * the whole block is hard-capped, so it cannot grow without limit.

Roughly 100-150 tokens at the cap, added once per request as part of the
system prompt.
"""

import re
from datetime import datetime, timedelta

MAX_CHARS = 600          # hard ceiling for the whole block
MAX_ITEMS = 4            # at most this many remembered lines
MAX_ITEM_CHARS = 90      # each line trimmed to this
LOOKBACK_DAYS = 7

_NOTHING = re.compile(
    r"^(nothing particular|nothing|none|n/?a|特になし|なし)\.?$", re.I)


def _clean(text):
    """One tidy line, or None if it says nothing worth remembering."""
    if not text:
        return None
    line = " ".join(str(text).split())
    if not line or _NOTHING.match(line.strip()):
        return None
    if len(line) > MAX_ITEM_CHARS:
        line = line[:MAX_ITEM_CHARS - 1].rsplit(" ", 1)[0] + "…"
    return line


def _key(line):
    """Loose fingerprint, so the same fact twice is stored once."""
    words = re.findall(r"[a-z]{4,}|[぀-ヿ一-龯]{2,}",
                       line.lower())
    return " ".join(sorted(set(words))[:6])


def recent_facts(store, resident_id, days=LOOKBACK_DAYS):
    """The few things worth carrying into the next conversation."""
    cutoff = (datetime.now() - timedelta(days=days)).timestamp()
    facts, seen = [], set()

    def add(when, text):
        line = _clean(text)
        if not line:
            return
        k = _key(line)
        if k in seen:
            return
        seen.add(k)
        facts.append(f"{when}: {line}")

    # Check-ins carry the most useful detail -- concerns and their own words.
    for c in store.checkins(resident_id=resident_id, limit=12):
        if c["ts"] < cutoff or len(facts) >= MAX_ITEMS:
            break
        day = c["day"][5:]                     # MM-DD is enough
        if c.get("concerns"):
            add(day, ", ".join(c["concerns"][:2]))
        elif c.get("summary"):
            add(day, c["summary"])

    # Then anything notable from recent conversations.
    if len(facts) < MAX_ITEMS:
        for i in range(days):
            day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            for r in store.conv_records(day):
                if r.get("resident_id") != resident_id or len(facts) >= MAX_ITEMS:
                    continue
                add(day[5:], r.get("notable_points") or r.get("summary"))

    return facts[:MAX_ITEMS]


def build(store, resident_id, lang="en"):
    """A compact block for the system prompt, or "" when there is nothing."""
    try:
        facts = recent_facts(store, resident_id)
    except Exception:                          # noqa: BLE001 - never block a reply
        return ""
    if not facts:
        return ""

    if lang == "ja":
        head = ("最近の様子（読み上げず、自然に触れられるときだけ使うこと。"
                "毎回持ち出さないこと）：")
    else:
        head = ("Recently, about this person (do not read this out; refer to "
                "it only when it fits naturally, not every turn):")

    block = head + "\n" + "\n".join(f"- {f}" for f in facts)
    if len(block) > MAX_CHARS:
        block = block[:MAX_CHARS].rsplit("\n", 1)[0]
    return block
