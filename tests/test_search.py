"""FTS5 full-text search: fields, ranking sanity, safety, languages."""

from __future__ import annotations

from app.db import repository as repo

from conftest import USER_A, make_text_data


def _seed(conn):
    repo.insert_item(conn, make_text_data(USER_A, "Python asyncio deep dive", 1))
    repo.insert_item(conn, make_text_data(USER_A, "minecraft server setup guide", 2))
    repo.insert_item(conn, make_text_data(USER_A, "Linux networking PDF notes", 3))
    repo.insert_item(conn, {
        "user_id": USER_A, "type": "document",
        "original_name": "linux-admin.pdf", "caption": "sysadmin handbook",
        "telegram_message_id": 4,
    })
    repo.insert_item(conn, make_text_data(USER_A, "یادداشت فارسی درباره امنیت شبکه", 5))


def test_search_matches_text(conn):
    _seed(conn)
    rows = repo.search_items(conn, USER_A, "python")
    assert len(rows) == 1
    assert "Python" in rows[0]["text"]


def test_search_matches_filename(conn):
    _seed(conn)
    rows = repo.search_items(conn, USER_A, "linux")
    # one document by filename, one text by content
    assert len(rows) == 2


def test_search_phrase_words_and(conn):
    _seed(conn)
    rows = repo.search_items(conn, USER_A, "minecraft server")
    assert len(rows) == 1
    assert "minecraft" in rows[0]["text"]


def test_search_persian_text(conn):
    _seed(conn)
    rows = repo.search_items(conn, USER_A, "امنیت شبکه")
    assert len(rows) == 1


def test_search_after_tag_and_note_update(conn):
    _seed(conn)
    item = repo.search_items(conn, USER_A, "python")[0]
    repo.add_tags(conn, USER_A, item["id"], ["tutorial"])
    repo.update_item_fields(conn, USER_A, item["id"], {"note": "for the NEXUS project"})

    assert repo.search_items(conn, USER_A, "tutorial")
    assert repo.search_items(conn, USER_A, "nexus")


def test_deleted_items_disappear_from_search(conn):
    _seed(conn)
    item = repo.search_items(conn, USER_A, "minecraft")[0]
    repo.soft_delete_item(conn, USER_A, item["id"])
    assert repo.search_items(conn, USER_A, "minecraft") == []
    repo.restore_item(conn, USER_A, item["id"])
    assert len(repo.search_items(conn, USER_A, "minecraft")) == 1


def test_fts_query_sanitization(conn):
    """Injection-style input must become a harmless quoted query or None,
    and must always execute safely against the FTS table."""
    import re as _re
    assert repo.build_fts_query("!!!") is None
    hostile = ['"; DROP TABLE items; --', '" OR 1=1 --',
               "linux & | ^ (pdf)", "فردا'--", "نیم‌فاصله‌ها"]
    for raw in hostile:
        q = repo.build_fts_query(raw)
        if q is None:
            continue
        assert _re.fullmatch(r'("[^"]+"\* ?)+', q), q  # only quoted word tokens
        conn.execute(
            "SELECT rowid FROM items_fts WHERE items_fts MATCH ?", (q,)
        ).fetchall()  # must not raise
