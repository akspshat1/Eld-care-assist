"""Access control and encryption at rest.

Two different people use this app on the same device, and they need opposite
things. The resident must never meet a login screen -- a lock between an
85-year-old and their companion is a safety problem, not a security feature.
The care team's view is different: it holds health records, phone numbers and
the resident's own words, and it should not be readable by whoever picks the
tablet up.

So: the resident view is always open; the care, family, medicine and report
views require a PIN, if one is configured.

Everything here is opt-in and fails open by design. With no CARE_PIN set the
app behaves exactly as before -- a forgotten PIN must not be able to lock a
caregiver out of a medication schedule mid-demo, let alone mid-shift.

Audio is different: recordings of a resident's voice are encrypted on disk
whenever a key exists, and one is generated automatically on first run.
"""

import os
import hmac
import json
import time
import base64
import hashlib
import secrets
import threading

import config

_lock = threading.Lock()
_sessions = {}                       # token -> expiry timestamp

SESSION_HOURS = 8                    # a care shift


# ------------------------------------------------------------------ PIN ----

def pin_required():
    return bool(config.CARE_PIN and str(config.CARE_PIN).strip())


def _pin_hash(pin, salt):
    """PBKDF2 rather than a bare hash: a 4-digit PIN is trivially brute-forced
    otherwise, and this file may be readable by anyone on the machine."""
    return hashlib.pbkdf2_hmac("sha256", str(pin).encode(), salt, 120_000).hex()


def check_pin(pin):
    if not pin_required():
        return True
    salt = str(config.CARE_PIN).encode()[:8].ljust(8, b"0")
    expected = _pin_hash(config.CARE_PIN, salt)
    given = _pin_hash(pin or "", salt)
    # Constant time, so the comparison cannot be timed to leak the PIN.
    return hmac.compare_digest(expected, given)


def new_session():
    token = secrets.token_urlsafe(24)
    with _lock:
        _sessions[token] = time.time() + SESSION_HOURS * 3600
        # Opportunistic cleanup; this never grows large in practice.
        for t, exp in list(_sessions.items()):
            if exp < time.time():
                _sessions.pop(t, None)
    return token


def valid_session(token):
    if not pin_required():
        return True
    if not token:
        return False
    with _lock:
        expiry = _sessions.get(token)
        if not expiry:
            return False
        if expiry < time.time():
            _sessions.pop(token, None)
            return False
    return True


def end_session(token):
    with _lock:
        _sessions.pop(token, None)


# ----------------------------------------------------------- encryption ----

_LEGACY_KEY_FILE = os.path.join(config.DATA_DIR, ".audio_key")
_fernet = None


def _write_env(key_name, value):
    """Persist a generated secret into the repo-root .env.

    Every secret lives in one gitignored place, so there is a single thing to
    back up and a single thing never to commit.
    """
    path = config.ENV_PATH
    try:
        lines = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                lines = [l.rstrip("\n") for l in fh
                         if not l.strip().startswith(f"{key_name}=")]
        if lines and lines[-1].strip():
            lines.append("")
        lines += [f"# Generated automatically - losing this makes stored "
                  f"recordings unreadable", f"{key_name}={value}"]
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        os.environ[key_name] = value
        return True
    except OSError:
        return False


def _get_fernet():
    """Load the audio key from .env, generating one on first run.

    An older build kept the key in data/.audio_key; if that file is present its
    key is adopted and moved into .env, so recordings encrypted before the
    change still open.
    """
    global _fernet
    if _fernet is not None:
        return _fernet
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return None

    key = (config.AUDIO_KEY or "").strip()

    if not key and os.path.exists(_LEGACY_KEY_FILE):
        try:
            key = open(_LEGACY_KEY_FILE, "rb").read().strip().decode()
            if _write_env("AUDIO_KEY", key):
                os.replace(_LEGACY_KEY_FILE, _LEGACY_KEY_FILE + ".migrated")
        except OSError:
            key = ""

    if not key:
        key = Fernet.generate_key().decode()
        _write_env("AUDIO_KEY", key)

    try:
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:                          # noqa: BLE001 - malformed key
        return None
    config.AUDIO_KEY = key
    return _fernet


ENC_MAGIC = b"ECA1"                   # marks a file this module encrypted


def encrypt_bytes(data):
    f = _get_fernet()
    if f is None or not data:
        return data
    return ENC_MAGIC + f.encrypt(data)


def decrypt_bytes(data):
    """Decrypt if it is ours; pass through anything written before this
    existed, so older recordings keep working."""
    if not data or not data.startswith(ENC_MAGIC):
        return data
    f = _get_fernet()
    if f is None:
        return data
    try:
        return f.decrypt(data[len(ENC_MAGIC):])
    except Exception:                          # noqa: BLE001 - wrong/rotated key
        return data


def is_encrypted(path):
    try:
        with open(path, "rb") as fh:
            return fh.read(len(ENC_MAGIC)) == ENC_MAGIC
    except OSError:
        return False


def encryption_active():
    return _get_fernet() is not None


# ------------------------------------------------------------ retention ----

def purge_old_audio(directory, days):
    """Delete recordings past their retention period.

    Keeping a resident's voice indefinitely is neither necessary nor
    defensible; the readings taken from it are already in the database.
    """
    if not days or days <= 0 or not os.path.isdir(directory):
        return 0
    cutoff = time.time() - days * 86400
    removed = 0
    for root, _dirs, files in os.walk(directory):
        for name in files:
            path = os.path.join(root, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    removed += 1
            except OSError:
                pass
    return removed


def status():
    return {
        "pin_required": pin_required(),
        "audio_encrypted": encryption_active(),
        "retention_days": config.AUDIO_RETENTION_DAYS,
        "active_sessions": len(_sessions),
    }
