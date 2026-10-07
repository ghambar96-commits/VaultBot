"""Storage usage reporting (real filesystem numbers) and tmp size caps."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from app.services.cleanup import cleanup_tmp
from app.services.storage_usage import format_storage_report, path_size, storage_report


@dataclass
class FakeSettings:
    db_path: Path
    backup_dir: Path
    tmp_dir: Path
    log_file: str = ""


def _mk(settings_root: Path) -> FakeSettings:
    db = settings_root / "vaultbot.db"
    db.write_bytes(b"x" * 1000)
    (settings_root / "vaultbot.db-wal").write_bytes(b"y" * 200)
    bak = settings_root / "backups"
    bak.mkdir()
    (bak / "b1.sqlite3").write_bytes(b"z" * 500)
    tmp = settings_root / "tmp"
    tmp.mkdir()
    (tmp / "t1.bin").write_bytes(b"t" * 300)
    return FakeSettings(db_path=db, backup_dir=bak, tmp_dir=tmp)


def test_storage_report_reads_real_sizes(tmp_path):
    s = _mk(tmp_path)
    usage = storage_report(s)
    assert usage["db"] == 1200          # main + wal
    assert usage["backups"] == 500
    assert usage["tmp"] == 300
    assert usage["logs"] == 0           # no log file configured

    text = format_storage_report(usage)
    assert "Database" in text and "Total" in text


def test_storage_report_counts_logs(tmp_path):
    s = _mk(tmp_path)
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "vaultbot.log").write_bytes(b"l" * 400)
    s.log_file = str(log_dir / "vaultbot.log")
    assert storage_report(s)["logs"] == 400


def test_path_size_missing_path(tmp_path):
    assert path_size(tmp_path / "nope") == 0


def test_cleanup_total_size_cap(tmp_path):
    """Even fresh files are pruned (oldest first) when over the size cap."""
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    base = time.time()
    for i in range(10):
        p = tmp / f"f{i}.bin"
        p.write_bytes(b"a" * 1024)             # 1 KB each -> 10 KB total
        os.utime(p, (base + i, base + i))     # f0 oldest, f9 newest

    removed = cleanup_tmp(tmp, max_age_minutes=60, max_total_mb=0)  # cap 0 MB
    assert removed == 10
    assert list(tmp.iterdir()) == []

    # cap at 5KB (0.005 MB): the 5 newest files survive, oldest get pruned
    for i in range(10):
        p = tmp / f"g{i}.bin"
        p.write_bytes(b"a" * 1024)
        os.utime(p, (base + i, base + i))
    removed = cleanup_tmp(tmp, max_age_minutes=60, max_total_mb=0.005)
    assert removed == 5
    survivors = sorted(p.name for p in tmp.iterdir())
    assert survivors == [f"g{i}.bin" for i in range(5, 10)]  # newest kept

    # generous cap: nothing is pruned
    assert cleanup_tmp(tmp, max_age_minutes=60, max_total_mb=1) == 0
    assert len(list(tmp.iterdir())) == 5
