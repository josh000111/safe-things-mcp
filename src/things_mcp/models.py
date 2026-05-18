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
