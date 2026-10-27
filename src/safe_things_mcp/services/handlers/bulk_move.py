"""``bulk_move`` handler — move multiple to-dos to a single target.

Bulk version of :mod:`move_todo`. The target applies uniformly to every
to-do in the batch, but the **inverse params are per-item** (each task
has its own original scheduling / project membership to restore on undo).

Reuses the inverse-derivation helpers from :mod:`move_todo` so the
restore logic stays in one place — refactoring those into a shared util
is overkill for two callers.

Requires ``THINGS_AUTH_TOKEN``. Always in :data:`config.NEVER_BYPASS_KINDS`.
"""
from __future__ import annotations

from ... import config
from .. import applescript, things_repo, url_scheme
from ...state import undo_log
from .move_todo import (
    _REJECT_KEYWORDS,
    _WHEN_KEYWORDS,
    _inverse_project,
    _inverse_scheduling,
)

KIND = "bulk_move"


def make_preview(payload: dict) -> str:
    n = len(payload.get("todo_ids") or [])
    target = payload.get("target")
    return f"Bulk move {n} to-do{'s' if n != 1 else ''} to {target!r}"


async def execute(payload: dict) -> dict:
    todo_ids = list(payload.get("todo_ids") or [])
    if not todo_ids:
        raise ValueError("bulk_move requires a non-empty todo_ids list.")

    target = payload.get("target")
    if not target:
        raise ValueError("target is required")
    target_lower = target.strip().lower()

    if target_lower in _REJECT_KEYWORDS:
        raise ValueError(
            f"target={target!r} not supported by bulk_move. "
            "Supported: 'inbox' (requires SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1), "
            "'today', 'anytime', 'someday', or a project/area UUID."
        )

    if target_lower == "inbox" and not config.ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "Bulk move to Inbox requires SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1. "
            "Set the environment variable and restart the MCP server."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "bulk_move requires THINGS_AUTH_TOKEN. Generate one in "
            "Things → Settings → General → Enable Things URLs → Manage, "
            "then export THINGS_AUTH_TOKEN before retrying."
        )

    is_inbox_move = target_lower == "inbox"
    is_scheduling_move = target_lower in _WHEN_KEYWORDS
    dimension = "inbox" if is_inbox_move else ("schedule" if is_scheduling_move else "project")

    group_id = payload.get("group_id")

    items: list[dict] = []
    for uid in todo_ids:
        row = things_repo.get_todo(uid)
        if row is None:
            raise ValueError(
                f"No to-do found with id={uid!r}. Bulk move aborts before "
                "any mutation."
            )
        if is_inbox_move:
            inverse_params = _inverse_scheduling(row)
            move_params: dict = {}  # handled via AppleScript
        elif is_scheduling_move:
            inverse_params = _inverse_scheduling(row)
            move_params = {"when": target_lower}
        else:
            inverse_params = _inverse_project(row)
            move_params = {"list_id": target}
        items.append({
            "target_uuid": uid,
            "title": row.get("title"),
            "inverse_params": inverse_params,
            "move_params": move_params,
        })

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=None,
        before_state={
            "items": items,
            "count": len(items),
            "dimension": dimension,
            "target": target,
        },
        after_state=None,
        group_id=group_id,
    )

    if is_inbox_move:
        lines = "\n".join(
            f'    move to do id "{applescript.escape(it["target_uuid"])}" to list "Inbox"'
            for it in items
        )
        script = f'tell application "Things3"\n{lines}\nend tell'
        await applescript.run_script(script)
    else:
        for item in items:
            url = url_scheme.build_update_url(
                id=item["target_uuid"],
                auth_token=auth_token,
                **item["move_params"],
            )
            await url_scheme.launch(url)

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "count": len(items),
        "ids": [it["target_uuid"] for it in items],
        "target": target,
        "dimension": dimension,
    }


async def undo(undo_entry: dict) -> dict:
    before = undo_entry.get("before_state")
    if not isinstance(before, dict) or not before.get("items"):
        raise RuntimeError(
            f"undo_log entry {undo_entry.get('id')!r} has no items to "
            "restore; original bulk_move may have failed before logging."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "Cannot undo bulk_move without THINGS_AUTH_TOKEN. Set it and "
            "retry."
        )

    # Partition items: those restoring to Inbox (AppleScript) vs URL scheme.
    inbox_items = [
        it for it in before["items"]
        if (it.get("inverse_params") or {}).get("to_inbox")
    ]
    url_items = [
        it for it in before["items"]
        if it not in inbox_items and (it.get("inverse_params") or {})
    ]

    if inbox_items:
        if not config.ALLOW_APPLESCRIPT:
            raise RuntimeError(
                "Cannot undo bulk_move back to Inbox without "
                "SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1. Set it and retry."
            )
        lines = "\n".join(
            f'    move to do id "{applescript.escape(it["target_uuid"])}" to list "Inbox"'
            for it in inbox_items
        )
        script = f'tell application "Things3"\n{lines}\nend tell'
        await applescript.run_script(script)

    for item in url_items:
        inverse_params = item["inverse_params"]
        url = url_scheme.build_update_url(
            id=item["target_uuid"],
            auth_token=auth_token,
            **inverse_params,
        )
        await url_scheme.launch(url)

    undo_log.delete(undo_entry["id"])

    return {
        "undone": True,
        "action_kind": KIND,
        "count": len(before["items"]),
        "ids": [it["target_uuid"] for it in before["items"]],
        "restored_dimension": before.get("dimension"),
    }
