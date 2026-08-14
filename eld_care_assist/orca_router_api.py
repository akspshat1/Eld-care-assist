"""OrcaRouter calls, for report generation from recorded data only.

Used by the daily report, the family digest and the conversation-to-record
extraction -- everything else (the conversation itself, check-in answer
interpretation, call routing) stays on Groq directly (see groq_api.py).

OrcaRouter's API is OpenAI-compatible, same as Groq's, so the request shape
mirrors groq_api.py. If OrcaRouter can't be reached, chat()/chat_json() fall
back to groq_api so a report still gets generated.
"""

import re
import json
import time

import requests

import config
import groq_api


class OrcaRouterError(Exception):
    """Anything that stops us getting a usable answer from OrcaRouter."""


def ready():
    return config.orcarouter_ready()


def _headers():
    return {"Authorization": f"Bearer {config.ORCAROUTER_API_KEY}"}


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


def _raise_for(r):
    if r.status_code == 401:
        raise OrcaRouterError("OrcaRouter rejected the API key.")
    detail = ""
    try:
        detail = r.json().get("error", {}).get("message", "")
    except Exception:                         # noqa: BLE001
        detail = r.text[:300]
    raise OrcaRouterError(f"OrcaRouter error {r.status_code}: {detail}")


def _post_chat(payload, retries_left=1):
    if not config.orcarouter_ready():
        raise OrcaRouterError(config.missing_orcarouter_key_message())
    try:
        r = requests.post(f"{config.ORCAROUTER_BASE_URL}/chat/completions",
                          headers=_headers(), json=payload,
                          timeout=config.TIMEOUT_SEC)
    except requests.exceptions.Timeout:
        raise OrcaRouterError("OrcaRouter timed out.")
    except requests.exceptions.RequestException as e:
        raise OrcaRouterError(f"Could not reach OrcaRouter: {e}")

    if r.status_code == 429:
        wait = _retry_after_seconds(r)
        if wait is not None and wait <= 15 and retries_left:
            time.sleep(wait + 0.5)
            return _post_chat(payload, retries_left - 1)
        raise OrcaRouterError("OrcaRouter rate limit reached.")
    if r.status_code >= 400:
        _raise_for(r)

    try:
        return r.json()["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, ValueError):
        raise OrcaRouterError("Unexpected response from OrcaRouter.")


def _parse_json(content):
    content = groq_api.strip_reasoning(content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(content[start:end + 1])
            except json.JSONDecodeError:
                pass
        raise OrcaRouterError("The model did not return readable JSON.")


def chat(messages, model=None, temperature=0.5, max_tokens=700):
    """Plain text reply. Falls back to Groq if OrcaRouter fails."""
    try:
        return groq_api.strip_reasoning(_post_chat({
            "model": model or config.ORCAROUTER_REPORT_MODEL,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": messages,
        }))
    except OrcaRouterError:
        return groq_api.chat(messages, temperature=temperature, max_tokens=max_tokens)


def chat_json(system, user, temperature=0.0, max_tokens=1200):
    """Reply parsed as a JSON object. Falls back to Groq if OrcaRouter fails."""
    try:
        payload_system = system
        if "json" not in (system + user).lower():
            payload_system = system + "\n\nRespond with a single JSON object."
        content = _post_chat({
            "model": config.ORCAROUTER_REPORT_MODEL,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": payload_system},
                         {"role": "user", "content": user}],
        })
        return _parse_json(content)
    except OrcaRouterError:
        return groq_api.chat_json(system, user, temperature=temperature,
                                  max_tokens=max_tokens)
