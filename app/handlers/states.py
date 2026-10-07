"""FSM states for multi-step interactions (kept tiny on purpose)."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class VaultStates(StatesGroup):
    waiting_search = State()          # user pressed 🔎; next text = query
    waiting_note = State()            # data: item_id
    waiting_tag = State()             # data: item_id
    waiting_folder_name = State()     # data: item_id (optional) for create+move
