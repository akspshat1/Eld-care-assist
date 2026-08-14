"""Hands-free voice conversation, reusing Converse_2way's Pipecat pipeline.

That pipeline is already built and working -- Silero VAD for turn detection,
Groq for STT and the reply, audio straight over WebRTC, no button presses. It
is imported as-is rather than reimplemented.

Two things are redirected so it serves this app instead of Converse_2way's:

  * `add_message`        -> this app's store, so turns land in care.db and
                            appear in the same transcript as typed messages;
  * `build_system_prompt`-> this app's persona prompt, so the companion has
                            the same character and reply-length rules
                            everywhere.

The audio of each spoken turn is also kept, so voice emotion can be run over a
conversation later.
"""

import os
import sys
import asyncio

import config

_pipeline = None
_error = None


def _load():
    """Import Converse_2way's pipeline module once, and patch its hooks."""
    global _pipeline, _error
    if _pipeline is not None or _error is not None:
        return _pipeline

    if not os.path.isdir(config.CONVERSE_DIR):
        _error = ("Converse_2way is not in this repo, so hands-free "
                  "conversation is unavailable.")
        return None
    if config.CONVERSE_DIR not in sys.path:
        sys.path.insert(0, config.CONVERSE_DIR)

    try:
        import core.voice_pipeline as vp
    except Exception as e:                    # noqa: BLE001
        _error = (f"Could not load the hands-free pipeline: {e}. "
                  "Install it with: pip install \"pipecat-ai[webrtc,groq,silero]\"")
        return None

    _pipeline = vp
    return vp


def available():
    return _load() is not None


def error():
    _load()
    return _error


def connection_class():
    _load()
    from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
    return SmallWebRTCConnection


def install_hooks(store, system_prompt_fn, call_offer_fn=None, alert_fn=None):
    """Point the imported pipeline at this app's store and prompt.

    `call_offer_fn(conversation_id, text) -> dict | None` spots a spoken
    request to phone someone. `alert_fn(conversation_id, text) -> dict | None`
    spots an urgent symptom and raises the alert. Both must be wired here as
    well as on the typed path: a hands-free call is exactly when someone is
    most likely to say "my chest hurts" out loud.
    """
    vp = _load()
    if vp is None:
        return False

    # What the last user turn raised, so the app message can carry it.
    pending = {"alert": None}

    def add_message(conversation_id, role, content):
        text = (content or "").strip()
        if not text:
            return                            # never store empty turns
        store.add_message(conversation_id, role, text)

        # Raise urgent alerts here, not in the app-message hook, so help is on
        # its way the moment the words are transcribed.
        if role == "user" and alert_fn:
            try:
                pending["alert"] = alert_fn(conversation_id, text)
            except Exception:                 # noqa: BLE001 - never break the call
                pending["alert"] = None

    def audio_sink(conversation_id, pcm, sample_rate):
        """Keep the recording of a spoken turn, so its tone can be analysed.

        Called straight after the turn's text was stored, so the newest user
        message is the one this audio belongs to.
        """
        message_id = store.last_message_id(conversation_id, "user")
        if message_id and pcm:
            store.save_audio_pcm(conversation_id, message_id, pcm, sample_rate)

    def app_message_hook(conversation_id, role, text):
        """Push anything the transcript alone cannot show to the browser.

        An urgent alert takes precedence over a call offer -- if both somehow
        fire on one turn, the emergency is the thing to put on screen.
        """
        if role != "user":
            return None

        alert = pending.pop("alert", None)
        pending["alert"] = None
        if alert:
            return {"type": "alert", **alert}

        if call_offer_fn:
            offer = call_offer_fn(conversation_id, text)
            if offer:
                return {"type": "call", **offer}
        return None

    vp.add_message = add_message
    vp.build_system_prompt = system_prompt_fn
    vp.audio_sink = audio_sink
    vp.app_message_hook = app_message_hook
    return True


async def start(webrtc_connection, conversation_id, resident, lang="en"):
    """Run one hands-free call until the browser hangs up."""
    vp = _load()
    if vp is None:
        raise RuntimeError(_error or "Hands-free pipeline unavailable.")
    await vp.run_voice_bot(webrtc_connection, conversation_id, resident, lang)


def spawn(webrtc_connection, conversation_id, resident, lang="en"):
    """Fire the call off in the background and return immediately."""
    return asyncio.create_task(
        start(webrtc_connection, conversation_id, resident, lang))
