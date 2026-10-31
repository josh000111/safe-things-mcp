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
from .. import preview_names as pn
from ...state import undo_log
from .dummy_heading import is_dummy_heading
from .delete_heading import _resolve_heading_uuid
from .update_heading import resolve_pinned_heading_uuid

KIND = "bulk_delete_heading"


def make_preview(payload: dict) -> str:
    project = pn.fmt(payload.get("project_id", ""), payload, "project_title")
    # Two refs (e.g. a name and its uuid) can resolve to one heading; execute acts
    # once per heading, so count and list distinct headings only.
    distinct: dict[str, dict] = {}
    for it in payload.get("heading_items") or []:
        distinct.setdefault(it.get("uuid") or f"ref:{it.get('ref')}", it)
    if distinct:
        n = len(distinct)
    else:  # legacy payload staged without resolved items
        n = len(set(payload.get("heading_ids_or_names") or []))
    header = (
        f"Soft-delete {n} dummy heading{'s' if n != 1 else ''} from project "
        f"{project} (mark canceled+completed → Logbook; restorable via undo)"
    )
    labels = []
    for it in distinct.values():
        if it.get("title"):
            labels.append(f"'{it['title']}' ({it.get('uuid') or it.get('ref')})")
        else:
            labels.append(f"{it.get('ref')} (not found)")
    return header + pn.item_lines(labels)


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
    # UUIDs pinned at propose time (aligned 1:1 with the refs) win over name
    # resolution so confirm acts on exactly what the preview showed.
    pinned_items = payload.get("heading_items") or []
    items: list[dict] = []
    seen: set[str] = set()
    for i, ref in enumerate(heading_ids_or_names):
        pin = pinned_items[i] if i < len(pinned_items) else None
        if pin and pin.get("ref") == ref and pin.get("uuid"):
            uuid = resolve_pinned_heading_uuid(project_id, pin["uuid"], "deleted")
        else:
            uuid = _resolve_heading_uuid(project_id, ref)
        if uuid in seen:
            continue  # two refs to the same heading: act once
        seen.add(uuid)
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
