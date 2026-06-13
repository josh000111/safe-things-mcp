"""``move_under_ai_heading`` handler — move tasks into an existing project
under a ``__NEWLY ADDED BY AI__`` marker heading.

Algorithm:
1. Validate project and all todos exist (fail-fast before any mutation).
2. Capture prior to-do order and per-task inverse project membership.
3. Write undo_log row BEFORE any mutation (CLAUDE.md V2 gate).
4. Find-or-create the marker (idempotent — reuses existing marker if present).
5. Patch the undo_log with marker_uuid and marker_created.
6. Move each todo into the project via URL scheme.
7. Poll each todo until it shows the new project membership (so reorder
   doesn't run against stale state).
8. Reorder: [pre-existing todos] → [marker] → [newly moved todos].

Undo (LIFO): restore prior order → move tasks back → cancel marker if created here.

Requires THINGS_AUTH_TOKEN and THINGS_MCP_ALLOW_APPLESCRIPT=1.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from ... import config
from .. import applescript, things_repo, url_scheme
from ...state import undo_log
from .dummy_heading import AI_NEWLY_ADDED_HEADING
from .move_todo import _inverse_project

KIND = "move_under_ai_heading"

_CREATED_FMT = "%Y-%m-%d %H:%M:%S"


def make_preview(payload: dict) -> str:
    n = len(payload.get("todo_ids") or [])
    project_id = payload.get("project_id", "")
    return (
        f"Move {n} to-do{'s' if n != 1 else ''} into project {project_id!r} "
        f"under '{AI_NEWLY_ADDED_HEADING}' marker (created if absent)"
    )


async def execute(payload: dict) -> dict:
    todo_ids = list(payload.get("todo_ids") or [])
    project_id = payload["project_id"]
    group_id = payload.get("group_id")

    if not todo_ids:
        raise ValueError("todo_ids must be non-empty.")

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "move_under_ai_heading requires THINGS_AUTH_TOKEN. Generate one in "
            "Things → Settings → General → Enable Things URLs → Manage."
        )

    if not config.ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "move_under_ai_heading requires THINGS_MCP_ALLOW_APPLESCRIPT=1. "
            "Set the environment variable and restart the MCP server."
        )

    if things_repo.project(project_id) is None:
        raise ValueError(
            f"Project {project_id!r} not found. "
            "Use list/search tools to find the correct project UUID."
        )

    # Validate all todos exist; filter out the marker if accidentally included.
    items: list[dict[str, Any]] = []
    for uid in todo_ids:
        row = things_repo.get_todo(uid)
        if row is None:
            raise ValueError(
                f"No to-do found with id={uid!r}. Aborting before any mutation."
            )
        if row.get("title") == AI_NEWLY_ADDED_HEADING:
            continue  # silently drop the marker from the move list
        items.append({
            "target_uuid": uid,
            "title": row.get("title"),
            "inverse_params": _inverse_project(row),
        })

    if not items:
        raise ValueError(
            "No valid to-dos to move after filtering. "
            "(All supplied IDs were either missing or the marker itself.)"
        )

    # Capture prior state BEFORE any mutation.
    prior_order = things_repo.get_container_todo_uuids("project", project_id)

    # Write undo_log BEFORE any mutation (V2 acceptance gate).
    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=None,
        before_state={
            "project_id": project_id,
            "prior_order": prior_order,
            "items": items,
            "marker_uuid": None,
            "marker_created": None,
        },
        after_state=None,
        group_id=group_id,
    )

    # Find-or-create the marker (idempotent).
    marker_uuid, marker_created = await _find_or_create_marker(project_id, auth_token)
    undo_log.update_before_state(entry_id, {
        "project_id": project_id,
        "prior_order": prior_order,
        "items": items,
        "marker_uuid": marker_uuid,
        "marker_created": marker_created,
    })

    # Move todos into the project.
    for item in items:
        url = url_scheme.build_update_url(
            id=item["target_uuid"],
            auth_token=auth_token,
            list_id=project_id,
        )
        await url_scheme.launch(url)

    # Poll each todo until Things confirms the new project membership.
    for item in items:
        await _poll_until_in_project(item["target_uuid"], project_id)

    # Reorder: pre-existing (sans marker if pre-existing) → marker → new todos.
    moved_uuids = [item["target_uuid"] for item in items]
    new_order = _build_new_order(prior_order, marker_uuid, moved_uuids)
    await _reorder_project(project_id, new_order)

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "project_id": project_id,
        "marker_uuid": marker_uuid,
        "marker_created": marker_created,
        "moved_count": len(items),
        "final_order": new_order,
    }


async def undo(undo_entry: dict) -> dict:
    before = undo_entry.get("before_state") or {}
    project_id = before.get("project_id")
    prior_order: list[str] = before.get("prior_order") or []
    items: list[dict] = before.get("items") or []
    marker_uuid: str | None = before.get("marker_uuid")
    marker_created: bool | None = before.get("marker_created")

    if not project_id:
        raise RuntimeError(
            f"undo_log entry {undo_entry.get('id')!r} has no project_id; "
            "original action may have failed before logging."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "Cannot undo move_under_ai_heading without THINGS_AUTH_TOKEN."
        )

    if not config.ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "Cannot undo move_under_ai_heading without THINGS_MCP_ALLOW_APPLESCRIPT=1."
        )

    # Step 1: Restore prior to-do order via AppleScript.
    if prior_order:
        await _reorder_project(project_id, prior_order)

    # Step 2: Move tasks back to their original lists.
    inbox_items = [it for it in items if (it.get("inverse_params") or {}).get("to_inbox")]
    url_items = [it for it in items if it not in inbox_items]

    if inbox_items:
        lines = "\n".join(
            f'    move to do id "{applescript.escape(it["target_uuid"])}" to list "Inbox"'
            for it in inbox_items
        )
        script = f'tell application "Things3"\n{lines}\nend tell'
        await applescript.run_script(script)

    for item in url_items:
        inverse_params = item.get("inverse_params") or {}
        if inverse_params:
            url = url_scheme.build_update_url(
                id=item["target_uuid"],
                auth_token=auth_token,
                **inverse_params,
            )
            await url_scheme.launch(url)

    # Step 3: Cancel the marker only if this action created it.
    if marker_created and marker_uuid:
        url = url_scheme.build_update_url(
            id=marker_uuid,
            auth_token=auth_token,
            completed=True,
            canceled=True,
        )
        await url_scheme.launch(url)

    undo_log.delete(undo_entry["id"])

    return {
        "undone": True,
        "action_kind": KIND,
        "project_id": project_id,
        "restored_count": len(items),
        "marker_cancelled": bool(marker_created and marker_uuid),
    }


# ---------- internals ----------


def _build_new_order(
    prior_order: list[str],
    marker_uuid: str,
    moved_uuids: list[str],
) -> list[str]:
    """Build the final ordered UUID list for the reorder command.

    If the marker was pre-existing (already in prior_order):
        [todos before marker] + [marker] + [todos after marker] + [moved_uuids]
    If the marker is new:
        [prior_order] + [marker] + [moved_uuids]

    The "todos after marker" are tasks from previous batches; new tasks always
    append after them.
    """
    if marker_uuid in prior_order:
        idx = prior_order.index(marker_uuid)
        before = prior_order[:idx]
        after = prior_order[idx + 1:]
        return before + [marker_uuid] + after + moved_uuids
    return prior_order + [marker_uuid] + moved_uuids


async def _find_or_create_marker(
    project_id: str,
    auth_token: str,
) -> tuple[str, bool]:
    """Return (marker_uuid, was_created). Idempotent — reuses existing marker."""
    proj = things_repo.project(project_id)
    if proj is not None:
        for item in (proj.get("items") or []):
            if item.get("type") == "to-do" and item.get("title") == AI_NEWLY_ADDED_HEADING:
                return item["uuid"], False

    # Create the marker heading task.
    created_after = time.strftime(_CREATED_FMT, time.localtime(time.time() - 2))
    url = url_scheme.build_add_url_v2(title=AI_NEWLY_ADDED_HEADING, list_id=project_id)
    await url_scheme.launch(url)
    verified = await _poll_for_marker(created_after)
    return verified["uuid"], True


async def _poll_for_marker(created_after: str) -> dict:
    deadline = asyncio.get_running_loop().time() + config.WRITE_POLL_TIMEOUT_SECONDS
    while True:
        match = things_repo.find_recent_by_title(AI_NEWLY_ADDED_HEADING, created_after)
        if match is not None:
            return match
        if asyncio.get_running_loop().time() >= deadline:
            raise RuntimeError(
                f"Timed out after {config.WRITE_POLL_TIMEOUT_SECONDS}s waiting for "
                f"marker {AI_NEWLY_ADDED_HEADING!r} to appear in Things. "
                "Is the Things app running with URL scheme enabled?"
            )
        await asyncio.sleep(config.WRITE_POLL_INTERVAL_SECONDS)


async def _poll_until_in_project(todo_id: str, project_id: str) -> None:
    """Wait until Things confirms the task is in the project (or best-effort timeout)."""
    deadline = asyncio.get_running_loop().time() + config.WRITE_POLL_TIMEOUT_SECONDS
    while True:
        row = things_repo.get_todo(todo_id)
        if row is not None and row.get("project") == project_id:
            return
        if asyncio.get_running_loop().time() >= deadline:
            return  # best-effort; proceed with reorder
        await asyncio.sleep(config.WRITE_POLL_INTERVAL_SECONDS)


async def _reorder_project(project_id: str, order: list[str]) -> None:
    """Issue the AppleScript reorder command for a project."""
    escaped_id = applescript.escape(project_id)
    uuids_str = ",".join(applescript.escape(u) for u in order)
    script = (
        f'tell application "Things3" to '
        f'_private_experimental_ reorder to dos in project id "{escaped_id}" '
        f'with ids "{uuids_str}"'
    )
    await applescript.run_script(script)
