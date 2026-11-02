"""Shared pytest fixtures.

The biggest concern is keeping tests away from the real
``~/.safe-things-mcp/state.db``. Every test that touches the state DB gets a
fresh, isolated SQLite file via the ``isolated_state_db`` fixture, which
monkeypatches the constants the state modules already imported at module
load time.
"""
from __future__ import annotations

import pytest

from safe_things_mcp import config
from safe_things_mcp.state import db as state_db


@pytest.fixture(autouse=True)
def _never_touch_real_things(request, monkeypatch):
    """Non-live tests must never reach the real Things app.

    Without this, any test whose path reached url_scheme.launch opened a real
    things:/// URL (dozens of "auth token incorrect" popups; an add URL needs no
    token and would create real to-dos). Tests that mock these themselves still win,
    because their monkeypatch runs after this one. Live tests opt out by file name.
    """
    if request.node.path.name.endswith("_live.py"):
        return
    from safe_things_mcp.services import applescript, url_scheme

    async def _no_launch(url: str) -> None:
        return None

    async def _no_script(*args, **kwargs) -> str:
        return ""

    monkeypatch.setattr(url_scheme, "launch", _no_launch)
    # The wrapper's own tests exercise run_script itself (with osascript mocked).
    if request.node.path.name != "test_applescript_wrapper.py":
        monkeypatch.setattr(applescript, "run_script", _no_script)


@pytest.fixture(autouse=True)
def _no_real_duplicate_query(request, monkeypatch):
    """Propose-time ambiguity checks must not read the real Things DB.

    Default: nothing is ambiguous. Tests that want ambiguity patch
    ``things_repo.live_uuids_by_title`` themselves; the helper's own SQL test
    (``*live_uuids_repo*``) opts out and runs it against a temp DB.
    """
    if "live_uuids_repo" in request.node.path.name or request.node.path.name.endswith("_live.py"):
        return
    from safe_things_mcp.services import things_repo

    monkeypatch.setattr(
        things_repo, "live_uuids_by_title", lambda kind, titles, project_uuid=None: {}
    )


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
