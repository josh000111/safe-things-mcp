"""CRUD tests for state/undo_log.py."""
from __future__ import annotations

import time

import pytest

from things_mcp import config
from things_mcp.state import undo_log


pytestmark = pytest.mark.usefixtures("isolated_state_db")


def test_record_returns_id_and_round_trips():
    entry_id = undo_log.record(
        action_kind="add_todo",
        target_uuid=None,  # filled in post-poll for adds
        before_state=None,
        after_state=None,
    )
    fetched = undo_log.get(entry_id)
    assert fetched is not None
    assert fetched["action_kind"] == "add_todo"
    assert fetched["target_uuid"] is None
    assert fetched["before_state"] is None
    assert fetched["after_state"] is None


def test_attach_target_fills_uuid_and_after_state():
    entry_id = undo_log.record(
        action_kind="add_todo",
        target_uuid=None,
        before_state=None,
        after_state=None,
    )
    assert undo_log.attach_target(
        entry_id, target_uuid="abc123", after_state={"uuid": "abc123", "title": "t"}
    ) is True
    fetched = undo_log.get(entry_id)
    assert fetched["target_uuid"] == "abc123"
    assert fetched["after_state"] == {"uuid": "abc123", "title": "t"}


def test_attach_target_missing_id_returns_false():
    assert undo_log.attach_target("nope", "uuid", None) is False


def test_delete_removes_row():
    entry_id = undo_log.record("add_todo", None, None, None)
    assert undo_log.delete(entry_id) is True
    assert undo_log.get(entry_id) is None
    assert undo_log.delete(entry_id) is False


def test_most_recent_returns_newest_row():
    first = undo_log.record("add_todo", "u1", None, {"v": 1})
    time.sleep(0.01)
    second = undo_log.record("update_todo", "u2", {"old": True}, {"new": True})
    latest = undo_log.most_recent()
    assert latest is not None
    assert latest["id"] == second
    assert latest["action_kind"] == "update_todo"
    # First entry still retrievable by id
    assert undo_log.get(first)["target_uuid"] == "u1"


def test_most_recent_returns_none_on_empty_table():
    assert undo_log.most_recent() is None


def test_recent_orders_newest_first_and_respects_limit():
    ids = []
    for i in range(5):
        ids.append(undo_log.record("add_todo", f"u{i}", None, None))
        time.sleep(0.005)
    rows = undo_log.recent(limit=3)
    assert len(rows) == 3
    assert [r["id"] for r in rows] == list(reversed(ids))[:3]


def test_trim_caps_table_to_max_rows(monkeypatch):
    monkeypatch.setattr(config, "UNDO_LOG_MAX_ROWS", 3)
    monkeypatch.setattr(undo_log, "UNDO_LOG_MAX_ROWS", 3)
    for i in range(6):
        undo_log.record("add_todo", f"u{i}", None, None)
        time.sleep(0.002)
    rows = undo_log.recent(limit=20)
    assert len(rows) == 3  # only newest 3 survive


def test_trim_drops_expired_rows(monkeypatch):
    monkeypatch.setattr(config, "UNDO_LOG_MAX_AGE_DAYS", -1)
    monkeypatch.setattr(undo_log, "UNDO_LOG_MAX_AGE_DAYS", -1)
    expired = undo_log.record("add_todo", "u_old", None, None)
    monkeypatch.setattr(undo_log, "UNDO_LOG_MAX_AGE_DAYS", 30)
    fresh = undo_log.record("add_todo", "u_new", None, None)
    rows = undo_log.recent(limit=20)
    assert [r["id"] for r in rows] == [fresh]
    assert undo_log.get(expired) is None
