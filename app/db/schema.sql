-- VaultBot database schema
-- Design goal: store ONLY metadata + Telegram references.
-- File bytes always stay on Telegram's servers (accessed via file_id).

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- users: minimal info, only what the bot needs.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ---------------------------------------------------------------------------
-- folders: user-defined groups for items.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS folders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_folders_user ON folders(user_id);

-- ---------------------------------------------------------------------------
-- items: the core table. One row per saved thing.
-- NOTE: file bytes are NOT stored here, only Telegram references.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS items (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                   INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    telegram_message_id       INTEGER,            -- message id in the bot chat
    telegram_file_id          TEXT,               -- to fetch/resend the file later
    telegram_file_unique_id   TEXT,               -- stable id, used for duplicates
    type                      TEXT NOT NULL,      -- text|link|photo|video|document|audio|voice|animation|sticker
    mime_type                 TEXT,
    original_name             TEXT,               -- filename if any
    file_size                 INTEGER,            -- bytes, metadata only
    caption                   TEXT,               -- caption for media
    text                      TEXT,               -- plain text content
    source_chat_id            INTEGER,            -- where a forward came from (best effort)
    source_message_id         INTEGER,
    folder_id                 INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    summary                   TEXT,               -- AI summary (optional)
    note                      TEXT,               -- user's private note
    tags                      TEXT NOT NULL DEFAULT '',  -- space separated, e.g. "python cyber"
    favorite                  INTEGER NOT NULL DEFAULT 0,   -- starred items
    created_at                TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    deleted                   INTEGER NOT NULL DEFAULT 0,   -- soft delete flag
    deleted_at                TEXT
);

CREATE INDEX IF NOT EXISTS idx_items_user        ON items(user_id);
CREATE INDEX IF NOT EXISTS idx_items_user_live   ON items(user_id, deleted, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_user_folder ON items(user_id, folder_id);
CREATE INDEX IF NOT EXISTS idx_items_user_type   ON items(user_id, type);
-- note: idx_items_user_fav is created in database.migrate() because older
-- databases don't have the favorite column yet.
-- duplicate detection within one user's vault
CREATE INDEX IF NOT EXISTS idx_items_unique_file ON items(user_id, telegram_file_unique_id);

-- ---------------------------------------------------------------------------
-- tags: normalized per-user tag list (helps /tags and future AI suggestions).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tags (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name     TEXT    NOT NULL,
    UNIQUE (user_id, name)
);

-- ---------------------------------------------------------------------------
-- item_tags: many-to-many between items and tags.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS item_tags (
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
    PRIMARY KEY (item_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_item_tags_tag ON item_tags(tag_id);

-- ---------------------------------------------------------------------------
-- reminders: simple datetime based reminders attached to an item.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reminders (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    item_id   INTEGER REFERENCES items(id) ON DELETE CASCADE,
    remind_at TEXT NOT NULL,          -- ISO-8601 UTC
    message   TEXT,
    sent      INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(sent, remind_at);

-- ---------------------------------------------------------------------------
-- Full-text search (FTS5). Standalone table (not external-content) so the
-- service layer controls syncing explicitly — easier to understand.
-- rowid always matches items.id.
-- remove_diacritics 2 helps with accented / Arabic-script text.
-- ---------------------------------------------------------------------------
-- content=''           -> contentless: FTS stores only the index (tiny on disk)
-- contentless_delete=1  -> rows can be removed by rowid (needs SQLite >= 3.43)
CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
    original_name,
    caption,
    text,
    note,
    tags,
    summary,
    content='',
    contentless_delete=1,
    tokenize = "unicode61 remove_diacritics 2"
);
