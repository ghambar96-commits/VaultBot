"""Offline bot-level integration test.

Feeds real Telegram-format Update objects through the actual dispatcher and
handlers, with the network session mocked out. Proves the main flow works
end-to-end without a bot token or internet access.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.types import Update

from app.ai.base import get_provider
from app.bot import create_dispatcher
from app.config import Settings
from app.context import AppContext
from app.db import repository as repo
from app.db.database import connect, init_db

USER = 555


def _settings(tmp_path) -> Settings:
    return Settings(
        bot_token="123456:TEST", db_path=tmp_path / "t.db",
        tmp_dir=tmp_path / "tmp", backup_dir=tmp_path / "bk",
        admin_ids=frozenset(), page_size=10, ai_provider="none",
        ai_api_key="", ai_model="", ai_max_download_mb=25,
        tmp_max_age_minutes=30, backup_keep=3, backup_interval_hours=24,
        log_level="CRITICAL", log_file="",
    )


def _update(update_id: int, payload: dict) -> Update:
    return Update.model_validate({"update_id": update_id, **payload})


def _cb(update_id: int, data: str, message_id: int = 900) -> Update:
    return Update.model_validate({
        "update_id": update_id,
        "callback_query": {
            "id": f"cb{update_id}",
            "from": {"id": USER, "is_bot": False, "first_name": "Tester"},
            "chat_instance": "x",
            "data": data,
            "message": {
                "message_id": message_id, "date": 1700000000,
                "chat": {"id": USER, "type": "private"},
            },
        },
    })


def _sent_methods(session_mock):
    """All Telegram methods the bot tried to send, in order."""
    return [c.args[1] for c in session_mock.await_args_list if len(c.args) > 1]


def _message(message_id: int, **extra) -> dict:
    return {
        "message": {
            "message_id": message_id,
            "date": 1700000000,
            "chat": {"id": USER, "type": "private"},
            "from": {"id": USER, "is_bot": False, "first_name": "Tester"},
            **extra,
        }
    }


@pytest.fixture(scope="module")
def shared_dp(tmp_path_factory):
    """One dispatcher for the whole module — aiogram routers cannot be
    attached to two dispatchers, so tests swap the ctx instead."""
    settings = _settings(tmp_path_factory.mktemp("dp"))
    conn = connect(settings.db_path)
    init_db(conn)
    dp = create_dispatcher(AppContext(conn=conn, settings=settings,
                                      ai=get_provider("none")))
    yield dp
    conn.close()


@pytest.fixture()
def rig(tmp_path, shared_dp):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    repo.ensure_user(conn, USER)
    shared_dp.workflow_data["ctx"] = AppContext(
        conn=conn, settings=settings, ai=get_provider("none"))

    bot = Bot(token=settings.bot_token)
    bot.session = AsyncMock(return_value=True)      # no network, ever
    yield shared_dp, bot, conn
    conn.close()


def _run(dp, bot, update):
    asyncio.run(dp.feed_update(bot, update))


def test_main_flow_through_dispatcher(rig):
    dp, bot, conn = rig
    calls = bot.session

    # /start
    _run(dp, bot, _update(1, _message(1, text="/start")))
    assert calls.await_count >= 1

    # user sends a plain text -> gets saved
    calls.reset_mock()
    _run(dp, bot, _update(2, _message(2, text="minecraft server config")))
    items = repo.list_items(conn, USER)
    assert len(items) == 1 and items[0]["text"] == "minecraft server config"

    # /search finds it
    calls.reset_mock()
    _run(dp, bot, _update(3, _message(3, text="/search minecraft")))
    sent = [c.args[1] for c in calls.await_args_list]
    assert any("minecraft" in str(getattr(m, "text", "")) for m in sent if hasattr(m, "text"))

    # /tag on the last item
    _run(dp, bot, _update(4, _message(4, text="/tag #gaming")))
    assert repo.get_last_item(conn, USER)["tags"] == "gaming"

    # /note on the last item
    _run(dp, bot, _update(5, _message(5, text="/note remember the port 25565")))
    assert "25565" in repo.get_last_item(conn, USER)["note"]

    # duplicate-ish second save is a distinct text item (fine), then delete it
    _run(dp, bot, _update(6, _message(6, text="second note")))
    last = repo.get_last_item(conn, USER)
    _run(dp, bot, _update(7, _message(7, text=f"/delete {last['id']}")))
    # confirmation keyboard was sent; simulate the confirm callback
    cb = Update.model_validate({
        "update_id": 8,
        "callback_query": {
            "id": "cb1",
            "from": {"id": USER, "is_bot": False, "first_name": "Tester"},
            "chat_instance": "x",
            "data": f"confirm-del:{last['id']}",
            "message": {
                "message_id": 99, "date": 1700000000,
                "chat": {"id": USER, "type": "private"},
            },
        },
    })
    _run(dp, bot, cb)
    assert repo.get_item(conn, USER, last["id"]) is None

    # restore brings it back
    _run(dp, bot, _update(9, _message(9, text=f"/restore {last['id']}")))
    assert repo.get_item(conn, USER, last["id"]) is not None

    # stats answers without error
    calls.reset_mock()
    _run(dp, bot, _update(10, _message(10, text="/stats")))
    assert calls.await_count >= 1


def test_search_button_flow(rig):
    """🔎 button -> bot asks for query -> next plain text becomes the search."""
    dp, bot, conn = rig

    _run(dp, bot, _update(1, _message(1, text="linux networking handbook")))

    # press the 🔎 button (asksearch callback)
    cb_ask = Update.model_validate({
        "update_id": 2,
        "callback_query": {
            "id": "cb-ask",
            "from": {"id": USER, "is_bot": False, "first_name": "Tester"},
            "chat_instance": "x",
            "data": "asksearch",
            "message": {
                "message_id": 50, "date": 1700000000,
                "chat": {"id": USER, "type": "private"},
            },
        },
    })
    _run(dp, bot, cb_ask)

    # user types the query as a plain message
    calls = bot.session
    calls.reset_mock()
    _run(dp, bot, _update(3, _message(3, text="networking")))

    sent_texts = [str(getattr(c.args[1], "text", ""))
                  for c in calls.await_args_list if len(c.args) > 1]
    assert any("networking handbook" in t or "نتایج" in t for t in sent_texts)


def test_search_pagination_and_result_details(rig):
    """25 items -> 3 pages; nav buttons and page callbacks must work."""
    dp, bot, conn = rig
    from app.db import repository as repo_mod

    for i in range(25):
        repo_mod.insert_item(conn, {"user_id": USER, "type": "text",
                                    "text": f"kernel patch notes {i}"})

    calls = bot.session
    calls.reset_mock()
    _run(dp, bot, _update(1, _message(1, text="/search kernel")))
    sent = _sent_methods(calls)
    assert sent, "search must answer"
    first = sent[0]
    assert "25 مورد" in first.text                     # total in header
    assert "kernel patch notes" in first.text          # truncated text list
    kb_rows = first.reply_markup.inline_keyboard
    nav_datas = [b.callback_data for b in kb_rows[-1]]
    assert "page:open:2" in nav_datas                  # next-page button
    assert len(kb_rows) == 10 + 1                      # 10 results + nav row

    # page 2 via callback
    calls.reset_mock()
    _run(dp, bot, _cb(2, "page:open:2"))
    edits = [m for m in _sent_methods(calls)
             if type(m).__name__ == "EditMessageText"]
    assert edits, "pagination must edit the results message"
    nav2 = edits[-1].reply_markup.inline_keyboard[-1]
    datas = [b.callback_data for b in nav2]
    assert "page:open:1" in datas and "page:open:3" in datas


def test_save_card_and_detail_view(rig):
    """Saving shows a clean card; opening shows the full detail page."""
    dp, bot, conn = rig

    calls = bot.session
    calls.reset_mock()
    _run(dp, bot, _update(1, _message(
        1, text=None, caption="networking book",
        document={"file_id": "DOCX", "file_unique_id": "UDOCX",
                  "file_name": "Linux.pdf", "file_size": 123456,
                  "mime_type": "application/pdf"})))
    card = _sent_methods(calls)[0]
    assert "✅ ذخیره شد" in card.text
    assert "Linux.pdf" in card.text
    assert "📄" in card.text

    item_id = repo.get_last_item(conn, USER)["id"]
    calls.reset_mock()
    _run(dp, bot, _cb(2, f"open:{item_id}"))
    detail = _sent_methods(calls)[0]
    assert f"آیتم #{item_id}" in detail.text
    assert "Linux.pdf" in detail.text
    assert "حجم" in detail.text                       # size line
    assert "نوع" in detail.text                        # type line
    labels = [b.text for row in detail.reply_markup.inline_keyboard for b in row]
    assert any("⭐" in t for t in labels)              # favorite button
    assert any("بازفرستادن" in t for t in labels)      # media restore button


def test_recent_favorites_random_storage(rig):
    dp, bot, conn = rig

    for i in range(3):
        _run(dp, bot, _update(i + 1, _message(i + 1, text=f"quick item {i}")))

    calls = bot.session
    # /recent
    calls.reset_mock()
    _run(dp, bot, _update(10, _message(10, text="/recent")))
    assert "quick item 2" in _sent_methods(calls)[0].text

    # /fav toggles the last item, /favorites lists it
    _run(dp, bot, _update(11, _message(11, text="/fav")))
    calls.reset_mock()
    _run(dp, bot, _update(12, _message(12, text="/favorites")))
    assert "quick item 2" in _sent_methods(calls)[0].text

    # /random shows some item detail
    calls.reset_mock()
    _run(dp, bot, _update(13, _message(13, text="/random")))
    assert "quick item" in _sent_methods(calls)[0].text

    # /storage reports real numbers
    calls.reset_mock()
    _run(dp, bot, _update(14, _message(14, text="/storage")))
    storage_text = _sent_methods(calls)[0].text
    assert "Database" in storage_text and "Total" in storage_text
