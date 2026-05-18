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

    For ``add_todo`` actions, undo is currently a *soft-undo* (marks the
    task completed and canceled). True hard-delete arrives with
    ``propose_delete_todo``.
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


def register(mcp: FastMCP) -> None:
    mcp.tool()(undo)
