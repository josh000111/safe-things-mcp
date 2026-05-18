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
"""


def init_state_db() -> None:
    ensure_state_dir()
    with connect() as conn:
        conn.executescript(SCHEMA_SQL)
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
