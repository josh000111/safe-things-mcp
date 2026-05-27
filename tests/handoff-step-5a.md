# Handoff: V2 Step 5A manual verification — AppleScript foundation + hard-delete

## Context

Working directory: `/Users/Shared/things-mcp`
Account: **Test** (verify with `whoami` before any writes — must print `Test`)

This is the live-app verification round for V2 Step 5A. Step 5A adds the
opt-in AppleScript execution layer and the `propose_hard_delete_todo` tool.

What landed this build session (on `main`):

- **`src/things_mcp/services/applescript.py`** (new) — Async `osascript`
  wrapper with hardened escaping (`"` → `\"`, `\` → `\\`; control chars
  rejected with `ValueError`). Includes `verify_authorization()` (runs a
  no-op AppleScript once and caches the result).
- **`src/things_mcp/config.py`** — Two new env flags:
  `THINGS_MCP_ALLOW_APPLESCRIPT` and `THINGS_MCP_ALLOW_EXPERIMENTAL_REORDER`.
  `"hard_delete_todo"` added to `NEVER_BYPASS_KINDS`.
- **`src/things_mcp/services/handlers/hard_delete_todo.py`** (new) — Handler
  following the V2 pattern. Execute: AppleScript `delete (todo id "X")`.
  Undo: AppleScript `move (todo id "X") to list "..."` (or project). The
  `undo_log` row is written BEFORE the AppleScript call (V2 acceptance gate).
- **`src/things_mcp/tools/propose.py`** — New `propose_hard_delete_todo(todo_id)`
  tool, registered with FastMCP.
- **`src/things_mcp/tools/meta.py`** — `health()` now reports 4 new fields:
  `applescript_enabled`, `experimental_reorder_enabled`, `applescript_authorized`,
  `reorder_command_available`.

Automated suite: **290 passing** at handoff (was 246 before Step 5A; 44 new
tests added for the AppleScript wrapper and hard-delete handler).

---

## Required pre-flight

1. `whoami` → must print `Test`.
2. `git pull origin main` to grab the build commit.
3. Set `THINGS_MCP_ALLOW_APPLESCRIPT=1` in Claude Desktop's MCP server config.
   Do NOT set `THINGS_MCP_ALLOW_EXPERIMENTAL_REORDER` — that's for Step 5B.
4. Restart Claude Desktop to reload the MCP server.
5. `health()` must return:
   - `things_app_running: true`
   - `state_db_exists: true`
   - `applescript_enabled: true`
   - `experimental_reorder_enabled: false`
   - `applescript_authorized: "unknown"` (not yet triggered)
   - `reorder_command_available: null`

---

## What to run

Walk items **131 through 135** in `tests/things-mcp-manual-verification.md`,
in order. As you go:

- Record each outcome (✅ / ⚠️ / ❌) and any surprises.
- Name the results doc `tests/V2-step-5a-verification-<YYYY-MM-DD>.md`.
- If a write doesn't land as expected within ~3s, note the exact script that
  was sent (visible in the response) before retrying.

The checklist groups:

- **131** — Flag-off clean error (no Things writes, no pending action).
- **132** — Hard-delete execute: task moves to Things Trash.
- **133** — Undo: task restored from Trash to original list.
- **134** — `health()` with flags off.
- **135** — `health()` with flags on after first AppleScript call.

---

## Specific things to watch closely

- **Item 132 (hard-delete in Trash)** — Things Trash is visible in the sidebar
  under the "Trash" smart list. The task must appear there by name immediately
  after `confirm_action`. If it disappears entirely (not in Trash) that suggests
  the SDEF `delete` command purges immediately — note that and the team will
  decide whether to fall back to an alternative approach.
- **Item 133 (undo restore)** — Undo uses AppleScript `move`. The task should
  reappear in the Inbox. If it goes to a different list (e.g. Today), that would
  indicate Things interprets the original `list` field differently — note the
  actual destination.
- **Item 134 (flag-off health)** — `reorder_command_available` should be `null`
  or absent (not `false`). If it's computed even when the flag is off, that's a
  bug to flag.
- **Item 135 (authorized after first call)** — `applescript_authorized` starts
  as `"unknown"`. After any AppleScript tool runs (even a failed proposal), it
  should flip to `true` if macOS Automation permission is granted. If it stays
  `"unknown"`, the `verify_authorization()` path was not triggered — check
  whether Things is in the Automation permission list in System Settings →
  Privacy & Security → Automation → Claude Desktop.

---

## Acceptance criteria for closing Step 5A verification

- All items 131–135 walked, every result recorded.
- Item 132 confirmed: task appears in Things Trash after `confirm_action`.
- Item 133 confirmed: task returns to original list after `undo()`.
- No mutations on the real `joshsmith` Things DB at any point.
- No new automated test failures (`uv run pytest` still green on Test machine).

When the round closes:

1. Push the results doc to `main`.
2. Update §0 of `docs/things-mcp-V2-technical-architecture-and-implementation-plan.md`
   — flip Step 5A from "awaiting manual verification" to "manually verified".
3. Hand off to Step 5C (checklist tools) or Step 5B (reorder) per the agreed
   sequence.

---

## If something looks wrong

- Don't keep mutating. Run `cancel_action(action_id)` if a proposal has not
  been confirmed yet, or call `undo()` if it has.
- For AppleScript failures, the error message from `osascript` is surfaced
  directly in the `RuntimeError`. Common causes:
  - Automation permission not granted → System Settings → Privacy & Security
    → Automation → enable Claude Desktop → Things 3.
  - Things not running → launch Things 3 first.
- For undo-log shape questions, call `recent_undo_log(limit=5)` and paste
  the JSON into the results doc.

The build session is happy to take a follow-up handoff if any item needs a
code-side fix — same shape as `tests/handoff-items-56-57.md`.
