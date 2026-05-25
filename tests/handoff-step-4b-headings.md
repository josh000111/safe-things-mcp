# Handoff: V2 Step 4b manual verification — Dummy heading layer

## Context

Working directory: `/Users/Shared/things-mcp`
Account: **Test** (verify with `whoami` before any writes — must print `Test`)

This is the live-app verification session for V2 step 4b: the URL-scheme-only dummy-heading layer.

### What landed in this build session

- **`propose_add_heading(project_id, name, after_todo_id?)`** — creates a to-do titled `__NAME__` (all-caps, double-underscore wrapped) inside a project. The `after_todo_id` hint is accepted but cannot be honoured by the URL scheme (position is unspecified). Undo soft-deletes the dummy task.
- **`propose_update_heading(project_id, heading_id_or_name, new_name)`** — renames a dummy heading by UUID or name. If both a native heading and a dummy share the same name, returns an ambiguity error listing both candidates.
- **`propose_delete_heading(project_id, heading_id_or_name)`** — soft-deletes a dummy heading. **Never auto-confirmed.** Undo restores the task.
- **`get_project` extended** — now returns a `headings: [{kind, id, name, position}]` array overlay covering both native Things headings and dummy `__NAME__` tasks. The `items` list is unchanged.
- Native heading operations (rename/delete) return a clear error pointing at step 5 (AppleScript).

Automated suite: **225 tests passing** at handoff.

---

## Required pre-flight

1. `whoami` → must print `Test`.
2. `git pull origin main` to grab the build commit.
3. Confirm `THINGS_AUTH_TOKEN` is set in Claude Desktop config — items #103/108/109/113/114/115/116 all need it.
4. Restart Claude Desktop to reload the MCP server.
5. `health()` returns `things_app_running=true`, `state_db_exists=true`, `url_scheme_auth_token_set=true`.
6. Create a scratch project: *"Propose adding a project titled '4b-test'."* Confirm. Use this project UUID for most tests below. Having 2–3 ordinary to-dos in it helps.

---

## Round-4 deferred items — close these first

Run items **120–122** from `tests/things-mcp-manual-verification.md` before the main 4b checklist. They require a config-change + restart sequence:

1. Unset `THINGS_AUTH_TOKEN` → restart MCP server → run item **#120** (undo on an add_project without token) and **#121** (update_project without token).
2. Restore `THINGS_AUTH_TOKEN` → restart → set `THINGS_MCP_AUTO_CONFIRM=1` → restart → run item **#122** (bulk op with AUTO_CONFIRM on) → unset `THINGS_MCP_AUTO_CONFIRM` → restart.

---

## What to run (main 4b session)

Walk items **98 through 119** in `tests/things-mcp-manual-verification.md`, in order. As you go:

- Record the outcome (✅ / ⚠️ / ❌) and any surprises in a results doc.
- Name the results doc `tests/V2-step-4b-verification-<YYYY-MM-DD>.md`.
- If a write doesn't land as expected within ~3s, screenshot Things, run `recent_undo_log()`, and note both before retrying.

The checklist is grouped:

- **98–102** — `propose_add_heading` basic + error cases.
- **103–104** — `add_heading` undo + auth-token error path.
- **105–107** — `get_project` headings overlay (native + dummy), empty project.
- **108–113** — `propose_update_heading` by name + by UUID + error cases + ambiguity + undo.
- **114–119** — `propose_delete_heading` by name + by UUID + undo + never-bypass + error cases.

---

## Things to watch closely

These items are the spec-ambiguous or load-bearing ones:

- **Item 106 (native + dummy together)** — the `headings` array must include both `kind: "native"` and `kind: "dummy"` entries from the same project. This is the key property of the unified overlay. If only one kind appears, the `get_project_with_headings` function has a scan gap.
- **Item 108/109 (rename)** — confirm `things:///update?title=__UX__&auth-token=...` actually changes the task title in the Things UI. The `modified` timestamp must advance (polling check). If renaming succeeds but `get_project` still shows the old title, that's a cache/poll timing issue.
- **Item 112 (ambiguity)** — the most complex setup: requires both a native heading AND a `__PLANNING__` dummy in the same project. If Things doesn't let you have both with the same display name, skip this item and note it.
- **Item 113 (selective undo for rename)** — after renaming and undoing, the title must revert. If you manually edited something else on the task between rename and undo, that other edit should survive (only the title is restored). Same load-bearing property as items #47 and #84 for to-dos and projects.
- **Item 116 (undo of delete)** — the `__UX__` task must return to `incomplete` status back in the project, not stay in the Logbook. Things' `update?canceled=false&completed=false` should move it back; confirm in Things UI.
- **Item 119 (never-bypass on delete_heading)** — same check as item #65 (delete_todo) and #97 (bulk ops). Even with `THINGS_MCP_AUTO_CONFIRM=1`, `propose_delete_heading` must return `auto_confirmed: False`.

---

## Visual caveat to note during testing

The `__DESIGN__` tasks created by `propose_add_heading` render in the Things UI as **ordinary to-do items** (checkboxes, visible underscores). They are NOT native section dividers. This is expected behaviour for the step 4b URL-scheme-only layer. Native dividers require:
- Project birth via `propose_add_project(headings=[...])` (already shipped in step D).
- Or AppleScript (step 5/6).

---

## Acceptance criteria for closing Round 5

- Items 98–122 walked, every result recorded.
- Items #106, #112, #113, #116, #119 confirmed working (the load-bearing / spec-ambiguous ones).
- Any unexpected failures captured as bug-handoff docs in `tests/` in the same shape as `handoff-items-56-57.md`.
- Round-4 deferred items #120/#121/#122 closed (or noted if environment prevents them).
- No mutations on the real `joshsmith` Things DB at any point.

When the round closes:

1. Push the results doc + any bug handoffs to `main`.
2. Update the spec §0 status table — flip "V2 step 4b" rows from "Not built / Not yet run" to the verified state.

---

## If something looks wrong

- Don't keep mutating. Run `cancel_action(action_id)` or `undo()` if a proposal has already confirmed, then inspect.
- For undo-log shape questions, query `recent_undo_log(limit=5)` and paste the JSON into the results doc.
- For URL-scheme behaviour mismatches, the dummy-heading handler source is:
  - `src/things_mcp/services/handlers/add_heading.py`
  - `src/things_mcp/services/handlers/update_heading.py`
  - `src/things_mcp/services/handlers/delete_heading.py`
  - `src/things_mcp/services/handlers/dummy_heading.py` (shared regex + title utilities)
- The read-layer extension is in `src/things_mcp/services/things_repo.py::get_project_with_headings`.

The build session is happy to take a follow-up handoff for any code-side fix needed.
