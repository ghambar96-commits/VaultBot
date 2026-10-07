# Changelog

All notable changes to VaultBot are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.2.0] - 2026-10-07

### Added
- **Media restore** extracted into `services/media.py` with status codes
  (`ok`, `text`, `not_found`, `forbidden`, `no_file_id`, `unknown_type`,
  `api_error`) and one retry on transient network errors.
- **Favorites**: `favorite` column (with automatic migration for old DBs),
  ⭐ toggle button, `/fav`, `/favorites`.
- **Quick actions**: `/recent` (paginated), `/random`.
- **Trash purge**: `/emptytrash` permanently removes soft-deleted items and
  runs VACUUM (the only automatic VACUUM in the codebase).
- **`/storage` command**: real filesystem usage report (DB, backups, tmp, logs).
- **Storage safety**: temp dir size cap (oldest-first eviction) in addition to
  the age sweep; optional rotating file log (`LOG_FILE`, 5MB x 3).
- **Backup safety**: every snapshot is verified with `PRAGMA quick_check`
  before being kept.
- **Search UX**: result lists now show a truncated text summary (type, name,
  date) above the clickable buttons.
- **UX**: clean save card (`✅ ذخیره شد` + name + tags + folder) and a rich
  item detail view (type, name, size, folder, tags, note, summary, source).
- AI tag suggestion wired into `/tag` when an AI provider is enabled.
- GitHub release files: LICENSE (MIT), CONTRIBUTING, SECURITY, CHANGELOG,
  `.dockerignore`, CI workflow.

### Changed
- `item_detail_text` now resolves folder names and shows source metadata.
- Inline keyboards restructured (open / tag / folder / note / delete / resend).

### Fixed
- Search no longer mutates the (frozen) aiogram `Message` object.
- `favorite` index is created in the migration, so old databases upgrade cleanly.

## [0.1.0] - 2026-10-07

### Added
- Initial MVP: save everything, FTS5 search, tags, folders, notes, duplicate
  detection, reminders, soft delete/restore, stats, backups, optional AI
  summarization, Docker deployment, full offline test suite.
