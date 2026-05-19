"""Unit tests for the ``add_project`` handler.

Mirrors :mod:`test_handler_add_todo` — proves the V2 acceptance gate
for the project-add path:

* undo_log row written *before* URL-scheme launch (CLAUDE.md hard rule)
* UUID polled back via ``find_recent_project_by_title``
* undo soft-deletes via ``update-project?canceled=true&completed=true``
* missing auth token on undo raises actionable error
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import things_repo, url_scheme
from things_mcp.services.handlers import add_project
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


def _stub_project(uuid: str = "proj-1", title: str = "t") -> dict:
    return {
        "uuid": uuid,
        "type": "project",
        "title": title,
        "status": "incomplete",
        "created": "2026-05-19 03:00:00",
    }


# ---------- execute ----------


async def test_execute_writes_undo_log_before_mutation(
    fast_polling, captured_launches, monkeypatch
):
    """The undo_log row must be present at the moment of URL launch."""
    pre_launch_rows: list[dict] = []
    real_launch = url_scheme.launch

    async def snapshotting_launch(url: str) -> None:
        pre_launch_rows.extend(undo_log.recent(limit=10))
        await real_launch(url)

    monkeypatch.setattr(url_scheme, "launch", snapshotting_launch)
    monkeypatch.setattr(
        things_repo, "find_recent_project_by_title",
        lambda title, created_after: _stub_project(title=title),
    )

    await add_project.execute({"title": "Big launch"})

    assert len(pre_launch_rows) == 1
    assert pre_launch_rows[0]["action_kind"] == "add_project"
    assert pre_launch_rows[0]["target_uuid"] is None


async def test_execute_returns_id_and_patches_undo_log(
    fast_polling, captured_launches, monkeypatch
):
    monkeypatch.setattr(
        things_repo, "find_recent_project_by_title",
        lambda title, created_after: _stub_project(uuid="abc", title=title),
    )

    result = await add_project.execute({"title": "Hello project"})
    assert result["id"] == "abc"
    assert result["action_kind"] == "add_project"
    assert result["headings_count"] == 0

    entry = undo_log.get(result["undo_id"])
    assert entry["target_uuid"] == "abc"
    assert entry["after_state"]["uuid"] == "abc"


async def test_execute_plain_url_when_no_headings(
    fast_polling, captured_launches, monkeypatch
):
    monkeypatch.setattr(
        things_repo, "find_recent_project_by_title",
        lambda title, created_after: _stub_project(title=title),
    )

    await add_project.execute({
        "title": "Plain", "area_id": "area-1", "tags": ["work"],
    })
    assert len(captured_launches) == 1
    url = captured_launches[0]
    assert url.startswith("things:///add-project?")
    assert "title=Plain" in url
    assert "area-id=area-1" in url


async def test_execute_json_url_when_headings(
    fast_polling, captured_launches, monkeypatch
):
    monkeypatch.setattr(
        things_repo, "find_recent_project_by_title",
        lambda title, created_after: _stub_project(title=title),
    )

    result = await add_project.execute({
        "title": "Launch", "headings": ["Design", "Dev"],
    })
    assert result["headings_count"] == 2
    url = captured_launches[0]
    assert url.startswith("things:///json?data=")


async def test_execute_times_out_when_poll_finds_nothing(
    captured_launches, monkeypatch
):
    monkeypatch.setattr(config, "WRITE_POLL_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(config, "WRITE_POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(
        things_repo, "find_recent_project_by_title", lambda *a, **kw: None
    )

    with pytest.raises(RuntimeError, match="Timed out"):
        await add_project.execute({"title": "Ghost"})

    leftover = undo_log.recent(limit=5)
    assert len(leftover) == 1
    assert leftover[0]["target_uuid"] is None


# ---------- undo ----------


async def test_undo_requires_auth_token(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    entry = {"id": "e1", "action_kind": "add_project", "target_uuid": "abc"}
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await add_project.undo(entry)


async def test_undo_requires_target_uuid(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", "tok")
    entry = {"id": "e1", "action_kind": "add_project", "target_uuid": None}
    with pytest.raises(RuntimeError, match="no target_uuid"):
        await add_project.undo(entry)


async def test_undo_round_trip_marks_canceled_and_completed(
    fast_polling, captured_launches, monkeypatch
):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", "tok-xyz")

    entry_id = undo_log.record(
        action_kind="add_project",
        target_uuid="abc",
        before_state=None,
        after_state={"uuid": "abc", "status": "incomplete"},
    )

    monkeypatch.setattr(
        things_repo, "get",
        lambda uuid: {"uuid": uuid, "status": "completed"} if uuid == "abc" else None,
    )

    result = await add_project.undo(undo_log.get(entry_id))
    assert result["undone"] is True
    assert result["target_uuid"] == "abc"
    assert result["status"] == "completed"

    assert len(captured_launches) == 1
    url = captured_launches[0]
    assert url.startswith("things:///update-project?")
    assert "auth-token=tok-xyz" in url
    assert "completed=true" in url
    assert "canceled=true" in url
    assert "id=abc" in url

    assert undo_log.get(entry_id) is None


# ---------- preview ----------


def test_make_preview_simple():
    s = add_project.make_preview({"title": "Plan"})
    assert "Plan" in s


def test_make_preview_with_headings():
    s = add_project.make_preview({
        "title": "Launch", "headings": ["A", "B", "C"], "tags": ["work"],
    })
    assert "headings=[3 sections]" in s
    assert "tags=work" in s
