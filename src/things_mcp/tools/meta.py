"""Meta/diagnostic tools."""
from __future__ import annotations

import subprocess
from importlib.metadata import PackageNotFoundError, version

from mcp.server.fastmcp import FastMCP

from ..config import STATE_DB_PATH, THINGS_AUTH_TOKEN, THINGS_DB_PATH
from ..models import HealthReport
from ..state import undo_log


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


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def health() -> dict:
        """Diagnostics: DB paths, Things app status, package versions."""
        return HealthReport(
            things_db_path=str(THINGS_DB_PATH),
            things_db_exists=THINGS_DB_PATH.exists(),
            things_app_running=_things_app_running(),
            things_py_version=_things_py_version(),
            state_db_path=str(STATE_DB_PATH),
            state_db_exists=STATE_DB_PATH.exists(),
            url_scheme_auth_token_set=bool(THINGS_AUTH_TOKEN),
        ).model_dump()

    @mcp.tool()
    def recent_undo_log(limit: int = 20) -> list[dict]:
        """The last N reversible actions. Empty in V1 (no destructive ops yet)."""
        return undo_log.recent(limit=limit)
