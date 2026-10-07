"""PHASE 1 — media restore / retrieval.

Real offline integration test of the most important guarantee:
an item saved earlier can be re-sent after a full restart, using ONLY the
SQLite reference (file_id). No network, no files on disk.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from app.db import repository as repo
from app.db.database import connect, init_db
from app.services.item_service import save_message
from app.services.media import MEDIA_SEND_METHODS, resend_item

from conftest import USER_A, USER_B, FakeFile, FakeMessage


def _bot():
    bot = AsyncMock()
    return bot


def test_restore_after_full_restart(tmp_path):
    """save -> close DB -> re-initialize app/repo -> restore via file_id."""
    db = tmp_path / "vault.db"

    # --- first "run": save one of each media type
    conn = connect(db)
    init_db(conn)
    repo.ensure_user(conn, USER_A)
    specs = [
        ("photo", [FakeFile(file_id="PH1", unique="u-ph", mime="image/jpeg", name="a.jpg")]),
        ("video", FakeFile(file_id="VD1", unique="u-vd", mime="video/mp4", name="v.mp4")),
        ("document", FakeFile(file_id="DC1", unique="u-dc", mime="application/pdf",
                              name="Linux.pdf")),
        ("audio", FakeFile(file_id="AU1", unique="u-au", mime="audio/mpeg", name="s.mp3")),
        ("voice", FakeFile(file_id="VO1", unique="u-vo", mime="audio/ogg", name=None)),
        ("animation", FakeFile(file_id="AN1", unique="u-an", mime="video/mp4", name="g.mp4")),
    ]
    for _type, media in specs:
        save_message(conn, FakeMessage(caption="cap", message_id=1, **{_type: media}), USER_A)
    conn.close()

    # --- second "run": brand-new connection & repository over the same DB
    conn2 = connect(db)
    init_db(conn2)
    items = repo.list_items(conn2, USER_A)
    assert len(items) == 6

    for item in items:
        bot = _bot()
        status = asyncio.run(resend_item(bot, item, chat_id=USER_A, user_id=USER_A))
        assert status == "ok", item["type"]
        method_name = MEDIA_SEND_METHODS[item["type"]]
        getattr(bot, method_name).assert_awaited_once()
        # the stored file_id is what gets sent — nothing else
        args, kwargs = getattr(bot, method_name).await_args
        assert USER_A in args and item["telegram_file_id"] in args

    conn2.close()


def test_sticker_and_text_restore(tmp_path):
    db = tmp_path / "v.db"
    conn = connect(db)
    init_db(conn)
    repo.ensure_user(conn, USER_A)

    class Sticker:
        file_id, file_unique_id, file_size = "ST1", "u-st", 100
        mime_type, file_name = None, None
        emoji = "😀"

    save_message(conn, FakeMessage(sticker=Sticker(), message_id=1), USER_A)
    save_message(conn, FakeMessage(text="plain thought", message_id=2), USER_A)

    sticker = repo.list_items(conn, USER_A, item_type="sticker")[0]
    bot = _bot()
    assert asyncio.run(resend_item(bot, sticker, USER_A, USER_A)) == "ok"
    bot.send_sticker.assert_awaited_once()
    _, kw = bot.send_sticker.await_args
    assert "caption" not in kw  # stickers carry no caption

    text_item = repo.list_items(conn, USER_A, item_type="text")[0]
    bot = _bot()
    assert asyncio.run(resend_item(bot, text_item, USER_A, USER_A)) == "text"
    bot.send_message.assert_awaited_once()
    conn.close()


def test_restore_edge_cases(tmp_path):
    db = tmp_path / "v.db"
    conn = connect(db)
    init_db(conn)
    repo.ensure_user(conn, USER_A)
    repo.ensure_user(conn, USER_B)

    # 1) missing item (never existed)
    bot = _bot()
    assert asyncio.run(resend_item(bot, None, USER_A, USER_A)) == "not_found"

    # 2) item of another user -> forbidden, nothing sent
    item_a = save_message(conn, FakeMessage(document=FakeFile(file_id="SECRET", unique="s1"),
                                            message_id=1), USER_A).item
    bot = _bot()
    assert asyncio.run(resend_item(bot, item_a, USER_B, USER_B)) == "forbidden"
    bot.send_document.assert_not_awaited()

    # 3) deleted item cannot be fetched, and even by reference it stays scoped
    repo.soft_delete_item(conn, USER_A, item_a["id"])
    assert repo.get_item(conn, USER_A, item_a["id"]) is None

    # 4) media item with empty/missing file_id
    row_no_fid = dict(item_a)
    row_no_fid["telegram_file_id"] = None
    row_no_fid["deleted"] = 0
    bot = _bot()
    assert asyncio.run(resend_item(bot, row_no_fid, USER_A, USER_A)) == "no_file_id"
    row_no_fid["telegram_file_id"] = "   "
    assert asyncio.run(resend_item(bot, row_no_fid, USER_A, USER_A)) == "no_file_id"

    # 5) unknown media type
    row_unknown = dict(item_a)
    row_unknown["type"] = "hologram"
    bot = _bot()
    assert asyncio.run(resend_item(bot, row_unknown, USER_A, USER_A)) == "unknown_type"
    conn.close()


def test_restore_retries_on_network_error(tmp_path):
    from aiogram.exceptions import TelegramNetworkError

    db = tmp_path / "v.db"
    conn = connect(db)
    init_db(conn)
    repo.ensure_user(conn, USER_A)
    item = save_message(conn, FakeMessage(photo=[FakeFile(file_id="P9", unique="u9",
                                                          mime="image/jpeg", name="x.jpg")],
                                          message_id=1), USER_A).item

    bot = _bot()
    bot.send_photo.side_effect = [TelegramNetworkError(method=None, message="boom"), True]
    status = asyncio.run(resend_item(bot, item, USER_A, USER_A))
    assert status == "ok"
    assert bot.send_photo.await_count == 2
    conn.close()


def test_restore_api_error_is_graceful(tmp_path):
    from aiogram.exceptions import TelegramBadRequest

    db = tmp_path / "v.db"
    conn = connect(db)
    init_db(conn)
    repo.ensure_user(conn, USER_A)
    item = save_message(conn, FakeMessage(document=FakeFile(file_id="GONE", unique="g1"),
                                          message_id=1), USER_A).item

    bot = _bot()
    bot.send_document.side_effect = TelegramBadRequest(method=None,
                                                       message="wrong file identifier")
    assert asyncio.run(resend_item(bot, item, USER_A, USER_A)) == "api_error"
    conn.close()
