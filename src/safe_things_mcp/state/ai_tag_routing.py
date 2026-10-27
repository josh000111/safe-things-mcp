"""CRUD helpers for ai_tag_routing — per-tag application records for AI-managed tags."""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime
from typing import Any

from .db import connect


def _now() -> str:
    return datetime.now(UTC).isoformat()


def insert(
    tag_name: str,
    todo_uuid: str,
    dest_kind: str | None,
    dest_uuid: str | None,
    transient: bool,
) -> str:
    """Insert a new routing row and return its id."""
    row_id = str(_uuid.uuid4())
    with connect() as conn:
        conn.execute(
            "INSERT INTO ai_tag_routing (id, tag_name, todo_uuid, dest_kind, dest_uuid, transient, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (row_id, tag_name, todo_uuid, dest_kind, dest_uuid, 1 if transient else 0, _now()),
        )
    return row_id


def upsert(
    tag_name: str,
    todo_uuid: str,
    dest_kind: str | None,
    dest_uuid: str | None,
    transient: bool,
) -> str:
    """Insert or update (idempotent on tag_name+todo_uuid)."""
    with connect() as conn:
        existing = conn.execute(
            "SELECT id FROM ai_tag_routing WHERE tag_name = ? AND todo_uuid = ?",
            (tag_name, todo_uuid),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE ai_tag_routing SET dest_kind=?, dest_uuid=?, transient=? WHERE id=?",
                (dest_kind, dest_uuid, 1 if transient else 0, existing["id"]),
            )
            return existing["id"]
        return insert(tag_name, todo_uuid, dest_kind, dest_uuid, transient)


def get(row_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM ai_tag_routing WHERE id = ?", (row_id,)
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def get_for_todo(todo_uuid: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM ai_tag_routing WHERE todo_uuid = ?", (todo_uuid,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_transient_for_todos(todo_uuids: list[str]) -> list[dict[str, Any]]:
    """Return all transient=1 rows matching the given todo_uuids."""
    if not todo_uuids:
        return []
    placeholders = ",".join("?" * len(todo_uuids))
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM ai_tag_routing WHERE transient=1 AND todo_uuid IN ({placeholders})",
            todo_uuids,
        ).fetchall()
    return [dict(r) for r in rows]


def delete(row_id: str) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM ai_tag_routing WHERE id = ?", (row_id,))
    return cur.rowcount > 0


def delete_for_todo(todo_uuid: str) -> int:
    with connect() as conn:
        cur = conn.execute("DELETE FROM ai_tag_routing WHERE todo_uuid = ?", (todo_uuid,))
    return cur.rowcount


def delete_by_ids(ids: list[str]) -> int:
    if not ids:
        return 0
    placeholders = ",".join("?" * len(ids))
    with connect() as conn:
        cur = conn.execute(f"DELETE FROM ai_tag_routing WHERE id IN ({placeholders})", ids)
    return cur.rowcount


def restore_rows(rows: list[dict[str, Any]]) -> None:
    """Re-insert previously deleted rows (used by undo)."""
    with connect() as conn:
        for row in rows:
            conn.execute(
                "INSERT OR REPLACE INTO ai_tag_routing "
                "(id, tag_name, todo_uuid, dest_kind, dest_uuid, transient, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    row["id"], row["tag_name"], row["todo_uuid"],
                    row.get("dest_kind"), row.get("dest_uuid"),
                    row.get("transient", 0), row.get("created_at", _now()),
                ),
            )
