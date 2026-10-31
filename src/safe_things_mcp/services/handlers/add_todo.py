"""``add_todo`` handler — add a to-do to any list.

The V2 surface for adding tasks. V1's ``add_inbox_todo`` remains as a
one-step shortcut that hard-codes the Inbox; this handler routes via
``propose_add_todo`` + ``confirm_action`` and is the only path that may
target Today/Anytime/Someday/a project.

Undo strategy: ``things:///update?completed=true&canceled=true``. This
is a *soft-undo* — the task is marked complete-and-canceled and is no
longer visible in active lists. To permanently delete a task (move to
Trash), use ``propose_delete_todo``, which requires AppleScript.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from ... import config
from .. import things_repo, url_scheme
from .. import preview_names as pn
from ...state import undo_log

KIND = "add_todo"

_CREATED_FMT = "%Y-%m-%d %H:%M:%S"
_CLOCK_SLACK = timedelta(seconds=2)


def make_preview(payload: dict) -> str:
    """One-line summary for the agent to surface to the user."""
    title = payload["title"]
    list_id = payload.get("list_id") or "inbox"
    dest = pn.fmt_destination(list_id, payload, quote_keyword=False)
    bits = [f"Add to-do {title!r} to {dest}"]
    if payload.get("when"):
        bits.append(f"when={payload['when']}")
    if payload.get("deadline"):
        bits.append(f"deadline={payload['deadline']}")
    if payload.get("tags"):
        bits.append(f"tags={','.join(payload['tags'])}")
    if payload.get("checklist"):
        bits.append(f"checklist=[{len(payload['checklist'])} items]")
    return ", ".join(bits)


async def execute(payload: dict) -> dict:
    """Add the to-do. Pattern:

    1. Write the undo_log row *before* the URL scheme call (per the
       CLAUDE.md V2 acceptance gate hard rule).
    2. Capture the pre-launch clock value (with 2s slack for sub-second
       skew between this process and SQLite's seconds-resolution
       ``created`` column).
    3. Build + launch the ``things:///add`` URL.
    4. Poll the read-only Things DB for the new task by title and
       created-timestamp, across all incomplete lists (the URL scheme
       has already routed it to the right one).
    5. Patch the undo_log row with the resolved UUID and an
       after-state snapshot.
    """
    title = payload["title"]
    list_id = payload.get("list_id") or "inbox"

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=None,
        before_state=None,
        after_state=None,
    )

    created_after = (datetime.now() - _CLOCK_SLACK).strftime(_CREATED_FMT)

    url = url_scheme.build_add_url_v2(
        title=title,
        list_id=list_id,
        notes=payload.get("notes"),
        when=payload.get("when"),
        deadline=payload.get("deadline"),
        tags=payload.get("tags"),
        checklist_items=payload.get("checklist"),
    )
    await url_scheme.launch(url)

    verified = await _poll_for_new_todo(title, created_after)
    undo_log.attach_target(
        entry_id, target_uuid=verified["uuid"], after_state=verified
    )

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "id": verified["uuid"],
        "title": verified.get("title", title),
        "list_id": list_id,
        "created_at": verified.get("created", created_after),
    }


async def undo(undo_entry: dict) -> dict:
    """Soft-undo: mark the task completed-and-canceled via ``update``.

    Requires ``THINGS_AUTH_TOKEN``. Hard-delete (AppleScript ``delete
    theTask``) lands with ``propose_delete_todo`` in a later step.
    """
    target_uuid = undo_entry.get("target_uuid")
    if not target_uuid:
        raise RuntimeError(
            f"undo_log entry {undo_entry['id']} has no target_uuid; the "
            "original add may not have completed cleanly. Inspect manually."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "Cannot undo an add_todo without THINGS_AUTH_TOKEN. Generate one "
            "in Things → Settings → General → Enable Things URLs → Manage, "
            "then export THINGS_AUTH_TOKEN before retrying."
        )

    url = url_scheme.build_update_url(
        id=target_uuid,
        auth_token=auth_token,
        completed=True,
        canceled=True,
    )
    await url_scheme.launch(url)

    verified = await _poll_for_status(target_uuid, {"completed", "canceled"})
    undo_log.delete(undo_entry["id"])

    return {
        "undone": True,
        "action_kind": KIND,
        "target_uuid": target_uuid,
        "status": verified.get("status"),
        "note": (
            "Soft-undo: the task is marked completed/canceled and moved out "
            "of active lists. Hard-delete arrives with propose_delete_todo."
        ),
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
                f"waiting for Things to create a to-do titled {title!r}. "
                "Is the Things app running and is the URL scheme enabled?"
            )
        await asyncio.sleep(config.WRITE_POLL_INTERVAL_SECONDS)


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
