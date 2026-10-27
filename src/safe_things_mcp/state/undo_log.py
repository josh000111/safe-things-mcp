"""undo_log CRUD. V1: scaffold only — no rows written yet (no destructive ops)."""
from __future__ import annotations

import json
import uuid as _uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from ..config import UNDO_LOG_MAX_AGE_DAYS, UNDO_LOG_MAX_ROWS
from .db import connect


def _now() -> datetime:
    return datetime.now(UTC)


def record(
    action_kind: str,
    target_uuid: str | None,
    before_state: dict[str, Any] | None,
    after_state: dict[str, Any] | None,
    group_id: str | None = None,
) -> str:
    entry_id = str(_uuid.uuid4())
    created = _now()
    expires = created + timedelta(days=UNDO_LOG_MAX_AGE_DAYS)
    with connect() as conn:
        conn.execute(
            "INSERT INTO undo_log (id, action_kind, target_uuid, before_state_json, "
            "after_state_json, created_at, expires_at, group_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry_id,
                action_kind,
                target_uuid,
                json.dumps(before_state) if before_state is not None else None,
                json.dumps(after_state) if after_state is not None else None,
                created.isoformat(),
                expires.isoformat(),
                group_id,
            ),
        )
        _trim(conn)
    return entry_id


def attach_target(
    entry_id: str,
    target_uuid: str,
    after_state: dict[str, Any] | None = None,
) -> bool:
    """Fill in target_uuid (and optionally after_state) on an existing row.

    Used by add-style mutations: the undo_log row is written *before* the
    URL-scheme call (per the V2 acceptance gate) with ``target_uuid=NULL``,
    then this helper patches in the new task's UUID after polling confirms
    it landed. Returns True if a row was updated.
    """
    with connect() as conn:
        cur = conn.execute(
            "UPDATE undo_log SET target_uuid = ?, after_state_json = ? WHERE id = ?",
            (
                target_uuid,
                json.dumps(after_state) if after_state is not None else None,
                entry_id,
            ),
        )
    return cur.rowcount > 0


def update_after_state(entry_id: str, after_state: dict[str, Any]) -> bool:
    """Replace after_state on an existing row.

    Used by bulk-add mutations to patch in resolved UUIDs after all URL
    launches complete (the row is written before any launch per the V2
    acceptance gate, so after_state starts NULL).
    """
    with connect() as conn:
        cur = conn.execute(
            "UPDATE undo_log SET after_state_json = ? WHERE id = ?",
            (json.dumps(after_state), entry_id),
        )
    return cur.rowcount > 0


def update_before_state(entry_id: str, before_state: dict[str, Any]) -> bool:
    """Replace before_state on an existing row.

    Used after find-or-create steps to patch in values (e.g. marker_uuid,
    marker_created) that were unknown at the time the row was first written.
    """
    with connect() as conn:
        cur = conn.execute(
            "UPDATE undo_log SET before_state_json = ? WHERE id = ?",
            (json.dumps(before_state), entry_id),
        )
    return cur.rowcount > 0


def delete(entry_id: str) -> bool:
    """Remove a single undo_log row. Used after a successful undo so the
    same action can't be undone twice."""
    with connect() as conn:
        cur = conn.execute("DELETE FROM undo_log WHERE id = ?", (entry_id,))
    return cur.rowcount > 0


def most_recent() -> dict[str, Any] | None:
    """Return the full row for the most recently recorded action, or None."""
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM undo_log ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return get(row["id"])


def recent(limit: int = 20) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, action_kind, target_uuid, created_at, expires_at, group_id "
            "FROM undo_log ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def list() -> list[dict[str, Any]]:
    """Return all undo_log entries, newest first."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id FROM undo_log ORDER BY created_at DESC"
        ).fetchall()
    return [{"id": r["id"]} for r in rows]


def get_by_group_id(group_id: str) -> list[dict[str, Any]]:
    """Return all entries in a group, ordered newest-first (LIFO for undo)."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id FROM undo_log WHERE group_id = ? ORDER BY created_at DESC",
            (group_id,),
        ).fetchall()
    return [get(r["id"]) for r in rows if get(r["id"]) is not None]


def get(entry_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM undo_log WHERE id = ?", (entry_id,)).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "action_kind": row["action_kind"],
        "target_uuid": row["target_uuid"],
        "before_state": json.loads(row["before_state_json"]) if row["before_state_json"] else None,
        "after_state": json.loads(row["after_state_json"]) if row["after_state_json"] else None,
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
        "group_id": row["group_id"] if "group_id" in row.keys() else None,
    }


def _trim(conn) -> None:
    conn.execute("DELETE FROM undo_log WHERE expires_at < ?", (_now().isoformat(),))
    conn.execute(
        "DELETE FROM undo_log WHERE id IN ("
        "SELECT id FROM undo_log ORDER BY created_at DESC LIMIT -1 OFFSET ?)",
        (UNDO_LOG_MAX_ROWS,),
    )
