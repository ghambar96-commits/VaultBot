"""Temp-file cleanup.

The bot never *intends* to leave files behind (AI downloads are removed in a
finally block), but this sweep guarantees nothing accumulates if anything
crashes mid-download. Two limits are enforced:

  1. age   — files older than max_age_minutes are removed
  2. total — if the dir still exceeds max_total_mb, oldest files go first
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def cleanup_tmp(tmp_dir: Path, max_age_minutes: int = 30,
                max_total_mb: float = 128) -> int:
    """Delete stale/overflow files in tmp_dir. Returns how many were removed."""
    if not tmp_dir.exists():
        return 0
    removed = 0
    cutoff = time.time() - max_age_minutes * 60
    remaining: list[tuple[float, int, Path]] = []

    for path in tmp_dir.iterdir():
        try:
            if not path.is_file():
                continue
            stat = path.stat()
            if stat.st_mtime < cutoff:
                path.unlink()
                removed += 1
            else:
                remaining.append((stat.st_mtime, stat.st_size, path))
        except OSError:
            logger.warning("cleanup could not inspect %s", path)

    # size cap: drop oldest files until under the limit
    cap = int(max_total_mb * 1024 * 1024)
    total = sum(size for _, size, _ in remaining)
    if total > cap:
        for mtime, size, path in sorted(remaining):  # oldest first
            if total <= cap:
                break
            try:
                path.unlink()
                total -= size
                removed += 1
            except OSError:
                logger.warning("cleanup could not remove %s", path)

    if removed:
        logger.info("tmp cleanup removed %d file(s)", removed)
    return removed
