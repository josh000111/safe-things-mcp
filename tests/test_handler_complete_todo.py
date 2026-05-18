"""Unit tests for the ``complete_todo`` handler.

Same V2 acceptance gate as ``add_todo``:

* inverse URL-scheme call exists (``update?completed=false``),
* undo_log row written *before* the mutation,
* round-trip undo restores incomplete status.

URL launcher and ``things_repo.get`` are mocked; no Things app required.
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import things_repo, url_scheme
from things_mcp.services.handlers import complete_todo
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
        await complete_todo.execute({"todo_id": "abc"})


async def test_execute_raises_on_missing_todo(with_auth, monkeypatch):
    monkeypatch.setattr(things_repo, "get", lambda uuid: None)
    with pytest.raises(ValueError, match="No to-do found"):
        await complete_todo.execute({"todo_id": "ghost"})


async def test_execute_writes_undo_log_before_mutation(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    """Order matters: the undo_log row must be present *before* launch."""
    before = {"uuid": "abc", "title": "t", "status": "incomplete"}
    after = {"uuid": "abc", "title": "t", "status": "completed"}
    monkeypatch.setattr(things_repo, "get", lambda uuid: before if uuid == "abc" else None)

    pre_launch_undo_rows: list[dict] = []
    real_launch = url_scheme.launch

    async def snapshotting_launch(url: str) -> None:
        pre_launch_undo_rows.extend(undo_log.recent(limit=10))
        # Flip the world to "completed" so post-launch polling resolves.
        monkeypatch.setattr(
            things_repo, "get",
            lambda uuid: after if uuid == "abc" else None,
        )
        await real_launch(url)

    monkeypatch.setattr(url_scheme, "launch", snapshotting_launch)

    await complete_todo.execute({"todo_id": "abc"})

    assert len(pre_launch_undo_rows) == 1
    summary = pre_launch_undo_rows[0]
    assert summary["action_kind"] == "complete_todo"
    assert summary["target_uuid"] == "abc"
    # before_state lives on the full row (recent() returns a summary view).
    full = undo_log.get(summary["id"])
    assert full["before_state"]["status"] == "incomplete"


async def test_execute_builds_correct_url(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    monkeypatch.setattr(
        things_repo, "get",
        lambda uuid: {"uuid": uuid, "title": "t", "status": "completed"},
    )
    # Note: the above mock returns "completed" immediately, even pre-launch.
    # That's fine — the handler only requires status=="completed" to resolve
    # polling, regardless of when the flip happens.

    await complete_todo.execute({"todo_id": "abc"})

    assert len(captured_launches) == 1
    url = captured_launches[0]
    assert url.startswith("things:///update?")
    assert "id=abc" in url
    assert "auth-token=tok-xyz" in url
    assert "completed=true" in url


async def test_execute_returns_result_with_undo_id(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    monkeypatch.setattr(
        things_repo, "get",
        lambda uuid: {"uuid": uuid, "title": "Buy milk", "status": "completed"},
    )

    result = await complete_todo.execute({"todo_id": "abc"})
    assert result["id"] == "abc"
    assert result["action_kind"] == "complete_todo"
    assert result["status"] == "completed"
    assert "undo_id" in result

    entry = undo_log.get(result["undo_id"])
    assert entry["target_uuid"] == "abc"
    assert entry["after_state"]["status"] == "completed"


async def test_execute_times_out_when_status_does_not_change(
    with_auth, captured_launches, monkeypatch
):
    monkeypatch.setattr(config, "WRITE_POLL_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(config, "WRITE_POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(
        things_repo, "get",
        lambda uuid: {"uuid": uuid, "status": "incomplete"},
    )

    with pytest.raises(RuntimeError, match="Timed out"):
        await complete_todo.execute({"todo_id": "abc"})

    # Forensic breadcrumb persists.
    rows = undo_log.recent(limit=5)
    assert len(rows) == 1
    assert rows[0]["target_uuid"] == "abc"


# ---------- undo ----------


async def test_undo_requires_auth_token(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await complete_todo.undo({
            "id": "e1", "action_kind": "complete_todo", "target_uuid": "abc"
        })


async def test_undo_requires_target_uuid(with_auth):
    with pytest.raises(RuntimeError, match="no target_uuid"):
        await complete_todo.undo({
            "id": "e1", "action_kind": "complete_todo", "target_uuid": None
        })


async def test_undo_round_trip_restores_incomplete(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    entry_id = undo_log.record(
        action_kind="complete_todo",
        target_uuid="abc",
        before_state={"uuid": "abc", "status": "incomplete"},
        after_state={"uuid": "abc", "status": "completed"},
    )

    monkeypatch.setattr(
        things_repo, "get",
        lambda uuid: {"uuid": uuid, "status": "incomplete"} if uuid == "abc" else None,
    )

    result = await complete_todo.undo(undo_log.get(entry_id))
    assert result["undone"] is True
    assert result["target_uuid"] == "abc"
    assert result["status"] == "incomplete"

    assert len(captured_launches) == 1
    url = captured_launches[0]
    assert url.startswith("things:///update?")
    assert "completed=false" in url
    assert "auth-token=tok-xyz" in url
    assert "id=abc" in url

    assert undo_log.get(entry_id) is None  # log row consumed


# ---------- preview ----------


def test_make_preview_returns_one_liner():
    s = complete_todo.make_preview({"todo_id": "abc-123"})
    assert "abc-123" in s
    assert "completed" in s.lower()
