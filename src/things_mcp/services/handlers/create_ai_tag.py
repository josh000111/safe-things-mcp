"""``create_ai_tag`` handler — create an asterisk-wrapped AI tag in Things.

Uses AppleScript to:
1. Ensure the parent tag (default "AI") exists.
2. Create the child tag parented under it.

If the tag already exists, this is a no-op (idempotent).

Undo: AppleScript ``delete tag "<name>"`` (only if tag was not pre-existing).

Requires ``THINGS_MCP_ALLOW_APPLESCRIPT=1``.
"""
from __future__ import annotations

import asyncio
import time

from .. import applescript, things_repo
from ...state import undo_log
from ...config import WRITE_POLL_INTERVAL_SECONDS, WRITE_POLL_TIMEOUT_SECONDS

KIND = "create_ai_tag"


def make_preview(payload: dict) -> str:
    name = payload["name"]
    parent = payload.get("parent", "AI")
    return f"Create AI tag '{name}' under parent '{parent}'."


async def execute(payload: dict) -> dict:
    from ...config import ALLOW_APPLESCRIPT, AI_TAG_PARENT
    if not ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "create_ai_tag requires THINGS_MCP_ALLOW_APPLESCRIPT=1. "
            "Set the environment variable and restart the MCP server."
        )

    name = payload["name"]
    parent = payload.get("parent") or AI_TAG_PARENT
    group_id = payload.get("group_id")

    # Validate asterisk wrapper (defensive — propose layer also checks)
    if not (name.startswith("*") and name.endswith("*") and len(name) > 2):
        raise ValueError(
            f"AI tag name {name!r} must be asterisk-wrapped (e.g. '*Do Taxes*'). "
            "The asterisks are mandatory structural markers."
        )

    # Idempotency: if tag already exists, return without creating
    existing_names = things_repo.get_tag_names()
    already_existed = name in existing_names

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=None,
        before_state={"name": name, "parent": parent, "existed": already_existed},
        after_state=None,
        group_id=group_id,
    )

    if already_existed:
        undo_log.attach_target(entry_id, target_uuid=name, after_state={"created": False, "existed": True})
        return {
            "action_kind": KIND,
            "undo_id": entry_id,
            "name": name,
            "parent": parent,
            "note": f"Tag '{name}' already exists — no-op.",
        }

    safe_name = applescript.escape(name)
    safe_parent = applescript.escape(parent)

    # Ensure parent tag exists
    parent_exists = parent in existing_names
    if not parent_exists:
        parent_script = f'tell application "Things3" to make new tag with properties {{name:"{safe_parent}"}}'
        await applescript.run_script(parent_script)

    # Create child tag parented under the parent
    child_script = (
        f'tell application "Things3"\n'
        f'    make new tag with properties {{name:"{safe_name}", parent tag:tag "{safe_parent}"}}\n'
        f'    return ""\n'
        f'end tell'
    )
    await applescript.run_script(child_script)

    # Poll until tag is visible in SQLite mirror
    deadline = time.monotonic() + WRITE_POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if name in things_repo.get_tag_names():
            break
        await asyncio.sleep(WRITE_POLL_INTERVAL_SECONDS)
    else:
        raise RuntimeError(
            f"Timed out waiting for tag '{name}' to appear in Things DB. "
            "The tag may have been created but the read-only mirror hasn't updated."
        )

    undo_log.attach_target(entry_id, target_uuid=name, after_state={"created": True, "existed": False})

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "name": name,
        "parent": parent,
        "note": f"Tag '{name}' created under parent '{parent}'.",
    }


async def undo(undo_entry: dict) -> dict:
    from ...config import ALLOW_APPLESCRIPT
    if not ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "Cannot undo create_ai_tag without THINGS_MCP_ALLOW_APPLESCRIPT=1."
        )

    before_state = undo_entry.get("before_state") or {}
    already_existed = before_state.get("existed", False)

    if already_existed:
        # Was a no-op — nothing to undo
        undo_log.delete(undo_entry["id"])
        return {
            "undone": True,
            "action_kind": KIND,
            "note": "Was a no-op (tag pre-existed); nothing to undo.",
        }

    name = before_state.get("name") or undo_entry.get("target_uuid")
    if not name:
        raise RuntimeError(f"undo_log entry {undo_entry.get('id')!r} has no tag name.")

    safe_name = applescript.escape(name)
    script = f'tell application "Things3" to delete tag "{safe_name}"'
    await applescript.run_script(script)

    # Poll until tag is gone
    deadline = time.monotonic() + WRITE_POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if name not in things_repo.get_tag_names():
            break
        await asyncio.sleep(WRITE_POLL_INTERVAL_SECONDS)

    undo_log.delete(undo_entry["id"])

    return {
        "undone": True,
        "action_kind": KIND,
        "target_uuid": name,
        "note": f"Tag '{name}' deleted (undo of create).",
    }
