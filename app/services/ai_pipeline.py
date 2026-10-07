"""Optional AI helpers with a strict temporary-download policy.

If a feature needs the actual bytes of a file (e.g. summarizing a PDF):
  1. download to the tmp dir
  2. process
  3. delete the file immediately (finally-block)
Nothing persistent is ever left behind; `cleanup` sweeps leftovers anyway.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from aiogram import Bot

from ..ai.base import AIProvider
from ..db import repository as repo

logger = logging.getLogger(__name__)


async def summarize_item(bot: Bot, conn: sqlite3.Connection, ai: AIProvider,
                         user_id: int, item_id: int, tmp_dir: Path,
                         max_download_mb: int) -> str | None:
    """Generate and store a summary for an item. Returns the summary or None.

    Text-only items never touch the network/disk. File items are downloaded
    to tmp ONLY if small enough, processed, then deleted.
    """
    if not getattr(ai, "enabled", True):
        return None  # AI disabled -> feature gracefully skipped

    item = repo.get_item(conn, user_id, item_id)
    if item is None:
        return None

    text_source = item["text"] or item["caption"] or ""

    # Plain text / links / captions: summarize directly, zero downloads.
    if item["type"] in ("text", "link") and text_source:
        summary = await ai.summarize(text_source)
        if summary:
            repo.update_item_fields(conn, user_id, item_id, {"summary": summary})
        return summary

    # Documents (PDF etc.): temporary download -> extract text -> delete.
    # Future hook: PDF parsing / OCR / speech-to-text can plug into _extract_text.
    if item["type"] == "document" and item["telegram_file_id"]:
        size_mb = (item["file_size"] or 0) / (1024 * 1024)
        if size_mb > max_download_mb:
            logger.info("skip AI download: item %s exceeds cap", item_id)
            return None
        path = tmp_dir / f"ai_{user_id}_{item_id}_{item['telegram_file_unique_id']}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        try:
            await bot.download(item["telegram_file_id"], destination=str(path))
            extracted = _extract_text(path)
            if extracted:
                summary = await ai.summarize(extracted)
                if summary:
                    repo.update_item_fields(conn, user_id, item_id, {"summary": summary})
                    return summary
        except Exception:
            logger.exception("AI file processing failed for item %s", item_id)
            return None
        finally:
            # ALWAYS remove the temp file, success or failure.
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                logger.warning("could not remove temp file %s", path)
    return None


def _extract_text(path: Path) -> str | None:
    """Extract text from a temporary file. Plain text only in the MVP —
    PDF parsing is a future extension hook (kept out of the MVP on purpose)."""
    try:
        return path.read_text(errors="ignore")[:20000] or None
    except OSError:
        return None


async def suggest_tags(ai: AIProvider, text: str) -> list[str]:
    """Return AI-suggested tags, or [] when AI is disabled/unavailable."""
    try:
        return await ai.generate_tags(text or "")
    except Exception:
        logger.exception("AI tag suggestion failed")
        return []
