"""``delete_todo`` handler -- move a to-do to Things Trash via AppleScript.

Uses AppleScript ``delete`` which moves the task to Things Trash (same as
manually deleting in the Things UI). Things auto-empties Trash after 30 days.

**Undo** uses AppleScript ``move to do id X to list "..."`` (or project) to
restore the task from Trash back to its original container.

This kind is in ``NEVER_BYPASS_KINDS`` -- explicit confirm required regardless
of ``THINGS_MCP_AUTO_CONFIRM``.

Requires ``THINGS_MCP_ALLOW_APPLESCRIPT=1``.
"""
from __future__ import annotations

from .. import things_repo
from .. import applescript
from ...state import undo_log

KIND = "delete_todo"


def make_preview(payload: dict) -> str:
    todo_id = payload["todo_id"]
    snapshot = payload.get("snapshot") or {}
    title = snapshot.get("title") or todo_id
    return (
        f"Hard-delete to-do '{title}' ({todo_id}) -> moves to Things Trash. "
        "Undo restores it from Trash. Trash auto-empties after 30 days."
    )


async def execute(payload: dict) -> dict:
    """Move a to-do to Things Trash via AppleScript.

    1. Verify AppleScript is enabled.
    2. Confirm to-do exists and is not already in Trash.
    3. Snapshot the full row (needed for undo target).
    4. Write undo_log row BEFORE the AppleScript call (V2 acceptance gate).
    5. Run: tell application "Things3" to delete (to do id "X").
    6. Return result with undo_id.
    """
    from ...config import ALLOW_APPLESCRIPT
    if not ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "delete_todo requires THINGS_MCP_ALLOW_APPLESCRIPT=1."
            "Set the environment variable and restart the MCP server."
        )

    todo_id = payload["todo_id"]
    if not todo_id:
        raise ValueError("todo_id is required")

    before = things_repo.get_todo(todo_id)
    if before is None:
        raise ValueError(
            f"No to-do found with id={todo_id!r}. It may already be deleted "
            "or the id may be wrong. Use list/search tools to find it."
        )
    if before.get("list") == "Trash":
        raise ValueError(
            f"To-do {todo_id!r} is already in Trash. "
            "Nothing to delete."
        )

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=todo_id,
        before_state={
            "full": before,
            "original_list": before.get("list"),
            "original_project": before.get("project"),
            "title": before.get("title"),
        },
        after_state=None,
    )

    safe_id = applescript.escape(todo_id)
    script = f'tell application "Things3" to delete (to do id "{safe_id}")'
    await applescript.run_script(script)

    undo_log.attach_target(entry_id, target_uuid=todo_id, after_state={"status": "trashed"})

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "id": todo_id,
        "title": before.get("title", ""),
        "note": (
            "Moved to Things Trash. Use undo() to restore. "
            "Things auto-empties Trash after 30 days."
        ),
    }


async def undo(undo_entry: dict) -> dict:
    """Restore a deleted to-do from Things Trash.

    Uses AppleScript ``move to do id X to list "..."`` (or project).
    If the original container was a project, moves back to that project.
    Otherwise moves to Inbox as the safe fallback.
    """
    from ...config import ALLOW_APPLESCRIPT
    if not ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "Cannot undo delete_todo without THINGS_MCP_ALLOW_APPLESCRIPT=1."
            "Set the environment variable and restart the MCP server."
        )

    target_uuid = undo_entry.get("target_uuid")
    if not target_uuid:
        raise RuntimeError(
            f"undo_log entry {undo_entry.get('id')!r} has no target_uuid; "
            "original delete may not have landed cleanly."
        )

    before_state = undo_entry.get("before_state") or {}
    original_project = before_state.get("original_project")
    original_list = before_state.get("original_list") or "Inbox"

    safe_id = applescript.escape(target_uuid)

    if original_project:
        safe_project = applescript.escape(original_project)
        script = (
            f'tell application "Things3"\n'
            f'    move (to do id "{safe_id}") to project id "{safe_project}"\n'
            f'    return ""\n'
            f'end tell'
        )
    else:
        # Restore to the original built-in list, defaulting to Inbox.
        # Things AppleScript uses title-cased list names.
        restore_list = _normalise_list_name(original_list)
        safe_list = applescript.escape(restore_list)
        script = (
            f'tell application "Things3"\n'
            f'    move (to do id "{safe_id}") to list "{safe_list}"\n'
            f'    return ""\n'
            f'end tell'
        )

    await applescript.run_script(script)
    undo_log.delete(undo_entry["id"])

    return {
        "undone": True,
        "action_kind": KIND,
        "target_uuid": target_uuid,
        "restored_to": original_project or original_list,
    }


# ---------- internals ----------


_LIST_ALIASES: dict[str, str] = {
    "inbox": "Inbox",
    "today": "Today",
    "anytime": "Anytime",
    "someday": "Someday",
    "upcoming": "Upcoming",
    "logbook": "Logbook",
    "trash": "Trash",
}


def _normalise_list_name(name: str) -> str:
    """Return the AppleScript-canonical (title-case) list name.

    Falls back to 'Inbox' for unknown values -- the safe restore target.
    """
    return _LIST_ALIASES.get(name.lower(), "Inbox")
