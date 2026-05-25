"""Thin wrapper over things.py.

Every read call site goes through this module so that if things.py breaks,
the swap is local. All returns are JSON-serializable dicts/lists.
"""
from __future__ import annotations

from typing import Any

import things

from ..config import THINGS_DB_PATH

_DB = str(THINGS_DB_PATH)


def _kw(**extra: Any) -> dict[str, Any]:
    kw: dict[str, Any] = {"filepath": _DB}
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
    return things.get(project_id, **_kw())


def todo(todo_id: str) -> dict[str, Any] | None:
    return things.get(todo_id, **_kw())


def tags(include_items: bool = False) -> list[dict[str, Any]]:
    return things.tags(include_items=include_items, **_kw())


def search(query: str) -> list[dict[str, Any]]:
    return things.search(query, **_kw())


def get(uuid: str) -> dict[str, Any] | None:
    return things.get(uuid, **_kw())


def get_todo(uuid: str) -> dict[str, Any] | None:
    """Return the full to-do row INCLUDING tags.

    ``things.get()`` omits the ``tags`` field; ``things.tasks(uuid)`` returns
    it (as a list of tag-name strings) when the task has tags, or omits the
    key entirely otherwise. Update-flavour handlers use this to snapshot
    before-state with tag fidelity.

    ``things.tasks`` raises ``ValueError`` when the argument is not a valid
    Things UUID (e.g. a plain name string). We treat that as not-found so
    callers can fall through to name-based scanning without a try/except.
    """
    try:
        row = things.tasks(uuid, **_kw())
    except ValueError:
        return None
    return row if isinstance(row, dict) else None


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
    """Return the full project row INCLUDING tags.

    Same pattern as :func:`get_todo` but constrained to ``type='project'``.
    ``things.tasks(uuid, type='project')`` returns ``[]`` (not the row)
    when the UUID doesn't refer to a project; treat that as not-found.
    """
    row = things.tasks(uuid, type="project", **_kw())
    return row if isinstance(row, dict) else None


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
