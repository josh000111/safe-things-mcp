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
    """V2 — propose soft-deleting a to-do (mark canceled + completed →
    moves to Logbook). Hard-delete (AppleScript) arrives in step 5.

    This kind is in ``NEVER_BYPASS_KINDS`` — even with
    ``THINGS_MCP_AUTO_CONFIRM=1`` the user must explicitly call
    ``confirm_action``.
    """
    todo_id: str = Field(..., min_length=1)


class HealthReport(BaseModel):
    things_db_path: str
    things_db_exists: bool
    things_app_running: bool
    things_py_version: str
    state_db_path: str
    state_db_exists: bool
    url_scheme_auth_token_set: bool
