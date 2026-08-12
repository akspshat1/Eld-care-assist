"""Minimal Groq client.

Groq's API is OpenAI-compatible, so plain HTTP is enough -- no extra SDK
dependency to drift out of date.

The shared config lives at the repo root; this finds it by walking up from
here, so no PYTHONPATH juggling is needed.
"""

import os
import re
import json
import time
import base64

import requests

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_config():
    """Import med_mgmt's own config.py, which sits next to this file.

    Loaded by path rather than a plain `import config` so it cannot be
    shadowed by an unrelated config module elsewhere on sys.path.
    """
    import importlib.util

    cfg_path = os.path.join(HERE, "config.py")
    if not os.path.exists(cfg_path):
        raise FileNotFoundError(
            f"config.py not found at {cfg_path}. It belongs in the med_mgmt "
            "folder and is tracked in git -- try 'git checkout "
            "med_mgmt/config.py'. Your API key goes in .env at the repo root "
            "(copy .env.example)."
        )

    spec = importlib.util.spec_from_file_location("med_mgmt_config", cfg_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


config = _load_config()


class GroqError(Exception):
    """Anything that stops us getting a usable answer from Groq."""


class GroqJSONError(GroqError):
    """Groq's json_object mode rejected the model's output.

    Intermittent, and recoverable: Groq returns the text it tried to produce,
    which is usually valid JSON anyway, and failing that we can ask again
    without the server-side constraint.
    """

    def __init__(self, message, failed_generation=None):
        super().__init__(message)
        self.failed_generation = failed_generation


def ready():
    return config.groq_ready()


def missing_key_message():
    return config.missing_key_message()


def _retry_after_seconds(r):
    """How long Groq says to wait, from the header or the message text."""
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


def _post(payload, _retries_left=1):
    if not config.groq_ready():
        raise GroqError(config.missing_key_message())

    try:
        r = requests.post(
            f"{config.GROQ_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {config.GROQ_API_KEY}",
                     "Content-Type": "application/json"},
            json=payload,
            timeout=config.GROQ_TIMEOUT_SEC,
        )
    except requests.exceptions.Timeout:
        raise GroqError("Groq timed out. Check your connection and try again.")
    except requests.exceptions.RequestException as e:
        raise GroqError(f"Could not reach Groq: {e}")

    if r.status_code == 401:
        raise GroqError("Groq rejected the API key. Check GROQ_API_KEY in config.py.")
    if r.status_code == 404:
        raise GroqError(
            f"Model '{payload.get('model')}' is not available on your Groq account. "
            "Model IDs change over time -- see the Settings tab for the list your "
            "key can actually use, then update config.py."
        )
    if r.status_code == 429:
        # Groq's free tier is easy to hit. It tells us how long to wait, so
        # wait it out once rather than bouncing the error straight at the user.
        wait = _retry_after_seconds(r)
        if wait is not None and wait <= 15 and _retries_left:
            time.sleep(wait + 0.5)
            return _post(payload, _retries_left - 1)
        detail = f" Try again in about {int(wait)}s." if wait else ""
        raise GroqError("Groq rate limit reached." + detail)
    if r.status_code >= 400:
        detail, failed = "", None
        try:
            err = r.json().get("error", {})
            detail = err.get("message", "")
            # When json_object mode rejects the output, Groq hands back the
            # text it tried to produce. It is often perfectly parseable.
            failed = err.get("failed_generation")
        except Exception:                     # noqa: BLE001
            detail = r.text[:300]
        if failed or "failed to validate json" in detail.lower():
            raise GroqJSONError(detail or "JSON validation failed",
                                failed_generation=failed)
        raise GroqError(f"Groq error {r.status_code}: {detail}")

    try:
        return r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError):
        raise GroqError("Unexpected response shape from Groq.")


def list_models():
    """Model IDs this key can actually use -- handy when a default 404s."""
    if not config.groq_ready():
        raise GroqError(config.missing_key_message())
    try:
        r = requests.get(
            f"{config.GROQ_BASE_URL}/models",
            headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
            timeout=config.GROQ_TIMEOUT_SEC,
        )
        r.raise_for_status()
        return sorted(m["id"] for m in r.json().get("data", []))
    except requests.exceptions.RequestException as e:
        raise GroqError(f"Could not list models: {e}")


STRICT_SUFFIX = ("\n\nReply with ONLY the JSON object. No prose before or "
                 "after it, no markdown code fence, no explanation.")


def _post_json(payload):
    """POST expecting JSON back, surviving json_object mode's occasional 400.

    Three chances, cheapest first:
      1. normal request
      2. parse the text Groq handed back when it rejected the output
      3. ask again without response_format, and parse it ourselves
    """
    try:
        return _parse_json(_post(payload))
    except GroqJSONError as e:
        if e.failed_generation:
            try:
                return _parse_json(e.failed_generation)
            except GroqError:
                pass

        retry = dict(payload)
        retry.pop("response_format", None)
        msgs = [dict(m) for m in retry["messages"]]
        msgs[0] = dict(msgs[0])
        msgs[0]["content"] = msgs[0]["content"] + STRICT_SUFFIX
        retry["messages"] = msgs
        return _parse_json(_post(retry))


def chat_json(system, user, model=None):
    """Ask for a JSON object back and parse it."""
    return _post_json({
        "model": model or config.GROQ_TEXT_MODEL,
        "temperature": config.GROQ_TEMPERATURE,
        "max_tokens": 4096,          # headroom: truncation produces broken JSON
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    })


def vision_text(system, user_text, image_bytes, mime="image/jpeg", model=None):
    """Send one image, get plain text back.

    Deliberately NOT json_object mode. Transcription is a blob of text, and
    wrapping it in JSON only added a failure mode: when the model's output
    failed Groq's JSON validation, the retry re-uploaded the whole image.
    Between that and the 429 retry, a single photo could be sent four times --
    slow, and the fastest possible way to hit the rate limit.

    One image, one upload, no retry.
    """
    if len(image_bytes) > 19 * 1024 * 1024:   # Groq's limit is 20 MB
        raise GroqError("That image is too large. Please use one under 20 MB.")

    b64 = base64.b64encode(image_bytes).decode()
    payload = {
        "model": model or config.GROQ_VISION_MODEL,
        "temperature": config.GROQ_TEMPERATURE,
        # Groq counts max_tokens against the per-minute token budget (8000 TPM
        # on the free tier), so this stays tight. With reasoning off a full
        # prescription transcribes in ~250 tokens.
        "max_tokens": 1600,
        # The decisive setting. Left to think, this model burns thousands of
        # tokens reasoning before answering -- which blew the whole TPM budget
        # on one photo and often never closed its <think> block.
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
        # One retry is allowed, and only for a 429: a rate-limited request is
        # rejected outright, so nothing was spent and waiting it out is free.
        # There is no JSON-validation retry here at all -- that was the path
        # that used to re-upload the same photo several times.
        content = _post(payload, _retries_left=1)
    except GroqError as e:
        # Not every model accepts reasoning_effort. Retry once without it,
        # with room for the thinking it will then do.
        if "reasoning_effort" not in str(e):
            raise
        payload.pop("reasoning_effort")
        payload["max_tokens"] = 4000
        content = _post(payload, _retries_left=0)
    return strip_reasoning(content)


_THINK_RE = re.compile(r"<think>.*?</think>", re.S | re.I)
_OPEN_THINK_RE = re.compile(r"<think>.*", re.S | re.I)


def strip_reasoning(text):
    """Remove a reasoning model's <think> block from its answer.

    Groq's reasoning_format='hidden' drops the answer along with the
    reasoning, so the block is removed here instead. An unclosed <think> means
    the response was truncated mid-thought -- there is no answer to keep.
    """
    if not isinstance(text, str):
        return text
    cleaned = _THINK_RE.sub("", text)
    if "<think>" in cleaned.lower():
        cleaned = _OPEN_THINK_RE.sub("", cleaned)
    return cleaned.strip()


def _parse_json(content):
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Some models wrap JSON in prose or a code fence despite json mode.
        start, end = content.find("{"), content.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(content[start:end + 1])
            except json.JSONDecodeError:
                pass
        raise GroqError("The model did not return readable JSON. Please try again.")
