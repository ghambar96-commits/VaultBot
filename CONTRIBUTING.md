# Contributing to VaultBot

Thanks for your interest! VaultBot aims to stay **simple, small and
disk-frugal**. Please keep those priorities when contributing.

## Ground rules

1. **No permanent file storage.** VaultBot must never write media files to
   disk. Only SQLite metadata and short-lived temp files (always cleaned up)
   are allowed.
2. **No heavy dependencies.** No Redis, no PostgreSQL, no Elasticsearch, no
   microservices. SQLite + aiogram is the stack.
3. **AI stays optional.** Anything AI-related must degrade gracefully when no
   API key is configured.
4. **User isolation is sacred.** Every query must stay scoped by `user_id`.
5. Keep the code readable for beginners — clear names over clever tricks.

## Development setup

```bash
git clone <repository-url> vaultbot
cd vaultbot
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env    # set BOT_TOKEN for manual testing
```

## Running the tests

The whole suite runs offline — no bot token, no network:

```bash
pytest
```

Any new feature needs tests covering at least the happy path, user isolation
and the relevant edge cases.

## Code style

- Run `ruff check app tests` before submitting a PR (CI enforces it).
- Type hints for function signatures, docstrings for modules and non-obvious
  functions.
- User-facing strings live in `app/utils/messages.py` — don't hardcode
  Persian strings elsewhere.

## Pull request process

1. Fork the repo and create a branch from `main`.
2. Keep PRs focused: one feature or fix per PR.
3. Make sure `pytest` and `ruff check` pass.
4. Describe what changed and why; include test output for new behavior.

## Architecture notes

See the **Architecture** and **Storage Model** sections of the README before
touching the database layer or the save/restore flow — those are the heart of
the project.
