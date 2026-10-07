"""Shared fixtures: a fresh on-disk SQLite DB per test + fake Telegram messages."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import repository as repo          # noqa: E402
from app.db.database import connect, init_db   # noqa: E402

USER_A = 111
USER_B = 222


@pytest.fixture()
def conn(tmp_path):
    c = connect(tmp_path / "test.db")
    init_db(c)
    repo.ensure_user(c, USER_A, "user_a")
    repo.ensure_user(c, USER_B, "user_b")
    yield c
    c.close()


class FakeFile:
    """Minimal stand-in for aiogram media objects."""

    def __init__(self, file_id="f-1", unique="u-1", size=1024,
                 mime="application/pdf", name="file.pdf"):
        self.file_id = file_id
        self.file_unique_id = unique
        self.file_size = size
        self.mime_type = mime
        self.file_name = name


class FakeMessage:
    """Mimics the attributes VaultBot reads from an aiogram Message."""

    def __init__(self, *, text=None, caption=None, photo=None, document=None,
                 video=None, audio=None, voice=None, animation=None, sticker=None,
                 message_id=1, forward_origin=None):
        self.text = text
        self.caption = caption
        self.photo = photo
        self.document = document
        self.video = video
        self.audio = audio
        self.voice = voice
        self.animation = animation
        self.sticker = sticker
        self.message_id = message_id
        self.forward_origin = forward_origin
        self.content_type = "unknown"


def make_text_data(user_id: int, text: str, message_id: int = 1) -> dict:
    """Ready-to-insert dict for a plain text item."""
    return {
        "user_id": user_id,
        "telegram_message_id": message_id,
        "type": "text",
        "text": text,
    }
