"""CRUD tests for state/pending.py."""
from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pytest

from things_mcp import config
from things_mcp.state import pending


pytestmark = pytest.mark.usefixtures("isolated_state_db")


def test_enqueue_returns_action_id_and_persists():
    res = pending.enqueue(
        kind="add_todo",
        payload={"title": "Buy milk", "list_id": "inbox"},
        preview="Add to-do 'Buy milk' to Inbox",
    )
    assert set(res) == {"action_id", "preview", "expires_at"}
    fetched = pending.get(res["action_id"])
    assert fetched is not None
    assert fetched["kind"] == "add_todo"
    assert fetched["payload"] == {"title": "Buy milk", "list_id": "inbox"}
    assert fetched["preview"] == "Add to-do 'Buy milk' to Inbox"


def test_get_returns_none_for_missing_id():
    assert pending.get("nope-not-here") is None


def test_delete_removes_row():
    res = pending.enqueue(kind="add_todo", payload={}, preview="p")
    assert pending.delete(res["action_id"]) is True
    assert pending.get(res["action_id"]) is None
    # second delete is idempotent (returns False, doesn't raise)
    assert pending.delete(res["action_id"]) is False


def test_list_all_orders_newest_first():
    a = pending.enqueue(kind="add_todo", payload={}, preview="first")
    time.sleep(0.01)
    b = pending.enqueue(kind="add_todo", payload={}, preview="second")
    rows = pending.list_all()
    assert [r["id"] for r in rows[:2]] == [b["action_id"], a["action_id"]]


def test_sweep_expired_only_drops_old_rows(monkeypatch):
    # First insert with an artificially short TTL → already expired.
    monkeypatch.setattr(config, "PENDING_TTL_SECONDS", -1)
    monkeypatch.setattr(pending, "PENDING_TTL_SECONDS", -1)
    stale = pending.enqueue(kind="add_todo", payload={}, preview="stale")

    # Then a fresh one with the normal TTL.
    monkeypatch.setattr(pending, "PENDING_TTL_SECONDS", 300)
    fresh = pending.enqueue(kind="add_todo", payload={}, preview="fresh")

    swept = pending.sweep_expired()
    assert swept == 1
    assert pending.get(stale["action_id"]) is None
    assert pending.get(fresh["action_id"]) is not None


def test_expires_at_is_roughly_now_plus_ttl():
    res = pending.enqueue(kind="add_todo", payload={}, preview="p")
    expires = datetime.fromisoformat(res["expires_at"])
    delta = expires - datetime.now(UTC)
    # Default TTL is 5 minutes; allow generous slack.
    assert timedelta(seconds=200) < delta < timedelta(seconds=400)
