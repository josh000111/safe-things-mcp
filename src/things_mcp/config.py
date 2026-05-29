"""Runtime configuration: paths, env, Things DB resolution."""
from __future__ import annotations

import os
from pathlib import Path

import things

STATE_DIR = Path(os.environ.get("THINGS_MCP_STATE_DIR", Path.home() / ".things-mcp"))
STATE_DB_PATH = STATE_DIR / "state.db"

THINGS_DB_PATH = Path(
    os.environ.get("THINGS_DB_PATH", things.database.DEFAULT_FILEPATH)
)

THINGS_AUTH_TOKEN = os.environ.get("THINGS_AUTH_TOKEN")

# When set, ``propose_*`` tools immediately execute their action in the
# same call instead of enqueueing for a separate confirm round-trip. The
# preview is still returned (so the agent can summarise to the user).
# Destructive / multi-target kinds in NEVER_BYPASS_KINDS ignore this flag
# and ALWAYS require an explicit ``confirm_action(...)``.
AUTO_CONFIRM = os.environ.get("THINGS_MCP_AUTO_CONFIRM", "").strip().lower() in {
    "1", "true", "yes", "on",
}

# When set, AppleScript-backed operations (hard-delete, reorder) are enabled.
# Default off — requires explicit opt-in.
ALLOW_APPLESCRIPT = os.environ.get("THINGS_MCP_ALLOW_APPLESCRIPT", "").strip().lower() in {
    "1", "true", "yes", "on",
}

# When set, enables the experimental reorder command (requires ALLOW_APPLESCRIPT too).
# Default off.
ALLOW_EXPERIMENTAL_REORDER = os.environ.get(
    "THINGS_MCP_ALLOW_EXPERIMENTAL_REORDER", ""
).strip().lower() in {"1", "true", "yes", "on"}

# Action kinds that must NEVER auto-confirm, regardless of THINGS_MCP_AUTO_CONFIRM.
# Anything destructive or multi-target lives here. New kinds added in later
# chunks (chunk C delete, chunk E bulk_*) are pre-listed so the gate is in
# place when those handlers ship.
NEVER_BYPASS_KINDS: frozenset[str] = frozenset({
    "delete_todo",      # AppleScript hard-delete → Things Trash
    "delete_heading",
    "delete_project",   # AppleScript hard-delete → Things Trash
    "bulk_cancel",
    "bulk_complete",
    "bulk_move",
    "bulk_update",
})

WRITE_POLL_TIMEOUT_SECONDS = float(
    os.environ.get(
        "THINGS_MCP_WRITE_POLL_TIMEOUT",
        os.environ.get("THINGS_MCP_CALLBACK_TIMEOUT", "5"),
    )
)
WRITE_POLL_INTERVAL_SECONDS = float(
    os.environ.get("THINGS_MCP_WRITE_POLL_INTERVAL", "0.1")
)

PENDING_TTL_SECONDS = 5 * 60
UNDO_LOG_MAX_ROWS = 200
UNDO_LOG_MAX_AGE_DAYS = 30


def ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
