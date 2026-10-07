"""Basic commands: /start /help /stats /settings /backup /cancel"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from ..context import AppContext
from ..db import repository as repo
from ..db.database import db_size_bytes
from ..services.backup import backup_database
from ..utils import messages as M
from ..utils.text import TYPE_EMOJI, format_size

logger = logging.getLogger(__name__)
router = Router(name="commands")


@router.message(CommandStart())
async def cmd_start(message: Message, ctx: AppContext) -> None:
    user = message.from_user
    repo.ensure_user(ctx.conn, message.chat.id,
                     getattr(user, "username", None))
    await message.answer(M.START)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(M.HELP)


@router.message(Command("stats"))
async def cmd_stats(message: Message, ctx: AppContext) -> None:
    user_id = message.chat.id
    stats = repo.user_stats(ctx.conn, user_id)
    by_type_lines = "\n".join(
        f"{TYPE_EMOJI.get(t, '📦')} {t}: {n}"
        for t, n in sorted(stats["by_type"].items(), key=lambda kv: -kv[1])
    ) or "—"
    await message.answer(M.STATS.format(
        total=f"{stats['total']:,}",
        by_type=by_type_lines,
        size=format_size(stats["total_size"]),
    ))


@router.message(Command("settings"))
async def cmd_settings(message: Message, ctx: AppContext) -> None:
    s = ctx.settings
    ai_state = f"فعال ({ctx.ai.name})" if ctx.ai.enabled else "غیرفعال (بدون کلید API)"
    await message.answer(M.SETTINGS.format(
        ai=ai_state, page=s.page_size, max_mb=s.ai_max_download_mb, db=s.db_path,
    ))


@router.message(Command("storage"))
async def cmd_storage(message: Message, ctx: AppContext) -> None:
    """Show real disk usage, measured from the filesystem."""
    from ..services.storage_usage import format_storage_report, storage_report
    usage = storage_report(ctx.settings)
    await message.answer(format_storage_report(usage))


@router.message(Command("backup"))
async def cmd_backup(message: Message, ctx: AppContext) -> None:
    path = backup_database(ctx.conn, ctx.settings.backup_dir, ctx.settings.backup_keep)
    if path:
        await message.answer(M.BACKUP_DONE.format(name=path.name))
    else:
        await message.answer(M.BACKUP_FAIL)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(M.CANCELLED)


@router.message(Command("dbinfo"))
async def cmd_dbinfo(message: Message, ctx: AppContext) -> None:
    """Small diagnostic: proves how little disk the bot actually uses."""
    size = db_size_bytes(ctx.conn)
    await message.answer(
        f"🗄 حجم دیتابیس: {format_size(size)}\n"
        f"🧹 برای فشرده‌سازی از دستور <code>/vacuumdb</code> استفاده کنید."
    )


@router.message(Command("vacuumdb"))
async def cmd_vacuum(message: Message, ctx: AppContext) -> None:
    from ..db.database import vacuum
    vacuum(ctx.conn)
    await message.answer("🧹 دیتابیس فشرده شد (VACUUM).")
