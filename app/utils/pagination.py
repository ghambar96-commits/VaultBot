"""Tiny pagination helper for search results and item lists."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Page:
    rows: list
    page: int          # 1-based
    pages: int
    total: int


def paginate(rows: list, page: int, page_size: int) -> Page:
    total = len(rows)
    pages = max(1, -(-total // page_size))
    page = min(max(1, page), pages)
    start = (page - 1) * page_size
    return Page(rows=rows[start:start + page_size], page=page, pages=pages, total=total)
