"""Lightweight background loops (single-process asyncio, no external queue).

  - reminder checker   : every 30s
  - tmp cleanup sweep  : every 15 minutes
  - scheduled backup   : every BACKUP_INTERVAL_HOURS
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from ..config import Settings
from ..db import repository as repo
from .backup import backup_database
from .cleanup import cleanup_tmp

logger = logging.getLogger(__name__)


async def reminder_loop(bot: Bot, ctx) -> None:
    from ..utils import messages as M
    while True:
        try:
            due = repo.due_reminders(ctx.conn)
            for rem in due:
                lines = [M.REMINDER_DUE]
                if rem["message"]:
                    lines.append(rem["message"])
                if rem["item_id"]:
                    item = repo.get_item(ctx.conn, rem["user_id"], rem["item_id"])
                    if item:
                        name = item["original_name"] or item["caption"] or item["text"] or ""
                        lines.append(f"📌 آیتم #{item['id']}: {name[:80]}")
                try:
                    await bot.send_message(rem["user_id"], "\n".join(lines))
                except Exception:
                    logger.exception("could not deliver reminder %s", rem["id"])
                repo.mark_reminder_sent(ctx.conn, rem["id"])
        except Exception:
            logger.exception("reminder loop error")
        await asyncio.sleep(30)


async def cleanup_loop(settings: Settings) -> None:
    while True:
        try:
            cleanup_tmp(settings.tmp_dir, settings.tmp_max_age_minutes,
                        max_total_mb=128)
        except Exception:
            logger.exception("cleanup loop error")
        await asyncio.sleep(15 * 60)


async def backup_loop(ctx) -> None:
    settings: Settings = ctx.settings
    while True:
        await asyncio.sleep(settings.backup_interval_hours * 3600)
        try:
            backup_database(ctx.conn, settings.backup_dir, settings.backup_keep)
        except Exception:
            logger.exception("scheduled backup error")
