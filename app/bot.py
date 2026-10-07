"""Bot & dispatcher assembly."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from .context import AppContext
from .handlers import (callbacks, commands, delete, folders, notes, quick,
                       reminders, save, search, tags)

logger = logging.getLogger(__name__)


def create_bot(settings) -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(ctx: AppContext) -> Dispatcher:
    """Router order matters: commands & FSM-state handlers first,
    the save catch-all LAST."""
    dp = Dispatcher(storage=MemoryStorage())
    dp.workflow_data["ctx"] = ctx

    dp.include_router(commands.router)
    dp.include_router(search.router)
    dp.include_router(folders.router)
    dp.include_router(tags.router)
    dp.include_router(notes.router)
    dp.include_router(delete.router)
    dp.include_router(reminders.router)
    dp.include_router(quick.router)
    dp.include_router(callbacks.router)
    dp.include_router(save.router)   # catch-all: must stay last
    return dp
