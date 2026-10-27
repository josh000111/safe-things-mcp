"""``update_project`` handler — edit fields of an existing project.

Mirrors :mod:`update_todo` (same before-state-snapshot + inverse-fields
pattern) but targets a Things *project* via ``things:///update-project``.

### First-cut scope

Supports updates to: ``title``, ``notes``, ``deadline``, ``tags``,
``area_id``. ``when`` is deferred (same rationale as update_todo).

### Undo strategy

The undo log captures the full project row pre-mutation plus an
``inverse_fields`` dict containing only the fields the proposal changed
(mapped back into URL-scheme format). Undo issues a single
``things:///update-project`` call restoring those fields, leaving any
concurrent manual edits to *other* fields alone.

### Auth

``things:///update-project`` is auth-gated. ``THINGS_AUTH_TOKEN`` must be
set; both execute and undo fail with an actionable error if it isn't.
"""
from __future__ import annotations

import asyncio
from typing import Any

from ... import config
from .. import things_repo, url_scheme
from ...state import undo_log

KIND = "update_project"

# Fields the propose call accepts AND that undo can faithfully restore.
_UPDATABLE_FIELDS = ("title", "notes", "deadline", "tags", "area_id")


def make_preview(payload: dict) -> str:
    """One-line summary of what the proposal will change.

    Empty strings render as ``(cleared)`` so the user sees that the field
    is being removed, not set to the literal empty string.
    """
    project_id = payload["project_id"]
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
    return f"Update project {project_id}: {body}"


async def execute(payload: dict) -> dict:
    project_id = payload["project_id"]

    fields = {k: payload[k] for k in _UPDATABLE_FIELDS if payload.get(k) is not None}
    if not fields:
        raise ValueError(
            f"propose_update_project for {project_id!r} has no fields to "
            f"update. Pass at least one of: {', '.join(_UPDATABLE_FIELDS)}."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "update_project requires THINGS_AUTH_TOKEN. Generate one in "
            "Things → Settings → General → Enable Things URLs → Manage, "
            "then export THINGS_AUTH_TOKEN before retrying."
        )

    before = things_repo.get_project_row(project_id)
    if before is None:
        raise ValueError(
            f"No project found with id={project_id!r}. It may have been "
            "deleted or the id may be wrong. Use list/search tools to find it."
        )

    inverse_fields = {f: _normalize_for_undo(f, before) for f in fields}
    pre_modified = before.get("modified") or ""

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=project_id,
        before_state={
            "full": before,
            "inverse_fields": inverse_fields,
            "changed": list(fields.keys()),
        },
        after_state=None,
    )

    url = url_scheme.build_update_project_url(
        id=project_id,
        auth_token=auth_token,
        title=fields.get("title"),
        notes=fields.get("notes"),
        deadline=fields.get("deadline"),
        tags=fields.get("tags"),
        area_id=fields.get("area_id"),
    )
    await url_scheme.launch(url)

    verified = await _poll_for_modified_advance(project_id, pre_modified)
    undo_log.attach_target(entry_id, target_uuid=project_id, after_state=verified)

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "id": project_id,
        "title": verified.get("title"),
        "changed_fields": list(fields.keys()),
    }


async def undo(undo_entry: dict) -> dict:
    """Reverse an update by re-applying the captured ``inverse_fields``."""
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
            "Cannot undo update_project without THINGS_AUTH_TOKEN. Set it "
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

    current = things_repo.get_project_row(target_uuid)
    if current is None:
        raise RuntimeError(
            f"project {target_uuid} no longer exists; cannot restore."
        )
    pre_modified = current.get("modified") or ""

    url = url_scheme.build_update_project_url(
        id=target_uuid,
        auth_token=auth_token,
        title=inverse_fields.get("title"),
        notes=inverse_fields.get("notes"),
        deadline=inverse_fields.get("deadline"),
        tags=inverse_fields.get("tags"),
        area_id=inverse_fields.get("area_id"),
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


def _normalize_for_undo(field: str, before_row: dict) -> Any:
    """Map a project row's field value back into the URL-scheme format
    that ``update-project`` accepts.

    * ``""`` clears string fields (``title`` / ``notes`` / ``deadline`` /
      ``area_id``).
    * ``[]`` clears all tags.
    * Otherwise the value passes through unchanged.

    Note: in things.py, project membership in an area is stored as
    ``area`` (UUID), not ``area_id`` — handle both keys defensively.
    """
    if field == "tags":
        val = before_row.get("tags")
        return val if isinstance(val, list) else []
    if field == "area_id":
        val = before_row.get("area") or before_row.get("area_id")
        return val if val is not None else ""
    val = before_row.get(field)
    if val is None:
        return ""
    return val


async def _poll_for_modified_advance(project_id: str, prev_modified: str) -> dict:
    """Wait for the project's ``modified`` column to advance.

    No-op updates won't bump ``modified`` — return the current row
    gracefully after the timeout (same convention as update_todo).
    """
    deadline = asyncio.get_running_loop().time() + config.WRITE_POLL_TIMEOUT_SECONDS
    last_row: dict | None = None
    while True:
        row = things_repo.get_project_row(project_id)
        if row is None:
            raise RuntimeError(
                f"project {project_id} disappeared during update; cannot verify."
            )
        last_row = row
        if (row.get("modified") or "") > prev_modified:
            return row
        if asyncio.get_running_loop().time() >= deadline:
            return last_row
        await asyncio.sleep(config.WRITE_POLL_INTERVAL_SECONDS)
