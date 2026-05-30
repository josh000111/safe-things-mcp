"""Live integration tests for V2 Step 5A — Items 132, 133, 135.

These tests require:
  - Things 3 running on macOS
  - Automation permission granted to this process / terminal
  - THINGS_AUTH_TOKEN env var set

They do NOT require THINGS_MCP_ALLOW_APPLESCRIPT in the environment;
the flag is patched via monkeypatch so that the config module sees it
as True for the duration of each test.

Run as the Test user:
    THINGS_AUTH_TOKEN=<token> uv run pytest tests/test_step5a_live.py -v -s
"""
from __future__ import annotations

import asyncio
import subprocess
import time

import pytest

from things_mcp import config
from things_mcp.services import applescript, things_repo
from things_mcp.services.handlers import hard_delete_todo
from things_mcp.state import undo_log
import things_mcp.tools.meta as meta_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_inbox_todo_via_applescript(title: str) -> str:
    """Create a todo in Things Inbox via AppleScript and return its id."""
    safe_title = applescript.escape(title)
    script = (
        f'tell application "Things3"\n'
        f'    set t to make new to do with properties {{name: "{safe_title}"}}\n'
        f'    return id of t\n'
        f'end tell'
    )
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"AppleScript todo creation failed: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _poll_for_todo(todo_id: str, timeout: float = 8.0) -> dict | None:
    """Poll Things DB until the todo with this id is readable."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = things_repo.get_todo(todo_id)
        if row is not None:
            return row
        time.sleep(0.25)
    return None


def _in_trash_via_applescript(todo_id: str) -> bool:
    """Return True if the todo appears in Things Trash list."""
    safe_id = applescript.escape(todo_id)
    script = (
        f'tell application "Things3"\n'
        f'    set trashItems to to dos of list "Trash"\n'
        f'    repeat with t in trashItems\n'
        f'        if id of t is "{safe_id}" then return "FOUND"\n'
        f'    end repeat\n'
        f'    return "NOT FOUND"\n'
        f'end tell'
    )
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, timeout=10
    )
    return result.stdout.strip() == "FOUND"


def _health_snapshot() -> dict:
    """Return the same fields health() would report."""
    reorder_available = (
        meta_mod._reorder_command_available() if config.ALLOW_APPLESCRIPT else None
    )
    return {
        "applescript_enabled": config.ALLOW_APPLESCRIPT,
        "experimental_reorder_enabled": config.ALLOW_APPLESCRIPT,
        "applescript_authorized": meta_mod._applescript_authorized(),
        "reorder_command_available": reorder_available,
    }


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
# Item 134 — flag-off health fields (live MCP already confirmed; repeat here
#             against the module constants as a fast sanity check)
# ---------------------------------------------------------------------------

def test_134_flags_off_health_fields():
    """Item 134: With no flag patching, health fields must show flags off."""
    snap = _health_snapshot()
    assert snap["applescript_enabled"] is False, (
        f"applescript_enabled should be False without patch; got {snap['applescript_enabled']}"
    )
    assert snap["experimental_reorder_enabled"] is False  # mirrors applescript_enabled
    assert snap["reorder_command_available"] is None, (
        f"reorder_command_available must be null when ALLOW_APPLESCRIPT is off; got {snap['reorder_command_available']}"
    )
    assert snap["applescript_authorized"] == "unknown"


# ---------------------------------------------------------------------------
# Item 135 — health fields with ALLOW_APPLESCRIPT=True (pre- and post-call)
# ---------------------------------------------------------------------------

def test_135_applescript_flag_on_health_before_call(applescript_on):
    """Item 135 pre-call: applescript_enabled=True, authorized still 'unknown'."""
    snap = _health_snapshot()
    assert snap["applescript_enabled"] is True
    assert snap["experimental_reorder_enabled"] is True  # mirrors applescript_enabled
    assert snap["reorder_command_available"] is not None  # checked when ALLOW_APPLESCRIPT is on
    assert snap["applescript_authorized"] == "unknown"


async def test_135_applescript_authorized_flips_after_verify(applescript_on):
    """Item 135 post-call: verify_authorization() flips applescript_authorized to True."""
    authorized = await applescript.verify_authorization()
    assert authorized is True, (
        "verify_authorization() returned False — check System Settings → "
        "Privacy & Security → Automation → enable Claude Desktop / Terminal → Things 3"
    )
    snap = _health_snapshot()
    assert snap["applescript_authorized"] is True, (
        f"applescript_authorized should be True after verify_authorization(); got {snap['applescript_authorized']}"
    )


# ---------------------------------------------------------------------------
# Items 132 + 133 — hard-delete round trip and undo
# ---------------------------------------------------------------------------

async def test_132_133_hard_delete_and_undo(applescript_on, isolated_state_db):
    """Items 132 and 133: propose→execute→Trash check→undo→restore check."""
    title = f"5A-HARDDELETE-{int(time.time())}"

    # ── 132 step 1: create test todo in Inbox via AppleScript ─────────────
    todo_id = _create_inbox_todo_via_applescript(title)
    assert todo_id, "AppleScript did not return a todo id"

    # Give Things a moment to flush to SQLite, then verify via DB
    todo = _poll_for_todo(todo_id, timeout=8.0)
    assert todo is not None, (
        f"Created todo {todo_id!r} ({title!r}) not visible in Things DB within 8 s"
    )
    print(f"\n  Created: id={todo_id}  title={title!r}  list={todo.get('list')!r}")

    # ── 132 step 2: execute hard-delete ────────────────────────────────────
    result = await hard_delete_todo.execute({"todo_id": todo_id})
    print(f"  execute() → {result}")
    assert result["action_kind"] == "delete_todo"
    assert result["id"] == todo_id
    assert result["undo_id"], "execute() must return a non-empty undo_id"
    undo_id = result["undo_id"]

    # ── 132 step 3: verify undo_log row was written BEFORE osascript ───────
    #   (The handler writes the row before calling run_script; if execute()
    #    returned successfully the row must already exist.)
    log_entry = undo_log.get(undo_id)
    assert log_entry is not None, f"undo_log row {undo_id!r} not found after execute()"
    assert log_entry["action_kind"] == "delete_todo"
    assert log_entry["target_uuid"] == todo_id

    # ── 132 step 4: verify todo is in Things Trash ─────────────────────────
    await asyncio.sleep(0.5)   # give Things a moment to reflect the change
    in_trash = _in_trash_via_applescript(todo_id)
    if not in_trash:
        pytest.fail(
            f"Todo {todo_id!r} ({title!r}) not found in Things Trash after execute(). "
            "Things SDEF 'delete' may purge immediately rather than moving to Trash — "
            "see handoff watchpoint for item 132."
        )
    print(f"  ✅ Item 132: todo {todo_id!r} found in Things Trash")

    # ── 133: undo restores from Trash ──────────────────────────────────────
    undo_result = await hard_delete_todo.undo(log_entry)
    print(f"  undo() → {undo_result}")
    assert undo_result["undone"] is True
    assert undo_result["target_uuid"] == todo_id
    restored_to = undo_result["restored_to"]

    await asyncio.sleep(0.5)   # give Things a moment to reflect the restore

    # Must no longer be in Trash
    still_in_trash = _in_trash_via_applescript(todo_id)
    assert not still_in_trash, (
        f"Todo {todo_id!r} still in Trash after undo() — move AppleScript may not have landed"
    )

    # Must be findable again in the active DB
    restored_row = things_repo.get_todo(todo_id)
    assert restored_row is not None, (
        f"get_todo({todo_id!r}) returned None after undo — todo may not be visible yet"
    )
    print(
        f"  ✅ Item 133: todo restored to list={restored_row.get('list')!r} "
        f"(reported restored_to={restored_to!r})"
    )

    # undo_log row should have been deleted after successful undo
    assert undo_log.get(undo_id) is None, "undo_log row should be deleted after undo()"
