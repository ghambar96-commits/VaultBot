"""Mock AI provider — used in tests and for trying the UX without an API key.

Enable with AI_PROVIDER=mock (no key needed).
"""

from __future__ import annotations

import re

from .base import AIProvider


class MockProvider(AIProvider):
    name = "mock"

    async def summarize(self, text: str, *, max_words: int = 80) -> str | None:
        words = (text or "").split()
        return " ".join(words[: min(max_words, 25)]) if words else None

    async def generate_tags(self, text: str, *, max_tags: int = 5) -> list[str]:
        words = re.findall(r"[A-Za-z]{4,}", text or "")
        out: list[str] = []
        for w in words:
            w = w.lower()
            if w not in out:
                out.append(w)
            if len(out) >= max_tags:
                break
        return out

    async def answer_search(self, question: str, context: str) -> str | None:
        return f"[mock] based on {len(context.split())} words of context"
