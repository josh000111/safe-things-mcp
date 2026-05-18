"""Pydantic request/response models for tool inputs and outputs."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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


class HealthReport(BaseModel):
    things_db_path: str
    things_db_exists: bool
    things_app_running: bool
    things_py_version: str
    state_db_path: str
    state_db_exists: bool
    url_scheme_auth_token_set: bool
