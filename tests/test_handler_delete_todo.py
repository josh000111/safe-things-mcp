"""Unit tests for the ``delete_todo`` handler (soft-delete).

* execute marks canceled+completed → moves to Logbook
* requires auth and a real, non-canceled target
* undo flips both flags back → returns to incomplete
* writes undo_log row before mutation (V2 acceptance gate)
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import things_repo, url_scheme
from things_mcp.services.handlers import delete_todo
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


def _row(uuid: str = "abc", status: str = "incomplete", title: str = "t") -> dict:
    return {
        "uuid": uuid,
        "type": "to-do",
        "title": title,
        "status": status,
        "start": "Inbox",
    }


# ---------- execute ----------


async def test_requires_auth(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await delete_todo.execute({"todo_id": "abc"})


async def test_raises_when_todo_missing(with_auth, monkeypatch):
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: None)
    with pytest.raises(ValueError, match="No to-do found"):
        await delete_todo.execute({"todo_id": "ghost"})


async def test_raises_on_already_canceled(with_auth, monkeypatch):
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: _row(status="canceled"))
    with pytest.raises(ValueError, match="already status"):
        await delete_todo.execute({"todo_id": "abc"})


async def test_raises_on_already_completed(with_auth, monkeypatch):
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: _row(status="completed"))
    with pytest.raises(ValueError, match="already status"):
        await delete_todo.execute({"todo_id": "abc"})


async def test_writes_undo_log_before_launch(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    pre_launch_rows: list[dict] = []
    state = {"status": "incomplete"}

    monkeypatch.setattr(
        things_repo, "get_todo",
        lambda uuid: _row(status=state["status"]) if uuid == "abc" else None,
    )
    monkeypatch.setattr(
        things_repo, "get",
        lambda uuid: _row(status=state["status"]) if uuid == "abc" else None,
    )

    real_launch = url_scheme.launch

    async def snapshotting(url: str) -> None:
        pre_launch_rows.extend(undo_log.recent(limit=10))
        state["status"] = "canceled"
        await real_launch(url)

    monkeypatch.setattr(url_scheme, "launch", snapshotting)

    await delete_todo.execute({"todo_id": "abc"})

    assert len(pre_launch_rows) == 1
    assert pre_launch_rows[0]["action_kind"] == "delete_todo"
    assert pre_launch_rows[0]["target_uuid"] == "abc"


async def test_execute_builds_correct_url(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    state = {"status": "incomplete"}

    monkeypatch.setattr(
        things_repo, "get_todo",
        lambda uuid: _row(status=state["status"]),
    )
    monkeypatch.setattr(
        things_repo, "get",
        lambda uuid: _row(status=state["status"]),
    )

    real_launch = url_scheme.launch

    async def advancing(url: str) -> None:
        state["status"] = "canceled"
        await real_launch(url)

    monkeypatch.setattr(url_scheme, "launch", advancing)

    await delete_todo.execute({"todo_id": "abc"})

    url = captured_launches[0]
    assert url.startswith("things:///update?")
    assert "id=abc" in url
    assert "auth-token=tok-xyz" in url
    assert "canceled=true" in url
    assert "completed=true" in url


async def test_execute_returns_undo_id_and_note(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    state = {"status": "incomplete"}
    monkeypatch.setattr(
        things_repo, "get_todo",
        lambda uuid: _row(status=state["status"]),
    )
    monkeypatch.setattr(
        things_repo, "get",
        lambda uuid: _row(status=state["status"]),
    )

    real_launch = url_scheme.launch

    async def advancing(url: str) -> None:
        state["status"] = "canceled"
        await real_launch(url)

    monkeypatch.setattr(url_scheme, "launch", advancing)

    result = await delete_todo.execute({"todo_id": "abc"})
    assert result["action_kind"] == "delete_todo"
    assert result["id"] == "abc"
    assert "undo_id" in result
    assert "Soft-deleted" in result["note"]


# ---------- undo ----------


async def test_undo_requires_auth(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await delete_todo.undo({
            "id": "e1", "action_kind": "delete_todo", "target_uuid": "abc"
        })


async def test_undo_round_trip_restores_incomplete(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    entry_id = undo_log.record(
        action_kind="delete_todo",
        target_uuid="abc",
        before_state={"full": _row(), "status": "incomplete"},
        after_state={"status": "canceled"},
    )

    monkeypatch.setattr(
        things_repo, "get",
        lambda uuid: _row(status="incomplete") if uuid == "abc" else None,
    )

    result = await delete_todo.undo(undo_log.get(entry_id))
    assert result["undone"] is True
    assert result["target_uuid"] == "abc"
    assert result["status"] == "incomplete"

    url = captured_launches[0]
    assert "canceled=false" in url
    assert "completed=false" in url

    assert undo_log.get(entry_id) is None


# ---------- preview ----------


def test_make_preview_mentions_logbook_and_undo():
    s = delete_todo.make_preview({"todo_id": "abc"})
    assert "abc" in s
    assert "Logbook" in s
    assert "undo" in s.lower()
