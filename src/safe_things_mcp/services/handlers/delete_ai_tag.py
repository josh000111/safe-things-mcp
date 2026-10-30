"""``delete_ai_tag`` handler — delete an AI tag from Things.

Uses AppleScript ``delete tag "<name>"`` which removes the tag from ALL
tasks that carry it. This is in NEVER_BYPASS_KINDS — explicit confirm
always required.

Undo: re-creates the tag (with original parent) and re-assigns it to
all tasks that previously carried it.

Requires ``SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1``.
"""
from __future__ import annotations

import asyncio
import time

from .. import applescript, things_repo
from ...state import undo_log
from ...config import WRITE_POLL_INTERVAL_SECONDS, WRITE_POLL_TIMEOUT_SECONDS

KIND = "delete_ai_tag"


def make_preview(payload: dict) -> str:
    name = payload["name"]
    carrying_count = payload.get("carrying_count", "?")
    return (
        f"Delete AI tag '{name}' — removes it from ALL tasks that carry it "
        f"({carrying_count} task(s)). This is irreversible without undo."
    )


async def execute(payload: dict) -> dict:
    from ...config import ALLOW_APPLESCRIPT
    if not ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "delete_ai_tag requires SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1. "
            "Set the environment variable and restart the MCP server."
        )

    name = payload["name"]

    # Verify tag exists
    if name not in things_repo.get_tag_names():
        raise ValueError(
            f"Tag '{name}' not found in Things. "
            "Use get_tags() to list existing tags."
        )

    # Read parent via AppleScript
    safe_name = applescript.escape(name)
    parent_script = (
        f'tell application "Things3"\n'
        f'    set t to tag "{safe_name}"\n'
        f'    try\n'
        f'        return name of parent tag of t\n'
        f'    on error\n'
        f'        return ""\n'
        f'    end try\n'
        f'end tell'
    )
    current_parent = (await applescript.run_script(parent_script)).strip()

    # Snapshot every task carrying this tag
    carrying_tasks = _find_tasks_with_tag(name)

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=name,
        before_state={
            "name": name,
            "parent": current_parent,
            "carrying_tasks": carrying_tasks,
        },
        after_state=None,
    )

    delete_script = f'tell application "Things3" to delete tag "{safe_name}"'
    await applescript.run_script(delete_script)

    # Poll until tag is gone from SQLite mirror
    deadline = time.monotonic() + WRITE_POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if name not in things_repo.get_tag_names():
            break
        await asyncio.sleep(WRITE_POLL_INTERVAL_SECONDS)

    undo_log.attach_target(
        entry_id,
        target_uuid=name,
        after_state={"deleted": True, "was_on_tasks": len(carrying_tasks)},
    )

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "name": name,
        "tasks_affected": len(carrying_tasks),
        "note": (
            f"Tag '{name}' deleted and removed from {len(carrying_tasks)} task(s). "
            "Use undo() to restore the tag and re-assign it."
        ),
    }


async def undo(undo_entry: dict) -> dict:
    from ...config import ALLOW_APPLESCRIPT, AI_TAG_PARENT
    if not ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "Cannot undo delete_ai_tag without SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1."
        )

    before_state = undo_entry.get("before_state") or {}
    name = before_state.get("name") or undo_entry.get("target_uuid")
    parent = before_state.get("parent") or AI_TAG_PARENT
    carrying_tasks = before_state.get("carrying_tasks") or []

    if not name:
        raise RuntimeError(f"undo_log entry {undo_entry.get('id')!r} has no tag name.")

    safe_name = applescript.escape(name)
    safe_parent = applescript.escape(parent)

    # Re-create the parent if it doesn't exist
    if parent and parent not in things_repo.get_tag_names():
        parent_create_script = (
            f'tell application "Things3" to make new tag with properties {{name:"{safe_parent}"}}'
        )
        await applescript.run_script(parent_create_script)

    # Re-create the tag
    if parent:
        create_script = (
            f'tell application "Things3"\n'
            f'    make new tag with properties {{name:"{safe_name}", parent tag:tag "{safe_parent}"}}\n'
            f'    return ""\n'
            f'end tell'
        )
    else:
        create_script = (
            f'tell application "Things3"\n'
            f'    make new tag with properties {{name:"{safe_name}"}}\n'
            f'    return ""\n'
            f'end tell'
        )
    await applescript.run_script(create_script)

    # Poll until tag reappears
    deadline = time.monotonic() + WRITE_POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if name in things_repo.get_tag_names():
            break
        await asyncio.sleep(WRITE_POLL_INTERVAL_SECONDS)

    # Re-assign tag to all previously-carrying tasks
    restored_count = 0
    for task_info in carrying_tasks:
        todo_uuid = task_info.get("uuid") or task_info.get("todo_uuid")
        prior_tags = task_info.get("prior_tags") or []
        if not todo_uuid:
            continue
        # Restore exact prior tag set (which included this tag)
        merged = sorted(set(prior_tags))
        safe_uuid = applescript.escape(todo_uuid)
        tag_string = ",".join(applescript.escape(t) for t in merged)
        assign_script = (
            f'tell application "Things3"\n'
            f'    set tag names of to do id "{safe_uuid}" to "{tag_string}"\n'
            f'    return ""\n'
            f'end tell'
        )
        try:
            await applescript.run_script(assign_script)
            restored_count += 1
        except Exception:
            pass  # Best-effort per-task restore

    undo_log.delete(undo_entry["id"])

    return {
        "undone": True,
        "action_kind": KIND,
        "name": name,
        "restored_to_tasks": restored_count,
    }


# ---------- internals ----------


def _find_tasks_with_tag(tag_name: str) -> list[dict]:
    """Return all tasks carrying this tag, with their full tag sets."""
    # Use things_repo.tags(include_items=True) to find tasks
    try:
        tags_with_items = things_repo.tags(include_items=True)
        for tag in tags_with_items:
            if tag.get("title") == tag_name:
                items = tag.get("items") or []
                result = []
                for item in items:
                    if item.get("type") == "to-do":
                        result.append({
                            "uuid": item["uuid"],
                            "title": item.get("title", ""),
                            "prior_tags": list(item.get("tags") or []),
                        })
                return result
    except Exception:
        pass
    return []
