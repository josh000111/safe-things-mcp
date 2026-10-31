"""Propose-time display-name lookups for confirmation previews.

The preview a user approves must show names, not bare UUIDs. ``for_*``
helpers read Things (read-only, via ``things_repo``) and return extra payload
keys; ``fmt*`` helpers render them inside ``make_preview``.

Contract: key present with a value -> ``'Name' (uuid)``; key present but
``None`` -> ``uuid (not found)`` (the item genuinely does not exist); key
absent (a payload staged before this module existed, or a hand-built test
payload) -> bare ``uuid``. All stored values are JSON-serializable (payloads
persist in state.db).

Failure policy: only "no such uuid" renders as "(not found)". A DB that can't
be read (``config.ThingsDBAccessError`` or any other read error) propagates so
propose fails loudly instead of showing a misleading "(not found)" on a
destructive action. ``for_project`` / ``for_area`` / ``for_destination`` /
``for_heading(s)`` also raise ``ValueError`` when the UUID exists but is the
wrong kind, or (headings) when execute would refuse it.
"""
from __future__ import annotations

from typing import Any, Iterable

from . import ref_checks, things_repo
from .ref_checks import KEYWORD_LISTS  # noqa: F401  (re-exported)

# Max item lines in a bulk preview before collapsing to "...and N more".
PREVIEW_LINE_CAP = 20


# ---------- lookups ----------


def _title(row: Any) -> str | None:
    if isinstance(row, dict):
        return row.get("title") or row.get("name") or None
    return None


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


def for_todo(todo_id: str) -> dict[str, Any]:
    """Propose-time to-do lookup. Raises ValueError if the uuid is a project /
    heading / area, so every ``propose_*`` that takes a to-do id refuses it here
    (execute re-checks)."""
    return {"todo_title": _title(ref_checks.check_todo(todo_id))}


def for_project(project_id: str) -> dict[str, Any]:
    return {"project_title": project_title(project_id)}


def for_todos(todo_ids: Iterable[str]) -> dict[str, Any]:
    """Titles for a batch; raises ValueError naming every non-to-do id."""
    rows = ref_checks.check_todos(todo_ids or [])
    return {"todo_titles": {u: _title(r) for u, r in rows.items()}}


def for_destination(dest_id: str | None) -> dict[str, Any]:
    """``destination_title`` for a non-keyword list_id/target; ``{}`` otherwise."""
    if not _is_destination_id(dest_id):
        return {}
    return {"destination_title": destination_title(dest_id)}


def for_area(area_id: str | None) -> dict[str, Any]:
    if not area_id:
        return {}
    return {"area_title": area_title(area_id)}


def _resolve_heading(project_id: str, ref: str, action: str) -> tuple[str, str | None]:
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
    return uuid, _title(things_repo.get_todo(uuid))


def for_heading(project_id: str, ref: str, action: str = "delete") -> dict[str, Any]:
    uuid, title = _resolve_heading(project_id, ref, action)
    return {
        "project_title": project_title(project_id),
        "heading_uuid": uuid,
        "heading_title": title,
    }


def for_headings(project_id: str, refs: list[str], action: str = "delete") -> dict[str, Any]:
    items = []
    for ref in refs or []:
        uuid, title = _resolve_heading(project_id, ref, action)
        items.append({"ref": ref, "uuid": uuid, "title": title})
    return {"project_title": project_title(project_id), "heading_items": items}


def container_titles(container_type: str, container_id: str, uuids: list[str]) -> dict[str, str | None]:
    """Titles for to-dos in a reorder container, read from one container fetch."""
    if container_type == "project":
        rows = (things_repo.project(container_id) or {}).get("items") or []
    else:
        rows = getattr(things_repo, container_id.lower())()
    by_id = {r.get("uuid"): r.get("title") for r in rows}
    return {u: (by_id.get(u) or todo_title(u)) for u in dict.fromkeys(uuids or [])}


# ---------- rendering (used by handlers' make_preview) ----------


def fmt(uuid: str | None, payload: dict, title_key: str) -> str:
    """``'Name' (uuid)``, ``uuid (not found)``, or bare ``uuid`` (legacy payload)."""
    uuid = uuid or ""
    if title_key not in payload:
        return uuid
    title = payload[title_key]
    return f"'{title}' ({uuid})" if title else f"{uuid} (not found)"


def fmt_destination(target: str | None, payload: dict, quote_keyword: bool = True) -> str:
    """Keyword targets render as-is (quoted unless told otherwise); UUID targets
    get name + uuid."""
    if not _is_destination_id(target) or "destination_title" not in payload:
        return repr(target) if quote_keyword else str(target)
    return fmt(target, payload, "destination_title")


def fmt_heading(ref: str, payload: dict) -> str:
    """Heading ref rendered with its resolved title + uuid; legacy payloads
    keep the raw ref (a UUID or a name)."""
    if "heading_title" not in payload:
        return repr(ref)
    title = payload["heading_title"]
    uuid = payload.get("heading_uuid") or ref
    return f"'{title}' ({uuid})" if title else f"{ref} (not found)"


def fmt_map(uuid: str, titles: dict | None) -> str:
    if titles is None or uuid not in titles:
        return uuid
    t = titles[uuid]
    return f"'{t}' ({uuid})" if t else f"{uuid} (not found)"


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
    return item_lines([fmt_map(u, titles) for u in uuids])
