# V2 Step 4b verification results — 2026-05-25

Run by: Claude Code (Test user, autonomous session)
Branch: main (cdb5a3e at session start)
Automated suite at session start: **225 passed**

---

## Pre-flight

| Check | Result |
|---|---|
| `whoami` | `Test` ✅ |
| `git pull origin main` | Permission denied on .git/FETCH_HEAD (expected — repo owned by joshsmith, Test is read-only on git ops). Not a blocker. ⚠️ |
| `uv run pytest -q` | 225 passed ✅ |
| `uv run things-mcp --help` | Clean exit ✅ |
| `health()` | `things_db_path` ✅ `things_app_running=true` ✅ `things_py_version=1.0.1` ✅ `state_db_exists=true` ✅ `url_scheme_auth_token_set=true` ✅ |

**Code inspection:**
- `NEVER_BYPASS_KINDS` includes `delete_heading` ✅
- All 4 handler files exist (`add_heading.py`, `update_heading.py`, `delete_heading.py`, `dummy_heading.py`) ✅
- `get_project_with_headings` present in `things_repo.py` ✅
- Name validation regex `^__[A-Z][A-Z0-9 _\-:]*__$` and `after_todo_id_note` wiring confirmed ✅

**Scratch project created:** `4b-test` → UUID `Gpc6kRWuL2fby4He414KCe`
**Mixed project created:** `4b-mixed` (headings=['Native A','Native B']) → UUID `UR2DAYGScKHVqDFnnXpspJ`

---

## Round-4 deferred items (120–122)

**Status: NOT RUN — require config changes + MCP server restart (manual).**
See "Items requiring manual input" section below.

---

## Step 4b checklist (items 98–119)

### `propose_add_heading` — basic + error cases

| # | Description | Result | Notes |
|---|---|---|---|
| 98 | Add dummy heading 'Design' | ✅ | `__DESIGN__` created (UUID `Ac9A92wh74e6MWfSWCsYWb`), `add_heading` undo row present |
| 99 | Name with space 'Phase 1' | ✅ | `__PHASE 1__` created (UUID `Jh3AxGndm2gu2CF7zSWxNE`) |
| 100 | Invalid name starts with digit '1st Sprint' | ⚠️ BUG-A | Propose succeeds (preview falls back to `__1ST SPRINT__`); error fires at confirm time, not propose time. No mutation. See [Bug A](#bug-a). |
| 101 | Project not found 'FAKE-UUID' | ⚠️ BUG-A | Same deferred-validation pattern. Error at confirm: "Project 'FAKE-UUID-DOES-NOT-EXIST' not found." No mutation. |
| 102 | `after_todo_id` hint acknowledged | ✅ | Preview contains hint note; result has `after_todo_id_note` field. `__BACKEND__` created (UUID `8Gubj6DGbkZ8gNBMCnaQSr`). |

### `propose_add_heading` — undo

| # | Description | Result | Notes |
|---|---|---|---|
| 103 | Undo heading add | ✅ | `undo(undo_id=...)` returned `undone:true, status:'canceled'`. `__DESIGN__` (UUID `Ac9A92wh74e6MWfSWCsYWb`) moved to Logbook. undo_log row consumed. |
| 104 | Undo without auth token | 🔲 MANUAL | Requires unsetting THINGS_AUTH_TOKEN in Claude Desktop config + restart. |

### `get_project` — unified headings overlay

| # | Description | Result | Notes |
|---|---|---|---|
| 105 | `headings` array present with `kind/id/name/position` | ✅ | 4b-test project returns `headings: [{kind:"dummy",id:...,name:"PHASE 1",position:2},{kind:"dummy",...,"BACKEND",position:3}]`. Canceled `__DESIGN__` correctly excluded. |
| **106** | **Native + dummy together (LOAD-BEARING)** | **✅** | `4b-mixed` headings array: `{kind:"dummy",name:"DUMMY EXTRA"}` + `{kind:"native",name:"Native A"}` + `{kind:"native",name:"Native B"}`. Both `kind:"native"` and `kind:"dummy"` entries present. The unified overlay works correctly. |
| 107 | Empty project → `headings: []` | ✅ | `4b-empty` (UUID `QDreuLWLoDsQo9KbhViYBE`) returns `headings:[]`. |

### `propose_update_heading`

| # | Description | Result | Notes |
|---|---|---|---|
| 108 | Rename by name | ❌ BUG-B | `confirm_action` fails: "No such task uuid found: 'Design'". `things.tasks()` raises ValueError for non-UUID strings; `get_todo()` didn't catch it, so name-scanning fallback never reached. **Fix applied** to `things_repo.get_todo` — requires server restart to activate. See [Bug B](#bug-b). |
| 109 | Rename by UUID | ✅ | `__PHASE 1__` (UUID `Jh3AxGndm2gu2CF7zSWxNE`) renamed to `__BACKEND__`, undo_id recorded. |
| 110 | Heading not found by name | ❌ BUG-B | Same root cause as #108. Confirm error: "No such task uuid found: 'NonExistent'". Correct error semantics but wrong error path. No mutation. |
| 111 | Target is not a dummy (UUID path) | ✅ | Confirm error: "Task '...' (title='task-alpha') is not a dummy heading." No mutation. |
| 112 | Ambiguity: native + dummy share name | 🔲 DEFERRED | Requires complex setup + server restart after Bug B fix. |
| **113** | **Undo rename (LOAD-BEARING, title restore)** | **✅ (partial)** | `undo(undo_id=...)` returned `undone:true, restored_title:"__PHASE 1__"`. Title reverted. The "manually edit notes between rename and undo" sub-step requires user interaction with Things UI — see manual items below. |

### `propose_delete_heading`

| # | Description | Result | Notes |
|---|---|---|---|
| 114 | Delete by name | ❌ BUG-B | Same root cause. Confirm: "No such task uuid found: 'Design'". No mutation. |
| 115 | Delete by UUID | ✅ | `__DESIGN__` (UUID `5SBMsN43DyphRBp5LLmcAX`) soft-deleted, status=canceled. |
| **116** | **Undo delete (LOAD-BEARING)** | **✅** | `undo()` returned `undone:true, status:'incomplete'`. `__DESIGN__` back in project with `status:incomplete`, visible in `get_project` headings array. |
| 117 | Refuse native heading | ✅ | Confirm error: "is not a dummy heading. Native headings require AppleScript (step 5)." No mutation. |
| 118 | Refuse already-canceled | ✅ | Confirm error: "already status='canceled'. Nothing to delete." No mutation. |
| 119 | Never auto-confirmed | 🔲 MANUAL | Requires `THINGS_MCP_AUTO_CONFIRM=1` config change + restart. Note: `auto_confirmed:False` was observed in every `propose_delete_heading` call this session, consistent with never-bypass wiring. |

---

## Bugs found

### Bug A

**Validation deferred from propose to confirm time** (items 100, 101; and error cases in 110, 111, 114, 117, 118)

`make_preview()` in `add_heading.py` (lines 33–36) catches `ValueError` from `make_dummy_title` and silently falls back to `f"__{name.upper()}__"`. This means an invalid heading name (starts with digit, empty, etc.) and an invalid project UUID both produce a successful proposal with a misleading preview. The `ValueError` fires correctly at `execute()` / confirm time — no mutation occurs — but the UX is wrong: the user sees an action ID, then the confirm fails.

Secondary observation: failed confirms leave the pending action row in `list_pending_actions` (caller must `cancel_action` manually). This matches the spec for auth-failure cases (item 51) and may be intentional as a retry affordance.

**Suggested fix:** call `make_dummy_title(name)` (and validate project exists) inside the proposal handler before enqueuing, not only inside `execute()`.

### Bug B

**`get_todo` raises instead of returning None for non-UUID strings** (items 108, 110, 112, 114)

`things.tasks('Design')` raises `ValueError("No such task uuid found: 'Design'")`. `things_repo.get_todo()` did not catch this, so `_resolve_heading_uuid` in `update_heading.py` and `delete_heading.py` never reached the name-scanning fallback (line 178 in `update_heading.py`, equivalent in `delete_heading.py`).

**Fix applied this session** — `things_repo.get_todo` now wraps the `things.tasks()` call in a `try/except ValueError` and returns `None`, matching the function's declared return type. 225 tests still pass. Server restart required to activate.

---

## Items requiring manual input

The following items cannot be run autonomously. They require config changes, MCP server restarts, or visual Things UI interaction.

### After Bug B fix + server restart

Re-run these (they will now work):
- **108** — Rename by name ('Design' → 'UX')
- **110** — Heading not found by name (correct error path)
- **112** — Ambiguity (native + dummy with same name) — complex setup: create project with native heading 'Planning', add `__PLANNING__` dummy to same project, then `propose_update_heading('Planning', ...)` — expect ValueError listing both candidates
- **114** — Delete by name

### Requires auth token unset + restart

- **104** — Unset `THINGS_AUTH_TOKEN` → restart → `propose_add_heading` → confirm → `undo()` → expect: `RuntimeError` pointing at Things → Settings → Manage. Restore token after.

### Requires `THINGS_MCP_AUTO_CONFIRM=1` + restart

- **119** — Set `THINGS_MCP_AUTO_CONFIRM=1` → restart → `propose_delete_heading(<dummy-uuid>)` → response must have `auto_confirmed:False` and note "never auto-confirmed". Unset after.

### Requires Things UI visual verification

- **113 (partial)** — After rename + undo, manually edit the task's NOTES in Things UI, then undo — confirm NOTES edit survives, only title is restored. (Title-restore itself was confirmed programmatically ✅.)
- **116 (partial)** — Visual check in Things UI that `__DESIGN__` task is visible in the project (not just the Logbook). Semantic state confirmed via `get_project` ✅.
- **106 (partial)** — Visual check that native headings ('Native A', 'Native B') render as section dividers in Things UI, not as checkbox tasks. Overlay data confirmed via API ✅.

### Round-4 deferred (items 120–122)

- **120** — Unset `THINGS_AUTH_TOKEN` → restart → create project → confirm → `undo()` → expect RuntimeError
- **121** — Still without token → `propose_update_project` → expect RuntimeError
- **122** — Restore token → restart → set `THINGS_MCP_AUTO_CONFIRM=1` → restart → propose any bulk op → expect `auto_confirmed:False`. Unset after.

---

## Acceptance gate status

| Criterion | Status |
|---|---|
| Items 98–119 walked, results recorded | ✅ (all run or blocked on manual) |
| Item 106 (native + dummy overlay) confirmed | ✅ |
| Item 112 (ambiguity) confirmed | 🔲 needs server restart + manual setup |
| Item 113 (selective undo title-only) confirmed | ✅ (semantic); 🔲 partial (UI notes edit) |
| Item 116 (undo delete restores to project) confirmed | ✅ |
| Item 119 (never auto-confirms) confirmed | 🔲 needs config change |
| Round-4 items 120–122 closed | 🔲 manual |
| No mutations on joshsmith DB | ✅ |
| Bug B fix committed | Pending commit (fix in working tree) |
