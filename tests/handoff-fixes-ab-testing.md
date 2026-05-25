# Handoff: Pre-release fixes A & B — manual testing session

## Context

Working directory: `/Users/Shared/things-mcp`
Account: **Test** (verify with `whoami` before any writes — must print `Test`)

This is the live-app verification session for pre-release fixes A and B. Both fixes are in place; the automated suite has been updated. This session verifies the changes against the real Things 3 app.

### What landed in the build session

**Fix A — tag pre-validation:**
- `services/things_repo.py`: new `get_tag_names()` helper.
- `services/url_scheme.py` (or `services/validators.py`): new `validate_tags(requested)` that raises `ValueError` with actionable message if any tag name isn't in Things.
- Wired into every write tool that accepts `tags`: `add_inbox_todo`, `add_today_todo`, `add_anytime_todo`, `add_someday_todo`, and all `propose_*` handlers that accept tags (`add_todo`, `update_todo`, `bulk_update`, `add_project`, `update_project`).
- Validation fires at propose time for `propose_*` tools — not at confirm time.

**Fix B — tags in read responses:**
- `things_repo.todo()` now uses `things.tasks(uuid)` (same pattern as the internal `get_todo()`) so the `tags` field is included.
- `things_repo.project()` now uses `things.tasks(uuid, type="project")` so the project row includes its `tags` field.
- Items inside `get_project` may or may not carry per-item tags depending on what `things.tasks()` returns for the project row — the implementation doc notes the outcome and any further steps taken.

---

## Required pre-flight

1. `whoami` → must print `Test`.
2. `git pull origin main` to grab the build commit. (Note: `Test` user may not have git write access; read-only pull is fine. If git pull is blocked, confirm the build commit SHA with the `joshsmith` session and verify `uv run pytest -q` shows the expected test count.)
3. `uv run pytest -q` → all green (note total count; will be higher than 227 from prior session).
4. `uv run things-mcp --help` → clean exit.
5. `health()` returns `things_app_running=true`, `state_db_exists=true`, `url_scheme_auth_token_set=true`.
6. Confirm at least one tag exists in the Test account's Things (e.g. "Errand"). If none exist, create one in Things UI before starting.

---

## What to run

Walk items **123 through 130** in `tests/things-mcp-manual-verification.md`, in order. Record each result (✅ / ⚠️ / ❌) plus any surprises in a results doc named `tests/fixes-ab-verification-<YYYY-MM-DD>.md`.

### Fix A items (123–126)

**Item 123 — unknown tag rejected (`add_inbox_todo`)**
- Call: *"Add a to-do to the Inbox titled 'Tag validation test' with tags ['NonExistentTag999']."*
- Expected: `ValueError` (or MCP error response) naming `NonExistentTag999` and listing available tags. **Nothing appears in the Inbox.**
- Check: Open Things Inbox, confirm no new task.

**Item 124 — known tag accepted (`add_inbox_todo`)**
- Call: *"Add a to-do to the Inbox titled 'Tag validation success' with tags ['Errand']."* (Use a tag that actually exists in the Test account.)
- Expected: Succeeds. Task appears in Inbox within ~1s. Open Things Inbox → task visible → tags panel shows "Errand".

**Item 125 — propose-time rejection for `propose_update_todo`**
- Need: any valid to-do UUID from the Test account. Get one via `list_inbox()` or `get_projects()`.
- Call: *"Propose updating to-do `<uuid>` with tags=['FakeTag']."*
- Expected: `ValueError` at propose stage (before confirm). `list_pending_actions()` shows no new entry.

**Item 126 — `propose_bulk_update` with mixed tags**
- Need: two valid to-do UUIDs.
- Call: *"Propose bulk updating todos `[<uuid1>, <uuid2>]` with tags=['Errand', 'GhostTag']."*
- Expected: `ValueError` at propose stage naming `GhostTag`, listing available tags. No pending action created. `list_pending_actions()` unchanged.

### Fix B items (127–130)

**Item 127 — `get_todo` returns tags**
- Setup: In Things UI, ensure the task created in #124 (or any other task) has the "Errand" tag.
- Call: `get_todo(<uuid>)`.
- Expected: Response dict includes `"tags": ["Errand"]` (or a list containing it). The `tags` key must be present and populated — not absent, not `null`.

**Item 128 — `get_todo` returns `tags: []` for untagged task**
- Setup: Find or create a to-do with no tags in the Test account.
- Call: `get_todo(<uuid>)`.
- Expected: Response includes `"tags": []`. The key must be present (not absent).

**Item 129 — `get_project` returns project-level tags**
- Setup: In Things UI, assign a tag to a project in the Test account (e.g. tag a scratch project with "Errand").
- Call: `get_project(<project_uuid>)`.
- Expected: Top-level response dict includes `"tags": ["Errand"]` (or whatever tags were assigned). Confirm the names match Things UI.

**Item 130 — `get_project` returns `tags: []` for untagged project**
- Setup: Use any project with no tags.
- Call: `get_project(<project_uuid>)`.
- Expected: Top-level dict includes `"tags": []`.

---

## Things to watch closely

- **Item 123 — error message quality.** The message must be *actionable*: name the unknown tag(s), list available options. A generic "error" response is a fail.
- **Item 124 — confirm in Things UI, not just the response.** The URL scheme can silently succeed but drop the tag. The test is what appears in the Things UI tag panel.
- **Item 125 — no pending action must be created.** The validate-at-propose-time requirement means `list_pending_actions()` is unchanged. If a pending action exists (even with an error state), Fix A is wired at the wrong point.
- **Item 127 — `tags` key must be present even if empty.** Consumers check `response.get("tags", [])` — but we want the field always explicit. If the key is absent on a tagged task, `things.tasks()` isn't returning it for this UUID type (report in results doc).
- **Items 129/130 — project-level tags vs. item tags.** `get_project` returns both the project row (top-level) and `items` (sub-tasks). These items check the project's *own* tags, not the tags on its child tasks. If child task tags are also now appearing, note it as a bonus — it's not a requirement for this session.

---

## Acceptance criteria for closing Round 6

- Items 123–130 walked, every result recorded.
- Items 123, 124, 127 are load-bearing — if any of these fail, the fix is not working correctly and a bug handoff is needed.
- Any failures captured as bug-handoff docs in `tests/` in the same shape as `tests/bug-handoff-4b-name-resolution.md`.
- No mutations on the real `joshsmith` Things DB at any point.

When the round closes:

1. Push the results doc (+ any bug handoffs) to `main`.
2. Update `docs/things-mcp-V2-technical-architecture-and-implementation-plan.md` §0 status table — flip Fix A and Fix B Manual Testing rows from `⏳ Not yet run` to `✅ Verified (Round 6 — ...)`.
3. If both fixes pass: the server is feature-complete for pre-release. Next up is V2 step 5 (opt-in AppleScript layer for hard-delete + reorder).

---

## If something looks wrong

- **Fix A not firing:** Check that `validate_tags()` is called before the URL is built in the relevant tool/handler. Add a quick `print(tags)` trace if needed, then revert.
- **Fix B still missing tags:** The root cause is `things.tasks(uuid)` vs `things.get(uuid)`. Verify with a quick Python snippet in `uv run python`:
  ```python
  import things
  task = things.tasks("<uuid>", filepath="/path/to/Things Database.thingsdatabase")
  print(task.get("tags"))  # should be a list, not None/absent
  ```
  If `things.tasks()` genuinely omits tags, the fallback is the SQLite supplementary query described in §11 Fix B "Outcome B" of the spec.
- **For undo-log or pending action questions:** `recent_undo_log(limit=5)` and `list_pending_actions()` are your tools.
- Source files for these fixes:
  - `src/things_mcp/services/things_repo.py` — `get_tag_names()`, `todo()`, `project()`
  - `src/things_mcp/services/url_scheme.py` (or `validators.py`) — `validate_tags()`
  - `src/things_mcp/tools/write.py` — direct write tools
  - `src/things_mcp/services/handlers/` — propose-path handlers
