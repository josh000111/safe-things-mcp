"""Unit tests for the ``add_todo`` handler.

The handler is the unit that owns the V2 acceptance gate — every
mutation must (a) have an inverse URL-scheme call, (b) write an
undo_log row before mutating, and (c) round-trip cleanly via undo.

These tests mock the URL-scheme launcher and the read-only things_repo
so the test runs anywhere, no Things app or real DB needed.
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import things_repo, url_scheme
from things_mcp.services.handlers import add_todo
from things_mcp.state import undo_log


pytestmark = pytest.mark.usefixtures("isolated_state_db")


@pytest.fixture
def fast_polling(monkeypatch):
    monkeypatch.setattr(config, "WRITE_POLL_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(config, "WRITE_POLL_INTERVAL_SECONDS", 0.01)


@pytest.fixture
def captured_launches(monkeypatch):
    """Capture every URL handed to ``url_scheme.launch`` instead of
    actually invoking ``open``."""
    launches: list[str] = []

    async def fake_launch(url: str) -> None:
        launches.append(url)

    monkeypatch.setattr(url_scheme, "launch", fake_launch)
    return launches


def _stub_match(uuid: str = "new-uuid", title: str = "t", status: str = "incomplete") -> dict:
    return {
        "uuid": uuid,
        "type": "to-do",
        "title": title,
        "status": status,
        "start": "Inbox",
        "created": "2026-05-18 03:00:00",
    }


# ---------- execute ----------


async def test_execute_writes_undo_log_before_mutation(
    fast_polling, captured_launches, monkeypatch
):
    """Order matters: the undo_log row must be present *before* launch.

    We assert by snapshotting ``undo_log.recent()`` from inside the fake
    launch, before the mutation has actually happened.
    """
    pre_launch_undo_rows: list[dict] = []
    real_launch = url_scheme.launch  # already the fake, but capture order

    async def snapshotting_launch(url: str) -> None:
        pre_launch_undo_rows.extend(undo_log.recent(limit=10))
        await real_launch(url)

    monkeypatch.setattr(url_scheme, "launch", snapshotting_launch)
    monkeypatch.setattr(
        things_repo, "find_recent_by_title",
        lambda title, created_after: _stub_match(title=title),
    )

    await add_todo.execute({"title": "Hello", "list_id": "inbox"})

    # At launch-time we should have seen one undo_log row with target_uuid still NULL.
    assert len(pre_launch_undo_rows) == 1
    assert pre_launch_undo_rows[0]["action_kind"] == "add_todo"
    assert pre_launch_undo_rows[0]["target_uuid"] is None


async def test_execute_returns_id_and_patches_undo_log(
    fast_polling, captured_launches, monkeypatch
):
    monkeypatch.setattr(
        things_repo, "find_recent_by_title",
        lambda title, created_after: _stub_match(uuid="abc", title=title),
    )

    result = await add_todo.execute({"title": "Hello", "list_id": "inbox"})
    assert result["id"] == "abc"
    assert result["action_kind"] == "add_todo"
    assert result["list_id"] == "inbox"

    # Undo log now has the resolved UUID and after_state.
    entry = undo_log.get(result["undo_id"])
    assert entry["target_uuid"] == "abc"
    assert entry["after_state"]["uuid"] == "abc"


async def test_execute_builds_correct_url(
    fast_polling, captured_launches, monkeypatch
):
    monkeypatch.setattr(
        things_repo, "find_recent_by_title",
        lambda title, created_after: _stub_match(title=title),
    )

    await add_todo.execute(
        {"title": "Plan trip", "list_id": "today", "tags": ["urgent"]}
    )
    assert len(captured_launches) == 1
    url = captured_launches[0]
    assert url.startswith("things:///add?")
    assert "when=today" in url  # today routes via when=, not list=
    assert "tags=urgent" in url


async def test_execute_times_out_when_poll_finds_nothing(
    captured_launches, monkeypatch
):
    monkeypatch.setattr(config, "WRITE_POLL_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(config, "WRITE_POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(things_repo, "find_recent_by_title", lambda *a, **kw: None)

    with pytest.raises(RuntimeError, match="Timed out"):
        await add_todo.execute({"title": "Hello", "list_id": "inbox"})

    # The undo_log row is still present (with target_uuid=NULL) — a
    # forensic breadcrumb for investigating the failure.
    leftover = undo_log.recent(limit=5)
    assert len(leftover) == 1
    assert leftover[0]["target_uuid"] is None


# ---------- undo ----------


async def test_undo_requires_auth_token(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    entry = {"id": "e1", "action_kind": "add_todo", "target_uuid": "abc"}
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await add_todo.undo(entry)


async def test_undo_requires_target_uuid(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", "tok")
    entry = {"id": "e1", "action_kind": "add_todo", "target_uuid": None}
    with pytest.raises(RuntimeError, match="no target_uuid"):
        await add_todo.undo(entry)


async def test_undo_round_trip_marks_completed(
    fast_polling, captured_launches, monkeypatch
):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", "tok-xyz")

    # Stage the undo_log row as the handler would have left it post-add.
    entry_id = undo_log.record(
        action_kind="add_todo",
        target_uuid="abc",
        before_state=None,
        after_state={"uuid": "abc", "status": "incomplete"},
    )

    # Things returns "completed" once the URL scheme processes our update.
    monkeypatch.setattr(
        things_repo, "get",
        lambda uuid: {"uuid": uuid, "status": "completed"} if uuid == "abc" else None,
    )

    result = await add_todo.undo(undo_log.get(entry_id))
    assert result["undone"] is True
    assert result["target_uuid"] == "abc"
    assert result["status"] == "completed"

    # URL scheme call shape — must include the auth token and completed=true.
    assert len(captured_launches) == 1
    url = captured_launches[0]
    assert url.startswith("things:///update?")
    assert "auth-token=tok-xyz" in url
    assert "completed=true" in url
    assert "canceled=true" in url
    assert "id=abc" in url

    # Undo-log row gone (action can't be undone twice).
    assert undo_log.get(entry_id) is None


# ---------- preview ----------


def test_make_preview_simple():
    s = add_todo.make_preview({"title": "Buy milk", "list_id": "inbox"})
    assert "Buy milk" in s
    assert "inbox" in s


def test_make_preview_includes_metadata():
    s = add_todo.make_preview({
        "title": "Plan", "list_id": "today", "when": "today",
        "deadline": "2026-06-01", "tags": ["a", "b"], "checklist": ["x", "y"],
    })
    assert "when=today" in s
    assert "deadline=2026-06-01" in s
    assert "tags=a,b" in s
    assert "checklist=[2 items]" in s
