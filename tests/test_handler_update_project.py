"""Unit tests for the ``update_project`` handler.

Mirrors :mod:`test_handler_update_todo`: pre-launch snapshot + inverse
fields + selective restore on undo. URL launcher and ``things_repo`` are
mocked.
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import things_repo, url_scheme
from things_mcp.services.handlers import update_project
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


def _make_row(
    uuid: str = "proj",
    title: str = "Original project",
    notes: str = "original notes",
    deadline: str | None = "2026-06-01",
    tags: list[str] | None = None,
    area: str | None = "area-1",
    modified: str = "2026-05-18 10:00:00",
) -> dict:
    row = {
        "uuid": uuid,
        "type": "project",
        "title": title,
        "notes": notes,
        "status": "incomplete",
        "deadline": deadline,
        "area": area,
        "modified": modified,
        "created": "2026-05-18 09:00:00",
    }
    if tags is not None:
        row["tags"] = tags
    return row


# ---------- execute ----------


async def test_execute_requires_auth(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await update_project.execute({"project_id": "p1", "title": "x"})


async def test_execute_raises_when_no_fields(with_auth, monkeypatch):
    monkeypatch.setattr(things_repo, "get_project_row", lambda uuid: _make_row())
    with pytest.raises(ValueError, match="no fields to update"):
        await update_project.execute({"project_id": "p1"})


async def test_execute_raises_when_project_missing(with_auth, monkeypatch):
    monkeypatch.setattr(things_repo, "get_project_row", lambda uuid: None)
    with pytest.raises(ValueError, match="No project found"):
        await update_project.execute({"project_id": "ghost", "title": "x"})


async def test_execute_writes_undo_log_before_launch(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    pre_launch_rows: list[dict] = []
    state = {"row": _make_row(modified="2026-05-18 10:00:00")}

    monkeypatch.setattr(things_repo, "get_project_row", lambda uuid: state["row"])
    real_launch = url_scheme.launch

    async def snapshotting_launch(url: str) -> None:
        pre_launch_rows.extend(undo_log.recent(limit=10))
        state["row"] = _make_row(
            title="New title", modified="2026-05-18 10:00:05"
        )
        await real_launch(url)

    monkeypatch.setattr(url_scheme, "launch", snapshotting_launch)

    await update_project.execute({"project_id": "proj", "title": "New title"})

    assert len(pre_launch_rows) == 1
    summary = pre_launch_rows[0]
    assert summary["action_kind"] == "update_project"
    assert summary["target_uuid"] == "proj"

    full = undo_log.get(summary["id"])
    assert full["before_state"]["full"]["title"] == "Original project"
    assert full["before_state"]["inverse_fields"]["title"] == "Original project"
    assert full["before_state"]["changed"] == ["title"]


async def test_execute_builds_url_with_all_fields(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    state = {"row": _make_row(modified="2026-05-18 10:00:00")}

    real_launch = url_scheme.launch

    async def advancing_launch(url: str) -> None:
        state["row"] = {**state["row"], "modified": "2026-05-18 10:00:05"}
        await real_launch(url)

    monkeypatch.setattr(things_repo, "get_project_row", lambda uuid: state["row"])
    monkeypatch.setattr(url_scheme, "launch", advancing_launch)

    await update_project.execute({
        "project_id": "proj",
        "title": "Renamed",
        "notes": "fresh notes",
        "deadline": "2026-07-01",
        "tags": ["x", "y"],
        "area_id": "area-9",
    })

    assert len(captured_launches) == 1
    url = captured_launches[0]
    assert url.startswith("things:///update-project?")
    assert "id=proj" in url
    assert "auth-token=tok-xyz" in url
    assert "title=Renamed" in url
    assert "deadline=2026-07-01" in url
    assert "area-id=area-9" in url


async def test_execute_returns_changed_fields(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    state = {"row": _make_row()}

    real_launch = url_scheme.launch

    async def advancing(url: str) -> None:
        state["row"] = {**state["row"], "title": "New", "modified": "2026-05-18 11:00:00"}
        await real_launch(url)

    monkeypatch.setattr(things_repo, "get_project_row", lambda uuid: state["row"])
    monkeypatch.setattr(url_scheme, "launch", advancing)

    result = await update_project.execute({"project_id": "proj", "title": "New"})
    assert result["id"] == "proj"
    assert result["action_kind"] == "update_project"
    assert result["changed_fields"] == ["title"]


# ---------- undo ----------


async def test_undo_requires_auth(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await update_project.undo({
            "id": "e1",
            "action_kind": "update_project",
            "target_uuid": "proj",
            "before_state": {"inverse_fields": {"title": "old"}},
        })


async def test_undo_raises_without_before_state(with_auth):
    with pytest.raises(RuntimeError, match="no target_uuid or before_state"):
        await update_project.undo({"id": "e1", "action_kind": "update_project"})


async def test_undo_round_trip_restores_title(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    state = {
        "row": _make_row(title="New title", modified="2026-05-18 11:00:00")
    }

    real_launch = url_scheme.launch

    async def advancing(url: str) -> None:
        state["row"] = {
            **state["row"],
            "title": "Original project",
            "modified": "2026-05-18 12:00:00",
        }
        await real_launch(url)

    monkeypatch.setattr(things_repo, "get_project_row", lambda uuid: state["row"])
    monkeypatch.setattr(url_scheme, "launch", advancing)

    entry_id = undo_log.record(
        action_kind="update_project",
        target_uuid="proj",
        before_state={
            "full": _make_row(),
            "inverse_fields": {"title": "Original project"},
            "changed": ["title"],
        },
        after_state={"title": "New title"},
    )

    result = await update_project.undo(undo_log.get(entry_id))
    assert result["undone"] is True
    assert result["target_uuid"] == "proj"
    assert result["restored_fields"] == ["title"]

    url = captured_launches[0]
    assert "title=Original%20project" in url or "title=Original project" in url
    assert undo_log.get(entry_id) is None


async def test_undo_only_restores_changed_fields(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    """If the user manually edited notes between confirm and undo, undo
    must NOT clobber that — only the originally-changed title gets
    restored."""
    state = {"row": _make_row(title="New", notes="user's manual edit")}

    real_launch = url_scheme.launch

    async def advancing(url: str) -> None:
        state["row"] = {
            **state["row"],
            "title": "Original",
            "modified": "2026-05-18 12:00:00",
        }
        await real_launch(url)

    monkeypatch.setattr(things_repo, "get_project_row", lambda uuid: state["row"])
    monkeypatch.setattr(url_scheme, "launch", advancing)

    entry_id = undo_log.record(
        action_kind="update_project",
        target_uuid="proj",
        before_state={
            "full": _make_row(),
            "inverse_fields": {"title": "Original"},
            "changed": ["title"],
        },
        after_state=None,
    )

    await update_project.undo(undo_log.get(entry_id))

    url = captured_launches[0]
    assert "title=Original" in url
    assert "notes=" not in url


async def test_inverse_for_area_id_reads_area_field(with_auth, monkeypatch):
    """``area_id`` updates need to read from the things.py ``area`` field
    when computing the inverse — projects store the area UUID under
    ``area``, not ``area_id``."""
    state = {"row": _make_row(area="original-area")}

    real_launch = url_scheme.launch

    async def advancing(url: str) -> None:
        state["row"] = {
            **state["row"],
            "area": "new-area",
            "modified": "2026-05-18 12:00:00",
        }
        await real_launch(url)

    monkeypatch.setattr(things_repo, "get_project_row", lambda uuid: state["row"])
    monkeypatch.setattr(url_scheme, "launch", advancing)
    monkeypatch.setattr(config, "WRITE_POLL_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(config, "WRITE_POLL_INTERVAL_SECONDS", 0.01)

    result = await update_project.execute({
        "project_id": "proj", "area_id": "new-area",
    })

    full = undo_log.get(result["undo_id"])
    assert full["before_state"]["inverse_fields"]["area_id"] == "original-area"


# ---------- preview ----------


def test_make_preview_simple():
    s = update_project.make_preview({"project_id": "p", "title": "New"})
    assert "p" in s
    assert "title=" in s


def test_make_preview_renders_clear_actions():
    s = update_project.make_preview({
        "project_id": "p", "notes": "", "tags": [], "area_id": "",
    })
    assert "notes=(cleared)" in s
    assert "tags=(cleared)" in s
    assert "area_id=(cleared)" in s


def test_make_preview_with_no_fields():
    s = update_project.make_preview({"project_id": "p"})
    assert "(no fields)" in s
