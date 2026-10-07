"""Reminder persistence + natural time parsing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db import repository as repo
from app.services.timeparse import parse_reminder_time

from conftest import USER_A, make_text_data

NOW = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)


def test_relative_offsets():
    assert parse_reminder_time("+30m", NOW) == NOW + timedelta(minutes=30)
    assert parse_reminder_time("+2h", NOW) == NOW + timedelta(hours=2)
    assert parse_reminder_time("+1d", NOW) == NOW + timedelta(days=1)


def test_clock_time_today_or_tomorrow():
    future_today = parse_reminder_time("14:30", NOW)
    assert future_today == NOW.replace(hour=14, minute=30, second=0)

    already_passed = parse_reminder_time("08:00", NOW)
    assert already_passed == (NOW + timedelta(days=1)).replace(hour=8, minute=0, second=0)


def test_tomorrow_word_including_persian():
    a = parse_reminder_time("tomorrow 08:00", NOW)
    b = parse_reminder_time("فردا 08:00", NOW)
    assert a == b == (NOW + timedelta(days=1)).replace(hour=8, minute=0, second=0)


def test_exact_datetime():
    dt = parse_reminder_time("2026-12-01 09:00", NOW)
    assert dt == datetime(2026, 12, 1, 9, 0, tzinfo=timezone.utc)


def test_garbage_returns_none():
    for bad in ("", "banana", "99:99", "+5x", "2020-01-01 00:00"):
        assert parse_reminder_time(bad, NOW) is None


def test_reminder_roundtrip(conn):
    item = repo.insert_item(conn, make_text_data(USER_A, "remind me about this", 1))
    repo.add_reminder(conn, USER_A, "2026-10-08T08:00:00Z", item_id=item["id"])

    due = repo.due_reminders(conn, now_iso="2026-10-08T09:00:00Z")
    assert len(due) == 1 and due[0]["item_id"] == item["id"]

    repo.mark_reminder_sent(conn, due[0]["id"])
    assert repo.due_reminders(conn, now_iso="2026-10-09T09:00:00Z") == []
