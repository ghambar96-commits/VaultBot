"""Small text helpers: formatting, link detection, privacy-aware log strings."""

from __future__ import annotations

import re

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

TYPE_EMOJI = {
    "text": "📝",
    "link": "🔗",
    "photo": "🖼",
    "video": "🎬",
    "document": "📄",
    "audio": "🎵",
    "voice": "🎤",
    "animation": "🌀",
    "sticker": "🩹",
}


def extract_urls(text: str) -> list[str]:
    return URL_RE.findall(text or "")


def looks_like_link_only(text: str) -> bool:
    """True when the message is essentially just one or more URLs."""
    stripped = (text or "").strip()
    if not stripped:
        return False
    without_urls = URL_RE.sub("", stripped)
    return len(without_urls.strip(" \n\t-—•·")) == 0


def truncate(text: str | None, limit: int = 60) -> str:
    if not text:
        return ""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def format_size(num: float | int | None) -> str:
    """Human readable size for metadata display (files stay on Telegram)."""
    if not num:
        return "0 B"
    n = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:,.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"


def format_tags(tags: str) -> str:
    return " ".join(f"#{t}" for t in tags.split() if t)


def mask_private(text: str | None, keep: int = 20) -> str:
    """For logs: never print full user content, only a short masked prefix."""
    if not text:
        return "<empty>"
    snippet = " ".join(text.split())[:keep]
    return f"{snippet}…" if len(text) > keep else snippet


def parse_item_ref(arg: str | None) -> int | None:
    """Parse an optional numeric item reference from command args."""
    if not arg:
        return None
    arg = arg.strip().lstrip("#")
    return int(arg) if arg.isdigit() else None


def format_result_line(row) -> str:
    """One truncated line of a result list:  📄 name — YYYY-MM-DD"""
    title = row["original_name"] or row["caption"] or row["text"] or f"#{row['id']}"
    date = (row["created_at"] or "")[:10]
    return f"{TYPE_EMOJI.get(row['type'], '📦')} {truncate(title, 44)} — {date}"
