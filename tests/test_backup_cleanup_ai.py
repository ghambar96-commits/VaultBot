"""Backup rotation, tmp cleanup, and the optional-AI contract."""

from __future__ import annotations

import asyncio
import os
import time

from app.ai.base import NullProvider, get_provider
from app.db import repository as repo
from app.services.backup import backup_database
from app.services.cleanup import cleanup_tmp

from conftest import USER_A, make_text_data


def test_backup_creates_file_and_rotates(conn, tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    repo.insert_item(conn, make_text_data(USER_A, "important", 1))

    # seed four older snapshots so rotation has something to prune
    for i in range(4):
        (backup_dir / f"vaultbot-2026010{i}T000000Z.sqlite3").touch()

    path = backup_database(conn, backup_dir, keep=3)
    assert path and path.exists()

    snapshots = sorted(backup_dir.glob("vaultbot-*.sqlite3"))
    assert len(snapshots) == 3          # rotated down to `keep`
    assert path in snapshots            # the fresh backup survived rotation


def test_backup_is_queryable(conn, tmp_path):
    import sqlite3
    repo.insert_item(conn, make_text_data(USER_A, "restorable", 1))
    path = backup_database(conn, tmp_path, keep=1)

    restored = sqlite3.connect(path)
    restored.row_factory = sqlite3.Row
    rows = restored.execute("SELECT * FROM items").fetchall()
    assert len(rows) == 1 and rows[0]["text"] == "restorable"
    restored.close()


def test_cleanup_removes_only_old_files(tmp_path):
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    old = tmp / "old.bin"
    new = tmp / "new.bin"
    old.write_bytes(b"x")
    new.write_bytes(b"y")
    past = time.time() - 2 * 3600
    os.utime(old, (past, past))

    removed = cleanup_tmp(tmp, max_age_minutes=30)
    assert removed == 1
    assert not old.exists() and new.exists()


def test_null_provider_disables_ai_cleanly():
    ai = get_provider("none")
    assert isinstance(ai, NullProvider)
    assert ai.enabled is False
    assert asyncio.run(ai.summarize("anything")) is None
    assert asyncio.run(ai.generate_tags("anything")) == []


def test_mock_provider_works_without_api_key():
    ai = get_provider("mock")
    assert ai.enabled is True
    summary = asyncio.run(ai.summarize("one two three four"))
    assert summary == "one two three four"
    tags = asyncio.run(ai.generate_tags("python asyncio programming here"))
    assert "python" in tags
