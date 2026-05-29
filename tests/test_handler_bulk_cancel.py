"""Unit tests for the ``bulk_cancel`` handler (bulk_delete.py, KIND=bulk_cancel).

Pins the V2 acceptance gate contract:
* KIND constant is "bulk_cancel"
* in NEVER_BYPASS_KINDS
* per-item snapshot in ONE undo_log row, sequential URL launches
* undo() restores the whole batch

URL launcher and ``things_repo`` are mocked — no Things app required.
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import things_repo, url_scheme
from things_mcp.services.handlers import bulk_delete
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


def _row(uuid: str, *, status: str = "incomplete", title: str | None = None) -> dict:
    return {
        "uuid": uuid,
        "type": "to-do",
        "title": title or f"task-{uuid}",
        "status": status,
        "modified": "2026-05-29 10:00:00",
    }


# ---------- KIND and NEVER_BYPASS_KINDS ----------


def test_kind_constant():
    assert bulk_delete.KIND == "bulk_cancel"


def test_kind_in_never_bypass_kinds():
    assert "bulk_cancel" in config.NEVER_BYPASS_KINDS


# ---------- execute — input validation ----------


async def test_execute_raises_on_empty_ids(with_auth):
    with pytest.raises(ValueError, match="non-empty"):
        await bulk_delete.execute({"todo_ids": []})


async def test_execute_raises_on_missing_todo(with_auth, monkeypatch):
    monkeypatch.setattr(things_repo, "get_todo", lambda uid: None)
    with pytest.raises(ValueError, match="No to-do found"):
        await bulk_delete.execute({"todo_ids": ["missing-id"]})


async def test_execute_raises_on_already_canceled_todo(with_auth, monkeypatch):
    rows = {"a": _row("a"), "b": _row("b", status="canceled")}
    monkeypatch.setattr(things_repo, "get_todo", lambda uid: rows.get(uid))
    with pytest.raises(ValueError, match="already status"):
        await bulk_delete.execute({"todo_ids": ["a", "b"]})


async def test_execute_requires_auth_token(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await bulk_delete.execute({"todo_ids": ["a"]})


# ---------- execute — undo_log written BEFORE mutation ----------


async def test_execute_writes_undo_log_before_mutation(with_auth, monkeypatch):
    """undo_log row must exist before the first URL launch."""
    rows = {"a": _row("a"), "b": _row("b")}
    monkeypatch.setattr(things_repo, "get_todo", lambda uid: rows.get(uid))

    pre_launch_rows: list[dict] = []
    real_launch = url_scheme.launch

    async def snapshotting_launch(url: str) -> None:
        pre_launch_rows.extend(undo_log.recent(limit=10))
        await real_launch(url)

    monkeypatch.setattr(url_scheme, "launch", snapshotting_launch)

    await bulk_delete.execute({"todo_ids": ["a", "b"]})

    # The snapshot was taken on the FIRST launch — row already exists.
    assert any(r["action_kind"] == "bulk_cancel" for r in pre_launch_rows)


# ---------- execute — URL shape ----------


async def test_execute_cancels_all_todos(with_auth, monkeypatch, captured_launches):
    rows = {"a": _row("a"), "b": _row("b")}
    monkeypatch.setattr(things_repo, "get_todo", lambda uid: rows.get(uid))

    result = await bulk_delete.execute({"todo_ids": ["a", "b"]})
    assert result["count"] == 2
    assert len(captured_launches) == 2
    for url in captured_launches:
        assert "canceled=true" in url


# ---------- undo ----------


async def test_undo_restores_all_todos(with_auth, monkeypatch, captured_launches):
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

    result = await bulk_delete.undo(undo_log.get(entry_id))
    assert result["undone"] is True
    assert result["count"] == 2
    assert len(captured_launches) == 2
    for url in captured_launches:
        assert "canceled=false" in url


# ---------- preview ----------


def test_make_preview_shows_count():
    preview = bulk_delete.make_preview({"todo_ids": ["a", "b", "c"]})
    assert "3" in preview
    assert "cancel" in preview.lower()
