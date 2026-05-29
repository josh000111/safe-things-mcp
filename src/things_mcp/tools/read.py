"""Read tools registered with FastMCP. All wrap services/things_repo.py."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..services import things_repo


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_inbox() -> list[dict[str, Any]]:
        """All to-dos currently in the Things Inbox."""
        return things_repo.inbox()

    @mcp.tool()
    def list_today() -> list[dict[str, Any]]:
        """To-dos scheduled for Today."""
        return things_repo.today()

    @mcp.tool()
    def list_upcoming(days: int = 7) -> list[dict[str, Any]]:
        """Upcoming scheduled to-dos within the next `days` (default 7)."""
        cutoff = (date.today() + timedelta(days=days)).isoformat()
        return [
            t for t in things_repo.upcoming()
            if (t.get("start_date") or "") <= cutoff
        ]

    @mcp.tool()
    def list_anytime() -> list[dict[str, Any]]:
        """To-dos in the Anytime list."""
        return things_repo.anytime()

    @mcp.tool()
    def list_someday() -> list[dict[str, Any]]:
        """To-dos in the Someday list."""
        return things_repo.someday()

    @mcp.tool()
    def list_logbook(days: int = 7) -> list[dict[str, Any]]:
        """Recently completed to-dos. Filters Logbook to items completed in the last `days`."""
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        return [
            t for t in things_repo.logbook()
            if (t.get("stop_date") or "") >= cutoff
        ]

    @mcp.tool()
    def list_trash() -> list[dict[str, Any]]:
        """Items currently in the Things Trash."""
        return things_repo.trash()

    @mcp.tool()
    def get_areas() -> list[dict[str, Any]]:
        """All top-level Areas."""
        return things_repo.areas()

    @mcp.tool()
    def get_projects(
        area_id: str | None = None, include_completed: bool = False
    ) -> list[dict[str, Any]]:
        """Projects, optionally filtered by Area. Excludes completed unless requested."""
        return things_repo.projects(area=area_id, include_completed=include_completed)

    @mcp.tool()
    def get_project(project_id: str) -> dict[str, Any] | None:
        """Single project with its to-dos, headings, and notes (via ``items``).

        The response includes a ``headings`` list containing both native Things
        section headings and dummy heading tasks (``__NAME__`` format), each
        with ``kind``, ``id``, ``name``, and ``position`` fields. Dummy heading
        tasks are also present in ``items`` as regular to-dos.
        """
        return things_repo.get_project_with_headings(project_id)

    @mcp.tool()
    def get_todo(todo_id: str) -> dict[str, Any] | None:
        """Single to-do including checklist items, tags, project/area refs."""
        return things_repo.todo(todo_id)

    @mcp.tool()
    def get_tags() -> list[dict[str, Any]]:
        """All tags."""
        return things_repo.tags()

    @mcp.tool()
    def search(query: str, limit: int = 25) -> list[dict[str, Any]]:
        """Full-text search across titles and notes. Capped at `limit` results."""
        results = things_repo.search(query)
        return results[:limit]

    @mcp.tool()
    def get_checklist_items(todo_id: str) -> list[dict[str, Any]]:
        """Checklist items for a to-do, with completion state.

        Returns items in order with ``{uuid, title, status}`` fields.
        Note: per-item edit, delete, completion, or reorder are not supported
        — use ``propose_append/prepend/replace_checklist`` to modify the list.
        """
        return things_repo.get_checklist_items(todo_id)
