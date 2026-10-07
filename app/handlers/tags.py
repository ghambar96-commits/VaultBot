"""Tags: /tag /untag /tags"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from ..context import AppContext
from ..db import repository as repo
from ..utils import messages as M
from ..utils.text import format_tags, parse_item_ref
from .common import esc, resolve_item
from .states import VaultStates

logger = logging.getLogger(__name__)
router = Router(name="tags")


def _parse(args: str | None):
    """Return (item_ref or None, tag-string) from command arguments."""
    parts = (args or "").split()
    item_ref = None
    if parts and parse_item_ref(parts[0]) is not None:
        item_ref = parts[0]
        parts = parts[1:]
    return item_ref, " ".join(parts)


@router.message(Command("tag"))
async def cmd_tag(message: Message, ctx: AppContext, state: FSMContext) -> None:
    user_id = message.chat.id
    split = (message.text or "").split(maxsplit=1)
    item_ref, tag_text = _parse(split[1] if len(split) > 1 else None)

    item = resolve_item(ctx.conn, user_id, item_ref)
    if item is None:
        await message.answer(M.NO_ITEM)
        return

    if not tag_text.strip():
        # When AI is enabled, suggest tags automatically instead of asking.
        if ctx.ai.enabled:
            from ..services.ai_pipeline import suggest_tags
            source = item["text"] or item["caption"] or item["original_name"] or ""
            suggested = await suggest_tags(ctx.ai, source)
            if suggested:
                updated = repo.add_tags(ctx.conn, user_id, item["id"], suggested)
                await message.answer(M.TAG_AI_ADDED.format(
                    id=item["id"], tags=esc(format_tags(updated["tags"]))))
                return
        await state.set_state(VaultStates.waiting_tag)
        await state.update_data(item_id=item["id"])
        await message.answer(f"🏷 تگ‌ها را برای آیتم <b>#{item['id']}</b> بفرستید "
                             f"(مثل <code>#python #project</code>) یا /cancel:")
        return

    updated = repo.add_tags(ctx.conn, user_id, item["id"], tag_text)
    await message.answer(M.TAG_UPDATED.format(id=item["id"],
                                              tags=esc(format_tags(updated["tags"])) or "—"))


@router.message(VaultStates.waiting_tag, F.text & ~F.text.startswith("/"))
async def input_tags(message: Message, ctx: AppContext, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    item_id = data.get("item_id")
    updated = repo.add_tags(ctx.conn, message.chat.id, item_id, message.text or "")
    if updated:
        await message.answer(M.TAG_UPDATED.format(id=item_id,
                                                  tags=esc(format_tags(updated["tags"]))))


@router.message(Command("untag"))
async def cmd_untag(message: Message, ctx: AppContext) -> None:
    user_id = message.chat.id
    split = (message.text or "").split(maxsplit=1)
    item_ref, tag_text = _parse(split[1] if len(split) > 1 else None)
    item = resolve_item(ctx.conn, user_id, item_ref)
    if item is None:
        await message.answer(M.NO_ITEM)
        return
    if not tag_text.strip():
        await message.answer(M.TAG_EMPTY)
        return
    updated = repo.remove_tags(ctx.conn, user_id, item["id"], tag_text)
    await message.answer(M.TAG_UPDATED.format(id=item["id"],
                                              tags=esc(format_tags(updated["tags"])) or "—"))


@router.message(Command("tags"))
async def cmd_tags(message: Message, ctx: AppContext) -> None:
    rows = repo.list_user_tags(ctx.conn, message.chat.id)
    if not rows:
        await message.answer(M.NO_TAGS)
        return
    tags = "  ".join(f"#{esc(r['name'])} ({r['n']})" for r in rows[:60])
    await message.answer(M.TAGS_LIST.format(tags=tags))
