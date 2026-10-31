"""Safety fixes found in review of the name-enriched propose/confirm previews.

Covers: heading ownership + pinning (update/delete/bulk), delete_ai_tag counting
every carrier and failing loudly, wrong-kind UUIDs (to-do passed as project/area),
replace_checklist read failure, and propose->confirm round trips proving the
enriched payloads build exactly the same commands as bare ones.

Everything is mocked: no live Things data is touched, the AppleScript/URL layer
only records.
"""
from __future__ import annotations

import copy
import sqlite3
from urllib.parse import parse_qs, urlparse

import pytest

from safe_things_mcp import config
from safe_things_mcp.services import applescript, things_repo, url_scheme
from safe_things_mcp.services.handlers import (
    bulk_delete_heading, cancel_project, delete_ai_tag, delete_heading,
    delete_project, update_heading, update_project, add_heading,
)
from safe_things_mcp.state import pending, undo_log
from safe_things_mcp.tools import confirm, propose

from .test_preview_names import (  # noqa: F401  (repo is a fixture)
    AREA, HDG, HDG_B, NATIVE, PROJ, PROJ_B, T1, T2, T3, repo,
)

pytestmark = pytest.mark.usefixtures("isolated_state_db")


# ---------- world: records URL/AppleScript commands, mutates rows like Things ----------


class World:
    def __init__(self, rows):
        self.rows = rows
        self._snapshot = copy.deepcopy(rows)
        self.commands: list[tuple[str, str]] = []
        self.checklists: dict[str, list[dict]] = {}

    def reset(self):
        self.rows.clear()
        self.rows.update(copy.deepcopy(self._snapshot))
        self.commands.clear()
        self.checklists.clear()


@pytest.fixture
def world(repo, monkeypatch):
    for row in repo.values():
        row.setdefault("status", "incomplete")
        row.setdefault("modified", "2026-01-01 00:00:00")
    w = World(repo)
    w.checklists[T1] = [{"title": "old a"}, {"title": "old b"}]

    async def fake_launch(url: str) -> None:
        w.commands.append(("url", url))
        parsed = urlparse(url)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        row = w.rows.get(params.get("id"))
        if row is None:
            return
        if params.get("canceled") == "true":
            row["status"] = "canceled"
        elif params.get("canceled") == "false":
            row["status"] = "incomplete"
        if "title" in params:
            row["title"] = params["title"]
        if "checklist-items" in params:
            w.checklists[params["id"]] = [
                {"title": t} for t in params["checklist-items"].split("\n") if t
            ]
        row["modified"] = "2026-02-01 00:00:00"

    async def fake_script(script: str) -> str:
        w.commands.append(("as", script))
        return ""

    monkeypatch.setattr(url_scheme, "launch", fake_launch)
    monkeypatch.setattr(applescript, "run_script", fake_script)
    monkeypatch.setattr(things_repo, "get", lambda u: w.rows.get(u))
    monkeypatch.setattr(things_repo, "get_checklist_items", lambda u: list(w.checklists.get(u, [])))
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", "tok-xyz")
    monkeypatch.setattr(config, "WRITE_POLL_TIMEOUT_SECONDS", 0.5)
    monkeypatch.setattr(config, "WRITE_POLL_INTERVAL_SECONDS", 0.01)
    return w


def _undo_rows():
    return undo_log.recent(limit=50)


# =====================================================================
# 1. Headings
# =====================================================================


@pytest.mark.parametrize("call", [
    lambda: propose.propose_delete_heading(PROJ, HDG_B),
    lambda: propose.propose_update_heading(PROJ, HDG_B, "New"),
    lambda: propose.propose_bulk_delete_heading(PROJ, [HDG, HDG_B]),
])
async def test_cross_project_heading_uuid_refused_at_propose(world, call):
    with pytest.raises(ValueError, match="does not belong to project"):
        await call()
    assert pending.list_all() == []


@pytest.mark.parametrize("mod, payload", [
    (delete_heading, {"project_id": PROJ, "heading_id_or_name": HDG_B}),
    (update_heading, {"project_id": PROJ, "heading_id_or_name": HDG_B, "new_name": "New"}),
    (bulk_delete_heading, {"project_id": PROJ, "heading_ids_or_names": [HDG_B]}),
])
async def test_cross_project_heading_uuid_refused_at_execute(world, mod, payload):
    """Pre-existing hole: PROJ_A + a heading uuid from PROJ_B used to act on B's heading."""
    with pytest.raises(ValueError, match="does not belong to project"):
        await mod.execute(payload)
    assert world.commands == [] and _undo_rows() == []
    assert world.rows[HDG_B]["status"] == "incomplete"


async def test_pinned_cross_project_uuid_also_refused(world):
    with pytest.raises(ValueError, match="does not belong to project"):
        await delete_heading.execute(
            {"project_id": PROJ, "heading_id_or_name": "x", "heading_uuid": HDG_B})
    assert world.commands == []


@pytest.mark.parametrize("call", [
    lambda: propose.propose_delete_heading(PROJ, NATIVE),
    lambda: propose.propose_update_heading(PROJ, NATIVE, "New"),
    lambda: propose.propose_delete_heading(PROJ, T1),  # an ordinary to-do
])
async def test_non_dummy_heading_uuid_refused_at_propose(world, call):
    with pytest.raises(ValueError, match="not a dummy heading"):
        await call()


async def test_project_titled_like_a_heading_is_not_a_heading(world):
    world.rows[PROJ_B]["title"] = "__SNEAKY__"
    with pytest.raises(ValueError, match="not a dummy heading"):
        await delete_heading.execute({"project_id": PROJ, "heading_id_or_name": PROJ_B})


def _add_second_design_heading(world):
    world.rows["HDG-2"] = {"uuid": "HDG-2", "type": "to-do", "title": "__DESIGN__",
                           "project": PROJ, "status": "incomplete", "modified": "m"}
    world.rows[PROJ]["items"].append({"uuid": "HDG-2", "type": "to-do", "title": "__DESIGN__"})


@pytest.mark.parametrize("call", [
    lambda: propose.propose_delete_heading(PROJ, "Design"),
    lambda: propose.propose_update_heading(PROJ, "Design", "Build"),
    lambda: propose.propose_bulk_delete_heading(PROJ, ["Design"]),
])
async def test_ambiguous_heading_name_refused_at_propose(world, call):
    _add_second_design_heading(world)
    with pytest.raises(ValueError, match="Ambiguous heading name"):
        await call()
    assert pending.list_all() == []


async def test_unknown_heading_name_refused_at_propose(world):
    with pytest.raises(ValueError, match="No heading named"):
        await propose.propose_delete_heading(PROJ, "nope")


async def test_native_only_name_refused_for_delete_but_preview_matches_execute(world):
    # Same resolver as execute: delete refuses a native-only name.
    with pytest.raises(ValueError, match="native heading"):
        await propose.propose_delete_heading(PROJ, "Native")
    with pytest.raises(ValueError, match="native heading"):
        await delete_heading.execute({"project_id": PROJ, "heading_id_or_name": "Native"})


async def test_propose_pins_uuid_and_execute_acts_on_exactly_it(world):
    r = await propose.propose_delete_heading(PROJ, "Design")
    stored = pending.get(r["action_id"])["payload"]
    assert stored["heading_uuid"] == HDG
    _add_second_design_heading(world)  # name now ambiguous, pin must still win
    await confirm.confirm_action(r["action_id"])
    ids = [parse_qs(urlparse(u).query)["id"][0] for k, u in world.commands if k == "url"]
    assert ids == [HDG]
    assert world.rows["HDG-2"]["status"] == "incomplete"


async def test_update_heading_pinned_uuid_used(world):
    r = await propose.propose_update_heading(PROJ, "Design", "Build")
    _add_second_design_heading(world)
    await confirm.confirm_action(r["action_id"])
    assert world.rows[HDG]["title"] == "__BUILD__"
    assert world.rows["HDG-2"]["title"] == "__DESIGN__"


@pytest.mark.parametrize("kind", ["delete", "update", "bulk"])
async def test_pinned_heading_refused_if_moved_to_other_project(world, kind):
    if kind == "delete":
        r = await propose.propose_delete_heading(PROJ, "Design")
    elif kind == "update":
        r = await propose.propose_update_heading(PROJ, "Design", "Build")
    else:
        r = await propose.propose_bulk_delete_heading(PROJ, ["Design"])
    world.rows[HDG]["project"] = PROJ_B  # user moved it after the preview
    with pytest.raises(ValueError, match="does not belong to project"):
        await confirm.confirm_action(r["action_id"])
    assert world.commands == [] and _undo_rows() == []
    assert pending.get(r["action_id"]) is not None  # still pending, nothing consumed


@pytest.mark.parametrize("kind", ["delete", "update", "bulk"])
async def test_pinned_heading_refused_if_deleted(world, kind):
    if kind == "delete":
        r = await propose.propose_delete_heading(PROJ, "Design")
    elif kind == "update":
        r = await propose.propose_update_heading(PROJ, "Design", "Build")
    else:
        r = await propose.propose_bulk_delete_heading(PROJ, ["Design"])
    del world.rows[HDG]
    world.rows[PROJ]["items"] = [i for i in world.rows[PROJ]["items"] if i["uuid"] != HDG]
    with pytest.raises(ValueError, match="no longer exists"):
        await confirm.confirm_action(r["action_id"])
    assert world.commands == [] and _undo_rows() == []


async def test_legacy_payload_without_pin_falls_back_to_name_resolution(world):
    out = await delete_heading.execute({"project_id": PROJ, "heading_id_or_name": "Design"})
    assert out["id"] == HDG
    world.rows[HDG]["status"] = "incomplete"
    out = await update_heading.execute(
        {"project_id": PROJ, "heading_id_or_name": "Design", "new_name": "Build"})
    assert out["id"] == HDG


async def test_dummy_heading_nested_under_native_heading_belongs_via_heading_project(world):
    world.rows["NESTED"] = {"uuid": "NESTED", "type": "to-do", "title": "__NESTED__",
                            "project": None, "heading": NATIVE, "status": "incomplete",
                            "modified": "m"}
    out = await delete_heading.execute({"project_id": PROJ, "heading_id_or_name": "NESTED"})
    assert out["id"] == "NESTED"
    with pytest.raises(ValueError, match="does not belong to project"):
        await delete_heading.execute({"project_id": PROJ_B, "heading_id_or_name": "NESTED"})


async def test_bulk_pins_align_per_item_and_duplicates_act_once(world):
    r = await propose.propose_bulk_delete_heading(PROJ, ["Design", HDG])  # same heading twice
    items = pending.get(r["action_id"])["payload"]["heading_items"]
    assert [i["uuid"] for i in items] == [HDG, HDG]
    out = await confirm.confirm_action(r["action_id"])
    assert out["result"]["ids"] == [HDG]
    assert len([c for c in world.commands if c[0] == "url"]) == 1


async def test_heading_undo_round_trip_still_works(world):
    r = await propose.propose_delete_heading(PROJ, "Design")
    out = await confirm.confirm_action(r["action_id"])
    assert world.rows[HDG]["status"] == "canceled"
    entry = undo_log.get(out["result"]["undo_id"])
    assert entry is not None  # undo row written
    await delete_heading.undo(entry)
    assert world.rows[HDG]["status"] == "incomplete"
    assert undo_log.get(out["result"]["undo_id"]) is None

    r = await propose.propose_update_heading(PROJ, "Design", "Build")
    out = await confirm.confirm_action(r["action_id"])
    assert world.rows[HDG]["title"] == "__BUILD__"
    await update_heading.undo(undo_log.get(out["result"]["undo_id"]))
    assert world.rows[HDG]["title"] == "__DESIGN__"


# =====================================================================
# 2. delete_ai_tag
# =====================================================================


@pytest.fixture
def things_db(tmp_path, monkeypatch):
    """A tiny real SQLite file with the Things tables items_with_tag reads."""
    path = tmp_path / "main.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE TMTask (uuid TEXT, title TEXT, type INT, status INT, trashed INT);
        CREATE TABLE TMTag (uuid TEXT, title TEXT, "index" INT, parent TEXT);
        CREATE TABLE TMTaskTag (tasks TEXT, tags TEXT);
        CREATE TABLE TMArea (uuid TEXT, title TEXT);
        CREATE TABLE TMAreaTag (areas TEXT, tags TEXT);
        INSERT INTO TMTag VALUES ('gai','AI',2,NULL),('g1','*Old*',0,'gai'),('g2','Errand',1,NULL);
        INSERT INTO TMTask VALUES
          ('open1','Open todo',0,0,0),
          ('done1','Completed todo',0,3,0),
          ('canc1','Canceled todo',0,2,0),
          ('trash1','Trashed todo',0,0,1),
          ('proj1','A project',1,0,0),
          ('projdone','Finished project',1,3,0),
          ('head1','A native heading',2,0,0),
          ('other','No tag',0,0,0);
        INSERT INTO TMTaskTag VALUES
          ('open1','g1'),('open1','g2'),('done1','g1'),('canc1','g1'),('trash1','g1'),
          ('proj1','g1'),('projdone','g1'),('head1','g1'),('other','g2');
        INSERT INTO TMArea VALUES ('area1','An area');
        INSERT INTO TMAreaTag VALUES ('area1','g1'),('area1','g2');
    """)
    conn.commit()
    conn.close()
    monkeypatch.setenv("THINGS_DB_PATH", str(path))
    return path


def test_items_with_tag_returns_every_status_projects_and_areas(things_db):
    items = things_repo.items_with_tag("*Old*")
    by_uuid = {i["uuid"]: i for i in items}
    assert set(by_uuid) == {"open1", "done1", "canc1", "trash1", "proj1", "projdone", "area1"}
    assert by_uuid["done1"]["status"] == "completed" and by_uuid["done1"]["kind"] == "to-do"
    assert by_uuid["canc1"]["status"] == "canceled"
    assert by_uuid["trash1"]["trashed"] is True
    assert by_uuid["proj1"]["kind"] == "project"
    assert by_uuid["projdone"]["kind"] == "project" and by_uuid["projdone"]["status"] == "completed"
    assert by_uuid["area1"]["kind"] == "area"
    # full tag set kept for undo
    assert by_uuid["open1"]["prior_tags"] == ["*Old*", "Errand"]
    assert by_uuid["area1"]["prior_tags"] == ["*Old*", "Errand"]


def test_things_py_default_view_would_have_missed_most_of_them(things_db):
    """Documents why the old lookup under-counted: incomplete to-dos only."""
    summary = delete_ai_tag.summarize_carriers(things_repo.items_with_tag("*Old*"))
    assert summary == {"count": 7, "todos": 4, "projects": 2, "areas": 1, "closed": 3, "trashed": 1}


def test_items_with_tag_unknown_tag_and_unreadable_db_raise(things_db, tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="not found"):
        things_repo.items_with_tag("*Nope*")
    monkeypatch.setenv("THINGS_DB_PATH", str(tmp_path / "missing.sqlite"))
    with pytest.raises(config.ThingsDBAccessError):
        things_repo.items_with_tag("*Old*")


def test_delete_ai_tag_preview_breakdown():
    p = delete_ai_tag.make_preview({
        "name": "*Old*", "carrying_count": 7,
        "carrying_summary": {"count": 7, "todos": 4, "projects": 2, "areas": 1, "closed": 3, "trashed": 1},
    })
    assert "7 item(s) (4 to-do(s), 2 project(s), 1 area(s); 3 completed/canceled, 1 in Trash)" in p
    assert "completed/canceled to-dos, projects and areas" in p


def test_delete_ai_tag_preview_unknown_is_not_zero():
    p = delete_ai_tag.make_preview({"name": "*Old*", "carrying_count": None})
    assert "UNKNOWN" in p and "(0" not in p and "0 item" not in p


async def test_propose_delete_ai_tag_counts_all_carriers(things_db, monkeypatch):
    monkeypatch.setattr(config, "ALLOW_APPLESCRIPT", True)
    r = await propose.propose_delete_ai_tag("*Old*")
    assert "7 item(s) (4 to-do(s), 2 project(s), 1 area(s)" in r["preview"]
    stored = pending.get(r["action_id"])["payload"]
    assert stored["carrying_count"] == 7


async def test_propose_delete_ai_tag_lookup_failure_says_unknown(monkeypatch, things_db):
    monkeypatch.setattr(config, "ALLOW_APPLESCRIPT", True)

    def boom(name):
        raise RuntimeError("database disk image is malformed")

    monkeypatch.setattr(things_repo, "items_with_tag", boom)
    r = await propose.propose_delete_ai_tag("*Old*")
    assert "UNKNOWN" in r["preview"] and "0 item" not in r["preview"]
    assert pending.get(r["action_id"])["payload"]["carrying_count"] is None


async def test_propose_delete_ai_tag_db_access_error_and_missing_tag_fail(monkeypatch, things_db):
    monkeypatch.setattr(config, "ALLOW_APPLESCRIPT", True)
    with pytest.raises(ValueError, match="not found"):
        await propose.propose_delete_ai_tag("*Nope*")

    def blocked(name):
        raise config.ThingsDBAccessError("macOS is blocking access")

    monkeypatch.setattr(things_repo, "items_with_tag", blocked)
    with pytest.raises(config.ThingsDBAccessError, match="blocking access"):
        await propose.propose_delete_ai_tag("*Old*")


async def test_delete_ai_tag_execute_aborts_before_mutation_if_lookup_fails(world, things_db, monkeypatch):
    monkeypatch.setattr(things_repo, "get_tag_names", lambda: {"*Old*", "AI"})

    def boom(name):
        raise RuntimeError("cannot read")

    monkeypatch.setattr(things_repo, "items_with_tag", boom)
    with pytest.raises(RuntimeError, match="cannot read"):
        await delete_ai_tag.execute({"name": "*Old*"})
    assert not any("delete tag" in c[1] for c in world.commands)  # tag NOT deleted
    assert _undo_rows() == []


async def test_delete_ai_tag_snapshot_and_undo_cover_completed_items_projects_areas(
    world, things_db, monkeypatch,
):
    names = iter([{"*Old*", "AI"}, set()])
    monkeypatch.setattr(things_repo, "get_tag_names", lambda: next(names, set()))
    out = await delete_ai_tag.execute({"name": "*Old*"})
    assert out["tasks_affected"] == 7
    assert out["affected"]["projects"] == 2 and out["affected"]["closed"] == 3
    entry = undo_log.get(out["undo_id"])
    snap = {c["uuid"]: c for c in entry["before_state"]["carrying_tasks"]}
    assert set(snap) == {"open1", "done1", "canc1", "trash1", "proj1", "projdone", "area1"}

    world.commands.clear()
    monkeypatch.setattr(things_repo, "get_tag_names", lambda: {"AI", "*Old*"})
    res = await delete_ai_tag.undo(entry)
    assert res["restored_to_tasks"] == 7 and res["failed"] == []
    scripts = [c[1] for c in world.commands if c[0] == "as" and "set tag names" in c[1]]
    assert len(scripts) == 7
    by_id = {u: next(s for s in scripts if f'"{u}"' in s) for u in snap}
    for u in ("done1", "canc1", "trash1", "open1"):  # to-dos of any status
        assert f'to do id "{u}"' in by_id[u] and "project id" not in by_id[u]
    for u in ("proj1", "projdone"):  # projects: project id, falling back to to do id
        assert f'set tag names of project id "{u}"' in by_id[u]
        assert f'on error' in by_id[u] and f'set tag names of to do id "{u}"' in by_id[u]
    assert 'area id "area1"' in by_id["area1"]
    for s in scripts:  # every item gets the deleted tag back
        assert "*Old*" in s
    assert '*Old*,Errand' in by_id["open1"] or 'Errand,*Old*' in by_id["open1"]
    assert undo_log.get(out["undo_id"]) is None


async def test_delete_ai_tag_undo_reports_failed_items(world, monkeypatch):
    monkeypatch.setattr(things_repo, "get_tag_names", lambda: {"AI", "*Old*"})
    monkeypatch.setattr(things_repo, "current_item_tags", lambda u, k: ["Errand"])

    async def flaky(script):
        world.commands.append(("as", script))
        if '"bad1"' in script:
            raise RuntimeError("Things got an error")
        return ""

    monkeypatch.setattr(applescript, "run_script", flaky)
    entry_id = undo_log.record(
        action_kind="delete_ai_tag", target_uuid="*Old*",
        before_state={"name": "*Old*", "parent": "AI", "carrying_tasks": [
            {"uuid": "ok1", "title": "ok", "kind": "to-do", "prior_tags": ["*Old*"]},
            {"uuid": "bad1", "title": "bad", "kind": "project", "prior_tags": ["*Old*"]},
        ]},
        after_state=None,
    )
    res = await delete_ai_tag.undo(undo_log.get(entry_id))
    assert res["restored_to_tasks"] == 1
    assert [f["uuid"] for f in res["failed"]] == ["bad1"]
    assert "could not be re-tagged" in res["note"]
    assert undo_log.get(entry_id) is not None  # kept so the user can retry


# =====================================================================
# 3 / 4. Wrong-kind UUIDs
# =====================================================================


@pytest.mark.parametrize("call", [
    lambda: propose.propose_delete_project(T1),
    lambda: propose.propose_cancel_project(T1),
    lambda: propose.propose_update_project(T1, title="x"),
    lambda: propose.propose_delete_project(HDG),
    lambda: propose.propose_move_todo(T2, T1),
    lambda: propose.propose_bulk_move([T2], T1),
    lambda: propose.propose_add_todo("x", list_id=T1),
    lambda: propose.propose_bulk_add_todo(T1, [{"title": "a"}]),
    lambda: propose.propose_move_under_ai_heading([T2], T1),
    lambda: propose.propose_add_heading(T1, "Plan"),
])
async def test_todo_uuid_as_project_or_destination_refused_at_propose(world, call):
    with pytest.raises(ValueError, match="is a to-do, not a project"):
        await call()
    assert pending.list_all() == []


async def test_error_message_names_the_kind(world):
    with pytest.raises(ValueError) as e:
        await propose.propose_delete_project(T1)
    assert f"{T1!r} is a to-do, not a project" in str(e.value)
    with pytest.raises(ValueError, match="is a heading, not a project"):
        await propose.propose_delete_project(NATIVE)


async def test_area_arguments_checked(world):
    with pytest.raises(ValueError, match="is a to-do, not an area"):
        await propose.propose_add_project("New", area_id=T1)
    with pytest.raises(ValueError, match="is a project, not an area"):
        await propose.propose_update_project(PROJ, area_id=PROJ_B)
    r = await propose.propose_update_project(PROJ, area_id=AREA)
    assert "'Personal' (AREA-1)" in r["preview"]


async def test_valid_project_and_area_destinations_still_accepted(world):
    for target in (PROJ, AREA, "today", "Inbox"):
        r = await propose.propose_move_todo(T1, target)
        assert r["action_id"]


async def test_delete_and_cancel_and_update_project_execute_refuse_a_todo_uuid(world, monkeypatch):
    """Pre-existing hole: propose_delete_project(<to-do uuid>) used to proceed."""
    for mod, payload in (
        (delete_project, {"project_id": T1}),
        (cancel_project, {"project_id": T1}),
        (update_project, {"project_id": T1, "title": "x"}),
    ):
        with pytest.raises(ValueError, match="is a to-do, not a project"):
            await mod.execute(payload)
    assert world.commands == [] and _undo_rows() == []
    assert world.rows[T1]["status"] == "incomplete"


async def test_add_heading_execute_refuses_a_todo_uuid_as_project(world):
    with pytest.raises(ValueError, match="is a to-do, not a project"):
        await add_heading.execute({"project_id": T1, "name": "Plan"})
    assert world.commands == []


# =====================================================================
# 5. replace_checklist
# =====================================================================


async def test_replace_checklist_refused_when_existing_checklist_unreadable(world, monkeypatch):
    def boom(u):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(things_repo, "get_checklist_items", boom)
    with pytest.raises(RuntimeError, match="refusing to propose replacing it without showing"):
        await propose.propose_replace_checklist(T1, ["n"])
    assert pending.list_all() == []


async def test_replace_checklist_db_access_error_propagates(world, monkeypatch):
    def blocked(u):
        raise config.ThingsDBAccessError("macOS is blocking access")

    monkeypatch.setattr(things_repo, "get_checklist_items", blocked)
    with pytest.raises(config.ThingsDBAccessError, match="blocking access"):
        await propose.propose_replace_checklist(T1, ["n"])


async def test_replace_checklist_empty_existing_has_no_removed_section(world):
    world.checklists[T1] = []
    r = await propose.propose_replace_checklist(T1, ["n"])
    assert "will be removed" not in r["preview"]
    assert pending.get(r["action_id"])["payload"]["existing_checklist"] == []


# =====================================================================
# 6. apply_ai_tags wording (semantics: tags + routing metadata only)
# =====================================================================


async def test_apply_ai_tags_preview_does_not_claim_a_move(world, monkeypatch):
    monkeypatch.setattr(things_repo, "tags", lambda include_items=False: [])
    r = await propose.propose_apply_ai_tags([
        {"todo_uuid": T1, "add_tags": ["*Errand*"],
         "routing": {"dest_kind": "project", "dest_uuid": PROJ, "transient": True}},
        {"todo_uuid": T2, "add_tags": ["*Unclear*"], "routing": None},
    ])
    p = r["preview"]
    assert "'Buy milk' (TODO-1): add *Errand* (suggested home: 'Home Admin' (PROJ-1); nothing moves yet)" in p
    assert "'Call mum' (TODO-2): add *Unclear*" in p
    assert "→" not in p and "does not move anything" in p


async def test_apply_ai_tags_destination_must_be_project_or_area(world, monkeypatch):
    monkeypatch.setattr(things_repo, "tags", lambda include_items=False: [])
    with pytest.raises(ValueError, match="not a project or area"):
        await propose.propose_apply_ai_tags([
            {"todo_uuid": T1, "add_tags": ["*Errand*"],
             "routing": {"dest_kind": "project", "dest_uuid": T3, "transient": True}},
        ])


# =====================================================================
# 7. propose -> confirm round trips: enriched payload == bare payload
# =====================================================================

ENRICH_KEYS = {
    "todo_title", "todo_titles", "project_title", "destination_title", "area_title",
    "heading_uuid", "heading_title", "heading_items", "existing_checklist",
    "carrying_count", "carrying_summary", "container_title", "after_todo_title",
    "destination_titles",
}


async def _same_commands_enriched_vs_bare(world, propose_call, module):
    world.reset()
    r = await propose_call()
    stored = copy.deepcopy(pending.get(r["action_id"])["payload"])
    assert ENRICH_KEYS & set(stored), "payload should be enriched"
    out = await confirm.confirm_action(r["action_id"])
    enriched = list(world.commands)
    assert enriched, "handler issued no command"
    world.reset()
    bare = {k: v for k, v in stored.items() if k not in ENRICH_KEYS}
    await module.execute(bare)
    assert world.commands == enriched
    return out


ROUND_TRIPS = [
    ("delete_heading", lambda: propose.propose_delete_heading(PROJ, "Design"), delete_heading),
    ("delete_heading_uuid", lambda: propose.propose_delete_heading(PROJ, HDG), delete_heading),
    ("update_heading", lambda: propose.propose_update_heading(PROJ, "Design", "Build"), update_heading),
    ("bulk_delete_heading", lambda: propose.propose_bulk_delete_heading(PROJ, ["Design"]), bulk_delete_heading),
    ("cancel_project", lambda: propose.propose_cancel_project(PROJ), cancel_project),
    ("delete_project", lambda: propose.propose_delete_project(PROJ), delete_project),
]


@pytest.mark.parametrize("name, call, module", ROUND_TRIPS, ids=[r[0] for r in ROUND_TRIPS])
async def test_round_trip_same_command_as_bare_payload(world, name, call, module):
    await _same_commands_enriched_vs_bare(world, call, module)


async def test_round_trip_todo_destructive_kinds(world):
    from safe_things_mcp.services.handlers import (
        bulk_delete, bulk_delete_todo, cancel_todo, delete_todo, replace_checklist,
    )
    await _same_commands_enriched_vs_bare(world, lambda: propose.propose_cancel_todo(T1), cancel_todo)
    await _same_commands_enriched_vs_bare(world, lambda: propose.propose_delete_todo(T1), delete_todo)
    await _same_commands_enriched_vs_bare(
        world, lambda: propose.propose_bulk_cancel([T1, T2]), bulk_delete)
    await _same_commands_enriched_vs_bare(
        world, lambda: propose.propose_bulk_delete_todo([T1, T2]), bulk_delete_todo)
    await _same_commands_enriched_vs_bare(
        world, lambda: propose.propose_replace_checklist(T1, ["n1", "n2"]), replace_checklist)


async def test_round_trip_delete_ai_tag_issues_same_scripts(world, things_db, monkeypatch):
    def fresh_names():
        seq = iter([{"*Old*", "AI"}, set()])
        monkeypatch.setattr(things_repo, "get_tag_names", lambda: next(seq, set()))

    fresh_names()
    r = await propose.propose_delete_ai_tag("*Old*")
    stored = copy.deepcopy(pending.get(r["action_id"])["payload"])
    assert stored["carrying_count"] == 7
    await confirm.confirm_action(r["action_id"])
    enriched = list(world.commands)
    assert any('delete tag "*Old*"' in c[1] for c in enriched)
    world.commands.clear()
    fresh_names()
    await delete_ai_tag.execute({k: v for k, v in stored.items() if k not in ENRICH_KEYS})
    assert world.commands == enriched
