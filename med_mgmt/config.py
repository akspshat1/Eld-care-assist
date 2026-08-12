"""Configuration for med_mgmt only.

Each app keeps its own config, because each one needs different models --
med_mgmt wants a vision model and a strong text model, another app might want
Whisper or something smaller. Change these freely; nothing else depends on them.

The API key is NOT here. It lives in a shared .env at the repo root so every
app and every teammate uses one key:

    Hackathon/
      .env            <- GROQ_API_KEY=gsk_...   (gitignored, shared)
      med_mgmt/
        config.py     <- this file: med_mgmt's models and settings

A med_mgmt/.env overrides the shared one if you ever need this app on a
different key, and a real environment variable beats both.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _repo_root(start):
    """Folder holding .git -- the boundary of this repo."""
    d = start
    while True:
        if os.path.isdir(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


ROOT = _repo_root(HERE) or os.path.dirname(HERE)

# Checked in order; the first value found for a key wins, and anything already
# in the real environment beats both files.
ENV_PATHS = [os.path.join(HERE, ".env"), os.path.join(ROOT, ".env")]
ENV_PATH = ENV_PATHS[1]            # the shared one, for messages


def _load_dotenv(paths=ENV_PATHS):
    """Read .env files into os.environ.

    Deliberately tiny -- no python-dotenv dependency.
    """
    for path in paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key, value = key.strip(), value.strip()
                    if value[:1] == value[-1:] and value[:1] in ("'", '"'):
                        value = value[1:-1]
                    if key and key not in os.environ:
                        os.environ[key] = value
        except OSError:
            pass                    # a bad .env must not crash the app


_load_dotenv()

# ------------------------------------------------------------------ Groq ----

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_BASE_URL = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

# --- models used by THIS app ---
# Structured extraction from prescription text.
GROQ_TEXT_MODEL = os.environ.get("MED_TEXT_MODEL",
                                 os.environ.get("GROQ_TEXT_MODEL",
                                                "llama-3.3-70b-versatile"))

# Transcribing photos of prescriptions. Must support image input.
# See https://console.groq.com/docs/models -- IDs change over time.
GROQ_VISION_MODEL = os.environ.get("MED_VISION_MODEL",
                                   os.environ.get("GROQ_VISION_MODEL",
                                                  "qwen/qwen3.6-27b"))

# Reading a prescription is extraction, not creative writing.
GROQ_TEMPERATURE = float(os.environ.get("GROQ_TEMPERATURE", "0"))
GROQ_TIMEOUT_SEC = int(os.environ.get("GROQ_TIMEOUT_SEC", "60"))

# Photos are downscaled to this before upload. Groq's free tier allows 8000
# tokens/minute and max_tokens counts against it, so image size matters.
IMAGE_MAX_SIDE = int(os.environ.get("MED_IMAGE_MAX_SIDE", "1200"))


def groq_ready():
    """True when a key looks present. Does not validate it against the API."""
    return bool(GROQ_API_KEY and GROQ_API_KEY.strip())


def missing_key_message():
    return (
        "No Groq API key found. Create a .env file at the repo root "
        f"({ENV_PATH}) containing:\n\n    GROQ_API_KEY=gsk_your_key_here\n\n"
        "Copy .env.example to .env to get started. Free key: "
        "https://console.groq.com/keys"
    )
