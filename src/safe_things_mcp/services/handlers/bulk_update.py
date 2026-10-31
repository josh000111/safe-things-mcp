"""``bulk_update`` handler — apply one set of field changes to N to-dos.

Bulk version of :mod:`update_todo`. The proposed changes are the same
across all targets, but **inverse_fields are computed per-item** (each
to-do has its own original values to restore on undo).

Reuses the per-field normalisation from :mod:`update_todo` so the
restore semantics are identical to the single-target tool.

Requires ``THINGS_AUTH_TOKEN``. Always in :data:`config.NEVER_BYPASS_KINDS`.
"""
from __future__ import annotations

from ... import config
from .. import things_repo, url_scheme
from .. import preview_names as pn
from .. import ref_checks
from ...state import undo_log
from .update_todo import _UPDATABLE_FIELDS, _normalize_for_undo

KIND = "bulk_update"


def make_preview(payload: dict) -> str:
    ids = payload.get("todo_ids") or []
    n = len(ids)
    changes: list[str] = []
    for f in _UPDATABLE_FIELDS:
        v = payload.get(f)
        if v is None:
            continue
        if isinstance(v, list):
            v_str = "(cleared)" if not v else f"[{','.join(v)}]"
        elif isinstance(v, str):
            v_str = "(cleared)" if v == "" else repr(v)
        else:
            v_str = repr(v)
        changes.append(f"{f}={v_str}")
    body = ", ".join(changes) if changes else "(no fields)"
    return f"Bulk update {n} to-do{'s' if n != 1 else ''}: {body}" + pn.todo_lines(ids, payload)


async def execute(payload: dict) -> dict:
    todo_ids = list(payload.get("todo_ids") or [])
    if not todo_ids:
        raise ValueError("bulk_update requires a non-empty todo_ids list.")
    group_id = payload.get("group_id")

    fields = {k: payload[k] for k in _UPDATABLE_FIELDS if payload.get(k) is not None}
    if not fields:
        raise ValueError(
            "bulk_update has no fields to update. Pass at least one of: "
            f"{', '.join(_UPDATABLE_FIELDS)}."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "bulk_update requires THINGS_AUTH_TOKEN. Generate one in "
            "Things → Settings → General → Enable Things URLs → Manage, "
            "then export THINGS_AUTH_TOKEN before retrying."
        )

    items: list[dict] = []
    # Refuse the whole batch (naming every project/heading/area id) before any
    # mutation or undo_log write.
    rows = ref_checks.check_todos(todo_ids, things_repo.get_todo)
    for uid in todo_ids:
        row = rows.get(uid)
        if row is None:
            raise ValueError(
                f"No to-do found with id={uid!r}. Bulk update aborts before "
                "any mutation."
            )
        inverse_fields = {f: _normalize_for_undo(f, row) for f in fields}
        items.append({
            "target_uuid": uid,
            "title": row.get("title"),
            "inverse_fields": inverse_fields,
        })

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=None,
        before_state={
            "items": items,
            "count": len(items),
            "changed": list(fields.keys()),
            "applied_fields": fields,
        },
        after_state=None,
        group_id=group_id,
    )

    for item in items:
        url = url_scheme.build_update_url(
            id=item["target_uuid"],
            auth_token=auth_token,
            title=fields.get("title"),
            notes=fields.get("notes"),
            deadline=fields.get("deadline"),
            tags=fields.get("tags"),
        )
        await url_scheme.launch(url)

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "count": len(items),
        "ids": [it["target_uuid"] for it in items],
        "changed_fields": list(fields.keys()),
    }


async def undo(undo_entry: dict) -> dict:
    before = undo_entry.get("before_state")
    if not isinstance(before, dict) or not before.get("items"):
        raise RuntimeError(
            f"undo_log entry {undo_entry.get('id')!r} has no items to "
            "restore; original bulk_update may have failed before logging."
        )

    auth_token = config.THINGS_AUTH_TOKEN
    if not auth_token:
        raise RuntimeError(
            "Cannot undo bulk_update without THINGS_AUTH_TOKEN. Set it and "
            "retry."
        )

    for item in before["items"]:
        inv = item.get("inverse_fields") or {}
        if not inv:
            continue
        url = url_scheme.build_update_url(
            id=item["target_uuid"],
            auth_token=auth_token,
            title=inv.get("title"),
            notes=inv.get("notes"),
            deadline=inv.get("deadline"),
            tags=inv.get("tags"),
        )
        await url_scheme.launch(url)

    undo_log.delete(undo_entry["id"])

    return {
        "undone": True,
        "action_kind": KIND,
        "count": len(before["items"]),
        "ids": [it["target_uuid"] for it in before["items"]],
        "restored_fields": before.get("changed"),
    }
