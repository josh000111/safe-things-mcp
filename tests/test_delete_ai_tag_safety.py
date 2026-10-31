"""delete_ai_tag safety: duplicate / parent / non-AI tags are refused, undo merges
into CURRENT tags and keeps its undo_log row on partial failure; plus the
bulk_delete_heading header-count dedup.

Uses a tiny real SQLite file shaped like the Things schema (TMTag has ``parent``);
AppleScript only records. No live Things data is touched.
"""
from __future__ import annotations

import re
import sqlite3

import pytest

from safe_things_mcp import config
from safe_things_mcp.services import applescript, things_repo
from safe_things_mcp.services.handlers import bulk_delete_heading, delete_ai_tag
from safe_things_mcp.state import pending, undo_log
from safe_things_mcp.tools import confirm, propose

from .test_preview_names import HDG, PROJ, repo  # noqa: F401  (fixture)

pytestmark = pytest.mark.usefixtures("isolated_state_db")


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "main.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE TMTask (uuid TEXT, title TEXT, type INT, status INT, trashed INT);
        CREATE TABLE TMTag (uuid TEXT, title TEXT, "index" INT, parent TEXT);
        CREATE TABLE TMTaskTag (tasks TEXT, tags TEXT);
        CREATE TABLE TMArea (uuid TEXT, title TEXT);
        CREATE TABLE TMAreaTag (areas TEXT, tags TEXT);
        INSERT INTO TMTag VALUES
          ('gai','AI',0,NULL),
          ('solo','*Solo*',1,'gai'),
          ('dup1','*Dup*',2,'gai'), ('dup2','*Dup*',3,'gai'),
          ('par','*Parent*',4,'gai'), ('kid','*Kid*',5,'par'),
          ('plain','Plain',6,NULL),
          ('other','Other',7,'plain'),
          ('errand','Errand',8,NULL),
          ('fresh','Fresh',9,NULL);
        INSERT INTO TMTask VALUES ('open1','Open',0,0,0),('done1','Done',0,3,0);
        INSERT INTO TMTaskTag VALUES ('open1','solo'),('open1','errand'),('done1','solo');
    """)
    conn.commit()
    conn.close()
    monkeypatch.setenv("THINGS_DB_PATH", str(path))

    def run(sql, *args):
        c = sqlite3.connect(path)
        c.execute(sql, args)
        c.commit()
        c.close()
    return run


@pytest.fixture
def scripts(monkeypatch):
    log: list[str] = []

    async def fake(script: str) -> str:
        log.append(script)
        return "AI" if "name of parent tag" in script else ""

    monkeypatch.setattr(applescript, "run_script", fake)
    monkeypatch.setattr(config, "ALLOW_APPLESCRIPT", True)
    monkeypatch.setattr(config, "AI_TAG_PARENT", "AI")
    monkeypatch.setattr(config, "WRITE_POLL_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(config, "WRITE_POLL_INTERVAL_SECONDS", 0.01)
    return log


# ---------- #2 refusals ----------

REFUSALS = [
    ("*Dup*", "2 tags are named '*Dup*'; rename one in Things first"),
    ("*Parent*", "has 1 child tag"),
    ("AI", "child tag"),                   # the AI parent itself: has children
    ("Plain", "has 1 child tag"),          # top-level non-AI parent
    ("Other", "is not an AI tag"),         # childless but filed under a non-AI parent
    ("Errand", "is not an AI tag"),        # top-level, childless, no parent
]


@pytest.mark.parametrize("name, msg", REFUSALS)
async def test_refused_at_propose_and_execute_with_no_side_effects(db, scripts, monkeypatch, name, msg):
    pattern = re.escape(msg)
    with pytest.raises(ValueError, match=pattern):
        await propose.propose_delete_ai_tag(name)
    assert pending.list_all() == []

    monkeypatch.setattr(things_repo, "get_tag_names", lambda: {name, "AI"})
    with pytest.raises(ValueError, match=pattern):
        await delete_ai_tag.execute({"name": name})
    assert scripts == []                      # no AppleScript at all (not even the parent read)
    assert undo_log.recent(limit=20) == []    # no undo_log row


async def test_unknown_tag_still_reports_not_found(db, scripts):
    with pytest.raises(ValueError, match="not found"):
        await propose.propose_delete_ai_tag("*Nope*")


async def test_single_childless_ai_tag_is_allowed(db, scripts, monkeypatch):
    r = await propose.propose_delete_ai_tag("*Solo*")
    assert "2 item(s)" in r["preview"]
    names = iter([{"*Solo*", "AI"}, set()])
    monkeypatch.setattr(things_repo, "get_tag_names", lambda: next(names, set()))
    out = await confirm.confirm_action(r["action_id"])
    assert out["result"]["tasks_affected"] == 2
    assert any('delete tag "*Solo*"' in s for s in scripts)


async def test_db_read_failure_refuses_instead_of_proceeding(scripts, monkeypatch):
    def boom(name):
        raise config.ThingsDBAccessError("macOS is blocking access")

    monkeypatch.setattr(things_repo, "tag_rows", boom)
    with pytest.raises(config.ThingsDBAccessError):
        await propose.propose_delete_ai_tag("*Solo*")
    with pytest.raises(config.ThingsDBAccessError):
        await delete_ai_tag.execute({"name": "*Solo*"})
    assert scripts == [] and undo_log.recent(limit=5) == []


# ---------- #3 undo merges into CURRENT tags ----------


def _entry(carrying):
    return undo_log.record(
        action_kind="delete_ai_tag", target_uuid="*Solo*",
        before_state={"name": "*Solo*", "parent": "AI", "carrying_tasks": carrying},
        after_state=None,
    )


def _assign(scripts, uuid):
    return next(s for s in scripts if "set tag names" in s and f'"{uuid}"' in s)


async def test_undo_adds_tag_to_current_tags_not_the_delete_time_snapshot(db, scripts, monkeypatch):
    # Delete time: open1 had [*Solo*, Errand]. Since then Things dropped *Solo* (the delete)
    # and the user swapped Errand for Fresh. Undo must keep Fresh and NOT resurrect Errand.
    db("DELETE FROM TMTaskTag WHERE tasks='open1'")
    db("INSERT INTO TMTaskTag VALUES ('open1','fresh')")
    db("DELETE FROM TMTaskTag WHERE tasks='done1'")
    names = iter([{"AI"}, {"AI", "*Solo*"}])
    monkeypatch.setattr(things_repo, "get_tag_names", lambda: next(names, {"AI", "*Solo*"}))
    entry_id = _entry([
        {"uuid": "open1", "title": "Open", "kind": "to-do", "prior_tags": ["*Solo*", "Errand"]},
        {"uuid": "done1", "title": "Done", "kind": "to-do", "prior_tags": ["*Solo*"]},
    ])
    res = await delete_ai_tag.undo(undo_log.get(entry_id))
    assert res["restored_to_tasks"] == 2 and res["failed"] == [] and res["undone"] is True
    s = _assign(scripts, "open1")
    assert "Fresh" in s and "*Solo*" in s and "Errand" not in s
    assert "*Solo*" in _assign(scripts, "done1")
    assert undo_log.get(entry_id) is None


async def test_undo_partial_failure_keeps_row_and_retry_only_redoes_failures(db, scripts, monkeypatch):
    # A retryable error (AppleScript failure) keeps the row; the retry only redoes the failure.
    db("DELETE FROM TMTaskTag WHERE tags='solo'")
    monkeypatch.setattr(things_repo, "get_tag_names", lambda: {"AI", "*Solo*"})
    broken = {"on": True}

    async def flaky(script):
        scripts.append(script)
        if broken["on"] and '"done1"' in script:
            raise RuntimeError("Things got an error")
        return ""

    monkeypatch.setattr(applescript, "run_script", flaky)
    entry_id = _entry([
        {"uuid": "open1", "title": "Open", "kind": "to-do", "prior_tags": ["*Solo*"]},
        {"uuid": "done1", "title": "Done", "kind": "to-do", "prior_tags": ["*Solo*"]},
    ])
    res = await delete_ai_tag.undo(undo_log.get(entry_id))
    assert res["restored_to_tasks"] == 1 and res["undone"] is False
    assert [f["uuid"] for f in res["failed"]] == ["done1"] and res["skipped"] == []
    assert res["undo_id"] == entry_id and "retry" in res["note"]

    kept = undo_log.get(entry_id)
    assert kept is not None                                   # row kept for a retry
    assert kept["before_state"]["restored"] == ["open1"]      # progress recorded
    assert len(kept["before_state"]["carrying_tasks"]) == 2   # original snapshot intact

    # Retry (error cleared): only the failed item is touched, tag is not re-created.
    scripts.clear()
    broken["on"] = False
    res2 = await delete_ai_tag.undo(undo_log.get(entry_id))
    assert res2["restored_to_tasks"] == 1 and res2["failed"] == [] and res2["undone"] is True
    assert not any("make new tag" in s for s in scripts)
    assert [s for s in scripts if "set tag names" in s and '"open1"' in s] == []
    assert '"done1"' in _assign(scripts, "done1")
    assert undo_log.get(entry_id) is None


async def test_undo_missing_item_is_skipped_and_row_deleted_when_only_skips_remain(db, scripts, monkeypatch):
    db("DELETE FROM TMTaskTag WHERE tags='solo'")
    monkeypatch.setattr(things_repo, "get_tag_names", lambda: {"AI", "*Solo*"})
    entry_id = _entry([
        {"uuid": "open1", "title": "Open", "kind": "to-do", "prior_tags": ["*Solo*"]},
        {"uuid": "gone1", "title": "Gone", "kind": "to-do", "prior_tags": ["*Solo*"]},  # not in DB
    ])
    res = await delete_ai_tag.undo(undo_log.get(entry_id))
    assert res["undone"] is True and res["failed"] == []
    assert res["restored_to_tasks"] == 1
    assert [x["uuid"] for x in res["skipped"]] == ["gone1"]
    assert "no longer exist" in res["skipped"][0]["reason"]
    assert "skipped" in res["note"] and "undo_id" not in res
    assert undo_log.get(entry_id) is None                      # complete: row deleted


async def test_undo_skipped_items_are_recorded_so_a_retry_never_revisits_them(db, scripts, monkeypatch):
    db("DELETE FROM TMTaskTag WHERE tags='solo'")
    monkeypatch.setattr(things_repo, "get_tag_names", lambda: {"AI", "*Solo*"})
    broken = {"on": True}

    async def flaky(script):
        if broken["on"] and '"done1"' in script:
            raise RuntimeError("Things got an error")
        return ""

    monkeypatch.setattr(applescript, "run_script", flaky)
    entry_id = _entry([
        {"uuid": "gone1", "title": "Gone", "kind": "to-do", "prior_tags": ["*Solo*"]},  # not in DB
        {"uuid": "done1", "title": "Done", "kind": "to-do", "prior_tags": ["*Solo*"]},
    ])
    res = await delete_ai_tag.undo(undo_log.get(entry_id))
    assert res["undone"] is False
    assert [f["uuid"] for f in res["failed"]] == ["done1"]
    assert [x["uuid"] for x in res["skipped"]] == ["gone1"]
    assert undo_log.get(entry_id)["before_state"]["restored"] == ["gone1"]  # skip is terminal

    # Even if gone1 "reappears" the retry must not touch it; only done1 is retried.
    db("INSERT INTO TMTask VALUES ('gone1','Gone',0,0,0)")
    broken["on"] = False
    res2 = await delete_ai_tag.undo(undo_log.get(entry_id))
    assert res2["undone"] is True and res2["skipped"] == [] and res2["failed"] == []
    assert res2["restored_to_tasks"] == 1
    assert undo_log.get(entry_id) is None


@pytest.mark.parametrize("rows", [
    [{"uuid": "x1", "parent_uuid": None, "parent_title": None, "child_count": 0}],
    [{"uuid": "x1", "parent_uuid": "o1", "parent_title": "Other", "child_count": 0}],
    [{"uuid": "x1", "parent_uuid": "gai", "parent_title": "AI", "child_count": 0},
     {"uuid": "x2", "parent_uuid": "gai", "parent_title": "AI", "child_count": 0}],
], ids=["no-parent", "other-parent", "duplicate-under-ai"])
async def test_undo_refuses_when_same_named_tag_is_not_exactly_one_under_ai(
        db, scripts, monkeypatch, rows):
    monkeypatch.setattr(things_repo, "get_tag_names", lambda: {"AI", "*Solo*"})
    monkeypatch.setattr(things_repo, "tag_rows", lambda name: rows)
    entry_id = _entry([{"uuid": "open1", "title": "Open", "kind": "to-do", "prior_tags": []}])
    expected = (r"tags named '\*Solo\*' now exist; rename or remove the extras" if len(rows) > 1
                else r"outside the AI tag group; rename or remove it in Things, then retry undo")
    with pytest.raises(RuntimeError, match=expected):
        await delete_ai_tag.undo(undo_log.get(entry_id))
    assert scripts == []                                       # nothing tagged or created
    assert undo_log.get(entry_id) is not None                  # row kept for a retry


async def test_undo_script_error_also_keeps_row(db, scripts, monkeypatch):
    monkeypatch.setattr(things_repo, "get_tag_names", lambda: {"AI", "*Solo*"})
    db("DELETE FROM TMTaskTag WHERE tags='solo'")

    async def flaky(script):
        if '"done1"' in script:
            raise RuntimeError("Things got an error")
        return ""

    monkeypatch.setattr(applescript, "run_script", flaky)
    entry_id = _entry([
        {"uuid": "open1", "title": "Open", "kind": "to-do", "prior_tags": []},
        {"uuid": "done1", "title": "Done", "kind": "to-do", "prior_tags": []},
    ])
    res = await delete_ai_tag.undo(undo_log.get(entry_id))
    assert [f["uuid"] for f in res["failed"]] == ["done1"]
    assert undo_log.get(entry_id) is not None


def test_current_item_tags_reads_any_status_and_missing(db):
    assert things_repo.current_item_tags("done1", "to-do") == ["*Solo*"]  # completed item found
    assert things_repo.current_item_tags("nope", "to-do") is None
    assert things_repo.current_item_tags("nope", "area") is None


# ---------- #4 bulk_delete_heading header count ----------


def test_bulk_delete_heading_header_counts_distinct_headings():
    p = bulk_delete_heading.make_preview({
        "project_id": PROJ, "project_title": "Home Admin",
        "heading_ids_or_names": ["Design", HDG],
        "heading_items": [
            {"ref": "Design", "uuid": HDG, "title": "__DESIGN__"},
            {"ref": HDG, "uuid": HDG, "title": "__DESIGN__"},
        ],
    })
    assert p.startswith("Soft-delete 1 dummy heading from project")
    assert p.count("'__DESIGN__' (HDG-1)") == 1  # listed once, like execute acts once


def test_bulk_delete_heading_header_legacy_payload_dedupes_refs():
    p = bulk_delete_heading.make_preview({
        "project_id": PROJ, "heading_ids_or_names": [HDG, HDG, "X"],
    })
    assert "Soft-delete 2 dummy headings" in p


async def test_bulk_delete_heading_propose_count_matches_execute(repo, monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", "tok")
    r = await propose.propose_bulk_delete_heading(PROJ, ["Design", HDG])  # same heading twice
    assert "Soft-delete 1 dummy heading from" in r["preview"]
