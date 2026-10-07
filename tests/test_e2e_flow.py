"""End-to-end test of the main flow, driven through the same service +
repository layers the bot handlers use (no network / no token needed).

Flow: save doc -> duplicate check -> folder -> tags -> note -> search ->
      delete -> restore -> stats.
"""

from __future__ import annotations

from app.db import repository as repo
from app.services.item_service import save_message

from conftest import USER_A, FakeFile, FakeMessage


def test_full_vault_flow(conn, tmp_path):
    # 1. save a document (reference only — nothing written to disk)
    doc = FakeFile(file_id="fid-1", unique="uniq-1", size=10_000_000,
                   mime="application/pdf", name="Linux.pdf")
    r1 = save_message(conn, FakeMessage(document=doc, caption="networking book",
                                        message_id=101), USER_A)
    assert not r1.is_duplicate
    item = r1.item
    assert list((tmp_path / "..").glob("**/Linux.pdf")) == []  # no file on disk

    # 2. duplicate is detected and skipped
    r2 = save_message(conn, FakeMessage(document=doc, message_id=102), USER_A)
    assert r2.is_duplicate and r2.duplicate_of["id"] == item["id"]

    # 3. save a text note too
    save_message(conn, FakeMessage(text="minecraft server config tips",
                                   message_id=103), USER_A)

    # 4. organize: folder + move
    folder = repo.create_folder(conn, USER_A, "Projects")
    repo.move_item(conn, USER_A, item["id"], folder["id"])

    # 5. tags + note
    repo.add_tags(conn, USER_A, item["id"], ["#linux", "#network"])
    repo.update_item_fields(conn, USER_A, item["id"],
                            {"note": "read before the exam"})

    # 6. search finds it by filename, tag, and note
    assert repo.search_items(conn, USER_A, "linux")
    assert repo.search_items(conn, USER_A, "network")   # tag is searchable
    assert repo.search_items(conn, USER_A, "exam")
    assert repo.search_items(conn, USER_A, "minecraft server")

    # 7. delete hides it everywhere
    assert repo.soft_delete_item(conn, USER_A, item["id"])
    assert repo.search_items(conn, USER_A, "networking book") == []
    assert repo.get_item(conn, USER_A, item["id"]) is None

    # 8. restore brings everything back
    restored = repo.restore_item(conn, USER_A, item["id"])
    assert restored["tags"] == "linux network"
    assert restored["note"] == "read before the exam"
    assert restored["folder_id"] == folder["id"]

    # 9. stats reflect the vault contents
    stats = repo.user_stats(conn, USER_A)
    assert stats["total"] == 2
    assert stats["by_type"]["document"] == 1
    assert stats["total_size"] >= 10_000_000
