"""``update_heading`` handler — rename a dummy heading in a project.

Only dummy headings (``__NAME__`` format) can be renamed here. Native
headings require AppleScript (step 5).

Resolution logic:
- If ``heading_id_or_name`` is a Things UUID, resolve it directly and verify
  it is a dummy heading that belongs to ``project_id`` (a UUID from another
  project is refused).
- A propose-time payload also pins ``heading_uuid``; execute then acts on
  exactly that UUID (re-verified), never re-resolving by name.
- Otherwise treat it as a heading name, scan the project items for
  matching dummy headings (and native headings for ambiguity detection).
- If ambiguous (multiple matches across dummy and/or native), raise
  ``ValueError`` listing candidates with their UUIDs and types.

Requires ``THINGS_AUTH_TOKEN``.
"""
from __future__ import annotations

import asyncio

from ... import config
from .. import things_repo, url_scheme
from .. import preview_names as pn
from .. import ref_checks
from ...state import undo_log
from .dummy_heading import make_dummy_title, is_dummy_heading, extract_name_from_dummy

KIND = "update_heading"


def make_preview(payload: dict) -> str:
    heading_ref = payload.get("heading_id_or_name", "")
    new_name = payload.get("new_name", "")
    try:
        new_dummy = make_dummy_title(new_name)
    except ValueError:
        new_dummy = f"__{new_name.upper()}__"
    project = pn.fmt(payload.get("project_id", ""), payload, "project_title")
    return (
        f"Rename heading {pn.fmt_heading(heading_ref, payload)} to {new_dummy!r} "
        f"in project {project}"
    )


async def execute(payload: dict) -> dict:
    """Rename a dummy heading.

    1. Resolve heading UUID.
    2. Validate it is a dummy heading.
    3. Compute new dummy title.
    4. Snapshot before_state.
    5. Write undo_log row BEFORE URL launch (CLAUDE.md hard rule).
    6. Launch things:///update.
    7. Poll for modified advance.
    8. Patch undo_log.
    """
    project_id = payload["project_id"]
    heading_id_or_name = payload["heading_id_or_name"]
    new_name = payload["new_name"]

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "update_heading requires THINGS_AUTH_TOKEN. Generate one in "
            "Things → Settings → General → Enable Things URLs → Manage, "
            "then export THINGS_AUTH_TOKEN before retrying."
        )

    new_dummy_title = make_dummy_title(new_name)

    # Resolve the heading UUID. A UUID pinned at propose time wins over the
    # name, so confirm acts on exactly what the preview showed.
    heading_uuid = resolve_pinned_or_ref(
        payload, project_id, heading_id_or_name, "renamed", _resolve_heading_uuid
    )

    before = things_repo.get_todo(heading_uuid)
    if before is None:
        raise ValueError(
            f"Heading task {heading_uuid!r} not found. "
            "It may have been deleted."
        )
    if not is_dummy_heading(before.get("title", "")):
        raise ValueError(
            f"Task {heading_uuid!r} (title={before.get('title')!r}) is not a "
            "dummy heading. Only dummy headings (__NAME__ format) can be "
            "renamed with update_heading. Native headings require AppleScript (step 5)."
        )

    pre_modified = before.get("modified") or ""
    old_title = before.get("title", "")

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=heading_uuid,
        before_state={"full": before, "title": old_title},
        after_state=None,
    )

    url = url_scheme.build_update_url(
        id=heading_uuid,
        auth_token=auth_token,
        title=new_dummy_title,
    )
    await url_scheme.launch(url)

    verified = await _poll_for_modified_advance(heading_uuid, pre_modified)
    undo_log.attach_target(entry_id, target_uuid=heading_uuid, after_state=verified)

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "id": heading_uuid,
        "old_title": old_title,
        "new_title": verified.get("title", new_dummy_title),
        "project_id": project_id,
    }


async def undo(undo_entry: dict) -> dict:
    """Restore original dummy heading title."""
    target_uuid = undo_entry.get("target_uuid")
    before = undo_entry.get("before_state")
    if not target_uuid or not isinstance(before, dict):
        raise RuntimeError(
            f"undo_log entry {undo_entry.get('id')!r} has no target_uuid "
            "or before_state."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "Cannot undo update_heading without THINGS_AUTH_TOKEN. Set it "
            "and retry."
        )

    old_title = before.get("title", "")
    current = things_repo.get_todo(target_uuid)
    if current is None:
        raise RuntimeError(
            f"Heading task {target_uuid!r} no longer exists; cannot restore."
        )
    pre_modified = current.get("modified") or ""

    url = url_scheme.build_update_url(
        id=target_uuid,
        auth_token=auth_token,
        title=old_title,
    )
    await url_scheme.launch(url)

    await _poll_for_modified_advance(target_uuid, pre_modified)
    undo_log.delete(undo_entry["id"])

    return {
        "undone": True,
        "action_kind": KIND,
        "target_uuid": target_uuid,
        "restored_title": old_title,
    }


# ---------- internals ----------


def verify_heading_row(project_id: str, ref: str, row: dict, verb: str) -> None:
    """Raise unless ``row`` is a dummy heading that belongs to ``project_id``.

    Fixes the cross-project hole where any heading UUID was accepted without
    checking which project it lived in. Membership: the row's own ``project``,
    or (for a to-do nested under a native heading) that heading's project.
    """
    title = row.get("title", "")
    if row.get("type") not in (None, "to-do") or not is_dummy_heading(title):
        raise ValueError(
            f"Task {ref!r} (title={title!r}, type={row.get('type')!r}) is not a "
            f"dummy heading. Only dummy headings (__NAME__ format) can be "
            f"{verb} here. Native headings require AppleScript (step 5)."
        )
    owner = row.get("project")
    if owner is None and row.get("heading"):
        parent = things_repo.get_todo(row["heading"])
        owner = (parent or {}).get("project")
    if owner != project_id:
        raise ValueError(
            f"Heading {ref!r} (title={title!r}) does not belong to project "
            f"{project_id!r} (it is in project {owner!r}). Refusing to act on a "
            "heading outside the given project."
        )


def resolve_pinned_or_ref(payload: dict, project_id: str, ref: str, verb: str, fallback) -> str:
    """UUID execute must act on: the propose-time pinned ``heading_uuid`` if
    present (re-checked to still exist and still belong to the project), else
    the legacy name/UUID resolution (``fallback``) for payloads staged before
    pinning."""
    pinned = payload.get("heading_uuid")
    if not pinned:
        return fallback(project_id, ref)
    return resolve_pinned_heading_uuid(project_id, pinned, verb)


def resolve_pinned_heading_uuid(project_id: str, pinned: str, verb: str) -> str:
    row = things_repo.get_todo(pinned)
    if row is None:
        raise ValueError(
            f"Heading {pinned!r} (pinned when this action was proposed) no longer "
            "exists. Re-propose the action."
        )
    verify_heading_row(project_id, pinned, row, verb)
    return pinned


def _resolve_heading_uuid(project_id: str, heading_id_or_name: str) -> str:
    """Return the UUID of the dummy heading task.

    If heading_id_or_name resolves directly via get_todo, use it (after
    checking it is a dummy heading IN ``project_id``). Otherwise scan the
    project items by name.
    """
    # Try direct UUID lookup first.
    row = things_repo.get_todo(heading_id_or_name)
    if row is not None:
        verify_heading_row(project_id, heading_id_or_name, row, "renamed")
        return heading_id_or_name

    # Treat as a name — scan project items.
    candidates = _find_dummy_heading_in_project(project_id, heading_id_or_name)
    if not candidates:
        raise ValueError(
            f"No heading named {heading_id_or_name!r} found in project {project_id!r}. "
            "Check the project UUID and heading name, then retry."
        )

    dummy_candidates = [c for c in candidates if c["kind"] == "dummy"]
    native_candidates = [c for c in candidates if c["kind"] == "native"]

    if len(dummy_candidates) == 1 and not native_candidates:
        return dummy_candidates[0]["uuid"]

    # Ambiguous.
    candidate_details = "; ".join(
        f"{c['uuid']!r} ({c['kind']}, title={c['title']!r})" for c in candidates
    )
    raise ValueError(
        f"Ambiguous heading name {heading_id_or_name!r} in project {project_id!r}. "
        f"Multiple matches: {candidate_details}. "
        "Retry with the specific dummy heading UUID."
    )


def _find_dummy_heading_in_project(project_id: str, name: str) -> list[dict]:
    """Return list of matching heading candidates in the project.

    Checks both dummy headings (__NAME__) and native headings for the
    same name, to enable ambiguity detection.
    Returns list of {"uuid": ..., "title": ..., "kind": "dummy"|"native"}.
    """
    proj = ref_checks.check_project(project_id)
    if proj is None:
        raise ValueError(f"Project {project_id!r} not found.")

    candidates = []
    for item in (proj.get("items") or []):
        item_title = item.get("title", "")
        item_type = item.get("type", "")
        item_uuid = item.get("uuid", "")

        if item_type == "heading" and item_title.lower() == name.lower():
            candidates.append({"uuid": item_uuid, "title": item_title, "kind": "native"})
        elif item_type == "to-do" and is_dummy_heading(item_title):
            extracted = extract_name_from_dummy(item_title)
            if extracted.lower() == name.lower():
                candidates.append({"uuid": item_uuid, "title": item_title, "kind": "dummy"})

    return candidates


async def _poll_for_modified_advance(todo_id: str, prev_modified: str) -> dict:
    deadline = asyncio.get_running_loop().time() + config.WRITE_POLL_TIMEOUT_SECONDS
    last_row: dict | None = None
    while True:
        row = things_repo.get_todo(todo_id)
        if row is None:
            raise RuntimeError(
                f"Heading task {todo_id!r} disappeared during update."
            )
        last_row = row
        if (row.get("modified") or "") > prev_modified:
            return row
        if asyncio.get_running_loop().time() >= deadline:
            return last_row
        await asyncio.sleep(config.WRITE_POLL_INTERVAL_SECONDS)
