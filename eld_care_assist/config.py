"""Configuration for eld_care_assist.

Models and settings are app-local; the API key comes from the shared .env at
the repo root so every app in this repo uses one key.

    Hackathon/
      .env                    <- GROQ_API_KEY=gsk_...   (gitignored)
      eld_care_assist/
        config.py             <- this file
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _repo_root(start):
    d = start
    while True:
        if os.path.isdir(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


ROOT = _repo_root(HERE) or os.path.dirname(HERE)

# Sibling apps whose engines and stores we reuse rather than duplicate.
FACE_DIR = os.path.join(ROOT, "Face_rec")
VOICE_DIR = os.path.join(ROOT, "voice_rec")
MED_DIR = os.path.join(ROOT, "med_mgmt")
CONVERSE_DIR = os.path.join(ROOT, "Converse_2way")

ENV_PATHS = [os.path.join(HERE, ".env"), os.path.join(ROOT, ".env")]
ENV_PATH = ENV_PATHS[1]


def _load_dotenv(paths=ENV_PATHS):
    """Read .env files into os.environ. A real env var always wins."""
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
            pass


_load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_BASE_URL = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

# OrcaRouter: used only for report generation from recorded data (daily
# report, family digest, conversation-to-record extraction). Everything
# else keeps using Groq directly. If OrcaRouter is unreachable, those
# call sites fall back to Groq.
ORCAROUTER_API_KEY = os.environ.get("ORCAROUTER_API_KEY", "")
ORCAROUTER_BASE_URL = os.environ.get("ORCAROUTER_BASE_URL", "https://api.orcarouter.ai/v1")
ORCAROUTER_REPORT_MODEL = os.environ.get("ECA_REPORT_MODEL", "orcarouter/auto")

# Conversation, summaries, check-in write-ups.
TEXT_MODEL = os.environ.get("ECA_TEXT_MODEL", "llama-3.3-70b-versatile")
# Reading prescription photos.
VISION_MODEL = os.environ.get("ECA_VISION_MODEL", "qwen/qwen3.6-27b")
# Speech to text.
WHISPER_MODEL = os.environ.get("ECA_WHISPER_MODEL", "whisper-large-v3-turbo")

TIMEOUT_SEC = int(os.environ.get("ECA_TIMEOUT_SEC", "60"))
IMAGE_MAX_SIDE = int(os.environ.get("ECA_IMAGE_MAX_SIDE", "1200"))

DATA_DIR = os.path.join(HERE, "data")
DB_PATH = os.path.join(DATA_DIR, "care.db")

# --- names Converse_2way's modules expect from a module called `config` ---
# Its hands-free voice pipeline is reused as-is (see handsfree.py). Because
# this app's config is already imported as `config`, its `from config import
# GROQ_MODEL, ...` resolves here -- so those names are provided, pointing at
# this app's settings. Without them the import fails outright.
GROQ_MODEL = TEXT_MODEL
GROQ_WHISPER_MODEL = WHISPER_MODEL
GROQ_API_BASE = GROQ_BASE_URL
CHROMA_PATH = os.path.join(DATA_DIR, "chroma")

# --- names fam_dashboard's sources.py expects from a module called `config` ---
# Its alert logic is reused for the Family tab (see family.py), and its
# `import config` resolves here. These point at this app's own data.
FAM_DIR = os.path.join(ROOT, "fam_dashboard")
CARE_DIR = HERE
CARE_DB = DB_PATH
MED_DB = os.path.join(MED_DIR, "data", "medications.db")

# Thresholds for what the family is told about.
LOW_WELLBEING = int(os.environ.get("FAM_LOW_WELLBEING", "40"))
QUIET_HOURS = int(os.environ.get("FAM_QUIET_HOURS", "36"))
MISSED_DOSES_ALERT = int(os.environ.get("FAM_MISSED_DOSES", "2"))


def care_db_exists():
    return os.path.exists(CARE_DB)


def med_db_exists():
    return os.path.exists(MED_DB)


def groq_ready():
    return bool(GROQ_API_KEY and GROQ_API_KEY.strip())


def missing_key_message():
    return (
        "No Groq API key found. Create a .env file at the repo root "
        f"({ENV_PATH}) containing:\n\n    GROQ_API_KEY=gsk_your_key_here\n\n"
        "Free key: https://console.groq.com/keys"
    )


def orcarouter_ready():
    return bool(ORCAROUTER_API_KEY and ORCAROUTER_API_KEY.strip())


def missing_orcarouter_key_message():
    return (
        "No OrcaRouter API key found. Add to the .env file at the repo root "
        f"({ENV_PATH}):\n\n    ORCAROUTER_API_KEY=your_key_here\n\n"
        "Get a key: https://orcarouter.ai/register"
    )
