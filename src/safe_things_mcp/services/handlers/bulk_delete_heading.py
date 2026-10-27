"""``bulk_delete_heading`` handler — soft-delete N dummy headings.

Bulk version of :mod:`delete_heading`. Marks each heading
canceled+completed via the Things URL scheme in a single airlocked op
with one ``undo_log`` row covering all N targets.

Undo restores each heading via ``things:///update?canceled=false``.

Requires ``THINGS_AUTH_TOKEN``. Always in :data:`config.NEVER_BYPASS_KINDS`.
"""
from __future__ import annotations

from ... import config
from .. import things_repo, url_scheme
from ...state import undo_log
from .dummy_heading import is_dummy_heading
from .delete_heading import _resolve_heading_uuid

KIND = "bulk_delete_heading"


def make_preview(payload: dict) -> str:
    project_id = payload.get("project_id", "")
    n = len(payload.get("heading_ids_or_names") or [])
    return (
        f"Soft-delete {n} dummy heading{'s' if n != 1 else ''} from project "
        f"{project_id} (mark canceled+completed → Logbook; restorable via undo)"
    )


async def execute(payload: dict) -> dict:
    project_id = payload["project_id"]
    heading_ids_or_names = list(payload.get("heading_ids_or_names") or [])
    group_id = payload.get("group_id")

    if not heading_ids_or_names:
        raise ValueError("bulk_delete_heading requires a non-empty heading_ids_or_names list.")

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "bulk_delete_heading requires THINGS_AUTH_TOKEN. Generate one in "
            "Things → Settings → General → Enable Things URLs → Manage."
        )

    # Resolve and validate all headings before any mutation.
    items: list[dict] = []
    for ref in heading_ids_or_names:
        uuid = _resolve_heading_uuid(project_id, ref)
        row = things_repo.get_todo(uuid)
        if row is None:
            raise ValueError(
                f"Heading task {uuid!r} not found. "
                "Bulk delete aborts before any mutation."
            )
        if not is_dummy_heading(row.get("title", "")):
            raise ValueError(
                f"Task {uuid!r} (title={row.get('title')!r}) is not a dummy heading. "
                "Only dummy headings can be deleted with bulk_delete_heading."
            )
        if row.get("status") in {"canceled", "completed"}:
            raise ValueError(
                f"Heading {uuid!r} is already status={row.get('status')!r}. "
                "Bulk delete aborts before any mutation — remove it from the list."
            )
        items.append({
            "target_uuid": uuid,
            "title": row.get("title"),
            "status": row.get("status"),
        })

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=None,
        before_state={"items": items, "count": len(items)},
        after_state=None,
        group_id=group_id,
    )

    for item in items:
        url = url_scheme.build_update_url(
            id=item["target_uuid"],
            auth_token=auth_token,
            canceled=True,
            completed=True,
        )
        await url_scheme.launch(url)

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "count": len(items),
        "ids": [it["target_uuid"] for it in items],
        "note": (
            "Soft-deleted: dummy headings moved to Logbook (canceled). "
            "Use undo() to restore all."
        ),
    }


async def undo(undo_entry: dict) -> dict:
    """Restore all soft-deleted dummy headings."""
    before = undo_entry.get("before_state")
    if not isinstance(before, dict) or not before.get("items"):
        raise RuntimeError(
            f"undo_log entry {undo_entry.get('id')!r} has no items to restore."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "Cannot undo bulk_delete_heading without THINGS_AUTH_TOKEN."
        )

    for item in before["items"]:
        url = url_scheme.build_update_url(
            id=item["target_uuid"],
            auth_token=auth_token,
            canceled=False,
            completed=False,
        )
        await url_scheme.launch(url)

    undo_log.delete(undo_entry["id"])

    return {
        "undone": True,
        "action_kind": KIND,
        "count": len(before["items"]),
        "ids": [it["target_uuid"] for it in before["items"]],
    }
