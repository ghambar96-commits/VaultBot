"""Saving anything the user sends. No file bytes touch the disk."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import Message

from ..context import AppContext
from ..keyboards.inline import item_actions
from ..services.item_service import save_message
from ..utils import messages as M
from .common import format_save_card

logger = logging.getLogger(__name__)
router = Router(name="save")

SUPPORTED = ("text", "photo", "document", "video", "audio",
             "voice", "animation", "sticker")


def _is_supported(message: Message) -> bool:
    if message.text:
        return True
    return any(getattr(message, attr) for attr in SUPPORTED if attr != "text")


@router.message()
async def save_anything(message: Message, ctx: AppContext) -> None:
    """Catch-all handler: whatever reaches this point gets saved."""
    user_id = message.from_user.id if message.from_user else message.chat.id

    if not _is_supported(message):
        await message.answer("🤔 این نوع پیام هنوز پشتیبانی نمی‌شود.")
        return

    try:
        result = save_message(ctx.conn, message, user_id)
    except Exception:
        logger.exception("save failed (user=%s type=%s)", user_id, message.content_type)
        await message.answer(M.ERROR)
        return

    if result.is_duplicate:
        dup = result.duplicate_of
        await message.answer(
            M.DUPLICATE.format(id=dup["id"]),
            reply_markup=item_actions(dup["id"], dup["type"]),
        )
        return

    item = result.item
    await message.answer(
        format_save_card(item),
        reply_markup=item_actions(item["id"], item["type"]),
    )
