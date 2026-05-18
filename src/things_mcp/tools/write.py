"""Write tools. V1: a single Inbox-quarantined create."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP

from ..config import WRITE_POLL_INTERVAL_SECONDS, WRITE_POLL_TIMEOUT_SECONDS
from ..models import AddInboxTodoInput, AddInboxTodoResult
from ..services import things_repo, url_scheme


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
        """Create a new to-do in the Things Inbox.

        V1 hard-codes list=inbox. Writes go via the Things URL scheme; the
        new task's UUID is recovered by polling the read-only Things DB for
        a matching newly-created Inbox row (the old ``x-callback-url`` path
        opened a Safari tab per call and was retired).
        """
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


async def _poll_for_new_todo(title: str, created_after: str) -> dict:
    """Poll the Things DB for the new Inbox task created by the URL scheme.

    Raises ``RuntimeError`` on timeout — Things may not be running, the URL
    scheme may be disabled, or the launch may have silently failed.
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
