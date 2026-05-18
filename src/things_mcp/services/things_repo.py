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
