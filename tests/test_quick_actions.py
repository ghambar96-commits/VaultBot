"""Quick actions: /recent /random /favorites, favorite flag, trash purge,
and backwards-compatible migration for older databases."""

from __future__ import annotations

import sqlite3

from app.db import repository as repo
from app.db.database import connect, init_db

from conftest import USER_A, USER_B, make_text_data


def test_toggle_favorite_and_listing(conn):
    i1 = repo.insert_item(conn, make_text_data(USER_A, "one", 1))
    i2 = repo.insert_item(conn, make_text_data(USER_A, "two", 2))

    assert repo.toggle_favorite(conn, USER_A, i1["id"])["favorite"] == 1
    assert repo.toggle_favorite(conn, USER_A, i2["id"])["favorite"] == 1
    assert repo.toggle_favorite(conn, USER_A, i1["id"])["favorite"] == 0  # toggle off

    favs = repo.list_items(conn, USER_A, favorites_only=True)
    assert [r["id"] for r in favs] == [i2["id"]]
    assert repo.count_items(conn, USER_A, favorites_only=True) == 1
    # normal listing is unaffected
    assert repo.count_items(conn, USER_A) == 2


def test_favorites_are_user_scoped(conn):
    item = repo.insert_item(conn, make_text_data(USER_A, "mine", 1))
    repo.toggle_favorite(conn, USER_A, item["id"])
    assert repo.list_items(conn, USER_B, favorites_only=True) == []
    assert repo.toggle_favorite(conn, USER_B, item["id"]) is None  # can't touch it


def test_random_item_stays_within_user(conn):
    repo.insert_item(conn, make_text_data(USER_A, "a1", 1))
    repo.insert_item(conn, make_text_data(USER_A, "a2", 2))
    for _ in range(5):
        item = repo.get_random_item(conn, USER_A)
        assert item is not None and item["user_id"] == USER_A
    assert repo.get_random_item(conn, USER_B) is None  # empty vault -> None


def test_recent_listing_order_and_offset(conn):
    for i in range(1, 6):
        repo.insert_item(conn, make_text_data(USER_A, f"item {i}", i))
    recent = repo.list_items(conn, USER_A, limit=3)
    assert [r["text"] for r in recent] == ["item 5", "item 4", "item 3"]
    page2 = repo.list_items(conn, USER_A, limit=3, offset=3)
    assert [r["text"] for r in page2] == ["item 2", "item 1"]


def test_purge_deleted_only_removes_trash(conn):
    keep = repo.insert_item(conn, make_text_data(USER_A, "keep me", 1))
    gone = repo.insert_item(conn, make_text_data(USER_A, "delete me", 2))
    repo.soft_delete_item(conn, USER_A, gone["id"])

    removed = repo.purge_deleted(conn, USER_A)
    assert removed == 1
    assert repo.get_item(conn, USER_A, keep["id"]) is not None
    assert repo.get_item(conn, USER_A, gone["id"], include_deleted=True) is None
    # second purge finds nothing
    assert repo.purge_deleted(conn, USER_A) == 0


def test_migration_adds_favorite_to_old_databases(tmp_path):
    """A database created by an older VaultBot version must keep working."""
    db = tmp_path / "old.db"
    c = sqlite3.connect(db)
    c.executescript("""
        CREATE TABLE users (user_id INTEGER PRIMARY KEY, username TEXT,
                            created_at TEXT);
        CREATE TABLE items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            telegram_message_id INTEGER, telegram_file_id TEXT,
            telegram_file_unique_id TEXT, type TEXT NOT NULL,
            mime_type TEXT, original_name TEXT, file_size INTEGER,
            caption TEXT, text TEXT, source_chat_id INTEGER,
            source_message_id INTEGER, folder_id INTEGER, summary TEXT,
            note TEXT, tags TEXT NOT NULL DEFAULT '',
            created_at TEXT, deleted INTEGER NOT NULL DEFAULT 0,
            deleted_at TEXT);
    """)
    c.execute("INSERT INTO users (user_id) VALUES (1)")
    c.execute("INSERT INTO items (user_id, type, text) VALUES (1, 'text', 'old item')")
    c.commit()
    c.close()

    conn = connect(db)
    init_db(conn)  # must not raise; runs the migration
    cols = {r[1] for r in conn.execute("PRAGMA table_info(items)")}
    assert "favorite" in cols

    row = conn.execute("SELECT favorite FROM items LIMIT 1").fetchone()
    assert row[0] == 0
    assert repo.toggle_favorite(conn, 1, 1)["favorite"] == 1
    conn.close()
