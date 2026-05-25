"""Unit tests for the ``add_heading`` handler.

* make_preview returns the dummy title
* execute validates project exists
* execute rejects invalid names
* execute success: undo_log recorded, result has undo_id and kind
* undo soft-deletes the dummy task and removes undo_log entry
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import things_repo, url_scheme
from things_mcp.services.handlers import add_heading
from things_mcp.state import undo_log


pytestmark = pytest.mark.usefixtures("isolated_state_db")


@pytest.fixture
def fast_polling(monkeypatch):
    monkeypatch.setattr(config, "WRITE_POLL_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(config, "WRITE_POLL_INTERVAL_SECONDS", 0.01)


@pytest.fixture
def captured_launches(monkeypatch):
    launches: list[str] = []

    async def fake_launch(url: str) -> None:
        launches.append(url)

    monkeypatch.setattr(url_scheme, "launch", fake_launch)
    return launches


@pytest.fixture
def with_auth(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", "tok-abc")


def _project_row(uuid: str = "PROJ-1") -> dict:
    return {"uuid": uuid, "type": "project", "title": "My Project", "items": []}


def _heading_row(
    uuid: str = "HDG-1",
    title: str = "__DESIGN__",
    status: str = "incomplete",
) -> dict:
    return {
        "uuid": uuid,
        "type": "to-do",
        "title": title,
        "status": status,
        "created": "2026-01-01 00:00:00",
    }


# ---------- make_preview ----------


def test_make_preview_basic():
    preview = add_heading.make_preview({"project_id": "PROJ-1", "name": "Design"})
    assert "__DESIGN__" in preview
    assert "PROJ-1" in preview
    assert "position not guaranteed" in preview


def test_make_preview_with_after_todo_id():
    preview = add_heading.make_preview({
        "project_id": "PROJ-1",
        "name": "Design",
        "after_todo_id": "TODO-1",
    })
    assert "position not guaranteed" in preview
    assert "TODO-1" in preview


# ---------- execute ----------


async def test_execute_project_not_found(fast_polling, monkeypatch):
    monkeypatch.setattr(things_repo, "project", lambda pid: None)
    with pytest.raises(ValueError, match="not found"):
        await add_heading.execute({"project_id": "GHOST", "name": "Design"})


async def test_execute_invalid_name(fast_polling, monkeypatch):
    monkeypatch.setattr(things_repo, "project", lambda pid: _project_row())
    # Empty name after strip cannot become a valid dummy title.
    with pytest.raises(ValueError):
        await add_heading.execute({"project_id": "PROJ-1", "name": "   "})


async def test_execute_name_with_invalid_chars(fast_polling, monkeypatch):
    monkeypatch.setattr(things_repo, "project", lambda pid: _project_row())
    # Name with characters outside [A-Z0-9 _\-:] after uppercasing.
    with pytest.raises(ValueError):
        await add_heading.execute({"project_id": "PROJ-1", "name": "Hello!"})


async def test_execute_success(fast_polling, captured_launches, monkeypatch):
    monkeypatch.setattr(things_repo, "project", lambda pid: _project_row())
    monkeypatch.setattr(
        things_repo,
        "find_recent_by_title",
        lambda title, created_after: _heading_row(title=title),
    )

    result = await add_heading.execute({"project_id": "PROJ-1", "name": "Design"})

    assert result["action_kind"] == "add_heading"
    assert "undo_id" in result
    assert result["id"] == "HDG-1"
    assert result["title"] == "__DESIGN__"
    assert result["project_id"] == "PROJ-1"

    # Verify undo_log was recorded and patched with UUID.
    entry = undo_log.get(result["undo_id"])
    assert entry is not None
    assert entry["target_uuid"] == "HDG-1"
    assert entry["action_kind"] == "add_heading"

    # Verify URL launched.
    assert len(captured_launches) == 1
    assert "things:///add" in captured_launches[0]
    assert "__DESIGN__" in captured_launches[0]
    assert "PROJ-1" in captured_launches[0]


async def test_execute_success_after_todo_id_acknowledged(
    fast_polling, captured_launches, monkeypatch
):
    monkeypatch.setattr(things_repo, "project", lambda pid: _project_row())
    monkeypatch.setattr(
        things_repo,
        "find_recent_by_title",
        lambda title, created_after: _heading_row(title=title),
    )

    result = await add_heading.execute({
        "project_id": "PROJ-1",
        "name": "Design",
        "after_todo_id": "TODO-99",
    })
    assert "after_todo_id_note" in result
    assert "TODO-99" in result["after_todo_id_note"]


async def test_undo_soft_deletes(with_auth, fast_polling, captured_launches, monkeypatch):
    entry_id = undo_log.record(
        action_kind="add_heading",
        target_uuid="HDG-1",
        before_state=None,
        after_state=_heading_row(),
    )

    state = {"status": "incomplete"}
    monkeypatch.setattr(
        things_repo, "get",
        lambda uuid: {**_heading_row(), "status": state["status"]},
    )

    real_launch = url_scheme.launch

    async def advancing(url: str) -> None:
        state["status"] = "canceled"
        captured_launches.append(url)

    monkeypatch.setattr(url_scheme, "launch", advancing)

    result = await add_heading.undo(undo_log.get(entry_id))
    assert result["undone"] is True
    assert result["target_uuid"] == "HDG-1"

    # Undo log entry deleted.
    assert undo_log.get(entry_id) is None

    # URL contained canceled=true / completed=true.
    url = captured_launches[0]
    assert "canceled=true" in url
    assert "completed=true" in url


async def test_undo_requires_auth(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await add_heading.undo({"id": "e1", "action_kind": "add_heading", "target_uuid": "HDG-1"})
