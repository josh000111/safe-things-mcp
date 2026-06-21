"""``add_heading`` handler — add a dummy heading to an existing project.

The Things URL scheme cannot create headings in existing projects, so we
represent headings as regular to-dos with a ``__NAME__`` title format (see
:mod:`dummy_heading`).

The ``after_todo_id`` parameter is accepted in the payload but CANNOT be
honoured by the URL scheme — the task will be appended at an unspecified
position. This is noted in the preview and result.

Undo: cancel the dummy task (marks completed/canceled, moves to Logbook).
Requires ``THINGS_AUTH_TOKEN``.
"""
from __future__ import annotations

import asyncio
import time

from ... import config
from .. import things_repo, url_scheme
from ...state import undo_log
from .dummy_heading import make_dummy_title, is_dummy_heading

KIND = "add_heading"

_CREATED_FMT = "%Y-%m-%d %H:%M:%S"


def make_preview(payload: dict) -> str:
    """One-line summary for the proposal.

    Validates name and project existence eagerly so a bad proposal fails
    here rather than silently enqueuing and only erroring at confirm time.
    """
    name = payload.get("name", "")
    project_id = payload.get("project_id", "")
    dummy_title = make_dummy_title(name)  # raises ValueError for invalid names
    if things_repo.project(project_id) is None:
        raise ValueError(
            f"Project {project_id!r} not found. "
            "Use list/search tools to find the correct project UUID."
        )
    parts = [
        f"Add dummy heading {dummy_title!r} to project {project_id}",
        "(URL-scheme only — position not guaranteed)",
    ]
    if payload.get("after_todo_id"):
        parts.append(
            f"[after_todo_id={payload['after_todo_id']!r} hint acknowledged but not honoured]"
        )
    return " ".join(parts)


async def execute(payload: dict) -> dict:
    """Add a dummy-heading to-do.

    1. Validate project exists.
    2. Convert name to ``__NAME__`` format.
    3. Write undo_log row BEFORE URL launch (CLAUDE.md hard rule).
    4. Launch ``things:///add?list-id=<project_id>&title=<dummy_title>``.
    5. Poll for the new task.
    6. Patch undo_log with the task UUID.
    """
    project_id = payload["project_id"]
    name = payload["name"]
    after_todo_id = payload.get("after_todo_id")
    group_id = payload.get("group_id")

    proj = things_repo.project(project_id)
    if proj is None:
        raise ValueError(
            f"Project {project_id!r} not found. "
            "Use list/search tools to find the correct project UUID."
        )

    dummy_title = make_dummy_title(name)

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=None,
        before_state=None,
        after_state=None,
        group_id=group_id,
    )

    # Use time-based created_after with 2s slack for sub-second skew.
    created_after = time.strftime(_CREATED_FMT, time.localtime(time.time() - 2))

    url = url_scheme.build_add_url_v2(
        title=dummy_title,
        list_id=project_id,
    )
    await url_scheme.launch(url)

    verified = await _poll_for_new_heading(dummy_title, created_after)
    undo_log.attach_target(
        entry_id, target_uuid=verified["uuid"], after_state=verified
    )

    result = {
        "action_kind": KIND,
        "undo_id": entry_id,
        "id": verified["uuid"],
        "title": verified.get("title", dummy_title),
        "project_id": project_id,
        "note": (
            "Dummy heading created as a to-do with title "
            f"{dummy_title!r}. Position is not guaranteed by the URL scheme."
        ),
    }
    if after_todo_id:
        result["after_todo_id_note"] = (
            f"after_todo_id={after_todo_id!r} was acknowledged but could not "
            "be honoured by the URL-scheme layer."
        )
    return result


async def undo(undo_entry: dict) -> dict:
    """Soft-delete the dummy heading task (cancel+complete)."""
    target_uuid = undo_entry.get("target_uuid")
    if not target_uuid:
        raise RuntimeError(
            f"undo_log entry {undo_entry.get('id')!r} has no target_uuid; "
            "the original add may not have completed cleanly."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "Cannot undo add_heading without THINGS_AUTH_TOKEN. Generate one "
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
        "note": "Dummy heading cancelled (marked completed/canceled).",
    }


# ---------- internals ----------


async def _poll_for_new_heading(dummy_title: str, created_after: str) -> dict:
    deadline = asyncio.get_running_loop().time() + config.WRITE_POLL_TIMEOUT_SECONDS
    while True:
        match = things_repo.find_recent_by_title(dummy_title, created_after)
        if match is not None:
            return match
        if asyncio.get_running_loop().time() >= deadline:
            raise RuntimeError(
                f"Timed out after {config.WRITE_POLL_TIMEOUT_SECONDS}s "
                f"waiting for Things to create heading {dummy_title!r}. "
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
