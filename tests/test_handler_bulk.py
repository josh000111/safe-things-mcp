"""Unit tests for the four ``bulk_*`` handlers.

Bulk ops share a shape: per-item snapshot in ONE undo_log row, sequential
URL launches, one undo() restores the whole batch. Tests below pin that
contract per kind.

URL launcher and ``things_repo`` are mocked — no Things app required.
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import things_repo, url_scheme
from things_mcp.services.handlers import (
    bulk_complete,
    bulk_delete,
    bulk_move,
    bulk_update,
)
from things_mcp.state import undo_log


pytestmark = pytest.mark.usefixtures("isolated_state_db")


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


def _row(uuid: str, *, status: str = "incomplete", title: str | None = None,
         notes: str = "n", deadline: str | None = "2026-06-01",
         tags: list[str] | None = None, start: str = "Anytime",
         start_date: str | None = None, project: str | None = None) -> dict:
    r = {
        "uuid": uuid,
        "type": "to-do",
        "title": title or f"task-{uuid}",
        "status": status,
        "notes": notes,
        "deadline": deadline,
        "start": start,
        "modified": "2026-05-18 10:00:00",
    }
    if start_date:
        r["start_date"] = start_date
    if project:
        r["project"] = project
    if tags is not None:
        r["tags"] = tags
    return r


# =============================================================================
# bulk_complete
# =============================================================================


async def test_bulk_complete_requires_auth(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await bulk_complete.execute({"todo_ids": ["a"]})


async def test_bulk_complete_rejects_empty_list(with_auth):
    with pytest.raises(ValueError, match="non-empty"):
        await bulk_complete.execute({"todo_ids": []})


async def test_bulk_complete_aborts_when_any_missing(with_auth, monkeypatch, captured_launches):
    rows = {"a": _row("a")}
    monkeypatch.setattr(things_repo, "get_todo", lambda uid: rows.get(uid))

    with pytest.raises(ValueError, match="No to-do found"):
        await bulk_complete.execute({"todo_ids": ["a", "ghost"]})
    # No URLs launched — abort happened pre-mutation.
    assert captured_launches == []
    # No undo_log row written either.
    assert undo_log.recent() == []


async def test_bulk_complete_aborts_when_any_already_done(with_auth, monkeypatch):
    rows = {"a": _row("a"), "b": _row("b", status="completed")}
    monkeypatch.setattr(things_repo, "get_todo", lambda uid: rows.get(uid))

    with pytest.raises(ValueError, match="already status"):
        await bulk_complete.execute({"todo_ids": ["a", "b"]})


async def test_bulk_complete_writes_one_undo_log_row_for_batch(
    with_auth, monkeypatch, captured_launches
):
    rows = {"a": _row("a"), "b": _row("b"), "c": _row("c")}
    monkeypatch.setattr(things_repo, "get_todo", lambda uid: rows.get(uid))

    result = await bulk_complete.execute({"todo_ids": ["a", "b", "c"]})
    assert result["count"] == 3
    assert result["ids"] == ["a", "b", "c"]

    # Exactly one undo_log row, three URL launches.
    rows_log = undo_log.recent(limit=10)
    assert len(rows_log) == 1
    full = undo_log.get(rows_log[0]["id"])
    assert len(full["before_state"]["items"]) == 3
    assert len(captured_launches) == 3
    for url in captured_launches:
        assert url.startswith("things:///update?")
        assert "completed=true" in url


async def test_bulk_complete_undo_round_trip(
    with_auth, monkeypatch, captured_launches
):
    """Undo issues N inverse URLs and deletes the log row."""
    entry_id = undo_log.record(
        action_kind="bulk_complete",
        target_uuid=None,
        before_state={
            "items": [
                {"target_uuid": "a", "title": "x", "before_status": "incomplete"},
                {"target_uuid": "b", "title": "y", "before_status": "incomplete"},
            ],
            "count": 2,
        },
        after_state=None,
    )

    result = await bulk_complete.undo(undo_log.get(entry_id))
    assert result["undone"] is True
    assert result["count"] == 2
    assert len(captured_launches) == 2
    for url in captured_launches:
        assert "completed=false" in url
        assert "canceled=false" in url
    assert undo_log.get(entry_id) is None


# =============================================================================
# bulk_cancel (was bulk_delete)
# =============================================================================


async def test_bulk_cancel_requires_auth(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await bulk_delete.execute({"todo_ids": ["a"]})


async def test_bulk_cancel_aborts_when_any_already_done(with_auth, monkeypatch):
    rows = {"a": _row("a"), "b": _row("b", status="canceled")}
    monkeypatch.setattr(things_repo, "get_todo", lambda uid: rows.get(uid))
    with pytest.raises(ValueError, match="already status"):
        await bulk_delete.execute({"todo_ids": ["a", "b"]})


async def test_bulk_cancel_launches_canceled_completed_per_item(
    with_auth, monkeypatch, captured_launches
):
    rows = {"a": _row("a"), "b": _row("b")}
    monkeypatch.setattr(things_repo, "get_todo", lambda uid: rows.get(uid))

    result = await bulk_delete.execute({"todo_ids": ["a", "b"]})
    assert result["count"] == 2
    assert len(captured_launches) == 2
    for url in captured_launches:
        assert "canceled=true" in url
        assert "completed=true" in url


async def test_bulk_cancel_undo_restores_all(
    with_auth, monkeypatch, captured_launches
):
    entry_id = undo_log.record(
        action_kind="bulk_cancel",
        target_uuid=None,
        before_state={
            "items": [
                {"target_uuid": "a", "title": "x", "before_status": "incomplete"},
                {"target_uuid": "b", "title": "y", "before_status": "incomplete"},
            ],
            "count": 2,
        },
        after_state=None,
    )

    await bulk_delete.undo(undo_log.get(entry_id))
    for url in captured_launches:
        assert "canceled=false" in url
        assert "completed=false" in url


# =============================================================================
# bulk_move
# =============================================================================


async def test_bulk_move_rejects_inbox(with_auth):
    with pytest.raises(ValueError, match="not supported"):
        await bulk_move.execute({"todo_ids": ["a"], "target": "inbox"})


async def test_bulk_move_requires_target(with_auth):
    with pytest.raises(ValueError, match="target is required"):
        await bulk_move.execute({"todo_ids": ["a"], "target": ""})


async def test_bulk_move_scheduling_captures_per_item_inverse(
    with_auth, monkeypatch, captured_launches
):
    """Each task has its own original scheduling — inverse_params must
    differ per item."""
    rows = {
        "a": _row("a", start="Today"),
        "b": _row("b", start="Anytime", start_date="2026-06-15"),
    }
    monkeypatch.setattr(things_repo, "get_todo", lambda uid: rows.get(uid))

    result = await bulk_move.execute({"todo_ids": ["a", "b"], "target": "someday"})
    assert result["dimension"] == "schedule"

    full = undo_log.get(result["undo_id"])
    inverses = {it["target_uuid"]: it["inverse_params"] for it in full["before_state"]["items"]}
    assert inverses["a"]["when"] == "today"
    assert inverses["b"]["when"] == "2026-06-15"

    for url in captured_launches:
        assert "when=someday" in url


async def test_bulk_move_project_dimension(
    with_auth, monkeypatch, captured_launches
):
    rows = {"a": _row("a", project="proj-old"), "b": _row("b")}
    monkeypatch.setattr(things_repo, "get_todo", lambda uid: rows.get(uid))

    result = await bulk_move.execute({
        "todo_ids": ["a", "b"], "target": "proj-new-uuid-1234",
    })
    assert result["dimension"] == "project"

    full = undo_log.get(result["undo_id"])
    inverses = {it["target_uuid"]: it["inverse_params"] for it in full["before_state"]["items"]}
    assert inverses["a"]["list_id"] == "proj-old"
    # b had no project, inverse clears
    assert inverses["b"]["list_id"] == ""


async def test_bulk_move_undo_restores_per_item(
    with_auth, monkeypatch, captured_launches
):
    entry_id = undo_log.record(
        action_kind="bulk_move",
        target_uuid=None,
        before_state={
            "items": [
                {"target_uuid": "a", "inverse_params": {"when": "today"}},
                {"target_uuid": "b", "inverse_params": {"when": "anytime"}},
            ],
            "count": 2,
            "dimension": "schedule",
            "target": "someday",
        },
        after_state=None,
    )

    result = await bulk_move.undo(undo_log.get(entry_id))
    assert result["undone"] is True
    assert len(captured_launches) == 2
    assert "when=today" in captured_launches[0]
    assert "when=anytime" in captured_launches[1]


# =============================================================================
# bulk_update
# =============================================================================


async def test_bulk_update_requires_auth(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await bulk_update.execute({"todo_ids": ["a"], "title": "x"})


async def test_bulk_update_requires_at_least_one_field(with_auth, monkeypatch):
    monkeypatch.setattr(things_repo, "get_todo", lambda uid: _row(uid))
    with pytest.raises(ValueError, match="no fields to update"):
        await bulk_update.execute({"todo_ids": ["a"]})


async def test_bulk_update_captures_per_item_inverse_fields(
    with_auth, monkeypatch, captured_launches
):
    rows = {
        "a": _row("a", title="A original", notes="a notes"),
        "b": _row("b", title="B original", notes="b notes"),
    }
    monkeypatch.setattr(things_repo, "get_todo", lambda uid: rows.get(uid))

    result = await bulk_update.execute({
        "todo_ids": ["a", "b"],
        "title": "Unified title",
    })
    assert result["changed_fields"] == ["title"]

    full = undo_log.get(result["undo_id"])
    inv = {it["target_uuid"]: it["inverse_fields"] for it in full["before_state"]["items"]}
    assert inv["a"]["title"] == "A original"
    assert inv["b"]["title"] == "B original"

    for url in captured_launches:
        assert "title=Unified" in url


async def test_bulk_update_undo_restores_per_item_values(
    with_auth, monkeypatch, captured_launches
):
    entry_id = undo_log.record(
        action_kind="bulk_update",
        target_uuid=None,
        before_state={
            "items": [
                {"target_uuid": "a", "inverse_fields": {"title": "A old"}},
                {"target_uuid": "b", "inverse_fields": {"title": "B old"}},
            ],
            "count": 2,
            "changed": ["title"],
            "applied_fields": {"title": "Unified"},
        },
        after_state=None,
    )

    await bulk_update.undo(undo_log.get(entry_id))
    # Two URLs, each restoring a different original title.
    assert any("title=A%20old" in u or "title=A old" in u for u in captured_launches)
    assert any("title=B%20old" in u or "title=B old" in u for u in captured_launches)


# =============================================================================
# previews
# =============================================================================


def test_previews_render_counts():
    assert "Bulk complete 3 to-dos" in bulk_complete.make_preview({"todo_ids": ["a", "b", "c"]})
    assert "Bulk cancel 1 to-do " in bulk_delete.make_preview({"todo_ids": ["a"]})
    assert "Bulk move 2 to-dos to 'today'" in bulk_move.make_preview({"todo_ids": ["a", "b"], "target": "today"})
    assert "Bulk update 2 to-dos: title='New'" in bulk_update.make_preview({"todo_ids": ["a", "b"], "title": "New"})
