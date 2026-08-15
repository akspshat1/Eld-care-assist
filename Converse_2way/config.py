"""Central place for environment variables and shared settings.

Change values here (or in .env) instead of hardcoding them in feature code.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# --- LLM provider settings (Groq now, swappable later) ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")
GROQ_API_BASE = "https://api.groq.com/openai/v1"

# --- Database settings ---
CHROMA_PATH = str(BASE_DIR / "data" / "chroma")
