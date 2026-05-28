# V2 Step 5A Verification — 2026-05-28

**Tester:** Test (verified via `whoami`)
**Commit:** `5c12704 feat(5A): AppleScript foundation + hard-delete todo`
**Automated suite at start:** 290 passed (290 expected per handoff)
**Automated suite at end:** 290 passed — no regressions

---

## Pre-flight

| Check | Result |
|---|---|
| `whoami` → `Test` | ✅ |
| `git status` → on `main`, up to date with `origin/main` | ✅ (`FETCH_HEAD` permission error is a shared-repo artifact, not a code issue) |
| `uv run pytest -q` → 290 passed | ✅ |
| Things 3 running | ✅ |

`THINGS_MCP_ALLOW_APPLESCRIPT` is **not** set in Claude Desktop's MCP env — tests for flag-on behaviour ran via pytest subprocess with the flag patched via `monkeypatch`, exactly as the existing unit tests do. Items 131/134 were exercised against the live MCP server (flag-off).

---

## Item 131 — Flag-off clean error ✅

**How run:** Live MCP call via `mcp__things-mcp__propose_hard_delete_todo(todo_id="00000000-0000-0000-0000-000000000001")`

**Result:**
```
Error: propose_hard_delete_todo requires THINGS_MCP_ALLOW_APPLESCRIPT=1.
Set the environment variable and restart the MCP server.
```

Error message names `THINGS_MCP_ALLOW_APPLESCRIPT` exactly as required. ✅

Follow-up `list_pending_actions()` → `{"result": []}` — no pending action was created. ✅

---

## Item 132 — Hard-delete execute ❌ BUG FOUND

**How run:** `tests/test_step5a_live.py::test_132_133_hard_delete_and_undo` (pytest, flag patched on, real osascript, real Things DB)

**Failing script:**
```applescript
tell application "Things3" to delete (todo id "M7DL2y19RuwYhCh2Lnu3GR")
```

**Error from osascript:**
```
43:45: syntax error: Expected "," but found property. (-2741)
```

**Root cause:** The Things 3 SDEF defines the class as `"to do"` (two words, code `tstk`), not `"todo"`. The single-word form is not a recognised AppleScript class alias and causes a parse error.

**Affected lines in `src/things_mcp/services/handlers/hard_delete_todo.py`:**

| Line | Current (broken) | Required fix |
|---|---|---|
| 80 | `to delete (todo id "{safe_id}")` | `to delete (to do id "{safe_id}")` |
| 127 | `to move (todo id "{safe_id}")` | `to move (to do id "{safe_id}")` |
| 136 | `to move (todo id "{safe_id}")` | `to move (to do id "{safe_id}")` |

Docstring references on lines 7 and 41 also say `todo id` but those are cosmetic.

**Manual smoke test confirming the fix works:**
```
$ osascript -e 'tell application "Things3"
    set t to make new to do with properties {name: "5A-syntax-canary"}
    set tid to id of t
    delete (to do id tid)
    return tid
end tell'
→ 9xxzzhQ4Lu88UdiGroTYf9   (exit 0)
```

Subsequent `to dos of list "Trash"` check confirmed the todo appeared in Things Trash — it was NOT permanently purged. ✅ (Answers the watchpoint: `delete` moves to Trash, does not purge.)

Stray test todos (`5A-HARDDELETE-*` and canary) were deleted via AppleScript before the session ended. Trash was checked — all test items landed there, none were permanently purged.

---

## Item 133 — Undo restores from Trash ⚠️ PARTIALLY VERIFIED

**Status:** Not exercised via the automated round-trip (blocked by Item 132's bug). However, the restore AppleScript syntax was manually smoke-tested:

```applescript
tell application "Things3"
    move (to do id "9xxzzhQ4Lu88UdiGroTYf9") to list "Inbox"
end tell
```

→ Exit 0. Follow-up check of `to dos of list "Inbox"` confirmed the todo returned. ✅

The undo handler logic (undo_log.delete, restored_to field) could not be exercised because execute() never completed. Once the `to do id` fix lands, `test_step5a_live.py::test_132_133_hard_delete_and_undo` exercises the full round-trip including undo_log cleanup.

---

## Item 134 — Flags off health() ✅

**How run:** Live MCP `mcp__things-mcp__health()` with `THINGS_MCP_ALLOW_APPLESCRIPT` unset.

**Response:**
```json
{
  "things_db_path": "…/ThingsData-2WYEQ/Things Database.thingsdatabase/main.sqlite",
  "things_db_exists": true,
  "things_app_running": true,
  "things_py_version": "1.0.1",
  "state_db_path": "/Users/Test/.things-mcp/state.db",
  "state_db_exists": true,
  "url_scheme_auth_token_set": true,
  "applescript_enabled": false,
  "experimental_reorder_enabled": false,
  "applescript_authorized": "unknown",
  "reorder_command_available": null
}
```

All flag-off fields match expected values:
- `applescript_enabled: false` ✅
- `experimental_reorder_enabled: false` ✅
- `reorder_command_available: null` (not `false`) ✅
- `applescript_authorized: "unknown"` ✅

---

## Item 135 — health() with flags on, after first AppleScript call ✅

**How run:** `tests/test_step5a_live.py::test_135_applescript_flag_on_health_before_call` and `test_135_applescript_authorized_flips_after_verify`

**Pre-call snapshot (flag patched on, no AppleScript yet triggered):**
- `applescript_enabled: true` ✅
- `experimental_reorder_enabled: false` ✅ (`THINGS_MCP_ALLOW_EXPERIMENTAL_REORDER` not set)
- `reorder_command_available: null` ✅ (correctly null when reorder flag is off)
- `applescript_authorized: "unknown"` ✅

**Post `verify_authorization()` call:**
- `applescript_authorized: true` ✅ (Automation permission is granted; Things 3 is in System Settings → Privacy & Security → Automation → Claude Desktop)

`verify_authorization()` returned `True` and the cache flipped on first call. ✅

**Note:** `hard_delete_todo.execute()` does NOT call `verify_authorization()` — it calls `run_script()` directly. So after a real `propose_hard_delete_todo` flow, `applescript_authorized` would remain `"unknown"` unless `verify_authorization()` is called somewhere else in the pipeline. The test explicitly calls `verify_authorization()` to exercise this path. Team should decide whether execute() should call verify_authorization() as a side effect or whether the docs/handoff should clarify the trigger.

---

## Pytest integration test file

`tests/test_step5a_live.py` was added during this session. It covers:
- `test_134_flags_off_health_fields` — fast unit-style check, no flag, no AppleScript ✅ passed
- `test_135_applescript_flag_on_health_before_call` — pre-call health snapshot ✅ passed
- `test_135_applescript_authorized_flips_after_verify` — auth cache flip via verify_authorization() ✅ passed
- `test_132_133_hard_delete_and_undo` — full round-trip ❌ blocked by `todo id` bug

Once the bug is fixed in the source, `test_132_133_hard_delete_and_undo` should pass without further changes.

---

## Summary

| Item | Result | Notes |
|---|---|---|
| 131 — Flag-off error | ✅ PASS | Error message correct; no pending action created |
| 132 — Hard-delete to Trash | ❌ BUG | `todo id` → `to do id` in execute() script (line 80) |
| 133 — Undo from Trash | ⚠️ PARTIAL | Move syntax confirmed correct via smoke test; full round-trip blocked by 132 |
| 134 — Flags-off health | ✅ PASS | All fields match expected |
| 135 — Flags-on health, auth flip | ✅ PASS | Both pre- and post-call assertions pass |

---

## Required fix before closing Step 5A

In `src/things_mcp/services/handlers/hard_delete_todo.py`, replace every occurrence of `todo id` with `to do id` in AppleScript string literals (lines 80, 127, 136). Then re-run `test_step5a_live.py` — all 4 tests should pass.

No mutations occurred on the `joshsmith` Things DB at any point. ✅

---

## No mutations on joshsmith DB

Confirmed: all operations targeted `Test` user's Things DB at
`/Users/Test/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/ThingsData-2WYEQ/`.
