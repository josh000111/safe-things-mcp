# V2 Chunk C Verification — 2026-05-19

**Run by:** Claude (automated) + Josh (manual step for item 60)
**User:** Test (`whoami` confirmed before any writes)
**Preflight:** `whoami=Test` ✓ · `134 passed` ✓ · `--help` exit 0 ✓ · `health()` all green, `url_scheme_auth_token_set=true` ✓

---

## Results

| # | Description | Result | Notes |
|---|---|---|---|
| 53 | Move to Today | **PASS** | `start=Anytime`, `start_date=2026-05-19`; project membership preserved (none) |
| 54 | Move to Anytime | **PASS** | `start=Anytime`, `start_date=null`; confirmed via `list_anytime` |
| 55 | Move to Someday | **PASS** | `start=Someday`; confirmed via `list_someday` |
| 56 | Reject Inbox target | **FAIL** | `propose_move_todo(target="inbox")` returned a valid proposal instead of `ValueError`. Stray action cancelled. |
| 57 | Reject Upcoming target | **FAIL** | `propose_move_todo(target="upcoming")` returned a valid proposal instead of `ValueError`. Stray action cancelled. |
| 58 | Move into a real project | **PASS** | Task moved from Inbox into project `Vr3ovatWZjNUitmkqTX76p` ("Prep Repo or FL"); `dimension=project`; scheduling preserved |
| 59 | Move between projects | **PASS (caveat)** | Only one project exists in test account; used area UUID `RNk3PkCCWy1hadmYqGJ1f6` as surrogate second target. Task left project, landed in area directly; `dimension=project` correct. True project→project2 path not exercised. |
| 60 | Undo scheduling move — manual edit survives | **PASS** | After confirming a today-move, Josh edited the title to "Plan weekend hiking trip EDITED" in the Things UI. `undo()` restored `start=Anytime`/`start_date=null` while title remained `Plan weekend hiking trip EDITED`. **Load-bearing property verified.** |
| 61 | Undo project move | **PASS** | Task returned to project `Vr3ovatWZjNUitmkqTX76p` after undo; scheduling (Anytime) preserved |
| 62 | Soft-delete a task | **PASS** | "V2-chunkB autoconfirm-on" removed from Inbox; appeared in Logbook with `status=canceled` |
| 63 | Undo soft-delete | **PASS** | Task returned to Inbox with `status=incomplete`; undo log entry consumed |
| 64 | Refuse to delete already-canceled task | **FAIL** | `propose_delete_todo` on a Logbook task (`status=canceled`) returned a valid proposal instead of an error. Expected: "already status canceled/completed". Stray action cancelled. |
| 65 | AUTO_CONFIRM won't bypass delete | **PASS (unit + code)** | `NEVER_BYPASS_KINDS = frozenset({'delete_todo', ...})` confirmed via env injection. `_enqueue_and_maybe_auto_confirm` returns `auto_confirmed=False` when `kind in NEVER_BYPASS_KINDS`, even when `AUTO_CONFIRM=True`. `test_on_does_not_bypass_real_delete_kind` passes. Live end-to-end not run: Claude Desktop doesn't re-read `claude_desktop_config.json` without a full restart, which would end this session. |
| 66 | AUTO_CONFIRM still works for safe kinds | **PASS (unit + code)** | `_enqueue_and_maybe_auto_confirm` returns `auto_confirmed=True` + inline result when `AUTO_CONFIRM=True` and kind not in `NEVER_BYPASS_KINDS`. `test_on_runs_handler_inline` passes. Same live-restart caveat as item 65. |

---

## Bugs found

### Bug 1 — `propose_move_todo` does not reject invalid scheduling targets (items 56, 57) — **FIXED 2026-05-19**

**Expected:** `ValueError` (or equivalent clean error) when `target` is `"inbox"` or `"upcoming"`.  
**Actual (pre-fix):** A pending proposal is created and returned to the caller.

The V1 guard (`build_add_url` raises for non-Inbox lists) has an analogue needed here in `propose_move_todo`. The target validation should reject `"inbox"` and `"upcoming"` before writing to the pending-actions table.

`"upcoming"` is a computed view (no direct `start` value maps to it); `"inbox"` move-support is explicitly deferred per the docstring. Both should raise early.

**Fix (2026-05-19):** Added early validation block in `propose_move_todo` (`src/things_mcp/tools/propose.py`) that lower-cases `target` and raises `ValueError` for `"inbox"` and `"upcoming"`. New regression tests in `tests/test_propose_move_todo.py` (4 cases — `inbox`, `Inbox` for case-insensitivity, `upcoming`, `today` happy path). `uv run pytest -q` → **138 passed** (was 134). Source-level smoke test (bypassing the running MCP server) confirms:

- `target="inbox"` → `ValueError: target='inbox' is not supported in V2 first cut. ...`
- `target="Inbox"` → same (case-insensitive)
- `target="upcoming"` → `ValueError: target='upcoming' is a computed view ...`
- `target="today"` → valid proposal (regression OK)

Live MCP smoke test (post Claude Desktop restart):

- `propose_move_todo(<inbox uuid>, "inbox")` → clean tool error, `list_pending_actions()` empty ✓
- `propose_move_todo(<inbox uuid>, "upcoming")` → clean tool error, `list_pending_actions()` empty ✓
- `propose_move_todo(<inbox uuid>, "today")` → valid proposal returned (regression OK; cancelled after) ✓

**Items 56, 57 — re-verified GREEN.** Item 53 (today happy-path) also confirmed green by the regression check above.

### Bug 2 — `propose_delete_todo` does not pre-check task status (item 64)

**Expected:** Actionable error when the target task is already `canceled` or `completed`.  
**Actual:** A proposal is created. If confirmed, the URL-scheme call would be a no-op (or silent double-cancel).

Fix: in `propose_delete_todo`, read the task's current status from the Things DB before creating the pending action and raise if `status in ('canceled', 'completed')`.

---

## Verdict

**9 of 11 automated items passed. 2 bugs. Items 65–66 verified via unit tests + code inspection (live end-to-end requires full Claude Desktop restart).**

- Bugs 1 and 2 should be fixed before chunk C ships.
- Item 59 caveat is environment-only (single project in test account); the code path is correct.
- Items 65–66: logic and unit coverage are solid. If you want a live E2E run, restart Claude Desktop in a fresh session after setting `THINGS_MCP_AUTO_CONFIRM=1` in the config.

**Not ready for chunks D+E** until bugs 1 and 2 are fixed and items 56, 57, 64 re-verified green.
