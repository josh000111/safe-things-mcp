"""``complete_todo`` handler — mark a to-do as completed.

Used by the direct ``complete_todo(todo_id)`` tool (no airlock; single-target
completion is reversible and is the most common everyday mutation) AND by
``propose_bulk_complete`` (step 4 chunk E) which DOES go through the airlock.

Undo strategy: ``things:///update?completed=false`` flips the task back to
``status=incomplete``. Things automatically clears ``stop_date`` on this
reversal. We still capture the full pre-mutation row in ``before_state`` so
edge cases (e.g. the user concurrently edits other fields) leave a forensic
record.

Requires ``THINGS_AUTH_TOKEN``. ``update`` is auth-gated by Cultured Code.
"""
from __future__ import annotations

import asyncio

from ... import config
from .. import things_repo, url_scheme
from ...state import undo_log

KIND = "complete_todo"


def make_preview(payload: dict) -> str:
    """One-line summary. Reused by ``propose_bulk_complete`` if the bulk
    variant ever goes through the airlock."""
    todo_id = payload["todo_id"]
    return f"Mark to-do {todo_id} as completed"


async def execute(payload: dict) -> dict:
    """Mark a to-do completed. Pattern:

    1. Resolve ``todo_id`` against the read-only DB to capture before_state
       (also serves as a "does this task exist?" guard).
    2. Write the undo_log row *before* the URL-scheme call, including the
       captured before_state (so undo can restore exactly).
    3. Build + launch ``things:///update?id=X&completed=true&auth-token=Y``.
    4. Poll the read-only DB until ``status`` flips to ``completed`` (or
       times out with an actionable error).
    5. Attach the post-mutation after_state to the undo_log row.
    """
    todo_id = payload["todo_id"]

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "complete_todo requires THINGS_AUTH_TOKEN. Generate one in "
            "Things → Settings → General → Enable Things URLs → Manage, "
            "then export THINGS_AUTH_TOKEN before retrying."
        )

    before_state = things_repo.get(todo_id)
    if before_state is None:
        raise ValueError(
            f"No to-do found with id={todo_id!r}. It may have been deleted or "
            "the id may be wrong. Use list/search tools to find the right id."
        )

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=todo_id,
        before_state=before_state,
        after_state=None,
    )

    url = url_scheme.build_update_url(
        id=todo_id,
        auth_token=auth_token,
        completed=True,
    )
    await url_scheme.launch(url)

    verified = await _poll_for_status(todo_id, {"completed"})
    undo_log.attach_target(entry_id, target_uuid=todo_id, after_state=verified)

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "id": todo_id,
        "title": verified.get("title", before_state.get("title", "")),
        "status": verified.get("status"),
        "before_status": before_state.get("status"),
    }


async def undo(undo_entry: dict) -> dict:
    """Reverse a completion: flip ``completed`` back to ``false``.

    Cultured Code's ``update`` endpoint accepts ``completed=false``, which
    restores ``status=incomplete`` and clears ``stop_date``.
    """
    target_uuid = undo_entry.get("target_uuid")
    if not target_uuid:
        raise RuntimeError(
            f"undo_log entry {undo_entry['id']} has no target_uuid; the "
            "original complete may not have landed cleanly. Inspect manually."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "Cannot undo a complete_todo without THINGS_AUTH_TOKEN. Generate "
            "one in Things → Settings → General → Enable Things URLs → "
            "Manage, then export THINGS_AUTH_TOKEN before retrying."
        )

    url = url_scheme.build_update_url(
        id=target_uuid,
        auth_token=auth_token,
        completed=False,
    )
    await url_scheme.launch(url)

    verified = await _poll_for_status(target_uuid, {"incomplete"})
    undo_log.delete(undo_entry["id"])

    return {
        "undone": True,
        "action_kind": KIND,
        "target_uuid": target_uuid,
        "status": verified.get("status"),
    }


async def _poll_for_status(target_uuid: str, expected: set[str]) -> dict:
    """Poll the read-only DB until the target task's status matches.

    Shared with ``add_todo.undo``'s polling needs in spirit but kept local
    here to avoid coupling handlers to each other.
    """
    deadline = asyncio.get_running_loop().time() + config.WRITE_POLL_TIMEOUT_SECONDS
    while True:
        row = things_repo.get(target_uuid)
        if row is not None and row.get("status") in expected:
            return row
        if asyncio.get_running_loop().time() >= deadline:
            actual = row.get("status") if row else "missing"
            raise RuntimeError(
                f"Timed out waiting for {target_uuid} to reach status in "
                f"{expected}; observed status={actual!r}."
            )
        await asyncio.sleep(config.WRITE_POLL_INTERVAL_SECONDS)
