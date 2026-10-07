"""/search — full-text search with pagination via inline keyboard."""

from __future__ import annotations

import logging
from collections import OrderedDict

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..context import AppContext
from ..db import repository as repo
from ..keyboards.inline import search_results
from ..utils import messages as M
from .states import VaultStates

logger = logging.getLogger(__name__)
router = Router(name="search")

# Remember the last query per user so pagination callbacks can re-run it.
# Single-process bot -> a small in-memory LRU is enough (no Redis).
_LAST_QUERY: "OrderedDict[int, str]" = OrderedDict()
_MAX = 512


def remember_query(user_id: int, query: str) -> None:
    _LAST_QUERY.pop(user_id, None)
    _LAST_QUERY[user_id] = query
    while len(_LAST_QUERY) > _MAX:
        _LAST_QUERY.popitem(last=False)


def _render_results(rows, query: str, page: int, page_size: int):
    """Header with a compact, truncated text list + clickable buttons."""
    import html
    from ..utils.pagination import paginate
    from ..utils.text import format_result_line
    pg = paginate(rows, page, page_size)
    lines = [html.escape(format_result_line(r)) for r in pg.rows]
    header = M.RESULTS.format(q=html.escape(query), total=pg.total)
    if lines:
        header += "\n\n" + "\n".join(lines)
    kb = search_results(pg.rows, pg.page, pg.pages, prefix="open")
    return header, kb


async def run_search(message: Message, ctx: AppContext, query: str) -> None:
    user_id = message.chat.id
    remember_query(user_id, query)
    rows = repo.search_items(ctx.conn, user_id, query, limit=200)
    if not rows:
        await message.answer(M.NO_RESULTS)
        return
    header, kb = _render_results(rows, query, 1, ctx.settings.page_size)
    await message.answer(header, reply_markup=kb)


@router.message(Command("search"))
async def cmd_search(message: Message, ctx: AppContext) -> None:
    args = (message.text or "").split(maxsplit=1)
    query = args[1].strip() if len(args) > 1 else ""
    if not query:
        await message.answer(M.EMPTY_QUERY)
        return
    await run_search(message, ctx, query)


@router.message(VaultStates.waiting_search, F.text & ~F.text.startswith("/"))
async def input_search(message: Message, ctx: AppContext, state: FSMContext) -> None:
    """The 🔎 button flow: next plain text message is the query."""
    await state.clear()
    await run_search(message, ctx, (message.text or "").strip())


@router.callback_query(lambda c: c.data and c.data.startswith("page:open:"))
async def cb_search_page(callback: CallbackQuery, ctx: AppContext) -> None:
    user_id = callback.from_user.id
    query = _LAST_QUERY.get(user_id)
    if not query:
        await callback.answer("نتیجه‌ای در حافظه نبود؛ دوباره /search کنید.", show_alert=True)
        return
    try:
        page = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        page = 1
    rows = repo.search_items(ctx.conn, user_id, query, limit=200)
    header, kb = _render_results(rows, query, page, ctx.settings.page_size)
    if callback.message:
        await callback.message.edit_text(header, reply_markup=kb)
    await callback.answer()
