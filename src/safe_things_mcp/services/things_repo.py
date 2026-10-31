"""Thin wrapper over things.py.

Every read call site goes through this module so that if things.py breaks,
the swap is local. All returns are JSON-serializable dicts/lists.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import things

from ..config import require_things_db_path


def _kw(**extra: Any) -> dict[str, Any]:
    kw: dict[str, Any] = {"filepath": str(require_things_db_path())}
    kw.update({k: v for k, v in extra.items() if v is not None})
    return kw


def inbox() -> list[dict[str, Any]]:
    return things.inbox(**_kw())


def today() -> list[dict[str, Any]]:
    return things.today(**_kw())


def upcoming() -> list[dict[str, Any]]:
    return things.upcoming(**_kw())


def anytime() -> list[dict[str, Any]]:
    return things.anytime(**_kw())


def someday() -> list[dict[str, Any]]:
    return things.someday(**_kw())


def logbook() -> list[dict[str, Any]]:
    return things.logbook(**_kw())


def trash() -> list[dict[str, Any]]:
    return things.trash(**_kw())


def areas(include_items: bool = False) -> list[dict[str, Any]]:
    return things.areas(include_items=include_items, **_kw())


def projects(area: str | None = None, include_completed: bool = False) -> list[dict[str, Any]]:
    kw = _kw(area=area)
    if not include_completed:
        kw["status"] = "incomplete"
    return things.projects(**kw)


def project(project_id: str) -> dict[str, Any] | None:
    """Return the full project row including tags.

    Uses things.tasks(type='project') (not things.get()) so the ``tags``
    field is present in the response.
    """
    row = things.tasks(project_id, type="project", **_kw())
    if isinstance(row, dict):
        row.setdefault("tags", [])
        return row
    return None


def todo(todo_id: str) -> dict[str, Any] | None:
    """Return the full to-do row including tags.

    Uses things.tasks() (not things.get()) so the ``tags`` field is
    present in the response.
    """
    try:
        row = things.tasks(todo_id, **_kw())
    except ValueError:
        return None
    if isinstance(row, dict):
        row.setdefault("tags", [])
        return row
    return None


def tags(include_items: bool = False) -> list[dict[str, Any]]:
    return things.tags(include_items=include_items, **_kw())


def get_tag_names() -> set[str]:
    """Return the set of all tag names currently in Things (case-sensitive)."""
    return {t["title"] for t in things.tags(**_kw())}


_STATUS_NAMES = {0: "incomplete", 2: "canceled", 3: "completed"}


def items_with_tag(tag_title: str) -> list[dict[str, Any]]:
    """Every to-do, project and area carrying ``tag_title``.

    Unlike ``things.tasks(tag=...)`` this ignores status, trash and recurrence
    filters: AppleScript ``delete tag`` strips the tag from ALL of them, so a
    count or undo snapshot built from the default (incomplete-only) view would
    silently under-report. Reads the tag join tables read-only.

    Each row: ``{uuid, title, kind: 'to-do'|'project'|'area', status, trashed,
    prior_tags}`` (``prior_tags`` = the item's full tag set, for undo).
    Raises on ANY failure; callers must never treat that as "no items".
    """
    path = require_things_db_path()
    conn = sqlite3.connect(f"{Path(path).as_uri()}?mode=ro", uri=True)
    try:
        tag_rows = conn.execute("SELECT uuid FROM TMTag WHERE title = ?", (tag_title,)).fetchall()
        if not tag_rows:
            raise ValueError(f"Tag {tag_title!r} not found in the Things database.")
        out: list[dict[str, Any]] = []
        for (tag_uuid,) in tag_rows:
            for uuid, title, type_, status, trashed in conn.execute(
                "SELECT T.uuid, T.title, T.type, T.status, T.trashed FROM TMTaskTag TT "
                "JOIN TMTask T ON T.uuid = TT.tasks WHERE TT.tags = ? AND T.type IN (0, 1)",
                (tag_uuid,),
            ).fetchall():
                prior = [r[0] for r in conn.execute(
                    'SELECT G.title FROM TMTaskTag TT JOIN TMTag G ON G.uuid = TT.tags '
                    'WHERE TT.tasks = ? ORDER BY G."index"', (uuid,))]
                out.append({
                    "uuid": uuid, "title": title or "",
                    "kind": "project" if type_ == 1 else "to-do",
                    "status": _STATUS_NAMES.get(status, str(status)),
                    "trashed": bool(trashed), "prior_tags": prior,
                })
            for uuid, title in conn.execute(
                "SELECT A.uuid, A.title FROM TMAreaTag AT JOIN TMArea A ON A.uuid = AT.areas "
                "WHERE AT.tags = ?", (tag_uuid,),
            ).fetchall():
                prior = [r[0] for r in conn.execute(
                    'SELECT G.title FROM TMAreaTag AT JOIN TMTag G ON G.uuid = AT.tags '
                    'WHERE AT.areas = ? ORDER BY G."index"', (uuid,))]
                out.append({
                    "uuid": uuid, "title": title or "", "kind": "area",
                    "status": "n/a", "trashed": False, "prior_tags": prior,
                })
        return out
    finally:
        conn.close()


def tag_rows(tag_title: str) -> list[dict[str, Any]]:
    """Every TMTag row titled ``tag_title`` (titles are NOT unique in Things).

    Each row: ``{uuid, parent_uuid, parent_title, child_count}``. Read-only SQL;
    raises on ANY failure (callers must never read that as "no such tag").
    """
    path = require_things_db_path()
    conn = sqlite3.connect(f"{Path(path).as_uri()}?mode=ro", uri=True)
    try:
        return [
            {"uuid": u, "parent_uuid": pu, "parent_title": pt, "child_count": cc}
            for u, pu, pt, cc in conn.execute(
                "SELECT T.uuid, T.parent, P.title, "
                "(SELECT COUNT(*) FROM TMTag C WHERE C.parent = T.uuid) "
                "FROM TMTag T LEFT JOIN TMTag P ON P.uuid = T.parent "
                "WHERE T.title = ? ORDER BY T.\"index\"",
                (tag_title,),
            ).fetchall()
        ]
    finally:
        conn.close()


def current_item_tags(uuid: str, kind: str) -> list[str] | None:
    """Current tag titles of a to-do/project/area in ANY status (incl. completed,
    canceled, trashed), or ``None`` if the item no longer exists. Unlike
    ``things.tasks(uuid)`` this is not limited to open, untrashed items. Read-only;
    raises on any DB failure."""
    path = require_things_db_path()
    conn = sqlite3.connect(f"{Path(path).as_uri()}?mode=ro", uri=True)
    try:
        if kind == "area":
            exists = conn.execute("SELECT 1 FROM TMArea WHERE uuid = ?", (uuid,)).fetchone()
            sql = ('SELECT G.title FROM TMAreaTag X JOIN TMTag G ON G.uuid = X.tags '
                   'WHERE X.areas = ? ORDER BY G."index"')
        else:
            exists = conn.execute("SELECT 1 FROM TMTask WHERE uuid = ?", (uuid,)).fetchone()
            sql = ('SELECT G.title FROM TMTaskTag X JOIN TMTag G ON G.uuid = X.tags '
                   'WHERE X.tasks = ? ORDER BY G."index"')
        if not exists:
            return None
        return [r[0] for r in conn.execute(sql, (uuid,)).fetchall()]
    finally:
        conn.close()


def search(query: str) -> list[dict[str, Any]]:
    return things.search(query, **_kw())


def get(uuid: str) -> dict[str, Any] | None:
    return things.get(uuid, **_kw())


def get_todo(uuid: str) -> dict[str, Any] | None:
    """Return the full to-do row INCLUDING tags. Delegates to :func:`todo`."""
    return todo(uuid)


def find_recent_inbox_by_title(title: str, created_after: str) -> dict[str, Any] | None:
    """Return the newest Inbox to-do with this title created at-or-after a Things
    ``created`` timestamp (``YYYY-MM-DD HH:MM:SS`` local-naive). Used by the
    V1 write path to recover the new task's UUID via polling instead of an
    HTTP callback. Returns ``None`` if nothing matches yet.
    """
    matches = [
        t for t in things.inbox(**_kw())
        if t.get("title") == title and (t.get("created") or "") >= created_after
    ]
    if not matches:
        return None
    matches.sort(key=lambda t: t.get("created") or "", reverse=True)
    return matches[0]


def get_project_row(uuid: str) -> dict[str, Any] | None:
    """Return the full project row INCLUDING tags. Delegates to :func:`project`."""
    return project(uuid)


def find_recent_project_by_title(title: str, created_after: str) -> dict[str, Any] | None:
    """Like :func:`find_recent_by_title` but scoped to projects.

    The add-project URL scheme doesn't return a UUID via callback (we
    retired the HTTP listener; see arch doc §2 Q2). To recover the new
    project's UUID we poll incomplete projects for a title + created
    window match. Single-creation scale makes title collisions a
    non-issue in practice (an existing project with the same title would
    have an earlier ``created`` timestamp).
    """
    matches = [
        p for p in things.tasks(type="project", status="incomplete", **_kw())
        if p.get("title") == title and (p.get("created") or "") >= created_after
    ]
    if not matches:
        return None
    matches.sort(key=lambda p: p.get("created") or "", reverse=True)
    return matches[0]


def find_recent_by_title(title: str, created_after: str) -> dict[str, Any] | None:
    """Like :func:`find_recent_inbox_by_title` but scans every incomplete
    to-do across all lists. The URL-scheme call already routed the task to
    the right list; we only need to recover the new UUID, and matching by
    title + a tight created-window across all open tasks is robust enough
    at single-task scale.
    """
    matches = [
        t for t in things.tasks(status="incomplete", **_kw())
        if t.get("title") == title and (t.get("created") or "") >= created_after
    ]
    if not matches:
        return None
    matches.sort(key=lambda t: t.get("created") or "", reverse=True)
    return matches[0]


def get_container_todo_uuids(container_type: str, container_id: str) -> list[str]:
    """Return ordered list of to-do UUIDs in the container.

    For projects: returns UUIDs of items with type=="to-do" only
    (native headings excluded — handled separately).
    For built-in lists: returns UUIDs in Things' current display order.
    Raises ValueError for unknown list names or missing projects.
    """
    if container_type == "project":
        proj = project(container_id)
        if proj is None:
            raise ValueError(f"Project {container_id!r} not found.")
        return [item["uuid"] for item in (proj.get("items") or [])
                if item.get("type") == "to-do"]
    _LIST_FN = {
        "Inbox": inbox, "Today": today, "Anytime": anytime,
        "Someday": someday, "Upcoming": upcoming,
        "Logbook": logbook, "Trash": trash,
    }
    fn = _LIST_FN.get(container_id)
    if fn is None:
        raise ValueError(f"Unknown list: {container_id!r}")
    return [t["uuid"] for t in fn()]


def get_checklist_items(todo_id: str) -> list[dict[str, Any]]:
    """Return checklist items for a to-do (SQLite read via things-py)."""
    return things.checklist_items(todo_id, **_kw())


def get_project_with_headings(project_id: str) -> dict[str, Any] | None:
    """Return a project row augmented with a unified ``headings`` list.

    The ``headings`` list contains entries for BOTH native Things headings
    and dummy heading tasks (``__NAME__`` pattern), each with:
        {kind: "native"|"dummy", id: str, name: str, position: int}

    ``position`` is the 0-based index within the project's ``items`` list.
    Dummy heading tasks are still present in ``items`` (the user sees them
    as regular tasks in Things); the ``headings`` key is an additional
    overlay so the agent can reason about structure.
    """
    from .handlers.dummy_heading import is_dummy_heading, extract_name_from_dummy

    proj = project(project_id)
    if proj is None:
        return None

    headings: list[dict[str, Any]] = []
    for position, item in enumerate(proj.get("items") or []):
        item_type = item.get("type", "")
        item_title = item.get("title", "")
        item_uuid = item.get("uuid", "")

        if item_type == "heading":
            headings.append({
                "kind": "native",
                "id": item_uuid,
                "name": item_title,
                "position": position,
            })
        elif item_type == "to-do" and is_dummy_heading(item_title):
            headings.append({
                "kind": "dummy",
                "id": item_uuid,
                "name": extract_name_from_dummy(item_title),
                "position": position,
            })

    return {**proj, "headings": headings}
