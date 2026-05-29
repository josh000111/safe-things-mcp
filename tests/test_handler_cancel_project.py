"""Unit tests for the ``cancel_project`` handler.

V2 acceptance gate:
* inverse URL-scheme call exists (``update-project?canceled=false``),
* undo_log row written *before* the mutation,
* round-trip undo restores incomplete status.

URL launcher and ``things_repo.get_project_row`` are mocked; no Things app required.
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import things_repo
from things_mcp.services import url_scheme
from things_mcp.services.handlers import cancel_project
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
        await cancel_project.execute({"project_id": "proj-abc"})


async def test_execute_raises_on_missing_project(with_auth, monkeypatch):
    monkeypatch.setattr(things_repo, "get_project_row", lambda uuid: None)
    with pytest.raises(ValueError, match="No project found"):
        await cancel_project.execute({"project_id": "ghost"})


async def test_execute_raises_when_already_canceled(with_auth, monkeypatch):
    monkeypatch.setattr(
        things_repo, "get_project_row",
        lambda uuid: {"uuid": uuid, "title": "p", "status": "canceled"},
    )
    with pytest.raises(ValueError, match="already canceled"):
        await cancel_project.execute({"project_id": "proj-abc"})


async def test_execute_writes_undo_log_before_mutation(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    """Order matters: the undo_log row must be present *before* launch."""
    before = {"uuid": "proj-abc", "title": "My Project", "status": "incomplete"}
    after = {"uuid": "proj-abc", "title": "My Project", "status": "canceled"}
    monkeypatch.setattr(
        things_repo, "get_project_row",
        lambda uuid: before if uuid == "proj-abc" else None,
    )

    pre_launch_undo_rows: list[dict] = []
    real_launch = url_scheme.launch

    async def snapshotting_launch(url: str) -> None:
        pre_launch_undo_rows.extend(undo_log.recent(limit=10))
        monkeypatch.setattr(
            things_repo, "get_project_row",
            lambda uuid: after if uuid == "proj-abc" else None,
        )
        await real_launch(url)

    monkeypatch.setattr(url_scheme, "launch", snapshotting_launch)

    await cancel_project.execute({"project_id": "proj-abc"})

    assert len(pre_launch_undo_rows) == 1
    summary = pre_launch_undo_rows[0]
    assert summary["action_kind"] == "cancel_project"
    assert summary["target_uuid"] == "proj-abc"
    full = undo_log.get(summary["id"])
    assert full["before_state"]["status"] == "incomplete"


async def test_execute_builds_correct_url(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    """Mock starts as incomplete, flips to canceled after launch."""
    before = {"uuid": "proj-abc", "title": "p", "status": "incomplete"}
    after = {"uuid": "proj-abc", "title": "p", "status": "canceled"}
    monkeypatch.setattr(things_repo, "get_project_row", lambda uuid: before)
    real_launch = url_scheme.launch

    async def flipping_launch(url: str) -> None:
        monkeypatch.setattr(things_repo, "get_project_row", lambda uuid: after)
        await real_launch(url)

    monkeypatch.setattr(url_scheme, "launch", flipping_launch)

    await cancel_project.execute({"project_id": "proj-abc"})

    assert len(captured_launches) == 1
    url = captured_launches[0]
    assert url.startswith("things:///update-project?")
    assert "id=proj-abc" in url
    assert "auth-token=tok-xyz" in url
    assert "canceled=true" in url


async def test_execute_returns_result_with_undo_id(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    """Mock starts as incomplete, flips to canceled after launch."""
    before = {"uuid": "proj-abc", "title": "Big Project", "status": "incomplete"}
    after = {"uuid": "proj-abc", "title": "Big Project", "status": "canceled"}
    monkeypatch.setattr(things_repo, "get_project_row", lambda uuid: before)
    real_launch = url_scheme.launch

    async def flipping_launch(url: str) -> None:
        monkeypatch.setattr(things_repo, "get_project_row", lambda uuid: after)
        await real_launch(url)

    monkeypatch.setattr(url_scheme, "launch", flipping_launch)

    result = await cancel_project.execute({"project_id": "proj-abc"})
    assert result["id"] == "proj-abc"
    assert result["action_kind"] == "cancel_project"
    assert result["status"] == "canceled"
    assert "undo_id" in result

    entry = undo_log.get(result["undo_id"])
    assert entry["target_uuid"] == "proj-abc"
    assert entry["after_state"]["status"] == "canceled"


# ---------- undo ----------


async def test_undo_requires_auth_token(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await cancel_project.undo({
            "id": "e1", "action_kind": "cancel_project", "target_uuid": "proj-abc"
        })


async def test_undo_requires_target_uuid(with_auth):
    with pytest.raises(RuntimeError, match="no target_uuid"):
        await cancel_project.undo({
            "id": "e1", "action_kind": "cancel_project", "target_uuid": None
        })


async def test_undo_round_trip_restores_incomplete(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    entry_id = undo_log.record(
        action_kind="cancel_project",
        target_uuid="proj-abc",
        before_state={"uuid": "proj-abc", "status": "incomplete"},
        after_state={"uuid": "proj-abc", "status": "canceled"},
    )

    monkeypatch.setattr(
        things_repo, "get_project_row",
        lambda uuid: {"uuid": uuid, "status": "incomplete"} if uuid == "proj-abc" else None,
    )

    result = await cancel_project.undo(undo_log.get(entry_id))
    assert result["undone"] is True
    assert result["target_uuid"] == "proj-abc"
    assert result["status"] == "incomplete"

    assert len(captured_launches) == 1
    url = captured_launches[0]
    assert url.startswith("things:///update-project?")
    assert "canceled=false" in url
    assert "auth-token=tok-xyz" in url
    assert "id=proj-abc" in url

    assert undo_log.get(entry_id) is None  # log row consumed


# ---------- preview ----------


def test_make_preview_returns_one_liner():
    s = cancel_project.make_preview({"project_id": "proj-123"})
    assert "proj-123" in s
    assert "cancel" in s.lower()
