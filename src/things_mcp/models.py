"""Pydantic request/response models for tool inputs and outputs."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ChecklistItemInput(BaseModel):
    title: str


class AddInboxTodoInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    notes: str | None = None
    when: str | None = Field(
        default=None,
        description=(
            "Things 'when' value: today, tomorrow, evening, anytime, someday, "
            "or an ISO date / datetime (YYYY-MM-DD or YYYY-MM-DD@HH:MM)."
        ),
    )
    deadline: str | None = Field(default=None, description="ISO date YYYY-MM-DD.")
    tags: list[str] | None = None
    checklist: list[str] | None = Field(
        default=None,
        description="Optional checklist item titles, added in order.",
    )


class AddInboxTodoResult(BaseModel):
    id: str
    title: str
    list: Literal["Inbox"] = "Inbox"
    created_at: str


class DirectAddTodoInput(BaseModel):
    """Input model for the V2 direct-add shortcuts (``add_today_todo``,
    ``add_anytime_todo``, ``add_someday_todo``).

    Distinct from ``ProposeAddTodoInput`` because direct adds intentionally
    do NOT accept a ``when`` parameter — the list is the scheduling, and
    accepting both would invite ambiguous URLs. Users who need a specific
    time (e.g. ``today@18:00``) should use ``propose_add_todo`` with the
    explicit ``when`` arg.
    """
    title: str = Field(..., min_length=1, max_length=500)
    list_id: str = Field(..., min_length=1)
    notes: str | None = None
    deadline: str | None = Field(default=None, description="ISO date YYYY-MM-DD.")
    tags: list[str] | None = None
    checklist: list[str] | None = None


class ProposeAddTodoInput(BaseModel):
    """V2 — propose adding a to-do to any list (not just Inbox).

    ``list_id`` accepts a reserved keyword (``inbox``, ``today``,
    ``anytime``, ``someday``, ``upcoming``) or a project/area UUID.
    """
    title: str = Field(..., min_length=1, max_length=500)
    list_id: str = Field(default="inbox", min_length=1)
    notes: str | None = None
    when: str | None = Field(
        default=None,
        description=(
            "Things 'when' value: today, tomorrow, evening, anytime, someday, "
            "or an ISO date / datetime."
        ),
    )
    deadline: str | None = Field(default=None, description="ISO date YYYY-MM-DD.")
    tags: list[str] | None = None
    checklist: list[str] | None = None


class ProposeUpdateTodoInput(BaseModel):
    """V2 — propose updating fields on an existing to-do.

    Convention: ``None`` means "don't change". Empty string ``""`` clears
    a string field (notes / deadline). Empty list ``[]`` clears all tags.
    Pass at least one updatable field.

    ``when`` is intentionally absent from the first cut — restoring
    scheduling cleanly requires a richer mapping and is scheduled for a
    follow-up.
    """
    todo_id: str = Field(..., min_length=1)
    title: str | None = Field(default=None, min_length=1, max_length=500)
    notes: str | None = None
    deadline: str | None = Field(
        default=None,
        description="ISO date YYYY-MM-DD, or '' to clear.",
    )
    tags: list[str] | None = Field(
        default=None,
        description="List of tag names; [] clears all tags.",
    )

    @model_validator(mode="after")
    def _require_at_least_one_field(self) -> "ProposeUpdateTodoInput":
        if self.title is None and self.notes is None and self.deadline is None and self.tags is None:
            raise ValueError(
                f"propose_update_todo for {self.todo_id!r} has no fields to update. "
                "Pass at least one of: title, notes, deadline, tags."
            )
        return self


class ProposeMoveTodoInput(BaseModel):
    """V2 — propose moving a to-do to a different list or project.

    ``target`` accepts:

    * ``"today"`` / ``"anytime"`` / ``"someday"`` — scheduling move
      (preserves project/area membership).
    * A 22-char Things UUID — project/area membership change.
    * Other strings are rejected with an actionable hint.

    Specific-date moves and move-to-Inbox are deferred to a follow-up.
    """
    todo_id: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)


class ProposeDeleteTodoInput(BaseModel):
    """V2 step 5A — propose deleting a to-do via AppleScript.

    Moves the task to Things Trash (the same as deleting manually in the
    Things UI). Requires ``THINGS_MCP_ALLOW_APPLESCRIPT=1``.

    This kind is in ``NEVER_BYPASS_KINDS`` — even with
    ``THINGS_MCP_AUTO_CONFIRM=1`` the user must explicitly call
    ``confirm_action``.
    """
    todo_id: str = Field(..., min_length=1)


class ProposeAddProjectInput(BaseModel):
    """V2 — propose adding a new Things project.

    Two URL-scheme paths under the hood:

    * No ``headings`` → ``things:///add-project?...`` (unauthenticated).
    * ``headings`` non-empty → ``things:///json?data=<JSON>`` — the only
      mechanism for creating native section headings at project birth.

    ``area_id`` puts the project under an existing area UUID. ``when`` /
    ``deadline`` follow the same conventions as the to-do tools.
    """
    title: str = Field(..., min_length=1, max_length=500)
    area_id: str | None = Field(default=None, min_length=1)
    when: str | None = Field(
        default=None,
        description=(
            "Things 'when' value: today, anytime, someday, or an ISO date "
            "(YYYY-MM-DD)."
        ),
    )
    deadline: str | None = Field(default=None, description="ISO date YYYY-MM-DD.")
    notes: str | None = None
    tags: list[str] | None = None
    headings: list[str] | None = Field(
        default=None,
        description=(
            "Native section headings to create at project birth. Routes "
            "through the things:///json endpoint."
        ),
    )


class ProposeUpdateProjectInput(BaseModel):
    """V2 — propose updating fields on an existing project.

    Convention mirrors :class:`ProposeUpdateTodoInput`: ``None`` means
    "don't change", ``""`` clears a string field, ``[]`` clears all tags.
    Pass at least one updatable field.

    ``when`` is intentionally absent from the first cut (same reason as
    update_todo — restoring scheduling cleanly is a follow-up).
    """
    project_id: str = Field(..., min_length=1)
    title: str | None = Field(default=None, min_length=1, max_length=500)
    notes: str | None = None
    deadline: str | None = Field(
        default=None,
        description="ISO date YYYY-MM-DD, or '' to clear.",
    )
    tags: list[str] | None = Field(
        default=None,
        description="List of tag names; [] clears all tags.",
    )
    area_id: str | None = Field(
        default=None,
        description="Area UUID to move the project into, or '' to clear.",
    )

    @model_validator(mode="after")
    def _require_at_least_one_field(self) -> "ProposeUpdateProjectInput":
        if (
            self.title is None
            and self.notes is None
            and self.deadline is None
            and self.tags is None
            and self.area_id is None
        ):
            raise ValueError(
                f"propose_update_project for {self.project_id!r} has no fields to "
                "update. Pass at least one of: title, notes, deadline, tags, area_id."
            )
        return self


class ProposeBulkCompleteInput(BaseModel):
    """V2 — propose marking N to-dos completed in one airlocked op.

    Always in :data:`config.NEVER_BYPASS_KINDS` — explicit confirm required.
    """
    todo_ids: list[str] = Field(..., min_length=1)


class ProposeBulkDeleteInput(BaseModel):
    """V2 — propose soft-deleting N to-dos in one airlocked op."""
    todo_ids: list[str] = Field(..., min_length=1)


class ProposeBulkMoveInput(BaseModel):
    """V2 — propose moving N to-dos to a single target."""
    todo_ids: list[str] = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    group_id: str | None = Field(default=None)


class ProposeBulkUpdateInput(BaseModel):
    """V2 — propose applying one set of field changes to N to-dos.

    Same convention as :class:`ProposeUpdateTodoInput`: ``None`` means
    "don't change", ``""`` clears a string field, ``[]`` clears tags.
    Pass at least one updatable field.
    """
    todo_ids: list[str] = Field(..., min_length=1)
    title: str | None = Field(default=None, min_length=1, max_length=500)
    notes: str | None = None
    deadline: str | None = Field(
        default=None,
        description="ISO date YYYY-MM-DD, or '' to clear.",
    )
    tags: list[str] | None = Field(
        default=None,
        description="List of tag names; [] clears all tags.",
    )

    @model_validator(mode="after")
    def _require_at_least_one_field(self) -> "ProposeBulkUpdateInput":
        if self.title is None and self.notes is None and self.deadline is None and self.tags is None:
            raise ValueError(
                "propose_bulk_update has no fields to update. Pass at least "
                "one of: title, notes, deadline, tags."
            )
        return self


class ProposeAddHeadingInput(BaseModel):
    project_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=200, description="Heading name (will be stored as __NAME__ dummy task title)")
    after_todo_id: str | None = Field(default=None, description="Hint for position (not honored by URL-scheme layer; acknowledged in preview)")


class ProposeUpdateHeadingInput(BaseModel):
    project_id: str = Field(..., min_length=1)
    heading_id_or_name: str = Field(..., min_length=1, description="UUID of the dummy heading task, or its current name")
    new_name: str = Field(..., min_length=1, max_length=200)


class ProposeDeleteHeadingInput(BaseModel):
    project_id: str = Field(..., min_length=1)
    heading_id_or_name: str = Field(..., min_length=1, description="UUID of the dummy heading task, or its name")


class ProposeCancelTodoInput(BaseModel):
    """V2 — propose canceling a to-do."""
    todo_id: str = Field(..., min_length=1)


class ProposeBulkCancelInput(BaseModel):
    """V2 — propose canceling N to-dos in one airlocked op."""
    todo_ids: list[str] = Field(..., min_length=1)


class ProposeCancelProjectInput(BaseModel):
    """V2 — propose canceling a project."""
    project_id: str = Field(..., min_length=1)


class ProposeDeleteProjectInput(BaseModel):
    """V2 step 5E — propose deleting a project via AppleScript."""
    project_id: str = Field(..., min_length=1)


class ProposeCreateAiTagInput(BaseModel):
    """V2 — propose creating an AI-managed tag.

    The name MUST be asterisk-wrapped: ``*Do Taxes*``. Server enforces
    this structural invariant. Parent defaults to the configured
    THINGS_MCP_AI_TAG_PARENT (default "AI").
    """
    name: str = Field(..., min_length=3)
    parent: str = Field(default="AI", min_length=1)

    @model_validator(mode="after")
    def _require_asterisk_wrapper(self) -> "ProposeCreateAiTagInput":
        if not (self.name.startswith("*") and self.name.endswith("*") and len(self.name) > 2):
            raise ValueError(
                f"AI tag name {self.name!r} must be asterisk-wrapped: e.g. '*Do Taxes*'. "
                "The asterisks are mandatory structural markers."
            )
        return self


class ProposeManageAiTagInput(BaseModel):
    """V2 — propose renaming and/or reparenting an AI tag.

    At least one of new_name / new_parent must be provided.
    """
    name: str = Field(..., min_length=1)
    new_name: str | None = Field(default=None)
    new_parent: str | None = Field(default=None)

    @model_validator(mode="after")
    def _require_at_least_one_change(self) -> "ProposeManageAiTagInput":
        if self.new_name is None and self.new_parent is None:
            raise ValueError(
                "propose_manage_ai_tag requires at least one of: new_name, new_parent."
            )
        if self.new_name is not None:
            if not (self.new_name.startswith("*") and self.new_name.endswith("*") and len(self.new_name) > 2):
                raise ValueError(
                    f"new_name {self.new_name!r} must be asterisk-wrapped: e.g. '*File Taxes*'."
                )
        return self


class ProposeDeleteAiTagInput(BaseModel):
    """V2 — propose deleting an AI tag (removes from ALL tasks).

    Always in NEVER_BYPASS_KINDS — explicit confirm required.
    """
    name: str = Field(..., min_length=1)


class AiTagRoutingInput(BaseModel):
    """Routing metadata for a single AI tag application."""
    dest_kind: str | None = Field(default=None)
    dest_uuid: str | None = Field(default=None)
    transient: bool = Field(default=False)


class AiTagItemInput(BaseModel):
    """Single item in an apply_ai_tags batch."""
    todo_uuid: str = Field(..., min_length=1)
    add_tags: list[str] = Field(..., min_length=1)
    routing: AiTagRoutingInput | None = Field(default=None)


class ProposeApplyAiTagsInput(BaseModel):
    """V2 — propose applying AI tags to one or more to-dos."""
    items: list[AiTagItemInput] = Field(..., min_length=1)
    group_id: str | None = Field(default=None)


class ProposeCleanupAiTagsInput(BaseModel):
    """V2 — propose cleaning up transient AI routing tags after a confirmed sort."""
    todo_uuids: list[str] = Field(..., min_length=1)
    group_id: str | None = Field(default=None)


class ProposeMoveUnderAiHeadingInput(BaseModel):
    """V2 — move to-dos into an existing project under the __NEWLY ADDED BY AI__ marker.

    Creates the marker if absent (idempotent — reuses it if already present).
    Reorders the project so pre-existing tasks appear above the marker and
    newly moved tasks appear below it. Safe to call multiple times for the
    same project; successive batches append under the marker.

    Requires ``THINGS_AUTH_TOKEN`` and ``THINGS_MCP_ALLOW_APPLESCRIPT=1``.
    """
    todo_ids: list[str] = Field(..., min_length=1)
    project_id: str = Field(..., min_length=1)
    group_id: str | None = Field(default=None)


class HealthReport(BaseModel):
    things_db_path: str
    things_db_exists: bool
    things_app_running: bool
    things_py_version: str
    state_db_path: str
    state_db_exists: bool
    url_scheme_auth_token_set: bool
    applescript_enabled: bool = False
    experimental_reorder_enabled: bool = False
    applescript_authorized: bool | str = "unknown"
    reorder_command_available: bool | None = None
