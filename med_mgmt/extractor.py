"""Turn a prescription (typed text or a photo) into a structured schedule.

Handles English and Japanese prescriptions. Japanese dosing instructions are
written as set phrases -- 1日3回毎食後, 就寝前, 頓服 -- which map onto specific
times of day, so those mappings are spelled out for the model rather than left
to guesswork.

Nothing here writes to the database. Extraction always returns a draft for a
human to review and correct first: a misread dose is a real-world harm, so the
confirmation step is not optional.
"""

import json

import groq_client

# Default clock times for common instructions. The reviewer can change any of
# them; these only exist so the draft is not empty.
DEFAULT_TIMES = {
    "once_daily": ["08:00"],
    "twice_daily": ["08:00", "20:00"],
    "three_times_daily": ["08:00", "13:00", "19:00"],
    "four_times_daily": ["08:00", "12:00", "16:00", "20:00"],
    "bedtime": ["21:00"],
    "morning": ["08:00"],
}

SYSTEM = """You read prescriptions and medicine labels and return structured JSON.

You handle both English and Japanese (処方箋・お薬手帳・薬袋). Japanese dosing
phrases map to times of day as follows:

  1日1回 = once daily          1日2回 = twice daily
  1日3回 = three times daily   1日4回 = four times daily
  毎食後 = after every meal (3 times: after breakfast, lunch, dinner)
  毎食前 = before every meal (3 times)
  朝食後 = after breakfast (08:00)   昼食後 = after lunch (13:00)
  夕食後 = after dinner (19:00)      就寝前 = before bed (21:00)
  起床時 = on waking (07:00)         食間 = between meals (10:30, 15:30)
  頓服 / 頓用 = as needed (no fixed time -- use an empty times list)
  食後 = after a meal   食前 = before a meal
  ～日分 = number of days supplied (e.g. 14日分 = 14 days)
  錠 = tablet   カプセル = capsule   包/g = powder sachet   mL = liquid

Rules you must follow:
- Extract ONLY what is actually written or clearly visible. Never invent a
  drug, a strength, or a frequency.
- If a field is not stated, use null. Do not guess a plausible value.
- Keep `name` exactly as written (Japanese stays Japanese). Put a romanised or
  English name in `name_en` only if you genuinely recognise the drug,
  otherwise null.
- If the text is not a prescription or you cannot read it, return an empty
  medications list and explain in `warnings`.
- Mark `confidence` per medication and list any field you are unsure about in
  `uncertain_fields`, so a human can check it.
- List EVERY medication on the document, without exception. Work through the
  numbered entries in order (Rp1, Rp2, Rp3, ... / 1), 2), 3) ...) and output
  one object for each, including the last one on the page. A dropped
  medication is the worst failure you can make here.
- As-needed items (頓服 / 頓用 / PRN / "as required") are real medications and
  must be included, with an empty `times` list and `timing` = "as_needed".
  Do not omit them just because they have no fixed clock time.

Return ONLY a JSON object of this exact shape:

{
  "language": "en" | "ja" | "other",
  "medications": [
    {
      "name": "string",
      "name_en": "string or null",
      "strength": "string or null",
      "form": "tablet|capsule|liquid|powder|inhaler|injection|cream|drops|other|null",
      "dose_amount": "string or null",
      "frequency_text": "string as written, or null",
      "times": ["HH:MM", ...],
      "timing": "after_meal|before_meal|with_food|bedtime|on_waking|between_meals|as_needed|anytime|null",
      "duration_days": integer or null,
      "notes": "string or null",
      "confidence": "high|medium|low",
      "uncertain_fields": ["field name", ...]
    }
  ],
  "warnings": ["string", ...]
}"""

USER_TEXT_PROMPT = """Extract every medication from this prescription text.

Return the JSON object described in your instructions and nothing else.

--- PRESCRIPTION TEXT ---
{text}
--- END ---"""

# Photos are handled in two passes. Asking one vision model to both read the
# image AND build the structured schedule proved unreliable -- on a 4-item
# Japanese prescription it returned 2-3 items, silently dropping the rest.
# Transcribing first, then extracting from that text with the stronger text
# model, keeps each step to one job.
TRANSCRIBE_SYSTEM = """You transcribe photographs of documents, exactly.

Return every character you can see, in reading order, preserving line breaks.
Japanese stays in Japanese -- do not translate, romanise, or summarise.
Do not add commentary, headings, explanation, or markdown formatting.
If something is genuinely unreadable, write [unreadable] in its place.

Output the transcription as plain text and nothing else."""

TRANSCRIBE_USER = """Transcribe every line of text in this image, top to bottom.

This is a prescription (処方箋), medicine label, medicine bag (薬袋) or
medication record (お薬手帳). It may be a photo taken at an angle, with glare
or shadows -- read it as carefully as you can.

If the medicines are laid out in a table, keep each row on its own line and
keep that row's drug name, dose, frequency and number of days together, so the
rows do not get mixed up. Include every row, including the last one."""


def _clean(draft):
    """Normalise whatever came back so the UI can rely on its shape."""
    if not isinstance(draft, dict):
        raise groq_client.GroqError("The model returned an unexpected format.")

    meds = draft.get("medications")
    if not isinstance(meds, list):
        meds = []

    cleaned = []
    for m in meds:
        if not isinstance(m, dict) or not m.get("name"):
            continue

        times = m.get("times")
        if not isinstance(times, list):
            times = []
        times = [t for t in (str(x).strip() for x in times) if _valid_time(t)]

        duration = m.get("duration_days")
        if not isinstance(duration, int) or duration <= 0:
            duration = None

        conf = m.get("confidence")
        if conf not in ("high", "medium", "low"):
            conf = "low"

        unc = m.get("uncertain_fields")
        if not isinstance(unc, list):
            unc = []

        cleaned.append({
            "name": str(m["name"]).strip(),
            "name_en": _s(m.get("name_en")),
            "strength": _s(m.get("strength")),
            "form": _s(m.get("form")),
            "dose_amount": _s(m.get("dose_amount")),
            "frequency_text": _s(m.get("frequency_text")),
            "times": sorted(set(times)),
            "timing": _s(m.get("timing")),
            "duration_days": duration,
            "notes": _s(m.get("notes")),
            "confidence": conf,
            "uncertain_fields": [str(u) for u in unc],
        })

    warnings = draft.get("warnings")
    if not isinstance(warnings, list):
        warnings = []

    # A medication with no times and no "as needed" marker cannot be scheduled;
    # flag it so the reviewer notices rather than it silently never firing.
    for m in cleaned:
        if not m["times"] and m["timing"] != "as_needed":
            warnings.append(
                f"No time of day was found for {m['name']} - please set one.")

    lang = draft.get("language")
    if lang not in ("en", "ja", "other"):
        lang = "other"

    return {"language": lang, "medications": cleaned,
            "warnings": [str(w) for w in warnings]}


def _s(v):
    if v is None:
        return None
    v = str(v).strip()
    return v or None


def _valid_time(t):
    if not isinstance(t, str) or len(t) != 5 or t[2] != ":":
        return False
    try:
        h, m = int(t[:2]), int(t[3:])
    except ValueError:
        return False
    return 0 <= h <= 23 and 0 <= m <= 59


def from_text(text, model=None):
    if not text or not text.strip():
        raise groq_client.GroqError("Please paste the prescription text first.")
    draft = groq_client.chat_json(
        SYSTEM, USER_TEXT_PROMPT.format(text=text.strip()), model=model)
    return _clean(draft)


def _shrink(image_bytes, mime, max_side=None):
    """Downscale big phone photos before sending them.

    A 12-megapixel photo costs far more tokens than it adds accuracy, and
    token spend is what trips Groq's rate limit. Text stays legible at 1600px.
    Returns the original bytes unchanged if Pillow is unavailable or the image
    is already small.
    """
    if max_side is None:
        max_side = getattr(groq_client.config, "IMAGE_MAX_SIDE", 1200)
    try:
        from PIL import Image
        import io as _io

        img = Image.open(_io.BytesIO(image_bytes))
        if max(img.size) <= max_side:
            return image_bytes, mime

        img.thumbnail((max_side, max_side), Image.LANCZOS)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        out = _io.BytesIO()
        img.save(out, format="JPEG", quality=88)
        return out.getvalue(), "image/jpeg"
    except Exception:                         # noqa: BLE001
        return image_bytes, mime               # never block on a resize failure


def from_image(image_bytes, mime="image/jpeg", model=None):
    """Photo -> transcription (vision model) -> schedule (text model).

    Returns the transcription too, so the reviewer can see what was actually
    read off the page and catch anything the camera missed.
    """
    image_bytes, mime = _shrink(image_bytes, mime)
    text = groq_client.vision_text(
        TRANSCRIBE_SYSTEM, TRANSCRIBE_USER, image_bytes, mime=mime, model=model)

    if not isinstance(text, str) or not text.strip():
        return {"language": "other", "medications": [],
                "warnings": ["No text could be read from that image. Try a "
                             "sharper, better-lit photo, or type the "
                             "prescription in instead."],
                "transcription": ""}

    draft = from_text(text)
    draft["transcription"] = text.strip()
    return draft
