"""Storage usage report — numbers are read from the real filesystem.

VaultBot's whole point is staying tiny; this service proves it.
"""

from __future__ import annotations

from pathlib import Path

from ..utils.text import format_size


def path_size(path: Path) -> int:
    """Size in bytes of a file or a directory (recursive, symlinks skipped)."""
    path = Path(path)
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file() and not p.is_symlink():
                total += p.stat().st_size
        except OSError:
            continue
    return total


def db_files(db_path: Path):
    """The main DB file plus WAL/SHM sidecars (counted even if 0 bytes)."""
    db_path = Path(db_path)
    return [db_path, db_path.with_suffix(db_path.suffix + "-wal"),
            db_path.with_suffix(db_path.suffix + "-shm")]


def storage_report(settings) -> dict[str, int]:
    """Measure real disk usage: database, backups, tmp, logs. All bytes."""
    db_bytes = sum(f.stat().st_size for f in db_files(settings.db_path) if f.exists())
    logs_dir = Path(settings.log_file).parent if settings.log_file else None
    return {
        "db": db_bytes,
        "backups": path_size(settings.backup_dir),
        "tmp": path_size(settings.tmp_dir),
        "logs": path_size(logs_dir) if logs_dir else 0,
    }


def format_storage_report(usage: dict[str, int]) -> str:
    total = sum(usage.values())
    return (
        "💽 <b>مصرف فضای سرور</b>\n\n"
        f"🗄 Database: {format_size(usage['db'])}\n"
        f"💾 Backups: {format_size(usage['backups'])}\n"
        f"⏳ Temp: {format_size(usage['tmp'])}\n"
        f"📜 Logs: {format_size(usage['logs'])}\n"
        f"━━━━━━━━━━\n"
        f"Σ Total: {format_size(total)}\n\n"
        "فایل‌های رسانه‌ای هرگز روی دیسک ذخیره نمی‌شوند؛ "
        "آن‌ها در تلگرام می‌مانند و اینجا فقط مرجعشان ثبت است."
    )
