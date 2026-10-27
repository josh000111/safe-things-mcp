"""``move_todo`` handler — change a to-do's list/schedule.

Move semantics in Things are dimensional:

* **Scheduling dimension** — Inbox / Today / Anytime / Someday / a future date.
  In Things data this is captured by ``start`` + ``start_date``. Changes
  to this dimension preserve project/area membership.
* **Project/area dimension** — which project or area the task lives in.
  In Things data this is the ``project`` (or ``area``) UUID. Changes
  here preserve scheduling.

This handler accepts a single ``target`` argument and infers which
dimension it represents:

* ``inbox`` → scheduling move via AppleScript (requires ALLOW_APPLESCRIPT)
* ``today`` / ``anytime`` / ``someday`` → scheduling move via ``when=``
* a 22-char UUID → project/area move via ``list-id=``
* ``upcoming`` / ``logbook`` / ``trash`` → rejected with hint

The undo restores **only the dimension that was changed**, leaving the
other dimension alone (so cross-dimensional manual edits made between
confirm and undo survive).

Requires ``THINGS_AUTH_TOKEN``.
"""
from __future__ import annotations

import asyncio
from typing import Any

from ... import config
from .. import applescript, things_repo, url_scheme
from ...state import undo_log

KIND = "move_todo"

_WHEN_KEYWORDS = {"today", "anytime", "someday"}
# Computed views and destructive targets: not valid move destinations.
_REJECT_KEYWORDS = {"upcoming", "logbook", "trash"}


def make_preview(payload: dict) -> str:
    return f"Move to-do {payload['todo_id']} to {payload['target']!r}"


async def execute(payload: dict) -> dict:
    todo_id = payload["todo_id"]
    target = payload["target"]
    target_lower = target.strip().lower()

    if target_lower in _REJECT_KEYWORDS:
        raise ValueError(
            f"target={target!r} not supported by propose_move_todo. "
            "Supported targets: 'inbox' (requires SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1), "
            "'today', 'anytime', 'someday', or a project/area UUID."
        )
    if not target:
        raise ValueError("target is required")

    if target_lower == "inbox" and not config.ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "Moving to Inbox requires SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1. "
            "Set the environment variable and restart the MCP server."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "move_todo requires THINGS_AUTH_TOKEN. Generate one in "
            "Things → Settings → General → Enable Things URLs → Manage, "
            "then export it before retrying."
        )

    before = things_repo.get_todo(todo_id)
    if before is None:
        raise ValueError(
            f"No to-do found with id={todo_id!r}. It may have been deleted "
            "or the id may be wrong."
        )

    # Decide which dimension we're moving along, and capture the inverse
    # params that will put the task back where it was.
    if target_lower == "inbox":
        move_params: dict[str, Any] = {}  # handled via AppleScript below
        # Moving to Inbox is cross-dimensional: it changes the schedule AND
        # removes the task from its project. Capture BOTH so undo restores both.
        inverse_params = _inverse_scheduling(before)
        original_project = before.get("project")
        if original_project:
            inverse_params["list_id"] = original_project
        dimension = "inbox"
    elif target_lower in _WHEN_KEYWORDS:
        move_params = {"when": target_lower}
        inverse_params = _inverse_scheduling(before)
        dimension = "schedule"
    else:
        # Treat anything else as a project/area UUID
        move_params = {"list_id": target}
        inverse_params = _inverse_project(before)
        dimension = "project"

    pre_modified = before.get("modified") or ""

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=todo_id,
        before_state={
            "full": before,
            "inverse_params": inverse_params,
            "dimension": dimension,
            "target": target,
        },
        after_state=None,
    )

    if dimension == "inbox":
        safe_id = applescript.escape(todo_id)
        script = (
            f'tell application "Things3"\n'
            f'    move to do id "{safe_id}" to list "Inbox"\n'
            f'end tell'
        )
        await applescript.run_script(script)
    else:
        url = url_scheme.build_update_url(
            id=todo_id,
            auth_token=auth_token,
            **move_params,
        )
        await url_scheme.launch(url)

    verified = await _poll_for_modified_advance(todo_id, pre_modified)
    undo_log.attach_target(entry_id, target_uuid=todo_id, after_state=verified)

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "id": todo_id,
        "target": target,
        "dimension": dimension,
        "title": verified.get("title"),
    }


async def undo(undo_entry: dict) -> dict:
    target_uuid = undo_entry.get("target_uuid")
    before = undo_entry.get("before_state")
    if not target_uuid or not isinstance(before, dict):
        raise RuntimeError(
            f"undo_log entry {undo_entry.get('id')!r} has no target_uuid "
            "or before_state; original move may have failed mid-flight."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "Cannot undo move_todo without THINGS_AUTH_TOKEN. Set it and "
            "retry."
        )

    inverse_params: dict[str, Any] = before.get("inverse_params") or {}
    if not inverse_params:
        undo_log.delete(undo_entry["id"])
        return {
            "undone": True,
            "action_kind": KIND,
            "target_uuid": target_uuid,
            "note": "No restoration needed (no recorded inverse).",
        }

    current = things_repo.get_todo(target_uuid)
    if current is None:
        raise RuntimeError(
            f"to-do {target_uuid} no longer exists; cannot restore."
        )
    pre_modified = current.get("modified") or ""

    if inverse_params.get("to_inbox"):
        if not config.ALLOW_APPLESCRIPT:
            raise RuntimeError(
                "Cannot undo move_todo back to Inbox without "
                "SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1. Set it and retry."
            )
        safe_id = applescript.escape(target_uuid)
        script = (
            f'tell application "Things3"\n'
            f'    move to do id "{safe_id}" to list "Inbox"\n'
            f'end tell'
        )
        await applescript.run_script(script)
    else:
        url = url_scheme.build_update_url(
            id=target_uuid,
            auth_token=auth_token,
            **inverse_params,
        )
        await url_scheme.launch(url)

    await _poll_for_modified_advance(target_uuid, pre_modified)
    undo_log.delete(undo_entry["id"])

    return {
        "undone": True,
        "action_kind": KIND,
        "target_uuid": target_uuid,
        "restored_dimension": before.get("dimension"),
    }


# ---------- internals ----------


def _inverse_scheduling(before_row: dict) -> dict[str, Any]:
    """Compute the params that restore the original scheduling.

    Cases:
    * Had a specific start_date → ``when=<YYYY-MM-DD>``.
    * Was in today/anytime/someday → ``when=<keyword>``.
    * Was in Inbox → ``{"to_inbox": True}`` sentinel (requires AppleScript).
    * Unknown → best-effort ``when=anytime``.
    """
    start_date = before_row.get("start_date")
    if start_date:
        return {"when": start_date}
    start = (before_row.get("start") or "Anytime").lower()
    if start in _WHEN_KEYWORDS:
        return {"when": start}
    if start == "inbox":
        return {"to_inbox": True}
    return {"when": "anytime"}


def _inverse_project(before_row: dict) -> dict[str, Any]:
    """Compute the params that restore the original project membership.

    Cases:
    * Was in a project → ``list_id=<original_project_uuid>``.
    * Was in Inbox (start="Inbox", no project) → ``{"to_inbox": True}``
      sentinel (requires AppleScript on undo).
    * Was unassigned/scheduled but not in any project → ``list_id=""``
      (clears the new project assignment; task stays in its schedule).
    """
    original_project = before_row.get("project")
    if original_project:
        return {"list_id": original_project}
    start = (before_row.get("start") or "").lower()
    if start == "inbox":
        return {"to_inbox": True}
    return {"list_id": ""}


async def _poll_for_modified_advance(todo_id: str, prev_modified: str) -> dict:
    """Wait for the ``modified`` column to advance past ``prev_modified``.

    No-op moves (e.g. moving a task to where it already is) won't bump
    ``modified`` — return gracefully after the timeout.
    """
    deadline = asyncio.get_running_loop().time() + config.WRITE_POLL_TIMEOUT_SECONDS
    last_row: dict | None = None
    while True:
        row = things_repo.get_todo(todo_id)
        if row is None:
            raise RuntimeError(
                f"to-do {todo_id} disappeared during move; cannot verify."
            )
        last_row = row
        if (row.get("modified") or "") > prev_modified:
            return row
        if asyncio.get_running_loop().time() >= deadline:
            return last_row
        await asyncio.sleep(config.WRITE_POLL_INTERVAL_SECONDS)
