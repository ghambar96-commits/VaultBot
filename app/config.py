"""Configuration — everything comes from environment variables (.env).

Secrets NEVER live in code. If BOT_TOKEN is missing the bot refuses to start.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    bot_token: str
    db_path: Path
    tmp_dir: Path
    backup_dir: Path
    admin_ids: frozenset[int]
    page_size: int
    # AI is optional — the bot must run fully without it.
    ai_provider: str            # "none" | "openai" | "mock"
    ai_api_key: str
    ai_model: str
    ai_max_download_mb: int     # cap for temporary downloads sent to the AI
    tmp_max_age_minutes: int    # cleanup threshold for temp files
    backup_keep: int            # number of backups to retain
    backup_interval_hours: int
    log_level: str
    log_file: str               # empty = console only; else rotating file log


def _ids(raw: str) -> frozenset[int]:
    out = set()
    for part in raw.replace(",", " ").split():
        try:
            out.add(int(part))
        except ValueError:
            pass
    return frozenset(out)


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token and os.getenv("VAULTBOT_ALLOW_NO_TOKEN") != "1":
        raise RuntimeError(
            "BOT_TOKEN is not set. Copy .env.example to .env and fill it in."
        )

    data_dir = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
    return Settings(
        bot_token=token,
        db_path=Path(os.getenv("DB_PATH", str(data_dir / "vaultbot.db"))),
        tmp_dir=Path(os.getenv("TMP_DIR", str(data_dir / "tmp"))),
        backup_dir=Path(os.getenv("BACKUP_DIR", str(data_dir / "backups"))),
        admin_ids=_ids(os.getenv("ADMIN_IDS", "")),
        page_size=int(os.getenv("PAGE_SIZE", "10")),
        ai_provider=os.getenv("AI_PROVIDER", "none").strip().lower(),
        ai_api_key=os.getenv("AI_API_KEY", "").strip(),
        ai_model=os.getenv("AI_MODEL", "gpt-4o-mini").strip(),
        ai_max_download_mb=int(os.getenv("AI_MAX_DOWNLOAD_MB", "25")),
        tmp_max_age_minutes=int(os.getenv("TMP_MAX_AGE_MINUTES", "30")),
        backup_keep=int(os.getenv("BACKUP_KEEP", "3")),
        backup_interval_hours=int(os.getenv("BACKUP_INTERVAL_HOURS", "24")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        log_file=os.getenv("LOG_FILE", "").strip(),
    )
