"""Meta/diagnostic tools."""
from __future__ import annotations

import subprocess
import uuid
from importlib.metadata import PackageNotFoundError, version
from typing import Optional

from mcp.server.fastmcp import FastMCP

from ..config import (
    AI_TAG_PARENT,
    ALLOW_APPLESCRIPT,
    STATE_DB_PATH,
    THINGS_AUTH_TOKEN,
    resolve_things_db_path,
    things_db_access_problem,
)
from ..models import HealthReport
from ..services import things_repo
from ..state import undo_log

# The 5 canonical AI flag tags that must exist for the sort workflow.
_AI_FLAG_TAGS: tuple[str, ...] = (
    "*Unclear*",
    "*Ambiguous Home*",
    "*Duplicate?*",
    "*No Time Signal*",
    "*Review Delete?*",
)

# Cached result of the SDEF grep for the reorder command.
# None = not yet checked; True/False = result.
_REORDER_CMD_CACHED: Optional[bool] = None

# Static help content — returned by help_docs() so any MCP client (including
# Claude Desktop, which has no filesystem access) can query the vocabulary.
_HELP_DOCS: dict = {
    "flag_tags": {
        "*Unclear*": "Catch-all abstain tag — no clean category or plausible destination found.",
        "*Ambiguous Home*": "Two or more projects/areas compete equally for this task.",
        "*Duplicate?*": "Suspected near-duplicate of an existing task; needs human review.",
        "*No Time Signal*": "Scheduling was requested but no date/duration evidence exists in the title or notes.",
        "*Review Delete?*": "Task was a bulk-delete candidate but membership in the delete set is uncertain.",
    },
    "propose_confirm_flow": (
        "propose_* tools stage an action for review; call confirm_action(action_id) to execute. "
        "Set SAFE_THINGS_MCP_AUTO_CONFIRM=1 to skip the confirm step for non-destructive operations."
    ),
    "undo_usage": {
        "undo_single": "undo() reverses the most recent action; undo(undo_id=X) targets a specific entry.",
        "undo_group": "undo_group(group_id) reverses a whole multi-step sort in LIFO order atomically.",
    },
    "features": {
        "sort_workflow": "Inbox/list sort: tag-first → review → move → cleanup. Always uses a shared group_id.",
        "ai_tags": "Asterisk-wrapped tags (*Name*) filed under the AI parent; created via propose_create_ai_tag.",
        "plain_tags": "User-named tags (no asterisks) created via propose_create_tag.",
        "ensure_ai_tags": "Bootstrap: idempotently creates AI parent + 5 flag tags; whole run undoable via undo_group.",
        "area_placement": "Pass area='Name' or area_id=UUID to propose_add_project; never construct raw URLs.",
        "reorder_guard": "Pre-existing tasks above __NEWLY ADDED BY AI__ marker are never reordered unless allow_existing_reorder=true.",
    },
}


def _things_py_version() -> str:
    for name in ("things.py", "things-py", "things"):
        try:
            return version(name)
        except PackageNotFoundError:
            continue
    return "unknown"


def _things_app_running() -> bool:
    try:
        result = subprocess.run(
            ["pgrep", "-x", "Things3"],
            capture_output=True,
            timeout=2,
        )
        return result.returncode == 0
    except Exception:
        return False


def _reorder_command_available() -> bool:
    """Grep the Things 3 SDEF for the reorder command code. Cached."""
    global _REORDER_CMD_CACHED
    if _REORDER_CMD_CACHED is not None:
        return _REORDER_CMD_CACHED
    try:
        result = subprocess.run(
            ["sdef", "/Applications/Things3.app"],
            capture_output=True,
            timeout=10,
        )
        _REORDER_CMD_CACHED = b"THGSreot" in result.stdout
    except Exception:
        _REORDER_CMD_CACHED = False
    return _REORDER_CMD_CACHED


def _applescript_authorized() -> bool | str:
    """Return the cached AppleScript authorization result.

    Returns 'unknown' if verify_authorization() has never been called.
    Does NOT trigger a live check -- health() is a read-only diagnostic.
    """
    from ..services.applescript import _AUTH_CACHED
    if _AUTH_CACHED is None:
        return "unknown"
    return _AUTH_CACHED


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def health() -> dict:
        """Diagnostics: DB paths, Things app status, package versions, AppleScript flags."""
        reorder_available: bool | None = None
        if ALLOW_APPLESCRIPT:
            reorder_available = _reorder_command_available()

        db_path = resolve_things_db_path()
        try:
            db_exists = db_path.exists()
        except OSError:
            db_exists = False  # EPERM under macOS denial must not crash health()
        report = HealthReport(
            things_db_path=str(db_path),
            things_db_exists=db_exists,
            things_app_running=_things_app_running(),
            things_py_version=_things_py_version(),
            state_db_path=str(STATE_DB_PATH),
            state_db_exists=STATE_DB_PATH.exists(),
            url_scheme_auth_token_set=bool(THINGS_AUTH_TOKEN),
            applescript_enabled=ALLOW_APPLESCRIPT,
            experimental_reorder_enabled=ALLOW_APPLESCRIPT,
            applescript_authorized=_applescript_authorized(),
            reorder_command_available=reorder_available,
        ).model_dump()
        # Added outside HealthReport so the model's existing fields stay untouched.
        report["things_db_access"] = things_db_access_problem() or "ok"
        return report

    @mcp.tool()
    def recent_undo_log(limit: int = 20) -> list[dict]:
        """The last N reversible actions."""
        return undo_log.recent(limit=limit)

    @mcp.tool()
    async def ensure_ai_tags() -> dict:
        """Idempotently create the AI parent tag and the 5 canonical flag tags.

        Creates the ``AI`` parent tag (controlled by
        ``SAFE_THINGS_MCP_AI_TAG_PARENT``) and the five persistent abstain tags —
        ``*Unclear*``, ``*Ambiguous Home*``, ``*Duplicate?*``,
        ``*No Time Signal*``, ``*Review Delete?*`` — if any are missing.

        Tags that already exist are skipped (no-op for those). All newly
        created tags share a single ``group_id`` so the entire bootstrap is
        undoable via ``undo_group(group_id)``.

        Returns a dict with:
        - ``group_id``: shared UUID for this bootstrap run (or ``null`` if
          nothing was created)
        - ``created``: list of tag names that were created
        - ``already_present``: list of tag names that already existed

        Requires ``SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1``.
        """
        from .. import config as _config
        if not _config.ALLOW_APPLESCRIPT:
            raise RuntimeError(
                "ensure_ai_tags requires SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1. "
                "Set the environment variable and restart the MCP server."
            )

        from ..services.handlers import create_ai_tag as _create_ai_tag_handler
        from ..services.handlers import create_tag as _create_tag_handler

        group_id = str(uuid.uuid4())
        created: list[str] = []
        already_present: list[str] = []

        # Ensure the AI parent tag (plain, no asterisks) using create_tag handler
        parent = AI_TAG_PARENT
        result = await _create_tag_handler.execute({"name": parent, "parent": None, "group_id": group_id})
        if "no-op" in result.get("note", ""):
            already_present.append(parent)
        else:
            created.append(parent)

        # Ensure each asterisk-wrapped flag tag using create_ai_tag handler
        for flag in _AI_FLAG_TAGS:
            result = await _create_ai_tag_handler.execute(
                {"name": flag, "parent": parent, "group_id": group_id}
            )
            if "no-op" in result.get("note", ""):
                already_present.append(flag)
            else:
                created.append(flag)

        return {
            "group_id": group_id if created else None,
            "created": created,
            "already_present": already_present,
        }

    @mcp.tool()
    def help_docs() -> dict:
        """Return the AI tag vocabulary, propose/confirm flow, undo usage, and feature index.

        Useful in any MCP client (including Claude Desktop, which has no
        filesystem access) to look up what flag tags mean, how the
        propose/confirm flow works, or what tools are available.

        Returns a dict with:
        - ``flag_tags``: mapping of each flag tag name → plain-English meaning
        - ``propose_confirm_flow``: one-line description of the two-step flow
        - ``undo_usage``: short descriptions of undo() and undo_group()
        - ``features``: one-line pointer per major feature
        """
        return _HELP_DOCS
