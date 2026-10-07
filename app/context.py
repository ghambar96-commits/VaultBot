"""Shared application context passed to every handler via workflow_data."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .ai.base import AIProvider
from .config import Settings


@dataclass
class AppContext:
    conn: sqlite3.Connection
    settings: Settings
    ai: AIProvider
