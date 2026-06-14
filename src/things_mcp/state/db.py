"""SQLite bootstrap for ~/.things-mcp/state.db."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from ..config import STATE_DB_PATH, ensure_state_dir

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pending_actions (
    id           TEXT PRIMARY KEY,
    kind         TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    preview      TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    expires_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pending_expires_at
    ON pending_actions(expires_at);

CREATE TABLE IF NOT EXISTS undo_log (
    id                TEXT PRIMARY KEY,
    action_kind       TEXT NOT NULL,
    target_uuid       TEXT,
    before_state_json TEXT,
    after_state_json  TEXT,
    created_at        TEXT NOT NULL,
    expires_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_undo_target_uuid
    ON undo_log(target_uuid);

CREATE INDEX IF NOT EXISTS idx_undo_created_at
    ON undo_log(created_at DESC);

CREATE TABLE IF NOT EXISTS ai_tag_routing (
    id            TEXT PRIMARY KEY,
    tag_name      TEXT NOT NULL,
    todo_uuid     TEXT NOT NULL,
    dest_kind     TEXT,
    dest_uuid     TEXT,
    transient     INTEGER NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_tag_routing_tag_name
    ON ai_tag_routing(tag_name);

CREATE INDEX IF NOT EXISTS idx_ai_tag_routing_todo_uuid
    ON ai_tag_routing(todo_uuid);

CREATE TABLE IF NOT EXISTS sort_session (
    group_id   TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    active     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sort_session_tagged (
    group_id  TEXT NOT NULL,
    todo_uuid TEXT NOT NULL,
    PRIMARY KEY (group_id, todo_uuid)
);

CREATE INDEX IF NOT EXISTS idx_sort_session_tagged_group
    ON sort_session_tagged(group_id);

CREATE TABLE IF NOT EXISTS sort_session_project (
    group_id     TEXT NOT NULL,
    project_uuid TEXT NOT NULL,
    PRIMARY KEY (group_id, project_uuid)
);

CREATE INDEX IF NOT EXISTS idx_sort_session_project_group
    ON sort_session_project(group_id);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """Apply additive schema migrations to an existing DB."""
    try:
        conn.execute("ALTER TABLE undo_log ADD COLUMN group_id TEXT")
    except sqlite3.OperationalError as exc:
        if "duplicate column name" not in str(exc):
            raise


def init_state_db() -> None:
    ensure_state_dir()
    with connect() as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate(conn)
        conn.commit()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    ensure_state_dir()
    conn = sqlite3.connect(STATE_DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()
