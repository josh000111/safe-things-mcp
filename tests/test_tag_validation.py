"""Unit tests for Fix A: tag pre-validation before write tools fire.

RED phase: all tests fail until validate_tags() exists and is wired in.
"""
from __future__ import annotations

import pytest

from things_mcp.services import things_repo, url_scheme
from things_mcp.state import pending
from things_mcp.tools import propose as propose_module


pytestmark = pytest.mark.usefixtures("isolated_state_db")


# ---------- validate_tags unit tests ----------


def test_validate_tags_empty_list_is_noop(monkeypatch):
    monkeypatch.setattr("things.tags", lambda **_: [{"title": "Errand"}])
    url_scheme.validate_tags([])  # must not raise


def test_validate_tags_none_is_noop(monkeypatch):
    monkeypatch.setattr("things.tags", lambda **_: [{"title": "Errand"}])
    url_scheme.validate_tags(None)  # must not raise


def test_validate_tags_known_tag_is_noop(monkeypatch):
    monkeypatch.setattr("things.tags", lambda **_: [{"title": "Errand"}])
    url_scheme.validate_tags(["Errand"])  # must not raise


def test_validate_tags_unknown_tag_raises_with_actionable_message(monkeypatch):
    monkeypatch.setattr("things.tags", lambda **_: [{"title": "Errand"}])
    with pytest.raises(ValueError) as exc_info:
        url_scheme.validate_tags(["Errand", "FakeTag"])
    msg = str(exc_info.value)
    assert "FakeTag" in msg
    assert "Errand" in msg  # available tags listed in error message


def test_validate_tags_multiple_unknown_tags_all_named(monkeypatch):
    monkeypatch.setattr("things.tags", lambda **_: [{"title": "Errand"}])
    with pytest.raises(ValueError) as exc_info:
        url_scheme.validate_tags(["FakeTag1", "FakeTag2"])
    msg = str(exc_info.value)
    assert "FakeTag1" in msg
    assert "FakeTag2" in msg


# ---------- propose_add_todo integration: rejects unknown tag before enqueue ----------


async def test_propose_add_todo_rejects_unknown_tag_before_enqueue(monkeypatch):
    monkeypatch.setattr("things.tags", lambda **_: [{"title": "Errand"}])

    before_count = len(pending.list_all())
    with pytest.raises(ValueError, match="NonExistentTag"):
        await propose_module.propose_add_todo(
            title="Tag test",
            tags=["NonExistentTag"],
        )
    assert len(pending.list_all()) == before_count, (
        "A pending action must NOT be created when tag validation fails"
    )


async def test_propose_add_todo_accepts_known_tag_and_enqueues(monkeypatch):
    monkeypatch.setattr("things.tags", lambda **_: [{"title": "Errand"}])

    before_count = len(pending.list_all())
    result = await propose_module.propose_add_todo(
        title="Tag test known",
        tags=["Errand"],
    )
    assert result.get("action_id") is not None
    assert len(pending.list_all()) == before_count + 1


# ---------- propose_bulk_update integration: rejects mixed tags before enqueue ----------


async def test_propose_bulk_update_rejects_mixed_unknown_tag_before_enqueue(monkeypatch):
    monkeypatch.setattr("things.tags", lambda **_: [{"title": "Errand"}])

    before_count = len(pending.list_all())
    with pytest.raises(ValueError, match="GhostTag"):
        await propose_module.propose_bulk_update(
            todo_ids=["uuid-1", "uuid-2"],
            tags=["Errand", "GhostTag"],
        )
    assert len(pending.list_all()) == before_count, (
        "No pending action must be created when tag validation fails at propose time"
    )


# ---------- propose_update_todo: rejects unknown tag before enqueue ----------


async def test_propose_update_todo_rejects_unknown_tag_before_enqueue(monkeypatch):
    monkeypatch.setattr("things.tags", lambda **_: [{"title": "Errand"}])

    before_count = len(pending.list_all())
    with pytest.raises(ValueError, match="FakeTag"):
        await propose_module.propose_update_todo(
            todo_id="some-valid-uuid",
            tags=["FakeTag"],
        )
    assert len(pending.list_all()) == before_count


# ---------- propose_add_project: rejects unknown tag before enqueue ----------


async def test_propose_add_project_rejects_unknown_tag_before_enqueue(monkeypatch):
    monkeypatch.setattr("things.tags", lambda **_: [{"title": "Errand"}])

    before_count = len(pending.list_all())
    with pytest.raises(ValueError, match="FakeProjectTag"):
        await propose_module.propose_add_project(
            title="Test project",
            tags=["FakeProjectTag"],
        )
    assert len(pending.list_all()) == before_count


# ---------- propose_update_project: rejects unknown tag before enqueue ----------


async def test_propose_update_project_rejects_unknown_tag_before_enqueue(monkeypatch):
    monkeypatch.setattr("things.tags", lambda **_: [{"title": "Errand"}])

    before_count = len(pending.list_all())
    with pytest.raises(ValueError, match="FakeProjectTag"):
        await propose_module.propose_update_project(
            project_id="some-project-uuid",
            tags=["FakeProjectTag"],
        )
    assert len(pending.list_all()) == before_count
