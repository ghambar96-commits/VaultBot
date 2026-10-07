"""User isolation: user A must never see user B's data."""

from __future__ import annotations

from app.db import repository as repo
from app.services.item_service import save_message

from conftest import USER_A, USER_B, FakeFile, FakeMessage, make_text_data


def _seed_both(conn):
    repo.insert_item(conn, make_text_data(USER_A, "secret plan of user A", 1))
    repo.insert_item(conn, make_text_data(USER_B, "secret plan of user B", 1))


def test_get_item_is_scoped(conn):
    _seed_both(conn)
    item_a = repo.get_last_item(conn, USER_A)
    # user B tries to read A's item by id
    assert repo.get_item(conn, USER_B, item_a["id"]) is None
    assert repo.get_item(conn, USER_A, item_a["id"]) is not None


def test_search_is_scoped(conn):
    _seed_both(conn)
    rows_a = repo.search_items(conn, USER_A, "secret")
    rows_b = repo.search_items(conn, USER_B, "secret")
    assert len(rows_a) == 1 and rows_a[0]["user_id"] == USER_A
    assert len(rows_b) == 1 and rows_b[0]["user_id"] == USER_B


def test_list_and_stats_are_scoped(conn):
    _seed_both(conn)
    repo.insert_item(conn, make_text_data(USER_A, "another A item", 2))
    assert repo.count_items(conn, USER_A) == 2
    assert repo.count_items(conn, USER_B) == 1
    assert repo.user_stats(conn, USER_A)["total"] == 2


def test_folders_are_scoped(conn):
    repo.create_folder(conn, USER_A, "Projects")
    folder = repo.find_folder_by_name(conn, USER_A, "Projects")
    assert repo.get_folder(conn, USER_B, folder["id"]) is None
    assert repo.list_folders(conn, USER_B) == []


def test_tags_are_scoped(conn):
    item_a = repo.insert_item(conn, make_text_data(USER_A, "A content", 1))
    repo.add_tags(conn, USER_A, item_a["id"], ["private"])
    assert repo.list_user_tags(conn, USER_B) == []
    names = [r["name"] for r in repo.list_user_tags(conn, USER_A)]
    assert names == ["private"]


def test_delete_restore_scoped(conn):
    item_a = repo.insert_item(conn, make_text_data(USER_A, "A only", 1))
    # B cannot delete or restore A's item
    assert repo.soft_delete_item(conn, USER_B, item_a["id"]) is False
    assert repo.restore_item(conn, USER_B, item_a["id"]) is None
    assert repo.get_item(conn, USER_A, item_a["id"]) is not None


def test_duplicate_detection_scoped(conn):
    doc = FakeFile(unique="dup-1")
    save_message(conn, FakeMessage(document=doc, message_id=1), USER_A)
    res_b = save_message(conn, FakeMessage(document=doc, message_id=9), USER_B)
    assert not res_b.is_duplicate
