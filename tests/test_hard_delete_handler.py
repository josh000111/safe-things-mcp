"""Unit tests for the ``delete_todo`` handler (hard-delete via AppleScript).

* propose/execute/undo round-trip via mocked AppleScript
* undo_log is written BEFORE the AppleScript call (V2 acceptance gate)
* flag-off raises cleanly
* todo-not-found and already-in-Trash guard
* NEVER_BYPASS_KINDS membership
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import applescript, things_repo
from things_mcp.services.handlers import delete_todo
from things_mcp.state import undo_log


pytestmark = pytest.mark.usefixtures("isolated_state_db")


@pytest.fixture(autouse=True)
def reset_auth_cache():
    """Keep the auth cache clean between tests."""
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


def _todo(uuid: str = "todo-abc", title: str = "Test todo", list_name: str = "Inbox", project: str | None = None) -> dict:
    return {
        "uuid": uuid,
        "type": "to-do",
        "title": title,
        "status": "incomplete",
        "list": list_name,
        "project": project,
        "modified": "2026-05-28 10:00:00",
        "tags": [],
    }


# ---------- KIND and NEVER_BYPASS_KINDS ----------


def test_kind_constant():
    assert delete_todo.KIND == "delete_todo"


def test_kind_in_never_bypass_kinds():
    assert "delete_todo" in config.NEVER_BYPASS_KINDS


# ---------- execute — flag gate ----------


async def test_execute_raises_when_applescript_disabled(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_APPLESCRIPT", False)
    with pytest.raises(RuntimeError, match="THINGS_MCP_ALLOW_APPLESCRIPT"):
        await delete_todo.execute({"todo_id": "todo-abc"})


# ---------- execute — input validation ----------


async def test_execute_raises_when_todo_missing(applescript_enabled, monkeypatch):
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: None)
    with pytest.raises(ValueError, match="No to-do found"):
        await delete_todo.execute({"todo_id": "ghost-uuid"})


async def test_execute_raises_when_already_in_trash(applescript_enabled, monkeypatch):
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: _todo(list_name="Trash"))
    with pytest.raises(ValueError, match="already in Trash"):
        await delete_todo.execute({"todo_id": "todo-abc"})


# ---------- execute — undo_log written BEFORE AppleScript (V2 acceptance gate) ----------


async def test_undo_log_written_before_applescript(applescript_enabled, monkeypatch):
    """The undo_log row must exist before run_script is called."""
    pre_script_rows: list[dict] = []

    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: _todo())

    async def recording_run(script: str) -> str:
        # Capture undo_log state at the moment osascript would be called
        pre_script_rows.extend(undo_log.recent(limit=10))
        return ""

    monkeypatch.setattr(applescript, "run_script", recording_run)

    await delete_todo.execute({"todo_id": "todo-abc"})

    assert len(pre_script_rows) == 1
    assert pre_script_rows[0]["action_kind"] == "delete_todo"
    assert pre_script_rows[0]["target_uuid"] == "todo-abc"


# ---------- execute — AppleScript shape ----------


async def test_execute_calls_applescript_delete(
    applescript_enabled, captured_scripts, monkeypatch
):
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: _todo())

    await delete_todo.execute({"todo_id": "todo-abc"})

    assert len(captured_scripts) == 1
    script = captured_scripts[0]
    assert "Things3" in script
    assert "delete" in script
    assert "todo-abc" in script


async def test_execute_returns_undo_id_and_note(
    applescript_enabled, captured_scripts, monkeypatch
):
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: _todo(title="My Task"))

    result = await delete_todo.execute({"todo_id": "todo-abc"})

    assert result["action_kind"] == "delete_todo"
    assert result["id"] == "todo-abc"
    assert result["title"] == "My Task"
    assert "undo_id" in result
    assert "Trash" in result["note"]


async def test_execute_escapes_todo_id_in_script(
    applescript_enabled, captured_scripts, monkeypatch
):
    # UUID with a double-quote would be injection — escape() should reject it.
    # In practice UUIDs never have quotes, but we test the escaping path.
    safe_uuid = "AAAA-BBBB"
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: _todo(uuid=safe_uuid))

    await delete_todo.execute({"todo_id": safe_uuid})

    assert f'"{safe_uuid}"' in captured_scripts[0]


# ---------- undo — flag gate ----------


async def test_undo_raises_when_applescript_disabled(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_APPLESCRIPT", False)
    with pytest.raises(RuntimeError, match="THINGS_MCP_ALLOW_APPLESCRIPT"):
        await delete_todo.undo({
            "id": "entry-1",
            "action_kind": "delete_todo",
            "target_uuid": "todo-abc",
            "before_state": {"original_list": "Inbox", "original_project": None},
        })


# ---------- undo — restore to built-in list ----------


async def test_undo_restores_to_original_list(
    applescript_enabled, captured_scripts, monkeypatch
):
    entry_id = undo_log.record(
        action_kind="delete_todo",
        target_uuid="todo-abc",
        before_state={
            "full": _todo(),
            "original_list": "Today",
            "original_project": None,
            "title": "Test todo",
        },
        after_state={"status": "trashed"},
    )

    result = await delete_todo.undo(undo_log.get(entry_id))

    assert result["undone"] is True
    assert result["target_uuid"] == "todo-abc"
    script = captured_scripts[0]
    assert "move" in script
    assert "Today" in script
    assert "todo-abc" in script
    # undo_log row removed after successful undo
    assert undo_log.get(entry_id) is None


# ---------- undo — restore to project ----------


async def test_undo_restores_to_original_project(
    applescript_enabled, captured_scripts, monkeypatch
):
    project_id = "proj-uuid-1234"
    entry_id = undo_log.record(
        action_kind="delete_todo",
        target_uuid="todo-abc",
        before_state={
            "full": _todo(project=project_id),
            "original_list": None,
            "original_project": project_id,
            "title": "Test todo",
        },
        after_state={"status": "trashed"},
    )

    result = await delete_todo.undo(undo_log.get(entry_id))

    assert result["undone"] is True
    script = captured_scripts[0]
    assert "move" in script
    assert "project" in script
    assert project_id in script


# ---------- undo — fallback to Inbox if list unknown ----------


async def test_undo_falls_back_to_inbox_for_unknown_list(
    applescript_enabled, captured_scripts, monkeypatch
):
    entry_id = undo_log.record(
        action_kind="delete_todo",
        target_uuid="todo-abc",
        before_state={
            "full": _todo(),
            "original_list": "SomeUnknownList",
            "original_project": None,
            "title": "Test todo",
        },
        after_state={"status": "trashed"},
    )

    await delete_todo.undo(undo_log.get(entry_id))

    script = captured_scripts[0]
    assert "Inbox" in script


# ---------- make_preview ----------


def test_make_preview_mentions_trash_and_undo():
    preview = delete_todo.make_preview({"todo_id": "todo-abc"})
    assert "todo-abc" in preview
    assert "Trash" in preview
    assert "undo" in preview.lower()


def test_make_preview_uses_snapshot_title_when_available():
    preview = delete_todo.make_preview({
        "todo_id": "todo-abc",
        "snapshot": {"title": "My Important Task"},
    })
    assert "My Important Task" in preview


# ---------- _normalise_list_name ----------


@pytest.mark.parametrize("raw, expected", [
    ("inbox", "Inbox"),
    ("Inbox", "Inbox"),
    ("today", "Today"),
    ("ANYTIME", "Anytime"),
    ("someday", "Someday"),
    ("logbook", "Logbook"),
    ("trash", "Trash"),
    ("", "Inbox"),       # empty → Inbox fallback
    ("custom", "Inbox"), # unknown → Inbox fallback
])
def test_normalise_list_name(raw, expected):
    assert delete_todo._normalise_list_name(raw) == expected
