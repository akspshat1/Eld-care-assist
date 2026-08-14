"""Always-on voice mode: "Hello Robo".

A third way to use the app, for a resident who cannot or will not use a screen.
The device sits on the sideboard listening. Say the wake word and it wakes up,
does whatever is asked, then goes back to sleep on its own.

Two states, deliberately:

  SLEEPING  Everything heard is transcribed, checked for the wake word and for
            a cry for help, then discarded. Nothing else happens and nothing
            is stored -- this is Guardian mode, always on.

  AWAKE     A normal conversation, plus spoken commands: medicines, the daily
            check-in, phoning family, and emergencies. Falls back to sleep
            after a stretch of silence so it is never listening *at* someone
            for longer than they asked for.

Intent matching is keyword-first and only asks the model when the words are
unclear. That keeps the common commands instant and free, and keeps the
emergency path working when the API does not.
"""

import re

import groq_api

# "Robo" is short, distinctive and survives a hard-of-hearing speaker and a
# transcriber that guesses. The variants are what Whisper actually produces.
WAKE_PATTERNS = [
    r"\bhello,? rob(o|ot|bo|oh)?\b", r"\bhey,? rob(o|ot|bo|oh)?\b",
    r"\bhi,? rob(o|ot|bo|oh)?\b", r"\bok(ay)?,? rob(o|ot|bo|oh)?\b",
    r"\bhello,? robo?t?\b", r"\brobo,? are you there\b",
    r"ロボ", r"ろぼ", r"ハロー ?ロボ",
]

SLEEP_PATTERNS = [
    r"\b(go(odbye)?|bye|that'?s all|thank you,? robo|goodnight)\b",
    r"\bgo to sleep\b", r"\bstop listening\b",
    r"おやすみ", r"ありがとう、?ロボ", r"もういい",
]

# What can be asked for by voice. Ordered: the earlier ones win a tie.
INTENTS = {
    "emergency": [
        r"\b(help me|call an ambulance|emergency|i need help)\b",
        r"助けて", r"救急車",
    ],
    "call": [
        r"\b(call|phone|ring|dial)\b", r"\bget hold of\b", r"\btalk to\b",
        r"電話", r"かけて", r"つないで",
    ],
    "medicine_taken": [
        r"\bi(\'ve| have)? (just )?(taken|took) (my )?(pills?|tablets?|medicine)",
        r"\b(pills?|tablets?|medicine).{0,12}\b(taken|done)\b",
        r"薬.{0,6}(飲んだ|のんだ|飲みました)",
    ],
    "medicine_query": [
        r"\b(what|which|when).{0,20}(medicine|pills?|tablets?)\b",
        r"\bdo i (need to|have to) take\b", r"\bmy (medicine|pills?|tablets?)\b",
        r"(薬|くすり).{0,8}(何|いつ|どれ)",
    ],
    "checkin": [
        r"\b(check[- ]?in|how am i doing|daily check)\b",
        r"\b(let'?s|start|do) (my|the) check",
        r"体調(チェック|確認)", r"チェックイン",
    ],
    "status": [
        r"\b(how am i|how have i been|what did i say)\b",
        r"\b(read|tell me) (my|the) (report|summary)\b",
        r"(調子|様子)はどう",
    ],
}

INTENT_SYSTEM = """You label what someone said to a voice assistant in their home.

Reply with exactly one of:
  emergency        they need help now
  call             they want to phone a person
  medicine_taken   they are saying they have taken their medicine
  medicine_query   they are asking about their medicine
  checkin          they want to do their daily check-in
  status           they are asking how they have been
  chat             anything else, including ordinary conversation

Return ONLY this JSON: {"intent": "<one of the above>"}"""


def _matches(text, patterns):
    return any(re.search(p, text) for p in patterns)


def normalise(text):
    return (text or "").lower().replace("’", "'").strip()


def is_wake(text):
    return _matches(normalise(text), WAKE_PATTERNS)


def is_sleep(text):
    return _matches(normalise(text), SLEEP_PATTERNS)


def strip_wake(text):
    """Remove the wake word, so "Hello Robo, call my son" leaves the request."""
    out = text or ""
    for p in WAKE_PATTERNS:
        out = re.sub(p, "", out, flags=re.I)
    return out.strip(" ,.।、。") or ""


def classify(text, use_model=True):
    """What is being asked for. Returns an intent name."""
    low = normalise(text)
    if not low:
        return "chat"

    for intent, patterns in INTENTS.items():
        if _matches(low, patterns):
            return intent

    if not use_model or len(low.split()) < 3:
        return "chat"

    try:
        data = groq_api.chat_json(INTENT_SYSTEM, f'They said: "{text}"',
                                  max_tokens=60)
        intent = data.get("intent")
        if intent in list(INTENTS) + ["chat"]:
            return intent
    except Exception:                          # noqa: BLE001 - fall back to chat
        pass
    return "chat"


# ----------------------------------------------------------- spoken text ----

def say_medicines(summary, lang="en"):
    """A spoken answer about today's medicines."""
    due = summary.get("due") or []
    nxt = summary.get("next")
    if due:
        d = due[0]
        name = d["name"]
        if lang == "ja":
            return f"{name}の時間です。飲まれましたか？"
        return f"It's time for {name}. Have you taken it?"
    if nxt:
        if lang == "ja":
            return f"次のお薬は{nxt['slot']}に{nxt['name']}です。"
        return f"Your next medicine is {nxt['name']} at {nxt['slot']}."
    if lang == "ja":
        return "今日のお薬はすべて終わりました。"
    return "You have no more medicines due today."


def confirm_taken(name, lang="en"):
    if lang == "ja":
        return f"ありがとうございます。{name}を服用済みにしました。"
    return f"Thank you. I've marked {name} as taken."


def greeting(resident_name, lang="en"):
    if lang == "ja":
        return f"はい、{resident_name}さん。どうされましたか？"
    return f"Yes, {resident_name}? How can I help?"


def going_to_sleep(lang="en"):
    if lang == "ja":
        return "わかりました。また呼んでくださいね。"
    return "All right. Just say hello robo if you need me."
