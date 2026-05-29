"""``cancel_todo`` handler — mark a to-do as canceled.

Uses ``things:///update?canceled=true`` (URL scheme). Undo uses
``canceled=false`` to restore to incomplete. NOT in NEVER_BYPASS_KINDS —
canceling is reversible and low-risk.

Requires ``THINGS_AUTH_TOKEN``.
"""
from __future__ import annotations

import asyncio

from ... import config
from .. import things_repo, url_scheme
from ...state import undo_log

KIND = "cancel_todo"


def make_preview(payload: dict) -> str:
    todo_id = payload["todo_id"]
    return f"Mark to-do {todo_id} as canceled"


async def execute(payload: dict) -> dict:
    todo_id = payload["todo_id"]

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "cancel_todo requires THINGS_AUTH_TOKEN. Generate one in "
            "Things → Settings → General → Enable Things URLs → Manage, "
            "then export THINGS_AUTH_TOKEN before retrying."
        )

    before_state = things_repo.get(todo_id)
    if before_state is None:
        raise ValueError(
            f"No to-do found with id={todo_id!r}. It may have been deleted or "
            "the id may be wrong. Use list/search tools to find the right id."
        )
    if before_state.get("status") == "canceled":
        raise ValueError(
            f"To-do {todo_id!r} is already canceled. Nothing to do."
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
        canceled=True,
    )
    await url_scheme.launch(url)

    verified = await _poll_for_status(todo_id, {"canceled"})
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
    target_uuid = undo_entry.get("target_uuid")
    if not target_uuid:
        raise RuntimeError(
            f"undo_log entry {undo_entry['id']} has no target_uuid; the "
            "original cancel may not have landed cleanly. Inspect manually."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "Cannot undo a cancel_todo without THINGS_AUTH_TOKEN. Generate "
            "one in Things → Settings → General → Enable Things URLs → "
            "Manage, then export THINGS_AUTH_TOKEN before retrying."
        )

    url = url_scheme.build_update_url(
        id=target_uuid,
        auth_token=auth_token,
        canceled=False,
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
