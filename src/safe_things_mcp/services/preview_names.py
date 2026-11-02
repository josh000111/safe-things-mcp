"""Propose-time display-name lookups for confirmation previews.

The preview a user approves must name what it acts on. ``for_*`` helpers read
Things (read-only, via ``things_repo``) and return extra payload keys;
``fmt*`` / ``label`` render them inside ``make_preview``.

Rendering contract (one function, ``label``, implements it):
- title found, not ambiguous -> ``'Title'`` (no ID).
- title found, and a different non-trashed item of the same kind has the exact
  same title -> ``'Title' (<hint>, ID <uuid>)``. The hint is built at propose
  time from the row already fetched: status if not open, then ``in Trash`` for a
  trashed item (it is flagged against its live twins) or its location. Projects
  and areas share one namespace, because a destination named ``Work`` could be
  either; their hint names the kind (``area`` / ``project in Home``). Headings
  are compared only within their project and have no hint. The parenthetical is
  just ``(ID <uuid>)`` when the hint is empty.
- a trashed item is always marked: ``'Title' (in Trash)``, or ``(in Trash, ID
  <uuid>)`` when also ambiguous (payload key ``trashed``: list of uuids).
- title key present but ``None`` -> ``uuid (not found)``.
- item exists but has an empty title (stored as ``""``) -> ``(untitled, <hint>,
  ID <uuid>)``: always with the ID, since there is no name to tell it apart.
- title key absent (hand-built test payload) -> bare ``uuid``.
- payload staged before ambiguity info existed (title key but no ``ambiguous``
  key) -> legacy ``'Title' (uuid)``, so an old pending proposal never hides an
  ID it would previously have shown.

Ambiguity lives in one payload key, ``ambiguous``: ``{uuid: hint}`` holding only
the ambiguous uuids. Its presence (even ``{}``) marks a new-style payload, so
every ``for_*`` helper returns it and ``merge`` unions it across helpers. All
lookups happen at propose time and stored values are JSON-serializable
(payloads persist in state.db).

Failure policy: only "no such uuid" renders as "(not found)". A DB that can't
be read (``config.ThingsDBAccessError`` or any other read error, including in
the ambiguity query) propagates so propose fails loudly instead of showing a
misleading "(not found)" or "not ambiguous" on a destructive action.
``for_project`` / ``for_area`` / ``for_destination`` / ``for_heading(s)`` also
raise ``ValueError`` when the UUID exists but is the wrong kind, or (headings)
when execute would refuse it.
"""
from __future__ import annotations

from typing import Any, Iterable

from . import ref_checks, things_repo
from .ref_checks import KEYWORD_LISTS  # noqa: F401  (re-exported)

# Max item lines in a bulk preview before collapsing to "...and N more".
PREVIEW_LINE_CAP = 20


# ---------- lookups ----------


def _title(row: Any) -> str | None:
    """Display title of a looked-up row: ``None`` when there is no row (not
    found), ``""`` when the row exists but is untitled (real Things data has
    many), so previews can tell the two apart."""
    if not isinstance(row, dict):
        return None
    return row.get("title") or row.get("name") or ""


def todo_title(uuid: str | None) -> str | None:
    if not uuid:
        return None
    return _title(things_repo.todo(uuid))  # None for an unknown uuid


def project_title(uuid: str | None) -> str | None:
    """Title of project ``uuid`` (None if it doesn't exist; ValueError if the
    uuid is a to-do/heading, so a to-do's name is never shown as a project)."""
    return _title(ref_checks.check_project(uuid))


def area_title(uuid: str | None) -> str | None:
    return _title(ref_checks.check_area(uuid))


def destination_title(dest_id: str | None) -> str | None:
    """Name of a project-or-area UUID."""
    return _title(ref_checks.check_destination(dest_id))


def _is_destination_id(dest_id: str | None) -> bool:
    return bool(dest_id) and dest_id.strip().lower() not in KEYWORD_LISTS  # type: ignore[union-attr]


# ---------- ambiguity ----------


def _hint(kind: str, row: dict) -> str:
    """Human context for an ambiguous item, from the row already fetched
    (empty when the row doesn't say; headings have none). ``kind`` is "to-do",
    "heading" or "destination" (project or area: the hint names which, because
    a project and an area can share a title)."""
    status = row.get("status")
    parts = [status] if status in ("completed", "canceled") else []
    trashed = bool(row.get("trashed"))
    if kind == "to-do":
        project, heading = row.get("project_title"), row.get("heading_title")
        if trashed:
            parts.append("in Trash")
        elif project and heading:
            parts.append(f"in {project} \u203a {heading}")
        elif project or heading:
            parts.append(f"in {project or heading}")
        elif row.get("area_title"):
            parts.append(f"in {row['area_title']}")
        elif row.get("start") in ("Inbox", "Anytime", "Someday"):
            parts.append(f"in {row['start']}")
    elif kind == "destination":
        if row.get("type") == "area":
            parts.append("area")
        elif trashed:
            parts.append("project in Trash")
        elif row.get("area_title"):
            parts.append(f"project in {row['area_title']}")
        else:
            parts.append("project")
    else:
        return ""
    return ", ".join(parts)


def _with_heading_project(row: dict) -> dict:
    """things.py leaves ``project_title`` NULL for a to-do under a native
    heading; read the heading's own row for it (only called for ambiguous items,
    so the extra read is rare)."""
    if row.get("project_title") or not row.get("heading_title") or not row.get("heading"):
        return row
    project = (things_repo.todo(row["heading"]) or {}).get("project_title")
    return {**row, "project_title": project} if project else row


def _ambiguity(kind: str, rows: Iterable[Any], project_id: str | None = None) -> dict[str, Any]:
    """``{"ambiguous": {uuid: hint}[, "trashed": [uuid, ...]]}`` for the titled rows among ``rows``: one
    ``things_repo.live_uuids_by_title`` query for the whole batch. A row is
    ambiguous when it is untitled, or when a LIVE item of the same kind and title exists besides itself
    (so a trashed row with one live twin is flagged too). Always returns the key
    (even empty) so the payload counts as new-style."""
    rows = [r for r in rows if isinstance(r, dict) and r.get("uuid")]
    titled = [r for r in rows if _title(r)]
    live = things_repo.live_uuids_by_title(kind, [_title(r) for r in titled], project_id)
    out: dict[str, str] = {}
    for r in rows:
        # An untitled item has no name to tell it apart: always flagged, so its
        # ID is always shown (and no title query applies to it).
        if not _title(r) or live.get(_title(r), set()) - {r["uuid"]}:
            out[r["uuid"]] = _hint(kind, _with_heading_project(r) if kind == "to-do" else r)
    result: dict[str, Any] = {"ambiguous": out}
    # Trashed items are marked in previews even when unambiguous (acting on
    # something in Trash is worth a visible flag); omitted when none, to keep payloads small.
    trashed = [r["uuid"] for r in rows if r.get("trashed")]
    if trashed:
        result["trashed"] = trashed
    return result


def merge(payload: dict, extra: dict) -> dict:
    """``payload.update(extra)`` except ``ambiguous`` dicts and ``trashed`` lists
    are unioned, so several ``for_*`` lookups for one proposal accumulate.
    Returns ``payload``."""
    extra = dict(extra)
    amb = extra.pop("ambiguous", None)
    trashed = extra.pop("trashed", None)
    payload.update(extra)
    if amb is not None:
        payload["ambiguous"] = {**(payload.get("ambiguous") or {}), **amb}
    if trashed:
        payload["trashed"] = list(dict.fromkeys([*(payload.get("trashed") or []), *trashed]))
    return payload


# ---------- for_* (propose-time lookups) ----------


def for_todo(todo_id: str) -> dict[str, Any]:
    """Propose-time to-do lookup. Raises ValueError if the uuid is a project /
    heading / area, so every ``propose_*`` that takes a to-do id refuses it here
    (execute re-checks)."""
    row = ref_checks.check_todo(todo_id)
    return {"todo_title": _title(row), **_ambiguity("to-do", [row])}


def for_project(project_id: str) -> dict[str, Any]:
    row = ref_checks.check_project(project_id)
    return {"project_title": _title(row), **_ambiguity("destination", [row])}


def for_todos(todo_ids: Iterable[str]) -> dict[str, Any]:
    """Titles for a batch; raises ValueError naming every non-to-do id."""
    rows = ref_checks.check_todos(todo_ids or [])
    return {
        "todo_titles": {u: _title(r) for u, r in rows.items()},
        **_ambiguity("to-do", rows.values()),
    }


def for_after_todo(todo_id: str | None) -> dict[str, Any]:
    """Title of the ``after_todo_id`` hint (no type check: it is only displayed)."""
    row = things_repo.todo(todo_id) if todo_id else None
    return {"after_todo_title": _title(row), **_ambiguity("to-do", [row])}


def for_destination(dest_id: str | None) -> dict[str, Any]:
    """``destination_title`` for a non-keyword list_id/target; ``{}`` otherwise."""
    if not _is_destination_id(dest_id):
        return {}
    row = ref_checks.check_destination(dest_id)
    return {"destination_title": _title(row), **_ambiguity("destination", [row])}


def for_destinations(dest_ids: Iterable[str]) -> dict[str, Any]:
    """Titles for several project-or-area uuids (``destination_titles`` map)."""
    rows = {d: ref_checks.check_destination(d) for d in dict.fromkeys(dest_ids or [])}
    return {
        "destination_titles": {d: _title(r) for d, r in rows.items()},
        **_ambiguity("destination", rows.values()),
    }


def for_area(area_id: str | None) -> dict[str, Any]:
    if not area_id:
        return {}
    row = ref_checks.check_area(area_id)
    return {"area_title": _title(row), **_ambiguity("destination", [row])}


def _resolve_heading(project_id: str, ref: str, action: str) -> tuple[str, dict | None]:
    """Resolve a heading ref with the SAME function execute uses, so a preview
    is never shown for something execute would refuse or apply elsewhere.
    ``action`` is "update" or "delete" (their name-resolution rules differ).
    Raises ValueError (ambiguous, wrong project, not a heading, not found)."""
    from .handlers import delete_heading, update_heading

    resolver = (
        update_heading._resolve_heading_uuid if action == "update"
        else delete_heading._resolve_heading_uuid
    )
    uuid = resolver(project_id, ref)
    return uuid, things_repo.get_todo(uuid)


def _heading_ambiguity(project_id: str, pairs: Iterable[tuple[str, dict | None]]) -> dict[str, Any]:
    """Heading ambiguity is checked only inside ``project_id`` (the preview
    already names the project)."""
    rows = [{"uuid": u, "title": _title(r), "trashed": r.get("trashed")}
            for u, r in pairs if isinstance(r, dict)]
    return _ambiguity("heading", rows, project_id)


def for_heading(project_id: str, ref: str, action: str = "delete") -> dict[str, Any]:
    uuid, row = _resolve_heading(project_id, ref, action)
    out = {"heading_uuid": uuid, "heading_title": _title(row)}
    merge(out, _heading_ambiguity(project_id, [(uuid, row)]))
    # project keys first in the payload, as before
    return merge(dict(for_project(project_id)), out)


def for_headings(project_id: str, refs: list[str], action: str = "delete") -> dict[str, Any]:
    items, pairs = [], []
    for ref in refs or []:
        uuid, row = _resolve_heading(project_id, ref, action)
        items.append({"ref": ref, "uuid": uuid, "title": _title(row)})
        pairs.append((uuid, row))
    out = for_project(project_id)
    out["heading_items"] = items
    return merge(out, _heading_ambiguity(project_id, pairs))


def for_container(container_type: str, container_id: str, uuids: list[str]) -> dict[str, Any]:
    """``todo_titles`` (+ ``container_title`` for a project) for a reorder
    container, read from one container fetch."""
    if container_type == "project":
        rows = (things_repo.project(container_id) or {}).get("items") or []
    else:
        rows = getattr(things_repo, container_id.lower())()
    by_id = {r.get("uuid"): r for r in rows}
    todo_rows: dict[str, Any] = {}
    for u in dict.fromkeys(uuids or []):
        row = by_id.get(u)
        todo_rows[u] = row if _title(row) else (things_repo.todo(u) or row)
    out: dict[str, Any] = {
        "todo_titles": {u: _title(r) for u, r in todo_rows.items()},
        **_ambiguity("to-do", todo_rows.values()),
    }
    if container_type == "project":
        proj = for_project(container_id)
        merge(out, {"container_title": proj.pop("project_title"), **proj})
    return out


# ---------- rendering (used by handlers' make_preview) ----------


def label(uuid: str | None, title: str | None, payload: dict) -> str:
    """The single rendering rule (see module docstring) for a looked-up item.
    ``title`` None means "looked up, not found"; ``""`` means "exists, untitled"."""
    uuid = uuid or ""
    amb = payload.get("ambiguous")
    if title is None or (not title and not isinstance(amb, dict)):
        return f"{uuid} (not found)"  # (untitled never occurs in legacy payloads)
    if not isinstance(amb, dict):
        return f"'{title}' ({uuid})"  # legacy payload: keep showing the ID
    hint = amb.get(uuid)
    if uuid in (payload.get("trashed") or []) and "in Trash" not in (hint or ""):
        hint = f"{hint}, in Trash" if hint else "in Trash"
    if not title:  # no name to show, so the ID is always needed
        return f"(untitled, {hint}, ID {uuid})" if hint else f"(untitled, ID {uuid})"
    if uuid not in amb:
        return f"'{title}' ({hint})" if hint else f"'{title}'"
    return f"'{title}' ({hint}, ID {uuid})" if hint else f"'{title}' (ID {uuid})"


def fmt(uuid: str | None, payload: dict, title_key: str) -> str:
    """``label`` for ``payload[title_key]``, or bare ``uuid`` if the key is absent."""
    if title_key not in payload:
        return uuid or ""
    return label(uuid, payload[title_key], payload)


def fmt_destination(target: str | None, payload: dict, quote_keyword: bool = True) -> str:
    """Keyword targets render as-is (quoted unless told otherwise); UUID targets
    get their name (and ID only when ambiguous)."""
    if not _is_destination_id(target) or "destination_title" not in payload:
        return repr(target) if quote_keyword else str(target)
    return fmt(target, payload, "destination_title")


def fmt_heading(ref: str, payload: dict) -> str:
    """Heading ref rendered with its resolved title; legacy payloads keep the
    raw ref (a UUID or a name)."""
    if "heading_title" not in payload:
        return repr(ref)
    uuid = payload.get("heading_uuid") or ref
    title = payload["heading_title"]
    # a not-found heading names the ref the caller passed, not a resolved uuid
    return label(uuid, title, payload) if title is not None else f"{ref} (not found)"


def fmt_map(uuid: str, titles: dict | None, payload: dict) -> str:
    if titles is None or uuid not in titles:
        return uuid
    return label(uuid, titles[uuid], payload)


def item_lines(labels: list[str], cap: int = PREVIEW_LINE_CAP, indent: str = "  ") -> str:
    """Bulleted lines (capped) with a leading newline, or '' when empty."""
    if not labels:
        return ""
    lines = [f"{indent}- {s}" for s in labels[:cap]]
    if len(labels) > cap:
        lines.append(f"{indent}…and {len(labels) - cap} more")
    return "\n" + "\n".join(lines)


def todo_lines(uuids: list[str], payload: dict, key: str = "todo_titles") -> str:
    """Per-to-do lines for bulk previews; '' for legacy payloads without titles."""
    titles = payload.get(key)
    if not isinstance(titles, dict):
        return ""
    return item_lines([fmt_map(u, titles, payload) for u in uuids])
