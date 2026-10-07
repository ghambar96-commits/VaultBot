# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security vulnerabilities.

Preferred process (responsible disclosure):

1. Use GitHub's **private vulnerability reporting** on this repository:
   *Security* tab → *Report a vulnerability*. This keeps the report private
   until a fix is available.
2. If private reporting is not available, open an issue with a **minimal,
   non-exploitable description** and explicitly ask the maintainers for a
   private channel — do not include reproduction details, payloads or
   credentials in the public issue.

When reporting, please include:

- a description of the issue,
- reproduction steps (as far as safe to share),
- affected version/commit.

No public security contact address is published at this time; the GitHub
repository itself is the point of contact.

## Design highlights

- **Secrets** are only read from environment variables (`.env`); `.env` is
  git-ignored and never committed. The bot refuses to start without a token.
- **User isolation** is enforced in the repository layer: every read/write is
  filtered by `user_id`. Cross-user access returns nothing.
- **SQL/FTS injection**: all queries are parameterized; free-text search input
  is sanitized into quoted FTS5 tokens; `update_item_fields` only accepts an
  allow-list of columns.
- **Privacy**: logs never contain message content (a logging filter plus a
  no-content-logging policy in the code).
- **No media on disk**: files are referenced via Telegram `file_id`s and are
  never stored persistently; temporary AI downloads are deleted in
  `finally` blocks and swept periodically.

## Supported versions

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |
| older   | :x:                |
