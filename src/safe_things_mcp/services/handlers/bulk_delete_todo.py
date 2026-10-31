"""``bulk_delete_todo`` handler — move N to-dos to Things Trash via AppleScript.

Bulk version of :mod:`delete_todo`. Moves each task to Things Trash in a
single airlocked op with one ``undo_log`` row covering all N targets.

Undo uses AppleScript ``move to do id X to list/project`` to restore each
task from Trash to its original container.

Requires ``SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1``. Always in
:data:`config.NEVER_BYPASS_KINDS`.
"""
from __future__ import annotations

from .. import things_repo, applescript
from .. import preview_names as pn
from .. import ref_checks
from ...state import undo_log

KIND = "bulk_delete_todo"


def make_preview(payload: dict) -> str:
    ids = payload.get("todo_ids") or []
    n = len(ids)
    return (
        f"Bulk delete {n} to-do{'s' if n != 1 else ''} — moves to Things Trash. "
        "Undo restores all. Trash auto-empties after 30 days."
    ) + pn.todo_lines(ids, payload)


async def execute(payload: dict) -> dict:
    from ...config import ALLOW_APPLESCRIPT
    if not ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "bulk_delete_todo requires SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1. "
            "Set the environment variable and restart the MCP server."
        )

    todo_ids = list(payload.get("todo_ids") or [])
    if not todo_ids:
        raise ValueError("bulk_delete_todo requires a non-empty todo_ids list.")
    group_id = payload.get("group_id")

    items: list[dict] = []
    # Refuse the whole batch (naming every project/heading/area id) before any
    # mutation or undo_log write.
    rows = ref_checks.check_todos(todo_ids, things_repo.get_todo)
    for uid in todo_ids:
        row = rows.get(uid)
        if row is None:
            raise ValueError(
                f"No to-do found with id={uid!r}. Bulk delete aborts before "
                "any mutation — fix the id list and retry."
            )
        if row.get("list") == "Trash":
            raise ValueError(
                f"To-do {uid!r} is already in Trash. "
                "Bulk delete aborts before any mutation — remove it from the list."
            )
        items.append({
            "target_uuid": uid,
            "title": row.get("title"),
            "original_list": row.get("list"),
            "original_project": row.get("project"),
        })

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=None,
        before_state={"items": items, "count": len(items)},
        after_state=None,
        group_id=group_id,
    )

    for item in items:
        safe_id = applescript.escape(item["target_uuid"])
        script = f'tell application "Things3" to delete (to do id "{safe_id}")'
        await applescript.run_script(script)

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "count": len(items),
        "ids": [it["target_uuid"] for it in items],
        "note": (
            "Moved to Things Trash. Use undo() to restore all. "
            "Things auto-empties Trash after 30 days."
        ),
    }


async def undo(undo_entry: dict) -> dict:
    """Restore all deleted to-dos from Things Trash."""
    from ...config import ALLOW_APPLESCRIPT
    if not ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "Cannot undo bulk_delete_todo without SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1."
        )

    before = undo_entry.get("before_state")
    if not isinstance(before, dict) or not before.get("items"):
        raise RuntimeError(
            f"undo_log entry {undo_entry.get('id')!r} has no items to restore."
        )

    for item in before["items"]:
        uid = item["target_uuid"]
        original_project = item.get("original_project")
        original_list = item.get("original_list") or "Inbox"
        safe_id = applescript.escape(uid)

        if original_project:
            safe_proj = applescript.escape(original_project)
            script = (
                f'tell application "Things3"\n'
                f'    move (to do id "{safe_id}") to project id "{safe_proj}"\n'
                f'    return ""\n'
                f'end tell'
            )
        else:
            restore = _normalise_list_name(original_list)
            safe_list = applescript.escape(restore)
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
        "count": len(before["items"]),
        "ids": [it["target_uuid"] for it in before["items"]],
    }


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
    return _LIST_ALIASES.get(name.lower(), "Inbox")
