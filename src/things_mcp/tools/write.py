"""Direct write tools — no airlock.

These tools mutate Things in a single MCP call, without going through
``propose_*`` / ``confirm_action``. The split is intentional:

* V1 ``add_inbox_todo`` — pre-V2 surface. Does NOT write an undo_log row
  (kept as the simplest, lowest-overhead path; Inbox quarantine made undo
  unnecessary at V1 time).
* V2 direct adds (``add_today_todo``, ``add_anytime_todo``,
  ``add_someday_todo``) — go through ``handlers.add_todo`` so the undo
  log catches them. Users can call ``undo()`` after any of these.
* V2 direct ``complete_todo`` — single-target completion. Reversible
  (``undo()`` flips it back). The bulk variant lives behind the airlock
  (``propose_bulk_complete``, step 4 chunk E).

Any operation that's destructive, multi-target, or hard to spot afterward
goes through the propose/confirm path instead — see ``tools/propose.py``.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP

from ..config import WRITE_POLL_INTERVAL_SECONDS, WRITE_POLL_TIMEOUT_SECONDS
from ..models import AddInboxTodoInput, AddInboxTodoResult, DirectAddTodoInput
from ..services import handlers, things_repo, url_scheme


_CREATED_FMT = "%Y-%m-%d %H:%M:%S"
_CLOCK_SLACK = timedelta(seconds=2)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def add_inbox_todo(
        title: str,
        notes: str | None = None,
        when: str | None = None,
        deadline: str | None = None,
        tags: list[str] | None = None,
        checklist: list[str] | None = None,
    ) -> dict:
        """Create a new to-do in the Things Inbox (V1, no undo log).

        Hard-codes ``list=inbox``. The new task's UUID is recovered by
        polling the read-only Things DB. Use this for fast Inbox triage
        writes when you don't need ``undo()`` support — for that, prefer
        ``propose_add_todo(list_id='inbox')``.
        """
        url_scheme.validate_tags(tags)
        payload = AddInboxTodoInput(
            title=title,
            notes=notes,
            when=when,
            deadline=deadline,
            tags=tags,
            checklist=checklist,
        )

        created_after = (datetime.now() - _CLOCK_SLACK).strftime(_CREATED_FMT)

        url = url_scheme.build_add_url(
            title=payload.title,
            list_id="inbox",
            notes=payload.notes,
            when=payload.when,
            deadline=payload.deadline,
            tags=payload.tags,
            checklist_items=payload.checklist,
        )
        await url_scheme.launch(url)

        verified = await _poll_for_new_todo(payload.title, created_after)

        return AddInboxTodoResult(
            id=verified["uuid"],
            title=verified.get("title", payload.title),
            created_at=verified.get("created", created_after),
        ).model_dump()

    @mcp.tool()
    async def add_today_todo(
        title: str,
        notes: str | None = None,
        deadline: str | None = None,
        tags: list[str] | None = None,
        checklist: list[str] | None = None,
    ) -> dict:
        """Create a new to-do scheduled for Today. Undoable via ``undo()``.

        Uses the V2 ``add_todo`` handler so an ``undo_log`` row is
        captured automatically.
        """
        return await _direct_add(
            list_id="today",
            title=title,
            notes=notes,
            deadline=deadline,
            tags=tags,
            checklist=checklist,
        )

    @mcp.tool()
    async def add_anytime_todo(
        title: str,
        notes: str | None = None,
        deadline: str | None = None,
        tags: list[str] | None = None,
        checklist: list[str] | None = None,
    ) -> dict:
        """Create a new to-do in Anytime. Undoable via ``undo()``."""
        return await _direct_add(
            list_id="anytime",
            title=title,
            notes=notes,
            deadline=deadline,
            tags=tags,
            checklist=checklist,
        )

    @mcp.tool()
    async def add_someday_todo(
        title: str,
        notes: str | None = None,
        deadline: str | None = None,
        tags: list[str] | None = None,
        checklist: list[str] | None = None,
    ) -> dict:
        """Create a new to-do in Someday. Undoable via ``undo()``."""
        return await _direct_add(
            list_id="someday",
            title=title,
            notes=notes,
            deadline=deadline,
            tags=tags,
            checklist=checklist,
        )

    @mcp.tool()
    async def complete_todo(todo_id: str) -> dict:
        """Mark a to-do as completed. Undoable via ``undo()``.

        Single-target only — for batches use ``propose_bulk_complete``,
        which surfaces a preview before executing.

        Requires ``THINGS_AUTH_TOKEN`` (Things → Settings → General →
        Enable Things URLs → Manage).
        """
        if not todo_id:
            raise ValueError("todo_id is required")
        return await handlers.complete_todo.execute({"todo_id": todo_id})


async def _direct_add(
    *,
    list_id: str,
    title: str,
    notes: str | None,
    deadline: str | None,
    tags: list[str] | None,
    checklist: list[str] | None,
) -> dict:
    """Validate inputs and delegate to ``handlers.add_todo.execute``.

    Direct adds are conceptually identical to ``confirm_action`` on a
    pre-existing ``propose_add_todo`` — we skip the queue but still go
    through the handler for undo-log bookkeeping.
    """
    url_scheme.validate_tags(tags)
    payload_model = DirectAddTodoInput(
        title=title,
        list_id=list_id,
        notes=notes,
        deadline=deadline,
        tags=tags,
        checklist=checklist,
    )
    return await handlers.add_todo.execute(payload_model.model_dump())


async def _poll_for_new_todo(title: str, created_after: str) -> dict:
    """Poll the Things DB for the new Inbox task created by the URL scheme.

    Only used by V1 ``add_inbox_todo``. V2 paths poll via the add_todo
    handler's own helper.
    """
    deadline = asyncio.get_running_loop().time() + WRITE_POLL_TIMEOUT_SECONDS
    while True:
        match = things_repo.find_recent_inbox_by_title(title, created_after)
        if match is not None:
            return match
        if asyncio.get_running_loop().time() >= deadline:
            raise RuntimeError(
                f"Timed out after {WRITE_POLL_TIMEOUT_SECONDS}s waiting for "
                f"Things to create a to-do titled {title!r} in the Inbox. "
                "Is the Things app running and is the URL scheme enabled in "
                "Settings → General → Enable Things URLs?"
            )
        await asyncio.sleep(WRITE_POLL_INTERVAL_SECONDS)
