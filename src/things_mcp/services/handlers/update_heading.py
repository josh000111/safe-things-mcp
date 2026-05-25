"""``update_heading`` handler — rename a dummy heading in a project.

Only dummy headings (``__NAME__`` format) can be renamed here. Native
headings require AppleScript (step 5).

Resolution logic:
- If ``heading_id_or_name`` looks like a Things UUID, resolve it directly
  and verify it is a dummy heading.
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
    return (
        f"Rename heading {heading_ref!r} to {new_dummy!r} "
        f"in project {payload.get('project_id', '')}"
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

    # Resolve the heading UUID.
    heading_uuid = _resolve_heading_uuid(project_id, heading_id_or_name)

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


def _resolve_heading_uuid(project_id: str, heading_id_or_name: str) -> str:
    """Return the UUID of the dummy heading task.

    If heading_id_or_name resolves directly via get_todo, use it.
    Otherwise scan the project items by name.
    """
    # Try direct UUID lookup first.
    row = things_repo.get_todo(heading_id_or_name)
    if row is not None:
        # It's a valid UUID reference — validate it's a dummy heading.
        if not is_dummy_heading(row.get("title", "")):
            raise ValueError(
                f"Task {heading_id_or_name!r} (title={row.get('title')!r}) is not a "
                "dummy heading. Only dummy headings (__NAME__ format) can be "
                "renamed with update_heading."
            )
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
    proj = things_repo.project(project_id)
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
            if extracted.lower() == name.upper().lower():
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
