"""Saving logic: turn an incoming Telegram message into a vault item.

Core storage rule: file BYTES are never written to disk. We store only
Telegram references (file_id / file_unique_id / message_id) plus metadata.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

from aiogram import types

from ..db import repository as repo
from ..utils.text import extract_urls, looks_like_link_only

logger = logging.getLogger(__name__)

MEDIA_ATTRS = (
    ("document", "document"),
    ("video", "video"),
    ("audio", "audio"),
    ("voice", "voice"),
    ("animation", "animation"),
    ("sticker", "sticker"),
)


@dataclass
class SaveResult:
    item: sqlite3.Row | None
    is_duplicate: bool = False
    duplicate_of: sqlite3.Row | None = None


def _media_field(message: types.Message):
    """Return (type, media_object) for the first media found, else (None, None)."""
    if message.photo:
        return "photo", message.photo[-1]      # biggest size only
    for attr, item_type in MEDIA_ATTRS:
        obj = getattr(message, attr, None)
        if obj is not None:
            return item_type, obj
    return None, None


def build_item_data(message: types.Message, user_id: int) -> dict:
    """Map an aiogram Message to a dict ready for repository.insert_item."""
    item_type, media = _media_field(message)
    data: dict = {
        "user_id": user_id,
        "telegram_message_id": message.message_id,
        "telegram_file_id": None,
        "telegram_file_unique_id": None,
        "type": "text",
        "mime_type": None,
        "original_name": None,
        "file_size": None,
        "caption": message.caption,
        "text": None,
        "source_chat_id": None,
        "source_message_id": None,
    }

    # forwarded message: remember the origin (best effort, privacy-safe)
    origin = getattr(message, "forward_origin", None)
    if origin is not None:
        data["source_message_id"] = getattr(origin, "message_id", None)
        chat = getattr(origin, "chat", None) or getattr(origin, "chat_id", None)
        data["source_chat_id"] = getattr(chat, "id", chat if isinstance(chat, int) else None)

    if media is not None:
        data["type"] = item_type
        data["telegram_file_id"] = media.file_id
        data["telegram_file_unique_id"] = media.file_unique_id
        data["file_size"] = getattr(media, "file_size", None)
        data["mime_type"] = getattr(media, "mime_type", None)
        data["original_name"] = getattr(media, "file_name", None)
        if item_type == "sticker":
            emoji = getattr(media, "emoji", None)
            if emoji:
                data["caption"] = data["caption"] or f"sticker {emoji}"
    elif message.text:
        if looks_like_link_only(message.text):
            data["type"] = "link"
        else:
            data["type"] = "text"
        data["text"] = message.text
        # keep urls searchable in the caption field too
        urls = extract_urls(message.text)
        if urls:
            data["caption"] = "\n".join(urls[:10])

    return data


def save_message(conn: sqlite3.Connection, message: types.Message,
                 user_id: int) -> SaveResult:
    """Save an incoming message; detects duplicates by file_unique_id."""
    data = build_item_data(message, user_id)

    # --- duplicate detection (files only): never re-download, never re-store
    unique_id = data.get("telegram_file_unique_id")
    if unique_id:
        existing = repo.find_duplicate(conn, user_id, unique_id)
        if existing is not None:
            logger.info("duplicate file skipped (unique_id=%s…)", unique_id[:8])
            return SaveResult(item=None, is_duplicate=True, duplicate_of=existing)

    item = repo.insert_item(conn, data)
    return SaveResult(item=item)
