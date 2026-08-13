"""Recognising "call my grandson" inside a conversation.

Runs on the resident's own words after each turn. Name and relationship
matching is done locally first -- it is instant, free, and keeps working when
the API is down -- and the model is only consulted when the wording is less
direct ("I'd love to hear Kenji's voice").

What "calling" means here: the app hands the browser a `tel:` link. On a phone
or tablet that opens the dialler with the number ready; on a desktop it opens
whatever handles tel: (Teams, Skype, nothing). There is no telephony provider
wired in, so the app never places a call by itself -- a person always confirms.
"""

import re

import groq_api

# Verbs that mean "put me through", in both languages.
_CALL_WORDS_EN = [
    "call", "phone", "ring", "dial", "speak to", "talk to", "get hold of",
    "put me through", "hear from", "contact",
]
_CALL_WORDS_JA = [
    "電話", "かけて", "つないで", "話したい", "連絡", "呼んで",
]

# Words that mean the opposite -- "don't call", "no need to call".
_NEGATIONS = ["don't", "do not", "no need", "not now", "later", "しないで",
              "いらない", "あとで"]


def _wants_call(text):
    low = text.lower()
    if any(n in low for n in _NEGATIONS):
        return False
    return (any(w in low for w in _CALL_WORDS_EN)
            or any(w in text for w in _CALL_WORDS_JA))


def _match_contact(text, contacts):
    """Find a contact by name or relationship. Longest match wins."""
    low = text.lower()
    best, best_len = None, 0

    for c in contacts:
        for field in ("name", "relationship"):
            value = (c.get(field) or "").strip().lower()
            if not value:
                continue
            # Whole words only, so "ken" does not match "kitchen".
            for token in [value] + value.split():
                if len(token) < 3:
                    continue
                if re.search(rf"\b{re.escape(token)}\b", low) and len(token) > best_len:
                    best, best_len = c, len(token)
    return best


INTENT_SYSTEM = """You decide whether someone is asking to phone a person from
their contact list.

You get what they said and the list of contacts. Reply with the contact id they
want to call, or null.

Say null unless they clearly want a call now. "I miss my daughter" is NOT a
request to call. "Can you get my daughter on the phone" IS.

Return ONLY this JSON: {"contact_id": <id or null>}"""


def detect(text, contacts, use_model=True):
    """Return the contact the resident asked to call, or None.

    `contacts` is a list of dicts from the store.
    """
    if not text or not contacts:
        return None

    if _wants_call(text):
        match = _match_contact(text, contacts)
        if match:
            return match
        # Asked for a call but named nobody: if there is exactly one primary
        # contact, that is the sensible default.
        primary = [c for c in contacts if c.get("is_primary")]
        if len(primary) == 1:
            return primary[0]

    if not use_model:
        return None

    # Indirect phrasing: ask the model, but only when a name is mentioned at
    # all, to avoid a pointless call on every ordinary sentence.
    if not _match_contact(text, contacts):
        return None

    listing = "\n".join(
        f"- id={c['id']}: {c['name']}"
        + (f" ({c['relationship']})" if c.get("relationship") else "")
        for c in contacts)
    try:
        data = groq_api.chat_json(
            INTENT_SYSTEM, f'They said: "{text}"\n\nContacts:\n{listing}',
            max_tokens=80)
        cid = data.get("contact_id")
        if cid is not None:
            for c in contacts:
                if c["id"] == int(cid):
                    return c
    except Exception:                         # noqa: BLE001 - never block a reply
        pass
    return None


def tel_link(phone):
    """A dialable tel: URI. Keeps a leading +, drops formatting."""
    cleaned = re.sub(r"[^\d+]", "", phone or "")
    return f"tel:{cleaned}" if cleaned else ""


def offer_text(contact, lang="en"):
    """What the companion says when it spots a call request."""
    name = contact["name"]
    if lang == "ja":
        return f"{name}さんにお電話しますね。おつなぎします。"
    return f"Let's call {name}. Tap the green button to start the call."
