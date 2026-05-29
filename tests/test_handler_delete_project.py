"""Unit tests for the ``delete_project`` handler (hard-delete via AppleScript).

* KIND constant is "delete_project"
* in NEVER_BYPASS_KINDS
* undo_log written BEFORE AppleScript call (V2 acceptance gate)
* flag-off raises cleanly
* project-not-found and already-in-Trash guard
* undo moves project to Anytime
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import applescript, things_repo
from things_mcp.services.handlers import delete_project
from things_mcp.state import undo_log


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
    area: str | None = None,
) -> dict:
    return {
        "uuid": uuid,
        "type": "project",
        "title": title,
        "status": "incomplete",
        "list": list_name,
        "area": area,
        "modified": "2026-05-29 10:00:00",
    }


# ---------- KIND and NEVER_BYPASS_KINDS ----------


def test_kind_constant():
    assert delete_project.KIND == "delete_project"


def test_kind_in_never_bypass_kinds():
    assert "delete_project" in config.NEVER_BYPASS_KINDS


# ---------- execute — flag gate ----------


async def test_execute_raises_when_applescript_disabled(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_APPLESCRIPT", False)
    with pytest.raises(RuntimeError, match="THINGS_MCP_ALLOW_APPLESCRIPT"):
        await delete_project.execute({"project_id": "proj-abc"})


# ---------- execute — input validation ----------


async def test_execute_raises_when_project_missing(applescript_enabled, monkeypatch):
    monkeypatch.setattr(things_repo, "get_project_row", lambda uuid: None)
    with pytest.raises(ValueError, match="No project found"):
        await delete_project.execute({"project_id": "ghost-uuid"})


async def test_execute_raises_when_already_in_trash(applescript_enabled, monkeypatch):
    monkeypatch.setattr(
        things_repo, "get_project_row",
        lambda uuid: _project(list_name="Trash"),
    )
    with pytest.raises(ValueError, match="already in Trash"):
        await delete_project.execute({"project_id": "proj-abc"})


# ---------- execute — undo_log written BEFORE AppleScript ----------


async def test_undo_log_written_before_applescript(applescript_enabled, monkeypatch):
    """The undo_log row must exist before run_script is called."""
    pre_script_rows: list[dict] = []

    monkeypatch.setattr(things_repo, "get_project_row", lambda uuid: _project())

    async def recording_run(script: str) -> str:
        pre_script_rows.extend(undo_log.recent(limit=10))
        return ""

    monkeypatch.setattr(applescript, "run_script", recording_run)

    await delete_project.execute({"project_id": "proj-abc"})

    assert len(pre_script_rows) == 1
    assert pre_script_rows[0]["action_kind"] == "delete_project"
    assert pre_script_rows[0]["target_uuid"] == "proj-abc"


# ---------- execute — AppleScript shape ----------


async def test_execute_calls_applescript_delete(
    applescript_enabled, captured_scripts, monkeypatch
):
    monkeypatch.setattr(things_repo, "get_project_row", lambda uuid: _project())

    await delete_project.execute({"project_id": "proj-abc"})

    assert len(captured_scripts) == 1
    script = captured_scripts[0]
    assert "Things3" in script
    assert "delete" in script
    assert "proj-abc" in script


async def test_execute_returns_undo_id_and_note(
    applescript_enabled, captured_scripts, monkeypatch
):
    monkeypatch.setattr(
        things_repo, "get_project_row",
        lambda uuid: _project(title="My Project"),
    )

    result = await delete_project.execute({"project_id": "proj-abc"})

    assert result["action_kind"] == "delete_project"
    assert result["id"] == "proj-abc"
    assert result["title"] == "My Project"
    assert "undo_id" in result
    assert "Trash" in result["note"]


# ---------- undo — flag gate ----------


async def test_undo_raises_when_applescript_disabled(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_APPLESCRIPT", False)
    with pytest.raises(RuntimeError, match="THINGS_MCP_ALLOW_APPLESCRIPT"):
        await delete_project.undo({
            "id": "entry-1",
            "action_kind": "delete_project",
            "target_uuid": "proj-abc",
            "before_state": {"original_area": None},
        })


# ---------- undo — restore to Anytime ----------


async def test_undo_restores_to_anytime(
    applescript_enabled, captured_scripts, monkeypatch
):
    entry_id = undo_log.record(
        action_kind="delete_project",
        target_uuid="proj-abc",
        before_state={
            "full": _project(),
            "title": "Test Project",
            "original_area": None,
        },
        after_state={"status": "trashed"},
    )

    result = await delete_project.undo(undo_log.get(entry_id))

    assert result["undone"] is True
    assert result["target_uuid"] == "proj-abc"
    assert result["restored_to"] == "Anytime"
    script = captured_scripts[0]
    assert "move" in script
    assert "Anytime" in script
    assert "proj-abc" in script


async def test_undo_deletes_log_row(
    applescript_enabled, captured_scripts, monkeypatch
):
    entry_id = undo_log.record(
        action_kind="delete_project",
        target_uuid="proj-abc",
        before_state={"original_area": None},
        after_state={"status": "trashed"},
    )

    await delete_project.undo(undo_log.get(entry_id))

    assert undo_log.get(entry_id) is None


# ---------- make_preview ----------


def test_make_preview_mentions_trash_and_undo():
    preview = delete_project.make_preview({"project_id": "proj-abc"})
    assert "proj-abc" in preview
    assert "Trash" in preview
    assert "undo" in preview.lower()
