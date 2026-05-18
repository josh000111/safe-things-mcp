"""pending_actions CRUD. V1: scaffold only — no propose tools wired yet."""
from __future__ import annotations

import json
import uuid as _uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from ..config import PENDING_TTL_SECONDS
from .db import connect


def _now() -> datetime:
    return datetime.now(UTC)


def enqueue(kind: str, payload: dict[str, Any], preview: str) -> dict[str, Any]:
    action_id = str(_uuid.uuid4())
    created = _now()
    expires = created + timedelta(seconds=PENDING_TTL_SECONDS)
    with connect() as conn:
        conn.execute(
            "INSERT INTO pending_actions (id, kind, payload_json, preview, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (action_id, kind, json.dumps(payload), preview, created.isoformat(), expires.isoformat()),
        )
    return {"action_id": action_id, "preview": preview, "expires_at": expires.isoformat()}


def get(action_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM pending_actions WHERE id = ?", (action_id,)
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "kind": row["kind"],
        "payload": json.loads(row["payload_json"]),
        "preview": row["preview"],
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
    }


def delete(action_id: str) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM pending_actions WHERE id = ?", (action_id,))
    return cur.rowcount > 0


def list_all() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, kind, preview, created_at, expires_at FROM pending_actions "
            "ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def sweep_expired() -> int:
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM pending_actions WHERE expires_at < ?", (_now().isoformat(),)
        )
    return cur.rowcount
