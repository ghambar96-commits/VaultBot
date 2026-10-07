"""Folders: /folders /newfolder /move"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from ..context import AppContext
from ..db import repository as repo
from ..keyboards.inline import folder_picker
from ..utils import messages as M
from .common import esc, resolve_item
from .states import VaultStates

logger = logging.getLogger(__name__)
router = Router(name="folders")


@router.message(Command("folders"))
async def cmd_folders(message: Message, ctx: AppContext) -> None:
    rows = repo.list_folders(ctx.conn, message.chat.id)
    if not rows:
        await message.answer(M.NO_FOLDERS)
        return
    items = "\n".join(
        f"📁 {esc(f['name'])} — {f['item_count']} آیتم (#{f['id']})" for f in rows
    )
    await message.answer(M.FOLDERS_LIST.format(items=items))


@router.message(Command("newfolder"))
async def cmd_new_folder(message: Message, ctx: AppContext, state: FSMContext) -> None:
    args = (message.text or "").split(maxsplit=1)
    if len(args) > 1 and args[1].strip():
        await _create_folder(message, ctx, args[1].strip())
        return
    await state.set_state(VaultStates.waiting_folder_name)
    await message.answer(M.FOLDER_ASK)


@router.message(VaultStates.waiting_folder_name, F.text & ~F.text.startswith("/"))
async def input_folder_name(message: Message, ctx: AppContext, state: FSMContext) -> None:
    name = (message.text or "").strip()
    data = await state.get_data()
    pending_item = data.get("item_id")
    await state.clear()
    folder = await _create_folder(message, ctx, name)
    if folder and pending_item:
        repo.move_item(ctx.conn, message.chat.id, pending_item, folder["id"])
        await message.answer(M.MOVED.format(id=pending_item, folder=esc(folder["name"])))


async def _create_folder(message: Message, ctx: AppContext, name: str):
    name = name[:40]
    folder = repo.create_folder(ctx.conn, message.chat.id, name)
    if folder is None:
        await message.answer(M.FOLDER_EXISTS)
        return None
    await message.answer(M.FOLDER_CREATED.format(name=esc(name)))
    return folder


@router.message(Command("move"))
async def cmd_move(message: Message, ctx: AppContext) -> None:
    user_id = message.chat.id
    args = (message.text or "").split()[1:]

    item = resolve_item(ctx.conn, user_id, " ".join(args))
    if item is None:
        await message.answer(M.NO_ITEM)
        return

    # /move <id> <folder-name…>  -> direct move when a name is given
    if args and args[0].lstrip("#").isdigit() and len(args) > 1:
        folder = repo.find_folder_by_name(ctx.conn, user_id, " ".join(args[1:]))
        if folder:
            repo.move_item(ctx.conn, user_id, item["id"], folder["id"])
            await message.answer(M.MOVED.format(id=item["id"], folder=esc(folder["name"])))
            return

    folders = repo.list_folders(ctx.conn, user_id)
    await message.answer(
        f"📦 آیتم <b>#{item['id']}</b> را به کدام پوشه منتقل کنم؟",
        reply_markup=folder_picker(item["id"], folders, item["folder_id"]),
    )
