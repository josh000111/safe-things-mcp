"""Runtime configuration: paths, env, Things DB resolution."""
from __future__ import annotations

import glob
import os
from pathlib import Path

STATE_DIR = Path(os.environ.get("SAFE_THINGS_MCP_STATE_DIR", Path.home() / ".safe-things-mcp"))
STATE_DB_PATH = STATE_DIR / "state.db"

THINGS_DB_GLOB = (
    "~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/"
    "ThingsData-*/Things Database.thingsdatabase/main.sqlite"
)
THINGS_DB_LEGACY_PATH = Path(
    "~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/"
    "Things Database.thingsdatabase/main.sqlite"
).expanduser()


def resolve_things_db_path() -> Path:
    # Resolved per call, not at import: a transient macOS permission denial at
    # startup would otherwise pin a dead fallback path for the process lifetime.
    override = os.environ.get("THINGS_DB_PATH")
    if override:
        return Path(override)
    match = next(glob.iglob(os.path.expanduser(THINGS_DB_GLOB)), None)
    return Path(match) if match else THINGS_DB_LEGACY_PATH


THINGS_AUTH_TOKEN = os.environ.get("THINGS_AUTH_TOKEN")

# When set, ``propose_*`` tools immediately execute their action in the
# same call instead of enqueueing for a separate confirm round-trip. The
# preview is still returned (so the agent can summarise to the user).
# Destructive / multi-target kinds in NEVER_BYPASS_KINDS ignore this flag
# and ALWAYS require an explicit ``confirm_action(...)``.
AUTO_CONFIRM = os.environ.get("SAFE_THINGS_MCP_AUTO_CONFIRM", "").strip().lower() in {
    "1", "true", "yes", "on",
}

# When set, AppleScript-backed operations (delete to Trash, reorder) are enabled.
# Default off — requires explicit opt-in.
ALLOW_APPLESCRIPT = os.environ.get("SAFE_THINGS_MCP_ALLOW_APPLESCRIPT", "").strip().lower() in {
    "1", "true", "yes", "on",
}

# Action kinds that must NEVER auto-confirm, regardless of SAFE_THINGS_MCP_AUTO_CONFIRM.
# Anything destructive or multi-target lives here. New kinds added in later
# chunks (chunk C delete, chunk E bulk_*) are pre-listed so the gate is in
# place when those handlers ship.
NEVER_BYPASS_KINDS: frozenset[str] = frozenset({
    # Single-item deletes (delete_todo, delete_heading) intentionally omitted:
    # they respect AUTO_CONFIRM=1 because deletes go to Trash (reversible via
    # undo()) and the user has expressed clear intent when naming the item.
    "delete_project",      # AppleScript delete → Trash, cascades to all tasks — always confirm
    "bulk_cancel",
    "bulk_complete",
    "bulk_delete_todo",    # multi-target AppleScript delete → Trash
    "bulk_delete_heading", # multi-target soft-delete
    "bulk_move",
    "bulk_update",
    "replace_checklist",  # destructive overwrite of entire checklist
    "delete_ai_tag",    # removes tag from ALL tasks — must always confirm
    "move_under_ai_heading",  # bulk move + reorder — must always confirm
})

WRITE_POLL_TIMEOUT_SECONDS = float(
    os.environ.get(
        "SAFE_THINGS_MCP_WRITE_POLL_TIMEOUT",
        os.environ.get("SAFE_THINGS_MCP_CALLBACK_TIMEOUT", "5"),
    )
)
WRITE_POLL_INTERVAL_SECONDS = float(
    os.environ.get("SAFE_THINGS_MCP_WRITE_POLL_INTERVAL", "0.1")
)

PENDING_TTL_SECONDS = 5 * 60
UNDO_LOG_MAX_ROWS = int(os.environ.get("SAFE_THINGS_MCP_UNDO_MAX_ROWS", "200"))
UNDO_LOG_MAX_AGE_DAYS = int(os.environ.get("SAFE_THINGS_MCP_UNDO_MAX_AGE_DAYS", "7"))

AI_TAG_PARENT = os.environ.get("SAFE_THINGS_MCP_AI_TAG_PARENT", "AI")


def ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
