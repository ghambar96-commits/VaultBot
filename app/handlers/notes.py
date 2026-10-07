"""Notes: /note [item_id] text"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from ..context import AppContext
from ..db import repository as repo
from ..utils import messages as M
from .states import VaultStates

logger = logging.getLogger(__name__)
router = Router(name="notes")

NOTE_LIMIT = 2000


@router.message(Command("note"))
async def cmd_note(message: Message, ctx: AppContext, state: FSMContext) -> None:
    user_id = message.chat.id
    split = (message.text or "").split(maxsplit=1)
    args = split[1] if len(split) > 1 else None

    parts = (args or "").split(maxsplit=1)
    if parts and parts[0].lstrip("#").isdigit():
        item = repo.get_item(ctx.conn, user_id, int(parts[0].lstrip("#")))
        note_text = parts[1].strip() if len(parts) > 1 else ""
    else:
        item = repo.get_last_item(ctx.conn, user_id)
        note_text = (args or "").strip()

    if item is None:
        await message.answer(M.NO_ITEM)
        return

    if not note_text:
        await state.set_state(VaultStates.waiting_note)
        await state.update_data(item_id=item["id"])
        await message.answer(M.NOTE_ASK.format(id=item["id"]))
        return

    await _save_note(message, ctx, item["id"], note_text)


@router.message(VaultStates.waiting_note, F.text)
async def input_note(message: Message, ctx: AppContext, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    item_id = data.get("item_id")
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        await message.answer(M.NOTE_EMPTY)
        return
    await _save_note(message, ctx, item_id, text)


async def _save_note(message: Message, ctx: AppContext, item_id: int, text: str) -> None:
    updated = repo.update_item_fields(ctx.conn, message.chat.id, item_id,
                                      {"note": text[:NOTE_LIMIT]})
    if updated is None:
        await message.answer(M.ITEM_NOT_FOUND)
        return
    await message.answer(M.NOTE_SAVED.format(id=item_id))
