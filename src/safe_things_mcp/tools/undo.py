"""``undo`` tool — reverses the most recent (or a specified) action.

Dispatches by ``undo_log.action_kind`` to the matching handler's
``undo()``. The handler performs the inverse URL-scheme call, verifies
it landed, and deletes the undo_log row.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..services import handlers
from ..state import undo_log


async def undo(undo_id: str | None = None) -> dict:
    """Reverse the most recent reversible action (or ``undo_id`` if
    given). Returns a description of what was undone.

    For ``add_todo`` actions, undo is a cancel-to-Logbook: the task is
    marked completed and canceled, moving it out of active lists.
    To permanently delete a task, use ``propose_delete_todo`` (moves to Trash).
    """
    if undo_id is None:
        entry = undo_log.most_recent()
        if entry is None:
            raise ValueError("No reversible actions to undo.")
    else:
        entry = undo_log.get(undo_id)
        if entry is None:
            raise ValueError(f"No undo_log entry {undo_id!r}.")

    handler = handlers.get(entry["action_kind"])
    return await handler.undo(entry)


async def undo_group(group_id: str) -> dict:
    """Reverse ALL actions in a sort group in correct reverse order (LIFO).

    A sort produces multiple undo_log entries (apply_ai_tags → bulk_move →
    cleanup_ai_tags) that share a ``group_id``. This tool reverses them all
    newest-first so the whole sort unwinds cleanly — even if unrelated actions
    happened in between.

    Use the ``group_id`` returned by ``propose_apply_ai_tags`` (or any handler
    in the sort chain). The ``group_id`` is also shown in ``recent_undo_log()``
    under the ``group_id`` field.

    Returns a list of undo results, one per reversed entry, in the order
    they were undone (cleanup → move → tags, i.e. newest-first).

    TIP: After undoing a sort, you can re-run it — the agent remembers what
    it just did and can reproduce the sort with adjustments based on feedback.
    """
    entries = undo_log.get_by_group_id(group_id)
    if not entries:
        raise ValueError(f"No undo_log entries found for group_id={group_id!r}.")
    results = []
    for entry in entries:
        handler = handlers.get(entry["action_kind"])
        result = await handler.undo(entry)
        results.append(result)
    return {
        "undone_group": group_id,
        "count": len(results),
        "results": results,
    }


def register(mcp: FastMCP) -> None:
    mcp.tool()(undo)
    mcp.tool()(undo_group)
