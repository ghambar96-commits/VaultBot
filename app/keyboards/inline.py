"""Inline keyboard builders. Callback data format is small and strict:
`action:id[:id2]` — everything after the action is an integer id.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

MEDIA_TYPES = {"photo", "video", "document", "audio", "voice", "animation", "sticker"}


def item_actions(item_id: int, item_type: str = "text") -> InlineKeyboardMarkup:
    """Compact action panel shown right after saving an item."""
    iid = str(item_id)
    rows = [
        [InlineKeyboardButton(text="🔎 باز کردن", callback_data=f"open:{iid}")],
        [
            InlineKeyboardButton(text="🏷 تگ", callback_data=f"tag:{iid}"),
            InlineKeyboardButton(text="📁 پوشه", callback_data=f"move:{iid}"),
        ],
        [
            InlineKeyboardButton(text="📝 یادداشت", callback_data=f"note:{iid}"),
            InlineKeyboardButton(text="🗑 حذف", callback_data=f"del:{iid}"),
        ],
    ]
    if item_type in MEDIA_TYPES:
        rows.append([InlineKeyboardButton(text="🔗 بازفرستادن فایل",
                                          callback_data=f"resend:{iid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def item_detail_kb(item_id: int, item_type: str = "text",
                   is_favorite: bool = False) -> InlineKeyboardMarkup:
    """Full action panel for the item detail view."""
    iid = str(item_id)
    fav_label = "⭐ حذف از علاقه‌مندی‌ها" if is_favorite else "⭐ علاقه‌مندی"
    rows = [[InlineKeyboardButton(text=fav_label, callback_data=f"fav:{iid}")]]
    if item_type in MEDIA_TYPES:
        rows[0].append(InlineKeyboardButton(text="🔗 بازفرستادن",
                                            callback_data=f"resend:{iid}"))
    rows += [
        [
            InlineKeyboardButton(text="🏷 تگ", callback_data=f"tag:{iid}"),
            InlineKeyboardButton(text="📁 پوشه", callback_data=f"move:{iid}"),
        ],
        [
            InlineKeyboardButton(text="📝 یادداشت", callback_data=f"note:{iid}"),
            InlineKeyboardButton(text="🔎 جستجو", callback_data="asksearch"),
        ],
        [InlineKeyboardButton(text="🗑 حذف", callback_data=f"del:{iid}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def results_keyboard(rows, page: int, pages: int, prefix: str = "open") -> InlineKeyboardMarkup:
    """Clickable result list + navigation. `prefix` distinguishes result sets
    (search vs recent vs favorites) so pagination callbacks can replay them."""
    from ..utils.text import TYPE_EMOJI, truncate
    buttons = []
    for row in rows:
        title = row["original_name"] or row["caption"] or row["text"] or f"#{row['id']}"
        label = f"{TYPE_EMOJI.get(row['type'], '📦')} {truncate(title, 28)}"
        buttons.append([InlineKeyboardButton(
            text=label, callback_data=f"{prefix}:{row['id']}")])
    nav = _nav_row(page, pages, prefix)
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Backwards-compatible alias (search module used this name first).
search_results = results_keyboard


def folder_picker(item_id: int, folders, current_folder_id: int | None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="🚫 بدون پوشه", callback_data=f"setfolder:{item_id}:0")]]
    for f in folders:
        mark = "✅ " if f["id"] == current_folder_id else ""
        rows.append([InlineKeyboardButton(
            text=f"{mark}📁 {f['name']} ({f['item_count']})",
            callback_data=f"setfolder:{item_id}:{f['id']}")])
    rows.append([InlineKeyboardButton(text="➕ پوشه جدید…", callback_data=f"newfolderto:{item_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_delete(item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله، حذف شود", callback_data=f"confirm-del:{item_id}")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data="noop")],
    ])


def reminder_actions(reminder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 حذف یادآور", callback_data=f"delrem:{reminder_id}")],
    ])


def _nav_row(page: int, pages: int, prefix: str):
    if pages <= 1:
        return []
    row = []
    if page > 1:
        row.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"page:{prefix}:{page - 1}"))
    row.append(InlineKeyboardButton(text=f"صفحه {page}/{pages}", callback_data="noop"))
    if page < pages:
        row.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"page:{prefix}:{page + 1}"))
    return row
