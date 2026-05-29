# Handoff: Steps 5D + 5E — cancel/delete todo & project

Working directory: `/Users/Shared/things-mcp`. Branch: `main`.
Run all commands with `uv run …` (never bare `python`).
You must be `joshsmith` for source edits. Do **not** run write-path live tests as
`joshsmith` — see the manual-testing note at the end.

Automated suite baseline: **284 tests, ~1.9 s, all green.**

---

## What to build

### Step 5D — `propose_cancel_todo` + `propose_bulk_delete` cleanup

**5D-1 — `cancel_todo` handler**

Create `src/things_mcp/services/handlers/cancel_todo.py`.

Pattern: follow `complete_todo.py` exactly — snapshot before_state, write
undo_log row before the URL call, poll for the expected status, attach
after_state. Key differences:

- KIND = `"cancel_todo"`
- execute: `url_scheme.build_update_url(id, auth_token, canceled=True)`,
  poll until `status == "canceled"`
- undo: `url_scheme.build_update_url(id, auth_token, canceled=False)`,
  poll until `status == "incomplete"`
- NOT in `NEVER_BYPASS_KINDS` (cancelling is reversible and low-risk)
- Guard: raise `ValueError` if task is already canceled
- `build_update_url` already accepts `canceled=` — no new URL builder needed

**5D-2 — Register and expose**

- `src/things_mcp/services/handlers/__init__.py` — add `cancel_todo` import
  and `cancel_todo.KIND: cancel_todo` entry in REGISTRY
- `src/things_mcp/tools/propose.py` — add `propose_cancel_todo(todo_id)`
  following the same shape as `propose_complete_todo` if it exists, or
  `propose_move_todo` as a model

**5D-3 — `propose_bulk_delete` decision and fix**

The `bulk_delete` handler (`src/things_mcp/services/handlers/bulk_delete.py`)
currently marks tasks `canceled=True, completed=True` (old soft-delete). This
is now misleading since `propose_delete_todo` means AppleScript → Trash.

**Recommended approach: rename to `propose_bulk_cancel`.**
Rationale: batch AppleScript deletes (one call per task) add complexity and
need `ALLOW_APPLESCRIPT=1`. Renaming to `bulk_cancel` is honest about what it
does, keeps the tool available without AppleScript, and a true
`propose_bulk_delete` (AppleScript) can be added later if needed.

Concretely:
- Rename `propose_bulk_delete` → `propose_bulk_cancel` in `tools/propose.py`
- Update the handler's `make_preview` and docstring to say "cancel" not "delete"
- Update KIND from `"bulk_delete"` → `"bulk_cancel"` in `bulk_delete.py`
  (rename the file to `bulk_cancel.py` if clean; otherwise leave and update KIND)
- Update `NEVER_BYPASS_KINDS` in `config.py` accordingly
- Update all unit tests that reference the old name/KIND

If after reading the code you judge approach (a) — AppleScript batch delete —
is cleaner, implement that instead, but document the reasoning.

---

### Step 5E — `propose_cancel_project` + `propose_delete_project`

**5E-1 — `cancel_project` handler**

Create `src/things_mcp/services/handlers/cancel_project.py`.

Same pattern as `cancel_todo` but for projects:
- KIND = `"cancel_project"`
- Use `things_repo.get_project_row(project_id)` to snapshot before-state and
  guard against missing/already-canceled projects
- execute: `url_scheme.build_update_project_url(id, auth_token, canceled=True)`
  — `build_update_project_url` already accepts `canceled=`; no new builder needed
- undo: `url_scheme.build_update_project_url(id, auth_token, canceled=False)`
- NOT in `NEVER_BYPASS_KINDS`

**5E-2 — `delete_project` handler**

Create `src/things_mcp/services/handlers/delete_project.py`.

Same pattern as `hard_delete_todo.py` (now `delete_todo`), adapted for projects:
- KIND = `"delete_project"`
- Requires `THINGS_MCP_ALLOW_APPLESCRIPT=1`
- Snapshot before-state using `things_repo.get_project_row(project_id)`
- execute AppleScript: `tell application "Things3" to delete (project id "{safe_id}")`
- undo AppleScript (multi-line form with `return ""`):
  ```
  tell application "Things3"
      move (project id "{safe_id}") to list "Anytime"
      return ""
  end tell
  ```
  Note: undo restores to "Anytime" as the safe fallback (projects don't live in
  Inbox or Today). Capture `original_area` from before-state snapshot; if the
  project belonged to an area, restore to that area — but area restore via
  AppleScript may not be possible. Verify during implementation; document the
  limitation in the preview string if area restore isn't supported.
- Always in `NEVER_BYPASS_KINDS`
- Preview must clearly state: "Deletes project AND all its tasks → Things Trash"

**IMPORTANT — verify AppleScript behaviour before writing tests:**
Before implementing, run a read-only SDEF check:

```bash
osascript -e 'tell application "Things3" to get class of first project of list "Anytime"'
```

Expected: `project`. If Things 3 returns an error, adjust the AppleScript
reference form. The `project id "X"` reference form mirrors `to do id "X"` and
should work — but confirm it in the SDEF or via a quick read-only probe before
writing the handler.

**5E-3 — Register and expose both**

- `handlers/__init__.py` — add both handlers and REGISTRY entries
- `tools/propose.py` — add `propose_cancel_project(project_id)` and
  `propose_delete_project(project_id)` following the same shape as
  `propose_cancel_todo` / `propose_delete_todo`
- `config.py` — add `"delete_project"` to `NEVER_BYPASS_KINDS`

---

## Unit tests

Each handler needs a `tests/test_handler_<kind>.py` covering:

1. execute — happy path (mock `run_script` / `url_scheme.launch` + poll)
2. undo — happy path
3. Already-canceled / already-in-Trash guard (ValueError)
4. Missing item guard (ValueError)
5. NEVER_BYPASS_KINDS membership (delete handlers only)
6. AppleScript flag check (delete_project only)
7. undo_log row written BEFORE the mutation (V2 acceptance gate)

Follow `tests/test_hard_delete_handler.py` and `tests/test_handler_complete_todo.py`
as templates.

**Verification command (run as `joshsmith`):**

```bash
uv run pytest -q
```

Must show **290+ tests passing** with no regressions. Adjust the expected count
to match what actually lands — the baseline is 284.

---

## After unit tests pass

Update `docs/things-mcp-V2-technical-architecture-and-implementation-plan.md`:

- §0 status table: flip Steps 5D and 5E Build column to ✅ Done with test count
- Note that 5E Manual Testing is pending (one smoke-test needed as Test user for
  `propose_delete_project`)

Commit message suggestion:
```
Step 5D+5E: propose_cancel_todo, propose_bulk_cancel, propose_cancel_project, propose_delete_project

284 → <N> tests passing. propose_bulk_delete renamed to propose_bulk_cancel
(honest semantics). propose_delete_project requires ALLOW_APPLESCRIPT=1;
live smoke-test pending (Test user session).
```

Push to `main`.

---

## Manual testing required after this session

Only **one item** needs the Test user:

`propose_delete_project` — AppleScript delete. Write a live test
`tests/test_step5e_live.py` during this session following the shape of
`tests/test_step5a_live.py`. The Test user session will:

1. Run `uv run pytest tests/test_step5e_live.py -v -s` with `THINGS_AUTH_TOKEN`
   and `THINGS_MCP_ALLOW_APPLESCRIPT=1` set
2. Confirm a test project + its tasks move to Trash on delete
3. Confirm undo restores the project from Trash

The cancel tools (cancel_todo, cancel_project, bulk_cancel) are URL-scheme only
and do not need a manual session.

---

## Orphan file to clean up

`src/things_mcp/services/handlers/delete_todo_new.py` — two-line tombstone,
safe to ignore. Remove it if `rm` permissions are available in this session;
otherwise leave it.
