"""Optional OpenAI-compatible provider.

Only loaded when AI_PROVIDER=openai and AI_API_KEY is set. Uses plain HTTP
(urllib) so there is no extra heavy dependency; swap freely for any other
API by implementing `AIProvider`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.request

from .base import AIProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini",
                 base_url: str = "https://api.openai.com/v1") -> None:
        self.api_key = api_key
        self.model = model or "gpt-4o-mini"
        self.base_url = base_url.rstrip("/")

    async def _chat(self, system: str, user: str, max_tokens: int = 400) -> str | None:
        payload = json.dumps({
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }).encode()

        def _call() -> str | None:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"]

        try:
            return await asyncio.to_thread(_call)
        except Exception:  # AI must never crash the bot
            logger.exception("AI request failed")
            return None

    async def summarize(self, text: str, *, max_words: int = 80) -> str | None:
        if not text:
            return None
        return await self._chat(
            f"Summarize the user's text in at most {max_words} words. "
            "Reply with the summary only.",
            text[:12000],
        )

    async def generate_tags(self, text: str, *, max_tags: int = 5) -> list[str]:
        if not text:
            return []
        raw = await self._chat(
            f"Suggest up to {max_tags} short lowercase tags for the text. "
            "Reply with tags separated by spaces, nothing else.",
            text[:8000],
            max_tokens=60,
        )
        if not raw:
            return []
        return [t.strip().lstrip("#").lower() for t in raw.split() if t.strip()][:max_tags]

    async def answer_search(self, question: str, context: str) -> str | None:
        if not question:
            return None
        return await self._chat(
            "Answer the question using ONLY the provided context. "
            "If the context is insufficient say so.",
            f"Context:\n{context[:12000]}\n\nQuestion: {question}",
        )
