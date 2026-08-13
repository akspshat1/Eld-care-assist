"""Configuration for the family dashboard.

This app is a *reader*. The care data belongs to eld_care_assist and the
medication data to med_mgmt; both are opened where they already live rather
than copied, so the dashboard is never out of date.

The one thing it writes is contacts, which live in the shared care database so
the resident's conversation app sees the same list.
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

CARE_DIR = os.path.join(ROOT, "eld_care_assist")
MED_DIR = os.path.join(ROOT, "med_mgmt")

CARE_DB = os.path.join(CARE_DIR, "data", "care.db")
MED_DB = os.path.join(MED_DIR, "data", "medications.db")

# --- names eld_care_assist's store.py expects from a module called `config` ---
# That module is imported here to read the care database, and its own
# `import config` resolves to THIS file (it is already in sys.modules under
# that name). Pointing these at the care app's data folder means its audio
# path and default database stay exactly where that app put them.
DATA_DIR = os.path.join(CARE_DIR, "data")
DB_PATH = CARE_DB

ENV_PATHS = [os.path.join(HERE, ".env"), os.path.join(ROOT, ".env")]
ENV_PATH = ENV_PATHS[1]


def _load_dotenv(paths=ENV_PATHS):
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
TEXT_MODEL = os.environ.get("FAM_TEXT_MODEL", "llama-3.3-70b-versatile")
TIMEOUT_SEC = int(os.environ.get("FAM_TIMEOUT_SEC", "60"))

# Thresholds that decide what the family is told about.
LOW_WELLBEING = int(os.environ.get("FAM_LOW_WELLBEING", "40"))
QUIET_HOURS = int(os.environ.get("FAM_QUIET_HOURS", "36"))   # no check-in for this long
MISSED_DOSES_ALERT = int(os.environ.get("FAM_MISSED_DOSES", "2"))


def groq_ready():
    return bool(GROQ_API_KEY and GROQ_API_KEY.strip())


def care_db_exists():
    return os.path.exists(CARE_DB)


def med_db_exists():
    return os.path.exists(MED_DB)
