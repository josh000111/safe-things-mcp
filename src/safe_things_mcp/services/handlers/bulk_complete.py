"""``bulk_complete`` handler — complete multiple to-dos in one airlocked op.

Pattern (shared with every ``bulk_*`` handler in this directory):

* Snapshot per-item before-state into a single ``undo_log`` row (items
  list under ``before_state``). One log entry → one ``undo()`` call
  reverses the whole batch.
* Launch URLs sequentially, awaiting each.
* No per-item polling. Bulk ops trade single-target verification for
  throughput; the user can re-query if they care.

This kind is in :data:`config.NEVER_BYPASS_KINDS` — even with
``SAFE_THINGS_MCP_AUTO_CONFIRM=1`` an explicit ``confirm_action`` is required.

Requires ``THINGS_AUTH_TOKEN``.
"""
from __future__ import annotations

from ... import config
from .. import things_repo, url_scheme
from ...state import undo_log

KIND = "bulk_complete"


def make_preview(payload: dict) -> str:
    n = len(payload.get("todo_ids") or [])
    return f"Bulk complete {n} to-do{'s' if n != 1 else ''}"


async def execute(payload: dict) -> dict:
    todo_ids = list(payload.get("todo_ids") or [])
    if not todo_ids:
        raise ValueError("bulk_complete requires a non-empty todo_ids list.")

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "bulk_complete requires THINGS_AUTH_TOKEN. Generate one in "
            "Things → Settings → General → Enable Things URLs → Manage, "
            "then export THINGS_AUTH_TOKEN before retrying."
        )

    items: list[dict] = []
    for uid in todo_ids:
        row = things_repo.get_todo(uid)
        if row is None:
            raise ValueError(
                f"No to-do found with id={uid!r}. Bulk complete aborts before "
                "any mutation — fix the id list and retry."
            )
        if row.get("status") != "incomplete":
            raise ValueError(
                f"to-do {uid!r} is already status={row.get('status')!r}. "
                "Bulk complete aborts before any mutation. Drop it from the "
                "list and retry."
            )
        items.append({
            "target_uuid": uid,
            "title": row.get("title"),
            "before_status": row.get("status"),
        })

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=None,
        before_state={"items": items, "count": len(items)},
        after_state=None,
    )

    for item in items:
        url = url_scheme.build_update_url(
            id=item["target_uuid"],
            auth_token=auth_token,
            completed=True,
        )
        await url_scheme.launch(url)

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "count": len(items),
        "ids": [it["target_uuid"] for it in items],
    }


async def undo(undo_entry: dict) -> dict:
    before = undo_entry.get("before_state")
    if not isinstance(before, dict) or not before.get("items"):
        raise RuntimeError(
            f"undo_log entry {undo_entry.get('id')!r} has no items to "
            "restore; original bulk_complete may have failed before logging."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "Cannot undo bulk_complete without THINGS_AUTH_TOKEN. Set it "
            "and retry."
        )

    for item in before["items"]:
        url = url_scheme.build_update_url(
            id=item["target_uuid"],
            auth_token=auth_token,
            completed=False,
            canceled=False,
        )
        await url_scheme.launch(url)

    undo_log.delete(undo_entry["id"])

    return {
        "undone": True,
        "action_kind": KIND,
        "count": len(before["items"]),
        "ids": [it["target_uuid"] for it in before["items"]],
    }
