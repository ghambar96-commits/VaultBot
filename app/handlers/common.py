"""Shared handler helpers: item resolution, HTML escaping, safe replies."""

from __future__ import annotations

import html
import logging
import sqlite3

from ..db import repository as repo
from ..utils.text import TYPE_EMOJI, format_size, format_tags, parse_item_ref, truncate

logger = logging.getLogger(__name__)


def esc(value) -> str:
    return html.escape(str(value or ""), quote=False)


def resolve_item(conn: sqlite3.Connection, user_id: int,
                 args: str | None = None) -> sqlite3.Row | None:
    """Resolve the item a command refers to.

    Priority: explicit numeric id in args -> user's last saved item.
    """
    item_id = parse_item_ref(args.split()[0] if args else None)
    if item_id:
        return repo.get_item(conn, user_id, item_id)
    return repo.get_last_item(conn, user_id)


def split_args(args: str | None, skip_first: bool = False) -> list[str]:
    parts = (args or "").split()
    return parts[1:] if skip_first else parts


def item_title(row: sqlite3.Row) -> str:
    """Short human title for an item."""
    name = row["original_name"] or row["caption"] or row["text"]
    title = truncate(name, 48) or f"آیتم #{row['id']}"
    return title


def _folder_name(conn: sqlite3.Connection, row: sqlite3.Row) -> str | None:
    if not row["folder_id"]:
        return None
    folder = repo.get_folder(conn, row["user_id"], row["folder_id"])
    return folder["name"] if folder else None


def format_save_card(row: sqlite3.Row, folder_name: str | None = None) -> str:
    """The clean, compact card shown right after saving."""
    title = item_title(row)
    lines = [f"✅ ذخیره شد  <b>#{row['id']}</b>", "",
             f"{TYPE_EMOJI.get(row['type'], '📦')} {esc(title)}"]
    if row["tags"]:
        lines.append(f"🏷 {esc(format_tags(row['tags']))}")
    if folder_name:
        lines.append(f"📁 {esc(folder_name)}")
    return "\n".join(lines)


TYPE_NAMES = {
    "text": "متن", "link": "لینک", "photo": "عکس", "video": "ویدیو",
    "document": "سند", "audio": "صوت", "voice": "پیام صوتی",
    "animation": "گیف", "sticker": "استیکر",
}


def item_detail_text(conn: sqlite3.Connection, row: sqlite3.Row) -> str:
    """The full detail page body for one item."""
    star = "⭐ " if row["favorite"] else ""
    lines = [f"{TYPE_EMOJI.get(row['type'], '📦')} <b>{star}آیتم #{row['id']}</b>", ""]
    lines.append(f"🧬 نوع: {TYPE_NAMES.get(row['type'], row['type'])}")
    if row["original_name"]:
        lines.append(f"📄 نام: <code>{esc(row['original_name'])}</code>")
    if row["mime_type"]:
        lines.append(f"⚙️ فرمت: <code>{esc(row['mime_type'])}</code>")
    if row["file_size"]:
        lines.append(f"⚖️ حجم: {format_size(row['file_size'])}")
    if row["caption"]:
        lines.append(f"✍️ کپشن: {esc(truncate(row['caption'], 200))}")
    if row["text"]:
        lines.append(f"📝 متن: {esc(truncate(row['text'], 300))}")
    if row["tags"]:
        lines.append(f"🏷 تگ‌ها: {esc(format_tags(row['tags']))}")
    folder_name = _folder_name(conn, row)
    if folder_name:
        lines.append(f"📁 پوشه: {esc(folder_name)}")
    if row["note"]:
        lines.append(f"📝 یادداشت: {esc(truncate(row['note'], 200))}")
    if row["summary"]:
        lines.append(f"🧠 خلاصه: {esc(truncate(row['summary'], 300))}")
    if row["source_chat_id"] or row["source_message_id"]:
        lines.append(f"↪️ منبع: چت <code>{esc(row['source_chat_id'])}</code>"
                     f" / پیام <code>{esc(row['source_message_id'])}</code>")
    lines.append(f"🕓 ذخیره در: {esc(row['created_at'])}")
    return "\n".join(lines)
