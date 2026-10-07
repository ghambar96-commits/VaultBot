"""Delete / restore (soft delete — restorable, metadata stays searchable)."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from ..context import AppContext
from ..db import repository as repo
from ..keyboards.inline import confirm_delete
from ..utils import messages as M
from .common import item_title, resolve_item

logger = logging.getLogger(__name__)
router = Router(name="delete")


@router.message(Command("delete"))
async def cmd_delete(message: Message, ctx: AppContext) -> None:
    user_id = message.chat.id
    args = (message.text or "").split()[1:]
    item = resolve_item(ctx.conn, user_id, " ".join(args))
    if item is None:
        await message.answer(M.NO_ITEM)
        return
    await message.answer(
        f"🗑 {M.DELETE_CONFIRM.format(id=item['id'])}\n\n«{item_title(item)}»",
        reply_markup=confirm_delete(item["id"]),
    )


@router.message(Command("restore"))
async def cmd_restore(message: Message, ctx: AppContext) -> None:
    user_id = message.chat.id
    parts = (message.text or "").split()[1:]

    if parts and parts[0].lstrip("#").isdigit():
        item_id = int(parts[0].lstrip("#"))
        item = repo.restore_item(ctx.conn, user_id, item_id)
        if item:
            await message.answer(M.RESTORED.format(id=item_id))
        else:
            await message.answer(M.ITEM_NOT_FOUND)
        return

    deleted = repo.list_items(ctx.conn, user_id, include_deleted=True, limit=200)
    deleted = [r for r in deleted if r["deleted"]]
    if not deleted:
        await message.answer(M.TRASH_EMPTY)
        return
    lines = [f"#{r['id']} — {item_title(r)}" for r in deleted[:15]]
    await message.answer(
        "♻️ آیتم‌های حذف‌شده:\n" + "\n".join(lines) +
        "\n\nبرای بازگردانی: <code>/restore شماره</code>"
    )
