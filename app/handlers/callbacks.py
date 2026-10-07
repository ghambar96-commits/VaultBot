"""Central inline-keyboard callback router."""

from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from ..context import AppContext
from ..db import repository as repo
from ..keyboards.inline import confirm_delete, folder_picker, item_detail_kb
from ..utils import messages as M
from .common import esc, item_detail_text
from .states import VaultStates

logger = logging.getLogger(__name__)
router = Router(name="callbacks")


def _parse(data: str) -> tuple[str, list[int]]:
    """'setfolder:3:7' -> ('setfolder', [3, 7])"""
    action, *rest = (data or "").split(":")
    ids = []
    for part in rest:
        try:
            ids.append(int(part))
        except ValueError:
            break
    return action, ids


@router.callback_query(lambda c: c.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(lambda c: c.data == "asksearch")
async def cb_ask_search(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(VaultStates.waiting_search)
    await callback.message.answer("🔎 متن جستجو را بفرستید (یا /cancel):")
    await callback.answer()


@router.callback_query(lambda c: c.data and (c.data.startswith("open:")
                                             or c.data.startswith("info:")))
async def cb_open_item(callback: CallbackQuery, ctx: AppContext) -> None:
    _, ids = _parse(callback.data)
    if not ids:
        await callback.answer()
        return
    item = repo.get_item(ctx.conn, callback.from_user.id, ids[0])
    if item is None:
        await callback.answer(M.ITEM_NOT_FOUND, show_alert=True)
        return
    await callback.message.answer(
        item_detail_text(ctx.conn, item),
        reply_markup=item_detail_kb(item["id"], item["type"], bool(item["favorite"])))
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("fav:"))
async def cb_favorite(callback: CallbackQuery, ctx: AppContext) -> None:
    """Toggle the ⭐ favorite flag and refresh the detail view in place."""
    _, ids = _parse(callback.data)
    user_id = callback.from_user.id
    item = repo.toggle_favorite(ctx.conn, user_id, ids[0]) if ids else None
    if item is None:
        await callback.answer(M.ITEM_NOT_FOUND, show_alert=True)
        return
    await callback.answer(M.FAV_ON if item["favorite"] else M.FAV_OFF)
    try:
        await callback.message.edit_text(
            item_detail_text(ctx.conn, item),
            reply_markup=item_detail_kb(item["id"], item["type"], bool(item["favorite"])))
    except Exception:
        logger.debug("could not edit message after fav toggle")


@router.callback_query(lambda c: c.data and c.data.startswith("tag:"))
async def cb_tag(callback: CallbackQuery, state: FSMContext) -> None:
    _, ids = _parse(callback.data)
    await state.set_state(VaultStates.waiting_tag)
    await state.update_data(item_id=ids[0] if ids else None)
    await callback.message.answer(
        f"🏷 تگ‌ها را برای آیتم <b>#{ids[0]}</b> بفرستید "
        f"(مثل <code>#python</code>) یا /cancel:")
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("note:"))
async def cb_note(callback: CallbackQuery, state: FSMContext) -> None:
    _, ids = _parse(callback.data)
    await state.set_state(VaultStates.waiting_note)
    await state.update_data(item_id=ids[0] if ids else None)
    await callback.message.answer(M.NOTE_ASK.format(id=ids[0] if ids else "—"))
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("move:"))
async def cb_move(callback: CallbackQuery, ctx: AppContext) -> None:
    _, ids = _parse(callback.data)
    user_id = callback.from_user.id
    item = repo.get_item(ctx.conn, user_id, ids[0]) if ids else None
    if item is None:
        await callback.answer(M.ITEM_NOT_FOUND, show_alert=True)
        return
    folders = repo.list_folders(ctx.conn, user_id)
    await callback.message.answer(
        f"📦 آیتم <b>#{item['id']}</b> به کدام پوشه برود؟",
        reply_markup=folder_picker(item["id"], folders, item["folder_id"]))
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("setfolder:"))
async def cb_set_folder(callback: CallbackQuery, ctx: AppContext) -> None:
    _, ids = _parse(callback.data)
    if len(ids) < 2:
        await callback.answer()
        return
    item_id, folder_id = ids[0], ids[1] or None
    user_id = callback.from_user.id
    folder = repo.get_folder(ctx.conn, user_id, folder_id) if folder_id else None
    if folder_id and folder is None:
        await callback.answer(M.ITEM_NOT_FOUND, show_alert=True)
        return
    repo.move_item(ctx.conn, user_id, item_id, folder_id)
    if folder:
        await callback.answer(M.MOVED.format(id=item_id, folder=folder["name"]),
                              show_alert=False)
        await callback.message.answer(M.MOVED.format(id=item_id,
                                                     folder=esc(folder["name"])))
    else:
        await callback.answer(M.MOVED_NONE.format(id=item_id))
        await callback.message.answer(M.MOVED_NONE.format(id=item_id))


@router.callback_query(lambda c: c.data and c.data.startswith("newfolderto:"))
async def cb_new_folder_for(callback: CallbackQuery, state: FSMContext) -> None:
    _, ids = _parse(callback.data)
    await state.set_state(VaultStates.waiting_folder_name)
    await state.update_data(item_id=ids[0] if ids else None)
    await callback.message.answer(M.FOLDER_ASK)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("del:"))
async def cb_delete(callback: CallbackQuery) -> None:
    _, ids = _parse(callback.data)
    if not ids:
        await callback.answer()
        return
    await callback.message.answer(M.DELETE_CONFIRM.format(id=ids[0]),
                                  reply_markup=confirm_delete(ids[0]))
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("confirm-del:"))
async def cb_confirm_delete(callback: CallbackQuery, ctx: AppContext) -> None:
    _, ids = _parse(callback.data)
    user_id = callback.from_user.id
    if ids and repo.soft_delete_item(ctx.conn, user_id, ids[0]):
        await callback.message.answer(M.DELETED.format(id=ids[0]))
        await callback.answer("✅")
    else:
        await callback.answer(M.ITEM_NOT_FOUND, show_alert=True)


@router.callback_query(lambda c: c.data and c.data.startswith("resend:"))
async def cb_resend(callback: CallbackQuery, ctx: AppContext, bot: Bot) -> None:
    """Restore the original content using only the stored Telegram reference —
    the file bytes travel Telegram-side, never through our disk."""
    from ..services.media import resend_item
    _, ids = _parse(callback.data)
    user_id = callback.from_user.id
    item = repo.get_item(ctx.conn, user_id, ids[0]) if ids else None
    status = await resend_item(bot, item, callback.message.chat.id, user_id)
    answers = {
        "ok": M.RESENT, "text": M.RESENT,
        "not_found": M.ITEM_NOT_FOUND, "forbidden": M.ITEM_NOT_FOUND,
        "no_file_id": M.RESTORE_NO_FILE, "unknown_type": M.RESTORE_UNKNOWN,
        "api_error": M.RESTORE_API_ERROR,
    }
    alert = status not in ("ok", "text")
    await callback.answer(answers.get(status, M.ERROR), show_alert=alert)


@router.callback_query(lambda c: c.data and c.data.startswith("delrem:"))
async def cb_delete_reminder(callback: CallbackQuery, ctx: AppContext) -> None:
    _, ids = _parse(callback.data)
    if ids and repo.delete_reminder(ctx.conn, callback.from_user.id, ids[0]):
        await callback.answer("🗑 یادآور حذف شد")
        try:
            await callback.message.edit_text("🗑 یادآور حذف شد.")
        except Exception:
            pass
    else:
        await callback.answer(M.ITEM_NOT_FOUND, show_alert=True)
