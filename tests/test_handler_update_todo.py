"""Unit tests for the ``update_todo`` handler.

Pattern-setter handler — these tests pin the contract every later non-add
handler (move, delete, project edits, bulk variants) will reuse:

* before_state snapshot captured pre-launch (with tags via ``get_todo``)
* inverse_fields computed for only the fields the proposal changed
* undo restores those fields exactly, leaving other concurrent edits alone
* missing-todo / missing-auth raise actionable errors

URL launcher and ``things_repo`` are mocked; no Things app needed.
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import things_repo, url_scheme
from things_mcp.services.handlers import update_todo
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
    uuid: str = "abc",
    title: str = "Original title",
    notes: str = "original notes",
    deadline: str | None = "2026-06-01",
    tags: list[str] | None = None,
    modified: str = "2026-05-18 10:00:00",
) -> dict:
    row = {
        "uuid": uuid,
        "type": "to-do",
        "title": title,
        "notes": notes,
        "status": "incomplete",
        "start": "Inbox",
        "deadline": deadline,
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
        await update_todo.execute({"todo_id": "abc", "title": "x"})


async def test_execute_raises_when_no_fields(with_auth, monkeypatch):
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: _make_row())
    with pytest.raises(ValueError, match="no fields to update"):
        await update_todo.execute({"todo_id": "abc"})


async def test_execute_raises_when_todo_missing(with_auth, monkeypatch):
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: None)
    with pytest.raises(ValueError, match="No to-do found"):
        await update_todo.execute({"todo_id": "ghost", "title": "x"})


async def test_execute_writes_undo_log_before_launch(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    """The hard rule: undo_log row exists at the moment of URL launch."""
    pre_launch_rows: list[dict] = []
    state = {"row": _make_row(modified="2026-05-18 10:00:00")}

    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: state["row"])

    real_launch = url_scheme.launch

    async def snapshotting_launch(url: str) -> None:
        pre_launch_rows.extend(undo_log.recent(limit=10))
        # Simulate Things processing the update — bump modified.
        state["row"] = _make_row(
            title="New title", modified="2026-05-18 10:00:05"
        )
        await real_launch(url)

    monkeypatch.setattr(url_scheme, "launch", snapshotting_launch)

    await update_todo.execute({"todo_id": "abc", "title": "New title"})

    assert len(pre_launch_rows) == 1
    summary = pre_launch_rows[0]
    assert summary["action_kind"] == "update_todo"
    assert summary["target_uuid"] == "abc"

    full = undo_log.get(summary["id"])
    assert full["before_state"]["full"]["title"] == "Original title"
    assert full["before_state"]["inverse_fields"]["title"] == "Original title"
    assert full["before_state"]["changed"] == ["title"]


async def test_execute_builds_url_for_each_field(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    state = {"row": _make_row(modified="2026-05-18 10:00:00")}

    real_launch = url_scheme.launch

    async def advancing_launch(url: str) -> None:
        state["row"] = {**state["row"], "modified": "2026-05-18 10:00:05"}
        await real_launch(url)

    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: state["row"])
    monkeypatch.setattr(url_scheme, "launch", advancing_launch)

    await update_todo.execute({
        "todo_id": "abc",
        "title": "New",
        "notes": "fresh notes",
        "deadline": "2026-07-01",
        "tags": ["x", "y"],
    })

    assert len(captured_launches) == 1
    url = captured_launches[0]
    assert url.startswith("things:///update?")
    assert "id=abc" in url
    assert "auth-token=tok-xyz" in url
    assert "title=New" in url
    assert "deadline=2026-07-01" in url
    assert "tags=x%2Cy" in url or "tags=x,y" in url


async def test_execute_clears_tags_with_empty_list(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    state = {"row": _make_row(tags=["old"])}

    real_launch = url_scheme.launch

    async def advancing_launch(url: str) -> None:
        state["row"] = {**state["row"], "modified": "2026-05-18 11:00:00", "tags": []}
        await real_launch(url)

    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: state["row"])
    monkeypatch.setattr(url_scheme, "launch", advancing_launch)

    await update_todo.execute({"todo_id": "abc", "tags": []})

    url = captured_launches[0]
    # tags= (empty value) clears all tags in Things URL scheme.
    assert "tags=" in url


async def test_execute_returns_undo_id_and_changed_fields(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    state = {"row": _make_row()}

    real_launch = url_scheme.launch

    async def advancing(url: str) -> None:
        state["row"] = {**state["row"], "title": "New", "modified": "2026-05-18 11:00:00"}
        await real_launch(url)

    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: state["row"])
    monkeypatch.setattr(url_scheme, "launch", advancing)

    result = await update_todo.execute({"todo_id": "abc", "title": "New"})
    assert result["id"] == "abc"
    assert result["action_kind"] == "update_todo"
    assert result["changed_fields"] == ["title"]
    assert "undo_id" in result


async def test_execute_no_op_when_modified_doesnt_advance(
    with_auth, captured_launches, monkeypatch
):
    """Setting a field to its existing value won't advance ``modified``;
    we should return gracefully rather than time out (the agent can
    decide if it cares)."""
    monkeypatch.setattr(config, "WRITE_POLL_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(config, "WRITE_POLL_INTERVAL_SECONDS", 0.01)

    row = _make_row(title="Same", modified="2026-05-18 10:00:00")
    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: row)

    result = await update_todo.execute({"todo_id": "abc", "title": "Same"})
    assert result["id"] == "abc"
    # undo_log row still recorded for forensics
    assert undo_log.get(result["undo_id"]) is not None


# ---------- undo ----------


async def test_undo_requires_auth(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
    with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
        await update_todo.undo({
            "id": "e1",
            "action_kind": "update_todo",
            "target_uuid": "abc",
            "before_state": {"inverse_fields": {"title": "old"}},
        })


async def test_undo_raises_without_before_state(with_auth):
    with pytest.raises(RuntimeError, match="no target_uuid or before_state"):
        await update_todo.undo({"id": "e1", "action_kind": "update_todo"})


async def test_undo_round_trip_restores_title(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    """Confirm → undo restores the original title via a single update URL."""
    state = {
        "row": _make_row(title="New title", modified="2026-05-18 11:00:00")
    }

    real_launch = url_scheme.launch

    async def advancing(url: str) -> None:
        state["row"] = {
            **state["row"],
            "title": "Original title",
            "modified": "2026-05-18 12:00:00",
        }
        await real_launch(url)

    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: state["row"])
    monkeypatch.setattr(url_scheme, "launch", advancing)

    entry_id = undo_log.record(
        action_kind="update_todo",
        target_uuid="abc",
        before_state={
            "full": _make_row(),
            "inverse_fields": {"title": "Original title"},
            "changed": ["title"],
        },
        after_state={"title": "New title"},
    )

    result = await update_todo.undo(undo_log.get(entry_id))
    assert result["undone"] is True
    assert result["target_uuid"] == "abc"
    assert result["restored_fields"] == ["title"]

    url = captured_launches[0]
    assert "title=Original%20title" in url or "title=Original title" in url
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

    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: state["row"])
    monkeypatch.setattr(url_scheme, "launch", advancing)

    entry_id = undo_log.record(
        action_kind="update_todo",
        target_uuid="abc",
        before_state={
            "full": _make_row(),
            "inverse_fields": {"title": "Original"},  # only title was changed
            "changed": ["title"],
        },
        after_state=None,
    )

    await update_todo.undo(undo_log.get(entry_id))

    url = captured_launches[0]
    assert "title=Original" in url
    assert "notes=" not in url  # notes was not in the original change set


async def test_undo_round_trip_restores_tags(
    with_auth, fast_polling, captured_launches, monkeypatch
):
    state = {"row": _make_row(tags=[])}

    real_launch = url_scheme.launch

    async def advancing(url: str) -> None:
        state["row"] = {
            **state["row"],
            "tags": ["original"],
            "modified": "2026-05-18 12:00:00",
        }
        await real_launch(url)

    monkeypatch.setattr(things_repo, "get_todo", lambda uuid: state["row"])
    monkeypatch.setattr(url_scheme, "launch", advancing)

    entry_id = undo_log.record(
        action_kind="update_todo",
        target_uuid="abc",
        before_state={
            "full": _make_row(tags=["original"]),
            "inverse_fields": {"tags": ["original"]},
            "changed": ["tags"],
        },
        after_state=None,
    )

    result = await update_todo.undo(undo_log.get(entry_id))
    assert result["undone"] is True

    url = captured_launches[0]
    assert "tags=original" in url


# ---------- preview ----------


def test_make_preview_simple():
    s = update_todo.make_preview({"todo_id": "abc", "title": "New"})
    assert "abc" in s
    assert "title=" in s


def test_make_preview_renders_clear_actions():
    s = update_todo.make_preview({
        "todo_id": "abc", "notes": "", "tags": [],
    })
    assert "notes=(cleared)" in s
    assert "tags=(cleared)" in s


def test_make_preview_with_no_fields():
    s = update_todo.make_preview({"todo_id": "abc"})
    assert "(no fields)" in s
