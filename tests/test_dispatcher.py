"""propose → confirm → undo dispatcher tests.

Tests call the module-level tool functions directly (no FastMCP wrapper
in the loop). A ``fake_things`` fixture stands in for the Things app
state, intercepting URL-scheme launches.
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import things_repo, url_scheme
from things_mcp.state import pending, undo_log
from things_mcp.tools.confirm import (
    cancel_action,
    confirm_action,
    list_pending_actions,
)
from things_mcp.tools.propose import propose_add_todo
from things_mcp.tools.undo import undo as undo_tool


pytestmark = pytest.mark.usefixtures("isolated_state_db")


@pytest.fixture
def fast_polling(monkeypatch):
    monkeypatch.setattr(config, "WRITE_POLL_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(config, "WRITE_POLL_INTERVAL_SECONDS", 0.01)


@pytest.fixture
def fake_things(monkeypatch):
    """Fake Things app: tracks created tasks in a dict, mutates on update."""
    state: dict[str, dict] = {}

    async def fake_launch(url: str) -> None:
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(url)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        # urlparse on ``things:///add?...`` gives scheme='things', netloc='',
        # path='/add'. So the path is /add or /update.
        if parsed.path == "/add":
            new_uuid = f"uuid-{len(state) + 1}"
            state[new_uuid] = {
                "uuid": new_uuid,
                "title": params.get("title", ""),
                "status": "incomplete",
                "created": "2026-05-18 03:00:00",
                "start": params.get("list", "Inbox").capitalize(),
            }
        elif parsed.path == "/update":
            uid = params["id"]
            if uid in state:
                if params.get("completed") == "true":
                    state[uid]["status"] = "completed"
                if params.get("canceled") == "true":
                    state[uid]["status"] = "canceled"

    monkeypatch.setattr(url_scheme, "launch", fake_launch)
    monkeypatch.setattr(
        things_repo, "find_recent_by_title",
        lambda title, created_after: next(
            (t for t in state.values() if t["title"] == title), None
        ),
    )
    monkeypatch.setattr(things_repo, "get", lambda uuid: state.get(uuid))
    return state


# ---------- propose ----------


async def test_propose_enqueues_action(fake_things):
    out = await propose_add_todo(title="Hello", list_id="today")
    assert "action_id" in out
    assert "Hello" in out["preview"]
    assert "today" in out["preview"]
    assert "next_step" in out
    assert out["auto_confirmed"] is False

    rows = pending.list_all()
    assert len(rows) == 1
    assert rows[0]["kind"] == "add_todo"


async def test_propose_validates_empty_title(fake_things):
    with pytest.raises(Exception):
        await propose_add_todo(title="", list_id="inbox")


async def test_propose_does_not_touch_things(fake_things):
    """Critical safety property: propose enqueues only — no launch happens."""
    await propose_add_todo(title="Hello", list_id="inbox")
    assert fake_things == {}  # no task created


# ---------- confirm ----------


async def test_confirm_full_flow(fast_polling, fake_things):
    proposed = await propose_add_todo(title="Confirmed task", list_id="inbox")
    action_id = proposed["action_id"]

    confirmed = await confirm_action(action_id)
    assert confirmed["kind"] == "add_todo"
    assert confirmed["result"]["title"] == "Confirmed task"

    new_uuid = confirmed["result"]["id"]
    assert new_uuid in fake_things

    # Pending row gone, undo_log row present with the new uuid.
    assert pending.get(action_id) is None
    entry = undo_log.get(confirmed["result"]["undo_id"])
    assert entry["target_uuid"] == new_uuid


async def test_confirm_missing_action_raises():
    with pytest.raises(ValueError, match="No pending action"):
        await confirm_action("does-not-exist")


async def test_confirm_expired_action_raises(fake_things, monkeypatch):
    monkeypatch.setattr(config, "PENDING_TTL_SECONDS", -1)
    monkeypatch.setattr(pending, "PENDING_TTL_SECONDS", -1)
    proposed = await propose_add_todo(title="Will expire", list_id="inbox")
    # sweep_expired() inside confirm_action will catch it and raise as missing.
    with pytest.raises(ValueError, match="expired|No pending"):
        await confirm_action(proposed["action_id"])


# ---------- cancel ----------


async def test_cancel_removes_pending_row(fake_things):
    proposed = await propose_add_todo(title="to-cancel", list_id="inbox")
    out = cancel_action(proposed["action_id"])
    assert out["cancelled"] is True
    assert pending.get(proposed["action_id"]) is None


def test_cancel_missing_action_raises():
    with pytest.raises(ValueError, match="No pending action"):
        cancel_action("nope")


async def test_cancel_does_not_touch_things(fake_things):
    proposed = await propose_add_todo(title="x", list_id="inbox")
    cancel_action(proposed["action_id"])
    assert fake_things == {}


# ---------- list_pending_actions ----------


async def test_list_pending_actions_returns_all(fake_things):
    a = await propose_add_todo(title="A", list_id="inbox")
    b = await propose_add_todo(title="B", list_id="today")
    rows = list_pending_actions()
    ids = {r["id"] for r in rows}
    assert ids == {a["action_id"], b["action_id"]}


# ---------- round-trip propose → confirm → undo ----------


async def test_full_round_trip_add_then_undo(fast_polling, fake_things, monkeypatch):
    """The V2 acceptance gate: round-trip undo must succeed."""
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", "tok-xyz")

    proposed = await propose_add_todo(title="Round trip", list_id="inbox")
    confirmed = await confirm_action(proposed["action_id"])
    new_uuid = confirmed["result"]["id"]
    assert fake_things[new_uuid]["status"] == "incomplete"

    undone = await undo_tool()
    assert undone["undone"] is True
    assert undone["target_uuid"] == new_uuid
    assert fake_things[new_uuid]["status"] in {"completed", "canceled"}

    # No undo log entries left after a successful undo.
    assert undo_log.most_recent() is None


async def test_undo_with_no_history_raises():
    with pytest.raises(ValueError, match="No reversible actions"):
        await undo_tool()


async def test_undo_with_unknown_id_raises():
    with pytest.raises(ValueError, match="No undo_log entry"):
        await undo_tool(undo_id="nope")


async def test_undo_by_explicit_id(fast_polling, fake_things, monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", "tok")
    proposed = await propose_add_todo(title="Pick by id", list_id="inbox")
    confirmed = await confirm_action(proposed["action_id"])
    undo_id = confirmed["result"]["undo_id"]

    out = await undo_tool(undo_id=undo_id)
    assert out["undone"] is True
    assert undo_log.get(undo_id) is None
