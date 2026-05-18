"""Shared pytest fixtures.

The biggest concern is keeping tests away from the real
``~/.things-mcp/state.db``. Every test that touches the state DB gets a
fresh, isolated SQLite file via the ``isolated_state_db`` fixture, which
monkeypatches the constants the state modules already imported at module
load time.
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.state import db as state_db


@pytest.fixture
def isolated_state_db(tmp_path, monkeypatch):
    """Point every state-DB code path at a tmp file for one test."""
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(config, "STATE_DIR", tmp_path)
    monkeypatch.setattr(config, "STATE_DB_PATH", db_path)
    monkeypatch.setattr(state_db, "STATE_DB_PATH", db_path)

    # Patch ensure_state_dir to be a no-op for the tmp path (it already exists).
    monkeypatch.setattr(config, "ensure_state_dir", lambda: None)
    monkeypatch.setattr(state_db, "ensure_state_dir", lambda: None)

    state_db.init_state_db()
    yield db_path
