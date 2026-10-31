"""``delete_ai_tag`` handler — delete an AI tag from Things.

Uses AppleScript ``delete tag "<name>"`` which removes the tag from ALL
items that carry it: open, completed and canceled to-dos, projects and areas.
This is in NEVER_BYPASS_KINDS — explicit confirm always required.

Refused (propose AND execute, before any undo_log write or AppleScript) unless
the title names exactly one tag, that tag has no child tags and its parent is the
configured AI parent tag: Things tag titles are not unique, AppleScript
``delete tag "X"`` deletes only one of several same-titled tags, and undo can only
re-create a single leaf tag. See :func:`check_deletable`.

Undo: re-creates the tag (with original parent) and re-adds it to the CURRENT tag
set of every item that previously carried it (to-dos of any status, projects,
areas), so tag changes made since the delete are not reverted. Items that no
longer exist (e.g. emptied from Trash) are terminal: reported in ``skipped`` and
recorded as done so a retry never revisits them. Items that fail to update
(AppleScript errors etc.) are reported in ``failed``; the undo_log row is then
KEPT (progress recorded in ``restored``) so ``undo(undo_id)`` can be retried. If
only skipped items remain, the undo counts as complete and the row is deleted.
Undo refuses (row kept, nothing tagged) if a same-named tag now exists outside the
AI parent or more than once.

Requires ``SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1``.
"""
from __future__ import annotations

import asyncio
import time

from .. import applescript, things_repo
from ...state import undo_log
from ...config import WRITE_POLL_INTERVAL_SECONDS, WRITE_POLL_TIMEOUT_SECONDS

KIND = "delete_ai_tag"


def summarize_carriers(items: list[dict]) -> dict:
    """JSON-safe breakdown of what a tag delete touches (stored in the payload)."""
    return {
        "count": len(items),
        "todos": sum(1 for i in items if i.get("kind", "to-do") == "to-do"),
        "projects": sum(1 for i in items if i.get("kind") == "project"),
        "areas": sum(1 for i in items if i.get("kind") == "area"),
        "closed": sum(1 for i in items if i.get("status") in {"completed", "canceled"}),
        "trashed": sum(1 for i in items if i.get("trashed")),
    }


def check_deletable(name: str) -> None:
    """Raise ValueError unless ``name`` is a single, childless AI tag.

    Reads TMTag read-only. Any read failure propagates (never "assume fine").
    AI tags are identified as elsewhere (``list_ai_tags``): the tag's parent is
    the configured ``AI_TAG_PARENT`` tag.
    """
    from ...config import AI_TAG_PARENT

    rows = things_repo.tag_rows(name)
    if not rows:
        raise ValueError(f"Tag {name!r} not found in the Things database.")
    if len(rows) > 1:
        raise ValueError(
            f"{len(rows)} tags are named {name!r}; rename one in Things first "
            "(deleting by title is ambiguous and undo could not restore the right one)."
        )
    row = rows[0]
    if row["child_count"]:
        raise ValueError(
            f"Tag {name!r} has {row['child_count']} child tag(s); deleting it would "
            "likely delete them too and undo only re-creates one tag. Delete or "
            "move the child tags in Things first."
        )
    if row["parent_title"] != AI_TAG_PARENT:
        where = (f"its parent is {row['parent_title']!r}" if row["parent_title"]
                 else "it has no parent tag")
        raise ValueError(
            f"Tag {name!r} is not an AI tag ({where}, not {AI_TAG_PARENT!r}); "
            "delete_ai_tag only deletes tags filed under the AI parent tag. "
            "Delete other tags in Things."
        )


def make_preview(payload: dict) -> str:
    name = payload["name"]
    count = payload.get("carrying_count")
    summary = payload.get("carrying_summary")
    if count is None and "carrying_count" in payload:
        # Lookup failed at propose time: say so rather than implying zero.
        scope = "an UNKNOWN number of items (the Things database could not be read to count them)"
    elif count is None:
        scope = "an unknown number of items"
    elif isinstance(summary, dict):
        parts = [f"{summary.get('todos', 0)} to-do(s)", f"{summary.get('projects', 0)} project(s)"]
        if summary.get("areas"):
            parts.append(f"{summary['areas']} area(s)")
        extra = []
        if summary.get("closed"):
            extra.append(f"{summary['closed']} completed/canceled")
        if summary.get("trashed"):
            extra.append(f"{summary['trashed']} in Trash")
        tail = f"; {', '.join(extra)}" if extra else ""
        scope = f"{count} item(s) ({', '.join(parts)}{tail})"
    else:
        scope = f"{count} item(s)"
    return (
        f"Delete AI tag '{name}' — removes it from ALL items that carry it, including "
        f"completed/canceled to-dos, projects and areas: {scope}. "
        "Undo re-creates the tag and re-applies it to each of them."
    )


async def execute(payload: dict) -> dict:
    from ...config import ALLOW_APPLESCRIPT
    if not ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "delete_ai_tag requires SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1. "
            "Set the environment variable and restart the MCP server."
        )

    name = payload["name"]

    # Refuse duplicates / parents / non-AI tags BEFORE any AppleScript or undo_log write.
    check_deletable(name)

    # Verify tag exists
    if name not in things_repo.get_tag_names():
        raise ValueError(
            f"Tag '{name}' not found in Things. "
            "Use get_tags() to list existing tags."
        )

    # Read parent via AppleScript
    safe_name = applescript.escape(name)
    parent_script = (
        f'tell application "Things3"\n'
        f'    set t to tag "{safe_name}"\n'
        f'    try\n'
        f'        return name of parent tag of t\n'
        f'    on error\n'
        f'        return ""\n'
        f'    end try\n'
        f'end tell'
    )
    current_parent = (await applescript.run_script(parent_script)).strip()

    # Snapshot every item carrying this tag. A failed lookup aborts BEFORE any
    # mutation: deleting without the snapshot would make undo impossible.
    carrying_tasks = _find_tasks_with_tag(name)

    entry_id = undo_log.record(
        action_kind=KIND,
        target_uuid=name,
        before_state={
            "name": name,
            "parent": current_parent,
            "carrying_tasks": carrying_tasks,
        },
        after_state=None,
    )

    delete_script = f'tell application "Things3" to delete tag "{safe_name}"'
    await applescript.run_script(delete_script)

    # Poll until tag is gone from SQLite mirror
    deadline = time.monotonic() + WRITE_POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if name not in things_repo.get_tag_names():
            break
        await asyncio.sleep(WRITE_POLL_INTERVAL_SECONDS)

    undo_log.attach_target(
        entry_id,
        target_uuid=name,
        after_state={"deleted": True, "was_on_tasks": len(carrying_tasks)},
    )
    summary = summarize_carriers(carrying_tasks)

    return {
        "action_kind": KIND,
        "undo_id": entry_id,
        "name": name,
        "tasks_affected": len(carrying_tasks),
        "affected": summary,
        "note": (
            f"Tag '{name}' deleted and removed from {len(carrying_tasks)} item(s) "
            f"({summary['todos']} to-do(s), {summary['projects']} project(s), "
            f"{summary['areas']} area(s)). "
            "Use undo() to restore the tag and re-assign it."
        ),
    }


async def undo(undo_entry: dict) -> dict:
    from ...config import ALLOW_APPLESCRIPT, AI_TAG_PARENT
    if not ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "Cannot undo delete_ai_tag without SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1."
        )

    before_state = undo_entry.get("before_state") or {}
    name = before_state.get("name") or undo_entry.get("target_uuid")
    parent = before_state.get("parent") or AI_TAG_PARENT
    carrying_tasks = before_state.get("carrying_tasks") or []

    if not name:
        raise RuntimeError(f"undo_log entry {undo_entry.get('id')!r} has no tag name.")

    safe_name = applescript.escape(name)
    safe_parent = applescript.escape(parent)

    # A same-named tag that isn't exactly one tag under the original parent would get
    # the wrong tag applied to every item. Check before ANY write (row is kept).
    existing = things_repo.tag_rows(name)
    if len(existing) > 1:
        raise RuntimeError(
            f"{len(existing)} tags named {name!r} now exist; rename or remove the "
            "extras in Things, then retry undo"
        )
    if existing and existing[0]["parent_title"] != parent:
        raise RuntimeError(
            f"A tag named {name!r} now exists outside the AI tag group; "
            "rename or remove it in Things, then retry undo"
        )

    # Re-create the parent if it doesn't exist
    if parent and parent not in things_repo.get_tag_names():
        parent_create_script = (
            f'tell application "Things3" to make new tag with properties {{name:"{safe_parent}"}}'
        )
        await applescript.run_script(parent_create_script)

    # Re-create the tag, unless a retry finds it already back (never make a duplicate)
    if name not in things_repo.get_tag_names():
        if parent:
            create_script = (
                f'tell application "Things3"\n'
                f'    make new tag with properties {{name:"{safe_name}", parent tag:tag "{safe_parent}"}}\n'
                f'    return ""\n'
                f'end tell'
            )
        else:
            create_script = (
                f'tell application "Things3"\n'
                f'    make new tag with properties {{name:"{safe_name}"}}\n'
                f'    return ""\n'
                f'end tell'
            )
        await applescript.run_script(create_script)

    # Poll until tag reappears
    deadline = time.monotonic() + WRITE_POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if name in things_repo.get_tag_names():
            break
        await asyncio.sleep(WRITE_POLL_INTERVAL_SECONDS)

    # Re-add the tag to every previously-carrying item (to-dos of any status,
    # projects, areas). Each item's CURRENT tags are read now and the tag is merged
    # in, so tags changed since the delete are preserved (the delete-time snapshot
    # is not written back). Failures are reported, never silently dropped.
    already_restored = set(before_state.get("restored") or [])  # progress from an earlier attempt
    restored_count = 0
    failed: list[dict] = []
    skipped: list[dict] = []  # gone for good: terminal, never retried
    restored_now: list[str] = []
    skipped_now: list[str] = []
    for task_info in carrying_tasks:
        item_uuid = task_info.get("uuid") or task_info.get("todo_uuid")
        if not item_uuid or item_uuid in already_restored:
            continue
        kind = task_info.get("kind", "to-do")
        try:
            current = things_repo.current_item_tags(item_uuid, kind)
            if current is None:
                skipped.append({
                    "uuid": item_uuid, "title": task_info.get("title", ""),
                    "reason": "item no longer exists in Things",
                })
                skipped_now.append(item_uuid)
                continue
            merged = sorted(set(current) | {name})
            tag_string = ",".join(applescript.escape(t) for t in merged)
            await applescript.run_script(_assign_script(kind, item_uuid, tag_string))
            restored_count += 1
            restored_now.append(item_uuid)
        except Exception as exc:
            failed.append({"uuid": item_uuid, "title": task_info.get("title", ""), "error": str(exc)})

    if failed:
        # Keep the undo row so the user can retry; record what already succeeded (and
        # which items are gone for good) so a retry only re-attempts the failures.
        undo_log.update_before_state(
            undo_entry["id"],
            {**before_state,
             "restored": sorted(already_restored | set(restored_now) | set(skipped_now))},
        )
    else:
        undo_log.delete(undo_entry["id"])

    result = {
        "undone": not failed,
        "action_kind": KIND,
        "name": name,
        "restored_to_tasks": restored_count,
        "failed": failed,
        "skipped": skipped,
    }
    if failed:
        result["undo_id"] = undo_entry["id"]
        result["note"] = (
            f"{len(failed)} item(s) could not be re-tagged; see 'failed'. The tag was "
            f"re-created and the undo entry was KEPT: call undo('{undo_entry['id']}') "
            "again to retry just those items."
        )
    elif skipped:
        result["note"] = (
            f"Undo complete. {len(skipped)} item(s) no longer exist in Things and were "
            "skipped; see 'skipped'."
        )
    return result


# ---------- internals ----------


def _assign_script(kind: str, item_uuid: str, tag_string: str) -> str:
    """AppleScript that sets the tag set of one item of any kind.

    Projects try ``project id`` first and fall back to ``to do id`` (completed /
    canceled / Logbook projects are not always reachable via ``project id``;
    same cascade as delete_project). Completed to-dos resolve via ``to do id``.
    """
    safe_uuid = applescript.escape(item_uuid)
    if kind == "area":
        target = f'area id "{safe_uuid}"'
        return (
            f'tell application "Things3"\n'
            f'    set tag names of {target} to "{tag_string}"\n'
            f'    return ""\n'
            f'end tell'
        )
    if kind == "project":
        return (
            f'tell application "Things3"\n'
            f'    try\n'
            f'        set tag names of project id "{safe_uuid}" to "{tag_string}"\n'
            f'    on error\n'
            f'        set tag names of to do id "{safe_uuid}" to "{tag_string}"\n'
            f'    end try\n'
            f'    return ""\n'
            f'end tell'
        )
    return (
        f'tell application "Things3"\n'
        f'    set tag names of to do id "{safe_uuid}" to "{tag_string}"\n'
        f'    return ""\n'
        f'end tell'
    )


def _find_tasks_with_tag(tag_name: str) -> list[dict]:
    """Every to-do (any status, incl. completed/canceled/trashed), project and
    area carrying this tag, with its full tag set (needed for undo).

    Raises if the lookup fails. It must never return [] for "could not read".
    """
    return things_repo.items_with_tag(tag_name)
