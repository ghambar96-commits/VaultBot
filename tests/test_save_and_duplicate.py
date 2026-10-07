"""Saving items + duplicate detection (files are referenced, never stored)."""

from __future__ import annotations

from app.services.item_service import save_message

from conftest import USER_A, FakeFile, FakeMessage


def test_save_text_item(conn):
    msg = FakeMessage(text="Python tutorial notes", message_id=10)
    result = save_message(conn, msg, USER_A)

    assert not result.is_duplicate
    item = result.item
    assert item["type"] == "text"
    assert item["text"] == "Python tutorial notes"
    assert item["telegram_message_id"] == 10
    # nothing file-like was stored
    assert item["telegram_file_id"] is None


def test_save_link_item(conn):
    msg = FakeMessage(text="https://example.com/linux-guide")
    result = save_message(conn, msg, USER_A)
    assert result.item["type"] == "link"


def test_save_document_stores_reference_only(conn):
    doc = FakeFile(file_id="doc-file-id", unique="doc-uniq", size=50_000_000,
                   mime="application/pdf", name="Linux.pdf")
    msg = FakeMessage(document=doc, caption="networking book", message_id=11)
    result = save_message(conn, msg, USER_A)

    item = result.item
    assert item["type"] == "document"
    assert item["telegram_file_id"] == "doc-file-id"
    assert item["telegram_file_unique_id"] == "doc-uniq"
    assert item["original_name"] == "Linux.pdf"
    assert item["file_size"] == 50_000_000
    assert item["caption"] == "networking book"


def test_duplicate_detection_same_file(conn):
    doc = FakeFile(unique="same-unique")
    first = save_message(conn, FakeMessage(document=doc, message_id=1), USER_A)
    assert not first.is_duplicate

    second = save_message(conn, FakeMessage(document=doc, message_id=2), USER_A)
    assert second.is_duplicate
    assert second.duplicate_of["id"] == first.item["id"]
    assert second.item is None  # nothing new inserted


def test_duplicate_not_shared_between_users(conn):
    """User B saving the same Telegram file is NOT a duplicate (isolation)."""
    from conftest import USER_B
    doc = FakeFile(unique="shared-unique")
    save_message(conn, FakeMessage(document=doc, message_id=1), USER_A)
    result = save_message(conn, FakeMessage(document=doc, message_id=1), USER_B)
    assert not result.is_duplicate
    assert result.item is not None


def test_unsupported_fields_never_crash(conn):
    msg = FakeMessage()  # empty message
    result = save_message(conn, msg, USER_A)
    assert result.item["type"] == "text"
