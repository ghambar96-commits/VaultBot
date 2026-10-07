"""Reminders: /remind [item_id] <time> and /reminders"""

from __future__ import annotations

import logging
from datetime import timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from ..context import AppContext
from ..db import repository as repo
from ..keyboards.inline import reminder_actions
from ..services.timeparse import parse_reminder_time
from ..utils import messages as M

logger = logging.getLogger(__name__)
router = Router(name="reminders")


@router.message(Command("remind"))
async def cmd_remind(message: Message, ctx: AppContext) -> None:
    user_id = message.chat.id
    split = (message.text or "").split(maxsplit=1)
    args = split[1] if len(split) > 1 else ""
    parts = args.split(maxsplit=1) if args else []

    item = None
    time_expr = args
    if parts and parts[0].lstrip("#").isdigit():
        item = repo.get_item(ctx.conn, user_id, int(parts[0].lstrip("#")))
        time_expr = parts[1] if len(parts) > 1 else ""
    if item is None:
        item = repo.get_last_item(ctx.conn, user_id)

    when = parse_reminder_time(time_expr)
    if when is None:
        await message.answer(M.REMINDER_BAD_TIME)
        return

    when_utc = when.astimezone(timezone.utc)
    rid = repo.add_reminder(
        ctx.conn, user_id,
        remind_at=when_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        item_id=item["id"] if item else None,
    )
    shown = when_utc.strftime("%Y-%m-%d %H:%M UTC")
    text = M.REMINDER_SET.format(id=item["id"] if item else "—", time=shown)
    await message.answer(text, reply_markup=reminder_actions(rid))


@router.message(Command("reminders"))
async def cmd_reminders(message: Message, ctx: AppContext) -> None:
    rows = repo.list_reminders(ctx.conn, message.chat.id)
    if not rows:
        await message.answer(M.NO_REMINDERS)
        return
    lines = "\n".join(
        f"⏰ {r['remind_at']}" + (f" — آیتم #{r['item_id']}" if r["item_id"] else "")
        for r in rows
    )
    await message.answer(M.REMINDERS_LIST.format(items=lines))
