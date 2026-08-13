"""Bridge to the models already built in the sibling apps.

Nothing is reimplemented here: Face_rec's ONNX pipeline and voice_rec's
Japanese speech-emotion model are imported as-is, and med_mgmt's medication
store and prescription reader are reused directly.

Everything loads lazily. voice_rec's model is 1.2 GB and takes ~12 s to load,
so it must not be pulled in at import time.
"""

import os
import sys
import threading

import config

_lock = threading.Lock()
_face = None
_voice = None
_voice_error = None
_med_store = None


def _add_path(path):
    if os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)


# ------------------------------------------------------------------ face --

def face_available():
    return os.path.exists(os.path.join(config.FACE_DIR, "models",
                                       "emotion-ferplus-8.onnx"))


def get_face_engine():
    """Face_rec's YuNet + FER+ pipeline (~34 MB, CPU, ~17 ms/frame)."""
    global _face
    with _lock:
        if _face is None:
            _add_path(config.FACE_DIR)
            from emotion_engine import EmotionEngine
            _face = EmotionEngine(models_dir=os.path.join(config.FACE_DIR, "models"))
        # A still photo is a one-off: no temporal smoothing should carry over.
        _face._ema = None
        return _face


def face_labels():
    _add_path(config.FACE_DIR)
    import emotion_engine
    return emotion_engine.EMOTIONS, emotion_engine.VALENCE, emotion_engine.COLORS


# ----------------------------------------------------------------- voice --

def voice_available():
    return os.path.isdir(os.path.join(config.VOICE_DIR, "models", "ja-ser"))


def get_voice_engine():
    """voice_rec's Japanese speech-emotion model. Raises if unavailable."""
    global _voice, _voice_error
    with _lock:
        if _voice is None and _voice_error is None:
            try:
                _add_path(config.VOICE_DIR)
                from voice_engine import VoiceEngine
                _voice = VoiceEngine(
                    model_dir=os.path.join(config.VOICE_DIR, "models", "ja-ser"))
            except Exception as e:            # noqa: BLE001 - surfaced to the UI
                _voice_error = str(e)
        if _voice_error:
            raise RuntimeError(_voice_error)
        return _voice


def voice_helpers():
    _add_path(config.VOICE_DIR)
    import voice_engine
    return voice_engine


# ----------------------------------------------------------- medications --

def get_med_store():
    """med_mgmt's SQLite medication store, shared with that app."""
    global _med_store
    with _lock:
        if _med_store is None:
            _add_path(config.MED_DIR)
            from med_store import MedStore, DB_PATH
            _med_store = MedStore(DB_PATH)
        return _med_store


def get_med_extractor():
    """med_mgmt's prescription reader (two-pass photo -> schedule)."""
    _add_path(config.MED_DIR)
    import extractor
    return extractor


def status():
    """What is installed, for the UI to show up front."""
    return {
        "face": face_available(),
        "voice": voice_available(),
        "medications": os.path.isdir(config.MED_DIR),
        "groq": config.groq_ready(),
    }
