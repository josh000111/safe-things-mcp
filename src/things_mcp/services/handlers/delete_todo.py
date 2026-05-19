"""``delete_todo`` handler — soft-delete a to-do.

V2 step 4 chunk C ships a soft-delete: the task is marked canceled AND
completed via the Things URL scheme, which moves it out of all active
lists and into the Logbook. The task itself is preserved (no data loss),
so undo can restore it fully.

A true hard-delete (move to Trash) requires AppleScript and is gated
behind ``THINGS_MCP_ALLOW_APPLESCRIPT`` in step 5.

This is the first **`NEVER_BYPASS_KIND`** to actually wire up — even
when ``THINGS_MCP_AUTO_CONFIRM=1`` the user must explicitly call
``confirm_action`` for a delete. The propose-layer enforces that;
nothing in this handler relies on it.

Requires ``THINGS_AUTH_TOKEN``.
"""
from __future__ import annotations

import asyncio

from ... import config
from .. import things_repo, url_scheme
from ...state import undo_log

KIND = "delete_todo"


def make_preview(payload: dict) -> str:
    return (
        f"Soft-delete to-do {payload['todo_id']} "
        "(mark canceled+completed → moves to Logbook; restorable via undo)"
    )


async def execute(payload: dict) -> dict:
    todo_id = payload["todo_id"]

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "delete_todo requires THINGS_AUTH_TOKEN. Generate one in "
            "Things → Settings → General → Enable Things URLs → Manage, "
            "then export THINGS_AUTH_TOKEN before retrying."
        )

    before = things_repo.get_todo(todo_id)
    if before is None:
        raise ValueError(
            f"No to-do found with id={todo_id!r}. It may have been deleted "
            "or the id may be wrong."
        )
    if before.get("status") in {"canceled", "completed"}:
        raise ValueError(
            f"to-do {todo_id!r} is already status={before.get('status')!r}. "
            "Nothing to delete. Use undo() if you want to restore it."
        )

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=todo_id,
        before_state={"full": before, "status": before.get("status")},
        after_state=None,
    )

    url = url_scheme.build_update_url(
        id=todo_id,
        auth_token=auth_token,
        canceled=True,
        completed=True,
    )
    await url_scheme.launch(url)

    verified = await _poll_for_status(todo_id, {"canceled", "completed"})
    undo_log.attach_target(entry_id, target_uuid=todo_id, after_state=verified)

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "id": todo_id,
        "title": verified.get("title", before.get("title", "")),
        "status": verified.get("status"),
        "note": (
            "Soft-deleted: task moved to Logbook (canceled). Use undo() "
            "to restore. Hard-delete via AppleScript arrives in step 5."
        ),
    }


async def undo(undo_entry: dict) -> dict:
    """Restore a soft-deleted task: flip canceled+completed back to false."""
    target_uuid = undo_entry.get("target_uuid")
    if not target_uuid:
        raise RuntimeError(
            f"undo_log entry {undo_entry.get('id')!r} has no target_uuid; "
            "original delete may not have landed cleanly."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "Cannot undo delete_todo without THINGS_AUTH_TOKEN. Set it "
            "and retry."
        )

    url = url_scheme.build_update_url(
        id=target_uuid,
        auth_token=auth_token,
        canceled=False,
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
