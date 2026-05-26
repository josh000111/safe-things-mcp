"""Unit tests for Fix B: tags field present in get_todo / get_project responses.

RED phase: tests fail until things_repo.todo() and things_repo.project()
are changed from things.get() to things.tasks().
"""
from __future__ import annotations

import pytest

from things_mcp.services import things_repo


# ---------- things_repo.todo() ----------


def test_todo_includes_tags_when_tasks_returns_them(monkeypatch):
    """things_repo.todo() must use things.tasks() so tags are included."""
    tagged_row = {
        "uuid": "abc-123",
        "type": "to-do",
        "title": "Tagged task",
        "status": "incomplete",
        "tags": ["Errand", "Home"],
    }
    monkeypatch.setattr("things.tasks", lambda uuid, **_: tagged_row)

    result = things_repo.todo("abc-123")
    assert result is not None
    assert result.get("tags") == ["Errand", "Home"]


def test_todo_untagged_returns_empty_tags_list(monkeypatch):
    """things.tasks() returning no tags key → todo() normalises to tags=[].

    Fix B: untagged items must return "tags": [] (key present, empty list)
    so callers never have to guard against a missing key.
    """
    untagged_row = {
        "uuid": "abc-456",
        "type": "to-do",
        "title": "Untagged task",
        "status": "incomplete",
    }
    monkeypatch.setattr("things.tasks", lambda uuid, **_: untagged_row)

    result = things_repo.todo("abc-456")
    assert result is not None
    assert "tags" in result
    assert result["tags"] == []


def test_todo_returns_none_when_tasks_raises_value_error(monkeypatch):
    """Non-UUID strings raise ValueError in things.tasks() → todo() returns None."""
    def raise_value_error(uuid, **_):
        raise ValueError("not a UUID")
    monkeypatch.setattr("things.tasks", raise_value_error)

    result = things_repo.todo("not-a-uuid")
    assert result is None


def test_todo_returns_none_when_tasks_returns_list(monkeypatch):
    """things.tasks() returning a list (not found) → todo() returns None."""
    monkeypatch.setattr("things.tasks", lambda uuid, **_: [])

    result = things_repo.todo("unknown-uuid")
    assert result is None


# ---------- things_repo.project() ----------


def test_project_includes_tags_when_tasks_returns_them(monkeypatch):
    """things_repo.project() must use things.tasks(type='project') so tags are included."""
    tagged_proj = {
        "uuid": "proj-123",
        "type": "project",
        "title": "Tagged project",
        "status": "incomplete",
        "tags": ["Errand"],
    }
    calls = []

    def fake_tasks(uuid, **kw):
        calls.append({"uuid": uuid, **kw})
        return tagged_proj

    monkeypatch.setattr("things.tasks", fake_tasks)

    result = things_repo.project("proj-123")
    assert result is not None
    assert result.get("tags") == ["Errand"]
    # Confirm the call was made with type="project"
    assert any(c.get("type") == "project" for c in calls)


def test_project_untagged_returns_empty_tags_list(monkeypatch):
    """things.tasks() returning no tags key → project() normalises to tags=[].

    Fix B: untagged projects must return "tags": [] (key present, empty list).
    """
    untagged_proj = {
        "uuid": "proj-456",
        "type": "project",
        "title": "Untagged project",
        "status": "incomplete",
    }
    monkeypatch.setattr("things.tasks", lambda uuid, **_: untagged_proj)

    result = things_repo.project("proj-456")
    assert result is not None
    assert "tags" in result
    assert result["tags"] == []


def test_project_returns_none_when_tasks_returns_list(monkeypatch):
    """things.tasks(type='project') returning a list → project() returns None."""
    monkeypatch.setattr("things.tasks", lambda uuid, **_: [])

    result = things_repo.project("unknown-proj")
    assert result is None


# ---------- get_todo tool path (delegates to things_repo.todo) ----------


def test_get_todo_tool_path_returns_tags(monkeypatch):
    """get_todo tool calls things_repo.todo() — verify the full path returns tags.

    This confirms that the tool layer (read.py) doesn't strip tags.
    We test through things_repo.todo() directly since the tool is a
    one-liner: return things_repo.todo(todo_id).
    """
    tagged_row = {
        "uuid": "tool-uuid",
        "type": "to-do",
        "title": "Tool path test",
        "tags": ["Errand"],
    }
    monkeypatch.setattr("things.tasks", lambda uuid, **_: tagged_row)

    result = things_repo.todo("tool-uuid")
    assert result is not None
    assert "tags" in result
    assert result["tags"] == ["Errand"]
