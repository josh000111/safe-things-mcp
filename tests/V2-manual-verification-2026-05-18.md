# V2 Manual Verification — 2026-05-18

**Tester:** Josh Smith (human) + Claude Code (guide)
**Account:** Test (macOS)
**Branch:** main
**Automated suite:** 67 passed ✓

---

## Phase 0 — Safety Preflight

| Check | Result | Notes |
|---|---|---|
| `whoami` → `Test` | PASS | |
| Things 3 running | PASS | `things_app_running: true` from `health()` |
| Codebase reachable | PASS | pyproject.toml, src/, tests/, docs/ all present |
| `uv run pytest -q` → 67 passed | PASS | 1 harmless permission warning on pytest cache dir |
| `uv run things-mcp --help` → exit 0 | PASS | |
| `health()` fields | PASS | `things_db_exists: true`, `things_app_running: true`, `things_py_version: 1.0.1`, `state_db_exists: true` |
| Claude Desktop config | DONE | Added `mcpServers.things-mcp` entry pointing to `uv run --directory /Users/Shared/things-mcp things-mcp` |

**Action required before Phase 1:** Restart Claude Desktop to pick up the new MCP server config.

---

## Phase 1 — V2 Manual Verification (Steps 1–3)

### Item 13 — Propose → confirm to Inbox
- **Status:** PASS ✓
- **Result:** Task "V2 inbox test" (id: `2itNgbWpem1PRtyBiQaqmd`) appeared in Things Inbox within ~1s. `recent_undo_log()` shows `add_todo` row with matching `target_uuid`. Confirmed visually by Josh.

### Item 14 — Propose → confirm to Today
- **Status:** PASS ✓ (after subprocess restart)
- **Root cause:** `build_add_url_v2` used `list=today`; Things URL scheme only accepts project/area names for `list=`. Built-in scheduling targets require `when=today`. Fix applied to `src/things_mcp/services/url_scheme.py`. Required Claude Desktop restart to reload subprocess.
- **Result:** Task "V2 today test" (id: `UNvoeBcrg4AzVNQW7aN26N`) confirmed in Things Today view. DB shows `start: "Anytime"`, `start_date: "2026-05-18"` ✓

### Item 15 — Propose → confirm to Anytime / Someday
- **Status:** PASS ✓
- **Result:** "V2 anytime test" (id: `PqweKa4xTnG77hZoiKRG7Q`) confirmed in Anytime — `start: "Anytime"`, `start_date: null`. "V2 someday test" (id: `Gjm5bfnnLaLH9HZRt8KtC`) confirmed in Someday — `start: "Someday"`, `start_date: null`. Both confirmed visually by Josh.
- **Note — Upcoming not tested:** `when=upcoming` is not a valid Things URL scheme value. Upcoming tasks require a specific future date (e.g. `when=2026-05-25`). `list_id='upcoming'` currently falls through to `list-id=upcoming` (wrong). Flagged as a follow-up gap — not blocking the must-run gate.

### Item 16 — Propose → confirm to a real project
- **Status:** PASS ✓
- **Result:** Task "V2 project test" (id: `KQZZHkiKb9dj1AKQoFvkSf`) landed inside project "Prep Repo or FL" (UUID: `Vr3ovatWZjNUitmkqTX76p`, area: "Development"). Confirmed visually by Josh.

### Item 21 — Undo round-trip
- **Status:** PASS ✓ (V2 acceptance gate cleared)
- **Result:** Task "V2 undo test" (id: `Grss3fbtcu2gSrNwfERgRG`) created in Inbox. `undo()` called with no args → `{undone: true, status: "canceled"}`. Task confirmed in Logbook (`stop_date: "2026-05-18 17:56:53"`, `status: "canceled"`). Undo log entry deleted on completion. `THINGS_AUTH_TOKEN` set via claude_desktop_config.json env block.

### Item 28 — Pre-mutation breadcrumb
- **Status:** MODIFIED PASS ✓ (code ordering verified; crash scenario unreproducible via quit)
- **Result:** Proposed "V2 crash test", user quit Things, then confirm_action was called. Instead of timing out, macOS's `open` command automatically relaunched Things to handle the `things:///add` URL — the task was created successfully (id: `AxWVKWKe71ZzQ9VWHgWczx`). Undo log shows proper `target_uuid`, not null.
- **Code ordering confirmed:** `undo_log.record()` (line 62) is called before `url_scheme.launch()` (line 80) in `add_todo.py` — the breadcrumb always precedes the mutation. The `target_uuid: null` scenario would occur only if the poll times out after launch (e.g. Things crashes between URL receipt and SQLite write), which is a narrower failure window than the quit test can reproduce.
- **macOS behavior note:** `open things:///...` always relaunches the app if quit. A true crash simulation would require killing the Things process mid-write, which is outside the scope of this checklist.

---

## Summary

**Date/time:** 2026-05-18, ~14:00–18:10 UTC  
**Tester:** Josh Smith (human) + Claude Code (guide), Test macOS account  
**Automated suite:** 68 passed (1 new test added during session)

| Item | Status | Notes |
|---|---|---|
| 13 — Propose → confirm to Inbox | **PASS** ✓ | |
| 14 — Propose → confirm to Today | **PASS** ✓ | Bug found and fixed (see code changes below) |
| 15 — Propose → confirm to Anytime / Someday | **PASS** ✓ | Upcoming not tested — see note |
| 16 — Propose → confirm to project UUID | **PASS** ✓ | Project: "Prep Repo or FL" |
| 21 — Undo round-trip | **PASS** ✓ | V2 acceptance gate cleared |
| 28 — Pre-mutation breadcrumb | **MODIFIED PASS** ✓ | Code ordering verified; crash scenario unreproducible via macOS `open` relaunch |

**Overall: READY FOR STEP 4** ✓

### Unexpected behaviour
- macOS `open` command automatically relaunches Things when a `things:///` URL is fired, even if Things was quit. This makes the Item 28 quit-based crash scenario unreproducible in practice. Not a code bug — a macOS platform behaviour.
- `list_id='upcoming'` currently falls through to `list-id=upcoming` (wrong). Flagged as a follow-up gap (spawned as a separate task).

### Code changes made during this session

**Bug: `build_add_url_v2` used wrong Things URL parameter for built-in lists**
- **File:** `src/things_mcp/services/url_scheme.py`
- **Change:** `today`/`anytime`/`someday` now emit `when=<value>`; `inbox` emits no extra param (Things default); project/area UUIDs use `list-id=`. Explicit `when` arg overrides list_id routing to avoid duplicate `when` params.
- **Tests updated:** `tests/test_url_scheme_v2.py` — updated 3 tests, added 1 (`test_add_v2_anytime_no_explicit_when`). `tests/test_handler_add_todo.py` — updated 1 assertion.
- **Suite:** 68 passed ✓

---

## Code changes made during this session

### Bug: `build_add_url_v2` used wrong Things URL parameter for built-in lists
- **File:** `src/things_mcp/services/url_scheme.py`
- **Change:** `today`/`anytime`/`someday` now emit `when=<value>`; `inbox` emits no extra param (Things default); project/area UUIDs use `list-id=`. Explicit `when` arg overrides list_id routing to avoid duplicate `when` params.
- **Tests:** `tests/test_url_scheme_v2.py` — updated 3 tests, added 1 new test (`test_add_v2_anytime_no_explicit_when`). `tests/test_handler_add_todo.py` — updated 1 assertion. Suite: 68 passed.
