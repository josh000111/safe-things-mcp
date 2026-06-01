"""``manage_ai_tag`` handler — rename and/or reparent an AI tag.

Uses AppleScript ``set name of tag`` / ``set parent tag of tag``.

Requires ``THINGS_MCP_ALLOW_APPLESCRIPT=1``.
"""
from __future__ import annotations

import asyncio
import time

from .. import applescript, things_repo
from ...state import undo_log
from ...config import WRITE_POLL_INTERVAL_SECONDS, WRITE_POLL_TIMEOUT_SECONDS

KIND = "manage_ai_tag"


def make_preview(payload: dict) -> str:
    name = payload["name"]
    parts = []
    if payload.get("new_name"):
        parts.append(f"name='{payload['new_name']}'")
    if payload.get("new_parent"):
        parts.append(f"parent='{payload['new_parent']}'")
    return f"Rename/reparent AI tag '{name}' → {', '.join(parts)}."


async def execute(payload: dict) -> dict:
    from ...config import ALLOW_APPLESCRIPT
    if not ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "manage_ai_tag requires THINGS_MCP_ALLOW_APPLESCRIPT=1. "
            "Set the environment variable and restart the MCP server."
        )

    name = payload["name"]
    new_name = payload.get("new_name")
    new_parent = payload.get("new_parent")

    if not new_name and not new_parent:
        raise ValueError("manage_ai_tag requires at least one of: new_name, new_parent.")

    # Verify tag exists
    if name not in things_repo.get_tag_names():
        raise ValueError(
            f"Tag '{name}' not found in Things. "
            "Use get_tags() to list existing tags."
        )

    # Read current parent via AppleScript (things_repo is flat — no hierarchy)
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

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=name,
        before_state={"name": name, "parent": current_parent},
        after_state=None,
    )

    # Apply new name
    if new_name:
        safe_new_name = applescript.escape(new_name)
        rename_script = (
            f'tell application "Things3"\n'
            f'    set name of tag "{safe_name}" to "{safe_new_name}"\n'
            f'    return ""\n'
            f'end tell'
        )
        await applescript.run_script(rename_script)
        # After rename, the effective name changes — update for subsequent operations
        effective_name = new_name
    else:
        effective_name = name

    # Apply new parent
    if new_parent:
        safe_effective = applescript.escape(effective_name)
        safe_new_parent = applescript.escape(new_parent)
        # Ensure new parent exists
        if new_parent not in things_repo.get_tag_names():
            parent_create_script = (
                f'tell application "Things3" to make new tag with properties {{name:"{safe_new_parent}"}}'
            )
            await applescript.run_script(parent_create_script)
        reparent_script = (
            f'tell application "Things3"\n'
            f'    set parent tag of tag "{safe_effective}" to tag "{safe_new_parent}"\n'
            f'    return ""\n'
            f'end tell'
        )
        await applescript.run_script(reparent_script)

    # Poll until change is visible (check by effective name)
    final_name = new_name or name
    deadline = time.monotonic() + WRITE_POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if final_name in things_repo.get_tag_names():
            break
        await asyncio.sleep(WRITE_POLL_INTERVAL_SECONDS)

    after_state = {"name": final_name, "parent": new_parent or current_parent}
    undo_log.attach_target(entry_id, target_uuid=final_name, after_state=after_state)

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "name": final_name,
        "parent": new_parent or current_parent,
    }


async def undo(undo_entry: dict) -> dict:
    from ...config import ALLOW_APPLESCRIPT
    if not ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "Cannot undo manage_ai_tag without THINGS_MCP_ALLOW_APPLESCRIPT=1."
        )

    before_state = undo_entry.get("before_state") or {}
    after_state = undo_entry.get("after_state") or {}

    original_name = before_state.get("name")
    original_parent = before_state.get("parent") or ""
    current_name = after_state.get("name") or undo_entry.get("target_uuid")

    if not current_name:
        raise RuntimeError(f"undo_log entry {undo_entry.get('id')!r} has no target name.")

    safe_current = applescript.escape(current_name)

    # Restore original name if it changed
    if original_name and original_name != current_name:
        safe_original = applescript.escape(original_name)
        rename_back_script = (
            f'tell application "Things3"\n'
            f'    set name of tag "{safe_current}" to "{safe_original}"\n'
            f'    return ""\n'
            f'end tell'
        )
        await applescript.run_script(rename_back_script)
        effective_name = original_name
    else:
        effective_name = current_name

    # Restore original parent if it changed
    safe_effective = applescript.escape(effective_name)
    if original_parent:
        safe_orig_parent = applescript.escape(original_parent)
        reparent_back_script = (
            f'tell application "Things3"\n'
            f'    set parent tag of tag "{safe_effective}" to tag "{safe_orig_parent}"\n'
            f'    return ""\n'
            f'end tell'
        )
        await applescript.run_script(reparent_back_script)
    else:
        # Remove parent (make it a top-level tag)
        # AppleScript: setting parent tag to "" or removing — use missing value
        clear_parent_script = (
            f'tell application "Things3"\n'
            f'    set parent tag of tag "{safe_effective}" to missing value\n'
            f'    return ""\n'
            f'end tell'
        )
        try:
            await applescript.run_script(clear_parent_script)
        except Exception:
            pass  # If clearing parent fails, proceed — not all AppleScript versions support this

    undo_log.delete(undo_entry["id"])

    return {
        "undone": True,
        "action_kind": KIND,
        "restored_name": effective_name,
        "restored_parent": original_parent or "(none)",
    }
