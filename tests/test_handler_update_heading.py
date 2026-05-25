"""Unit tests for the ``update_heading`` handler.

* make_preview contains new_name uppercased
* execute raises when UUID not found
* execute raises when task is not a dummy heading
* execute raises when name not found in project
* execute raises when name is ambiguous (native + dummy)
* execute success by UUID
* undo restores original title
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import things_repo, url_scheme
from things_mcp.services.handlers import update_heading
from things_mcp.state import undo_log


pytestmark = pytest.mark.usefixtures("isolated_state_db")


@pytest.fixture
def fast_polling(monkeypatch):
    monkeypatch.setattr(config, "WRITE_POLL_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(config, "WRITE_POLL_INTERVAL_SECONDS", 0.01)


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


def _heading_row(
    uuid: str = "HDG-1",
    title: str = "__DESIGN__",
    modified: str = "2026-01-01 10:00:00",
) -> dict:
    return {
        "uuid": uuid,
        "type": "to-do",
        "title": title,
        "status": "incomplete",
        "modified": modified,
    }


def _project_row(items: list | None = None) -> dict:
    return {
        "uuid": "PROJ-1",
        "type": "project",
        "title": "My Project",
        "items": items or [],
    }


# ---------- make_preview ----------


def test_make_preview():
    preview = update_heading.make_preview({
        "project_id": "PROJ-1",
        "heading_id_or_name": "HDG-1",
        "new_name": "Implementation",
    })
    assert "__IMPLEMENTATION__" in preview
    assert "PROJ-1" in preview


# ---------- execute ----------


async def test_execute_uuid_not_found(with_auth, fast_polling, monkeypatch):
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: None)
    monkeypatch.setattr(things_repo, "project", lambda pid: _project_row())
    with pytest.raises(ValueError):
        await update_heading.execute({
            "project_id": "PROJ-1",
            "heading_id_or_name": "GHOST-UUID",
            "new_name": "NewName",
        })


async def test_execute_not_a_dummy(with_auth, fast_polling, monkeypatch):
    # get_todo returns a regular task (not a dummy heading).
    monkeypatch.setattr(
        things_repo, "get_todo",
        lambda uuid: {"uuid": uuid, "type": "to-do", "title": "Regular task", "status": "incomplete"},
    )
    with pytest.raises(ValueError, match="not a dummy heading"):
        await update_heading.execute({
            "project_id": "PROJ-1",
            "heading_id_or_name": "REGULAR-1",
            "new_name": "NewName",
        })


async def test_execute_name_not_found(with_auth, fast_polling, monkeypatch):
    # get_todo returns None (not a UUID match), project has no matching items.
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: None)
    monkeypatch.setattr(things_repo, "project", lambda pid: _project_row(items=[]))
    with pytest.raises(ValueError, match="No heading named"):
        await update_heading.execute({
            "project_id": "PROJ-1",
            "heading_id_or_name": "Nonexistent",
            "new_name": "NewName",
        })


async def test_execute_ambiguous(with_auth, fast_polling, monkeypatch):
    # Project has both a native heading AND a dummy heading with same name.
    items = [
        {"uuid": "NATIVE-1", "type": "heading", "title": "Design"},
        {"uuid": "HDG-1", "type": "to-do", "title": "__DESIGN__"},
    ]
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: None)
    monkeypatch.setattr(things_repo, "project", lambda pid: _project_row(items=items))
    with pytest.raises(ValueError, match="Ambiguous"):
        await update_heading.execute({
            "project_id": "PROJ-1",
            "heading_id_or_name": "Design",
            "new_name": "NewName",
        })


async def test_execute_success_by_uuid(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    original_row = _heading_row(uuid="HDG-1", title="__DESIGN__", modified="2026-01-01 10:00:00")
    updated_row = _heading_row(uuid="HDG-1", title="__IMPLEMENTATION__", modified="2026-01-01 10:00:01")

    call_count = {"n": 0}

    def fake_get_todo(uuid: str) -> dict | None:
        if uuid == "HDG-1":
            call_count["n"] += 1
            # Calls 1 and 2: resolution + before-state snapshot → original.
            # Subsequent calls (polling): return updated.
            if call_count["n"] <= 2:
                return original_row
            return updated_row
        return None

    monkeypatch.setattr(things_repo, "get_todo", fake_get_todo)

    result = await update_heading.execute({
        "project_id": "PROJ-1",
        "heading_id_or_name": "HDG-1",
        "new_name": "Implementation",
    })

    assert result["action_kind"] == "update_heading"
    assert "undo_id" in result
    assert result["id"] == "HDG-1"
    assert result["old_title"] == "__DESIGN__"
    assert result["new_title"] == "__IMPLEMENTATION__"

    # Verify URL launched with correct title.
    assert len(captured_launches) == 1
    url = captured_launches[0]
    assert "things:///update" in url
    assert "HDG-1" in url
    assert "__IMPLEMENTATION__" in url

    # undo_log entry exists.
    entry = undo_log.get(result["undo_id"])
    assert entry is not None
    assert entry["target_uuid"] == "HDG-1"


async def test_undo_restores_original_title(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    entry_id = undo_log.record(
        action_kind="update_heading",
        target_uuid="HDG-1",
        before_state={"full": _heading_row(), "title": "__DESIGN__"},
        after_state=_heading_row(title="__IMPLEMENTATION__", modified="2026-01-01 10:00:01"),
    )

    state = {"modified": "2026-01-01 10:00:01"}

    def fake_get_todo(uuid: str) -> dict | None:
        if uuid == "HDG-1":
            row = _heading_row(title="__DESIGN__", modified="2026-01-01 10:00:02")
            return row
        return None

    # First call returns current row (for pre_modified), polling returns advanced row.
    call_count = {"n": 0}

    def fake_get_todo_seq(uuid: str) -> dict | None:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _heading_row(title="__IMPLEMENTATION__", modified="2026-01-01 10:00:01")
        return _heading_row(title="__DESIGN__", modified="2026-01-01 10:00:02")

    monkeypatch.setattr(things_repo, "get_todo", fake_get_todo_seq)

    result = await update_heading.undo(undo_log.get(entry_id))
    assert result["undone"] is True
    assert result["restored_title"] == "__DESIGN__"

    # undo_log entry deleted.
    assert undo_log.get(entry_id) is None

    # URL contained the original title.
    url = captured_launches[0]
    assert "__DESIGN__" in url


async def test_undo_requires_auth(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await update_heading.undo({
            "id": "e1",
            "action_kind": "update_heading",
            "target_uuid": "HDG-1",
            "before_state": {"title": "__DESIGN__"},
        })
