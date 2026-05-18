"""Dispatcher tools: ``confirm_action``, ``cancel_action``,
``list_pending_actions``.

These are kind-agnostic. They look up a pending row, dispatch to the
right handler (or just remove the row in cancel/list cases), and
deliberately know nothing about ``add_todo`` vs ``update_todo`` etc.

The tool functions are defined at module level so tests can call them
directly without going through the FastMCP wrapper. ``register`` just
exposes them on a server instance.
"""
from __future__ import annotations

from datetime import UTC, datetime

from mcp.server.fastmcp import FastMCP

from ..services import handlers
from ..state import pending


async def confirm_action(action_id: str) -> dict:
    """Execute a pending action by id. Dispatches by kind.

    Raises if the action is missing, already executed, or expired.
    Sweeps expired siblings on the way in.
    """
    pending.sweep_expired()
    row = pending.get(action_id)
    if row is None:
        raise ValueError(
            f"No pending action {action_id!r}. It may have been "
            "confirmed, cancelled, or expired."
        )

    expires = datetime.fromisoformat(row["expires_at"])
    if expires < datetime.now(UTC):
        pending.delete(action_id)
        raise ValueError(
            f"Pending action {action_id!r} expired at {row['expires_at']}."
        )

    handler = handlers.get(row["kind"])
    result = await handler.execute(row["payload"])
    pending.delete(action_id)
    return {"action_id": action_id, "kind": row["kind"], "result": result}


def cancel_action(action_id: str) -> dict:
    """Drop a pending action without executing it."""
    if not pending.delete(action_id):
        raise ValueError(f"No pending action {action_id!r} to cancel.")
    return {"action_id": action_id, "cancelled": True}


def list_pending_actions() -> list[dict]:
    """Return all pending actions, newest first. Sweeps expired rows."""
    pending.sweep_expired()
    return pending.list_all()


def register(mcp: FastMCP) -> None:
    mcp.tool()(confirm_action)
    mcp.tool()(cancel_action)
    mcp.tool()(list_pending_actions)
