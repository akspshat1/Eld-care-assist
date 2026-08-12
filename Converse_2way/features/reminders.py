"""Voice reminders feature: speak reminder content out loud at scheduled times.

A single daemon thread re-reads active reminders from the DB and lets the
`schedule` library fire them. The thread is started once per process by
start_scheduler() (safe to call every time the reminders page loads).
"""
import threading
import time

import schedule

from core.database import get_active_reminders
from core.tts_client import speak

_scheduler_started = False
_scheduler_lock = threading.Lock()

RESCAN_SECONDS = 60  # how often to re-read reminders from the DB


def _speak_reminder(resident_name, content):
    """The action a scheduled job runs when its time is reached."""
    speak(f"{resident_name}さん、{content}の時間です。")


def _rebuild_schedule():
    """Drop all scheduled jobs and re-register one per currently active reminder.
    This picks up reminders added/edited/deleted since the last scan."""
    schedule.clear()
    for reminder in get_active_reminders():
        schedule.every().day.at(reminder["time"]).do(
            _speak_reminder,
            resident_name=reminder["resident_name"],
            content=reminder["content"],
        )


def _run_loop():
    while True:
        _rebuild_schedule()
        deadline = time.time() + RESCAN_SECONDS
        while time.time() < deadline:
            schedule.run_pending()
            time.sleep(1)


def start_scheduler():
    """Start the background reminder-checking thread once per process."""
    global _scheduler_started
    with _scheduler_lock:
        if not _scheduler_started:
            threading.Thread(target=_run_loop, daemon=True).start()
            _scheduler_started = True
