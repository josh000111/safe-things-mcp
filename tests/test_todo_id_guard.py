"""Every tool that takes a to-do id must refuse a project / native-heading id.

``things.tasks(uuid)`` ignores ``type=``, so ``get_todo(<project uuid>)`` returns the
project row; ``delete_todo`` would then trash the whole project (undo cannot restore
it). The guard lives in ``ref_checks`` and is enforced at propose time AND in
``execute`` for every to-do-id tool. Bulk tools refuse the whole batch (naming every
offending id) before any mutation or undo_log write.

Everything is mocked; nothing touches real Things data.
"""
from __future__ import annotations

import pytest

from safe_things_mcp import config
from safe_things_mcp.services import ref_checks, things_repo
from safe_things_mcp.services.handlers import (
    add_project, append_checklist, apply_ai_tags, bulk_complete, bulk_delete,
    bulk_delete_todo, bulk_move, bulk_update, cancel_todo, cleanup_ai_tags,
    complete_todo, delete_todo, move_todo, move_under_heading, prepend_checklist,
    reorder_todos, replace_checklist, update_todo,
)
from safe_things_mcp.state import pending, sort_session, undo_log
from safe_things_mcp.tools import propose

from .test_preview_names import HDG, NATIVE, PROJ, PROJ_B, T1, T2, T3, repo  # noqa: F401
from .test_preview_safety_fixes import world  # noqa: F401  (fixture; needs ``repo``)

pytestmark = pytest.mark.usefixtures("isolated_state_db")

BAD = [PROJ, NATIVE]  # a project and a native heading: both must be refused


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_APPLESCRIPT", True)
    monkeypatch.setattr(things_repo, "get_tag_names", lambda: set())
    monkeypatch.setattr(sort_session, "active", lambda: None)


def _mutations(world):
    return [c for c in world.commands]


def _assert_untouched(world):
    assert _mutations(world) == [], "refused call must not issue any URL/AppleScript command"
    assert undo_log.recent(limit=50) == [], "refused call must not write undo_log"


# ---------- ref_checks unit behaviour ----------


def test_check_todo_accepts_plain_todo_and_dummy_heading(repo):
    assert ref_checks.check_todo(T1)["uuid"] == T1
    # Deliberate: dummy headings are type == "to-do" rows with no children.
    assert ref_checks.check_todo(HDG)["title"] == "__DESIGN__"
    assert ref_checks.check_todo("GHOST") is None  # unknown -> None; callers say "not found"


@pytest.mark.parametrize("uuid, kind", [(PROJ, "project"), (NATIVE, "heading")])
def test_check_todo_refuses_containers(repo, uuid, kind):
    with pytest.raises(ValueError, match=f"'{uuid}' is a {kind}, not a to-do"):
        ref_checks.check_todo(uuid)


def test_check_todo_refuses_area_and_other_row_types():
    for kind in ("area", "tag", "checklist-item"):
        with pytest.raises(ValueError, match=f"is a {kind}, not a to-do"):
            ref_checks.require_todo("X", {"uuid": "X", "type": kind})


def test_check_todos_names_every_offender(repo):
    with pytest.raises(ValueError) as e:
        ref_checks.check_todos([T1, PROJ, T2, NATIVE])
    msg = str(e.value)
    assert f"'{PROJ}' is a project" in msg and f"'{NATIVE}' is a heading" in msg
    assert "whole batch" in msg and T1 not in msg


# ---------- single-id tools: refused at propose AND execute ----------

SINGLE = [
    ("delete_todo", lambda x: propose.propose_delete_todo(x),
     lambda x: delete_todo.execute({"todo_id": x})),
    ("cancel_todo", lambda x: propose.propose_cancel_todo(x),
     lambda x: cancel_todo.execute({"todo_id": x})),
    ("update_todo", lambda x: propose.propose_update_todo(x, title="n"),
     lambda x: update_todo.execute({"todo_id": x, "title": "n"})),
    ("move_todo", lambda x: propose.propose_move_todo(x, "today"),
     lambda x: move_todo.execute({"todo_id": x, "target": "today"})),
    ("append_checklist", lambda x: propose.propose_append_checklist_items(x, ["a"]),
     lambda x: append_checklist.execute({"todo_id": x, "items": ["a"]})),
    ("prepend_checklist", lambda x: propose.propose_prepend_checklist_items(x, ["a"]),
     lambda x: prepend_checklist.execute({"todo_id": x, "items": ["a"]})),
    ("replace_checklist", lambda x: propose.propose_replace_checklist(x, ["a"]),
     lambda x: replace_checklist.execute({"todo_id": x, "items": ["a"]})),
    # complete_todo is a direct tool (no propose step): execute is the only gate.
    ("complete_todo", None, lambda x: complete_todo.execute({"todo_id": x})),
]


@pytest.mark.parametrize("bad", BAD)
@pytest.mark.parametrize("name, prop, ex", SINGLE, ids=[s[0] for s in SINGLE])
async def test_single_todo_tool_refuses_container_ids(world, name, prop, ex, bad):
    if prop is not None:
        with pytest.raises(ValueError, match="not a to-do"):
            await prop(bad)
        assert pending.list_all() == []
    with pytest.raises(ValueError, match="not a to-do"):
        await ex(bad)
    _assert_untouched(world)


async def test_delete_todo_still_deletes_real_todo_and_dummy_heading(world):
    for target in (T3, HDG):
        r = await propose.propose_delete_todo(target)
        assert "Delete to-do" in r["preview"]
    out = await delete_todo.execute({"todo_id": T3})
    assert out["id"] == T3
    assert any("delete (to do id" in c[1] for c in world.commands)


# ---------- bulk tools: whole batch refused, nothing mutated ----------

BULK = [
    ("bulk_complete", lambda ids: propose.propose_bulk_complete(ids),
     lambda ids: bulk_complete.execute({"todo_ids": ids})),
    ("bulk_cancel", lambda ids: propose.propose_bulk_cancel(ids),
     lambda ids: bulk_delete.execute({"todo_ids": ids})),
    ("bulk_delete_todo", lambda ids: propose.propose_bulk_delete_todo(ids),
     lambda ids: bulk_delete_todo.execute({"todo_ids": ids})),
    ("bulk_move", lambda ids: propose.propose_bulk_move(ids, "today"),
     lambda ids: bulk_move.execute({"todo_ids": ids, "target": "today"})),
    ("bulk_update", lambda ids: propose.propose_bulk_update(ids, title="n"),
     lambda ids: bulk_update.execute({"todo_ids": ids, "title": "n"})),
    ("move_under_heading", lambda ids: propose.propose_move_under_ai_heading(ids, PROJ_B),
     lambda ids: move_under_heading.execute({"todo_ids": ids, "project_id": PROJ_B})),
    ("apply_ai_tags",
     lambda ids: propose.propose_apply_ai_tags([{"todo_uuid": u, "add_tags": ["*A*"]} for u in ids]),
     lambda ids: apply_ai_tags.execute(
         {"items": [{"todo_uuid": u, "add_tags": ["*A*"]} for u in ids]})),
    ("cleanup_ai_tags", lambda ids: propose.propose_cleanup_ai_tags(ids),
     lambda ids: cleanup_ai_tags.execute({"todo_uuids": ids})),
    ("add_project_members",
     lambda ids: propose.propose_add_project("New", member_todo_ids=ids),
     lambda ids: add_project.execute({"title": "New", "member_todo_ids": ids})),
]


@pytest.mark.parametrize("name, prop, ex", BULK, ids=[b[0] for b in BULK])
async def test_bulk_tool_refuses_whole_batch_naming_offenders(world, name, prop, ex):
    ids = [T1, PROJ, T2, NATIVE]
    for call in (prop, ex):
        with pytest.raises(ValueError) as e:
            await call(ids)
        msg = str(e.value)
        assert f"'{PROJ}' is a project, not a to-do" in msg
        assert f"'{NATIVE}' is a heading, not a to-do" in msg
        assert "whole batch" in msg
    assert pending.list_all() == []
    _assert_untouched(world)


async def test_refused_apply_and_bulk_move_leave_sort_session_untouched(world, monkeypatch):
    began, registered = [], []
    monkeypatch.setattr(sort_session, "begin", lambda g=None: began.append(g) or "g1")
    monkeypatch.setattr(sort_session, "register_tagged", lambda ids: registered.extend(ids))
    with pytest.raises(ValueError, match="not a to-do"):
        await propose.propose_apply_ai_tags([{"todo_uuid": PROJ, "add_tags": ["*A*"]}])
    with pytest.raises(ValueError, match="not a to-do"):
        await propose.propose_bulk_move([PROJ], "today")
    assert began == [] and registered == []


# ---------- reorder_todos: NO to-do type guard ----------
# Someday/Anytime legitimately contain projects; reorder only changes positions and
# cannot trash, complete or retag anything, so a project id is a valid member there.


async def test_reorder_accepts_project_id_in_list_container_at_propose_and_execute(world, monkeypatch):
    monkeypatch.setattr(things_repo, "get_container_todo_uuids", lambda t, c: [T1, T2, PROJ])
    queued = []

    async def fake_enqueue(*, kind, payload, preview):
        queued.append(payload)
        return {"queued": True}

    monkeypatch.setattr(propose, "_enqueue_and_maybe_auto_confirm", fake_enqueue)
    await propose.propose_reorder_todos("someday", [PROJ, T1])
    assert queued and queued[0]["master_order"] == [PROJ, T2, T1]

    result = await reorder_todos.execute({
        "container_type": "list", "container_id": "Someday",
        "master_order": [PROJ, T2, T1], "original_order": [T1, T2, PROJ],
    })
    assert result["new_order"] == [PROJ, T2, T1]
    assert any(k == "as" and "reorder to dos in list" in c for k, c in world.commands)


async def test_reorder_project_container_still_rejects_non_member_ids(world, monkeypatch):
    # Project containers keep only type=="to-do" rows, so a project / native heading
    # id is not a member and build_master_order refuses it at propose time.
    monkeypatch.setattr(things_repo, "get_container_todo_uuids", lambda t, c: [T1, T2])
    monkeypatch.setattr(things_repo, "project", lambda u: None)
    with pytest.raises(ValueError, match="not found in current container"):
        await propose.propose_reorder_todos(PROJ_B, [PROJ, T1])
    assert pending.list_all() == []
    _assert_untouched(world)
