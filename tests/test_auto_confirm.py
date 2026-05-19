"""Tests for the ``THINGS_MCP_AUTO_CONFIRM`` env-flag behaviour.

Verifies:

* Off (default): ``propose_*`` enqueues and returns ``auto_confirmed: False``.
* On + safe kind: ``propose_*`` runs the handler inline and returns
  ``auto_confirmed: True`` with the result attached.
* On + never-bypass kind: ``propose_*`` still enqueues only — the kind's
  destructive nature wins regardless of the flag.
* On + handler raises mid-execute: the pending row is preserved so the
  user can retry via explicit ``confirm_action`` after fixing the issue.
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import handlers, things_repo, url_scheme
from things_mcp.state import pending, undo_log
from things_mcp.tools.propose import propose_add_todo


pytestmark = pytest.mark.usefixtures("isolated_state_db")


@pytest.fixture
def fast_polling(monkeypatch):
    monkeypatch.setattr(config, "WRITE_POLL_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(config, "WRITE_POLL_INTERVAL_SECONDS", 0.01)


@pytest.fixture
def fake_things(monkeypatch):
    state: dict[str, dict] = {}

    async def fake_launch(url: str) -> None:
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(url)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        if parsed.path == "/add":
            uid = f"u-{len(state) + 1}"
            state[uid] = {
                "uuid": uid,
                "title": params.get("title", ""),
                "status": "incomplete",
                "created": "2026-05-19 03:00:00",
                "start": "Inbox",
            }

    monkeypatch.setattr(url_scheme, "launch", fake_launch)
    monkeypatch.setattr(
        things_repo, "find_recent_by_title",
        lambda title, created_after: next(
            (t for t in state.values() if t["title"] == title), None
        ),
    )
    return state


# ---------- off (default) ----------


async def test_off_just_enqueues(fake_things):
    """Default behaviour: AUTO_CONFIRM unset → return propose stub only."""
    out = await propose_add_todo(title="No autoconfirm", list_id="inbox")
    assert out["auto_confirmed"] is False
    assert "result" not in out
    assert pending.get(out["action_id"]) is not None
    assert fake_things == {}  # no mutation happened


# ---------- on + safe kind ----------


async def test_on_runs_handler_inline(fast_polling, fake_things, monkeypatch):
    monkeypatch.setattr(config, "AUTO_CONFIRM", True)

    out = await propose_add_todo(title="Auto landed", list_id="inbox")
    assert out["auto_confirmed"] is True
    assert "result" in out
    assert out["result"]["title"] == "Auto landed"
    # Pending row is gone — auto-confirm removed it after success.
    assert pending.get(out["action_id"]) is None
    # And Things received the mutation.
    assert any(t["title"] == "Auto landed" for t in fake_things.values())
    # Undo log row exists (the handler always writes one).
    assert undo_log.most_recent() is not None


# ---------- on + never-bypass kind ----------


async def test_on_does_not_bypass_real_delete_kind(fast_polling, fake_things, monkeypatch):
    """``delete_todo`` is hard-coded into NEVER_BYPASS_KINDS. With the
    flag on, ``propose_delete_todo`` must still enqueue and require
    explicit confirm."""
    from things_mcp.tools.propose import propose_delete_todo

    monkeypatch.setattr(config, "AUTO_CONFIRM", True)
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", "tok")

    # Seed a task in the fake state so existence check passes (the test
    # is about gating, not about whether delete completes).
    fake_things["target-1"] = {"uuid": "target-1", "title": "x", "status": "incomplete"}
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: fake_things.get(uuid))
    monkeypatch.setattr(things_repo, "get", lambda uuid: fake_things.get(uuid))

    out = await propose_delete_todo(todo_id="target-1")
    assert out["auto_confirmed"] is False
    assert "never auto-confirmed" in out["next_step"]
    # Task untouched — still incomplete.
    assert fake_things["target-1"]["status"] == "incomplete"


async def test_on_does_not_bypass_never_kinds(fast_polling, fake_things, monkeypatch):
    """A kind in NEVER_BYPASS_KINDS still enqueues even with the flag on."""
    monkeypatch.setattr(config, "AUTO_CONFIRM", True)
    # Inject add_todo into the never-bypass set just for this test.
    monkeypatch.setattr(
        config, "NEVER_BYPASS_KINDS", frozenset({handlers.add_todo.KIND})
    )

    out = await propose_add_todo(title="Should not auto-confirm", list_id="inbox")
    assert out["auto_confirmed"] is False
    # Pending row remains; nothing landed in Things.
    assert pending.get(out["action_id"]) is not None
    assert fake_things == {}
    # The next_step hint mentions never-auto-confirmed wording.
    assert "never auto-confirmed" in out["next_step"]


# ---------- on + handler raises ----------


async def test_on_keeps_pending_row_when_handler_fails(monkeypatch):
    """If the auto-confirm execute() raises, the pending row is preserved
    so the user can retry via explicit confirm_action after fixing the
    underlying issue (e.g. a missing auth token)."""
    monkeypatch.setattr(config, "AUTO_CONFIRM", True)

    # Force the handler to raise by removing the mocked URL launcher and
    # the things_repo finder — execute() will time out / fail.
    async def boom(url: str) -> None:
        raise RuntimeError("Things URL scheme is unreachable")

    monkeypatch.setattr(url_scheme, "launch", boom)

    with pytest.raises(RuntimeError, match="unreachable"):
        await propose_add_todo(title="Will fail mid-flight", list_id="inbox")

    # Pending row survives the failure.
    rows = pending.list_all()
    assert len(rows) == 1
    assert rows[0]["kind"] == "add_todo"
