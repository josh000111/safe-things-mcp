# safe-things-mcp — Project Instructions

Adds to (does not override) `~/.claude/CLAUDE.md`. Governs **dev and in-repo testing only** — does not travel with the MCP to end users. Runtime safety must live in the code, not here.

## Project

Python FastMCP **stdio** server for Things 3 on macOS. V1: full reads (read-only SQLite), writes **Inbox-only** via the Things URL scheme. V2: full-parity writes behind propose/confirm + undo.

## Hard rules

- **Before any write-path test, run `whoami`.** If it returns `joshsmith` (main user), STOP and confirm with the user. Write tests should run as the `Test` user.
- **If a session genuinely needs to touch the main user's real Things DB, run `backup_things3.sh` first** and confirm a fresh timestamped `.thingsdatabase` landed in `~/Documents/Things DB Backups (Cultured Code)/`.
- **Never edit `~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/` directly.** All writes go through the URL scheme. The Inbox-only guard lives in `services/url_scheme.py` (`build_add_url` must raise `ValueError` for non-Inbox lists) — do not add a bypass.

## V2 acceptance gate

No mutating tool ships in V2 without (a) an inverse URL-scheme call, (b) a row written to `undo_log` *before* the mutation, and (c) a passing round-trip undo test. Propose/confirm is the second layer.

## Verification before "done"

Overrides the global ask-before-complete fallback. Before claiming a task done:

1. `uv run pytest` — all green (or state clearly that no tests cover the change).
2. `uv run safe-things-mcp --help` runs without error.
3. `health()` returns `things_db_path`, `things_app_running=true`, `things_py_version`, `state_db_exists=true`.
4. Write-path / URL-scheme changes: run relevant items from `tests/safe-things-mcp-manual-verification.md` as the `Test` user.
5. V2 destructive ops: undo round-trip proven.

If a step can't run in the current environment, say so explicitly — never silently skip.

## Conventions

- Python 3.11+, `uv run …` (never bare `python`).
