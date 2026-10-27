"""``reorder_todos`` handler — reorder to-dos in a list or project.

Uses the private AppleScript command ``_private_experimental_ reorder to dos``.
Requires SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1.

For projects with native headings, dummy heading tasks are created at the
original heading positions before reorder. Undo cannot reinstate native
heading positions.
"""
from __future__ import annotations

import asyncio
import time

from ... import config
from .. import applescript, things_repo, url_scheme
from ...state import undo_log
from .dummy_heading import AI_NEWLY_ADDED_HEADING

KIND = "reorder_todos"

_CREATED_FMT = "%Y-%m-%d %H:%M:%S"


def make_preview(payload: dict) -> str:
    container_id = payload["container_id"]
    master_order = payload["master_order"]
    dummy_creation_plan = payload.get("dummy_creation_plan", [])

    count = len(master_order)
    lines = [f"Reorder {count} to-do(s) in '{container_id}'."]

    if dummy_creation_plan:
        names = ", ".join(repr(e["name"]) for e in dummy_creation_plan)
        lines.append(
            f"Note: {len(dummy_creation_plan)} native heading(s) ({names}) will be "
            "auto-converted to dummy heading tasks at their original positions before "
            "reorder. The original empty native headings will appear at the project "
            "bottom after reorder and must be deleted manually."
        )
        lines.append(
            "Warning: undo cannot reinstate native heading positions."
        )

    return " ".join(lines)


async def execute(payload: dict) -> dict:
    if not config.ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "reorder_todos requires SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1. "
            "Set the environment variable and restart the MCP server."
        )

    container_type = payload["container_type"]
    container_id = payload["container_id"]
    master_order = list(payload["master_order"])
    dummy_creation_plan = payload.get("dummy_creation_plan", [])
    original_order = payload["original_order"]
    created_dummy_uuids: list[str] = list(payload.get("created_dummy_uuids", []))
    allow_existing_reorder: bool = bool(payload.get("allow_existing_reorder", False))

    # Validate container_id early to prevent AppleScript injection
    if '"' in container_id or '\\' in container_id:
        raise ValueError(
            f"container_id {container_id!r} contains characters that cannot be "
            "safely interpolated into AppleScript. Things UUIDs and list names "
            "do not contain quotes or backslashes."
        )

    # Pre-flight read (call 1) — establishes baseline for race-window detection
    current_uuids_preflight = things_repo.get_container_todo_uuids(container_type, container_id)

    # Anti-priority-sort guard: if a __NEWLY ADDED BY AI__ marker is present,
    # block reordering of tasks at or above it unless allow_existing_reorder=True.
    # "Reordering" means the UUID ended up at a different position than it held in
    # original_order — tasks that stay in place don't trigger the guard.
    if not allow_existing_reorder and container_type == "project":
        marker_idx: int | None = None
        for i, u in enumerate(current_uuids_preflight):
            row = things_repo.get_todo(u)
            if row is not None and row.get("title") == AI_NEWLY_ADDED_HEADING:
                marker_idx = i
                break
        if marker_idx is not None:
            protected = set(current_uuids_preflight[: marker_idx + 1])
            # Find UUIDs that changed position relative to original_order.
            original_positions = {u: i for i, u in enumerate(original_order)}
            actually_moved = {
                u for i, u in enumerate(master_order)
                if original_positions.get(u, -1) != i
            }
            blocked = actually_moved & protected
            if blocked:
                raise ValueError(
                    f"Reordering tasks at or above the {AI_NEWLY_ADDED_HEADING!r} marker "
                    "is blocked so your existing tasks stay pinned at the top. "
                    "Pass allow_existing_reorder=true to override."
                )

    # Create dummy heading tasks for each native heading that needs conversion
    if dummy_creation_plan:
        created_after = time.strftime(_CREATED_FMT, time.localtime(time.time() - 2))
        for entry in dummy_creation_plan:
            # Use raw name with __ wrappers (not make_dummy_title) so the title
            # is discoverable by the caller without knowing the uppercase transform.
            dummy_title = f"__{entry['name']}__"
            url = url_scheme.build_add_url_v2(title=dummy_title, list_id=container_id)
            await url_scheme.launch(url)
            new_item = await _poll_for_dummy(dummy_title, created_after)
            created_dummy_uuids.append(new_item["uuid"])

    # Splice dummy UUIDs into master_order at their todo_position indices.
    # Iterate in reverse so earlier inserts don't shift later positions.
    for entry, dummy_uuid in reversed(list(zip(dummy_creation_plan, created_dummy_uuids))):
        master_order.insert(entry["todo_position"], dummy_uuid)

    # Race-window check (call 2): abort if unexpected UUIDs appeared since propose
    current_after = things_repo.get_container_todo_uuids(container_type, container_id)
    unexpected = set(current_after) - set(original_order) - set(created_dummy_uuids)
    if unexpected:
        raise RuntimeError(
            f"stale: {len(unexpected)} unexpected UUID(s) appeared in "
            f"'{container_id}' since propose — re-propose required. "
            f"Unexpected: {sorted(unexpected)}"
        )

    # Write undo_log BEFORE AppleScript (V2 acceptance gate)
    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=None,
        before_state={
            "container_type": container_type,
            "container_id": container_id,
            "original_order": original_order,
            "created_dummy_uuids": created_dummy_uuids,
        },
        after_state=None,
    )

    # Build and run AppleScript reorder command
    escaped_id = applescript.escape(container_id)
    uuids_str = ",".join(applescript.escape(u) for u in master_order)
    if container_type == "list":
        script = (
            f'tell application "Things3" to '
            f'_private_experimental_ reorder to dos in list "{escaped_id}" '
            f'with ids "{uuids_str}"'
        )
    else:
        script = (
            f'tell application "Things3" to '
            f'_private_experimental_ reorder to dos in project id "{escaped_id}" '
            f'with ids "{uuids_str}"'
        )

    await applescript.run_script(script)

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "container_type": container_type,
        "container_id": container_id,
        "new_order": master_order,
    }


async def undo(undo_entry: dict) -> dict:
    if not config.ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "undo reorder_todos requires SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1."
        )

    before = undo_entry["before_state"]
    container_type = before["container_type"]
    container_id = before["container_id"]
    original_order = before["original_order"]
    created_dummy_uuids = before.get("created_dummy_uuids", [])

    # Soft-delete any dummies that were created during execute
    auth_token = config.THINGS_AUTH_TOKEN
    for dummy_uuid in created_dummy_uuids:
        if auth_token:
            url = url_scheme.build_update_url(
                id=dummy_uuid,
                auth_token=auth_token,
                completed=True,
                canceled=True,
            )
            await url_scheme.launch(url)

    # Restore original order via AppleScript (dummies excluded — they're being deleted)
    escaped_id = applescript.escape(container_id)
    uuids_str = ",".join(applescript.escape(u) for u in original_order)
    if container_type == "list":
        script = (
            f'tell application "Things3" to '
            f'_private_experimental_ reorder to dos in list "{escaped_id}" '
            f'with ids "{uuids_str}"'
        )
    else:
        script = (
            f'tell application "Things3" to '
            f'_private_experimental_ reorder to dos in project id "{escaped_id}" '
            f'with ids "{uuids_str}"'
        )

    await applescript.run_script(script)

    undo_log.delete(undo_entry["id"])

    return {"undone": True, "action_kind": KIND}


async def _poll_for_dummy(dummy_title: str, created_after: str) -> dict:
    deadline = asyncio.get_running_loop().time() + config.WRITE_POLL_TIMEOUT_SECONDS
    while True:
        match = things_repo.find_recent_by_title(dummy_title, created_after)
        if match is not None:
            return match
        if asyncio.get_running_loop().time() >= deadline:
            raise RuntimeError(
                f"Timed out after {config.WRITE_POLL_TIMEOUT_SECONDS}s "
                f"waiting for Things to create dummy heading {dummy_title!r}. "
                "Is Things running with URL scheme enabled?"
            )
        await asyncio.sleep(config.WRITE_POLL_INTERVAL_SECONDS)
