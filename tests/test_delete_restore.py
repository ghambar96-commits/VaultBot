"""Soft delete / restore lifecycle."""

from __future__ import annotations

from app.db import repository as repo

from conftest import USER_A, make_text_data


def test_soft_delete_hides_item(conn):
    item = repo.insert_item(conn, make_text_data(USER_A, "delete me", 1))
    assert repo.soft_delete_item(conn, USER_A, item["id"])

    assert repo.get_item(conn, USER_A, item["id"]) is None
    assert repo.count_items(conn, USER_A) == 0
    # still visible when explicitly asking for the trash
    trash = repo.list_items(conn, USER_A, include_deleted=True)
    assert len(trash) == 1 and trash[0]["deleted"] == 1


def test_restore_brings_item_back(conn):
    item = repo.insert_item(conn, make_text_data(USER_A, "bring me back", 1))
    repo.soft_delete_item(conn, USER_A, item["id"])
    restored = repo.restore_item(conn, USER_A, item["id"])

    assert restored is not None and restored["deleted"] == 0
    assert repo.count_items(conn, USER_A) == 1
    assert repo.search_items(conn, USER_A, "bring")


def test_hard_delete_removes_everything(conn):
    item = repo.insert_item(conn, make_text_data(USER_A, "gone forever", 1))
    assert repo.hard_delete_item(conn, USER_A, item["id"])
    assert repo.get_item(conn, USER_A, item["id"], include_deleted=True) is None
    assert repo.search_items(conn, USER_A, "gone") == []


def test_restore_unknown_item(conn):
    assert repo.restore_item(conn, USER_A, 9999) is None
