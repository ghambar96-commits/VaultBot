"""Media restore / retrieval.

The single most important VaultBot guarantee: an item saved today can be
sent back to its owner at any later time using ONLY the references stored
in SQLite (telegram_file_id). File bytes always travel Telegram-side —
nothing is ever downloaded to this server.

Status codes returned by `resend_item`:
  ok            -> content was sent
  text          -> plain text/link was re-sent as a message
  not_found     -> item is None (deleted / never existed)
  forbidden     -> item belongs to another user (isolation guard)
  no_file_id    -> media item without a usable file_id
  unknown_type  -> type has no known send method
  api_error     -> Telegram API rejected the reference (e.g. expired/invalid)
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3

from aiogram import Bot
from aiogram.exceptions import TelegramNetworkError, TelegramAPIError

logger = logging.getLogger(__name__)

# item.type -> Bot method name. Sticker has no caption support.
MEDIA_SEND_METHODS = {
    "photo": "send_photo",
    "video": "send_video",
    "document": "send_document",
    "audio": "send_audio",
    "voice": "send_voice",
    "animation": "send_animation",
    "sticker": "send_sticker",
}


async def resend_item(bot: Bot, item: sqlite3.Row | dict | None, chat_id: int,
                      user_id: int) -> str:
    """Re-send a stored item using its Telegram references only.

    Never raises for expected failure modes — returns a status code instead.
    Retries once on transient network errors.
    """
    if item is None:
        return "not_found"
    if item["user_id"] != user_id:
        logger.warning("cross-user resend attempt blocked (item=%s)", item["id"])
        return "forbidden"

    kind = item["type"]

    if kind in ("text", "link"):
        payload = item["text"] or item["caption"] or ""
        if not payload:
            return "no_file_id"
        await _with_retry(bot.send_message, chat_id, payload)
        return "text"

    method_name = MEDIA_SEND_METHODS.get(kind)
    if method_name is None:
        logger.warning("unknown media type %r for item %s", kind, item["id"])
        return "unknown_type"

    file_id = item["telegram_file_id"]
    if not file_id or not str(file_id).strip():
        logger.warning("item %s has no file_id (type=%s)", item["id"], kind)
        return "no_file_id"

    kwargs: dict = {}
    if kind != "sticker" and item["caption"]:
        kwargs["caption"] = item["caption"]

    try:
        await _with_retry(getattr(bot, method_name), chat_id, file_id, **kwargs)
        return "ok"
    except TelegramAPIError:
        logger.exception("telegram rejected file reference for item %s", item["id"])
        return "api_error"


async def _with_retry(method, *args, retries: int = 1, delay: float = 0.5, **kwargs):
    """Call a bot method, retrying once on transient network errors only."""
    attempt = 0
    while True:
        try:
            return await method(*args, **kwargs)
        except TelegramNetworkError:
            if attempt >= retries:
                raise
            attempt += 1
            logger.warning("network error, retry %d/%d", attempt, retries)
            await asyncio.sleep(delay)
