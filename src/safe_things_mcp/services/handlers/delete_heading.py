"""``delete_heading`` handler — cancel a dummy heading.

Only dummy headings (``__NAME__`` format) can be deleted here. Native
headings require AppleScript (step 5).

Cancel: mark canceled AND completed via the Things URL scheme (same
approach as ``delete_todo``). The task is preserved in the Logbook, so
undo can fully restore it.

This kind is in ``NEVER_BYPASS_KINDS`` (same as ``delete_todo``) —
explicit confirm is always required.

Requires ``THINGS_AUTH_TOKEN``.
"""
from __future__ import annotations

import asyncio

from ... import config
from .. import things_repo, url_scheme
from .. import preview_names as pn
from ...state import undo_log
from .dummy_heading import is_dummy_heading, extract_name_from_dummy
from .update_heading import (
    _find_dummy_heading_in_project,
    resolve_pinned_or_ref,
    verify_heading_row,
)

KIND = "delete_heading"


def make_preview(payload: dict) -> str:
    heading_ref = payload.get("heading_id_or_name", "")
    project = pn.fmt(payload.get("project_id", ""), payload, "project_title")
    return (
        f"Soft-delete dummy heading {pn.fmt_heading(heading_ref, payload)} from project "
        f"{project} (mark canceled+completed → moves to Logbook; restorable via undo)"
    )


async def execute(payload: dict) -> dict:
    """Soft-delete a dummy heading.

    1. Resolve heading UUID.
    2. Validate it is a dummy heading.
    3. Check it isn't already deleted.
    4. Write undo_log row BEFORE URL launch (CLAUDE.md hard rule).
    5. Launch things:///update?canceled=true&completed=true.
    6. Poll for status.
    7. Patch undo_log.
    """
    project_id = payload["project_id"]
    heading_id_or_name = payload["heading_id_or_name"]
    group_id = payload.get("group_id")

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "delete_heading requires THINGS_AUTH_TOKEN. Generate one in "
            "Things → Settings → General → Enable Things URLs → Manage, "
            "then export THINGS_AUTH_TOKEN before retrying."
        )

    # A UUID pinned at propose time wins over the name (confirm acts on exactly
    # what the preview showed); legacy payloads fall back to name resolution.
    heading_uuid = resolve_pinned_or_ref(
        payload, project_id, heading_id_or_name, "deleted", _resolve_heading_uuid
    )

    before = things_repo.get_todo(heading_uuid)
    if before is None:
        raise ValueError(
            f"Heading task {heading_uuid!r} not found. It may have been deleted."
        )
    if not is_dummy_heading(before.get("title", "")):
        raise ValueError(
            f"Task {heading_uuid!r} (title={before.get('title')!r}) is not a "
            "dummy heading. Only dummy headings (__NAME__ format) can be deleted "
            "with delete_heading. Native headings require AppleScript (step 5)."
        )
    if before.get("status") in {"canceled", "completed"}:
        raise ValueError(
            f"Heading task {heading_uuid!r} is already "
            f"status={before.get('status')!r}. Nothing to delete."
        )

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=heading_uuid,
        before_state={"full": before, "status": before.get("status"), "title": before.get("title")},
        after_state=None,
        group_id=group_id,
    )

    url = url_scheme.build_update_url(
        id=heading_uuid,
        auth_token=auth_token,
        canceled=True,
        completed=True,
    )
    await url_scheme.launch(url)

    verified = await _poll_for_status(heading_uuid, {"canceled", "completed"})
    undo_log.attach_target(entry_id, target_uuid=heading_uuid, after_state=verified)

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "id": heading_uuid,
        "title": verified.get("title", before.get("title", "")),
        "status": verified.get("status"),
        "note": (
            "Soft-deleted: dummy heading moved to Logbook (canceled). "
            "Use undo() to restore."
        ),
    }


async def undo(undo_entry: dict) -> dict:
    """Restore a cancelled dummy heading."""
    target_uuid = undo_entry.get("target_uuid")
    if not target_uuid:
        raise RuntimeError(
            f"undo_log entry {undo_entry.get('id')!r} has no target_uuid; "
            "original delete may not have landed cleanly."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "Cannot undo delete_heading without THINGS_AUTH_TOKEN. Set it "
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


# ---------- internals ----------


def _resolve_heading_uuid(project_id: str, heading_id_or_name: str) -> str:
    """Resolve heading UUID — same logic as update_heading (UUIDs must be dummy
    headings that belong to ``project_id``)."""
    # Try direct UUID lookup first.
    row = things_repo.get_todo(heading_id_or_name)
    if row is not None:
        verify_heading_row(project_id, heading_id_or_name, row, "deleted")
        return heading_id_or_name

    # Treat as a name — scan project items.
    candidates = _find_dummy_heading_in_project(project_id, heading_id_or_name)
    if not candidates:
        raise ValueError(
            f"No heading named {heading_id_or_name!r} found in project {project_id!r}. "
            "Check the project UUID and heading name, then retry."
        )

    dummy_candidates = [c for c in candidates if c["kind"] == "dummy"]
    native_candidates = [c for c in candidates if c["kind"] == "native"]

    if native_candidates and not dummy_candidates:
        names = ", ".join(c["uuid"] for c in native_candidates)
        raise ValueError(
            f"Heading {heading_id_or_name!r} exists as a native heading (UUID(s): {names}) "
            f"in project {project_id!r} but native headings cannot be deleted with "
            "delete_heading. Native heading deletion requires AppleScript (step 5)."
        )

    if len(dummy_candidates) == 1 and not native_candidates:
        return dummy_candidates[0]["uuid"]

    # Ambiguous.
    candidate_details = "; ".join(
        f"{c['uuid']!r} ({c['kind']}, title={c['title']!r})" for c in candidates
    )
    raise ValueError(
        f"Ambiguous heading name {heading_id_or_name!r} in project {project_id!r}. "
        f"Multiple matches: {candidate_details}. "
        "Retry with the specific dummy heading UUID."
    )


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
