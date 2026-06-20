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

    @mcp.tool()
    def list_ai_tags() -> dict:
        """List all AI-managed tags under the AI parent, with tasks and routing info.

        Use this during the REVIEW PHASE of a tag-first→review→move sort to
        inspect proposed routing before confirming ``bulk_move``. Each tag shows:
        - tasks carrying it (uuid, title, status)
        - routing rows from ``ai_tag_routing`` (proposed destination, transient flag)

        Disambiguating context for destinations:
        - "Name — in Area 'AreaName'" for projects inside an Area
        - "Name — a standalone project (not in any Area)" for top-level projects

        Persistent abstain tags (``*Unclear*``, ``*Duplicate?*``,
        ``*Ambiguous Home*``, ``*No Time Signal*``, ``*Review Delete?*``)
        appear here and must be resolved manually — they are never
        auto-cleaned by ``cleanup_ai_tags``.
        """
        from ..state import ai_tag_routing as atr
        from ..config import AI_TAG_PARENT

        # Get all tags with items
        all_tags = things_repo.tags(include_items=True)

        # Find the AI parent tag
        ai_parent = next((t for t in all_tags if t.get("title") == AI_TAG_PARENT), None)

        # Get all areas and projects for disambiguation
        all_areas = things_repo.areas()
        all_projects = things_repo.projects()

        area_by_id = {a["uuid"]: a for a in all_areas}

        def dest_label(dest_kind: str | None, dest_uuid: str | None) -> str | None:
            if not dest_kind or not dest_uuid:
                return None
            if dest_kind == "area":
                a = area_by_id.get(dest_uuid)
                return f"{a['title']} (area)" if a else f"Area {dest_uuid}"
            if dest_kind == "project":
                proj = next((p for p in all_projects if p["uuid"] == dest_uuid), None)
                if proj:
                    area_id = proj.get("area") or proj.get("area_id")
                    if area_id and area_id in area_by_id:
                        area_name = area_by_id[area_id]["title"]
                        return f"{proj['title']} — in Area '{area_name}'"
                    return f"{proj['title']} — a standalone project (not in any Area)"
                return f"Project {dest_uuid}"
            return f"{dest_kind} {dest_uuid}"

        # Build a uuid→parent_uuid map directly from TMTag (things.py's flat list
        # omits the parent field, so we query SQLite ourselves, read-only).
        import sqlite3 as _sqlite3
        from ..config import THINGS_DB_PATH as _DB_PATH
        _child_uuids: set[str] = set()
        try:
            with _sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True) as _conn:
                _rows = _conn.execute(
                    "SELECT child.uuid FROM TMTag child "
                    "JOIN TMTag parent ON child.parent = parent.uuid "
                    "WHERE parent.title = ?",
                    (AI_TAG_PARENT,),
                ).fetchall()
                _child_uuids = {r[0] for r in _rows}
        except Exception:
            pass  # Fall back to empty set; ai_tags will be [] rather than crash

        # Collect AI child tags
        ai_children: list[dict] = []
        if ai_parent:
            for tag in all_tags:
                if tag.get("uuid") not in _child_uuids:
                    continue
                title = tag.get("title", "")
                # Get tasks carrying this tag
                tasks = tag.get("items") or []
                task_summaries = [
                    {"uuid": t.get("uuid"), "title": t.get("title"), "status": t.get("status")}
                    for t in tasks if isinstance(t, dict)
                ]
                # Get routing rows for tasks carrying this tag
                task_uuids = [t["uuid"] for t in task_summaries if t.get("uuid")]
                routing_rows = []
                if task_uuids:
                    for task_uuid in task_uuids:
                        rows = atr.get_for_todo(task_uuid)
                        for row in rows:
                            if row.get("tag_name") == title:
                                routing_rows.append({
                                    "todo_uuid": task_uuid,
                                    "dest_kind": row.get("dest_kind"),
                                    "dest_uuid": row.get("dest_uuid"),
                                    "transient": bool(row.get("transient")),
                                    "dest_label": dest_label(
                                        row.get("dest_kind"), row.get("dest_uuid")
                                    ),
                                })
                ai_children.append({
                    "name": title,
                    "transient": any(r["transient"] for r in routing_rows) if routing_rows else False,
                    "task_count": len(task_summaries),
                    "tasks": task_summaries,
                    "routing": routing_rows,
                })

        return {
            "ai_parent": AI_TAG_PARENT,
            "ai_parent_found": ai_parent is not None,
            "ai_tags": ai_children,
            "total_tags": len(ai_children),
        }
