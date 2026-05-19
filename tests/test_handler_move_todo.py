"""Unit tests for the ``move_todo`` handler.

Two-dimensional move semantics:

* scheduling moves (today/anytime/someday → ``when=``) preserve project
* project moves (UUID → ``list-id=``) preserve scheduling
* the undo restores only the dimension that was changed

URL launcher and ``things_repo`` are mocked.
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import things_repo, url_scheme
from things_mcp.services.handlers import move_todo
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
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", "tok-xyz")


def _row(
    uuid: str = "abc",
    title: str = "task",
    start: str = "Inbox",
    start_date: str | None = None,
    project: str | None = None,
    modified: str = "2026-05-19 10:00:00",
) -> dict:
    row = {
        "uuid": uuid,
        "type": "to-do",
        "title": title,
        "status": "incomplete",
        "start": start,
        "start_date": start_date,
        "modified": modified,
    }
    if project:
        row["project"] = project
    return row


# ---------- input validation ----------


async def test_rejects_inbox_with_hint(with_auth, monkeypatch):
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: _row())
    with pytest.raises(ValueError, match="not supported"):
        await move_todo.execute({"todo_id": "abc", "target": "inbox"})


async def test_rejects_upcoming(with_auth, monkeypatch):
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: _row())
    with pytest.raises(ValueError, match="not supported"):
        await move_todo.execute({"todo_id": "abc", "target": "upcoming"})


async def test_requires_auth(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await move_todo.execute({"todo_id": "abc", "target": "today"})


async def test_raises_when_todo_missing(with_auth, monkeypatch):
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: None)
    with pytest.raises(ValueError, match="No to-do found"):
        await move_todo.execute({"todo_id": "ghost", "target": "today"})


# ---------- scheduling move ----------


async def test_scheduling_move_emits_when_param(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    state = {"row": _row(start="Inbox")}

    real_launch = url_scheme.launch

    async def advancing(url: str) -> None:
        state["row"] = {**state["row"], "start": "Today",
                        "modified": "2026-05-19 11:00:00"}
        await real_launch(url)

    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: state["row"])
    monkeypatch.setattr(url_scheme, "launch", advancing)

    result = await move_todo.execute({"todo_id": "abc", "target": "today"})
    assert result["dimension"] == "schedule"

    url = captured_launches[0]
    assert "when=today" in url
    assert "list-id" not in url


async def test_scheduling_move_inverse_is_original_when(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    """Task was in Anytime → move to today → undo restores Anytime."""
    state = {"row": _row(start="Anytime")}

    real_launch = url_scheme.launch

    async def advancing(url: str) -> None:
        state["row"] = {**state["row"], "start": "Today",
                        "modified": "2026-05-19 11:00:00"}
        await real_launch(url)

    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: state["row"])
    monkeypatch.setattr(url_scheme, "launch", advancing)

    result = await move_todo.execute({"todo_id": "abc", "target": "today"})
    entry = undo_log.get(result["undo_id"])
    assert entry["before_state"]["inverse_params"] == {"when": "anytime"}


async def test_scheduling_move_inverse_preserves_start_date(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    """Task had a specific Upcoming date → inverse uses that date."""
    state = {"row": _row(start="Upcoming", start_date="2026-12-25")}

    real_launch = url_scheme.launch

    async def advancing(url: str) -> None:
        state["row"] = {**state["row"], "start": "Today",
                        "modified": "2026-05-19 11:00:00"}
        await real_launch(url)

    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: state["row"])
    monkeypatch.setattr(url_scheme, "launch", advancing)

    result = await move_todo.execute({"todo_id": "abc", "target": "today"})
    entry = undo_log.get(result["undo_id"])
    assert entry["before_state"]["inverse_params"] == {"when": "2026-12-25"}


# ---------- project move ----------


async def test_project_move_emits_list_id(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    state = {"row": _row(project=None)}

    real_launch = url_scheme.launch

    async def advancing(url: str) -> None:
        state["row"] = {**state["row"], "project": "PROJ-NEW",
                        "modified": "2026-05-19 11:00:00"}
        await real_launch(url)

    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: state["row"])
    monkeypatch.setattr(url_scheme, "launch", advancing)

    proj_uuid = "Vr3ovatWZjNUitmkqTX76p"
    result = await move_todo.execute({"todo_id": "abc", "target": proj_uuid})
    assert result["dimension"] == "project"

    url = captured_launches[0]
    assert f"list-id={proj_uuid}" in url
    assert "when=" not in url


async def test_project_move_inverse_to_original_project(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    state = {"row": _row(project="PROJ-ORIG")}

    real_launch = url_scheme.launch

    async def advancing(url: str) -> None:
        state["row"] = {**state["row"], "project": "PROJ-NEW",
                        "modified": "2026-05-19 11:00:00"}
        await real_launch(url)

    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: state["row"])
    monkeypatch.setattr(url_scheme, "launch", advancing)

    result = await move_todo.execute({"todo_id": "abc", "target": "PROJ-NEW"})
    entry = undo_log.get(result["undo_id"])
    assert entry["before_state"]["inverse_params"] == {"list_id": "PROJ-ORIG"}


async def test_project_move_inverse_clears_when_no_original(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    """Task wasn't in a project before → inverse clears list-id."""
    state = {"row": _row(project=None)}

    real_launch = url_scheme.launch

    async def advancing(url: str) -> None:
        state["row"] = {**state["row"], "project": "PROJ-NEW",
                        "modified": "2026-05-19 11:00:00"}
        await real_launch(url)

    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: state["row"])
    monkeypatch.setattr(url_scheme, "launch", advancing)

    result = await move_todo.execute({"todo_id": "abc", "target": "PROJ-NEW"})
    entry = undo_log.get(result["undo_id"])
    assert entry["before_state"]["inverse_params"] == {"list_id": ""}


# ---------- undo ----------


async def test_undo_round_trip_scheduling(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    state = {"row": _row(start="Today",
                          modified="2026-05-19 11:00:00")}

    real_launch = url_scheme.launch

    async def advancing(url: str) -> None:
        state["row"] = {**state["row"], "start": "Anytime",
                        "modified": "2026-05-19 12:00:00"}
        await real_launch(url)

    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: state["row"])
    monkeypatch.setattr(url_scheme, "launch", advancing)

    entry_id = undo_log.record(
        action_kind="move_todo",
        target_uuid="abc",
        before_state={
            "full": _row(start="Anytime"),
            "inverse_params": {"when": "anytime"},
            "dimension": "schedule",
            "target": "today",
        },
        after_state=None,
    )

    result = await move_todo.undo(undo_log.get(entry_id))
    assert result["undone"] is True
    assert result["restored_dimension"] == "schedule"

    url = captured_launches[0]
    assert "when=anytime" in url
    assert undo_log.get(entry_id) is None


async def test_undo_round_trip_project(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    state = {"row": _row(project="PROJ-NEW",
                          modified="2026-05-19 11:00:00")}

    real_launch = url_scheme.launch

    async def advancing(url: str) -> None:
        state["row"] = {**state["row"], "project": "PROJ-ORIG",
                        "modified": "2026-05-19 12:00:00"}
        await real_launch(url)

    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: state["row"])
    monkeypatch.setattr(url_scheme, "launch", advancing)

    entry_id = undo_log.record(
        action_kind="move_todo",
        target_uuid="abc",
        before_state={
            "full": _row(project="PROJ-ORIG"),
            "inverse_params": {"list_id": "PROJ-ORIG"},
            "dimension": "project",
            "target": "PROJ-NEW",
        },
        after_state=None,
    )

    result = await move_todo.undo(undo_log.get(entry_id))
    assert result["undone"] is True

    url = captured_launches[0]
    assert "list-id=PROJ-ORIG" in url


# ---------- preview ----------


def test_make_preview():
    s = move_todo.make_preview({"todo_id": "abc", "target": "today"})
    assert "abc" in s
    assert "today" in s
