"""``delete_project`` handler — move a project to Things Trash via AppleScript.

Uses AppleScript ``delete`` which moves the project to Things Trash.
Undo uses AppleScript to move the project back to Anytime (original area
restore is not supported by Things' SDEF).

The delete and undo scripts use a ``try … on error … end try`` cascade:
``project id`` is tried first (works for URL-scheme-created and active
projects); on failure falls back to ``to do id`` (needed for cancelled/
Logbook projects that are unreachable via ``project id``).

This kind is in ``NEVER_BYPASS_KINDS`` — explicit confirm required.

Requires ``SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1``.
"""
from __future__ import annotations

from .. import things_repo
from .. import applescript
from ...state import undo_log

KIND = "delete_project"


def make_preview(payload: dict) -> str:
    project_id = payload["project_id"]
    snapshot = payload.get("snapshot") or {}
    title = snapshot.get("title") or project_id
    return (
        f"Deletes project AND all its tasks '{title}' ({project_id}) → Things Trash. "
        "Undo restores the project from Trash to Anytime (area membership not restored). "
        "Trash auto-empties after 30 days."
    )


async def execute(payload: dict) -> dict:
    """Move a project to Things Trash via AppleScript.

    1. Verify AppleScript is enabled.
    2. Confirm project exists and is not already in Trash.
    3. Snapshot the full row (needed for undo).
    4. Write undo_log row BEFORE the AppleScript call (V2 acceptance gate).
    5. Run: tell application "Things3" to delete (to do id "X").
    6. Return result with undo_id.
    """
    from ...config import ALLOW_APPLESCRIPT
    if not ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "delete_project requires SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1. "
            "Set the environment variable and restart the MCP server."
        )

    project_id = payload["project_id"]
    if not project_id:
        raise ValueError("project_id is required")

    before = things_repo.get_project_row(project_id)
    if before is None:
        raise ValueError(
            f"No project found with id={project_id!r}. It may already be deleted "
            "or the id may be wrong. Use list/search tools to find it."
        )
    if before.get("list") == "Trash":
        raise ValueError(
            f"Project {project_id!r} is already in Trash. "
            "Nothing to delete."
        )

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=project_id,
        before_state={
            "full": before,
            "title": before.get("title"),
            "original_area": before.get("area"),
        },
        after_state=None,
    )

    safe_id = applescript.escape(project_id)
    script = (
        f'tell application "Things3"\n'
        f'    try\n'
        f'        delete (project id "{safe_id}")\n'
        f'    on error\n'
        f'        delete (to do id "{safe_id}")\n'
        f'    end try\n'
        f'end tell'
    )
    await applescript.run_script(script)

    undo_log.attach_target(entry_id, target_uuid=project_id, after_state={"status": "trashed"})

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "id": project_id,
        "title": before.get("title", ""),
        "note": (
            "Project and all its tasks moved to Things Trash. Use undo() to restore. "
            "Undo restores to Anytime (area membership not restored). "
            "Things auto-empties Trash after 30 days."
        ),
    }


async def undo(undo_entry: dict) -> dict:
    """Restore a deleted project from Things Trash to Anytime.

    Area restore via AppleScript is not supported by Things' SDEF — the
    project is always restored to Anytime as the safe fallback. The
    original_area is captured in before_state for reference.
    """
    from ...config import ALLOW_APPLESCRIPT
    if not ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "Cannot undo delete_project without SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1. "
            "Set the environment variable and restart the MCP server."
        )

    target_uuid = undo_entry.get("target_uuid")
    if not target_uuid:
        raise RuntimeError(
            f"undo_log entry {undo_entry.get('id')!r} has no target_uuid; "
            "original delete may not have landed cleanly."
        )

    safe_id = applescript.escape(target_uuid)
    script = (
        f'tell application "Things3"\n'
        f'    try\n'
        f'        move (project id "{safe_id}") to list "Anytime"\n'
        f'    on error\n'
        f'        move (to do id "{safe_id}") to list "Anytime"\n'
        f'    end try\n'
        f'    return ""\n'
        f'end tell'
    )
    await applescript.run_script(script)
    undo_log.delete(undo_entry["id"])

    before_state = undo_entry.get("before_state") or {}
    return {
        "undone": True,
        "action_kind": KIND,
        "target_uuid": target_uuid,
        "restored_to": "Anytime",
        "original_area": before_state.get("original_area"),
        "note": "Project restored to Anytime. Area membership was not restored (not supported via AppleScript).",
    }
