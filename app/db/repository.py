"""Data access layer.

All queries are scoped by `user_id` (user isolation is enforced here, not in
the handlers). All writes that touch `items` also keep the FTS5 index in sync.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable

ITEM_TYPES = (
    "text", "link", "photo", "video", "document",
    "audio", "voice", "animation", "sticker",
)


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _normalize_tags(raw: str | Iterable[str]) -> list[str]:
    """'#Python #cyber!' -> ['python', 'cyber'] (lowercase, unique, ordered)."""
    if isinstance(raw, str):
        parts = re.findall(r"#?[\w\u0600-\u06FF][\w\u0600-\u06FF\-]*", raw)
    else:
        parts = list(raw)
    seen: dict[str, None] = {}
    for p in parts:
        t = p.lstrip("#").strip().lower()
        if t and t not in seen:
            seen[t] = None
    return list(seen)


def build_fts_query(raw: str) -> str | None:
    """Convert free user text into a safe FTS5 MATCH expression.

    Each word becomes a quoted prefix token (`"linux"*`), combined with AND.
    FTS special characters are stripped so user input can't break the query
    or act like SQL/FTS injection.
    """
    words = re.findall(r"[\w\u0600-\u06FF][\w\u0600-\u06FF\-]*", raw)
    if not words:
        return None
    return " ".join(f'"{w}"*' for w in words)


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------

def ensure_user(conn: sqlite3.Connection, user_id: int, username: str | None = None) -> None:
    conn.execute(
        """INSERT INTO users (user_id, username) VALUES (?, ?)
           ON CONFLICT(user_id) DO UPDATE SET
             username = COALESCE(excluded.username, users.username)""",
        (user_id, username),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# folders
# ---------------------------------------------------------------------------

def create_folder(conn: sqlite3.Connection, user_id: int, name: str) -> sqlite3.Row | None:
    """Create a folder; returns None if the name already exists
    (compared case-insensitively)."""
    name = name.strip()
    if not name or find_folder_by_name(conn, user_id, name) is not None:
        return None
    try:
        cur = conn.execute(
            "INSERT INTO folders (user_id, name) VALUES (?, ?)", (user_id, name)
        )
        conn.commit()
        return conn.execute("SELECT * FROM folders WHERE id = ?", (cur.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        return None


def list_folders(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT f.*, COUNT(i.id) AS item_count
           FROM folders f
           LEFT JOIN items i ON i.folder_id = f.id AND i.deleted = 0
           WHERE f.user_id = ?
           GROUP BY f.id ORDER BY f.name""",
        (user_id,),
    ).fetchall()


def get_folder(conn: sqlite3.Connection, user_id: int, folder_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM folders WHERE id = ? AND user_id = ?", (folder_id, user_id)
    ).fetchone()


def find_folder_by_name(conn: sqlite3.Connection, user_id: int, name: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM folders WHERE user_id = ? AND lower(name) = lower(?)",
        (user_id, name.strip()),
    ).fetchone()


def delete_folder(conn: sqlite3.Connection, user_id: int, folder_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM folders WHERE id = ? AND user_id = ?", (folder_id, user_id)
    )
    conn.commit()
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# items — writes (keep FTS in sync!)
# ---------------------------------------------------------------------------

def _fts_sync_insert(conn: sqlite3.Connection, item_id: int, row: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO items_fts (rowid, original_name, caption, text, note, tags, summary)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            item_id,
            row.get("original_name") or "",
            row.get("caption") or "",
            row.get("text") or "",
            row.get("note") or "",
            row.get("tags") or "",
            row.get("summary") or "",
        ),
    )


def _fts_sync_delete(conn: sqlite3.Connection, item_id: int) -> None:
    # With contentless_delete=1 a plain DELETE by rowid works.
    conn.execute("DELETE FROM items_fts WHERE rowid = ?", (item_id,))


def set_item_tags(conn: sqlite3.Connection, item_id: int, tag_names: list[str]) -> None:
    """Replace an item's tag set (items.tags column + normalized tables)."""
    for name in tag_names:
        conn.execute(
            "INSERT INTO tags (user_id, name) SELECT user_id, ? FROM items WHERE id = ?"
            " ON CONFLICT(user_id, name) DO NOTHING",
            (name, item_id),
        )
    conn.execute("DELETE FROM item_tags WHERE item_id = ?", (item_id,))
    for name in tag_names:
        conn.execute(
            """INSERT OR IGNORE INTO item_tags (item_id, tag_id)
               SELECT ?, t.id FROM tags t JOIN items i ON i.id = ?
               WHERE t.user_id = i.user_id AND t.name = ?""",
            (item_id, item_id, name),
        )
    conn.execute("UPDATE items SET tags = ? WHERE id = ?", (" ".join(tag_names), item_id))


def insert_item(conn: sqlite3.Connection, data: dict[str, Any]) -> sqlite3.Row:
    """Insert one saved item. `data` keys match the items columns."""
    data = dict(data)
    tags = _normalize_tags(data.pop("tags", ""))
    data["tags"] = " ".join(tags)
    cols = ", ".join(data)
    placeholders = ", ".join(":" + c for c in data)
    cur = conn.execute(f"INSERT INTO items ({cols}) VALUES ({placeholders})", data)
    item_id = cur.lastrowid
    _fts_sync_insert(conn, item_id, data)
    set_item_tags(conn, item_id, tags)
    conn.commit()
    return get_item(conn, data["user_id"], item_id)  # type: ignore[return-value]


def get_item(conn: sqlite3.Connection, user_id: int, item_id: int,
             include_deleted: bool = False) -> sqlite3.Row | None:
    q = "SELECT * FROM items WHERE id = ? AND user_id = ?"
    if not include_deleted:
        q += " AND deleted = 0"
    return conn.execute(q, (item_id, user_id)).fetchone()


def find_duplicate(conn: sqlite3.Connection, user_id: int,
                   file_unique_id: str) -> sqlite3.Row | None:
    """Duplicate detection based on Telegram's stable file_unique_id."""
    return conn.execute(
        """SELECT * FROM items
           WHERE user_id = ? AND telegram_file_unique_id = ? AND deleted = 0
           LIMIT 1""",
        (user_id, file_unique_id),
    ).fetchone()


def update_item_fields(conn: sqlite3.Connection, user_id: int, item_id: int,
                       fields: dict[str, Any]) -> sqlite3.Row | None:
    """Update allowed columns and re-sync FTS."""
    allowed = {"note", "summary", "folder_id", "caption", "text"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return get_item(conn, user_id, item_id)
    row = get_item(conn, user_id, item_id)
    if row is None:
        return None
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE items SET {sets} WHERE id = ? AND user_id = ?",
        (*fields.values(), item_id, user_id),
    )
    _fts_sync_delete(conn, item_id)
    merged = dict(row)
    merged.update(fields)
    _fts_sync_insert(conn, item_id, merged)
    conn.commit()
    return get_item(conn, user_id, item_id)


def add_tags(conn: sqlite3.Connection, user_id: int, item_id: int,
             new_tags: str | list[str]) -> sqlite3.Row | None:
    row = get_item(conn, user_id, item_id)
    if row is None:
        return None
    merged = _normalize_tags(row["tags"])
    for t in _normalize_tags(new_tags):
        if t not in merged:
            merged.append(t)
    set_item_tags(conn, item_id, merged)
    _fts_sync_delete(conn, item_id)
    fresh = dict(conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone())
    _fts_sync_insert(conn, item_id, fresh)
    conn.commit()
    return get_item(conn, user_id, item_id)


def remove_tags(conn: sqlite3.Connection, user_id: int, item_id: int,
                drop: str | list[str]) -> sqlite3.Row | None:
    row = get_item(conn, user_id, item_id)
    if row is None:
        return None
    drop_set = set(_normalize_tags(drop))
    merged = [t for t in _normalize_tags(row["tags"]) if t not in drop_set]
    set_item_tags(conn, item_id, merged)
    _fts_sync_delete(conn, item_id)
    fresh = dict(conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone())
    _fts_sync_insert(conn, item_id, fresh)
    conn.commit()
    return get_item(conn, user_id, item_id)


def move_item(conn: sqlite3.Connection, user_id: int, item_id: int,
              folder_id: int | None) -> sqlite3.Row | None:
    return update_item_fields(conn, user_id, item_id, {"folder_id": folder_id})


def soft_delete_item(conn: sqlite3.Connection, user_id: int, item_id: int) -> bool:
    cur = conn.execute(
        "UPDATE items SET deleted = 1, deleted_at = ? WHERE id = ? AND user_id = ?",
        (utcnow(), item_id, user_id),
    )
    if cur.rowcount:
        _fts_sync_delete(conn, item_id)
        conn.commit()
    return cur.rowcount > 0


def restore_item(conn: sqlite3.Connection, user_id: int, item_id: int) -> sqlite3.Row | None:
    row = conn.execute(
        "SELECT * FROM items WHERE id = ? AND user_id = ? AND deleted = 1",
        (item_id, user_id),
    ).fetchone()
    if row is None:
        return None
    conn.execute(
        "UPDATE items SET deleted = 0, deleted_at = NULL WHERE id = ?", (item_id,)
    )
    _fts_sync_insert(conn, item_id, dict(row))
    conn.commit()
    return get_item(conn, user_id, item_id)


def hard_delete_item(conn: sqlite3.Connection, user_id: int, item_id: int) -> bool:
    """Permanent delete (removes metadata + FTS row). File bytes are on
    Telegram's side and were never on our disk."""
    row = get_item(conn, user_id, item_id, include_deleted=True)
    if row is None:
        return False
    _fts_sync_delete(conn, item_id)
    conn.execute("DELETE FROM items WHERE id = ? AND user_id = ?", (item_id, user_id))
    conn.commit()
    return True


# ---------------------------------------------------------------------------
# items — reads / listing / stats
# ---------------------------------------------------------------------------

def list_items(conn: sqlite3.Connection, user_id: int, *, folder_id: int | None = None,
               item_type: str | None = None, favorites_only: bool = False,
               limit: int = 20, offset: int = 0,
               include_deleted: bool = False) -> list[sqlite3.Row]:
    q = "SELECT * FROM items WHERE user_id = ?"
    params: list[Any] = [user_id]
    if not include_deleted:
        q += " AND deleted = 0"
    if folder_id is not None:
        q += " AND folder_id = ?"
        params.append(folder_id)
    if item_type:
        q += " AND type = ?"
        params.append(item_type)
    if favorites_only:
        q += " AND favorite = 1"
    q += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    return conn.execute(q, params).fetchall()


def count_items(conn: sqlite3.Connection, user_id: int, *,
                favorites_only: bool = False, include_deleted: bool = False) -> int:
    q = "SELECT COUNT(*) FROM items WHERE user_id = ?"
    if not include_deleted:
        q += " AND deleted = 0"
    if favorites_only:
        q += " AND favorite = 1"
    return conn.execute(q, (user_id,)).fetchone()[0]


def toggle_favorite(conn: sqlite3.Connection, user_id: int, item_id: int) -> sqlite3.Row | None:
    row = get_item(conn, user_id, item_id)
    if row is None:
        return None
    conn.execute("UPDATE items SET favorite = 1 - favorite WHERE id = ? AND user_id = ?",
                 (item_id, user_id))
    conn.commit()
    return get_item(conn, user_id, item_id)


def get_random_item(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT * FROM items WHERE user_id = ? AND deleted = 0
           ORDER BY RANDOM() LIMIT 1""",
        (user_id,),
    ).fetchone()


def purge_deleted(conn: sqlite3.Connection, user_id: int) -> int:
    """Permanently remove soft-deleted items (metadata only — file bytes were
    never local). Returns how many rows were removed."""
    cur = conn.execute(
        "DELETE FROM items WHERE user_id = ? AND deleted = 1", (user_id,)
    )
    conn.commit()
    return cur.rowcount


def get_last_item(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM items WHERE user_id = ? AND deleted = 0 ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()


def search_items(conn: sqlite3.Connection, user_id: int, query: str, *,
                 limit: int = 20, offset: int = 0) -> list[sqlite3.Row]:
    """Full-text search scoped to one user."""
    match = build_fts_query(query)
    if not match:
        return []
    return conn.execute(
        """SELECT i.*
           FROM items_fts f
           JOIN items i ON i.id = f.rowid
           WHERE items_fts MATCH ? AND i.user_id = ? AND i.deleted = 0
           ORDER BY rank LIMIT ? OFFSET ?""",
        (match, user_id, limit, offset),
    ).fetchall()


def user_stats(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    rows = conn.execute(
        """SELECT type, COUNT(*) AS n, COALESCE(SUM(file_size), 0) AS size
           FROM items WHERE user_id = ? AND deleted = 0 GROUP BY type""",
        (user_id,),
    ).fetchall()
    stats = {
        "total": 0,
        "total_size": 0,
        "by_type": {r["type"]: r["n"] for r in rows},
        "size_by_type": {r["type"]: r["size"] for r in rows},
    }
    stats["total"] = sum(stats["by_type"].values())
    stats["total_size"] = sum(stats["size_by_type"].values())
    return stats


def list_user_tags(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT t.name, COUNT(it.item_id) AS n
           FROM tags t LEFT JOIN item_tags it ON it.tag_id = t.id
           WHERE t.user_id = ? GROUP BY t.id ORDER BY n DESC, t.name""",
        (user_id,),
    ).fetchall()


# ---------------------------------------------------------------------------
# reminders
# ---------------------------------------------------------------------------

def add_reminder(conn: sqlite3.Connection, user_id: int, remind_at: str,
                 item_id: int | None = None, message: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO reminders (user_id, item_id, remind_at, message) VALUES (?, ?, ?, ?)",
        (user_id, item_id, remind_at, message),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def due_reminders(conn: sqlite3.Connection, now_iso: str | None = None) -> list[sqlite3.Row]:
    now_iso = now_iso or utcnow()
    return conn.execute(
        "SELECT * FROM reminders WHERE sent = 0 AND remind_at <= ? ORDER BY remind_at",
        (now_iso,),
    ).fetchall()


def mark_reminder_sent(conn: sqlite3.Connection, reminder_id: int) -> None:
    conn.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,))
    conn.commit()


def list_reminders(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM reminders WHERE user_id = ? AND sent = 0 ORDER BY remind_at",
        (user_id,),
    ).fetchall()


def delete_reminder(conn: sqlite3.Connection, user_id: int, reminder_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM reminders WHERE id = ? AND user_id = ?", (reminder_id, user_id)
    )
    conn.commit()
    return cur.rowcount > 0
