"""V2 ``propose_*`` tools.

A ``propose_*`` tool validates inputs and enqueues a pending action
keyed by ``kind``. It never mutates Things directly. The agent surfaces
the preview to the user; once approved, the agent calls
``confirm_action(action_id)`` which dispatches to the matching handler
in ``services/handlers/``.

Step 3 ships ``propose_add_todo`` only. Adding more is one new tool +
one new handler per kind — see ``services/handlers/__init__.py``.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..models import ProposeAddTodoInput
from ..services import handlers
from ..state import pending


def propose_add_todo(
    title: str,
    list_id: str = "inbox",
    notes: str | None = None,
    when: str | None = None,
    deadline: str | None = None,
    tags: list[str] | None = None,
    checklist: list[str] | None = None,
) -> dict:
    """Propose adding a to-do to any list (Inbox, Today, Anytime,
    Someday, Upcoming, or a project UUID).

    Returns ``{action_id, preview, expires_at, next_step}``. The agent
    shows the preview to the user; on approval call
    ``confirm_action(action_id)``; otherwise ``cancel_action``.
    """
    payload_model = ProposeAddTodoInput(
        title=title,
        list_id=list_id,
        notes=notes,
        when=when,
        deadline=deadline,
        tags=tags,
        checklist=checklist,
    )
    payload = payload_model.model_dump()
    preview = handlers.add_todo.make_preview(payload)
    stub = pending.enqueue(
        kind=handlers.add_todo.KIND, payload=payload, preview=preview
    )
    return {
        **stub,
        "next_step": (
            "Show the preview to the user. On approval call "
            "confirm_action(action_id); to drop call cancel_action(action_id)."
        ),
    }


def register(mcp: FastMCP) -> None:
    mcp.tool()(propose_add_todo)
