"""Entry point:  python -m app.main"""

from __future__ import annotations

import asyncio
import logging
import logging.config

import aiogram

from .ai.base import get_provider
from .bot import create_bot, create_dispatcher
from .config import load_settings
from .context import AppContext
from .db.database import connect, init_db
from .services.tasks import backup_loop, cleanup_loop, reminder_loop

PRIVACY_NOISE = ("magic.eof", "aiogram.event.event", "aiogram.dispatcher.dispatcher")


class PrivacyFilter(logging.Filter):
    """Defense in depth: never let message content reach the logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        # aiogram logs update objects at DEBUG; drop those wholesale.
        return "update=" not in msg and "Update(" not in msg


def setup_logging(level: str, log_file: str = "") -> None:
    """Console always; optional rotating file log (5MB x 3)."""
    handlers: dict = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "std",
            "filters": ["privacy"],
        },
    }
    root_handlers = ["console"]
    if log_file:
        from pathlib import Path
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": log_file,
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "std",
            "filters": ["privacy"],
            "encoding": "utf-8",
        }
        root_handlers.append("file")

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"privacy": {"()": PrivacyFilter}},
        "formatters": {
            "std": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
        },
        "handlers": handlers,
        "root": {"handlers": root_handlers, "level": level},
        "loggers": {
            name: {"level": "WARNING"} for name in PRIVACY_NOISE
        },
    })


async def run() -> None:
    settings = load_settings()
    setup_logging(settings.log_level, settings.log_file)
    logger = logging.getLogger("vaultbot")

    conn = connect(settings.db_path)
    init_db(conn)
    ai = get_provider(settings.ai_provider, settings.ai_api_key, settings.ai_model)
    ctx = AppContext(conn=conn, settings=settings, ai=ai)

    bot = create_bot(settings)
    dp = create_dispatcher(ctx)

    logger.info("VaultBot starting (ai=%s, db=%s)", ai.name, settings.db_path)
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)

    tasks = [
        asyncio.create_task(reminder_loop(bot, ctx), name="reminders"),
        asyncio.create_task(cleanup_loop(settings), name="tmp-cleanup"),
        asyncio.create_task(backup_loop(ctx), name="backup"),
    ]
    try:
        await dp.start_polling(bot)
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        conn.close()
        await bot.session.close()


def main() -> None:
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        pass
    except aiogram.exceptions.TelegramUnauthorizedError:
        logging.getLogger("vaultbot").error("Invalid BOT_TOKEN — check your .env")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
