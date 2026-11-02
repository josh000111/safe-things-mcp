"""Titles-only previews: a found item renders as ``'Title'``; the ID (plus a
human hint) appears only when another non-trashed item of the same kind has the
exact same title. Legacy payloads (titles but no ``ambiguous`` key) keep the
old ``'Title' (uuid)`` form.

``things_repo`` is mocked; the live-uuid query is faked (its SQL is covered in
``test_live_uuids_repo.py``).
"""
from __future__ import annotations

import json

import pytest

from safe_things_mcp import config
from safe_things_mcp.services import preview_names as pn
from safe_things_mcp.services import things_repo
from safe_things_mcp.services.handlers import delete_todo, move_todo
from safe_things_mcp.state import pending, sort_session
from safe_things_mcp.tools import propose

pytestmark = pytest.mark.usefixtures("isolated_state_db")


@pytest.fixture
def world(monkeypatch):
    """Rows + a fake ``duplicate_titles`` that really counts same-title rows of
    the asked kind (so duplicates are declared simply by adding rows)."""
    rows: dict[str, dict] = {}
    calls: list[tuple] = []

    def add(uuid, title, type_="to-do", **kw):
        rows[uuid] = {"uuid": uuid, "type": type_, "title": title, "status": "incomplete", **kw}

    def live(kind, titles, project_uuid=None):
        """What the real query promises: live (non-trashed, non-template) rows
        grouped by title; headings include dummies nested under a native heading."""
        calls.append((kind, tuple(titles), project_uuid))
        out: dict[str, set] = {}
        for r in rows.values():
            if r["title"] not in titles or r.get("trashed") or r.get("template"):
                continue
            if kind == "to-do":
                ok = r["type"] == "to-do"
            elif kind == "destination":
                ok = r["type"] in ("project", "area")
            else:  # heading
                parent = rows.get(r.get("heading"), {}).get("project")
                ok = (r.get("project") == project_uuid or parent == project_uuid) and (
                    r["type"] == "heading" or r["title"].startswith("__"))
            if ok:
                out.setdefault(r["title"], set()).add(r["uuid"])
        return out

    def task_row(u):  # like things.py: areas are not in the task table
        r = rows.get(u)
        return None if r is None or r["type"] == "area" else r

    def by_uuid(u):
        if task_row(u) is None:
            raise ValueError(f"No such task uuid found: {u!r}")
        return rows[u]

    monkeypatch.setattr(things_repo, "live_uuids_by_title", live)
    monkeypatch.setattr(things_repo, "todo", task_row)
    monkeypatch.setattr(things_repo, "get_todo", task_row)
    monkeypatch.setattr(things_repo, "project", by_uuid)
    monkeypatch.setattr(things_repo, "get_project_row", by_uuid)
    monkeypatch.setattr(
        things_repo, "areas", lambda **kw: [r for r in rows.values() if r["type"] == "area"])
    monkeypatch.setattr(things_repo, "get_checklist_items", lambda u: [])
    monkeypatch.setattr(config, "ALLOW_APPLESCRIPT", True)
    monkeypatch.setattr(config, "AUTO_CONFIRM", False)
    monkeypatch.setattr(sort_session, "active", lambda: None)
    return type("W", (), {"rows": rows, "add": staticmethod(add), "calls": calls})


# ---------- rendering rule ----------


def test_label_rules():
    amb = {"U": "completed, in Home", "V": ""}
    p = {"ambiguous": amb}
    assert pn.label("X", "Plain", p) == "'Plain'"
    assert pn.label("U", "Dup", p) == "'Dup' (completed, in Home, ID U)"
    assert pn.label("V", "Dup", p) == "'Dup' (ID V)"
    assert pn.label("X", None, p) == "X (not found)"
    assert pn.label("X", "Old", {}) == "'Old' (X)"  # legacy


def test_fmt_helpers_share_the_rule():
    p = {"ambiguous": {"U": "in Inbox"}, "t": "Dup", "destination_title": "Dup",
         "heading_title": "__A__", "heading_uuid": "U"}
    assert pn.fmt("U", p, "t") == "'Dup' (in Inbox, ID U)"
    assert pn.fmt("Z", {}, "t") == "Z"  # no title key: bare uuid
    assert pn.fmt_destination("U", p) == "'Dup' (in Inbox, ID U)"
    assert pn.fmt_destination("today", p) == "'today'"
    assert pn.fmt_heading("ref", p) == "'__A__' (in Inbox, ID U)"
    assert pn.fmt_map("U", {"U": "Dup", "W": "Solo"}, p) == "'Dup' (in Inbox, ID U)"
    assert pn.fmt_map("W", {"U": "Dup", "W": "Solo"}, p) == "'Solo'"
    assert pn.fmt_map("W", {"W": None}, p) == "W (not found)"
    assert pn.fmt_map("Q", {"W": "Solo"}, p) == "Q"
    assert pn.todo_lines(["U", "W"], {**p, "todo_titles": {"U": "Dup", "W": "Solo"}}) == (
        "\n  - 'Dup' (in Inbox, ID U)\n  - 'Solo'")


def test_legacy_payload_with_titles_but_no_ambiguous_keeps_old_form():
    payload = {"todo_id": "T", "todo_title": "Buy milk"}
    assert delete_todo.make_preview(payload).startswith("Delete to-do 'Buy milk' (T) ")
    payload = {"todo_id": "T", "todo_title": "Buy milk", "target": "P", "destination_title": "Home"}
    assert "to-do 'Buy milk' (T) to 'Home' (P)" in move_todo.make_preview(payload)


def test_merge_unions_ambiguous_and_updates_the_rest():
    p = {"a": 1, "ambiguous": {"x": "h1"}}
    out = pn.merge(p, {"a": 2, "b": 3, "ambiguous": {"y": ""}})
    assert out is p
    assert p == {"a": 2, "b": 3, "ambiguous": {"x": "h1", "y": ""}}
    q = pn.merge({}, {"k": 1})
    assert q == {"k": 1}  # no ambiguous key invented
    assert pn.merge({}, {"ambiguous": {}}) == {"ambiguous": {}}


# ---------- to-do ----------


def test_unique_todo_is_title_only(world):
    world.add("T1", "Buy milk")
    assert pn.for_todo("T1") == {"todo_title": "Buy milk", "ambiguous": {}}


def test_ambiguous_todo_hints_cover_status_and_location(world):
    # Like real things.py: a to-do under a native heading has heading/heading_title
    # but no project_title; the heading's own row carries the project.
    world.add("P", "Home", "project")
    world.add("HD", "Bills", "heading", project="P", project_title="Home")
    world.add("A", "Pay rent", heading="HD", heading_title="Bills")
    world.add("B", "Pay rent", status="completed", project_title="Home")
    world.add("C", "Pay rent", status="canceled", area_title="Personal")
    world.add("D", "Pay rent", start="Inbox")
    world.add("E", "Pay rent", start="Anytime")
    world.add("F", "Pay rent", start="Someday")
    world.add("G", "Pay rent")  # nothing known: no location
    world.add("H", "Pay rent", status="completed")
    out = pn.for_todos(list("ABCDEFGH"))
    assert out["ambiguous"] == {
        "A": "in Home › Bills",
        "B": "completed, in Home",
        "C": "canceled, in Personal",
        "D": "in Inbox",
        "E": "in Anytime",
        "F": "in Someday",
        "G": "",
        "H": "completed",
    }
    json.dumps(out)
    p = {**out, "todo_id": "B", "todo_title": "Pay rent"}
    assert delete_todo.make_preview(p).startswith(
        "Delete to-do 'Pay rent' (completed, in Home, ID B) ")

def test_todo_ambiguity_ignores_trashed_twin(world):
    world.add("A", "Pay rent")
    world.add("B", "Pay rent", trashed=1)
    assert pn.for_todo("A")["ambiguous"] == {}


def test_bulk_preview_with_a_duplicate_pair(world):
    world.add("A", "Pay rent", project_title="Home")
    world.add("B", "Pay rent", status="completed", project_title="Home")
    world.add("C", "Solo")
    assert (pn.for_todos(["A", "B", "C", "GHOST"])["todo_titles"]
            == {"A": "Pay rent", "B": "Pay rent", "C": "Solo", "GHOST": None})
    # one query for the whole batch (titles deduped), not one per item
    assert [c[0] for c in world.calls] == ["to-do"]


async def test_propose_bulk_complete_lists_dup_pair_with_hints(world):
    world.add("A", "Pay rent", project_title="Home")
    world.add("B", "Pay rent", status="completed", project_title="Home")
    world.add("C", "Solo")
    r = await propose.propose_bulk_complete(["A", "B", "C", "GHOST"])
    assert r["preview"] == (
        "Bulk complete 4 to-dos\n"
        "  - 'Pay rent' (in Home, ID A)\n"
        "  - 'Pay rent' (completed, in Home, ID B)\n"
        "  - 'Solo'\n"
        "  - GHOST (not found)"
    )
    stored = pending.get(r["action_id"])["payload"]
    assert stored["ambiguous"] == {"A": "in Home", "B": "completed, in Home"}


async def test_propose_delete_todo_title_only(world):
    world.add("A", "Buy milk")
    r = await propose.propose_delete_todo("A")
    assert r["preview"].startswith("Delete to-do 'Buy milk' —")
    assert "A" not in r["preview"].split("—")[0].replace("Delete to-do 'Buy milk'", "")


async def test_propose_delete_todo_not_found(world):
    r = await propose.propose_delete_todo("GHOST")
    assert "GHOST (not found)" in r["preview"]


# ---------- projects / destinations ----------


def test_ambiguous_project_hint(world):
    world.add("P1", "Garden", "project", area_title="Home")
    world.add("P2", "Garden", "project", status="completed")
    world.add("P3", "Taxes", "project")
    assert pn.for_project("P1") == {
        "project_title": "Garden", "ambiguous": {"P1": "project in Home"}}
    assert pn.for_project("P2")["ambiguous"] == {"P2": "completed, project"}
    assert pn.for_project("P3")["ambiguous"] == {}


async def test_move_to_ambiguous_project_shows_hint_and_id(world):
    world.add("T1", "Buy milk")
    world.add("P1", "Garden", "project", area_title="Home")
    world.add("P2", "Garden", "project", area_title="Work")
    r = await propose.propose_move_todo("T1", "P1")
    assert r["preview"] == "Move to-do 'Buy milk' to 'Garden' (project in Home, ID P1)"
    r = await propose.propose_move_todo("T1", "P2")
    assert r["preview"].endswith("to 'Garden' (project in Work, ID P2)")


def test_destination_batches_one_query(world):
    world.add("P1", "Garden", "project")
    world.add("P2", "Garden", "project")
    world.add("A1", "Home", "area")
    world.add("A2", "Home", "area")
    world.add("P3", "Solo", "project")
    out = pn.for_destinations(["P1", "A1", "P3", "GHOST"])
    assert out["destination_titles"] == {"P1": "Garden", "A1": "Home", "P3": "Solo", "GHOST": None}
    assert out["ambiguous"] == {"P1": "project", "A1": "area"}
    # projects and areas share one namespace, so a single query covers both
    assert [c[0] for c in world.calls] == ["destination"]


# ---------- areas ----------


def test_area_ambiguity_hint_names_the_kind(world):
    world.add("A1", "Home", "area")
    world.add("A2", "Home", "area")
    world.add("A3", "Work", "area")
    assert pn.for_area("A1") == {"area_title": "Home", "ambiguous": {"A1": "area"}}
    assert pn.for_area("A3")["ambiguous"] == {}
    assert pn.for_area("GHOST") == {"area_title": None, "ambiguous": {}}
    assert pn.for_area(None) == {}
    assert pn.label("A1", "Home", {"ambiguous": {"A1": ""}}) == "'Home' (ID A1)"
    assert pn.label("A1", "Home", {"ambiguous": {"A1": "area"}}) == "'Home' (area, ID A1)"


# ---------- headings (scoped to one project) ----------


def test_heading_ambiguity_is_scoped_to_the_project(world):
    world.add("P1", "Proj one", "project")
    world.add("P2", "Proj two", "project")
    world.add("H1", "__DESIGN__", project="P1")
    world.add("H2", "__DESIGN__", project="P1")   # twin in the SAME project
    world.add("H3", "__BUILD__", project="P1")
    world.add("H4", "__BUILD__", project="P2")    # same title, OTHER project
    world.rows["H1"]["status"] = world.rows["H2"]["status"] = "incomplete"

    out = pn.for_heading("P1", "H1", "delete")
    assert out["heading_title"] == "__DESIGN__"
    assert out["ambiguous"] == {"H1": ""}
    assert ("heading", ("__DESIGN__",), "P1") in world.calls

    out = pn.for_heading("P1", "H3", "delete")
    assert out["ambiguous"] == {}  # "__BUILD__" only once in P1
    out = pn.for_headings("P1", ["H1", "H3"], "delete")
    assert out["ambiguous"] == {"H1": ""}
    assert [i["uuid"] for i in out["heading_items"]] == ["H1", "H3"]
    json.dumps(out)


async def test_propose_delete_heading_renders_id_only_when_ambiguous(world):
    world.add("P1", "Proj one", "project")
    world.add("H1", "__DESIGN__", project="P1")
    world.add("H2", "__DESIGN__", project="P1")
    world.add("H3", "__BUILD__", project="P1")
    r = await propose.propose_delete_heading("P1", "H1")
    assert "dummy heading '__DESIGN__' (ID H1) from project 'Proj one'" in r["preview"]
    r = await propose.propose_delete_heading("P1", "H3")
    assert "dummy heading '__BUILD__' from project 'Proj one'" in r["preview"]
    r = await propose.propose_bulk_delete_heading("P1", ["H1", "H3"])
    assert "  - '__DESIGN__' (ID H1)\n  - '__BUILD__'" in r["preview"]


# ---------- after_todo_id, containers, ai sort ----------


async def test_add_heading_after_todo_title_reports_ambiguity(world):
    world.add("P1", "Proj one", "project")
    world.add("A", "Pay rent", project_title="Proj one")
    world.add("B", "Pay rent", status="completed")
    r = await propose.propose_add_heading("P1", "Plan", after_todo_id="A")
    stored = pending.get(r["action_id"])["payload"]
    assert stored["after_todo_title"] == "Pay rent"
    assert stored["ambiguous"] == {"A": "in Proj one"}
    assert "after_todo_id='Pay rent' (in Proj one, ID A)" in r["preview"]
    assert "project 'Proj one' (URL" in r["preview"]


async def test_every_title_key_path_ends_with_an_ambiguous_key(world):
    world.add("P1", "Proj one", "project")
    world.add("A1", "Home", "area")
    world.add("T1", "One", project="P1")
    world.add("T2", "Two", project="P1")
    world.add("H1", "__X__", project="P1")
    world.rows["P1"]["items"] = [world.rows["T1"], world.rows["T2"]]
    calls = [
        propose.propose_cancel_todo("T1"),
        propose.propose_update_todo("T1", title="n"),
        propose.propose_add_todo("x", list_id="P1"),
        propose.propose_move_todo("T1", "A1"),
        propose.propose_add_project("n", area_id="A1", member_todo_ids=["T1"]),
        propose.propose_update_project("P1", area_id="A1"),
        propose.propose_cancel_project("P1"),
        propose.propose_delete_project("P1"),
        propose.propose_bulk_delete_todo(["T1", "T2"]),
        propose.propose_replace_checklist("T1", ["n"]),
        propose.propose_bulk_update(["T1", "T2"], title="X"),
        propose.propose_move_under_ai_heading(["T1", "T2"], "P1"),
        propose.propose_cleanup_ai_tags(["T1"]),
        propose.propose_bulk_cancel(["T1", "T2"]),
        propose.propose_bulk_move(["T1"], "P1"),
        propose.propose_bulk_add_todo("P1", [{"title": "a"}]),
        propose.propose_update_heading("P1", "H1", "Y"),
        propose.propose_append_checklist_items("T1", ["a"]),
        propose.propose_reorder_todos("P1", ["T2", "T1"]),
        propose.propose_add_heading("P1", "Plan", after_todo_id="T1"),
    ]
    for c in calls:
        r = await c
        payload = pending.get(r["action_id"])["payload"]
        assert isinstance(payload.get("ambiguous"), dict), r["preview"]
        json.dumps(payload)


async def test_reorder_container_titles_report_ambiguity(world):
    world.add("P1", "Proj one", "project")
    world.add("T1", "Same", project="P1")
    world.add("T2", "Same", project="P1")
    world.add("T3", "Other", project="P1")
    world.rows["P1"]["items"] = [world.rows[k] for k in ("T1", "T2", "T3")]
    r = await propose.propose_reorder_todos("P1", ["T3", "T2", "T1"])
    assert "  - 'Other'\n  - 'Same' (ID T2)\n  - 'Same' (ID T1)" in r["preview"]
    assert "in 'Proj one'." in r["preview"]


async def test_apply_ai_tags_dest_and_todo_ambiguity(world, monkeypatch):
    monkeypatch.setattr(things_repo, "tags", lambda include_items=False: [])
    world.add("T1", "Buy milk")
    world.add("P1", "Garden", "project", area_title="Home")
    world.add("P2", "Garden", "project")
    r = await propose.propose_apply_ai_tags([
        {"todo_uuid": "T1", "add_tags": ["*Errand*"],
         "routing": {"dest_kind": "project", "dest_uuid": "P1", "transient": True}},
    ])
    assert ("'Buy milk': add *Errand* (suggested home: 'Garden' (project in Home, ID P1); "
            "nothing moves yet)") in r["preview"]
    json.dumps(pending.get(r["action_id"])["payload"])


# ---------- trashed / template previewed items ----------


def test_trashed_item_with_a_live_twin_is_flagged_in_trash(world):
    world.add("OLD", "Pay rent", trashed=True, status="completed")
    world.add("LIVE", "Pay rent", project_title="Home")
    out = pn.for_todo("OLD")
    assert out["ambiguous"] == {"OLD": "completed, in Trash"}
    # ... and the live one is flagged against the trashed one's live twin only
    assert pn.for_todo("LIVE")["ambiguous"] == {}


def test_trashed_item_without_a_live_twin_is_not_flagged(world):
    world.add("OLD", "Pay rent", trashed=True)
    world.add("ALSO", "Pay rent", trashed=True)
    assert pn.for_todo("OLD")["ambiguous"] == {}


async def test_propose_delete_of_trashed_item_shows_id_and_trash(world):
    world.add("OLD", "Pay rent", trashed=True)
    world.add("LIVE", "Pay rent", project_title="Home")
    r = await propose.propose_delete_todo("OLD")
    assert r["preview"].startswith("Delete to-do 'Pay rent' (in Trash, ID OLD) ")


def test_recurring_template_is_flagged_against_its_instance(world):
    world.add("TPL", "Water plants", template=True)
    world.add("INST", "Water plants", start="Anytime")
    assert pn.for_todo("TPL")["ambiguous"] == {"TPL": ""}
    assert pn.for_todo("INST")["ambiguous"] == {}


def test_trashed_project_hint(world):
    world.add("P1", "Garden", "project", trashed=True)
    world.add("P2", "Garden", "project", area_title="Home")
    assert pn.for_project("P1")["ambiguous"] == {"P1": "project in Trash"}


# ---------- trashed items are always marked ----------


def test_label_marks_trashed_with_and_without_ambiguity():
    p = {"ambiguous": {"B": "completed, in Trash", "C": "", "D": "in Home"}, "trashed": ["A", "B", "C", "D"]}
    assert pn.label("A", "Solo", p) == "'Solo' (in Trash)"
    assert pn.label("B", "Dup", p) == "'Dup' (completed, in Trash, ID B)"   # no double mark
    assert pn.label("C", "Dup", p) == "'Dup' (in Trash, ID C)"              # e.g. a heading
    assert pn.label("D", "Dup", p) == "'Dup' (in Home, in Trash, ID D)"
    assert pn.label("E", "Live", p) == "'Live'"
    # legacy payloads (no ambiguous key) are unchanged
    assert pn.label("A", "Old", {"trashed": ["A"]}) == "'Old' (A)"


def test_merge_unions_trashed():
    p = pn.merge({"trashed": ["a"]}, {"trashed": ["b", "a"], "ambiguous": {}})
    assert p == {"trashed": ["a", "b"], "ambiguous": {}}
    assert pn.merge({}, {"ambiguous": {}}) == {"ambiguous": {}}  # no empty trashed key


def test_unambiguous_trashed_todo_and_project_are_listed_as_trashed(world):
    world.add("T", "Buy milk", trashed=True)
    world.add("P", "Garden", "project", trashed=True)
    assert pn.for_todo("T") == {"todo_title": "Buy milk", "ambiguous": {}, "trashed": ["T"]}
    assert pn.for_project("P")["trashed"] == ["P"]


async def test_propose_previews_mark_trashed_items(world):
    world.add("T", "Buy milk", trashed=True)
    world.add("L", "Call mum")
    world.add("P", "Garden", "project", trashed=True)
    r = await propose.propose_delete_todo("T")
    assert r["preview"].startswith("Delete to-do 'Buy milk' (in Trash) \u2014")
    r = await propose.propose_bulk_complete(["T", "L"])
    assert "  - 'Buy milk' (in Trash)\n  - 'Call mum'" in r["preview"]
    r = await propose.propose_move_todo("L", "P")
    assert r["preview"].endswith("to 'Garden' (in Trash)")


async def test_trashed_dummy_heading_is_marked(world):
    world.add("P1", "Proj one", "project")
    world.add("H1", "__OLD__", project="P1", trashed=True)
    world.add("H2", "__LIVE__", project="P1")
    r = await propose.propose_delete_heading("P1", "H1")
    assert "dummy heading '__OLD__' (in Trash) from project 'Proj one'" in r["preview"]
    # trashed + a live twin in the project: both marks
    world.add("H3", "__OLD__", project="P1")
    r = await propose.propose_delete_heading("P1", "H1")
    assert "'__OLD__' (in Trash, ID H1)" in r["preview"]
    r = await propose.propose_bulk_delete_heading("P1", ["H1", "H2"])
    assert "  - '__OLD__' (in Trash, ID H1)\n  - '__LIVE__'" in r["preview"]


# ---------- existing but untitled items (real data has many) ----------


def test_label_untitled_vs_not_found():
    p = {"ambiguous": {"U": "", "V": "in Home"}, "trashed": ["V"]}
    assert pn.label("U", "", p) == "(untitled, ID U)"
    assert pn.label("V", "", p) == "(untitled, in Home, in Trash, ID V)"
    assert pn.label("X", None, p) == "X (not found)"
    # legacy payload: untitled never occurs there, rendering stays "not found"
    assert pn.label("U", "", {}) == "U (not found)"
    assert pn.fmt_map("U", {"U": ""}, p) == "(untitled, ID U)"
    assert pn.fmt_map("X", {"X": None}, p) == "X (not found)"


def test_lookups_distinguish_untitled_from_not_found(world):
    world.add("T", "", start="Inbox")
    world.add("P", "", "project", area_title="Home")
    world.add("A", "", "area")
    assert pn.for_todo("T") == {"todo_title": "", "ambiguous": {"T": "in Inbox"}}
    assert pn.for_project("P") == {"project_title": "", "ambiguous": {"P": "project in Home"}}
    assert pn.for_area("A") == {"area_title": "", "ambiguous": {"A": "area"}}
    assert pn.for_todos(["T", "GHOST"])["todo_titles"] == {"T": "", "GHOST": None}
    assert pn.for_destinations(["P", "GHOST"])["destination_titles"] == {"P": "", "GHOST": None}
    assert pn.for_todo("GHOST") == {"todo_title": None, "ambiguous": {}}
    assert pn.todo_title("T") == "" and pn.todo_title("GHOST") is None
    # untitled rows never reach the title query
    assert all("" not in titles for _, titles, _ in world.calls)
    json.dumps(pn.for_todos(["T", "GHOST"]))


async def test_delete_untitled_todo_shows_untitled_and_id(world):
    world.add("U", "", project_title="Home")
    r = await propose.propose_delete_todo("U")
    assert r["preview"].startswith("Delete to-do (untitled, in Home, ID U) \u2014")
    assert "not found" not in r["preview"]
    world.add("W", "", trashed=True)
    r = await propose.propose_delete_todo("W")
    assert r["preview"].startswith("Delete to-do (untitled, in Trash, ID W) \u2014")
    r = await propose.propose_delete_todo("GHOST")
    assert "GHOST (not found)" in r["preview"]


async def test_bulk_with_an_untitled_and_a_titled_todo(world):
    world.add("U", "")
    world.add("T", "Buy milk")
    r = await propose.propose_bulk_complete(["U", "T", "GHOST"])
    assert r["preview"] == (
        "Bulk complete 3 to-dos\n"
        "  - (untitled, ID U)\n"
        "  - 'Buy milk'\n"
        "  - GHOST (not found)"
    )


async def test_untitled_project_destination(world):
    world.add("T1", "Buy milk")
    world.add("P", "", "project", area_title="Home")
    world.add("A", "", "area")
    r = await propose.propose_move_todo("T1", "P")
    assert r["preview"] == "Move to-do 'Buy milk' to (untitled, project in Home, ID P)"
    r = await propose.propose_move_todo("T1", "A")
    assert r["preview"] == "Move to-do 'Buy milk' to (untitled, area, ID A)"
    r = await propose.propose_move_todo("T1", "GHOST")
    assert r["preview"].endswith("to GHOST (not found)")


async def test_untitled_in_heading_list_container_and_after_todo(world):
    world.add("P1", "Proj one", "project")
    # (an untitled row can't resolve as a dummy heading, so render the handler directly)
    from safe_things_mcp.services.handlers import bulk_delete_heading
    out = bulk_delete_heading.make_preview({
        "project_id": "P1", "project_title": "Proj one", "heading_ids_or_names": ["H1"],
        "heading_items": [{"ref": "H1", "uuid": "H1", "title": ""},
                          {"ref": "G", "uuid": "G", "title": None}],
        "ambiguous": {"H1": ""},
    })
    assert "  - (untitled, ID H1)\n  - G (not found)" in out
    world.add("T1", "", project="P1")
    world.add("T2", "Two", project="P1")
    world.rows["P1"]["items"] = [world.rows["T1"], world.rows["T2"]]
    r = await propose.propose_reorder_todos("P1", ["T2", "T1"])
    assert "  - 'Two'\n  - (untitled, ID T1)" in r["preview"]
    r = await propose.propose_add_heading("P1", "Plan", after_todo_id="T1")
    assert "after_todo_id=(untitled, ID T1)" in r["preview"]


# ---------- project / area clash ----------


async def test_project_and_area_with_one_name_are_flagged_everywhere(world):
    world.add("T1", "Buy milk")
    world.add("P1", "Work", "project", area_title="Home")
    world.add("A1", "Work", "area")
    r = await propose.propose_move_todo("T1", "A1")
    assert r["preview"] == "Move to-do 'Buy milk' to 'Work' (area, ID A1)"
    r = await propose.propose_move_todo("T1", "P1")
    assert r["preview"] == "Move to-do 'Buy milk' to 'Work' (project in Home, ID P1)"
    r = await propose.propose_bulk_move(["T1"], "A1")
    assert "to 'Work' (area, ID A1)\n" in r["preview"]
    r = await propose.propose_update_project("P1", area_id="A1")
    assert "Update project 'Work' (project in Home, ID P1): area_id='Work' (area, ID A1)" in r["preview"]
    r = await propose.propose_add_project("New", area_id="A1")
    assert "area_id='Work' (area, ID A1)" in r["preview"]
    assert pn.for_area("A1")["ambiguous"] == {"A1": "area"}
    assert pn.for_destinations(["P1", "A1"])["ambiguous"] == {
        "P1": "project in Home", "A1": "area"}
    assert [c[0] for c in world.calls[-1:]] == ["destination"]  # one query, not one per kind


# ---------- nested dummy headings ----------


def test_dummy_heading_nested_under_a_native_heading_counts_as_a_twin(world):
    world.add("P1", "Proj one", "project")
    world.add("NH", "Phase", "heading", project="P1")
    world.add("D1", "__BUILD__", project="P1")
    world.add("D2", "__BUILD__", heading="NH")  # project is NULL, like real data
    assert pn.for_heading("P1", "D1", "delete")["ambiguous"] == {"D1": ""}
    assert pn.for_heading("P1", "D2", "delete")["ambiguous"] == {"D2": ""}


# ---------- failure policy ----------


async def test_ambiguity_query_failure_propagates_and_stages_nothing(world, monkeypatch):
    world.add("T1", "Buy milk")

    def boom(*a, **k):
        raise config.ThingsDBAccessError("macOS is blocking access to the Things database")

    monkeypatch.setattr(things_repo, "live_uuids_by_title", boom)
    with pytest.raises(config.ThingsDBAccessError, match="blocking access"):
        await propose.propose_delete_todo("T1")
    with pytest.raises(config.ThingsDBAccessError):
        pn.for_todos(["T1"])
    assert pending.list_all() == []


def test_wrong_kind_still_raises(world):
    world.add("T1", "Buy milk")
    with pytest.raises(ValueError, match="is a to-do, not a project"):
        pn.for_project("T1")
