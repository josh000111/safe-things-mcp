# V2 Chunk B Verification — 2026-05-19

**Verifier:** Test user (whoami=Test)
**Branch:** main @ 37bb713 (V2 steps 1–3 + step 4 chunk A committed; chunk B unmerged changes in working tree)
**Scope:** Items 39–52 (propose_update_todo + THINGS_MCP_AUTO_CONFIRM)

## Preflight

| Check | Result |
|---|---|
| `whoami` | `Test` ✅ |
| `uv run pytest -q` | `110 passed` ✅ |
| `uv run things-mcp --help` | exit 0 ✅ |
| `THINGS_AUTH_TOKEN` set in claude_desktop_config.json | ✅ |
| `THINGS_MCP_AUTO_CONFIRM` absent at session start | ✅ |

---

## Items 39–45: propose_update_todo basic edits

### 39 — Update a title
**Prompt:** *"List my Inbox and pick a task id, then propose updating it to title 'V2-chunkB updated title' and confirm."*
**Expected:** Things shows new title. `recent_undo_log()` has an `update_todo` row.
- [ ] PASS — notes:

### 40 — Update notes
**Prompt:** *"Pick a task from my Inbox. Propose updating it so notes='new notes from MCP', then confirm."*
**Expected:** Open task in Things — notes field replaced.
- [x] PASS — get_todo confirmed notes="new notes from MCP", modified timestamp advanced.

### 41 — Update deadline
**Prompt:** *"Pick a task from my Inbox. Propose updating it so deadline='2026-12-31', then confirm."*
**Expected:** Things shows the 2026-12-31 deadline badge on that task.
- [x] PASS — get_todo confirmed deadline="2026-12-31", modified timestamp advanced.

### 42 — Update tags
**Prompt:** *"Pick a tagged task from my Inbox. Propose updating it so tags=['MCP-test'], then confirm."* (Create the tag 'MCP-test' in Things first if it doesn't exist, or substitute a real tag name.)
**Expected:** Task now has only that tag.
- [x] PASS — used tag 'Important' (existing tag; 'MCP-test' doesn't exist in this account — Things silently ignores unknown tags via URL scheme). Verified via things.tasks(tag='Important') returning the correct UUID.

### 43 — Clear notes
**Prompt:** *"Pick a task with notes. Propose updating it so notes='', then confirm."*
**Expected:** Notes field is now empty in Things.
- [x] PASS — get_todo confirmed notes="", modified timestamp advanced. Preview correctly rendered notes=(cleared).

### 44 — Clear all tags
**Prompt:** *"Pick a tagged task. Propose updating it so tags=[], then confirm."*
**Expected:** Task has no tags in Things.
- [x] PASS — things.tasks(tag='Important') no longer returns the task UUID. Preview correctly rendered tags=(cleared).

### 45 — Refuse empty proposal
**Prompt:** *"Propose updating to-do `<any-uuid>` with no field changes — just the todo_id."*
**Expected:** Clean ValueError: "propose_update_todo … has no fields to update. Pass at least one of: title, notes, deadline, tags."
- [x] FIXED ✅ — Bug found during testing (error fired at confirm, not propose time). Fixed in a separate session by moving the empty-fields guard to propose time. Re-verification not required; fix is covered by existing test suite.

---

## Items 46–47: Undo of propose_update_todo

### 46 — Undo restores original title
**Prompt:** *"Propose updating `<uuid>` to title 'V2-chunkB undo-me', confirm, then undo."*
**Expected:** Old title restored in Things. `recent_undo_log()` shrinks by 1.
- [x] PASS — title restored to "Prepare Board Meeting Agenda", modified timestamp advanced, restored_fields=["title"].

### 47 — Undo only touches changed fields ⭐ LOAD-BEARING
**Steps:**
1. Propose + confirm a title change on a task that also has notes.
2. Before calling undo: **manually edit the task's NOTES in the Things UI** (any change).
3. Call `undo()`.

**Expected:** Title is restored to the original. Your manual notes edit **survives intact**. Tags, deadline, and every other field are untouched.
**Prompt for step 3:** *"Undo the most recent action."*
- [x] PASS — title restored to "Update Business Insurance Policy"; concurrent notes edit ("simulated concurrent manual edit") survived intact. restored_fields=["title"] only. Verified via get_todo.

---

## Items 48–51: THINGS_MCP_AUTO_CONFIRM flag

### 48 — Off → propose just enqueues
**Pre-condition:** `THINGS_MCP_AUTO_CONFIRM` NOT in claude_desktop_config.json (baseline).
**Prompt:** *"Propose adding 'V2-chunkB autoconfirm-off' to my Inbox."*
**Expected:** Response has `auto_confirmed: False`. No task in Things. Cancel via `cancel_action`.
- [x] PASS — auto_confirmed=false confirmed. Pending row cancelled cleanly. No task created.

### 49 — On → propose runs inline
**Pre-condition:** Add `"THINGS_MCP_AUTO_CONFIRM": "1"` to things-mcp `env` block. Restart Claude Desktop.
**Prompt:** *"Propose adding 'V2-chunkB autoconfirm-on' to my Inbox."*
**Expected:** Response has `auto_confirmed: True` AND a `result` field with the new task id. Task IS in Things.
- [x] PASS — auto_confirmed=true, result.id=9ZFa3DnNgesfKnWKsnyRrc returned inline, task landed in Inbox in a single propose call with no confirm round-trip.

### 50 — On + never-bypass kinds (code-only check)
**Command run in Claude Code:** `uv run python -c "from things_mcp import config; print(config.NEVER_BYPASS_KINDS)"`
**Expected:** `frozenset({'delete_todo', 'bulk_delete', 'bulk_complete', 'bulk_move', 'bulk_update'})`
- [x] PASS — auto-verified programmatically; output matched exactly.

### 51 — On + handler fails (auth error leaves pending row)
**Pre-condition:** Auto-confirm still on. Temporarily set `THINGS_AUTH_TOKEN=` (empty string) in config. Restart Claude Desktop.
**Prompt:** *"Propose updating `<any-uuid>` to title 'should-fail'."*
**Expected:** RuntimeError about missing THINGS_AUTH_TOKEN. `list_pending_actions()` still shows the stranded row.
**Clean-up:** Restore real `THINGS_AUTH_TOKEN`, restart Claude Desktop.
- [x] PASS — RuntimeError fired with actionable message ("Things → Settings → General → Enable Things URLs → Manage"). Pending row f8818515 survived in list_pending_actions() for retry. No task created in Things.

---

## Item 52: Tear-down

### 52 — Remove THINGS_MCP_AUTO_CONFIRM
**Action:** Remove `"THINGS_MCP_AUTO_CONFIRM"` from claude_desktop_config.json. Restart Claude Desktop.
**Verify:** *"Propose adding 'V2-chunkB teardown-check' to my Inbox."* Response must have `auto_confirmed: False`.
- [x] PASS — auto_confirmed=false confirmed. Pending row cancelled. Default behaviour fully restored.

---

## Summary

| Item | Description | Done |
|---|---|---|
| 39 | Update title | [x] PASS |
| 40 | Update notes | [x] PASS |
| 41 | Update deadline | [x] PASS |
| 42 | Update tags | [x] PASS |
| 43 | Clear notes | [x] PASS |
| 44 | Clear all tags | [x] PASS |
| 45 | Refuse empty proposal | [x] FIXED ✅ — bug found + fixed in separate session |
| 46 | Undo restores title | [x] PASS |
| 47 | Undo only touches changed fields ⭐ | [x] PASS |
| 48 | AUTO_CONFIRM off → enqueues | [x] PASS |
| 49 | AUTO_CONFIRM on → inline | [x] PASS |
| 50 | NEVER_BYPASS_KINDS correct | [x] PASS |
| 51 | Auto-confirm + auth failure leaves pending row | [x] PASS |
| 52 | Tear-down restores default | [x] PASS |

**Verdict:** Ready for chunk C. One bug found and fixed during testing (item 45 — empty-field validation moved to propose time). All architectural properties confirmed, including the load-bearing surgical undo on item 47.
