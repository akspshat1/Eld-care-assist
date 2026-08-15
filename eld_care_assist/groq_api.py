"""Groq calls: chat, JSON chat, vision transcription, speech-to-text.

Groq's API is OpenAI-compatible, so plain HTTP is enough. Error handling here
carries over what the medication app learned the hard way:

  * max_tokens counts against the per-minute token budget as a reservation,
    so it stays tight;
  * reasoning models burn thousands of tokens thinking unless told not to;
  * a 429 means the request was rejected, so waiting it out costs nothing.
"""

import re
import io
import json
import time
import base64

import requests

import config


class GroqError(Exception):
    """Anything that stops us getting a usable answer from Groq."""


def ready():
    return config.groq_ready()


def missing_key_message():
    return config.missing_key_message()


def _headers():
    return {"Authorization": f"Bearer {config.GROQ_API_KEY}"}


def _retry_after_seconds(r):
    raw = r.headers.get("retry-after")
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    try:
        msg = r.json().get("error", {}).get("message", "")
    except Exception:                         # noqa: BLE001
        return None
    m = re.search(r"try again in ([\d.]+)\s*s", msg, re.I)
    return float(m.group(1)) if m else None


def _raise_for(r, payload=None):
    if r.status_code == 401:
        raise GroqError("Groq rejected the API key. Check GROQ_API_KEY in .env.")
    if r.status_code == 404:
        model = (payload or {}).get("model", "the model")
        raise GroqError(
            f"Model '{model}' is not available on your Groq account. Model IDs "
            "change over time -- check https://console.groq.com/docs/models "
            "and update .env."
        )
    detail = ""
    try:
        detail = r.json().get("error", {}).get("message", "")
    except Exception:                         # noqa: BLE001
        detail = r.text[:300]
    raise GroqError(f"Groq error {r.status_code}: {detail}")


# Models that think before answering. Their reasoning is billed against
# max_tokens, so a budget sized for a plain model runs out mid-thought and the
# reply arrives truncated -- in JSON mode that surfaces as a 400 that reads
# like a prompt problem. Keeping the reasoning short fixes both.
_REASONING_HINTS = ("gpt-oss", "qwen3", "deepseek-r1", "o1", "o3")


def _is_reasoning_model(model):
    m = (model or "").lower()
    return any(h in m for h in _REASONING_HINTS)


def _prepare(payload):
    """Adjust a payload for whichever model is actually configured."""
    if _is_reasoning_model(payload.get("model")):
        # "none" is rejected by gpt-oss ("must be low, medium or high"); low is
        # the least it will accept.
        payload.setdefault("reasoning_effort", "low")
        # Leave room for the thinking as well as the answer.
        if payload.get("max_tokens"):
            floor = 1200 if "response_format" in payload else 900
            payload["max_tokens"] = max(payload["max_tokens"], floor)
    return payload


def _post_chat(payload, retries_left=1):
    if not config.groq_ready():
        raise GroqError(config.missing_key_message())
    payload = _prepare(payload)
    try:
        r = requests.post(f"{config.GROQ_BASE_URL}/chat/completions",
                          headers=_headers(), json=payload,
                          timeout=config.TIMEOUT_SEC)
    except requests.exceptions.Timeout:
        raise GroqError("Groq timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        raise GroqError(f"Could not reach Groq: {e}")

    if r.status_code == 429:
        wait = _retry_after_seconds(r)
        if wait is not None and wait <= 15 and retries_left:
            time.sleep(wait + 0.5)
            return _post_chat(payload, retries_left - 1)
        raise GroqError("Groq rate limit reached."
                        + (f" Try again in about {int(wait)}s." if wait else ""))
    if r.status_code >= 400:
        _raise_for(r, payload)

    try:
        return r.json()["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, ValueError):
        raise GroqError("Unexpected response from Groq.")


_THINK_RE = re.compile(r"<think>.*?</think>", re.S | re.I)
_OPEN_THINK_RE = re.compile(r"<think>.*", re.S | re.I)


def strip_reasoning(text):
    """Remove a reasoning model's <think> block."""
    if not isinstance(text, str):
        return text
    cleaned = _THINK_RE.sub("", text)
    if "<think>" in cleaned.lower():
        cleaned = _OPEN_THINK_RE.sub("", cleaned)
    return cleaned.strip()


def chat(messages, model=None, temperature=0.5, max_tokens=700):
    """Plain text reply."""
    return strip_reasoning(_post_chat({
        "model": model or config.TEXT_MODEL,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": messages,
    }))


def chat_json(system, user, model=None, temperature=0.0, max_tokens=1200):
    """Reply parsed as a JSON object.

    Groq rejects json_object mode unless the literal word "json" appears
    somewhere in the messages, with a 400 that reads like a prompt problem.
    Rather than rely on every caller remembering, it is ensured here.
    """
    if "json" not in (system + user).lower():
        system = system + "\n\nRespond with a single JSON object."

    content = _post_chat({
        "model": model or config.TEXT_MODEL,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    })
    return _parse_json(content)


def _parse_json(content):
    content = strip_reasoning(content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(content[start:end + 1])
            except json.JSONDecodeError:
                pass
        raise GroqError("The model did not return readable JSON. Please retry.")


def shrink_image(image_bytes, mime="image/jpeg", max_side=None):
    """Downscale big photos before upload; image tokens drive the rate limit."""
    max_side = max_side or config.IMAGE_MAX_SIDE
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        if max(img.size) <= max_side:
            return image_bytes, mime
        img.thumbnail((max_side, max_side), Image.LANCZOS)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=88)
        return out.getvalue(), "image/jpeg"
    except Exception:                         # noqa: BLE001
        return image_bytes, mime


def vision_text(system, user_text, image_bytes, mime="image/jpeg", model=None):
    """Send one image, get plain text back. One upload, no retry on content."""
    image_bytes, mime = shrink_image(image_bytes, mime)
    if len(image_bytes) > 19 * 1024 * 1024:
        raise GroqError("That image is too large. Please use one under 20 MB.")

    b64 = base64.b64encode(image_bytes).decode()
    payload = {
        "model": model or config.VISION_MODEL,
        "temperature": 0.0,
        "max_tokens": 1600,
        # Without this the model spends thousands of tokens thinking and
        # often never closes its <think> block.
        "reasoning_effort": "none",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ]},
        ],
    }
    try:
        return strip_reasoning(_post_chat(payload))
    except GroqError as e:
        if "reasoning_effort" not in str(e):
            raise
        payload.pop("reasoning_effort")
        payload["max_tokens"] = 4000
        return strip_reasoning(_post_chat(payload))


def transcribe(audio_bytes, filename="audio.wav", lang="en"):
    """Speech to text via Groq Whisper.

    The language must match what is actually spoken -- Whisper will happily
    transcribe English as Japanese if told to, producing nonsense.
    """
    if not config.groq_ready():
        raise GroqError(config.missing_key_message())
    try:
        r = requests.post(
            f"{config.GROQ_BASE_URL}/audio/transcriptions",
            headers=_headers(),
            files={"file": (filename, audio_bytes)},
            data={"model": config.WHISPER_MODEL,
                  "language": "ja" if lang == "ja" else "en"},
            timeout=config.TIMEOUT_SEC,
        )
    except requests.exceptions.RequestException as e:
        raise GroqError(f"Could not reach Groq: {e}")

    if r.status_code == 429:
        raise GroqError("Groq rate limit reached. Please try again shortly.")
    if r.status_code >= 400:
        _raise_for(r)
    try:
        return (r.json().get("text") or "").strip()
    except ValueError:
        raise GroqError("Unexpected response from Groq transcription.")
