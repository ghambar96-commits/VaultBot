"""Tags, folders and notes behavior."""

from __future__ import annotations

from app.db import repository as repo

from conftest import USER_A, make_text_data


def test_add_and_dedupe_tags(conn):
    item = repo.insert_item(conn, make_text_data(USER_A, "tag test", 1))
    repo.add_tags(conn, USER_A, item["id"], "#Python #CYBER python")
    fresh = repo.get_item(conn, USER_A, item["id"])
    assert fresh["tags"] == "python cyber"  # normalized + deduplicated


def test_remove_tags(conn):
    item = repo.insert_item(conn, make_text_data(USER_A, "x", 1))
    repo.add_tags(conn, USER_A, item["id"], ["a", "b", "c"])
    repo.remove_tags(conn, USER_A, item["id"], "#b")
    assert repo.get_item(conn, USER_A, item["id"])["tags"] == "a c"


def test_user_tag_list_with_counts(conn):
    i1 = repo.insert_item(conn, make_text_data(USER_A, "x", 1))
    i2 = repo.insert_item(conn, make_text_data(USER_A, "y", 2))
    repo.add_tags(conn, USER_A, i1["id"], ["dev"])
    repo.add_tags(conn, USER_A, i2["id"], ["dev", "fun"])
    tags = {r["name"]: r["n"] for r in repo.list_user_tags(conn, USER_A)}
    assert tags == {"dev": 2, "fun": 1}


def test_folder_create_and_uniqueness(conn):
    assert repo.create_folder(conn, USER_A, "Projects") is not None
    assert repo.create_folder(conn, USER_A, "projects") is None  # case-insensitive
    assert repo.create_folder(conn, USER_A, "School") is not None
    assert len(repo.list_folders(conn, USER_A)) == 2


def test_move_item_into_folder(conn):
    item = repo.insert_item(conn, make_text_data(USER_A, "movable", 1))
    folder = repo.create_folder(conn, USER_A, "Projects")

    repo.move_item(conn, USER_A, item["id"], folder["id"])
    assert repo.get_item(conn, USER_A, item["id"])["folder_id"] == folder["id"]
    counts = {f["name"]: f["item_count"] for f in repo.list_folders(conn, USER_A)}
    assert counts["Projects"] == 1

    # move out again
    repo.move_item(conn, USER_A, item["id"], None)
    assert repo.get_item(conn, USER_A, item["id"])["folder_id"] is None


def test_folder_delete_nulls_items(conn):
    item = repo.insert_item(conn, make_text_data(USER_A, "x", 1))
    folder = repo.create_folder(conn, USER_A, "Temp")
    repo.move_item(conn, USER_A, item["id"], folder["id"])
    assert repo.delete_folder(conn, USER_A, folder["id"])
    assert repo.get_item(conn, USER_A, item["id"])["folder_id"] is None


def test_note_saved_and_searchable(conn):
    item = repo.insert_item(conn, make_text_data(USER_A, "some link dump", 1))
    repo.update_item_fields(conn, USER_A, item["id"],
                            {"note": "این لینک برای پروژه NEXUS مفید است"})
    assert repo.get_item(conn, USER_A, item["id"])["note"].startswith("این لینک")
    assert repo.search_items(conn, USER_A, "NEXUS")


def test_disallowed_fields_cannot_be_updated(conn):
    item = repo.insert_item(conn, make_text_data(USER_A, "x", 1))
    repo.update_item_fields(conn, USER_A, item["id"],
                            {"user_id": 999, "deleted": 1, "note": "ok"})
    fresh = repo.get_item(conn, USER_A, item["id"])
    assert fresh["user_id"] == USER_A       # injection attempt ignored
    assert fresh["deleted"] == 0
    assert fresh["note"] == "ok"
