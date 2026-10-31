"""Runtime configuration: paths, env, Things DB resolution."""
from __future__ import annotations

import glob
import os
from pathlib import Path

STATE_DIR = Path(os.environ.get("SAFE_THINGS_MCP_STATE_DIR", Path.home() / ".safe-things-mcp"))
STATE_DB_PATH = STATE_DIR / "state.db"

THINGS_GROUP_CONTAINER = Path(
    "~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac"
).expanduser()
THINGS_DB_GLOB = (
    "~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/"
    "ThingsData-*/Things Database.thingsdatabase/main.sqlite"
)
THINGS_DB_LEGACY_PATH = Path(
    "~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/"
    "Things Database.thingsdatabase/main.sqlite"
).expanduser()

# macOS silently denies the container (no popup) until the user flips a switch,
# so the generic sqlite "unable to open database file" is useless to them.
PERMISSION_GUIDANCE = (
    "macOS is blocking access to the Things database. Open System Settings > "
    "Privacy & Security > Files & Folders, find the app running this server "
    '("SafeThingsMCP" if you installed the Claude Desktop extension; otherwise '
    'your terminal, editor or the "claude" app) and turn on "Data shared by '
    'Things and affiliated apps". macOS never shows a popup for this, so that '
    "switch is the only way to allow it. No restart needed."
)
NOT_FOUND_GUIDANCE = (
    "Things 3 data was not found at "
    "~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac. "
    "Install Things 3 for Mac and open it at least once."
)


class ThingsDBAccessError(RuntimeError):
    """The Things database can't be reached; the message is user-facing guidance."""


def resolve_things_db_path() -> Path:
    # Resolved per call, not at import: a transient macOS permission denial at
    # startup would otherwise pin a dead fallback path for the process lifetime.
    override = os.environ.get("THINGS_DB_PATH")
    if override:
        return Path(override)
    match = next(glob.iglob(os.path.expanduser(THINGS_DB_GLOB)), None)
    return Path(match) if match else THINGS_DB_LEGACY_PATH


def things_db_access_problem() -> str | None:
    """Return None if the Things DB is readable, else user-facing guidance on why not."""
    override = os.environ.get("THINGS_DB_PATH")
    try:
        if not override:
            # Listing the container is what macOS denies first; it tells
            # "blocked" apart from "Things not installed".
            os.listdir(THINGS_GROUP_CONTAINER)
        path = resolve_things_db_path()
        open(path, "rb").close()
    except (FileNotFoundError, NotADirectoryError):
        if override:
            return f"THINGS_DB_PATH is set to {override} but no database was found there."
        return NOT_FOUND_GUIDANCE
    except PermissionError:
        if override:
            return f"Permission denied reading THINGS_DB_PATH ({override}). " + PERMISSION_GUIDANCE
        return PERMISSION_GUIDANCE
    except OSError as exc:
        return f"Could not open the Things database: {exc}"
    return None


def require_things_db_path() -> Path:
    """Return the Things DB path, or raise ThingsDBAccessError with actionable guidance."""
    path = resolve_things_db_path()
    try:
        # Open, not stat: macOS can allow stat yet deny reading, which would let
        # sqlite's unhelpful "unable to open database file" through.
        open(path, "rb").close()
        return path
    except OSError:
        pass  # fall through to diagnosis
    problem = things_db_access_problem()
    raise ThingsDBAccessError(problem or f"Things database not found at {path}")


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
