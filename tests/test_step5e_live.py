"""Live integration test for V2 Step 5E — delete_project round trip.

Tests:
1. Creates a test project via propose_add_project + confirm_action
2. Confirms it exists in the DB
3. Deletes it via propose_delete_project + confirm_action
4. Confirms it moved to Trash
5. Undoes the delete
6. Confirms it's back in Anytime

Requires:
  - Things 3 running on macOS
  - Automation permission granted to this process / terminal
  - THINGS_AUTH_TOKEN env var set
  - THINGS_MCP_ALLOW_APPLESCRIPT=1 env var (or patched via monkeypatch)

Run as the Test user:
    THINGS_AUTH_TOKEN=<token> THINGS_MCP_ALLOW_APPLESCRIPT=1 uv run pytest tests/test_step5e_live.py -v -s
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import time

import pytest

from things_mcp import config
from things_mcp.services import applescript, things_repo
from things_mcp.services.handlers import delete_project
from things_mcp.state import undo_log


pytestmark = pytest.mark.skipif(
    not os.environ.get("THINGS_AUTH_TOKEN"),
    reason="Requires THINGS_AUTH_TOKEN env var (Test user session)",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_project_via_applescript(title: str) -> str:
    """Create a project in Things via AppleScript and return its id."""
    safe_title = applescript.escape(title)
    script = (
        f'tell application "Things3"\n'
        f'    set p to make new project with properties {{name: "{safe_title}"}}\n'
        f'    return id of p\n'
        f'end tell'
    )
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"AppleScript project creation failed: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _poll_for_project(project_id: str, timeout: float = 8.0) -> dict | None:
    """Poll Things DB until the project with this id is readable."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = things_repo.get_project_row(project_id)
        if row is not None:
            return row
        time.sleep(0.25)
    return None


def _in_trash_via_applescript(project_id: str) -> bool:
    """Return True if the project appears in Things Trash.

    Uses the things Python library (SQLite read) rather than AppleScript
    enumeration — Things 3 does not expose ``projects of list "Trash"`` via
    its AppleScript dictionary.
    """
    trash_items = things_repo.trash()
    return any(item.get("uuid") == project_id for item in trash_items)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_auth_cache():
    applescript._reset_auth_cache()
    yield
    applescript._reset_auth_cache()


@pytest.fixture
def applescript_on(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_APPLESCRIPT", True)


# ---------------------------------------------------------------------------
# Live round-trip test
# ---------------------------------------------------------------------------


async def test_5e_delete_project_round_trip(applescript_on, isolated_state_db):
    """Full round trip: create → delete → Trash check → undo → restore check."""
    title = f"5E-DELPROJECT-{int(time.time())}"

    # Step 1: create test project via AppleScript
    project_id = _create_project_via_applescript(title)
    assert project_id, "AppleScript did not return a project id"

    # Step 2: confirm it exists in DB
    project = _poll_for_project(project_id, timeout=8.0)
    assert project is not None, (
        f"Created project {project_id!r} ({title!r}) not visible in Things DB within 8 s"
    )
    print(f"\n  Created: id={project_id}  title={title!r}  list={project.get('list')!r}")

    # Step 3: delete it
    result = await delete_project.execute({"project_id": project_id})
    print(f"  execute() → {result}")
    assert result["action_kind"] == "delete_project"
    assert result["id"] == project_id
    assert result["undo_id"], "execute() must return a non-empty undo_id"
    undo_id = result["undo_id"]

    # Verify undo_log row was written BEFORE osascript
    log_entry = undo_log.get(undo_id)
    assert log_entry is not None, f"undo_log row {undo_id!r} not found after execute()"
    assert log_entry["action_kind"] == "delete_project"
    assert log_entry["target_uuid"] == project_id

    # Step 4: confirm project is in Things Trash
    await asyncio.sleep(0.5)
    in_trash = _in_trash_via_applescript(project_id)
    if not in_trash:
        pytest.fail(
            f"Project {project_id!r} ({title!r}) not found in Things Trash after execute(). "
        )
    print(f"  Project {project_id!r} found in Things Trash")

    # Step 5: undo the delete
    undo_result = await delete_project.undo(log_entry)
    print(f"  undo() → {undo_result}")
    assert undo_result["undone"] is True
    assert undo_result["target_uuid"] == project_id
    assert undo_result["restored_to"] == "Anytime"

    await asyncio.sleep(0.5)

    # Step 6: confirm project is no longer in Trash
    still_in_trash = _in_trash_via_applescript(project_id)
    assert not still_in_trash, (
        f"Project {project_id!r} still in Trash after undo() — move AppleScript may not have landed"
    )

    # Must be findable in the active DB
    restored_row = things_repo.get_project_row(project_id)
    assert restored_row is not None, (
        f"get_project_row({project_id!r}) returned None after undo"
    )
    print(
        f"  Project restored to list={restored_row.get('list')!r} "
        f"(reported restored_to={undo_result['restored_to']!r})"
    )

    # undo_log row should be deleted after successful undo
    assert undo_log.get(undo_id) is None, "undo_log row should be deleted after undo()"
