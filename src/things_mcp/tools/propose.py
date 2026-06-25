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
    BulkAddTodoItem,
    ProposeAddHeadingInput,
    ProposeAddProjectInput,
    ProposeAddTodoInput,
    ProposeApplyAiTagsInput,
    ProposeBulkAddTodoInput,
    ProposeBulkCancelInput,
    ProposeBulkCompleteInput,
    ProposeBulkDeleteHeadingInput,
    ProposeBulkDeleteInput,
    ProposeBulkMoveInput,
    ProposeBulkUpdateInput,
    ProposeCancelProjectInput,
    ProposeCancelTodoInput,
    ProposeCleanupAiTagsInput,
    ProposeCreateAiTagInput,
    ProposeCreateTagInput,
    ProposeDeleteAiTagInput,
    ProposeDeleteHeadingInput,
    ProposeDeleteProjectInput,
    ProposeDeleteTodoInput,
    ProposeManageAiTagInput,
    ProposeMoveTodoInput,
    ProposeMoveUnderAiHeadingInput,
    ProposeUpdateHeadingInput,
    ProposeUpdateProjectInput,
    ProposeUpdateTodoInput,
)
from ..services import handlers, things_repo, url_scheme
from ..state import pending, sort_session

# Move targets that are NOT a project/area UUID (keywords + computed views).
_NON_LIST_TARGETS = {"inbox", "today", "anytime", "someday", "upcoming"}


def _targets_existing_user_project(target: str) -> bool:
    """True if ``target`` is a pre-existing user project (not a keyword, area,
    or AI-created sort project) — i.e. a move into it should land under the
    ``__NEWLY ADDED BY AI__`` marker."""
    if not target or target.strip().lower() in _NON_LIST_TARGETS:
        return False
    if sort_session.is_ai_created(target):
        return False
    return things_repo.project(target) is not None


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
    * ``"inbox"`` — move to Inbox via AppleScript (requires
      ``THINGS_MCP_ALLOW_APPLESCRIPT=1``). Undo restores the original
      scheduling; if the task was already in Inbox before the move it
      uses AppleScript to restore it there.
    * ``"today"`` / ``"anytime"`` / ``"someday"`` — change scheduling
      (preserves project/area membership).
    * A project/area UUID — change membership (preserves scheduling).

    Requires ``THINGS_AUTH_TOKEN``.
    """
    if target and target.lower() == "upcoming":
        raise ValueError(
            "target='upcoming' is a computed view in Things, not a move "
            "destination. To schedule a task for a future date that appears "
            "in Upcoming, update the to-do with `when='<YYYY-MM-DD>'`."
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

    Respects ``THINGS_MCP_AUTO_CONFIRM=1`` — single-item deletes go to
    Trash (reversible via ``undo()``), so confirmation is not forced
    when the user has explicitly named the item. Use
    ``propose_bulk_delete_todo`` for multi-target deletes, which always
    require explicit confirmation.
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
    area: str | None = None,
    area_id: str | None = None,
    when: str | None = None,
    deadline: str | None = None,
    notes: str | None = None,
    tags: list[str] | None = None,
    headings: list[str] | None = None,
    member_todo_ids: list[str] | None = None,
) -> dict:
    """Propose adding a new Things project.

    When ``headings`` is non-empty, the project is created through Things'
    ``things:///json`` endpoint — the only URL-scheme path that produces
    native section headings at project birth. Without headings the
    unauthenticated ``add-project`` URL is used.

    ``area`` (area NAME) places the project in an **existing** area by name;
    it must already exist (it is NOT auto-created). ``area_id`` places the
    project in an existing area by UUID. Pass at most one — they are mutually
    exclusive.

    Undo cancels the created project (canceled+completed → Logbook).
    Undo requires ``THINGS_AUTH_TOKEN`` even though execute does not.

    **Sort-session contract:** when a sort session is active,
    ``member_todo_ids`` MUST be provided and contain at least 3 task UUIDs
    (the tasks that will go into this project).  If fewer than 3 are
    supplied, the call is rejected with a validation error and the agent
    must instead tag those tasks with ``*Unclear*`` rather than creating a
    project for a sub-threshold cluster.  When no sort is active this
    parameter is optional and no size check is applied, so normal
    (non-sort) project creation is unaffected.
    """
    # Enforce the >=3 member guard during an active sort session.
    if sort_session.active() is not None:
        count = len(member_todo_ids) if member_todo_ids else 0
        if count < 3:
            sort_session.record_rejected_project(title, member_todo_ids)
            return {
                "validation_error": True,
                "message": (
                    f"A sort session is active but only {count} task(s) were "
                    "provided in member_todo_ids (minimum 3 required). "
                    "Do NOT create this project. Instead tag the task(s) with "
                    "*Unclear* (routing=null, transient=false) and let the user "
                    "decide whether a project is warranted."
                ),
            }

    url_scheme.validate_tags(tags)
    payload_model = ProposeAddProjectInput(
        title=title,
        area=area,
        area_id=area_id,
        when=when,
        deadline=deadline,
        notes=notes,
        tags=tags,
        headings=headings,
        member_todo_ids=member_todo_ids,
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


async def propose_bulk_cancel(todo_ids: list[str], group_id: str | None = None) -> dict:
    """Propose canceling N to-dos in one airlocked op.

    Each task gets marked canceled. Use ``undo()`` to restore the whole
    batch. **Never auto-confirmed.**

    ``group_id`` — optional label written to the undo_log so that
    ``undo_group(group_id)`` can reverse multiple operations atomically.
    """
    payload_model = ProposeBulkCancelInput(todo_ids=todo_ids, group_id=group_id)
    payload = payload_model.model_dump()
    preview = handlers.bulk_delete.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.bulk_delete.KIND, payload=payload, preview=preview
    )


async def propose_bulk_move(
    todo_ids: list[str],
    target: str,
    group_id: str | None = None,
) -> dict:
    """Propose moving N to-dos to a single target.

    ``target`` follows the same rules as :func:`propose_move_todo`:
    * ``"inbox"`` — move to Inbox via AppleScript (requires
      ``THINGS_MCP_ALLOW_APPLESCRIPT=1``).
    * ``"today"`` / ``"anytime"`` / ``"someday"`` — scheduling move.
    * A project/area UUID — membership move.

    ``group_id`` — if no sort session is active, one is started automatically
    so that ``group_id`` is always non-null in the undo log.  Pass the same
    group_id used in
    ``propose_apply_ai_tags`` and ``propose_cleanup_ai_tags`` to keep
    the undo group linked so ``undo_group(group_id)`` can reverse the
    entire sort atomically.

    **Never auto-confirmed.**
    """
    if target and target.lower() == "upcoming":
        raise ValueError(
            "target='upcoming' is a computed view in Things, not a move "
            "destination. To schedule tasks for a future date that appears "
            "in Upcoming, use propose_bulk_update with `when`."
        )
    # Auto-init: ensure a sort session is open so group_id is always
    # non-null in the undo log, even when the agent skips
    # propose_apply_ai_tags.  Do NOT register todo_ids here — is_sort_move()
    # must remain gated on explicit tagging via propose_apply_ai_tags so that
    # unrelated bulk_moves are not promoted to the heading path.
    group_id = sort_session.begin(group_id)
    sort_move = sort_session.is_sort_move(todo_ids)
    # During a sort, a move of sort-member tasks into a pre-existing user project
    # must land under the marker — auto-promote to the heading path so the audit
    # marker is enforced in code, not left to the agent's tool choice.
    if sort_move and _targets_existing_user_project(target):
        return await propose_move_under_ai_heading(
            todo_ids=todo_ids, project_id=target, group_id=group_id
        )
    payload_model = ProposeBulkMoveInput(todo_ids=todo_ids, target=target, group_id=group_id)
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
    group_id: str | None = None,
) -> dict:
    """Propose applying one set of field changes to N to-dos.

    Convention matches :func:`propose_update_todo`: ``None`` means "don't
    change", ``""`` clears a string field, ``[]`` clears tags. At least
    one updatable field required. **Never auto-confirmed.**

    ``group_id`` — optional label written to the undo_log so that
    ``undo_group(group_id)`` can reverse multiple operations atomically.
    """
    url_scheme.validate_tags(tags)
    payload_model = ProposeBulkUpdateInput(
        todo_ids=todo_ids,
        title=title,
        notes=notes,
        deadline=deadline,
        tags=tags,
        group_id=group_id,
    )
    payload = payload_model.model_dump(exclude_none=True)
    preview = handlers.bulk_update.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.bulk_update.KIND, payload=payload, preview=preview
    )


async def propose_bulk_delete_todo(
    todo_ids: list[str],
    group_id: str | None = None,
) -> dict:
    """Propose deleting N to-dos in one airlocked op (moves all to Things Trash).

    Bulk version of ``propose_delete_todo``. Validates every id before any
    mutation — if one is missing or already in Trash, the whole batch aborts.
    Undo restores each task from Trash to its original list or project.

    Requires ``THINGS_MCP_ALLOW_APPLESCRIPT=1``.

    **Never auto-confirmed** — explicit ``confirm_action`` always required.
    """
    if not config.ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "propose_bulk_delete_todo requires THINGS_MCP_ALLOW_APPLESCRIPT=1. "
            "Set the environment variable and restart the MCP server."
        )
    payload_model = ProposeBulkDeleteInput(todo_ids=todo_ids, group_id=group_id)
    payload = payload_model.model_dump()
    preview = handlers.bulk_delete_todo.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.bulk_delete_todo.KIND, payload=payload, preview=preview
    )


async def propose_bulk_delete_heading(
    project_id: str,
    heading_ids_or_names: list[str],
    group_id: str | None = None,
) -> dict:
    """Propose soft-deleting N dummy headings from a project in one airlocked op.

    Bulk version of ``propose_delete_heading``. Validates every heading
    before any mutation — all must be dummy headings (``__NAME__`` format)
    and not already deleted. Undo restores each heading to incomplete.

    Requires ``THINGS_AUTH_TOKEN``.

    **Never auto-confirmed** — explicit ``confirm_action`` always required.
    """
    payload_model = ProposeBulkDeleteHeadingInput(
        project_id=project_id,
        heading_ids_or_names=heading_ids_or_names,
        group_id=group_id,
    )
    payload = payload_model.model_dump()
    preview = handlers.bulk_delete_heading.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.bulk_delete_heading.KIND, payload=payload, preview=preview
    )


async def propose_bulk_add_todo(
    list_id: str,
    items: list[dict],
    group_id: str | None = None,
    preserve_order: bool = True,
) -> dict:
    """Propose adding N to-dos to a single destination in one airlocked op.

    Each item in ``items`` is a dict with ``title`` (required) and optional
    ``notes``, ``when``, ``deadline``, ``tags``, ``checklist``. All items
    land in the same ``list_id`` — use ``propose_add_todo`` for items going
    to different lists.

    ``list_id`` accepts the same values as ``propose_add_todo``: ``inbox``,
    ``today``, ``anytime``, ``someday``, or a project/area UUID.

    ``preserve_order`` (default True) ensures the final visible order in Things
    matches the order of ``items``. The Things Inbox and Today views insert each
    new task at the TOP of the list, so adding [A, B, C] sequentially produces
    visible order [C, B, A]. When ``preserve_order=True`` and the target is a
    top-inserting list (``inbox`` or ``today``), the handler reverses the add
    sequence internally so [A, B, C] is the final visible order. For project and
    area targets (which insert at the bottom), the original order is preserved
    without reversal. Pass ``preserve_order=False`` to disable this behavior.

    Undo soft-cancels every added task (completed+canceled). Requires
    ``THINGS_AUTH_TOKEN`` for undo.
    """
    parsed_items = [BulkAddTodoItem(**it) for it in items]
    payload_model = ProposeBulkAddTodoInput(
        list_id=list_id,
        items=parsed_items,
        group_id=group_id,
        preserve_order=preserve_order,
    )
    payload = payload_model.model_dump()
    preview = handlers.bulk_add_todo.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.bulk_add_todo.KIND, payload=payload, preview=preview
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
    group_id: str | None = None,
) -> dict:
    """Propose adding a dummy heading to an existing project.

    Creates a to-do titled ``__NAME__`` (all-caps between double
    underscores) inside the project. This is a URL-scheme-only workaround —
    position via ``after_todo_id`` is accepted but NOT honored (ordering
    requires AppleScript, arriving in step 5). The dummy task is visible
    in Things as a regular to-do (with underscores). Native heading
    conversion is not currently supported.

    Undo cancels the dummy task (moves to Logbook). Requires ``THINGS_AUTH_TOKEN`` only
    for undo.

    ``group_id`` — optional label written to the undo_log so that
    ``undo_group(group_id)`` can reverse multiple operations atomically.
    """
    payload_model = ProposeAddHeadingInput(
        project_id=project_id, name=name, after_todo_id=after_todo_id, group_id=group_id
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
    group_id: str | None = None,
) -> dict:
    """Propose soft-deleting a dummy heading task inside a project.

    ``heading_id_or_name`` is the UUID of the dummy task or the heading
    name. The dummy task is moved to the Logbook (canceled+completed).
    Use ``undo()`` to restore it.

    Only dummy headings can be deleted here — native heading delete
    requires AppleScript (step 5).

    **Never auto-confirmed.** Requires ``THINGS_AUTH_TOKEN``.

    ``group_id`` — optional label written to the undo_log so that
    ``undo_group(group_id)`` can reverse multiple operations atomically.
    """
    payload_model = ProposeDeleteHeadingInput(
        project_id=project_id,
        heading_id_or_name=heading_id_or_name,
        group_id=group_id,
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


async def propose_reorder_todos(
    container: str,
    new_order: list[str],
    allow_existing_reorder: bool = False,
) -> dict:
    """Propose reordering to-dos in a list or project.

    container: built-in list name ("inbox", "today", "anytime", "someday")
               or a project UUID.
    new_order: list of to-do UUIDs in the desired order. May be a complete
               list (full reorder) or a partial list (partial reorder —
               specified UUIDs are placed in the given relative order at
               their original sorted positions; other todos keep relative
               positions).
    allow_existing_reorder: if False (default) and a __NEWLY ADDED BY AI__
               marker is present, reordering tasks at or above the marker
               is rejected to keep pre-existing tasks pinned at the top.
               Pass True to override this guard.

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
        "allow_existing_reorder": allow_existing_reorder,
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


# ---------- AI sort — move under marker ----------


async def propose_move_under_ai_heading(
    todo_ids: list[str],
    project_id: str,
    group_id: str | None = None,
) -> dict:
    """Propose moving to-dos into an existing project under ``__NEWLY ADDED BY AI__``.

    Creates the ``__NEWLY ADDED BY AI__`` marker heading inside the project if it
    does not already exist, then moves all ``todo_ids`` into the project and
    reorders so pre-existing tasks appear **above** the marker and newly moved
    tasks appear **below** it.

    Idempotent with respect to the marker — calling this multiple times for the
    same project reuses the existing marker and appends new tasks under it (after
    any tasks placed by earlier calls).

    The marker itself is silently filtered out if accidentally included in
    ``todo_ids``.

    Use this instead of plain ``propose_bulk_move`` when moving tasks into an
    **existing** project during a sort — the marker lets the user distinguish
    AI-placed tasks from tasks that were already there.

    ``group_id`` — pass the same group_id used in ``propose_apply_ai_tags`` and
    ``propose_bulk_move`` to keep the undo group linked for ``undo_group``.

    **Never auto-confirmed.** Requires ``THINGS_AUTH_TOKEN`` and
    ``THINGS_MCP_ALLOW_APPLESCRIPT=1``.
    """
    if not config.ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "propose_move_under_ai_heading requires THINGS_MCP_ALLOW_APPLESCRIPT=1. "
            "Set the environment variable and restart the MCP server."
        )
    if group_id is None:
        group_id = sort_session.active()
    payload_model = ProposeMoveUnderAiHeadingInput(
        todo_ids=todo_ids, project_id=project_id, group_id=group_id
    )
    payload = payload_model.model_dump()
    preview = handlers.move_under_heading.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.move_under_heading.KIND, payload=payload, preview=preview
    )


# ---------- AI tag tools ----------


async def propose_create_ai_tag(name: str, parent: str = "AI") -> dict:
    """Propose creating an AI-managed tag under the AI parent folder.

    NAMING CONVENTION — all AI tags must follow this pattern:
    - Asterisk-wrapped: ``*Do Taxes*``, ``*Buy Groceries*``, ``*Errand*``
    - ≤2–3 words, actionable imperative or clear noun, Title Case
    - Under the ``AI`` parent (server enforces parent assignment)
    - Server enforces the asterisk wrapper — rejects malformed names

    Use the persistent abstain vocabulary for ambiguous cases:
    ``*Unclear*``, ``*Duplicate?*``, ``*No Time Signal*``,
    ``*Ambiguous Home*``, ``*Review Delete?*`` — all parented under
    ``AI``, all with ``transient=false``.

    Idempotent: if the tag already exists, this is a no-op success.

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


async def propose_create_tag(name: str, parent: str | None = None) -> dict:
    """Propose creating a plain user-named tag in Things.

    Use this for USER-NAMED tags — tags the user explicitly asked to create,
    such as "admin", "Health", or "Finance". These are plain tags with no
    asterisk wrapping.

    If the user asked to create an AI-INVENTED tag (a name the agent chose
    with no user involvement), use ``propose_create_ai_tag`` instead — it
    enforces the asterisk-wrapper convention and files the tag under the AI
    parent.

    ``parent`` is optional: omit to create a top-level tag; supply to nest
    the new tag under an existing (or auto-created) parent tag.

    Idempotent: if the tag already exists, this is a no-op success.

    Requires ``THINGS_MCP_ALLOW_APPLESCRIPT=1``.
    """
    if not config.ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "propose_create_tag requires THINGS_MCP_ALLOW_APPLESCRIPT=1."
        )
    payload_model = ProposeCreateTagInput(name=name, parent=parent)
    payload = payload_model.model_dump()
    preview = handlers.create_tag.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=handlers.create_tag.KIND, payload=payload, preview=preview
    )


async def propose_manage_ai_tag(
    name: str,
    new_name: str | None = None,
    new_parent: str | None = None,
) -> dict:
    """Propose renaming and/or reparenting an AI tag.

    At least one of ``new_name`` / ``new_parent`` is required.
    ``new_name`` must also be asterisk-wrapped (``*New Name*``).

    Naming convention: ≤2–3 words, Title Case, asterisk-wrapped.
    Parent is normally ``AI``; only change if intentional.

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

    WARNING: Wide-blast destructive operation. The tag is removed from
    every task carrying it — not just the current batch. Use
    ``list_ai_tags()`` first to see how many tasks carry the tag.

    Consider ``propose_cleanup_ai_tags`` for targeted post-sort cleanup
    (strips only transient routing tags from specific tasks); use this
    only to permanently remove a tag from the entire system.

    This is a NEVER_BYPASS kind — explicit ``confirm_action()`` required
    even with ``THINGS_MCP_AUTO_CONFIRM=1``.

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

    ABSTAIN RULE (90% soft anchor — criteria-based, not numeric):
    When confidence is below ~90%, or any criterion fires, abstain and
    apply ``*Unclear*`` (with ``routing=null``, ``transient=false``) rather
    than guessing. Criteria that trigger abstain:
    - Ambiguous destination (multiple equally-plausible projects/areas)
    - No time signal (scheduling requested but no date/duration evidence)
    - Suspected near-duplicate
    - Nothing-fits semantic label (forced label would mislead)
    - Uncertain destructive membership (bulk-delete criteria unclear)
    Use the specific vocabulary when the reason is known:
    ``*Duplicate?*``, ``*No Time Signal*``, ``*Ambiguous Home*``,
    ``*Review Delete?*``. One unclear task NEVER blocks the rest of the
    batch — mix confident and unclear items in the same call.

    PARTIAL EXECUTION: Confident items get routing tags; unclear items
    get abstain tags (``transient=false``). Both in the same ``items`` list.

    Each item in ``items`` must have:
    - ``todo_uuid`` — the to-do's UUID
    - ``add_tags`` — list of asterisk-wrapped AI tag names (e.g. ``["*Do Taxes*"]``)
    - ``routing`` (optional) — ``{dest_kind, dest_uuid, transient}`` if this
      tag encodes a proposed sort destination. Set ``transient=true`` for
      routing tags that should be auto-cleaned after the move. Leave ``null``
      for persistent abstain tags (``*Unclear*``, ``*Ambiguous Home*``, etc.).

    EXISTING-LIST MATCHING (default bias): Before calling, read existing
    projects/areas via ``get_projects``/``get_areas`` and prefer existing
    destinations. Only propose a new list where nothing fits, and only
    with explicit user approval. When a destination name is ambiguous
    (duplicate names), show context: "Shopping — in Area 'Home'" or
    "Shopping — a standalone project (not in any Area)".

    SORT WORKFLOW: apply_ai_tags → (user reviews via list_ai_tags) →
    bulk_move → cleanup_ai_tags. Pass ``group_id`` (a shared UUID you
    generate once per sort) to link all undo_log entries so
    ``undo_group(group_id)`` can reverse the whole sort atomically.
    Surface the ``group_id`` to the user so they can undo in one command.

    Requires ``THINGS_MCP_ALLOW_APPLESCRIPT=1``.
    """
    if not config.ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "propose_apply_ai_tags requires THINGS_MCP_ALLOW_APPLESCRIPT=1."
        )
    # apply_ai_tags is the sort anchor: open a session so every later sort tool
    # inherits this group_id even if the agent never threads one through. A
    # server-owned id guarantees undo_group can reverse the whole run.
    group_id = sort_session.begin(group_id)
    sort_session.register_tagged(item.get("todo_uuid") for item in items)
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
    NEVER strips ``*Unclear*``, ``*Duplicate?*``, ``*Ambiguous Home*``,
    ``*No Time Signal*``, or ``*Review Delete?*`` — persistent abstain tags
    have ``transient=0`` and are never touched by cleanup.

    Call AFTER ``bulk_move`` has confirmed tasks landed in their new
    destinations. Pass the same ``group_id`` used in ``propose_apply_ai_tags``
    and ``propose_bulk_move`` to keep the undo group linked.

    After this completes, the user can call ``undo_group(group_id)`` to
    reverse the entire sort (cleanup → move → tag-apply) in correct LIFO
    order.

    Requires ``THINGS_MCP_ALLOW_APPLESCRIPT=1``.
    """
    if not config.ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "propose_cleanup_ai_tags requires THINGS_MCP_ALLOW_APPLESCRIPT=1."
        )
    if group_id is None:
        group_id = sort_session.active()
    payload_model = ProposeCleanupAiTagsInput(todo_uuids=todo_uuids, group_id=group_id)
    payload = payload_model.model_dump()
    preview = handlers.cleanup_ai_tags.make_preview(payload)
    result = await _enqueue_and_maybe_auto_confirm(
        kind=handlers.cleanup_ai_tags.KIND, payload=payload, preview=preview
    )
    # cleanup is the final sort step — close the session so later standalone
    # moves are not auto-grouped or auto-marked.
    sort_session.end()
    return result


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
    mcp.tool()(propose_bulk_delete_todo)
    mcp.tool()(propose_bulk_delete_heading)
    mcp.tool()(propose_bulk_add_todo)
    mcp.tool()(propose_bulk_move)
    mcp.tool()(propose_bulk_update)
    mcp.tool()(propose_add_heading)
    mcp.tool()(propose_update_heading)
    mcp.tool()(propose_delete_heading)
    mcp.tool()(propose_append_checklist_items)
    mcp.tool()(propose_prepend_checklist_items)
    mcp.tool()(propose_replace_checklist)
    mcp.tool()(propose_reorder_todos)
    mcp.tool()(propose_move_under_ai_heading)
    mcp.tool()(propose_create_ai_tag)
    mcp.tool()(propose_create_tag)
    mcp.tool()(propose_manage_ai_tag)
    mcp.tool()(propose_delete_ai_tag)
    mcp.tool()(propose_apply_ai_tags)
    mcp.tool()(propose_cleanup_ai_tags)
