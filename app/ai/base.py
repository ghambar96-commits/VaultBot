"""AI provider interface.

The bot must work 100% without any AI. This module only defines the
contract; concrete providers are selected in `get_provider()` based on env
config. When no provider is configured every method returns None and the
bot skips the feature gracefully.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class AIProvider(ABC):
    """Minimal contract for optional AI features."""

    name: str = "abstract"
    enabled: bool = True

    @abstractmethod
    async def summarize(self, text: str, *, max_words: int = 80) -> str | None:
        """Summarize plain text (e.g. a message or extracted PDF text)."""

    @abstractmethod
    async def generate_tags(self, text: str, *, max_tags: int = 5) -> list[str]:
        """Suggest short lowercase tags for the given text."""

    @abstractmethod
    async def answer_search(self, question: str, context: str) -> str | None:
        """Answer a question using the user's own stored context (future)."""


class NullProvider(AIProvider):
    """Default provider: does nothing, costs nothing, never fails the bot."""

    name = "none"

    async def summarize(self, text: str, *, max_words: int = 80) -> str | None:
        return None

    async def generate_tags(self, text: str, *, max_tags: int = 5) -> list[str]:
        return []

    async def answer_search(self, question: str, context: str) -> str | None:
        return None

    @property
    def enabled(self) -> bool:
        return False


def get_provider(kind: str, api_key: str = "", model: str = "") -> AIProvider:
    """Factory. Unknown/absent providers fall back to NullProvider."""
    kind = (kind or "none").lower()
    if kind == "openai" and api_key:
        from .openai_provider import OpenAIProvider
        return OpenAIProvider(api_key=api_key, model=model)
    if kind == "mock":
        from .mock_provider import MockProvider
        return MockProvider()
    return NullProvider()
