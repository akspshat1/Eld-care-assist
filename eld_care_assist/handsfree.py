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


def install_hooks(store, system_prompt_fn):
    """Point the imported pipeline at this app's store and prompt."""
    vp = _load()
    if vp is None:
        return False

    def add_message(conversation_id, role, content):
        text = (content or "").strip()
        if not text:
            return                            # never store empty turns
        store.add_message(conversation_id, role, text)

    vp.add_message = add_message
    vp.build_system_prompt = system_prompt_fn
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
