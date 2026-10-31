"""``prepend_checklist`` handler — prepend items to a to-do's checklist.

Uses ``things:///update?prepend-checklist-items=...`` (URL scheme).
Undo restores the prior checklist via ``replace_checklist_url``.
"""
from __future__ import annotations

import asyncio

from ... import config
from .. import things_repo, url_scheme
from .. import preview_names as pn
from .. import ref_checks
from ...state import undo_log

KIND = "prepend_checklist"


def make_preview(payload: dict) -> str:
    items = payload.get("items", [])
    todo = pn.fmt(payload["todo_id"], payload, "todo_title")
    return (
        f"Prepend {len(items)} checklist item(s) to to-do {todo}"
        + pn.item_lines([f"'{i}'" for i in items])
    )


async def execute(payload: dict) -> dict:
    todo_id = payload["todo_id"]
    items: list[str] = payload.get("items", [])

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "prepend_checklist requires THINGS_AUTH_TOKEN. Generate one in "
            "Things → Settings → General → Enable Things URLs → Manage, "
            "then export THINGS_AUTH_TOKEN before retrying."
        )

    todo = things_repo.get(todo_id)
    if todo is None:
        raise ValueError(
            f"No to-do found with id={todo_id!r}. It may have been deleted or "
            "the id may be wrong. Use list/search tools to find the right id."
        )
    # Refuse project/heading/area ids: acting on them would hit the whole container.
    ref_checks.require_todo(todo_id, todo)

    before_items = things_repo.get_checklist_items(todo_id)
    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=todo_id,
        before_state={"items": before_items},
        after_state=None,
    )

    url = url_scheme.build_prepend_checklist_url(
        todo_id=todo_id, items=items, auth_token=auth_token
    )
    await url_scheme.launch(url)

    after_items = await _poll_for_item_count(
        todo_id, expected_count=len(before_items) + len(items)
    )
    undo_log.attach_target(entry_id, target_uuid=todo_id, after_state={"items": after_items})

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "todo_id": todo_id,
        "prepended_count": len(items),
        "total_items": len(after_items),
    }


async def undo(undo_entry: dict) -> dict:
    target_uuid = undo_entry.get("target_uuid")
    if not target_uuid:
        raise RuntimeError(
            f"undo_log entry {undo_entry['id']} has no target_uuid."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "Cannot undo prepend_checklist without THINGS_AUTH_TOKEN."
        )

    before_items: list[dict] = undo_entry.get("before_state", {}).get("items", [])
    titles = [item.get("title", "") for item in before_items]

    url = url_scheme.build_replace_checklist_url(
        todo_id=target_uuid, items=titles, auth_token=auth_token
    )
    await url_scheme.launch(url)

    restored = await _poll_for_item_count(target_uuid, expected_count=len(titles))
    undo_log.delete(undo_entry["id"])

    return {
        "undone": True,
        "action_kind": KIND,
        "target_uuid": target_uuid,
        "item_count": len(restored),
    }


async def _poll_for_item_count(todo_id: str, expected_count: int) -> list[dict]:
    deadline = asyncio.get_running_loop().time() + config.WRITE_POLL_TIMEOUT_SECONDS
    while True:
        items = things_repo.get_checklist_items(todo_id)
        if len(items) == expected_count:
            return items
        if asyncio.get_running_loop().time() >= deadline:
            raise RuntimeError(
                f"Timed out waiting for {todo_id} checklist to reach "
                f"{expected_count} items; found {len(items)}."
            )
        await asyncio.sleep(config.WRITE_POLL_INTERVAL_SECONDS)
