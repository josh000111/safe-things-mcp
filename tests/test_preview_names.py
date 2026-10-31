"""Propose-time previews must show names, not bare UUIDs.

Covers ``services/preview_names`` (lookups + rendering), every handler's
``make_preview`` with enriched / not-found / legacy payloads, and the
``propose_*`` tools end to end with ``things_repo`` mocked.
"""
from __future__ import annotations

import json

import pytest

from safe_things_mcp import config
from safe_things_mcp.services import preview_names as pn
from safe_things_mcp.services import things_repo
from safe_things_mcp.services.handlers import (
    add_heading, add_project, add_todo, append_checklist, apply_ai_tags,
    bulk_add_todo, bulk_complete, bulk_delete, bulk_delete_heading,
    bulk_delete_todo, bulk_move, bulk_update, cancel_project, cancel_todo,
    cleanup_ai_tags, complete_todo, delete_heading, delete_project,
    delete_todo, move_todo, move_under_heading, prepend_checklist,
    reorder_todos, replace_checklist, update_heading, update_project,
    update_todo,
)
from safe_things_mcp.state import pending, sort_session
from safe_things_mcp.tools import propose

pytestmark = pytest.mark.usefixtures("isolated_state_db")

T1, T2, T3 = "TODO-1", "TODO-2", "TODO-3"
PROJ, AREA, HDG = "PROJ-1", "AREA-1", "HDG-1"
PROJ_B, HDG_B, NATIVE = "PROJ-B", "HDG-B", "NATIVE-1"


# ---------- fakes ----------


@pytest.fixture
def repo(monkeypatch):
    """Mock things_repo faithfully to things.py: one project (+ a second one),
    one area, three to-dos, dummy headings in each project, one native heading.

    Like the real library, lookups by UUID return a row of ANY type (the
    ``type=`` argument is ignored) and unknown UUIDs raise ValueError.
    """
    rows = {
        T1: {"uuid": T1, "type": "to-do", "title": "Buy milk", "project": PROJ},
        T2: {"uuid": T2, "type": "to-do", "title": "Call mum", "project": PROJ},
        T3: {"uuid": T3, "type": "to-do", "title": "File taxes"},
        HDG: {"uuid": HDG, "type": "to-do", "title": "__DESIGN__", "project": PROJ, "status": "incomplete"},
        HDG_B: {"uuid": HDG_B, "type": "to-do", "title": "__OTHER__", "project": PROJ_B, "status": "incomplete"},
        NATIVE: {"uuid": NATIVE, "type": "heading", "title": "Native", "project": PROJ},
        PROJ: {
            "uuid": PROJ, "type": "project", "title": "Home Admin",
            "items": [
                {"uuid": HDG, "type": "to-do", "title": "__DESIGN__"},
                {"uuid": NATIVE, "type": "heading", "title": "Native"},
                {"uuid": T1, "type": "to-do", "title": "Buy milk"},
                {"uuid": T2, "type": "to-do", "title": "Call mum"},
            ],
        },
        PROJ_B: {
            "uuid": PROJ_B, "type": "project", "title": "Other Project",
            "items": [{"uuid": HDG_B, "type": "to-do", "title": "__OTHER__"}],
        },
    }

    def by_uuid(u):
        if u not in rows:
            raise ValueError(f"No such task uuid found: {u!r}")
        return rows[u]

    monkeypatch.setattr(things_repo, "todo", lambda u: rows.get(u))
    monkeypatch.setattr(things_repo, "get_todo", lambda u: rows.get(u))
    monkeypatch.setattr(things_repo, "project", by_uuid)
    monkeypatch.setattr(things_repo, "get_project_row", by_uuid)
    monkeypatch.setattr(things_repo, "areas", lambda **kw: [{"uuid": AREA, "title": "Personal"}])
    monkeypatch.setattr(things_repo, "get_checklist_items",
                        lambda u: [{"title": "old a"}, {"title": "old b"}])
    monkeypatch.setattr(things_repo, "inbox", lambda: [rows[T1], rows[T2]])
    monkeypatch.setattr(config, "ALLOW_APPLESCRIPT", True)
    monkeypatch.setattr(config, "AUTO_CONFIRM", False)
    monkeypatch.setattr(sort_session, "active", lambda: None)
    return rows


def _stored_payload(result: dict) -> dict:
    row = pending.get(result["action_id"])
    return row["payload"]


# ---------- preview_names helpers ----------


def test_lookups_resolve_names(repo):
    assert pn.todo_title(T1) == "Buy milk"
    assert pn.project_title(PROJ) == "Home Admin"
    assert pn.area_title(AREA) == "Personal"
    assert pn.destination_title(AREA) == "Personal"  # falls through project -> area
    assert pn.destination_title(PROJ) == "Home Admin"


def test_unknown_uuid_is_none_not_an_error(repo):
    assert pn.todo_title("GHOST") is None
    assert pn.project_title("GHOST") is None
    assert pn.area_title("GHOST") is None
    assert pn.destination_title("GHOST") is None


def test_unreadable_db_propagates_instead_of_not_found(monkeypatch):
    """DB unreadable is NOT 'not found': it must surface the actionable guidance."""
    def blocked(*a, **k):
        raise config.ThingsDBAccessError("macOS is blocking access to the Things database")

    for fn in ("todo", "project", "get_project_row", "areas", "get_todo"):
        monkeypatch.setattr(things_repo, fn, blocked)
    for call in (pn.todo_title, pn.project_title, pn.area_title, pn.destination_title,
                 pn.for_todo, pn.for_project, pn.for_area):
        with pytest.raises(config.ThingsDBAccessError, match="blocking access"):
            call("x")
    with pytest.raises(config.ThingsDBAccessError):
        pn.for_todos(["x"])
    with pytest.raises(config.ThingsDBAccessError):
        pn.for_heading("p", "h")


def test_for_destination_skips_keywords(repo):
    assert pn.for_destination("today") == {}
    assert pn.for_destination("Inbox") == {}
    assert pn.for_destination(PROJ) == {"destination_title": "Home Admin"}
    assert pn.for_destination("GHOST") == {"destination_title": None}


def test_fmt_three_states():
    assert pn.fmt("U", {"t": "Name"}, "t") == "'Name' (U)"
    assert pn.fmt("U", {"t": None}, "t") == "U (not found)"
    assert pn.fmt("U", {}, "t") == "U"  # legacy payload


def test_item_lines_caps_at_20():
    out = pn.item_lines([f"'t{i}'" for i in range(25)])
    assert out.count("\n  - ") == 20
    assert out.endswith("…and 5 more")
    assert pn.item_lines([]) == ""


def test_payload_values_are_json_serializable(repo):
    p = {}
    p.update(pn.for_todos([T1, "GHOST"]))
    p.update(pn.for_headings(PROJ, ["Design"]))
    p.update(pn.for_destination(PROJ))
    json.dumps(p)


# ---------- handler make_preview: enriched payloads ----------


@pytest.mark.parametrize(
    "mod, payload, expected",
    [
        (delete_todo, {"todo_id": T1, "todo_title": "Buy milk"}, "Delete to-do 'Buy milk' (TODO-1)"),
        (cancel_todo, {"todo_id": T1, "todo_title": "Buy milk"}, "Mark to-do 'Buy milk' (TODO-1) as canceled"),
        (complete_todo, {"todo_id": T1, "todo_title": "Buy milk"}, "Mark to-do 'Buy milk' (TODO-1) as completed"),
        (update_todo, {"todo_id": T1, "todo_title": "Buy milk", "title": "New"}, "Update to-do 'Buy milk' (TODO-1): title='New'"),
        (move_todo, {"todo_id": T1, "todo_title": "Buy milk", "target": PROJ, "destination_title": "Home Admin"},
         "Move to-do 'Buy milk' (TODO-1) to 'Home Admin' (PROJ-1)"),
        (move_todo, {"todo_id": T1, "todo_title": "Buy milk", "target": "today"},
         "Move to-do 'Buy milk' (TODO-1) to 'today'"),
        (cancel_project, {"project_id": PROJ, "project_title": "Home Admin"}, "Mark project 'Home Admin' (PROJ-1) as canceled"),
        (delete_project, {"project_id": PROJ, "project_title": "Home Admin"}, "'Home Admin' (PROJ-1)"),
        (update_project, {"project_id": PROJ, "project_title": "Home Admin", "area_id": AREA, "area_title": "Personal"},
         "Update project 'Home Admin' (PROJ-1): area_id='Personal' (AREA-1)"),
        (add_todo, {"title": "X", "list_id": PROJ, "destination_title": "Home Admin"},
         "Add to-do 'X' to 'Home Admin' (PROJ-1)"),
        (add_project, {"title": "P", "area_id": AREA, "area_title": "Personal"}, "area_id='Personal' (AREA-1)"),
        (append_checklist, {"todo_id": T1, "todo_title": "Buy milk", "items": ["a", "b"]},
         "Append 2 checklist item(s) to to-do 'Buy milk' (TODO-1)\n  - 'a'\n  - 'b'"),
        (prepend_checklist, {"todo_id": T1, "todo_title": "Buy milk", "items": ["a"]},
         "Prepend 1 checklist item(s) to to-do 'Buy milk' (TODO-1)\n  - 'a'"),
        (update_heading, {"project_id": PROJ, "project_title": "Home Admin", "heading_id_or_name": "Design",
                          "heading_uuid": HDG, "heading_title": "__DESIGN__", "new_name": "Build"},
         "Rename heading '__DESIGN__' (HDG-1) to '__BUILD__' in project 'Home Admin' (PROJ-1)"),
        (delete_heading, {"project_id": PROJ, "project_title": "Home Admin", "heading_id_or_name": HDG,
                          "heading_uuid": HDG, "heading_title": "__DESIGN__"},
         "Soft-delete dummy heading '__DESIGN__' (HDG-1) from project 'Home Admin' (PROJ-1)"),
        (move_under_heading, {"todo_ids": [T1], "project_id": PROJ, "project_title": "Home Admin",
                              "todo_titles": {T1: "Buy milk"}},
         "into project 'Home Admin' (PROJ-1)"),
    ],
)
def test_enriched_previews(mod, payload, expected):
    assert expected in mod.make_preview(payload)


def test_replace_checklist_preview_shows_new_and_removed_items():
    p = replace_checklist.make_preview({
        "todo_id": T1, "todo_title": "Buy milk", "items": ["n1"],
        "existing_checklist": ["old a", "old b"],
    })
    assert "Replace checklist of to-do 'Buy milk' (TODO-1) with 1 item(s)" in p
    assert "- 'n1'" in p
    assert "Existing 2 item(s) that will be removed" in p
    assert "- 'old a'" in p and "- 'old b'" in p


def test_reorder_preview_shows_container_and_todo_titles():
    p = reorder_todos.make_preview({
        "container_id": PROJ, "container_title": "Home Admin",
        "master_order": [T2, T1], "todo_titles": {T1: "Buy milk", T2: "Call mum"},
    })
    assert "in 'Home Admin' (PROJ-1)" in p
    assert p.index("'Call mum' (TODO-2)") < p.index("'Buy milk' (TODO-1)")


def test_bulk_previews_list_titles():
    titles = {T1: "Buy milk", T2: None}
    payload = {"todo_ids": [T1, T2], "todo_titles": titles}
    for mod in (bulk_complete, bulk_delete, bulk_delete_todo):
        p = mod.make_preview(payload)
        assert "  - 'Buy milk' (TODO-1)" in p
        assert "  - TODO-2 (not found)" in p
    p = bulk_update.make_preview({**payload, "title": "New"})
    assert "Bulk update 2 to-dos: title='New'" in p and "'Buy milk' (TODO-1)" in p
    p = bulk_move.make_preview({**payload, "target": PROJ, "destination_title": "Home Admin"})
    assert "to 'Home Admin' (PROJ-1)" in p and "'Buy milk' (TODO-1)" in p


def test_bulk_preview_caps_lines_at_20():
    ids = [f"T{i}" for i in range(25)]
    p = bulk_complete.make_preview({"todo_ids": ids, "todo_titles": {i: f"Task {i}" for i in ids}})
    assert p.count("\n  - ") == 20
    assert p.endswith("…and 5 more")
    assert "Bulk complete 25 to-dos" in p


def test_bulk_add_todo_preview_lists_titles_and_destination():
    p = bulk_add_todo.make_preview({
        "list_id": PROJ, "destination_title": "Home Admin",
        "items": [{"title": "a"}, {"title": "b"}],
    })
    assert "to 'Home Admin' (PROJ-1)" in p and "  - 'a'" in p and "  - 'b'" in p
    p = bulk_add_todo.make_preview({"list_id": "inbox", "items": [{"title": "a"}]})
    assert "to inbox" in p


def test_bulk_delete_heading_preview():
    p = bulk_delete_heading.make_preview({
        "project_id": PROJ, "project_title": "Home Admin",
        "heading_ids_or_names": ["Design", "nope"],
        "heading_items": [
            {"ref": "Design", "uuid": HDG, "title": "__DESIGN__"},
            {"ref": "nope", "uuid": None, "title": None},
        ],
    })
    assert "from project 'Home Admin' (PROJ-1)" in p
    assert "  - '__DESIGN__' (HDG-1)" in p
    assert "  - nope (not found)" in p


def test_apply_and_cleanup_previews():
    payload = {
        "items": [
            {"todo_uuid": T1, "add_tags": ["*Errand*"],
             "routing": {"dest_kind": "project", "dest_uuid": PROJ, "transient": True}},
            {"todo_uuid": T2, "add_tags": ["*Unclear*"], "routing": None},
        ],
        "todo_titles": {T1: "Buy milk", T2: "Call mum"},
        "destination_titles": {PROJ: "Home Admin"},
    }
    p = apply_ai_tags.make_preview(payload)
    assert "Apply AI tags to 2 to-do(s)" in p
    assert ("'Buy milk' (TODO-1): add *Errand* "
            "(suggested home: 'Home Admin' (PROJ-1); nothing moves yet)") in p
    assert "'Call mum' (TODO-2): add *Unclear*" in p and "suggested home" not in p.split("Call mum")[1]
    assert "does not move anything" in p and "→" not in p
    p = cleanup_ai_tags.make_preview({"todo_uuids": [T1], "todo_titles": {T1: "Buy milk"}})
    assert "'Buy milk' (TODO-1)" in p


def test_add_project_preview_lists_member_titles():
    p = add_project.make_preview({
        "title": "P", "member_todo_ids": [T1, T2],
        "todo_titles": {T1: "Buy milk", T2: "Call mum"},
    })
    assert "+ populate 2 tasks" in p and "'Buy milk' (TODO-1)" in p


# ---------- not found / legacy payloads ----------


@pytest.mark.parametrize(
    "mod, payload, expected",
    [
        (delete_todo, {"todo_id": "GHOST", "todo_title": None}, "Delete to-do GHOST (not found)"),
        (cancel_todo, {"todo_id": "GHOST", "todo_title": None}, "GHOST (not found)"),
        (delete_project, {"project_id": "GHOST", "project_title": None}, "GHOST (not found)"),
        (move_todo, {"todo_id": T1, "todo_title": "Buy milk", "target": "GHOST", "destination_title": None},
         "to GHOST (not found)"),
        (delete_heading, {"project_id": PROJ, "heading_id_or_name": "nope", "heading_title": None},
         "nope (not found)"),
    ],
)
def test_not_found_renders_without_raising(mod, payload, expected):
    assert expected in mod.make_preview(payload)


def test_legacy_payloads_without_name_keys_still_render():
    assert "TODO-1" in cancel_todo.make_preview({"todo_id": T1})
    assert "TODO-1" in update_todo.make_preview({"todo_id": T1, "title": "x"})
    assert "Bulk complete 2 to-dos" == bulk_complete.make_preview({"todo_ids": [T1, T2]})
    assert "Bulk move 1 to-do to 'today'" == bulk_move.make_preview({"todo_ids": [T1], "target": "today"})
    assert "PROJ-1" in update_heading.make_preview(
        {"project_id": PROJ, "heading_id_or_name": "Design", "new_name": "B"})
    assert "PROJ-1" in reorder_todos.make_preview(
        {"container_id": PROJ, "master_order": [T1]})
    # Older delete payloads kept the title only in the execute-time snapshot.
    assert "'Old' (TODO-1)" in delete_todo.make_preview({"todo_id": T1, "snapshot": {"title": "Old"}})
    assert "'Old' (PROJ-1)" in delete_project.make_preview({"project_id": PROJ, "snapshot": {"title": "Old"}})


def test_add_heading_preview_shows_project_title(repo):
    p = add_heading.make_preview({"project_id": PROJ, "name": "Design"})
    assert "'Home Admin' (PROJ-1)" in p


# ---------- propose_* tools end to end ----------


async def test_propose_delete_todo_shows_title_not_uuid_twice(repo):
    r = await propose.propose_delete_todo(T1)
    assert r["preview"].startswith("Delete to-do 'Buy milk' (TODO-1)")
    assert _stored_payload(r)["todo_title"] == "Buy milk"


async def test_propose_delete_todo_missing_item(repo):
    r = await propose.propose_delete_todo("GHOST")
    assert "GHOST (not found)" in r["preview"]


async def test_propose_fails_with_guidance_when_db_unreadable(monkeypatch):
    def blocked(*a, **k):
        raise config.ThingsDBAccessError("macOS is blocking access to the Things database")

    monkeypatch.setattr(things_repo, "todo", blocked)
    monkeypatch.setattr(config, "AUTO_CONFIRM", False)
    monkeypatch.setattr(config, "ALLOW_APPLESCRIPT", True)
    # Not "U1 (not found)": nothing may be staged on a destructive kind.
    with pytest.raises(config.ThingsDBAccessError, match="blocking access"):
        await propose.propose_cancel_todo("U1")
    with pytest.raises(config.ThingsDBAccessError, match="blocking access"):
        await propose.propose_delete_todo("U1")
    assert pending.list_all() == []


async def test_propose_single_item_tools(repo):
    r = await propose.propose_cancel_todo(T2)
    assert "'Call mum' (TODO-2)" in r["preview"]
    r = await propose.propose_update_todo(T1, title="Milk!")
    assert "Update to-do 'Buy milk' (TODO-1)" in r["preview"]
    # The new title stays under its original key; the current name is separate.
    stored = _stored_payload(r)
    assert stored["title"] == "Milk!" and stored["todo_title"] == "Buy milk"
    r = await propose.propose_move_todo(T1, PROJ)
    assert "to 'Home Admin' (PROJ-1)" in r["preview"]
    r = await propose.propose_move_todo(T1, AREA)
    assert "to 'Personal' (AREA-1)" in r["preview"]
    r = await propose.propose_move_todo(T1, "today")
    assert r["preview"].endswith("to 'today'")
    r = await propose.propose_add_todo("New", list_id=PROJ)
    assert "to 'Home Admin' (PROJ-1)" in r["preview"]
    r = await propose.propose_add_todo("New")
    assert "to inbox" in r["preview"]


async def test_propose_project_tools(repo):
    r = await propose.propose_cancel_project(PROJ)
    assert "'Home Admin' (PROJ-1)" in r["preview"]
    r = await propose.propose_delete_project(PROJ)
    assert "'Home Admin' (PROJ-1)" in r["preview"]
    r = await propose.propose_update_project(PROJ, area_id=AREA)
    assert "Update project 'Home Admin' (PROJ-1): area_id='Personal' (AREA-1)" in r["preview"]
    r = await propose.propose_add_project("New", area_id=AREA, member_todo_ids=[T1, T2, T3])
    assert "area_id='Personal' (AREA-1)" in r["preview"]
    assert "'File taxes' (TODO-3)" in r["preview"]


async def test_propose_bulk_tools(repo):
    for fn in (propose.propose_bulk_complete, propose.propose_bulk_cancel,
               propose.propose_bulk_delete_todo):
        r = await fn([T1, "GHOST"])
        assert "  - 'Buy milk' (TODO-1)" in r["preview"]
        assert "  - GHOST (not found)" in r["preview"]
    r = await propose.propose_bulk_update([T1, T2], title="X")
    assert "'Call mum' (TODO-2)" in r["preview"]
    r = await propose.propose_bulk_move([T1, T2], PROJ)
    assert "to 'Home Admin' (PROJ-1)" in r["preview"]
    assert "'Buy milk' (TODO-1)" in r["preview"]
    r = await propose.propose_bulk_add_todo(PROJ, [{"title": "a"}, {"title": "b"}])
    assert "to 'Home Admin' (PROJ-1)" in r["preview"] and "  - 'b'" in r["preview"]


async def test_propose_bulk_complete_caps_at_20(repo):
    r = await propose.propose_bulk_complete([f"U{i}" for i in range(23)])
    assert r["preview"].count("\n  - ") == 20
    assert r["preview"].endswith("…and 3 more")


async def test_propose_heading_tools(repo):
    r = await propose.propose_update_heading(PROJ, "Design", "Build")
    assert "'__DESIGN__' (HDG-1)" in r["preview"] and "'Home Admin' (PROJ-1)" in r["preview"]
    r = await propose.propose_delete_heading(PROJ, HDG)
    assert "'__DESIGN__' (HDG-1)" in r["preview"]
    r = await propose.propose_bulk_delete_heading(PROJ, ["Design", HDG])
    assert "  - '__DESIGN__' (HDG-1)" in r["preview"]
    r = await propose.propose_add_heading(PROJ, "Plan", after_todo_id=T1)
    assert "'Buy milk' (TODO-1)" in r["preview"]


async def test_propose_checklist_tools(repo):
    r = await propose.propose_append_checklist_items(T1, ["x"])
    assert "to-do 'Buy milk' (TODO-1)" in r["preview"] and "- 'x'" in r["preview"]
    r = await propose.propose_prepend_checklist_items(T1, ["x"])
    assert "to-do 'Buy milk' (TODO-1)" in r["preview"]
    r = await propose.propose_replace_checklist(T1, ["n"])
    assert "- 'n'" in r["preview"] and "- 'old a'" in r["preview"]


async def test_propose_reorder_project_and_builtin(repo):
    r = await propose.propose_reorder_todos(PROJ, [T2, T1])
    assert "in 'Home Admin' (PROJ-1)" in r["preview"]
    assert "'Call mum' (TODO-2)" in r["preview"]
    r = await propose.propose_reorder_todos("inbox", [T2, T1])
    assert "in 'Inbox'" in r["preview"] and "'Call mum' (TODO-2)" in r["preview"]


async def test_propose_ai_sort_tools(repo, monkeypatch):
    monkeypatch.setattr(things_repo, "tags", lambda include_items=False: [])
    r = await propose.propose_apply_ai_tags([
        {"todo_uuid": T1, "add_tags": ["*Errand*"],
         "routing": {"dest_kind": "project", "dest_uuid": PROJ, "transient": True}},
    ])
    assert ("'Buy milk' (TODO-1): add *Errand* "
            "(suggested home: 'Home Admin' (PROJ-1); nothing moves yet)") in r["preview"]
    json.dumps(_stored_payload(r))
    r = await propose.propose_move_under_ai_heading([T1, T2], PROJ)
    assert "into project 'Home Admin' (PROJ-1)" in r["preview"]
    assert "'Call mum' (TODO-2)" in r["preview"]
    r = await propose.propose_cleanup_ai_tags([T1])
    assert "'Buy milk' (TODO-1)" in r["preview"]


