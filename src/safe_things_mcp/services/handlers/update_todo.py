"""``update_todo`` handler — edit fields of an existing to-do.

**Pattern-setter for every non-add mutation in V2.** The shape below
(snapshot before / apply via URL scheme / restore via inverse URL on
undo) is what ``move_todo``, ``delete_todo``, project edits, and bulk
variants all reuse. Keep this module clean and well-commented; it's the
template.

### First-cut scope

Supports updates to: ``title``, ``notes``, ``deadline``, ``tags``.

``when`` is intentionally **not** supported in the first cut — restoring
the original ``when`` cleanly across all of Things' scheduling states
(``Inbox`` / ``Today`` / specific date / ``Anytime`` / ``Someday`` /
``Upcoming``) requires a richer field mapping. Deferred to a follow-up;
the architectural pattern doesn't change.

### Undo strategy

The undo log captures the **full** to-do row pre-mutation (forensics)
plus a focused ``inverse_fields`` dict containing only the fields the
proposal changed, mapped back into URL-scheme format. Undo issues a
single ``things:///update`` call restoring those specific fields, so any
*other* edits the user made manually in Things between confirm and undo
are preserved.

### Auth

``things:///update`` is auth-gated by Cultured Code. ``THINGS_AUTH_TOKEN``
must be set; both execute and undo fail with an actionable error if it
isn't.
"""
from __future__ import annotations

import asyncio
from typing import Any

from ... import config
from .. import things_repo, url_scheme
from .. import preview_names as pn
from .. import ref_checks
from ...state import undo_log

KIND = "update_todo"

# Fields the propose call accepts AND that undo can faithfully restore.
# Keep this list small and well-tested — every entry is a contract.
_UPDATABLE_FIELDS = ("title", "notes", "deadline", "tags")


def make_preview(payload: dict) -> str:
    """One-line summary of what the proposal will change.

    Empty strings render as ``(cleared)`` so the user sees that the field
    is being removed, not set to the literal empty string.
    """
    todo = pn.fmt(payload["todo_id"], payload, "todo_title")
    changes: list[str] = []
    for f in _UPDATABLE_FIELDS:
        v = payload.get(f)
        if v is None:
            continue
        if isinstance(v, list):
            v_str = "(cleared)" if not v else f"[{','.join(v)}]"
        elif isinstance(v, str):
            v_str = "(cleared)" if v == "" else repr(v)
        else:
            v_str = repr(v)
        changes.append(f"{f}={v_str}")
    body = ", ".join(changes) if changes else "(no fields)"
    return f"Update to-do {todo}: {body}"


async def execute(payload: dict) -> dict:
    """Apply a multi-field update to one to-do.

    1. Validate inputs (auth token set, at least one field present,
       to-do exists).
    2. Snapshot the full pre-mutation row.
    3. Compute ``inverse_fields`` — what the URL-scheme call would need
       to look like to put each changed field back where it was.
    4. Write undo_log row *before* the URL launch (CLAUDE.md hard rule).
    5. Launch ``things:///update?id=X&<fields>&auth-token=Y``.
    6. Poll for the ``modified`` timestamp to advance past pre-launch.
    7. Patch the undo_log row with after_state (verified row).
    """
    todo_id = payload["todo_id"]

    fields = {k: payload[k] for k in _UPDATABLE_FIELDS if payload.get(k) is not None}
    if not fields:
        raise ValueError(
            f"propose_update_todo for {todo_id!r} has no fields to update. "
            f"Pass at least one of: {', '.join(_UPDATABLE_FIELDS)}."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "update_todo requires THINGS_AUTH_TOKEN. Generate one in "
            "Things → Settings → General → Enable Things URLs → Manage, "
            "then export THINGS_AUTH_TOKEN before retrying."
        )

    before = things_repo.get_todo(todo_id)
    if before is None:
        raise ValueError(
            f"No to-do found with id={todo_id!r}. It may have been deleted "
            "or the id may be wrong. Use list/search tools to find it."
        )
    # Refuse project/heading/area ids: acting on them would hit the whole container.
    ref_checks.require_todo(todo_id, before)

    inverse_fields = {f: _normalize_for_undo(f, before) for f in fields}
    pre_modified = before.get("modified") or ""

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=todo_id,
        before_state={
            "full": before,
            "inverse_fields": inverse_fields,
            "changed": list(fields.keys()),
        },
        after_state=None,
    )

    url = url_scheme.build_update_url(
        id=todo_id,
        auth_token=auth_token,
        title=fields.get("title"),
        notes=fields.get("notes"),
        deadline=fields.get("deadline"),
        tags=fields.get("tags"),
    )
    await url_scheme.launch(url)

    verified = await _poll_for_modified_advance(todo_id, pre_modified)
    undo_log.attach_target(entry_id, target_uuid=todo_id, after_state=verified)

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "id": todo_id,
        "title": verified.get("title"),
        "changed_fields": list(fields.keys()),
    }


async def undo(undo_entry: dict) -> dict:
    """Reverse an update by re-applying the captured ``inverse_fields``.

    Only the originally-changed fields are restored — concurrent manual
    edits to *other* fields (made between confirm and undo) survive.
    """
    target_uuid = undo_entry.get("target_uuid")
    before = undo_entry.get("before_state")
    if not target_uuid or not isinstance(before, dict):
        raise RuntimeError(
            f"undo_log entry {undo_entry.get('id')!r} has no target_uuid "
            "or before_state; original update may have failed mid-flight."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "Cannot undo update_todo without THINGS_AUTH_TOKEN. Set it "
            "(Things → Settings → General → Enable Things URLs → Manage) "
            "and retry."
        )

    inverse_fields: dict[str, Any] = before.get("inverse_fields") or {}
    if not inverse_fields:
        undo_log.delete(undo_entry["id"])
        return {
            "undone": True,
            "action_kind": KIND,
            "target_uuid": target_uuid,
            "note": "No fields needed restoration.",
        }

    current = things_repo.get_todo(target_uuid)
    if current is None:
        raise RuntimeError(
            f"to-do {target_uuid} no longer exists; cannot restore."
        )
    pre_modified = current.get("modified") or ""

    url = url_scheme.build_update_url(
        id=target_uuid,
        auth_token=auth_token,
        title=inverse_fields.get("title"),
        notes=inverse_fields.get("notes"),
        deadline=inverse_fields.get("deadline"),
        tags=inverse_fields.get("tags"),
    )
    await url_scheme.launch(url)

    await _poll_for_modified_advance(target_uuid, pre_modified)
    undo_log.delete(undo_entry["id"])

    return {
        "undone": True,
        "action_kind": KIND,
        "target_uuid": target_uuid,
        "restored_fields": list(inverse_fields.keys()),
    }


# ---------- internals ----------


def _normalize_for_undo(field: str, before_row: dict) -> Any:
    """Map a Things row's field value back into the URL-scheme format
    that ``update`` accepts.

    Conventions:
    * ``""`` clears a string field (``title`` / ``notes`` / ``deadline``).
      Title clearing is technically invalid in Things (titles must be
      non-empty); we leave that to the Things app to ignore.
    * ``[]`` clears all tags.
    * Otherwise the value passes through unchanged (ISO date string for
      deadline; tag-name list for tags).
    """
    val = before_row.get(field)
    if field == "tags":
        return val if isinstance(val, list) else []
    if val is None:
        return ""
    return val


async def _poll_for_modified_advance(todo_id: str, prev_modified: str) -> dict:
    """Wait until the to-do's ``modified`` column advances past
    ``prev_modified`` (seconds-resolution), or the timeout elapses.

    No-op updates (e.g. setting a field to the value it already had)
    won't advance ``modified`` — we treat that as success and return the
    current row. A timeout WITHOUT a vanished task is recoverable; the
    update may still process out-of-band.
    """
    deadline = asyncio.get_running_loop().time() + config.WRITE_POLL_TIMEOUT_SECONDS
    last_row: dict | None = None
    while True:
        row = things_repo.get_todo(todo_id)
        if row is None:
            raise RuntimeError(
                f"to-do {todo_id} disappeared during update; cannot verify."
            )
        last_row = row
        if (row.get("modified") or "") > prev_modified:
            return row
        if asyncio.get_running_loop().time() >= deadline:
            return last_row  # graceful fallback — modified didn't advance
        await asyncio.sleep(config.WRITE_POLL_INTERVAL_SECONDS)
