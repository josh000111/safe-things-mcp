"""Unit tests for the ``delete_heading`` handler.

* make_preview mentions "dummy heading"
* execute raises when not found
* execute raises when not a dummy heading (native heading)
* execute raises when already deleted
* execute success: cancels heading, records undo_log
* undo restores canceled=false, completed=false
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import things_repo, url_scheme
from things_mcp.services.handlers import delete_heading
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
    }


def _project_row(items: list | None = None) -> dict:
    return {
        "uuid": "PROJ-1",
        "type": "project",
        "title": "My Project",
        "items": items or [],
    }


# ---------- make_preview ----------


def test_make_preview():
    preview = delete_heading.make_preview({
        "project_id": "PROJ-1",
        "heading_id_or_name": "HDG-1",
    })
    assert "dummy heading" in preview
    assert "Logbook" in preview
    assert "undo" in preview.lower()


# ---------- execute ----------


async def test_execute_not_found(with_auth, fast_polling, monkeypatch):
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: None)
    monkeypatch.setattr(things_repo, "project", lambda pid: _project_row(items=[]))
    with pytest.raises(ValueError):
        await delete_heading.execute({
            "project_id": "PROJ-1",
            "heading_id_or_name": "GHOST",
        })


async def test_execute_not_a_dummy(with_auth, fast_polling, monkeypatch):
    # get_todo returns a regular task (not a dummy heading).
    monkeypatch.setattr(
        things_repo, "get_todo",
        lambda uuid: {"uuid": uuid, "type": "to-do", "title": "Regular task", "status": "incomplete"},
    )
    with pytest.raises(ValueError, match="not a dummy heading"):
        await delete_heading.execute({
            "project_id": "PROJ-1",
            "heading_id_or_name": "REGULAR-1",
        })


async def test_execute_native_heading_via_name_scan(with_auth, fast_polling, monkeypatch):
    # Scanning by name finds only a native heading — should raise actionable error.
    items = [{"uuid": "NATIVE-1", "type": "heading", "title": "Design"}]
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: None)
    monkeypatch.setattr(things_repo, "project", lambda pid: _project_row(items=items))
    with pytest.raises(ValueError, match="native heading"):
        await delete_heading.execute({
            "project_id": "PROJ-1",
            "heading_id_or_name": "Design",
        })


async def test_execute_already_deleted(with_auth, fast_polling, monkeypatch):
    monkeypatch.setattr(
        things_repo, "get_todo",
        lambda uuid: _heading_row(status="canceled"),
    )
    with pytest.raises(ValueError, match="already"):
        await delete_heading.execute({
            "project_id": "PROJ-1",
            "heading_id_or_name": "HDG-1",
        })


async def test_execute_success(with_auth, fast_polling, captured_launches, monkeypatch):
    state = {"status": "incomplete"}

    monkeypatch.setattr(
        things_repo, "get_todo",
        lambda uuid: _heading_row(status=state["status"]),
    )
    monkeypatch.setattr(
        things_repo, "get",
        lambda uuid: _heading_row(status=state["status"]),
    )

    real_launch = url_scheme.launch

    async def advancing(url: str) -> None:
        state["status"] = "canceled"
        captured_launches.append(url)

    monkeypatch.setattr(url_scheme, "launch", advancing)

    result = await delete_heading.execute({
        "project_id": "PROJ-1",
        "heading_id_or_name": "HDG-1",
    })

    assert result["action_kind"] == "delete_heading"
    assert "undo_id" in result
    assert result["id"] == "HDG-1"
    assert result["status"] == "canceled"
    assert "Soft-deleted" in result["note"]

    # Verify URL launched with canceled=true completed=true.
    url = captured_launches[0]
    assert "canceled=true" in url
    assert "completed=true" in url

    # undo_log entry exists and is patched.
    entry = undo_log.get(result["undo_id"])
    assert entry is not None
    assert entry["target_uuid"] == "HDG-1"


async def test_undo_restores_task(with_auth, fast_polling, captured_launches, monkeypatch):
    entry_id = undo_log.record(
        action_kind="delete_heading",
        target_uuid="HDG-1",
        before_state={"full": _heading_row(), "status": "incomplete", "title": "__DESIGN__"},
        after_state={"status": "canceled"},
    )

    state = {"status": "canceled"}
    monkeypatch.setattr(
        things_repo, "get",
        lambda uuid: _heading_row(status=state["status"]) if uuid == "HDG-1" else None,
    )

    async def advancing(url: str) -> None:
        state["status"] = "incomplete"
        captured_launches.append(url)

    monkeypatch.setattr(url_scheme, "launch", advancing)

    result = await delete_heading.undo(undo_log.get(entry_id))
    assert result["undone"] is True
    assert result["target_uuid"] == "HDG-1"
    assert result["status"] == "incomplete"

    # undo_log entry deleted.
    assert undo_log.get(entry_id) is None

    # URL contained canceled=false / completed=false.
    url = captured_launches[0]
    assert "canceled=false" in url
    assert "completed=false" in url


async def test_undo_requires_auth(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await delete_heading.undo({
            "id": "e1",
            "action_kind": "delete_heading",
            "target_uuid": "HDG-1",
        })
