"""Unit tests for things_repo helpers that don't require the live Things DB.

The full read-layer tests need a real ``main.sqlite`` and Things app; those
remain in ``things-mcp-manual-verification.md`` for now. Here we only cover pure helpers
that can be exercised by monkey-patching ``things.inbox``.
"""
from __future__ import annotations

from things_mcp.services import things_repo


def _make_todo(uuid: str, title: str, created: str) -> dict:
    return {"uuid": uuid, "type": "to-do", "title": title, "created": created}


def test_find_recent_inbox_by_title_returns_match(monkeypatch):
    rows = [
        _make_todo("u1", "MCP test 1", "2026-05-18 02:00:00"),
        _make_todo("u2", "Old task",   "2026-05-17 12:00:00"),
    ]
    monkeypatch.setattr("things.inbox", lambda **_: rows)

    hit = things_repo.find_recent_inbox_by_title(
        "MCP test 1", created_after="2026-05-18 01:59:58"
    )
    assert hit is not None
    assert hit["uuid"] == "u1"


def test_find_recent_inbox_by_title_ignores_older_rows(monkeypatch):
    rows = [_make_todo("u1", "MCP test 1", "2026-05-17 23:00:00")]
    monkeypatch.setattr("things.inbox", lambda **_: rows)

    hit = things_repo.find_recent_inbox_by_title(
        "MCP test 1", created_after="2026-05-18 02:00:00"
    )
    assert hit is None


def test_find_recent_inbox_by_title_ignores_other_titles(monkeypatch):
    rows = [_make_todo("u1", "Different title", "2026-05-18 02:00:00")]
    monkeypatch.setattr("things.inbox", lambda **_: rows)

    hit = things_repo.find_recent_inbox_by_title(
        "MCP test 1", created_after="2026-05-18 01:00:00"
    )
    assert hit is None


def test_find_recent_inbox_by_title_picks_newest_when_duplicate_titles(monkeypatch):
    rows = [
        _make_todo("older", "Same title", "2026-05-18 02:00:00"),
        _make_todo("newer", "Same title", "2026-05-18 02:00:05"),
    ]
    monkeypatch.setattr("things.inbox", lambda **_: rows)

    hit = things_repo.find_recent_inbox_by_title(
        "Same title", created_after="2026-05-18 01:59:00"
    )
    assert hit is not None
    assert hit["uuid"] == "newer"
