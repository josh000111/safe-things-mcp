"""``things_repo.live_uuids_by_title`` against a small temp SQLite DB.

Only the TMTask / TMArea columns the query reads exist here. The autouse
default stub in conftest is skipped for files named ``*live_uuids_repo*``.
"""
from __future__ import annotations

import sqlite3

import pytest

from safe_things_mcp.services import things_repo

P1, P2 = "PROJ-1", "PROJ-2"
live = things_repo.live_uuids_by_title


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "main.sqlite"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE TMTask (uuid TEXT PRIMARY KEY, title TEXT, type INTEGER, "
        "trashed INTEGER, project TEXT, heading TEXT, rt1_recurrenceRule BLOB)"
    )
    conn.execute("CREATE TABLE TMArea (uuid TEXT PRIMARY KEY, title TEXT)")
    tasks = [
        # (uuid, title, type, trashed, project, heading, recurrence rule)
        ("t1", "Pay rent", 0, 0, None, None, None),
        ("t2", "Pay rent", 0, 0, P1, None, None),
        ("t3", "Solo", 0, 0, None, None, None),
        ("t4", "Trashed twin", 0, 0, None, None, None),
        ("t5", "Trashed twin", 0, 1, None, None, None),   # trashed: never listed
        ("t6", "Repeats", 0, 0, None, None, None),
        ("t7", "Repeats", 0, 0, None, None, b"rule"),     # recurring template: never listed
        # projects
        ("p1", "Garden", 1, 0, None, None, None),
        ("p2", "Garden", 1, 1, None, None, None),          # trashed project
        ("p3", "Pay rent", 1, 0, None, None, None),        # other kind: no clash with to-dos
        ("p4", "Work", 1, 0, None, None, None),            # clashes with area "Work"
        # headings: native (type 2) + dummy to-dos, scoped per project
        (P1, "Proj one", 1, 0, None, None, None),
        ("h1", "Phase 1", 2, 0, P1, None, None),
        ("h2", "Phase 1", 2, 0, P1, None, None),
        ("h3", "Phase 1", 2, 0, P2, None, None),           # same title, other project
        ("h4", "Plan", 2, 0, P1, None, None),
        ("h5", "Plan", 2, 0, P2, None, None),
        ("d1", "__BUILD__", 0, 0, P1, None, None),
        ("d2", "__BUILD__", 0, 0, None, "h4", None),       # dummy nested under native heading h4
        ("d3", "__DESIGN__", 0, 0, P1, None, None),
        ("d4", "__DESIGN__", 0, 0, P2, None, None),
    ]
    conn.executemany("INSERT INTO TMTask VALUES (?,?,?,?,?,?,?)", tasks)
    conn.executemany("INSERT INTO TMArea VALUES (?,?)", [
        ("a1", "Home"), ("a2", "Home"), ("a3", "Work"),
    ])
    conn.commit()
    conn.close()
    monkeypatch.setattr(things_repo, "require_things_db_path", lambda: path)
    return path


def test_todos_list_live_uuids_only(db):
    got = live("to-do", ["Pay rent", "Solo", "Trashed twin", "Repeats", "Garden", "Nope"])
    assert got == {
        "Pay rent": {"t1", "t2"},
        "Solo": {"t3"},
        "Trashed twin": {"t4"},   # t5 is trashed: a previewed t5 is flagged because t4 != t5
        "Repeats": {"t6"},        # the template t7 is excluded
    }


def test_trashed_item_sees_its_live_twin(db):
    # The caller flags a row when the live set holds a uuid other than its own.
    assert live("to-do", ["Trashed twin"])["Trashed twin"] - {"t5"} == {"t4"}
    assert live("to-do", ["Repeats"])["Repeats"] - {"t7"} == {"t6"}      # previewed template
    assert live("to-do", ["Solo"])["Solo"] - {"t3"} == set()


def test_destination_spans_projects_and_areas(db):
    got = live("destination", ["Work", "Home", "Garden", "Solo", "Pay rent"])
    assert got == {
        "Work": {"p4", "a3"},        # project + area with one name clash
        "Home": {"a1", "a2"},
        "Garden": {"p1"},            # p2 is trashed
        "Pay rent": {"p3"},          # to-dos are not destinations
    }


def test_headings_are_scoped_to_the_project(db):
    titles = ["Phase 1", "Plan", "__BUILD__", "__DESIGN__"]
    assert live("heading", titles, P1) == {
        "Phase 1": {"h1", "h2"},
        "Plan": {"h4"},
        "__BUILD__": {"d1", "d2"},   # d2 is nested under native heading h4 (project NULL)
        "__DESIGN__": {"d3"},
    }
    # "Phase 1" appears once in PROJ-2, so it is not a clash there.
    assert live("heading", titles, P2) == {"Phase 1": {"h3"}, "Plan": {"h5"}, "__DESIGN__": {"d4"}}


def test_heading_needs_project(db):
    with pytest.raises(ValueError, match="project_uuid"):
        live("heading", ["x"])


def test_unknown_kind(db):
    with pytest.raises(ValueError, match="kind"):
        live("tag", ["x"])


def test_empty_titles_skip_the_db(monkeypatch):
    def boom():
        raise AssertionError("must not open the DB")

    monkeypatch.setattr(things_repo, "require_things_db_path", boom)
    assert live("to-do", []) == {}
    assert live("to-do", [None, ""]) == {}


def test_large_batches_are_chunked(db):
    titles = [f"x{i}" for i in range(1200)] + ["Pay rent"]
    assert live("to-do", titles) == {"Pay rent": {"t1", "t2"}}
    assert live("destination", titles + ["Home"])["Home"] == {"a1", "a2"}


def test_read_failure_propagates(monkeypatch, tmp_path):
    monkeypatch.setattr(things_repo, "require_things_db_path", lambda: tmp_path / "missing.sqlite")
    with pytest.raises(sqlite3.OperationalError):
        live("to-do", ["x"])


def test_chunk_keeps_bound_params_under_old_sqlite_limit():
    # destination binds each title twice; heading adds two project uuids.
    assert 2 * things_repo._LIVE_CHUNK <= 999
    assert things_repo._LIVE_CHUNK + 2 <= 999
