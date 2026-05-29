"""Unit tests for the ``cancel_todo`` handler.

V2 acceptance gate:
* inverse URL-scheme call exists (``update?canceled=false``),
* undo_log row written *before* the mutation,
* round-trip undo restores incomplete status.

URL launcher and ``things_repo.get`` are mocked; no Things app required.
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import things_repo
from things_mcp.services import url_scheme
from things_mcp.services.handlers import cancel_todo
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


# ---------- execute ----------


async def test_execute_requires_auth_token(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await cancel_todo.execute({"todo_id": "abc"})


async def test_execute_raises_on_missing_todo(with_auth, monkeypatch):
    monkeypatch.setattr(things_repo, "get", lambda uuid: None)
    with pytest.raises(ValueError, match="No to-do found"):
        await cancel_todo.execute({"todo_id": "ghost"})


async def test_execute_raises_when_already_canceled(with_auth, monkeypatch):
    monkeypatch.setattr(
        things_repo, "get",
        lambda uuid: {"uuid": uuid, "title": "t", "status": "canceled"},
    )
    with pytest.raises(ValueError, match="already canceled"):
        await cancel_todo.execute({"todo_id": "abc"})


async def test_execute_writes_undo_log_before_mutation(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    """Order matters: the undo_log row must be present *before* launch."""
    before = {"uuid": "abc", "title": "t", "status": "incomplete"}
    after = {"uuid": "abc", "title": "t", "status": "canceled"}
    monkeypatch.setattr(things_repo, "get", lambda uuid: before if uuid == "abc" else None)

    pre_launch_undo_rows: list[dict] = []
    real_launch = url_scheme.launch

    async def snapshotting_launch(url: str) -> None:
        pre_launch_undo_rows.extend(undo_log.recent(limit=10))
        monkeypatch.setattr(
            things_repo, "get",
            lambda uuid: after if uuid == "abc" else None,
        )
        await real_launch(url)

    monkeypatch.setattr(url_scheme, "launch", snapshotting_launch)

    await cancel_todo.execute({"todo_id": "abc"})

    assert len(pre_launch_undo_rows) == 1
    summary = pre_launch_undo_rows[0]
    assert summary["action_kind"] == "cancel_todo"
    assert summary["target_uuid"] == "abc"
    full = undo_log.get(summary["id"])
    assert full["before_state"]["status"] == "incomplete"


async def test_execute_builds_correct_url(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    """Mock starts as incomplete, flips to canceled after launch."""
    before = {"uuid": "abc", "title": "t", "status": "incomplete"}
    after = {"uuid": "abc", "title": "t", "status": "canceled"}
    monkeypatch.setattr(things_repo, "get", lambda uuid: before)
    real_launch = url_scheme.launch

    async def flipping_launch(url: str) -> None:
        monkeypatch.setattr(things_repo, "get", lambda uuid: after)
        await real_launch(url)

    monkeypatch.setattr(url_scheme, "launch", flipping_launch)

    await cancel_todo.execute({"todo_id": "abc"})

    assert len(captured_launches) == 1
    url = captured_launches[0]
    assert url.startswith("things:///update?")
    assert "id=abc" in url
    assert "auth-token=tok-xyz" in url
    assert "canceled=true" in url


async def test_execute_returns_result_with_undo_id(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    """Mock starts as incomplete, flips to canceled after launch."""
    before = {"uuid": "abc", "title": "Buy milk", "status": "incomplete"}
    after = {"uuid": "abc", "title": "Buy milk", "status": "canceled"}
    monkeypatch.setattr(things_repo, "get", lambda uuid: before)
    real_launch = url_scheme.launch

    async def flipping_launch(url: str) -> None:
        monkeypatch.setattr(things_repo, "get", lambda uuid: after)
        await real_launch(url)

    monkeypatch.setattr(url_scheme, "launch", flipping_launch)

    result = await cancel_todo.execute({"todo_id": "abc"})
    assert result["id"] == "abc"
    assert result["action_kind"] == "cancel_todo"
    assert result["status"] == "canceled"
    assert "undo_id" in result

    entry = undo_log.get(result["undo_id"])
    assert entry["target_uuid"] == "abc"
    assert entry["after_state"]["status"] == "canceled"


# ---------- undo ----------


async def test_undo_requires_auth_token(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await cancel_todo.undo({
            "id": "e1", "action_kind": "cancel_todo", "target_uuid": "abc"
        })


async def test_undo_requires_target_uuid(with_auth):
    with pytest.raises(RuntimeError, match="no target_uuid"):
        await cancel_todo.undo({
            "id": "e1", "action_kind": "cancel_todo", "target_uuid": None
        })


async def test_undo_round_trip_restores_incomplete(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    entry_id = undo_log.record(
        action_kind="cancel_todo",
        target_uuid="abc",
        before_state={"uuid": "abc", "status": "incomplete"},
        after_state={"uuid": "abc", "status": "canceled"},
    )

    monkeypatch.setattr(
        things_repo, "get",
        lambda uuid: {"uuid": uuid, "status": "incomplete"} if uuid == "abc" else None,
    )

    result = await cancel_todo.undo(undo_log.get(entry_id))
    assert result["undone"] is True
    assert result["target_uuid"] == "abc"
    assert result["status"] == "incomplete"

    assert len(captured_launches) == 1
    url = captured_launches[0]
    assert url.startswith("things:///update?")
    assert "canceled=false" in url
    assert "auth-token=tok-xyz" in url
    assert "id=abc" in url

    assert undo_log.get(entry_id) is None  # log row consumed


# ---------- preview ----------


def test_make_preview_returns_one_liner():
    s = cancel_todo.make_preview({"todo_id": "abc-123"})
    assert "abc-123" in s
    assert "cancel" in s.lower()
