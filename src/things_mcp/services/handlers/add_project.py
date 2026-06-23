"""``add_project`` handler — create a new Things project.

Mirrors :mod:`add_todo` but for projects, with two URL-scheme paths:

* No headings → ``things:///add-project`` (unauthenticated).
* Headings non-empty → ``things:///json?data=<JSON>``. Things' JSON
  endpoint is the only URL-scheme route that creates native section
  headings inside a *new* project (arch doc §5.3).

Undo strategy: cancel the created project via
``things:///update-project?id=...&canceled=true&completed=true``. The
project moves to the Logbook; ``undo`` does not purge it.
``update-project`` requires ``THINGS_AUTH_TOKEN``, so undo will raise an
actionable error if the token isn't set even though execute didn't need it.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from ... import config
from .. import things_repo, url_scheme
from ...state import sort_session, undo_log
from . import bulk_move

KIND = "add_project"

_CREATED_FMT = "%Y-%m-%d %H:%M:%S"
_CLOCK_SLACK = timedelta(seconds=2)


def make_preview(payload: dict) -> str:
    title = payload["title"]
    bits = [f"Add project {title!r}"]
    if payload.get("area"):
        bits.append(f"area={payload['area']!r}")
    if payload.get("area_id"):
        bits.append(f"area_id={payload['area_id']}")
    if payload.get("when"):
        bits.append(f"when={payload['when']}")
    if payload.get("deadline"):
        bits.append(f"deadline={payload['deadline']}")
    if payload.get("tags"):
        bits.append(f"tags={','.join(payload['tags'])}")
    if payload.get("headings"):
        bits.append(f"headings=[{len(payload['headings'])} sections]")
    if payload.get("member_todo_ids"):
        bits.append(f"+ populate {len(payload['member_todo_ids'])} tasks")
    return ", ".join(bits)


async def execute(payload: dict) -> dict:
    title = payload["title"]

    # Capture group_id before any mutation so both undo_log entries share it.
    # undo_group(group_id) will then reverse them LIFO: bulk_move first (tasks
    # back to Inbox), then add_project (project cancelled) — correct order.
    group_id = sort_session.active()

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=None,
        before_state=None,
        after_state=None,
        group_id=group_id,
    )

    created_after = (datetime.now() - _CLOCK_SLACK).strftime(_CREATED_FMT)

    # NOTE: area (name, auto-created by Things) is intentionally NOT removed
    # on undo — areas are cheap to keep and Things' AppleScript cannot
    # reliably delete areas without side-effects.
    url = url_scheme.build_add_project_url(
        title=title,
        area=payload.get("area"),
        area_id=payload.get("area_id"),
        when=payload.get("when"),
        deadline=payload.get("deadline"),
        notes=payload.get("notes"),
        tags=payload.get("tags"),
        headings=payload.get("headings"),
    )
    await url_scheme.launch(url)

    verified = await _poll_for_new_project(title, created_after)
    undo_log.attach_target(
        entry_id, target_uuid=verified["uuid"], after_state=verified
    )
    # An AI-created project is never "user-curated", so a later sort move into
    # it must NOT get the __NEWLY ADDED BY AI__ marker. Record it so
    # propose_bulk_move's auto-promote excludes it.
    sort_session.register_created_project(verified["uuid"])

    # Atomic populate: move member_todo_ids into the new project immediately.
    # This makes an empty cluster-project structurally impossible when the
    # agent supplies the task list (which it always does during a sort).
    member_todo_ids = payload.get("member_todo_ids") or []
    populate_result = None
    if member_todo_ids:
        populate_result = await bulk_move.execute({
            "todo_ids": member_todo_ids,
            "target": verified["uuid"],
            "group_id": group_id,
        })

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "id": verified["uuid"],
        "title": verified.get("title", title),
        "created_at": verified.get("created", created_after),
        "headings_count": len(payload.get("headings") or []),
        "populated_count": len(member_todo_ids),
        "populate_undo_id": populate_result["undo_id"] if populate_result else None,
    }


async def undo(undo_entry: dict) -> dict:
    """Soft-undo: mark the project canceled+completed via update-project.

    Hard-delete (AppleScript) arrives in step 5.
    """
    target_uuid = undo_entry.get("target_uuid")
    if not target_uuid:
        raise RuntimeError(
            f"undo_log entry {undo_entry['id']} has no target_uuid; the "
            "original add_project may not have completed cleanly. Inspect "
            "manually."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "Cannot undo an add_project without THINGS_AUTH_TOKEN. Generate "
            "one in Things → Settings → General → Enable Things URLs → "
            "Manage, then export THINGS_AUTH_TOKEN before retrying."
        )

    url = url_scheme.build_update_project_url(
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
            "Soft-undo: the project is marked completed/canceled and moved "
            "to the Logbook. Hard-delete arrives with the AppleScript layer."
        ),
    }


async def _poll_for_new_project(title: str, created_after: str) -> dict:
    deadline = asyncio.get_running_loop().time() + config.WRITE_POLL_TIMEOUT_SECONDS
    while True:
        match = things_repo.find_recent_project_by_title(title, created_after)
        if match is not None:
            return match
        if asyncio.get_running_loop().time() >= deadline:
            raise RuntimeError(
                f"Timed out after {config.WRITE_POLL_TIMEOUT_SECONDS}s "
                f"waiting for Things to create a project titled {title!r}. "
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
                f"Timed out waiting for project {target_uuid} to reach "
                f"status in {expected}; observed status={actual!r}."
            )
        await asyncio.sleep(config.WRITE_POLL_INTERVAL_SECONDS)
