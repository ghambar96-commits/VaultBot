"""SQLite connection management, tuned for a small (5GB) server.

Only one writer exists (the bot), so plain sqlite3 with WAL mode is the
simplest and most disk-friendly choice. No SQLAlchemy, no Redis, no extras.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# Path used by tests unless overridden.
DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "vaultbot.db"


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a connection with sane pragmas for low disk usage.

    `check_same_thread=False` is safe here because the repository serializes
    access through the async event loop via short, self-contained calls.
    """
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path, check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")     # safe with WAL, less fsync
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA cache_size = -2000")        # ~2MB page cache
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables/indexes if they don't exist, then run migrations."""
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        conn.executescript(fh.read())
    conn.commit()
    migrate(conn)


def migrate(conn: sqlite3.Connection) -> None:
    """Tiny forward-only migrations so older databases keep working.

    CREATE TABLE IF NOT EXISTS never modifies existing tables, so new
    columns are added here with ALTER TABLE.
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(items)")}
    if "favorite" not in cols:
        conn.execute("ALTER TABLE items ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_user_fav"
        " ON items(user_id, favorite, deleted)")
    conn.commit()


def vacuum(conn: sqlite3.Connection) -> None:
    """Reclaim free space. Run occasionally (e.g. after bulk deletes)."""
    conn.execute("VACUUM")


def db_size_bytes(conn: sqlite3.Connection) -> int:
    """Current database size in bytes (main file only)."""
    pages = conn.execute("PRAGMA page_count").fetchone()[0]
    size = conn.execute("PRAGMA page_size").fetchone()[0]
    return pages * size
