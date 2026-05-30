"""Meta/diagnostic tools."""
from __future__ import annotations

import subprocess
from importlib.metadata import PackageNotFoundError, version
from typing import Optional

from mcp.server.fastmcp import FastMCP

from ..config import (
    ALLOW_APPLESCRIPT,
    STATE_DB_PATH,
    THINGS_AUTH_TOKEN,
    THINGS_DB_PATH,
)
from ..models import HealthReport
from ..state import undo_log

# Cached result of the SDEF grep for the reorder command.
# None = not yet checked; True/False = result.
_REORDER_CMD_CACHED: Optional[bool] = None


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

        return HealthReport(
            things_db_path=str(THINGS_DB_PATH),
            things_db_exists=THINGS_DB_PATH.exists(),
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

    @mcp.tool()
    def recent_undo_log(limit: int = 20) -> list[dict]:
        """The last N reversible actions."""
        return undo_log.recent(limit=limit)
