"""Fix delete_project — try-cascade: project id first, fall back to to do id.

URL-scheme-created projects resolve as the ``project`` class. Catching the
-1728 error with a cascade lets us delete both active URL-scheme projects
(``project id``) and cancelled/Logbook ones (``to do id``).

Also verifies the V2 acceptance gate: undo_log written BEFORE AppleScript.
"""
from __future__ import annotations

import pytest

from safe_things_mcp import config
from safe_things_mcp.services import applescript, things_repo
from safe_things_mcp.services.handlers import delete_project
from safe_things_mcp.state import undo_log


pytestmark = pytest.mark.usefixtures("isolated_state_db")


@pytest.fixture(autouse=True)
def reset_auth_cache():
    applescript._reset_auth_cache()
    yield
    applescript._reset_auth_cache()


@pytest.fixture
def applescript_enabled(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_APPLESCRIPT", True)


@pytest.fixture
def captured_scripts(monkeypatch):
    scripts: list[str] = []

    async def fake_run(script: str) -> str:
        scripts.append(script)
        return ""

    monkeypatch.setattr(applescript, "run_script", fake_run)
    return scripts


def _project(
    uuid: str = "proj-abc",
    title: str = "Test Project",
    list_name: str = "Anytime",
) -> dict:
    return {
        "uuid": uuid,
        "type": "project",
        "title": title,
        "status": "incomplete",
        "list": list_name,
        "area": None,
        "modified": "2026-05-29 10:00:00",
    }


async def test_delete_script_uses_try_cascade(
    applescript_enabled, monkeypatch, captured_scripts
):
    """The delete AppleScript must try ``project id`` first, then ``to do id``."""
    monkeypatch.setattr(things_repo, "get_project_row", lambda uuid: _project(uuid))

    await delete_project.execute({"project_id": "proj-abc", "snapshot": {}})

    assert captured_scripts, "AppleScript must have been called"
    script = captured_scripts[0]
    assert 'project id "proj-abc"' in script, "must try project id first"
    assert 'to do id "proj-abc"' in script, "must fall back to to do id"
    assert "try" in script
    assert "on error" in script
    assert "end try" in script


async def test_undo_log_written_before_applescript(
    applescript_enabled, monkeypatch
):
    """undo_log entry must exist before the AppleScript fires (V2 gate)."""
    log_ids_at_applescript_time: list[int] = []

    async def fake_run(script: str) -> str:
        log_ids_at_applescript_time.extend(
            [e["id"] for e in undo_log.recent(limit=10)]
        )
        return ""

    monkeypatch.setattr(applescript, "run_script", fake_run)
    monkeypatch.setattr(things_repo, "get_project_row", lambda uuid: _project(uuid))

    await delete_project.execute({"project_id": "proj-abc", "snapshot": {}})

    assert log_ids_at_applescript_time, (
        "undo_log must already have an entry when AppleScript fires"
    )


async def test_undo_script_uses_try_cascade(
    applescript_enabled, monkeypatch, captured_scripts
):
    """The undo (restore) AppleScript must also use the project-id cascade."""
    monkeypatch.setattr(things_repo, "get_project_row", lambda uuid: _project(uuid))

    await delete_project.execute({"project_id": "proj-abc", "snapshot": {}})
    entries = undo_log.recent(limit=1)
    assert entries

    await delete_project.undo(entries[0])

    assert len(captured_scripts) == 2, "execute + undo must each fire one script"
    undo_script = captured_scripts[1]
    assert 'project id "proj-abc"' in undo_script
    assert 'to do id "proj-abc"' in undo_script
    assert "try" in undo_script
    assert "on error" in undo_script
    assert 'list "Anytime"' in undo_script
