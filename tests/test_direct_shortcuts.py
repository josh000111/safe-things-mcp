"""Tests for V2 direct (no-airlock) tools.

These exercise the user-facing tool functions that skip the propose/confirm
queue: ``add_today_todo``, ``add_anytime_todo``, ``add_someday_todo``, and
``complete_todo``. URL launches are mocked; the fake-Things state from
``test_dispatcher.py`` is recreated here in a focused form.
"""
from __future__ import annotations

import pytest
from mcp.server.fastmcp import FastMCP

from things_mcp import config
from things_mcp.services import things_repo, url_scheme
from things_mcp.state import undo_log
from things_mcp.tools import write as write_tool


pytestmark = pytest.mark.usefixtures("isolated_state_db")


@pytest.fixture
def fast_polling(monkeypatch):
    monkeypatch.setattr(config, "WRITE_POLL_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(config, "WRITE_POLL_INTERVAL_SECONDS", 0.01)


@pytest.fixture
def fake_things(monkeypatch):
    """In-memory Things stand-in: tracks adds and completion state."""
    state: dict[str, dict] = {}

    async def fake_launch(url: str) -> None:
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(url)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        if parsed.path == "/add":
            new_uuid = f"uuid-{len(state) + 1}"
            state[new_uuid] = {
                "uuid": new_uuid,
                "title": params.get("title", ""),
                "status": "incomplete",
                "created": "2026-05-18 03:00:00",
                "start": params.get("when", "Inbox").capitalize(),
            }
        elif parsed.path == "/update":
            uid = params["id"]
            if uid in state and params.get("completed") == "true":
                state[uid]["status"] = "completed"
            elif uid in state and params.get("completed") == "false":
                state[uid]["status"] = "incomplete"

    monkeypatch.setattr(url_scheme, "launch", fake_launch)
    monkeypatch.setattr(
        things_repo, "find_recent_by_title",
        lambda title, created_after: next(
            (t for t in state.values() if t["title"] == title), None
        ),
    )
    monkeypatch.setattr(things_repo, "get", lambda uuid: state.get(uuid))
    return state


def _register_tools() -> dict:
    """Build a FastMCP server and pull the registered closures out of it."""
    mcp = FastMCP("things-mcp-test")
    write_tool.register(mcp)
    # FastMCP stores tools in mcp._tool_manager._tools — but the underlying
    # callables are easier to reach via the public list_tools.
    return mcp


# ---------- add_today_todo ----------


async def test_add_today_todo_creates_and_logs_undo(fast_polling, fake_things):
    # Call the inner closure directly via _direct_add (same wire as the tool).
    result = await write_tool._direct_add(
        list_id="today", title="Buy milk", notes=None,
        deadline=None, tags=None, checklist=None,
    )
    assert result["list_id"] == "today"
    assert result["id"] in fake_things

    # Undo log row was written.
    entry = undo_log.get(result["undo_id"])
    assert entry["action_kind"] == "add_todo"
    assert entry["target_uuid"] == result["id"]


async def test_add_today_todo_routes_via_when_param(fast_polling, fake_things):
    """``today`` must produce ``when=today`` in the URL (bug we fixed)."""
    captured: list[str] = []
    original = url_scheme.launch

    async def spy(url: str) -> None:
        captured.append(url)
        await original(url)

    # monkey-patch directly (no fixture — keep this self-contained)
    url_scheme.launch = spy
    try:
        await write_tool._direct_add(
            list_id="today", title="x", notes=None,
            deadline=None, tags=None, checklist=None,
        )
    finally:
        url_scheme.launch = original

    assert any("when=today" in u for u in captured)
    assert not any("list=today" in u for u in captured)


async def test_add_anytime_and_someday_round_trip(fast_polling, fake_things):
    a = await write_tool._direct_add(
        list_id="anytime", title="A", notes=None,
        deadline=None, tags=None, checklist=None,
    )
    s = await write_tool._direct_add(
        list_id="someday", title="S", notes=None,
        deadline=None, tags=None, checklist=None,
    )
    assert a["id"] in fake_things
    assert s["id"] in fake_things


async def test_direct_add_validates_empty_title(fast_polling, fake_things):
    with pytest.raises(Exception):
        await write_tool._direct_add(
            list_id="today", title="", notes=None,
            deadline=None, tags=None, checklist=None,
        )


# ---------- complete_todo ----------


async def test_complete_todo_requires_auth_token(fast_polling, fake_things, monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    fake_things["existing-1"] = {
        "uuid": "existing-1", "title": "t", "status": "incomplete"
    }

    from things_mcp.services.handlers import complete_todo
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await complete_todo.execute({"todo_id": "existing-1"})


async def test_complete_todo_marks_completed_and_logs_undo(
    fast_polling, fake_things, monkeypatch
):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", "tok")
    fake_things["existing-1"] = {
        "uuid": "existing-1", "title": "t", "status": "incomplete"
    }

    from things_mcp.services.handlers import complete_todo
    result = await complete_todo.execute({"todo_id": "existing-1"})
    assert result["status"] == "completed"
    assert fake_things["existing-1"]["status"] == "completed"

    entry = undo_log.get(result["undo_id"])
    assert entry["action_kind"] == "complete_todo"
    assert entry["before_state"]["status"] == "incomplete"
    assert entry["after_state"]["status"] == "completed"


async def test_complete_then_undo_restores_incomplete(
    fast_polling, fake_things, monkeypatch
):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", "tok")
    fake_things["existing-1"] = {
        "uuid": "existing-1", "title": "t", "status": "incomplete"
    }

    from things_mcp.services.handlers import complete_todo
    from things_mcp.tools.undo import undo as undo_tool

    result = await complete_todo.execute({"todo_id": "existing-1"})
    assert fake_things["existing-1"]["status"] == "completed"

    undone = await undo_tool()
    assert undone["undone"] is True
    assert fake_things["existing-1"]["status"] == "incomplete"
    assert undo_log.get(result["undo_id"]) is None
