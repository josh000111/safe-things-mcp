"""V2 ``propose_*`` tools.

A ``propose_*`` tool validates inputs and enqueues a pending action keyed
by ``kind``. It does NOT mutate Things directly — the agent surfaces the
preview to the user, and on approval the agent calls
``confirm_action(action_id)`` which dispatches to the right handler.

### Auto-confirm escape hatch

When the env flag ``THINGS_MCP_AUTO_CONFIRM`` is set (see ``config.py``),
``propose_*`` tools immediately execute their action in the same call
and return the result inline. The preview is still emitted (so the LLM
can summarise) but the user is spared a second round-trip.

**Never bypassable** — kinds listed in ``config.NEVER_BYPASS_KINDS``
(deletes and bulk variants) ALWAYS require an explicit
``confirm_action``, regardless of the flag. This is hard-coded for
safety; users cannot loosen it via env var.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .. import config
from ..models import (
    ProposeAddTodoInput,
    ProposeDeleteTodoInput,
    ProposeMoveTodoInput,
    ProposeUpdateTodoInput,
)
from ..services import handlers
from ..state import pending


# ---------- module-level tool functions (testable without FastMCP) ----------


async def propose_add_todo(
    title: str,
    list_id: str = "inbox",
    notes: str | None = None,
    when: str | None = None,
    deadline: str | None = None,
    tags: list[str] | None = None,
    checklist: list[str] | None = None,
) -> dict:
    """Propose adding a to-do to any list (Inbox, Today, Anytime,
    Someday, or a project UUID).

    Returns ``{action_id, preview, expires_at, auto_confirmed, ...}``.
    On approval the agent calls ``confirm_action(action_id)``; to drop
    call ``cancel_action(action_id)``. When ``THINGS_MCP_AUTO_CONFIRM=1``
    the action is executed immediately and ``auto_confirmed=True`` is
    set — the result lives in the ``result`` field.
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
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.add_todo.KIND, payload=payload, preview=preview
    )


async def propose_update_todo(
    todo_id: str,
    title: str | None = None,
    notes: str | None = None,
    deadline: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Propose editing fields on an existing to-do.

    Convention: ``None`` means "don't change" the field; pass ``""`` to
    clear a string field; pass ``[]`` to clear all tags. At least one
    updatable field must be set.

    Requires ``THINGS_AUTH_TOKEN`` (Things → Settings → General → Enable
    Things URLs → Manage).

    First cut supports: title, notes, deadline, tags. ``when`` rescheduling
    arrives in a follow-up.
    """
    payload_model = ProposeUpdateTodoInput(
        todo_id=todo_id,
        title=title,
        notes=notes,
        deadline=deadline,
        tags=tags,
    )
    # exclude_none so the handler's "is this field being changed?" check
    # works correctly. Empty string / empty list survive (they mean
    # "clear"), but None ("don't touch") gets stripped.
    payload = payload_model.model_dump(exclude_none=True)
    preview = handlers.update_todo.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.update_todo.KIND, payload=payload, preview=preview
    )


async def propose_move_todo(todo_id: str, target: str) -> dict:
    """Propose moving a to-do to a different list or project.

    ``target`` is one of:
    * ``"today"`` / ``"anytime"`` / ``"someday"`` — change scheduling
      (preserves project/area membership).
    * A project/area UUID — change membership (preserves scheduling).

    Requires ``THINGS_AUTH_TOKEN``. Move-to-Inbox and specific-date moves
    are deferred to a follow-up.
    """
    target_lower = target.lower() if target else target
    if target_lower == "inbox":
        raise ValueError(
            "target='inbox' is not supported in V2 first cut. "
            "Use 'today', 'anytime', 'someday', or a project/area UUID."
        )
    if target_lower == "upcoming":
        raise ValueError(
            "target='upcoming' is a computed view in Things, not a move "
            "destination. To schedule a task for a future date that appears "
            "in Upcoming, update the to-do with `when='<YYYY-MM-DD>'` "
            "(specific-date moves arrive in a follow-up)."
        )
    payload_model = ProposeMoveTodoInput(todo_id=todo_id, target=target)
    payload = payload_model.model_dump()
    preview = handlers.move_todo.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.move_todo.KIND, payload=payload, preview=preview
    )


async def propose_delete_todo(todo_id: str) -> dict:
    """Propose soft-deleting a to-do.

    The task is marked canceled+completed via the URL scheme, which
    moves it to the Logbook. The task is **not** purged — use ``undo()``
    to restore it. Hard-delete (move to Trash) requires AppleScript and
    arrives in step 5.

    **Never auto-confirmed.** Even with ``THINGS_MCP_AUTO_CONFIRM=1`` the
    user must call ``confirm_action`` explicitly.

    Requires ``THINGS_AUTH_TOKEN``.
    """
    payload_model = ProposeDeleteTodoInput(todo_id=todo_id)
    payload = payload_model.model_dump()
    preview = handlers.delete_todo.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.delete_todo.KIND, payload=payload, preview=preview
    )


# ---------- shared helper ----------


async def _enqueue_and_maybe_auto_confirm(
    *, kind: str, payload: dict, preview: str
) -> dict:
    """Common tail for every propose tool.

    Always enqueues the action (so it shows up in
    ``list_pending_actions`` and is auditable). If auto-confirm is on
    AND the kind isn't in NEVER_BYPASS_KINDS, immediately dispatches to
    the handler and removes the pending row.

    If the handler fails mid-auto-confirm, we **keep** the pending row
    so the user can retry via ``confirm_action`` after fixing the
    underlying issue (e.g. set a missing auth token). The exception
    propagates so the agent reports it.
    """
    stub = pending.enqueue(kind=kind, payload=payload, preview=preview)

    is_never_bypass = kind in config.NEVER_BYPASS_KINDS
    if not config.AUTO_CONFIRM or is_never_bypass:
        return {
            **stub,
            "auto_confirmed": False,
            "next_step": (
                "Show the preview to the user. On approval call "
                "confirm_action(action_id); to drop call cancel_action(action_id)."
                + (
                    " (Note: this kind is never auto-confirmed — explicit "
                    "approval always required.)"
                    if is_never_bypass and config.AUTO_CONFIRM
                    else ""
                )
            ),
        }

    handler = handlers.get(kind)
    result = await handler.execute(payload)  # may raise; pending row remains
    pending.delete(stub["action_id"])
    return {
        **stub,
        "auto_confirmed": True,
        "result": result,
        "next_step": (
            "Auto-confirmed via THINGS_MCP_AUTO_CONFIRM. Action executed; "
            "use undo() to reverse if needed."
        ),
    }


# ---------- FastMCP registration ----------


def register(mcp: FastMCP) -> None:
    mcp.tool()(propose_add_todo)
    mcp.tool()(propose_update_todo)
    mcp.tool()(propose_move_todo)
    mcp.tool()(propose_delete_todo)
