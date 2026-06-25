"""Fix 2D — undo of move-to-Inbox must restore project membership.

When a task belongs to a project and is moved to Inbox, the undo must
restore BOTH the schedule (via ``when=``) AND the project (via ``list-id=``).
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import applescript, things_repo, url_scheme
from things_mcp.services.handlers import move_todo
from things_mcp.state import undo_log


pytestmark = pytest.mark.usefixtures("isolated_state_db")


@pytest.fixture(autouse=True)
def _enable_applescript_and_auth(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_APPLESCRIPT", True)
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", "tok-test")
    monkeypatch.setattr(config, "WRITE_POLL_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(config, "WRITE_POLL_INTERVAL_SECONDS", 0.01)


@pytest.fixture
def captured_scripts(monkeypatch):
    scripts: list[str] = []

    async def fake_run(script: str) -> str:
        scripts.append(script)
        return ""

    monkeypatch.setattr(applescript, "run_script", fake_run)
    return scripts


@pytest.fixture
def captured_launches(monkeypatch):
    launches: list[str] = []

    async def fake_launch(url: str) -> None:
        launches.append(url)

    monkeypatch.setattr(url_scheme, "launch", fake_launch)
    return launches


def _row(
    uuid: str = "t1",
    start: str = "Anytime",
    start_date: str | None = None,
    project: str | None = None,
    modified: str = "2026-05-19 10:00:00",
) -> dict:
    row: dict = {
        "uuid": uuid,
        "type": "to-do",
        "title": "task",
        "status": "incomplete",
        "start": start,
        "start_date": start_date,
        "modified": modified,
    }
    if project is not None:
        row["project"] = project
    return row


async def test_move_to_inbox_fires_applescript(
    monkeypatch, captured_scripts, captured_launches
):
    """Moving to inbox must call AppleScript move-to-Inbox."""
    before_row = _row(uuid="t1", project="proj-1", start="Anytime")
    after_row = {**before_row, "start": "Inbox", "modified": "2026-05-19 10:00:01"}
    call_count = 0

    def fake_get_todo(uuid: str) -> dict:
        nonlocal call_count
        call_count += 1
        return before_row if call_count == 1 else after_row

    monkeypatch.setattr(things_repo, "get_todo", fake_get_todo)

    result = await move_todo.execute({"todo_id": "t1", "target": "inbox"})

    assert result["dimension"] == "inbox"
    assert any('move to do id "t1" to list "Inbox"' in s for s in captured_scripts)
    assert captured_launches == [], "inbox move must NOT use the URL scheme"


async def test_undo_move_to_inbox_restores_project_and_schedule(
    monkeypatch, captured_scripts, captured_launches
):
    """Undo of a move-to-inbox for a task that was in a project must include
    BOTH list-id=<project> and when=anytime in the update URL."""
    before_row = _row(uuid="t1", project="proj-1", start="Anytime")
    after_row = {**before_row, "start": "Inbox", "modified": "2026-05-19 10:00:01"}
    call_count = 0

    def fake_get_todo(uuid: str) -> dict:
        nonlocal call_count
        call_count += 1
        return before_row if call_count == 1 else after_row

    monkeypatch.setattr(things_repo, "get_todo", fake_get_todo)

    result = await move_todo.execute({"todo_id": "t1", "target": "inbox"})
    entry = undo_log.get(result["undo_id"])
    assert entry is not None

    # For undo polling: return a row with an advanced modified timestamp
    monkeypatch.setattr(
        things_repo,
        "get_todo",
        lambda uuid: {**after_row, "modified": "2026-05-19 10:00:02"},
    )

    await move_todo.undo(entry)

    assert captured_launches, "undo must fire a URL-scheme update"
    undo_url = captured_launches[-1]
    assert "list-id=proj-1" in undo_url, "undo URL must include original project"
    assert "when=anytime" in undo_url, "undo URL must include original schedule"


async def test_undo_move_to_inbox_no_project_omits_list_id(
    monkeypatch, captured_scripts, captured_launches
):
    """Undo of a move-to-inbox for a task with NO project must NOT include list-id."""
    before_row = _row(uuid="t2", project=None, start="Anytime")
    after_row = {**before_row, "start": "Inbox", "modified": "2026-05-19 10:00:01"}
    call_count = 0

    def fake_get_todo(uuid: str) -> dict:
        nonlocal call_count
        call_count += 1
        return before_row if call_count == 1 else after_row

    monkeypatch.setattr(things_repo, "get_todo", fake_get_todo)

    result = await move_todo.execute({"todo_id": "t2", "target": "inbox"})
    entry = undo_log.get(result["undo_id"])
    assert entry is not None

    monkeypatch.setattr(
        things_repo,
        "get_todo",
        lambda uuid: {**after_row, "modified": "2026-05-19 10:00:02"},
    )

    await move_todo.undo(entry)

    assert captured_launches, "undo must fire a URL-scheme update"
    undo_url = captured_launches[-1]
    assert "list-id" not in undo_url, "undo URL must NOT include list-id when task had no project"
    assert "when=anytime" in undo_url
