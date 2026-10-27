"""DB-backed tracking for the AI sort workflow.

Replaces the previous module-global backing store with three SQLite tables
(``sort_session``, ``sort_session_tagged``, ``sort_session_project``) so the
invariants survive process restarts and multi-process deployments.

Public function signatures are unchanged — callers do not need to be updated.

Tables (created/migrated by :func:`state.db.init_state_db` at startup):

* ``sort_session(group_id TEXT PK, created_at TEXT, active INTEGER)``
* ``sort_session_tagged(group_id TEXT, todo_uuid TEXT)``
* ``sort_session_project(group_id TEXT, project_uuid TEXT)``

Lifecycle
---------
* ``begin(group_id)`` — open or reuse a non-stale active session.
  A session is stale when its ``created_at`` is older than
  ``_STALE_HOURS`` hours.  Stale sessions are superseded (marked inactive)
  and a fresh one is started.  If ``group_id`` is ``None`` a UUID4 is
  generated.
* ``register_tagged(uuids)`` — persist tagged task UUIDs for the active group.
* ``is_sort_move(todo_ids)`` — True iff a non-stale active session exists AND
  every id was registered by ``register_tagged``.
* ``register_created_project / is_ai_created`` — persist/query into
  ``sort_session_project``. ``is_ai_created`` queries ALL sessions
  (cross-session identity, preserved from the old behaviour).
* ``end()`` — mark the active session inactive; delete its tagged rows.
  Project rows are kept (AI-created project identity must survive session end).
* ``reset()`` — test helper: hard-deletes all three tables' rows.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from .db import connect

_STALE_HOURS = 6


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _is_stale(created_at: str) -> bool:
    """Return True if *created_at* is older than _STALE_HOURS hours."""
    try:
        created = datetime.fromisoformat(created_at)
    except ValueError:
        return True
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return datetime.now(UTC) - created > timedelta(hours=_STALE_HOURS)


# ---------- session lifecycle ----------


def begin(group_id: str | None = None) -> str:
    """Open (or reuse) a sort session and return its group_id.

    Reuse-if-active semantics: if a non-stale active session already exists
    and *group_id* is None, reuse it (accumulate tagged UUIDs into the same
    group).  If *group_id* is provided, set the active group to that value
    (creates a new row if it did not exist).

    A stale session (created > 6 h ago) is superseded: the old row is marked
    inactive and a fresh session is started.
    """
    with connect() as conn:
        # Find any currently active session row.
        row = conn.execute(
            "SELECT group_id, created_at FROM sort_session WHERE active = 1 LIMIT 1"
        ).fetchone()

        if row is not None:
            existing_id = row["group_id"]
            existing_stale = _is_stale(row["created_at"])

            if not existing_stale:
                # Non-stale active session exists.
                if group_id is None or group_id == existing_id:
                    # Reuse it.
                    return existing_id
                else:
                    # Caller supplied a *different* explicit group_id — supersede.
                    conn.execute(
                        "UPDATE sort_session SET active = 0 WHERE group_id = ?",
                        (existing_id,),
                    )
            else:
                # Stale: supersede regardless.
                conn.execute(
                    "UPDATE sort_session SET active = 0 WHERE group_id = ?",
                    (existing_id,),
                )

        # Start a fresh session.
        new_id = group_id if group_id is not None else str(uuid.uuid4())
        conn.execute(
            "INSERT OR REPLACE INTO sort_session (group_id, created_at, active) "
            "VALUES (?, ?, 1)",
            (new_id, _now()),
        )
        return new_id


def active() -> str | None:
    """Return the current session's group_id, or ``None`` if none is open.

    Stale sessions are treated as if they don't exist.
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT group_id, created_at FROM sort_session WHERE active = 1 LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    if _is_stale(row["created_at"]):
        return None
    return row["group_id"]


def end() -> str | None:
    """Close the active session.  Returns the group_id that was active.

    Marks the session row inactive and deletes its tagged rows.
    Project rows are intentionally kept so ``is_ai_created`` remains
    accurate after the session ends.
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT group_id FROM sort_session WHERE active = 1 LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        group = row["group_id"]
        conn.execute(
            "UPDATE sort_session SET active = 0 WHERE group_id = ?", (group,)
        )
        conn.execute(
            "DELETE FROM sort_session_tagged WHERE group_id = ?", (group,)
        )
        return group


# ---------- tagged-membership tracking ----------


def register_tagged(uuids) -> None:
    """Record task UUIDs tagged by the active sort.

    Accepts any iterable of UUID strings.  Falsy values (``None``, empty
    string) are silently skipped.  No-ops when no session is active.
    """
    group = active()
    if group is None:
        return
    valid = [uid for uid in uuids if uid]
    if not valid:
        return
    with connect() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO sort_session_tagged (group_id, todo_uuid) VALUES (?, ?)",
            [(group, uid) for uid in valid],
        )


def is_sort_move(todo_ids) -> bool:
    """True iff this move is fully within the active sort's membership.

    Returns ``True`` only when:

    * A non-stale sort session is active, AND
    * ``todo_ids`` is non-empty, AND
    * EVERY id in ``todo_ids`` was registered by ``register_tagged``.

    A mixed or unrelated move (any untagged task) returns ``False`` —
    conservative, prevents a stale session from capturing unrelated moves.
    """
    group = active()
    if group is None:
        return False
    ids = list(todo_ids)
    if not ids:
        return False
    placeholders = ",".join("?" * len(ids))
    with connect() as conn:
        count = conn.execute(
            f"SELECT COUNT(*) FROM sort_session_tagged "
            f"WHERE group_id = ? AND todo_uuid IN ({placeholders})",
            [group, *ids],
        ).fetchone()[0]
    return count == len(ids)


# ---------- AI-created project tracking ----------


_SENTINEL_GROUP = "__global__"


def register_created_project(project_uuid: str) -> None:
    """Record a project UUID the AI created, so it is excluded from auto-marking.

    When no sort session is active the project is recorded under a sentinel
    group (``__global__``) so ``is_ai_created`` still returns ``True`` for
    it across any future session.
    """
    if not project_uuid:
        return
    group = active()
    if group is None:
        # No live session — fall back to any active row, then the sentinel.
        with connect() as conn:
            row = conn.execute(
                "SELECT group_id FROM sort_session WHERE active = 1 LIMIT 1"
            ).fetchone()
            group = row["group_id"] if row is not None else _SENTINEL_GROUP
            if group == _SENTINEL_GROUP:
                # Ensure the sentinel row exists.
                conn.execute(
                    "INSERT OR IGNORE INTO sort_session "
                    "(group_id, created_at, active) VALUES (?, ?, 0)",
                    (_SENTINEL_GROUP, _now()),
                )
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sort_session_project (group_id, project_uuid) VALUES (?, ?)",
            (group, project_uuid),
        )


def is_ai_created(project_uuid: str) -> bool:
    """True if ``project_uuid`` was created by the AI in ANY session.

    Cross-session/process-lifetime semantics: once a project is recorded as
    AI-created (across any past session), it is permanently flagged.
    """
    if not project_uuid:
        return False
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM sort_session_project WHERE project_uuid = ? LIMIT 1",
            (project_uuid,),
        ).fetchone()
    return row is not None


def record_rejected_project(title: str, task_ids: list[str] | None) -> None:
    """Write a row to sort_guard_rejected when the <3-task guard fires.

    No-ops if no sort session is active (guard should only fire during a
    session, but guard defensively).
    """
    group = active()
    if group is None:
        return
    ids = list(task_ids) if task_ids else []
    with connect() as conn:
        conn.execute(
            "INSERT INTO sort_guard_rejected "
            "(id, group_id, title, member_count, task_ids_json, rejected_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), group, title, len(ids), json.dumps(ids), _now()),
        )


# ---------- test helper ----------


def reset() -> None:
    """Clear all session state.  Test helper — not used in normal operation."""
    with connect() as conn:
        conn.execute("DELETE FROM sort_session_tagged")
        conn.execute("DELETE FROM sort_session_project")
        conn.execute("DELETE FROM sort_guard_rejected")
        conn.execute("DELETE FROM sort_session")
