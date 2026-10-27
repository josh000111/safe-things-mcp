"""``apply_ai_tags`` handler — apply AI tags to one or more to-dos.

Uses a merge model: new tag set = existing tags ∪ add_tags. Never clobbers
user tags. Undo restores the EXACT prior tag set.

Requires ``SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1``.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from .. import applescript, things_repo
from ...state import undo_log, ai_tag_routing
from ...config import WRITE_POLL_INTERVAL_SECONDS, WRITE_POLL_TIMEOUT_SECONDS

KIND = "apply_ai_tags"


def make_preview(payload: dict) -> str:
    items = payload.get("items") or []
    n = len(items)
    all_tags: list[str] = []
    for item in items:
        all_tags.extend(item.get("add_tags") or [])
    unique_tags = sorted(set(all_tags))
    tag_str = ", ".join(unique_tags) if unique_tags else "(none)"
    titles = []
    for item in items[:3]:
        todo_uuid = item.get("todo_uuid", "")
        titles.append(todo_uuid)
    suffix = f"... and {n - 3} more" if n > 3 else ""
    return (
        f"Apply AI tags to {n} to-do(s): [{tag_str}] → "
        + ", ".join(titles)
        + suffix
    )


async def execute(payload: dict) -> dict:
    from ...config import ALLOW_APPLESCRIPT, AI_TAG_PARENT
    if not ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "apply_ai_tags requires SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1. "
            "Set the environment variable and restart the MCP server."
        )

    items = payload.get("items") or []
    group_id = payload.get("group_id")

    if not items:
        raise ValueError("apply_ai_tags requires at least one item.")

    # Read all existing tag names once
    existing_names = things_repo.get_tag_names()

    # Build undo snapshot: read current tags for each todo before mutation
    undo_items: list[dict[str, Any]] = []
    for item in items:
        todo_uuid = item["todo_uuid"]
        add_tags = item.get("add_tags") or []
        todo = things_repo.get_todo(todo_uuid)
        if todo is None:
            raise ValueError(f"To-do '{todo_uuid}' not found in Things.")
        current_tags: list[str] = list(todo.get("tags") or [])
        undo_items.append({
            "todo_uuid": todo_uuid,
            "inverse_tags": current_tags,
            "added_tags": add_tags,
        })

    # Write undo_log BEFORE mutation (V2 acceptance gate)
    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=None,
        before_state={"items": undo_items},
        after_state=None,
        group_id=group_id,
    )

    # Ensure each new AI tag exists and is parented under AI_TAG_PARENT
    safe_parent = applescript.escape(AI_TAG_PARENT)
    if AI_TAG_PARENT not in existing_names:
        parent_script = (
            f'tell application "Things3" to make new tag with properties {{name:"{safe_parent}"}}'
        )
        await applescript.run_script(parent_script)
        existing_names = things_repo.get_tag_names()

    # Collect all unique new tags across all items
    all_new_tags: set[str] = set()
    for item in items:
        all_new_tags.update(item.get("add_tags") or [])

    for tag_name in all_new_tags:
        if tag_name not in existing_names:
            safe_tag = applescript.escape(tag_name)
            child_script = (
                f'tell application "Things3"\n'
                f'    make new tag with properties {{name:"{safe_tag}", parent tag:tag "{safe_parent}"}}\n'
                f'    return ""\n'
                f'end tell'
            )
            await applescript.run_script(child_script)
            # Poll until tag appears
            deadline = time.monotonic() + WRITE_POLL_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                if tag_name in things_repo.get_tag_names():
                    break
                await asyncio.sleep(WRITE_POLL_INTERVAL_SECONDS)
            else:
                raise RuntimeError(
                    f"Timed out waiting for tag '{tag_name}' to appear in Things DB."
                )
            existing_names = things_repo.get_tag_names()

    # Apply merged tags to each todo via AppleScript
    for undo_item in undo_items:
        todo_uuid = undo_item["todo_uuid"]
        add_tags = undo_item["added_tags"]

        # Re-read current tags so that if the same uuid appears multiple times
        # in items (e.g. one routing tag + one *Unclear*), each sub-apply
        # stacks on top of what the previous one landed, not on stale pre-loop state.
        current_todo = things_repo.get_todo(todo_uuid)
        current_tags_now = list(current_todo.get("tags") or []) if current_todo else []

        merged = sorted(set(current_tags_now) | set(add_tags))
        safe_uuid = applescript.escape(todo_uuid)
        tag_string = ",".join(applescript.escape(t) for t in merged)
        assign_script = (
            f'tell application "Things3"\n'
            f'    set tag names of to do id "{safe_uuid}" to "{tag_string}"\n'
            f'    return ""\n'
            f'end tell'
        )
        await applescript.run_script(assign_script)

        # Poll until all add_tags appear in the task's tag set
        deadline = time.monotonic() + WRITE_POLL_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            current = things_repo.get_todo(todo_uuid)
            current_tags = set(current.get("tags") or []) if current else set()
            if all(t in current_tags for t in add_tags):
                break
            await asyncio.sleep(WRITE_POLL_INTERVAL_SECONDS)
        else:
            raise RuntimeError(
                f"Timed out waiting for tags to appear on to-do '{todo_uuid}'."
            )

    # Write ai_tag_routing rows
    for item in items:
        todo_uuid = item["todo_uuid"]
        add_tags = item.get("add_tags") or []
        routing = item.get("routing") or {}
        for tag_name in add_tags:
            if routing:
                dest_kind = routing.get("dest_kind")
                dest_uuid = routing.get("dest_uuid")
                transient = bool(routing.get("transient", False))
            else:
                dest_kind = None
                dest_uuid = None
                transient = False
            ai_tag_routing.upsert(
                tag_name=tag_name,
                todo_uuid=todo_uuid,
                dest_kind=dest_kind,
                dest_uuid=dest_uuid,
                transient=transient,
            )

    undo_log.attach_target(
        entry_id,
        target_uuid=None,
        after_state={"applied": True, "item_count": len(items)},
    )

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "count": len(items),
        "group_id": group_id,
    }


async def undo(undo_entry: dict) -> dict:
    from ...config import ALLOW_APPLESCRIPT
    if not ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "Cannot undo apply_ai_tags without SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1."
        )

    before_state = undo_entry.get("before_state") or {}
    undo_items = before_state.get("items") or []

    for undo_item in undo_items:
        todo_uuid = undo_item["todo_uuid"]
        inverse_tags: list[str] = undo_item.get("inverse_tags") or []
        added_tags: list[str] = undo_item.get("added_tags") or []

        # Restore exact prior tag set via AppleScript
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

        # Delete ai_tag_routing rows for the added tags on this todo
        rows = ai_tag_routing.get_for_todo(todo_uuid)
        ids_to_delete = [r["id"] for r in rows if r.get("tag_name") in added_tags]
        if ids_to_delete:
            ai_tag_routing.delete_by_ids(ids_to_delete)

    undo_log.delete(undo_entry["id"])

    return {
        "undone": True,
        "action_kind": KIND,
        "item_count": len(undo_items),
        "note": f"Restored prior tag sets for {len(undo_items)} to-do(s).",
    }
