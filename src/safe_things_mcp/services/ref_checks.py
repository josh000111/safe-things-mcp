"""Type guards for UUID arguments that must be a project and/or an area.

things.py ignores ``type=`` whenever a UUID is given, so ``things_repo.project(x)``
happily returns a to-do row for a to-do UUID. Callers that act on "a project"
must therefore check the returned row's own ``type``. These helpers do that in
one place, for both propose time and execute time.

Contract: a UUID that does not exist yields ``None`` (callers decide whether
that is "not found" or an error); a UUID that exists with the wrong type raises
``ValueError``; DB access failures (``config.ThingsDBAccessError`` etc.)
propagate untouched. A row with no ``type`` key (only hand-built test rows;
things.py always sets it) is accepted.

To-do guard (``check_todo`` / ``check_todos`` / ``require_todo``): every tool
that acts on a to-do id must refuse a project, native heading or area id,
because ``things.tasks(uuid)`` ignores ``type=`` and AppleScript / URL-scheme
commands addressed at that id would act on the whole project (e.g.
``delete (to do id "<project uuid>")`` trashes the project and its contents,
and undo cannot restore it).

Dummy headings (to-dos titled ``__NAME__``, see ``handlers/dummy_heading.py``)
ARE accepted as to-dos, deliberately: they are plain ``type == "to-do"`` rows
with no children, so acting on one has exactly the blast radius of any single
to-do, and legitimate flows (reorder_todos over a container, the AI marker and
separator in move_under_heading) pass them as members. Only rows whose own
``type`` is not ``to-do`` (project, heading, area, tag, checklist-item) are
refused.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable

from . import things_repo

# Move/list targets that are keywords rather than UUIDs.
KEYWORD_LISTS = {"inbox", "today", "anytime", "someday", "upcoming"}


def is_keyword(target: str | None) -> bool:
    return bool(target) and target.strip().lower() in KEYWORD_LISTS  # type: ignore[union-attr]


def _lookup(fn: Callable[[str], Any], uuid: str) -> dict | None:
    try:
        row = fn(uuid)
    except ValueError:  # things.py: "No such uuid found"
        return None
    return row if isinstance(row, dict) else None


def _wrong_type(uuid: str, row: dict, wanted: str) -> ValueError:
    return ValueError(
        f"{uuid!r} is a {row.get('type')}, not {wanted}. "
        f"Pass the UUID of {wanted}."
    )


def check_project(uuid: str | None) -> dict | None:
    """Project row for ``uuid``; ``None`` if it doesn't exist; ValueError if it
    exists but is not a project (e.g. a to-do or heading UUID)."""
    if not uuid:
        return None
    row = _lookup(things_repo.get_project_row, uuid)
    if row is None:
        return None
    if row.get("type") not in (None, "project"):
        raise _wrong_type(uuid, row, "a project")
    return row


def check_area(uuid: str | None) -> dict | None:
    """Area row for ``uuid``; ``None`` if absent; ValueError if the UUID belongs
    to a to-do/project/heading."""
    if not uuid:
        return None
    task_row = _lookup(things_repo.todo, uuid)
    if task_row is not None and task_row.get("type") != "area":
        raise _wrong_type(uuid, task_row, "an area")
    for a in things_repo.areas():
        if a.get("uuid") == uuid:
            return a
    return None


def check_destination(dest_id: str | None) -> dict | None:
    """Row for a project-or-area UUID. Keywords and unknown UUIDs give ``None``;
    a to-do/heading UUID raises ValueError."""
    if not dest_id or is_keyword(dest_id):
        return None
    row = _lookup(things_repo.get_project_row, dest_id)
    if row is not None:
        if row.get("type") not in (None, "project"):
            raise _wrong_type(dest_id, row, "a project or area")
        return row
    for a in things_repo.areas():
        if a.get("uuid") == dest_id:
            return a
    return None


# ---------- to-do guard ----------


def _todo_type_error(uuid: str, row: Any) -> str | None:
    """Error text if ``row`` exists but is not a plain to-do, else ``None``.
    A non-dict row (not found) and a row without a ``type`` key pass."""
    if not isinstance(row, dict):
        return None
    kind = row.get("type")
    if kind in (None, "to-do"):
        return None
    return f"{uuid!r} is a {kind}, not a to-do"


def require_todo(uuid: str, row: Any) -> Any:
    """Validate an already-fetched row for ``uuid``; return it unchanged.
    Raises ValueError for a project/heading/area/etc. row. Handlers call this on
    the row they fetched anyway, so no extra DB read and the same mocks apply."""
    err = _todo_type_error(uuid, row)
    if err:
        raise ValueError(f"{err}. Pass the UUID of a to-do, not of a container.")
    return row


def check_todo(uuid: str | None, getter: Callable[[str], Any] | None = None) -> dict | None:
    """To-do row for ``uuid``; ``None`` if it doesn't exist; ValueError if it
    exists but is a project/heading/area. ``getter`` defaults to
    ``things_repo.todo``; DB access failures propagate."""
    if not uuid:
        return None
    row = _lookup(getter or things_repo.todo, uuid)
    return require_todo(uuid, row)


def check_todos(
    uuids: Iterable[str], getter: Callable[[str], Any] | None = None
) -> dict[str, dict | None]:
    """Batch ``check_todo``. Looks up EVERY id first, then raises one ValueError
    naming every offending id, so a bulk tool refuses the whole batch before it
    mutates or writes an undo_log row. Returns ``{uuid: row-or-None}``."""
    get = getter or things_repo.todo
    rows: dict[str, dict | None] = {}
    errors: list[str] = []
    for uuid in dict.fromkeys(u for u in (uuids or []) if u):
        row = _lookup(get, uuid)
        rows[uuid] = row
        err = _todo_type_error(uuid, row)
        if err:
            errors.append(err)
    if errors:
        raise ValueError(
            "Refusing the whole batch, nothing was changed: "
            + "; ".join(errors)
            + ". Pass only to-do UUIDs."
        )
    return rows
