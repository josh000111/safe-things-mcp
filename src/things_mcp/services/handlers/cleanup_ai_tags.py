"""``cleanup_ai_tags`` handler — remove transient AI routing tags from to-dos.

Strips ONLY transient=1 routing tags recorded in ai_tag_routing. Never
strips *Unclear* or other persistent abstain tags (transient=0).

Call this AFTER bulk_move has confirmed the tasks landed in their new
destinations.

Requires ``THINGS_MCP_ALLOW_APPLESCRIPT=1``.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from .. import applescript, things_repo
from ...state import undo_log, ai_tag_routing
from ...config import WRITE_POLL_INTERVAL_SECONDS, WRITE_POLL_TIMEOUT_SECONDS

KIND = "cleanup_ai_tags"


def make_preview(payload: dict) -> str:
    todo_uuids = payload.get("todo_uuids") or []
    n = len(todo_uuids)
    return f"Remove transient AI routing tags from {n} to-do(s) after confirmed sort."


async def execute(payload: dict) -> dict:
    from ...config import ALLOW_APPLESCRIPT
    if not ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "cleanup_ai_tags requires THINGS_MCP_ALLOW_APPLESCRIPT=1. "
            "Set the environment variable and restart the MCP server."
        )

    todo_uuids: list[str] = payload.get("todo_uuids") or []
    group_id = payload.get("group_id")

    if not todo_uuids:
        raise ValueError("cleanup_ai_tags requires at least one todo_uuid.")

    # Query transient routing rows for these todos (transient=1 only)
    transient_rows = ai_tag_routing.get_transient_for_todos(todo_uuids)
    if not transient_rows:
        return {
            "action_kind": KIND,
            "undo_id": None,
            "count": 0,
            "group_id": group_id,
            "note": "No transient routing tags found for the given to-dos.",
        }

    # Group transient rows by todo_uuid
    rows_by_uuid: dict[str, list[dict[str, Any]]] = {}
    for row in transient_rows:
        uuid = row["todo_uuid"]
        rows_by_uuid.setdefault(uuid, []).append(row)

    # Build undo snapshot: for each affected task, capture current tags
    undo_items: list[dict[str, Any]] = []
    for todo_uuid, rows in rows_by_uuid.items():
        todo = things_repo.get_todo(todo_uuid)
        current_tags: list[str] = list(todo.get("tags") or []) if todo else []
        stripped_tag_names = [r["tag_name"] for r in rows]
        undo_items.append({
            "todo_uuid": todo_uuid,
            "inverse_tags": current_tags,
            "stripped_tags": stripped_tag_names,
            "routing_rows": rows,  # Full row dicts for restore_rows()
        })

    # Write undo_log BEFORE mutation (V2 acceptance gate)
    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=None,
        before_state={"items": undo_items},
        after_state=None,
        group_id=group_id,
    )

    # Strip transient tags from each affected todo
    ids_to_delete: list[str] = []
    for undo_item in undo_items:
        todo_uuid = undo_item["todo_uuid"]
        inverse_tags: list[str] = undo_item["inverse_tags"]
        stripped_tags: list[str] = undo_item["stripped_tags"]
        rows: list[dict[str, Any]] = undo_item["routing_rows"]

        # Compute reduced tag set: current minus transient tags
        reduced = sorted(set(inverse_tags) - set(stripped_tags))
        safe_uuid = applescript.escape(todo_uuid)
        tag_string = ",".join(applescript.escape(t) for t in reduced)
        assign_script = (
            f'tell application "Things3"\n'
            f'    set tag names of to do id "{safe_uuid}" to "{tag_string}"\n'
            f'    return ""\n'
            f'end tell'
        )
        await applescript.run_script(assign_script)

        # Poll until stripped tags are gone
        deadline = time.monotonic() + WRITE_POLL_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            current = things_repo.get_todo(todo_uuid)
            current_tag_set = set(current.get("tags") or []) if current else set()
            if not any(t in current_tag_set for t in stripped_tags):
                break
            await asyncio.sleep(WRITE_POLL_INTERVAL_SECONDS)
        else:
            raise RuntimeError(
                f"Timed out waiting for transient tags to be removed from to-do '{todo_uuid}'."
            )

        ids_to_delete.extend(r["id"] for r in rows)

    # Delete the consumed ai_tag_routing rows
    if ids_to_delete:
        ai_tag_routing.delete_by_ids(ids_to_delete)

    undo_log.attach_target(
        entry_id,
        target_uuid=None,
        after_state={"cleaned": True, "tasks_affected": len(undo_items)},
    )

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "count": len(undo_items),
        "group_id": group_id,
    }


async def undo(undo_entry: dict) -> dict:
    from ...config import ALLOW_APPLESCRIPT
    if not ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "Cannot undo cleanup_ai_tags without THINGS_MCP_ALLOW_APPLESCRIPT=1."
        )

    before_state = undo_entry.get("before_state") or {}
    undo_items = before_state.get("items") or []

    for undo_item in undo_items:
        todo_uuid = undo_item["todo_uuid"]
        inverse_tags: list[str] = undo_item.get("inverse_tags") or []
        routing_rows: list[dict[str, Any]] = undo_item.get("routing_rows") or []

        # Re-apply the full prior tag set (which included the stripped tags)
        safe_uuid = applescript.escape(todo_uuid)
        if inverse_tags:
            tag_string = ",".join(applescript.escape(t) for t in sorted(inverse_tags))
        else:
            tag_string = ""
        assign_script = (
            f'tell application "Things3"\n'
            f'    set tag names of to do id "{safe_uuid}" to "{tag_string}"\n'
            f'    return ""\n'
            f'end tell'
        )
        await applescript.run_script(assign_script)

        # Re-insert the routing rows
        if routing_rows:
            ai_tag_routing.restore_rows(routing_rows)

    undo_log.delete(undo_entry["id"])

    return {
        "undone": True,
        "action_kind": KIND,
        "item_count": len(undo_items),
        "note": f"Re-applied stripped tags and restored routing rows for {len(undo_items)} to-do(s).",
    }
