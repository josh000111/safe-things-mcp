"""``bulk_add_todo`` handler — add N to-dos to one destination.

Each item is dispatched sequentially via the URL scheme and its UUID is
polled and captured individually. One ``undo_log`` row covers the whole
batch with per-item resolved UUIDs in ``after_state``.

Undo soft-cancels every added task (completed+canceled, moved out of
active lists). Requires ``THINGS_AUTH_TOKEN`` for undo; the add itself
is unauthenticated for Inbox or authenticated for other targets.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from ... import config
from .. import things_repo, url_scheme
from ...state import undo_log

KIND = "bulk_add_todo"

_CREATED_FMT = "%Y-%m-%d %H:%M:%S"
_CLOCK_SLACK = timedelta(seconds=2)

# Things URL-scheme inserts new tasks at the TOP of these list views.
# Adding [A, B, C] sequentially yields visible order [C, B, A].
# To produce the intended order the add loop must be reversed for these targets.
# Project and area targets insert at the BOTTOM, so no reversal is needed there.
_TOP_INSERTING_LISTS = {"inbox", "today"}


def make_preview(payload: dict) -> str:
    items = payload.get("items") or []
    list_id = payload.get("list_id") or "inbox"
    n = len(items)
    titles = ", ".join(repr(it.get("title", "?")) for it in items[:3])
    suffix = f" … (+{n - 3} more)" if n > 3 else ""
    return f"Bulk add {n} to-do{'s' if n != 1 else ''} to {list_id}: {titles}{suffix}"


async def execute(payload: dict) -> dict:
    list_id = payload.get("list_id") or "inbox"
    items = list(payload.get("items") or [])
    group_id = payload.get("group_id")
    preserve_order = payload.get("preserve_order", True)

    if not items:
        raise ValueError("bulk_add_todo requires a non-empty items list.")

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=None,
        before_state={"specs": items, "list_id": list_id, "count": len(items)},
        after_state=None,
        group_id=group_id,
    )

    # Determine add sequence. Top-inserting lists (inbox, today) place each new
    # task at the TOP, so adding [A, B, C] produces visible order [C, B, A].
    # Reversing the add sequence makes the last-added item (the caller's first)
    # land on top, giving the intended visible order [A, B, C].
    is_top_inserting = list_id.lower() in _TOP_INSERTING_LISTS
    add_sequence = list(reversed(items)) if (preserve_order and is_top_inserting) else items

    # resolved_map tracks uuid per spec index so we can report in the
    # caller's original order regardless of add direction.
    resolved_by_index: dict[int, dict] = {}
    for add_idx, spec in enumerate(add_sequence):
        # Map back to the original index to keep the returned list stable.
        original_idx = (len(items) - 1 - add_idx) if (preserve_order and is_top_inserting) else add_idx
        title = spec.get("title", "")
        created_after = (datetime.now() - _CLOCK_SLACK).strftime(_CREATED_FMT)
        url = url_scheme.build_add_url_v2(
            title=title,
            list_id=list_id,
            notes=spec.get("notes"),
            when=spec.get("when"),
            deadline=spec.get("deadline"),
            tags=spec.get("tags"),
            checklist_items=spec.get("checklist"),
        )
        await url_scheme.launch(url)
        verified = await _poll_for_new_todo(title, created_after)
        resolved_by_index[original_idx] = {"uuid": verified["uuid"], "title": title}

    # Report resolved todos in the caller's original intended order.
    resolved = [resolved_by_index[i] for i in range(len(items))]

    undo_log.update_after_state(entry_id, {"items": resolved, "count": len(resolved)})

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "count": len(resolved),
        "list_id": list_id,
        "ids": [it["uuid"] for it in resolved],
        "titles": [it["title"] for it in resolved],
    }


async def undo(undo_entry: dict) -> dict:
    """Soft-undo: mark every added to-do completed+canceled."""
    after = undo_entry.get("after_state")
    if not isinstance(after, dict) or not after.get("items"):
        raise RuntimeError(
            f"undo_log entry {undo_entry.get('id')!r} has no items to reverse; "
            "the original bulk_add may not have completed cleanly."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "Cannot undo bulk_add_todo without THINGS_AUTH_TOKEN. Generate one "
            "in Things → Settings → General → Enable Things URLs → Manage."
        )

    for item in after["items"]:
        url = url_scheme.build_update_url(
            id=item["uuid"],
            auth_token=auth_token,
            completed=True,
            canceled=True,
        )
        await url_scheme.launch(url)

    undo_log.delete(undo_entry["id"])

    return {
        "undone": True,
        "action_kind": KIND,
        "count": len(after["items"]),
        "ids": [it["uuid"] for it in after["items"]],
        "note": "Soft-undo: tasks marked completed/canceled and moved out of active lists.",
    }


async def _poll_for_new_todo(title: str, created_after: str) -> dict:
    deadline = asyncio.get_running_loop().time() + config.WRITE_POLL_TIMEOUT_SECONDS
    while True:
        match = things_repo.find_recent_by_title(title, created_after)
        if match is not None:
            return match
        if asyncio.get_running_loop().time() >= deadline:
            raise RuntimeError(
                f"Timed out after {config.WRITE_POLL_TIMEOUT_SECONDS}s "
                f"waiting for Things to create to-do titled {title!r}. "
                "Is the Things app running and is the URL scheme enabled?"
            )
        await asyncio.sleep(config.WRITE_POLL_INTERVAL_SECONDS)
