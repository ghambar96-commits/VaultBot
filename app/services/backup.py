"""Backup: SQLite database only.

Files themselves are referenced by file_id and live on Telegram's servers,
so a small rotating set of DB snapshots is the complete backup story.
Uses SQLite's online backup API — safe while the bot is running.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


def backup_database(conn: sqlite3.Connection, backup_dir: Path,
                    keep: int = 3) -> Path | None:
    """Create a timestamped DB snapshot and rotate old ones."""
    from ..db.repository import utcnow
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = utcnow().replace(":", "").replace("-", "")
    dest = backup_dir / f"vaultbot-{stamp}.sqlite3"

    try:
        dst = sqlite3.connect(dest)
        try:
            # SQLite's online backup API: a consistent snapshot even while
            # the bot is writing (no need to stop or lock the app out).
            conn.backup(dst)
        finally:
            dst.close()
    except sqlite3.Error:
        logger.exception("backup failed")
        dest.unlink(missing_ok=True)
        return None

    # verify the snapshot before trusting it
    try:
        check = sqlite3.connect(dest)
        try:
            ok = check.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        finally:
            check.close()
        if not ok:
            logger.error("backup failed integrity check: %s", dest.name)
            dest.unlink(missing_ok=True)
            return None
    except sqlite3.Error:
        logger.exception("backup verification failed")
        dest.unlink(missing_ok=True)
        return None

    # rotate: keep only the newest `keep` snapshots
    snapshots = sorted(backup_dir.glob("vaultbot-*.sqlite3"))
    for old in snapshots[:-keep] if keep else []:
        old.unlink(missing_ok=True)
    logger.info("backup written: %s (%d kept)", dest.name, min(len(snapshots), keep))
    return dest
