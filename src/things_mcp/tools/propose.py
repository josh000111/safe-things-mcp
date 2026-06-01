"""V2 ``propose_*`` tools.

A ``propose_*`` tool validates inputs and enqueues a pending action keyed
by ``kind``. It does NOT mutate Things directly — the agent surfaces the
preview to the user, and on approval the agent calls
``confirm_action(action_id)`` which dispatches to the right handler.

### Auto-confirm escape hatch

When the env flag ``THINGS_MCP_AUTO_CONFIRM`` is set (see ``config.py``),
``propose_*`` tools immediately execute their action in the same call
and return the result inline. The preview is still emitted (so the LLM
can summarise) but the user is spared a second round-trip.

**Never bypassable** — kinds listed in ``config.NEVER_BYPASS_KINDS``
(deletes and bulk variants) ALWAYS require an explicit
``confirm_action``, regardless of the flag. This is hard-coded for
safety; users cannot loosen it via env var.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .. import config
from ..models import (
    ProposeAddHeadingInput,
    ProposeAddProjectInput,
    ProposeAddTodoInput,
    ProposeApplyAiTagsInput,
    ProposeBulkCancelInput,
    ProposeBulkCompleteInput,
    ProposeBulkDeleteInput,
    ProposeBulkMoveInput,
    ProposeBulkUpdateInput,
    ProposeCancelProjectInput,
    ProposeCancelTodoInput,
    ProposeCleanupAiTagsInput,
    ProposeCreateAiTagInput,
    ProposeDeleteAiTagInput,
    ProposeDeleteHeadingInput,
    ProposeDeleteProjectInput,
    ProposeDeleteTodoInput,
    ProposeManageAiTagInput,
    ProposeMoveTodoInput,
    ProposeUpdateHeadingInput,
    ProposeUpdateProjectInput,
    ProposeUpdateTodoInput,
)
from ..services import handlers, url_scheme
from ..state import pending


# ---------- module-level tool functions (testable without FastMCP) ----------


async def propose_add_todo(
    title: str,
    list_id: str = "inbox",
    notes: str | None = None,
    when: str | None = None,
    deadline: str | None = None,
    tags: list[str] | None = None,
    checklist: list[str] | None = None,
) -> dict:
    """Propose adding a to-do to any list (Inbox, Today, Anytime,
    Someday, or a project UUID).

    Returns ``{action_id, preview, expires_at, auto_confirmed, ...}``.
    On approval the agent calls ``confirm_action(action_id)``; to drop
    call ``cancel_action(action_id)``. When ``THINGS_MCP_AUTO_CONFIRM=1``
    the action is executed immediately and ``auto_confirmed=True`` is
    set — the result lives in the ``result`` field.
    """
    url_scheme.validate_tags(tags)
    payload_model = ProposeAddTodoInput(
        title=title,
        list_id=list_id,
        notes=notes,
        when=when,
        deadline=deadline,
        tags=tags,
        checklist=checklist,
    )
    payload = payload_model.model_dump()
    preview = handlers.add_todo.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.add_todo.KIND, payload=payload, preview=preview
    )


async def propose_update_todo(
    todo_id: str,
    title: str | None = None,
    notes: str | None = None,
    deadline: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Propose editing fields on an existing to-do.

    Convention: ``None`` means "don't change" the field; pass ``""`` to
    clear a string field; pass ``[]`` to clear all tags. At least one
    updatable field must be set.

    Requires ``THINGS_AUTH_TOKEN`` (Things → Settings → General → Enable
    Things URLs → Manage).

    First cut supports: title, notes, deadline, tags. ``when`` rescheduling
    arrives in a follow-up.
    """
    url_scheme.validate_tags(tags)
    payload_model = ProposeUpdateTodoInput(
        todo_id=todo_id,
        title=title,
        notes=notes,
        deadline=deadline,
        tags=tags,
    )
    # exclude_none so the handler's "is this field being changed?" check
    # works correctly. Empty string / empty list survive (they mean
    # "clear"), but None ("don't touch") gets stripped.
    payload = payload_model.model_dump(exclude_none=True)
    preview = handlers.update_todo.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.update_todo.KIND, payload=payload, preview=preview
    )


async def propose_move_todo(todo_id: str, target: str) -> dict:
    """Propose moving a to-do to a different list or project.

    ``target`` is one of:
    * ``"today"`` / ``"anytime"`` / ``"someday"`` — change scheduling
      (preserves project/area membership).
    * A project/area UUID — change membership (preserves scheduling).

    Requires ``THINGS_AUTH_TOKEN``. Move-to-Inbox and specific-date moves
    are deferred to a follow-up.
    """
    target_lower = target.lower() if target else target
    if target_lower == "inbox":
        raise ValueError(
            "target='inbox' is not supported in V2 first cut. "
            "Use 'today', 'anytime', 'someday', or a project/area UUID."
        )
    if target_lower == "upcoming":
        raise ValueError(
            "target='upcoming' is a computed view in Things, not a move "
            "destination. To schedule a task for a future date that appears "
            "in Upcoming, update the to-do with `when='<YYYY-MM-DD>'` "
            "(specific-date moves arrive in a follow-up)."
        )
    payload_model = ProposeMoveTodoInput(todo_id=todo_id, target=target)
    payload = payload_model.model_dump()
    preview = handlers.move_todo.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.move_todo.KIND, payload=payload, preview=preview
    )


async def propose_delete_todo(todo_id: str) -> dict:
    """Propose deleting a to-do by moving it to Things Trash.

    Uses AppleScript to move the task to Things Trash — the same as
    deleting it manually in the Things UI. Undo uses AppleScript to
    restore it from Trash. Things auto-empties Trash after 30 days.

    Requires ``THINGS_MCP_ALLOW_APPLESCRIPT=1``.

    **Never auto-confirmed.** Even with ``THINGS_MCP_AUTO_CONFIRM=1`` the
    user must call ``confirm_action`` explicitly.
    """
    if not config.ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "propose_delete_todo requires THINGS_MCP_ALLOW_APPLESCRIPT=1. "
            "Set the environment variable and restart the MCP server."
        )
    payload_model = ProposeDeleteTodoInput(todo_id=todo_id)
    payload = payload_model.model_dump()
    preview = handlers.delete_todo.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.delete_todo.KIND, payload=payload, preview=preview
    )


async def propose_add_project(
    title: str,
    area_id: str | None = None,
    when: str | None = None,
    deadline: str | None = None,
    notes: str | None = None,
    tags: list[str] | None = None,
    headings: list[str] | None = None,
) -> dict:
    """Propose adding a new Things project.

    When ``headings`` is non-empty, the project is created through Things'
    ``things:///json`` endpoint — the only URL-scheme path that produces
    native section headings at project birth. Without headings the
    unauthenticated ``add-project`` URL is used.

    Undo cancels the created project (canceled+completed → Logbook).
    Undo requires ``THINGS_AUTH_TOKEN`` even though execute does not.
    """
    url_scheme.validate_tags(tags)
    payload_model = ProposeAddProjectInput(
        title=title,
        area_id=area_id,
        when=when,
        deadline=deadline,
        notes=notes,
        tags=tags,
        headings=headings,
    )
    payload = payload_model.model_dump()
    preview = handlers.add_project.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.add_project.KIND, payload=payload, preview=preview
    )


async def propose_update_project(
    project_id: str,
    title: str | None = None,
    notes: str | None = None,
    deadline: str | None = None,
    tags: list[str] | None = None,
    area_id: str | None = None,
) -> dict:
    """Propose editing fields on an existing project.

    Convention: ``None`` means "don't change"; ``""`` clears a string
    field; ``[]`` clears all tags. At least one updatable field required.

    Requires ``THINGS_AUTH_TOKEN``. First cut supports: title, notes,
    deadline, tags, area_id. ``when`` rescheduling is a follow-up.
    """
    url_scheme.validate_tags(tags)
    payload_model = ProposeUpdateProjectInput(
        project_id=project_id,
        title=title,
        notes=notes,
        deadline=deadline,
        tags=tags,
        area_id=area_id,
    )
    payload = payload_model.model_dump(exclude_none=True)
    preview = handlers.update_project.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.update_project.KIND, payload=payload, preview=preview
    )


# ---------- bulk tools (always in NEVER_BYPASS_KINDS) ----------


async def propose_bulk_complete(todo_ids: list[str]) -> dict:
    """Propose completing N to-dos in one airlocked op.

    **Never auto-confirmed** — explicit ``confirm_action`` required even
    when ``THINGS_MCP_AUTO_CONFIRM=1``. Requires ``THINGS_AUTH_TOKEN``.
    """
    payload_model = ProposeBulkCompleteInput(todo_ids=todo_ids)
    payload = payload_model.model_dump()
    preview = handlers.bulk_complete.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.bulk_complete.KIND, payload=payload, preview=preview
    )


async def propose_bulk_cancel(todo_ids: list[str]) -> dict:
    """Propose canceling N to-dos in one airlocked op.

    Each task gets marked canceled. Use ``undo()`` to restore the whole
    batch. **Never auto-confirmed.**
    """
    payload_model = ProposeBulkCancelInput(todo_ids=todo_ids)
    payload = payload_model.model_dump()
    preview = handlers.bulk_delete.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.bulk_delete.KIND, payload=payload, preview=preview
    )


async def propose_bulk_move(todo_ids: list[str], target: str) -> dict:
    """Propose moving N to-dos to a single target.

    ``target`` follows the same rules as :func:`propose_move_todo`:
    ``today`` / ``anytime`` / ``someday`` for scheduling, or a
    project/area UUID for membership. **Never auto-confirmed.**
    """
    target_lower = target.lower() if target else target
    if target_lower == "inbox":
        raise ValueError(
            "target='inbox' is not supported in V2 first cut. "
            "Use 'today', 'anytime', 'someday', or a project/area UUID."
        )
    if target_lower == "upcoming":
        raise ValueError(
            "target='upcoming' is a computed view in Things, not a move "
            "destination. To schedule tasks for a future date that appears "
            "in Upcoming, use propose_bulk_update with `when` (arrives in a "
            "follow-up)."
        )
    payload_model = ProposeBulkMoveInput(todo_ids=todo_ids, target=target)
    payload = payload_model.model_dump()
    preview = handlers.bulk_move.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.bulk_move.KIND, payload=payload, preview=preview
    )


async def propose_bulk_update(
    todo_ids: list[str],
    title: str | None = None,
    notes: str | None = None,
    deadline: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Propose applying one set of field changes to N to-dos.

    Convention matches :func:`propose_update_todo`: ``None`` means "don't
    change", ``""`` clears a string field, ``[]`` clears tags. At least
    one updatable field required. **Never auto-confirmed.**
    """
    url_scheme.validate_tags(tags)
    payload_model = ProposeBulkUpdateInput(
        todo_ids=todo_ids,
        title=title,
        notes=notes,
        deadline=deadline,
        tags=tags,
    )
    payload = payload_model.model_dump(exclude_none=True)
    preview = handlers.bulk_update.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.bulk_update.KIND, payload=payload, preview=preview
    )


async def propose_cancel_todo(todo_id: str) -> dict:
    """Propose canceling a to-do.

    Marks the to-do canceled via the URL scheme. Undo restores it to
    incomplete. Requires ``THINGS_AUTH_TOKEN``. Auto-confirmable.
    """
    payload_model = ProposeCancelTodoInput(todo_id=todo_id)
    payload = payload_model.model_dump()
    preview = handlers.cancel_todo.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.cancel_todo.KIND, payload=payload, preview=preview
    )


async def propose_cancel_project(project_id: str) -> dict:
    """Propose canceling a project.

    Marks the project canceled via the URL scheme. Undo restores it to
    incomplete. Requires ``THINGS_AUTH_TOKEN``. Auto-confirmable.
    """
    payload_model = ProposeCancelProjectInput(project_id=project_id)
    payload = payload_model.model_dump()
    preview = handlers.cancel_project.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.cancel_project.KIND, payload=payload, preview=preview
    )


async def propose_delete_project(project_id: str) -> dict:
    """Propose deleting a project by moving it to Things Trash.

    Uses AppleScript to move the project (and all its tasks) to Things Trash.
    Undo restores the project to Anytime (area membership not restored).

    Requires ``THINGS_MCP_ALLOW_APPLESCRIPT=1``.

    **Never auto-confirmed.**
    """
    if not config.ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "propose_delete_project requires THINGS_MCP_ALLOW_APPLESCRIPT=1. "
            "Set the environment variable and restart the MCP server."
        )
    payload_model = ProposeDeleteProjectInput(project_id=project_id)
    payload = payload_model.model_dump()
    preview = handlers.delete_project.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.delete_project.KIND, payload=payload, preview=preview
    )


# ---------- heading tools ----------


async def propose_add_heading(
    project_id: str,
    name: str,
    after_todo_id: str | None = None,
) -> dict:
    """Propose adding a dummy heading to an existing project.

    Creates a to-do titled ``__NAME__`` (all-caps between double
    underscores) inside the project. This is a URL-scheme-only workaround —
    position via ``after_todo_id`` is accepted but NOT honored (ordering
    requires AppleScript, arriving in step 5). The dummy task is visible
    in Things as a regular to-do (with underscores). Use
    ``convert_dummy_to_native_heading`` (step 6) to upgrade it later.

    Undo cancels the dummy task (moves to Logbook). Requires ``THINGS_AUTH_TOKEN`` only
    for undo.
    """
    payload_model = ProposeAddHeadingInput(
        project_id=project_id, name=name, after_todo_id=after_todo_id
    )
    payload = payload_model.model_dump()
    preview = handlers.add_heading.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.add_heading.KIND, payload=payload, preview=preview
    )


async def propose_update_heading(
    project_id: str,
    heading_id_or_name: str,
    new_name: str,
) -> dict:
    """Propose renaming a dummy heading inside a project.

    ``heading_id_or_name`` is either the UUID of the dummy heading task
    or the heading's current name. If both a native heading and a dummy
    share the same name, the tool raises with a list of candidates and
    asks you to retry with the specific UUID.

    Only dummy headings can be renamed here — native heading rename
    requires AppleScript (step 5). Requires ``THINGS_AUTH_TOKEN``.
    """
    payload_model = ProposeUpdateHeadingInput(
        project_id=project_id,
        heading_id_or_name=heading_id_or_name,
        new_name=new_name,
    )
    payload = payload_model.model_dump()
    preview = handlers.update_heading.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.update_heading.KIND, payload=payload, preview=preview
    )


async def propose_delete_heading(
    project_id: str,
    heading_id_or_name: str,
) -> dict:
    """Propose soft-deleting a dummy heading task inside a project.

    ``heading_id_or_name`` is the UUID of the dummy task or the heading
    name. The dummy task is moved to the Logbook (canceled+completed).
    Use ``undo()`` to restore it.

    Only dummy headings can be deleted here — native heading delete
    requires AppleScript (step 5).

    **Never auto-confirmed.** Requires ``THINGS_AUTH_TOKEN``.
    """
    payload_model = ProposeDeleteHeadingInput(
        project_id=project_id,
        heading_id_or_name=heading_id_or_name,
    )
    payload = payload_model.model_dump()
    preview = handlers.delete_heading.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.delete_heading.KIND, payload=payload, preview=preview
    )


async def propose_append_checklist_items(todo_id: str, items: list[str]) -> dict:
    """Propose appending items to a to-do's checklist.

    Items are appended to the end of the existing checklist. Use
    ``propose_prepend_checklist_items`` to add to the beginning, or
    ``propose_replace_checklist`` to overwrite the entire list.

    **Limitation:** per-item edit, delete, completion, or reorder are not
    supported by the Things URL scheme or AppleScript. Use
    ``propose_replace_checklist`` to rewrite the whole list.
    """
    payload = {"todo_id": todo_id, "items": items}
    from ..services.handlers import append_checklist as _append_checklist
    preview = _append_checklist.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=_append_checklist.KIND, payload=payload, preview=preview
    )


async def propose_prepend_checklist_items(todo_id: str, items: list[str]) -> dict:
    """Propose prepending items to a to-do's checklist.

    Items are inserted at the beginning of the existing checklist, in order.

    **Limitation:** per-item edit, delete, completion, or reorder are not
    supported. Use ``propose_replace_checklist`` to rewrite the whole list.
    """
    payload = {"todo_id": todo_id, "items": items}
    from ..services.handlers import prepend_checklist as _prepend_checklist
    preview = _prepend_checklist.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=_prepend_checklist.KIND, payload=payload, preview=preview
    )


async def propose_reorder_todos(container: str, new_order: list[str]) -> dict:
    """Propose reordering to-dos in a list or project.

    container: built-in list name ("inbox", "today", "anytime", "someday")
               or a project UUID.
    new_order: list of to-do UUIDs in the desired order. May be a complete
               list (full reorder) or a partial list (partial reorder —
               specified UUIDs are placed in the given relative order at
               their original sorted positions; other todos keep relative
               positions).

    Requires THINGS_MCP_ALLOW_APPLESCRIPT=1.

    Projects with native headings: native headings are auto-converted to
    dummy heading tasks at their original positions before reorder. The
    original empty native headings appear at the project bottom and must
    be deleted manually. Undo cannot reinstate native heading positions.
    """
    if not new_order:
        raise ValueError("new_order must contain at least one UUID.")

    from ..services.reorder import (
        resolve_container, build_master_order, detect_native_headings_in_project,
    )
    from ..services import things_repo as _things_repo
    from ..services.handlers import reorder_todos as _reorder_todos

    container_type, container_id = resolve_container(container)
    current_uuids = _things_repo.get_container_todo_uuids(container_type, container_id)
    master_order = build_master_order(current_uuids, new_order)

    proj_row = _things_repo.project(container_id) if container_type == "project" else None
    native_headings = detect_native_headings_in_project(proj_row)
    dummy_creation_plan = [
        {"name": h["name"], "todo_position": h["todo_position"]}
        for h in native_headings
    ]

    payload = {
        "container_type": container_type,
        "container_id": container_id,
        "master_order": master_order,
        "dummy_creation_plan": dummy_creation_plan,
        "original_order": current_uuids,
        "created_dummy_uuids": [],
    }

    preview = _reorder_todos.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=_reorder_todos.KIND, payload=payload, preview=preview
    )


async def propose_replace_checklist(todo_id: str, items: list[str]) -> dict:
    """Propose replacing a to-do's entire checklist with new items.

    **Never auto-confirmed** — this is a destructive overwrite. Always
    requires explicit ``confirm_action``.

    Pass ``items=[]`` to clear the checklist entirely. Undo restores the
    prior checklist snapshot.

    **Limitation:** per-item edit, delete, completion, or reorder are not
    supported by Things URL scheme or AppleScript — this tool is the only
    way to restructure a checklist.
    """
    payload = {"todo_id": todo_id, "items": items}
    from ..services.handlers import replace_checklist as _replace_checklist
    preview = _replace_checklist.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=_replace_checklist.KIND, payload=payload, preview=preview
    )


# ---------- AI tag tools ----------


async def propose_create_ai_tag(name: str, parent: str = "AI") -> dict:
    """Propose creating an AI-managed tag under the AI parent folder.

    The name MUST be asterisk-wrapped (e.g. '*Do Taxes*'). Server
    enforces this structural invariant. If the tag already exists,
    this is a no-op.

    Requires ``THINGS_MCP_ALLOW_APPLESCRIPT=1``.
    """
    if not config.ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "propose_create_ai_tag requires THINGS_MCP_ALLOW_APPLESCRIPT=1."
        )
    payload_model = ProposeCreateAiTagInput(name=name, parent=parent)
    payload = payload_model.model_dump()
    preview = handlers.create_ai_tag.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.create_ai_tag.KIND, payload=payload, preview=preview
    )


async def propose_manage_ai_tag(
    name: str,
    new_name: str | None = None,
    new_parent: str | None = None,
) -> dict:
    """Propose renaming and/or reparenting an AI tag.

    At least one of new_name / new_parent is required. new_name must
    also be asterisk-wrapped.

    Requires ``THINGS_MCP_ALLOW_APPLESCRIPT=1``.
    """
    if not config.ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "propose_manage_ai_tag requires THINGS_MCP_ALLOW_APPLESCRIPT=1."
        )
    payload_model = ProposeManageAiTagInput(
        name=name, new_name=new_name, new_parent=new_parent
    )
    payload = payload_model.model_dump(exclude_none=True)
    preview = handlers.manage_ai_tag.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.manage_ai_tag.KIND, payload=payload, preview=preview
    )


async def propose_delete_ai_tag(name: str) -> dict:
    """Propose deleting an AI tag — removes it from ALL tasks that carry it.

    This is a NEVER_BYPASS kind — explicit confirm_action() required
    even with THINGS_MCP_AUTO_CONFIRM=1.

    Requires ``THINGS_MCP_ALLOW_APPLESCRIPT=1``.
    """
    if not config.ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "propose_delete_ai_tag requires THINGS_MCP_ALLOW_APPLESCRIPT=1."
        )
    payload_model = ProposeDeleteAiTagInput(name=name)
    payload = payload_model.model_dump()
    preview = handlers.delete_ai_tag.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.delete_ai_tag.KIND, payload=payload, preview=preview
    )


async def propose_apply_ai_tags(
    items: list[dict],
    group_id: str | None = None,
) -> dict:
    """Propose applying AI tags to one or more to-dos.

    MERGE MODEL: new tag set = existing tags ∪ add_tags. Never clobbers
    user tags. Undo restores the EXACT prior tag set.

    Each item in ``items`` must have:
    - ``todo_uuid`` — the to-do's UUID
    - ``add_tags`` — list of asterisk-wrapped AI tag names (e.g. ``["*Do Taxes*"]``)
    - ``routing`` (optional) — ``{dest_kind, dest_uuid, transient}`` if this
      tag encodes a proposed sort destination. Set ``transient=true`` for
      routing tags that should be auto-cleaned after the move. Leave ``null``
      for persistent semantic tags (``*Unclear*``, ``*Ambiguous Home*``, etc.).

    EXISTING-LIST MATCHING (G6): Before calling this tool, read existing
    projects/areas via ``get_projects``/``get_areas`` and prefer existing
    destinations. Only propose a new list where nothing fits, and only with
    explicit user approval. When a destination name is ambiguous (duplicate
    names), show context: "Shopping — in Area 'Home'" or "Shopping — a
    standalone project (not in any Area)".

    ABSTAIN RULE: When confidence < 90% or criteria are ambiguous, apply
    ``*Unclear*`` (transient=false) rather than guessing. One unclear task
    never blocks the rest of the batch.

    Pass ``group_id`` (a shared UUID) to link all undo_log entries from one
    sort (apply_ai_tags → bulk_move → cleanup_ai_tags) so ``undo_group`` can
    reverse the whole sort atomically.

    Requires ``THINGS_MCP_ALLOW_APPLESCRIPT=1``.
    """
    if not config.ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "propose_apply_ai_tags requires THINGS_MCP_ALLOW_APPLESCRIPT=1."
        )
    payload_model = ProposeApplyAiTagsInput(items=items, group_id=group_id)
    payload = payload_model.model_dump()
    preview = handlers.apply_ai_tags.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.apply_ai_tags.KIND, payload=payload, preview=preview
    )


async def propose_cleanup_ai_tags(
    todo_uuids: list[str],
    group_id: str | None = None,
) -> dict:
    """Propose removing transient AI routing tags from to-dos after a confirmed sort.

    Strips ONLY ``transient=1`` routing tags recorded in ``ai_tag_routing``.
    NEVER strips ``*Unclear*`` or other persistent abstain tags (those have
    ``transient=0`` and are not touched by cleanup).

    Call this AFTER ``bulk_move`` has confirmed the tasks landed in their new
    destinations. Pass the same ``group_id`` used in ``propose_apply_ai_tags``
    and ``propose_bulk_move`` to keep the undo group linked.

    Requires ``THINGS_MCP_ALLOW_APPLESCRIPT=1``.
    """
    if not config.ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "propose_cleanup_ai_tags requires THINGS_MCP_ALLOW_APPLESCRIPT=1."
        )
    payload_model = ProposeCleanupAiTagsInput(todo_uuids=todo_uuids, group_id=group_id)
    payload = payload_model.model_dump()
    preview = handlers.cleanup_ai_tags.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.cleanup_ai_tags.KIND, payload=payload, preview=preview
    )


# ---------- shared helper ----------


async def _enqueue_and_maybe_auto_confirm(
    *, kind: str, payload: dict, preview: str
) -> dict:
    """Common tail for every propose tool.

    Always enqueues the action (so it shows up in
    ``list_pending_actions`` and is auditable). If auto-confirm is on
    AND the kind isn't in NEVER_BYPASS_KINDS, immediately dispatches to
    the handler and removes the pending row.

    If the handler fails mid-auto-confirm, we **keep** the pending row
    so the user can retry via ``confirm_action`` after fixing the
    underlying issue (e.g. set a missing auth token). The exception
    propagates so the agent reports it.
    """
    stub = pending.enqueue(kind=kind, payload=payload, preview=preview)

    is_never_bypass = kind in config.NEVER_BYPASS_KINDS
    if not config.AUTO_CONFIRM or is_never_bypass:
        return {
            **stub,
            "auto_confirmed": False,
            "next_step": (
                "Show the preview to the user. On approval call "
                "confirm_action(action_id); to drop call cancel_action(action_id)."
                + (
                    " (Note: this kind is never auto-confirmed — explicit "
                    "approval always required.)"
                    if is_never_bypass and config.AUTO_CONFIRM
                    else ""
                )
            ),
        }

    handler = handlers.get(kind)
    result = await handler.execute(payload)  # may raise; pending row remains
    pending.delete(stub["action_id"])
    return {
        **stub,
        "auto_confirmed": True,
        "result": result,
        "next_step": (
            "Auto-confirmed via THINGS_MCP_AUTO_CONFIRM. Action executed; "
            "use undo() to reverse if needed."
        ),
    }


# ---------- FastMCP registration ----------


def register(mcp: FastMCP) -> None:
    mcp.tool()(propose_add_todo)
    mcp.tool()(propose_cancel_todo)
    mcp.tool()(propose_update_todo)
    mcp.tool()(propose_move_todo)
    mcp.tool()(propose_delete_todo)
    mcp.tool()(propose_add_project)
    mcp.tool()(propose_cancel_project)
    mcp.tool()(propose_delete_project)
    mcp.tool()(propose_update_project)
    mcp.tool()(propose_bulk_complete)
    mcp.tool()(propose_bulk_cancel)
    mcp.tool()(propose_bulk_move)
    mcp.tool()(propose_bulk_update)
    mcp.tool()(propose_add_heading)
    mcp.tool()(propose_update_heading)
    mcp.tool()(propose_delete_heading)
    mcp.tool()(propose_append_checklist_items)
    mcp.tool()(propose_prepend_checklist_items)
    mcp.tool()(propose_replace_checklist)
    mcp.tool()(propose_reorder_todos)
    mcp.tool()(propose_create_ai_tag)
    mcp.tool()(propose_manage_ai_tag)
    mcp.tool()(propose_delete_ai_tag)
    mcp.tool()(propose_apply_ai_tags)
    mcp.tool()(propose_cleanup_ai_tags)
