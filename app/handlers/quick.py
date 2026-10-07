"""Quick daily actions: /recent /random /favorites /fav /emptytrash"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from ..context import AppContext
from ..db import repository as repo
from ..keyboards.inline import item_detail_kb, results_keyboard
from ..utils import messages as M
from ..utils.pagination import paginate
from .common import esc, item_detail_text, item_title, resolve_item

logger = logging.getLogger(__name__)
router = Router(name="quick")

LIST_LIMIT = 100  # hard cap on how many rows a paginated list pre-fetches


def _render_list(rows, page: int, page_size: int, prefix: str, header: str):
    """Same readable layout as search: truncated text list + buttons."""
    from ..utils.text import format_result_line
    pg = paginate(rows, page, page_size)
    lines = "\n".join(esc(format_result_line(r)) for r in pg.rows)
    text = header.format(total=pg.total)
    if lines:
        text += "\n\n" + lines
    kb = results_keyboard(pg.rows, pg.page, pg.pages, prefix=prefix)
    return text, kb


@router.message(Command("recent"))
async def cmd_recent(message: Message, ctx: AppContext) -> None:
    user_id = message.chat.id
    rows = repo.list_items(ctx.conn, user_id, limit=LIST_LIMIT)
    if not rows:
        await message.answer(M.NO_ITEM)
        return
    header, kb = _render_list(rows, 1, ctx.settings.page_size, "recent", M.RECENT)
    await message.answer(header, reply_markup=kb)


@router.callback_query(lambda c: c.data and c.data.startswith("page:recent:"))
async def cb_recent_page(callback: CallbackQuery, ctx: AppContext) -> None:
    page = _page_from(callback)
    rows = repo.list_items(ctx.conn, callback.from_user.id, limit=LIST_LIMIT)
    header, kb = _render_list(rows, page, ctx.settings.page_size, "recent", M.RECENT)
    await callback.message.edit_text(header, reply_markup=kb)
    await callback.answer()


@router.message(Command("favorites"))
async def cmd_favorites(message: Message, ctx: AppContext) -> None:
    user_id = message.chat.id
    rows = repo.list_items(ctx.conn, user_id, favorites_only=True, limit=LIST_LIMIT)
    if not rows:
        await message.answer(M.NO_FAVORITES)
        return
    header, kb = _render_list(rows, 1, ctx.settings.page_size, "fav", M.FAVORITES)
    await message.answer(header, reply_markup=kb)


@router.callback_query(lambda c: c.data and c.data.startswith("page:fav:"))
async def cb_fav_page(callback: CallbackQuery, ctx: AppContext) -> None:
    page = _page_from(callback)
    rows = repo.list_items(ctx.conn, callback.from_user.id, favorites_only=True,
                           limit=LIST_LIMIT)
    header, kb = _render_list(rows, page, ctx.settings.page_size, "fav", M.FAVORITES)
    await callback.message.edit_text(header, reply_markup=kb)
    await callback.answer()


@router.message(Command("random"))
async def cmd_random(message: Message, ctx: AppContext) -> None:
    user_id = message.chat.id
    item = repo.get_random_item(ctx.conn, user_id)
    if item is None:
        await message.answer(M.NO_ITEM)
        return
    await message.answer(
        f"{M.RANDOM}\n\n{item_detail_text(ctx.conn, item)}",
        reply_markup=item_detail_kb(item["id"], item["type"], bool(item["favorite"])))


@router.message(Command("fav"))
async def cmd_fav(message: Message, ctx: AppContext) -> None:
    """/fav [id] — toggle the ⭐ favorite flag (defaults to the last item)."""
    user_id = message.chat.id
    args = (message.text or "").split()[1:]
    item = resolve_item(ctx.conn, user_id, " ".join(args))
    if item is None:
        await message.answer(M.NO_ITEM)
        return
    updated = repo.toggle_favorite(ctx.conn, user_id, item["id"])
    await message.answer((M.FAV_ON if updated["favorite"] else M.FAV_OFF) +
                         f"\n{esc(item_title(updated))}")


@router.message(Command("emptytrash"))
async def cmd_empty_trash(message: Message, ctx: AppContext) -> None:
    """Permanently purge soft-deleted items, then reclaim space."""
    user_id = message.chat.id
    removed = repo.purge_deleted(ctx.conn, user_id)
    if removed:
        from ..db.database import vacuum
        vacuum(ctx.conn)  # only here, never on normal operations
    await message.answer(f"🧹 {removed} آیتم حذف‌شده برای همیشه پاک شد.")


def _page_from(callback: CallbackQuery) -> int:
    try:
        return int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        return 1
