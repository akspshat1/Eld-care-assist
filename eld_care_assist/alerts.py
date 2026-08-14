"""Getting an urgent alert to a real person.

Detecting that a resident said "my chest hurts" is worthless if the warning
only lands on a dashboard nobody has open. This module closes that loop: it
spots urgent statements in a conversation or a check-in, then delivers a
message to the people listed as contacts.

Delivery degrades on purpose. Whatever is configured is used; whatever is not
is skipped; and the alert is *always* recorded and shown in the app. An alert
must never be lost because an SMTP password was missing.

Channels, in the order they are tried:
  in-app   always -- recorded, shown to the care team and the family view
  webhook  ALERT_WEBHOOK_URL   (Slack/Discord/IFTTT all accept a JSON POST)
  email    SMTP_HOST/USER/PASS
  sms      TWILIO_SID/TOKEN/FROM

Scope: this raises a human. It never diagnoses and never advises treatment.
"""

import re
import json
import smtplib
import threading
from email.message import EmailMessage

import requests

import config

# Symptoms worth interrupting someone's day for. Matched on the resident's own
# words, in both languages, before any model is consulted -- these must still
# fire when the API is down or rate limited.
URGENT_PATTERNS = {
    "chest": {
        "en": [r"\bchest (pain|hurts?|tight|pressure)", r"\bpain in my chest",
               r"\bheart (hurts?|is racing|pounding)", r"\bcrushing (pain|feeling)",
               r"\bpain in my (left )?arm and chest"],
        "ja": [r"胸が痛", r"胸の痛み", r"胸が苦し", r"心臓が痛", r"動悸"],
        "label": {"en": "chest pain", "ja": "胸の痛み"},
    },
    "breath": {
        "en": [r"can'?t breathe", r"cannot breathe", r"trouble breathing",
               r"short of breath", r"struggling to breathe", r"gasping"],
        "ja": [r"息が(苦し|できな)", r"呼吸が(苦し|できな)", r"息切れ"],
        "label": {"en": "difficulty breathing", "ja": "息苦しさ"},
    },
    "stroke": {
        # Time matters more here than almost anywhere in medicine.
        "en": [r"\bface (is )?(droop|numb)", r"\bslurr(ed|ing) (my )?(words|speech)",
               r"can'?t (move|feel) my (arm|leg|left|right)",
               r"\bone side of my body", r"\bweak(ness)? (on|down) one side",
               r"can'?t speak properly", r"\bwords (won'?t|not) come out"],
        "ja": [r"呂律", r"ろれつ", r"顔が(しびれ|ゆがん)", r"片側が(動かな|しびれ)",
               r"(手|足)が動かな", r"言葉が出な"],
        "label": {"en": "possible stroke signs", "ja": "脳卒中の疑い"},
    },
    "fall": {
        "en": [r"\bi fell\b", r"\bi'?ve fallen", r"\bfell (down|over)",
               r"\bhad a fall", r"can'?t get up", r"\bon the floor and"],
        "ja": [r"転(んだ|倒)", r"転んでしま", r"起き上がれな", r"床に倒れ"],
        "label": {"en": "a fall", "ja": "転倒"},
    },
    "head": {
        "en": [r"\b(hit|banged|knocked) my head", r"\bhead injury"],
        "ja": [r"頭を(打|ぶつけ)"],
        "label": {"en": "a head injury", "ja": "頭部の打撲"},
    },
    "bleeding": {
        "en": [r"\bbleeding\b", r"\blot of blood", r"\bblood everywhere",
               r"\bcut myself badly", r"\bcoughing up blood",
               r"\bblood in my (stool|urine|vomit)"],
        "ja": [r"出血", r"血が(止まらな|出て)", r"血を吐"],
        "label": {"en": "bleeding", "ja": "出血"},
    },
    "choking": {
        "en": [r"\bchoking\b", r"\bcan'?t swallow", r"\bsomething stuck in my throat"],
        "ja": [r"のどに詰ま", r"喉に詰ま", r"飲み込めな", r"むせ"],
        "label": {"en": "choking or trouble swallowing", "ja": "のどの詰まり"},
    },
    "dizzy": {
        "en": [r"\b(feel|feeling) dizzy", r"\blight[- ]headed",
               r"\babout to faint", r"\bthe room is spinning", r"\bblacked out",
               r"\bpassed out"],
        "ja": [r"めまい", r"ふらつ", r"倒れそう", r"気を失"],
        "label": {"en": "dizziness or feeling faint", "ja": "めまい・立ちくらみ"},
    },
    "severe_pain": {
        "en": [r"\b(terrible|severe|unbearable|excruciating|worst) pain",
               r"\bpain is unbearable", r"\bagony\b"],
        "ja": [r"(激痛|耐えられない痛|ひどく痛)"],
        "label": {"en": "severe pain", "ja": "激しい痛み"},
    },
    "numbness": {
        "en": [r"\b(arm|leg|hand|foot) (has gone|is) numb",
               r"\bcan'?t feel my (arm|leg|hand|foot|face)"],
        "ja": [r"(手|足|腕)がしびれ", r"感覚がな"],
        "label": {"en": "numbness or loss of feeling", "ja": "しびれ・感覚の低下"},
    },
    "vision": {
        "en": [r"\b(can'?t see|lost my sight|going blind)",
               r"\bvision (has gone|went) (blurry|dark)"],
        "ja": [r"目が見えな", r"視界が(暗|ぼやけ)"],
        "label": {"en": "sudden vision problems", "ja": "急な視覚の異常"},
    },
    "overdose": {
        "en": [r"\btook too many (pills|tablets)",
               r"\btook (it|them|my pills) twice",
               r"\bdouble dose", r"\btook the wrong (pill|tablet|medicine)"],
        "ja": [r"(薬を)?(二回|2回|多く)飲んで", r"間違えて飲"],
        "label": {"en": "a possible medication error", "ja": "服薬の誤り"},
    },
    "self_harm": {
        # Older adults have high suicide rates and are under-asked about it.
        "en": [r"\bwant to die\b", r"\bdon'?t want to (live|be here)",
               r"\bend it all\b", r"\bkill myself", r"\bno reason to (live|go on)",
               r"\bbetter off (dead|without me)"],
        "ja": [r"死にたい", r"生きていたくな", r"消えてしまいたい"],
        "label": {"en": "thoughts of not wanting to live",
                  "ja": "死にたいという発言"},
    },
    "help": {
        "en": [r"\bhelp me\b", r"\bcall an ambulance", r"\bemergency\b",
               r"\bi think i'?m dying", r"\bsomething is (very )?wrong with me"],
        "ja": [r"助けて", r"救急車", r"緊急", r"様子がおかしい"],
        "label": {"en": "a call for help", "ja": "助けを求める発言"},
    },
}

# Worth a caregiver's attention, but not worth waking the family at 2am.
# These are logged and shown, and notified without an @here ping.
CONCERN_PATTERNS = {
    "not_eating": {
        "en": [r"\bhaven'?t eaten", r"\bnot eaten (all day|anything|since)",
               r"\bcan'?t eat\b", r"\bno appetite at all"],
        "ja": [r"何も食べて(いな|な)", r"食欲が(全く|まったく)な"],
        "label": {"en": "not eating", "ja": "食事がとれていない"},
    },
    "not_sleeping": {
        "en": [r"\bhaven'?t slept (in|for)", r"\bcan'?t sleep at all",
               r"\bawake all night"],
        "ja": [r"眠れて(いな|な)", r"一睡もできな"],
        "label": {"en": "not sleeping", "ja": "眠れていない"},
    },
    "pain_worse": {
        "en": [r"\bpain is (getting )?worse", r"\bhurts more than"],
        "ja": [r"痛みが(ひどく|強く)なって"],
        "label": {"en": "pain getting worse", "ja": "痛みの悪化"},
    },
    "very_low": {
        "en": [r"\b(so|very|terribly) lonely", r"\bnobody (comes|visits|cares)",
               r"\bfeel (so )?(hopeless|worthless)", r"\bcrying all"],
        "ja": [r"とても(寂し|さみし)", r"誰も来て", r"むなしい", r"泣いて"],
        "label": {"en": "low mood or loneliness", "ja": "気分の落ち込み・孤独"},
    },
    "fever": {
        "en": [r"\b(burning up|high temperature|fever)", r"\bshivering\b"],
        "ja": [r"熱が(ある|高)", r"発熱", r"寒気"],
        "label": {"en": "possible fever", "ja": "発熱の可能性"},
    },
    "vomiting": {
        "en": [r"\b(been sick|vomit(ing|ed)?|throwing up)",
               r"\bcan'?t keep anything down"],
        "ja": [r"吐いて", r"嘔吐", r"戻して"],
        "label": {"en": "vomiting", "ja": "嘔吐"},
    },
}

# Said *about* something else, these are not the resident reporting a symptom.
# "My husband had a fall last year" must not page the family.
_NOT_NOW = [
    r"\blast (year|month|week)\b", r"\byears? ago\b", r"\bused to\b",
    r"\bmy (husband|wife|friend|sister|brother|mother|father)\b",
    r"\bon (tv|the news)\b", r"\bdream(ed|t)?\b",
    r"去年", r"昔", r"前に", r"夫が", r"妻が", r"友達が", r"テレビ",
]


# Speech-to-text writes "cannot" and "do not" where a person would type
# "can't" and "don't", so the text is normalised before matching. Without
# this, "I do not want to live any more" slipped straight past.
_EXPANDED = [
    (r"\bcan\s?not\b", "can't"), (r"\bdo not\b", "don't"),
    (r"\bdoes not\b", "doesn't"), (r"\bdid not\b", "didn't"),
    (r"\bhave not\b", "haven't"), (r"\bhas not\b", "hasn't"),
    (r"\bhad not\b", "hadn't"), (r"\bwill not\b", "won't"),
    (r"\bwould not\b", "wouldn't"), (r"\bcould not\b", "couldn't"),
    (r"\bis not\b", "isn't"), (r"\bare not\b", "aren't"),
    (r"\bwas not\b", "wasn't"), (r"\bi am\b", "i'm"),
]


def _normalise(text):
    low = text.lower().replace("’", "'").replace("‘", "'")
    for pattern, contraction in _EXPANDED:
        low = re.sub(pattern, contraction, low)
    return low


def detect_urgent(text, lang="en"):
    """Spot something worth telling a person about.

    Returns {"kind", "label", "quote", "severity"} or None, where severity is
    "urgent" (tell the family now) or "concern" (a caregiver should know).
    Keyword matching only: fast, free, and unaffected by an API outage --
    exactly the properties an emergency path needs.
    """
    if not text:
        return None
    low = _normalise(text)

    # Someone recounting the past is not someone in trouble now.
    if any(re.search(p, low) for p in _NOT_NOW):
        return None

    # Urgent wins over concern when a sentence contains both.
    for severity, table in (("urgent", URGENT_PATTERNS),
                            ("concern", CONCERN_PATTERNS)):
        for kind, spec in table.items():
            for pattern in spec["en"] + spec["ja"]:
                if re.search(pattern, low):
                    return {"kind": kind,
                            "label": spec["label"].get(lang, spec["label"]["en"]),
                            "quote": text.strip()[:200],
                            "severity": severity}
    return None


# ------------------------------------------------------------- messages ----

def compose(resident_name, label, quote, source, lang="en", when=""):
    """The words a family member actually receives."""
    where = {"checkin": {"en": "during their daily check-in",
                         "ja": "毎日の体調チェック中"},
             "conversation": {"en": "while talking with the assistant",
                              "ja": "会話中"},
             "guardian": {"en": "-- the room was being listened to and this "
                                "was heard out loud",
                          "ja": "（見守り中に聞こえました）"},
             }.get(source, {"en": "", "ja": ""})

    if lang == "ja":
        body = (f"【確認のお願い】{resident_name}さんが{where['ja']}に"
                f"「{label}」を訴えました。\n\n"
                f"ご本人の言葉：「{quote}」\n"
                f"時刻：{when}\n\n"
                "至急ご本人にご連絡ください。緊急の場合は医療機関に連絡してください。\n"
                "（このメッセージは自動送信です。診断ではありません。）")
        subject = f"【確認のお願い】{resident_name}さん - {label}"
    else:
        body = (f"{resident_name} reported {label} {where['en']}.\n\n"
                f"In their words: \"{quote}\"\n"
                f"Time: {when}\n\n"
                "Please check on them now. If this is an emergency, call for "
                "medical help.\n"
                "(Sent automatically by the care assistant. This is not a "
                "diagnosis.)")
        subject = f"Please check on {resident_name} - {label}"
    return subject, body


# ------------------------------------------------------------- channels ----

DISCORD_RED = 0xE01B24        # urgent -- tell the family now
DISCORD_AMBER = 0xE8A33D      # concern -- a caregiver should know
DISCORD_GREY = 0x95A5A6       # test alerts


def _discord_payload(resident, label, quote, source, when, contacts, is_test,
                     severity="urgent"):
    """A Discord embed, so the alert is readable at a glance on a phone."""
    where = {"checkin": "during their daily check-in",
             "conversation": "while talking with the assistant",
             "guardian": "**heard aloud in the room** (nobody pressed anything)"
             }.get(source, "")
    who = ", ".join(
        f"{c['name']}" + (f" ({c['relationship']})" if c.get("relationship") else "")
        for c in contacts) or "nobody listed"

    fields = [{"name": "In their words", "value": f"“{quote[:900]}”"},
              {"name": "When", "value": when or "just now", "inline": True},
              {"name": "Contacts", "value": who[:900], "inline": True}]

    return {
        "username": "Elder Care Assistant",
        # Pings the channel for a real alert; a test stays quiet.
        "content": "" if is_test else "@here",
        "embeds": [{
            "title": ("Test alert" if is_test
                      else f"\U0001F6A8 Please check on {resident}"),
            "description": (f"Reported **{label}** {where}.".strip()
                            if not is_test else
                            "This is a test of the alert system."),
            "color": DISCORD_GREY if is_test else DISCORD_RED,
            "fields": fields,
            "footer": {"text": "Sent automatically by the care assistant. "
                               "Not a diagnosis."},
        }],
    }


def _send_webhook(subject, body, payload):
    """Post the alert to a webhook, shaped for whatever is on the other end.

    Discord and Slack each want their own JSON, and Discord rejects a payload
    it cannot parse -- so the URL decides the shape rather than sending one
    blob and hoping.
    """
    url = config.ALERT_WEBHOOK_URL
    if not url:
        return None

    low = url.lower()
    if "discord.com/api/webhooks" in low or "discordapp.com/api/webhooks" in low:
        data = _discord_payload(
            payload.get("resident", ""), payload.get("label", ""),
            payload.get("quote", ""), payload.get("source", ""),
            payload.get("when", ""), payload.get("contacts", []),
            payload.get("kind") == "test",
            payload.get("severity", "urgent"))
    elif "hooks.slack.com" in low:
        data = {"text": f"*{subject}*\n{body}"}
    else:
        data = {"subject": subject, "body": body, **payload}

    try:
        r = requests.post(url, json=data, timeout=15)
        if r.status_code < 400:
            return "sent"
        return f"failed ({r.status_code}: {r.text[:120]})"
    except requests.exceptions.RequestException as e:
        return f"failed ({e.__class__.__name__})"


def _send_email(to_address, subject, body):
    if not (config.SMTP_HOST and to_address):
        return None
    try:
        msg = EmailMessage()
        msg["From"] = config.ALERT_FROM or config.SMTP_USER
        msg["To"] = to_address
        msg["Subject"] = subject
        msg.set_content(body)

        if config.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(config.SMTP_HOST, 465, timeout=20)
            with server:
                if config.SMTP_USER:
                    server.login(config.SMTP_USER, config.SMTP_PASS)
                server.send_message(msg)
            return "sent"

        server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20)
        with server:
            server.ehlo()
            # Upgrade only if the server offers it. Calling starttls()
            # unconditionally fails outright against servers without TLS,
            # which loses the alert entirely.
            if server.has_extn("starttls"):
                server.starttls()
                server.ehlo()
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASS)
            server.send_message(msg)
        return "sent"
    except Exception as e:                    # noqa: BLE001 - report, never raise
        return f"failed ({e.__class__.__name__})"


def _send_sms(to_number, body):
    if not (config.TWILIO_SID and config.TWILIO_TOKEN
            and config.TWILIO_FROM and to_number):
        return None
    try:
        r = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{config.TWILIO_SID}"
            "/Messages.json",
            auth=(config.TWILIO_SID, config.TWILIO_TOKEN),
            data={"From": config.TWILIO_FROM, "To": to_number,
                  "Body": body[:1500]},
            timeout=20)
        return "sent" if r.status_code < 400 else f"failed ({r.status_code})"
    except requests.exceptions.RequestException as e:
        return f"failed ({e.__class__.__name__})"


def channels_configured():
    return {
        "in_app": True,
        "webhook": bool(config.ALERT_WEBHOOK_URL),
        "email": bool(config.SMTP_HOST),
        "sms": bool(config.TWILIO_SID and config.TWILIO_TOKEN
                    and config.TWILIO_FROM),
    }


# ---------------------------------------------------------------- raise ----

def raise_alert(store, resident, kind, label, quote, source, lang="en",
                severity="urgent"):
    """Record an urgent alert and push it to whoever is contactable.

    Returns the stored alert. Delivery runs on a worker thread: a resident
    saying "my chest hurts" must get an immediate reply from the assistant,
    not wait on an SMTP handshake.
    """
    contacts = store.contacts(resident["id"])
    when = store.now_string() if hasattr(store, "now_string") else ""
    subject, body = compose(resident["name"], label, quote, source, lang, when)

    alert_id = store.add_alert(
        resident_id=resident["id"], kind=kind, label=label, quote=quote,
        source=source, subject=subject, body=body,
        contact_count=len(contacts))

    def deliver():
        results = []
        payload = {"resident": resident["name"], "kind": kind,
                   "label": label, "quote": quote, "source": source,
                   "severity": severity,
                   "when": when,
                   "contacts": [{"name": c["name"],
                                 "relationship": c.get("relationship")}
                                for c in contacts]}
        status = _send_webhook(subject, body, payload)
        if status:
            results.append(f"webhook: {status}")

        for c in contacts:
            if c.get("email"):
                st = _send_email(c["email"], subject, body)
                if st:
                    results.append(f"email {c['name']}: {st}")
            if c.get("phone"):
                st = _send_sms(c["phone"], body)
                if st:
                    results.append(f"sms {c['name']}: {st}")

        if not results:
            # Nothing is configured. Say so plainly rather than implying the
            # family was told.
            results.append("not delivered: no email/SMS/webhook configured")
        store.set_alert_delivery(alert_id, "; ".join(results))

    threading.Thread(target=deliver, daemon=True).start()

    return {"id": alert_id, "kind": kind, "label": label, "quote": quote,
            "source": source, "severity": severity,
            "subject": subject, "body": body,
            "contacts": [{"name": c["name"], "phone": c.get("phone"),
                          "relationship": c.get("relationship")}
                         for c in contacts],
            "channels": channels_configured()}
