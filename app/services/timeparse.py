"""Reminder time parsing (simple, dependency-free) and scheduling helpers."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

REL_RE = re.compile(r"^\+\s*(\d+)\s*([mhd])$", re.IGNORECASE)
TIME_RE = re.compile(r"^\s*(\d{1,2})[:.](\d{2})\s*$")


def parse_reminder_time(raw: str,
                        now: datetime | None = None) -> datetime | None:
    """Parse user-friendly time expressions into an aware UTC datetime.

    Supported forms:
      +30m / +2h / +1d       -> relative offsets
      14:30                  -> today (tomorrow if already passed)
      tomorrow 08:00 / فردا  -> tomorrow at the given time
      2026-01-05 08:00       -> exact datetime
    Returns None when nothing can be parsed.
    """
    now = now or datetime.now(timezone.utc)
    raw = (raw or "").strip()
    if not raw:
        return None

    m = REL_RE.match(raw)
    if m:
        amount, unit = int(m.group(1)), m.group(2).lower()
        delta = {"m": timedelta(minutes=amount),
                 "h": timedelta(hours=amount),
                 "d": timedelta(days=amount)}[unit]
        return now + delta

    low = raw.lower()
    tomorrow_shift = 0
    for word in ("tomorrow", "فردا"):
        if low.startswith(word):
            tomorrow_shift = 1
            low = low[len(word):].strip()
            break

    m = TIME_RE.match(low)
    if m:
        hh, mm = int(m.group(1)), int(m.group(2))
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            return None
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if tomorrow_shift or target <= now:
            target += timedelta(days=1)
        return target

    for fmt in ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt <= now.replace(tzinfo=None):
                continue
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None
