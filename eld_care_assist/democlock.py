"""An adjustable clock, for demos.

Medicine reminders, "due" doses, day boundaries and the timestamps written to
the database are all decided from the current time -- on the server, not in the
browser. So a demo clock that only moved the on-screen time would change
nothing. This shifts the app's idea of "now" itself.

It works by swapping `datetime` and `date` inside the handful of modules that
ask for the time, for subclasses whose `now()` / `today()` include an offset.
That is deliberately a demo-only mechanism: with the offset at zero (the
default) every call behaves exactly as before, and `reset()` restores real
time.
"""

import datetime as _dt
import threading

_lock = threading.Lock()
_offset = 0.0            # seconds added to real time
_patched = []


def offset():
    return _offset


def now():
    return _dt.datetime.now() + _dt.timedelta(seconds=_offset)


def today():
    return now().date()


def is_shifted():
    return abs(_offset) >= 1


class DemoDateTime(_dt.datetime):
    """datetime whose now() follows the demo offset."""

    @classmethod
    def now(cls, tz=None):
        base = _dt.datetime.now(tz)
        return base + _dt.timedelta(seconds=_offset)

    @classmethod
    def today(cls):
        return cls.now()

    @classmethod
    def utcnow(cls):
        return _dt.datetime.utcnow() + _dt.timedelta(seconds=_offset)


class DemoDate(_dt.date):
    """date whose today() follows the demo offset."""

    @classmethod
    def today(cls):
        d = DemoDateTime.now().date()
        return _dt.date(d.year, d.month, d.day)


def patch(*modules):
    """Point a module's `datetime` / `date` names at the demo versions.

    Only affects modules that did `from datetime import datetime, date`, which
    is how the stores and the server read the clock.
    """
    for m in modules:
        if m is None or m in _patched:
            continue
        if getattr(m, "datetime", None) is _dt.datetime:
            m.datetime = DemoDateTime
        if getattr(m, "date", None) is _dt.date:
            m.date = DemoDate
        _patched.append(m)


def set_offset(seconds):
    global _offset
    with _lock:
        _offset = float(seconds)
    return _offset


def shift(seconds):
    """Move the clock by a relative amount (e.g. +300 for five minutes on)."""
    global _offset
    with _lock:
        _offset += float(seconds)
    return _offset


def set_time(hh, mm, on_today=True):
    """Jump to a wall-clock time today, keeping the real date."""
    global _offset
    real = _dt.datetime.now()
    target = real.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    if not on_today and target < real:
        target += _dt.timedelta(days=1)
    with _lock:
        _offset = (target - real).total_seconds()
    return _offset


def reset():
    return set_offset(0)


def state():
    return {
        "offset_seconds": round(_offset),
        "shifted": is_shifted(),
        "now": now().strftime("%Y-%m-%d %H:%M:%S"),
        "time": now().strftime("%H:%M"),
        "real_now": _dt.datetime.now().strftime("%H:%M:%S"),
    }
