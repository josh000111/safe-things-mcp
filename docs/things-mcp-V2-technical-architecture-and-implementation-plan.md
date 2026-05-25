# Things 3 MCP Server — Technical Architecture & Implementation Plan

> **Master copy.** This file lives at `/Users/Shared/things-mcp/docs/things-mcp-V2-technical-architecture-and-implementation-plan.md`. Edit here, not in `~/.claude/plans/`.

## 0. Implementation Status (as of 2026-05-25)

Each phase now tracks two rows: **Build** (automated tests green) and **Manual Testing Session** (verified on `Test` user against real Things).

| Phase | Build | Manual Testing Session |
| --- | --- | --- |
| V1 — Read + Inbox-create via URL scheme | ✅ Shipped | ✅ Verified (Round 1) |
| V1 — HTTP callback retired, DB polling in its place | ✅ Shipped | ✅ Verified (Round 1) |
| V2 step 1 — `pending_actions` + `undo_log` CRUD + tests | ✅ Done | n/a — unit tests only |
| V2 step 2 — handler registry + `confirm_action` / `cancel_action` / `list_pending_actions` / `undo` | ✅ Done | n/a — unit tests only |
| V2 step 3 — `propose_add_todo` + round-trip undo test | ✅ Done | ✅ Verified (Round 1) |
| V2 step 4 chunk A — direct shortcuts (`add_today/anytime/someday_todo`, `complete_todo`) + `upcoming` rejection | ✅ Done | ✅ Verified (Round 2) |
| V2 step 4 chunk B — `THINGS_MCP_AUTO_CONFIRM` flag + `propose_update_todo` | ✅ Done | ✅ Verified (Round 2) |
| V2 step 4 chunk C — `propose_move_todo`, `propose_delete_todo` (soft) | ✅ Done | ✅ Verified (Round 3 — items 56/57 target-validation fix landed post-run) |
| V2 step 4 chunk D — `propose_add_project` (with headings via `things:///json`), `propose_update_project` | ✅ Done | ✅ Verified (Round 4 — 27/30 pass, 3 deferred; 0 blocking bugs; see `tests/V2-Round4-chunks-D-E-verification-2026-05-19.md`) |
| V2 step 4 chunk E — `propose_bulk_*` tools (complete/delete/move/update) | ✅ Done | ✅ Verified (Round 4 — same session; 0 blocking bugs) |
| V2 step 4b — dummy-heading interim layer (URL-scheme only) | ⏳ Not built | ⏳ Manual Testing Session: Not yet run |
| V2 step 5 — opt-in AppleScript layer (`THINGS_MCP_ALLOW_APPLESCRIPT`) for hard-delete + reorder | ⏳ Not built | ⏳ Manual Testing Session: Not yet run |
| V2 step 6 — native heading support via AppleScript + dummy→native converter | ⏳ Not built | ⏳ Manual Testing Session: Not yet run |

Automated suite: 195 tests, ~1.5s, hermetic (no real Things DB / URL launches).

### Round-4 deferred items (non-blocking)
Items #73, #82, #97 require a config-change + session restart (token removal or `AUTO_CONFIRM` flag toggle). All three test error paths already covered by unit tests. To close them: unset token → restart → run #73 + #82 → restore token → restart → run #97. Can be batched with Round-5 preflight.

### Known limitations documented in Round 4
- **Unknown tags silently no-op** — `add_inbox_todo` and `propose_bulk_update` with tags that don't exist in Things report success but Things silently ignores them. Things URL-scheme limitation, not a regression. Low-priority follow-up: add pre-validation against `get_tags()`.
- **`get_project` / `get_todo` don't return tags** — `things-py` library limitation. Tag verification in tests falls back to direct SQLite reads.

## 1. Context

Build a local Python MCP server that lets any MCP-capable agent (Claude Desktop, Claude Code, Codex, Cursor, etc.) safely read and write to the user's Things 3 database on macOS. The server must:

- Expose rich read access to projects, areas, tags, headings, checklists, and task hierarchies.
- Allow the agent to create new to-dos. **V1 is deliberately quarantined to the Inbox** so we can validate the write path without risking the user's curated projects.
- Provide a generic safeguard framework (two-phase confirmation) for destructive actions in V2.
- Provide an undo log so any agent-initiated mutation can be reversed.

The goal of V1 is to ship the smallest end-to-end vertical slice (read + Inbox-create) with the right architectural seams so V2 (full write parity) is purely additive — no rework of the core.

There are several community Things-MCP implementations (most are thin URL-scheme wrappers). What's novel here is the safeguard + undo layer and the portable two-phase confirm pattern.

---

## 2. Direct Answers to Your Four Open Questions

### Q1. Dependency vs. Direct SQL — use `things.py`
Use **`things.py`** as the read layer. It's actively maintained (commits within the last 60 days), wraps the read-only SQLite path, covers the full schema (todos, projects, areas, tags, headings, checklists, deadlines, trashed/status state), and abstracts schema migrations between Things versions. Direct SQL gains nothing here except brittleness.

Mitigation against dependency rot: pin a known-good version in `pyproject.toml`, and keep one thin internal `things_repo.py` module that wraps every call. If `things.py` ever breaks, we only swap the inside of that module — call sites stay stable.

### Q2. The AppleScript UUID Problem — sidestep it entirely
Use the **official Things URL Scheme** for writes, not AppleScript. The URL scheme's `x-callback-url` mechanism returns the new task ID as `x-things-id` directly. This is documented and stable. AppleScript becomes a narrow fallback for the small set of operations the URL scheme can't do (and we don't hit any of those in V1).

```
things:///add?title=Buy%20milk&list=inbox&x-success=things-mcp://callback?id={id}
```

We register a local `things-mcp://` URL handler (via a tiny LaunchAgent or a one-shot local HTTP listener on 127.0.0.1) to capture the callback. See §5 for the chosen mechanism.

### Q3. Concurrency & Timeouts — solved by two-phase confirm
With your chosen safeguard pattern (two-phase), the server **never blocks on user input**. The flow is:
1. `propose_destructive_action(...)` → returns immediately with `{action_id, preview, expires_at}`.
2. Agent surfaces the preview in chat. User says "yes" in natural language.
3. Agent calls `confirm_action(action_id)` → executes, returns result.

No `osascript` dialogs, no elicitation dependency, no client-timeout risk, identical UX across all MCP clients. The MCP server's event loop never stalls. Pending actions live in a SQLite table with a 5-minute TTL.

For URL-scheme callbacks (which *do* require waiting briefly for Things to respond), we run the callback listener in `asyncio.to_thread()` with a 5-second timeout, well under any client's tool-call ceiling.

### Q4. Undo Cache — small SQLite, not JSON
Use a local **SQLite** database (`~/.things-mcp/state.db`) for both the undo log and the pending-action queue. Two tables:

- `pending_actions(id, kind, payload_json, preview, created_at, expires_at)` — two-phase confirm queue.
- `undo_log(id, action_kind, target_uuid, before_state_json, after_state_json, created_at, expires_at)` — reversible operations.

SQLite over JSONL because we need indexed lookups by `action_id` and `target_uuid`, time-range queries, and atomic insert/delete. Retention: last 200 actions or 30 days, whichever is smaller. The `undo_log` table is irrelevant in V1 (no destructive ops) but the table exists from day one so V2 lights up by adding rows.

---

## 3. Proposed Tech Stack

| Layer | Choice | Why |
| --- | --- | --- |
| Language | Python 3.11+ | Required by `mcp` SDK; matches Things community tooling. |
| MCP SDK | `mcp` (official Python SDK, FastMCP API) | Async-native, decorator-based tool registration, broad client compatibility. |
| Read path | `things-py` (`pip install things.py`) | Maintained read wrapper around the SQLite DB. |
| Write path | Things URL Scheme via `subprocess`+`open`/`urllib.parse` | Official, no AppleScript needed for add/update/move. |
| New-task UUID recovery | **DB polling** (read-only `things.py`, 100ms interval, 5s timeout) | The original HTTP callback (`x-success` → `aiohttp` listener) was retired because macOS routed each callback through Safari, spawning a tab per write. Polling is simpler and side-effect-free. |
| Local state | `sqlite3` (stdlib) | Pending actions + undo log. No external dep. |
| Package mgmt | `uv` (recommended) or `pip` + `pyproject.toml` | Fast, deterministic; works for both end-user installs. |
| Lint/format | `ruff` | Single tool, fast. |
| Tests | `pytest` + `pytest-asyncio` | Stdlib-friendly. |

Auth-token for URL-scheme `update`/`update-project` (V2 only): user generates it once in **Things → Settings → General → Enable Things URLs → Manage**, then sets `THINGS_AUTH_TOKEN` in the MCP server env. V1 doesn't need this token.

---

## 4. Architecture

### 4.1 Component diagram (text)

```
┌─────────────────────────────────────────────────────────────────┐
│  MCP Client (Claude Desktop / Claude Code / Codex / Cursor)     │
└───────────────────────────┬─────────────────────────────────────┘
                            │ stdio (MCP protocol)
┌───────────────────────────▼─────────────────────────────────────┐
│  things-mcp server  (Python, FastMCP)                           │
│                                                                 │
│   ┌──────────────┐    ┌────────────────┐    ┌──────────────┐   │
│   │ tools/       │    │ services/      │    │ state/       │   │
│   │  read.py     │───▶│  things_repo   │    │  db.py       │   │
│   │  write.py    │───▶│  url_scheme    │───▶│  pending.py  │   │
│   │  confirm.py  │───▶│  callbacks     │    │  undo_log.py │   │
│   │  undo.py     │    │  applescript*  │    │              │   │
│   └──────────────┘    └────────────────┘    └──────────────┘   │
│           │                   │                                 │
└───────────┼───────────────────┼─────────────────────────────────┘
            │                   │
            │ read              │ write (URL scheme)
            ▼                   ▼
   ┌────────────────┐   ┌──────────────────────┐
   │ main.sqlite    │   │  Things 3 app        │
   │ (read-only)    │   │  (handles things:///)│
   └────────────────┘   └──────────────────────┘

   *applescript layer is V2+ only.
```

### 4.2 Read flow (V1)
1. Agent calls `list_inbox()` (or any read tool).
2. `tools/read.py` calls `services/things_repo.todos(start="Inbox")`.
3. `things_repo` opens a **read-only** connection (`file:...main.sqlite?mode=ro&immutable=0`, `PRAGMA query_only=ON`) — never holds it open between calls, never writes.
4. Returns a typed dict.

Concurrent reads while Things has the DB open are safe: Things uses WAL, and we connect read-only.

### 4.3 Write flow (V1: create in Inbox via polling)
1. Agent calls `add_inbox_todo(title, notes?, when?, deadline?, tags?, checklist?)`.
2. `tools/write.py` validates inputs and forces `list=inbox`.
3. Records a pre-launch wall-clock timestamp (with 2s slack to absorb SQLite's seconds-resolution `created` column).
4. Constructs a clean URL: `things:///add?title=...&list=inbox&...`. No `x-success` / `x-error` params.
5. Launches it via `await asyncio.to_thread(subprocess.run, ["open", url], check=True)`.
6. Polls `things_repo.find_recent_inbox_by_title(title, created_after)` every 100ms up to `WRITE_POLL_TIMEOUT_SECONDS` (default 5).
7. On match, returns `{id, title, list: "Inbox", created_at}`. On timeout, raises with an actionable error pointing at the URL-scheme settings.

**Why polling, not callback:** The original design used `things:///add?x-success=http://127.0.0.1:PORT/cb` and an aiohttp listener. macOS routed each `http://` callback through Safari, opening a tab per write. Polling has slightly higher resource cost (a few extra SQLite reads) but no UX side effects.

### 4.4 Two-phase confirm flow (V2 scaffold, exposed but no-op in V1)
1. `propose_<destructive_op>(...)` → writes a row to `pending_actions`, returns `{action_id, preview, expires_at}`.
2. Agent shows preview to user, gets approval.
3. `confirm_action(action_id)` → loads row, executes, logs reversal payload to `undo_log`, deletes pending row, returns result.
4. `cancel_action(action_id)` → deletes pending row.
5. Sweeper (lazy, on every tool call) deletes expired pending rows.

---

## 5. Tool Definitions

### 5.1 V1 surface (ship this first)

**Read tools** (all read-only, never trigger confirm):

| Tool | Purpose |
| --- | --- |
| `list_inbox()` | All to-dos in Inbox. |
| `list_today()` | Today list. |
| `list_upcoming(days: int = 7)` | Scheduled within N days. |
| `list_anytime()` | Anytime list. |
| `list_someday()` | Someday list. |
| `list_logbook(days: int = 7)` | Recently completed. |
| `list_trash()` | Trash. |
| `get_areas()` | All areas. |
| `get_projects(area_id?: str, include_completed: bool = False)` | Projects, optionally filtered by area. |
| `get_project(project_id: str)` | Single project with its to-dos, headings, and notes. |
| `get_todo(todo_id: str)` | Single to-do incl. checklist items, tags, project/area refs. |
| `get_tags()` | All tags. |
| `search(query: str, limit: int = 25)` | Full-text search across titles + notes. |

**Write tools** (V1 = Inbox-only, no destructive ops):

| Tool | Purpose |
| --- | --- |
| `add_inbox_todo(title, notes?, when?, deadline?, tags?, checklist?)` | Create a to-do in Inbox. Returns `{id, title}`. Hard-coded `list=inbox`. |

**Meta tools** (scaffold, exposed in V1 for visibility but mostly no-ops):

| Tool | Purpose |
| --- | --- |
| `health()` | Reports DB path, Things app running?, URL scheme enabled?, things.py version. |
| `recent_undo_log(limit: int = 20)` | Returns last N reversible actions (empty in V1). |

### 5.2 V2 surface

Mutating tools split into two tiers based on risk. **Low-risk direct shortcuts** skip the airlock (host permissions are sufficient). **Anything destructive, multi-target, or hard to reverse goes through propose/confirm.**

**Tier 1 — Direct shortcuts (no airlock):**

| Tool | Purpose | Why no airlock |
| --- | --- | --- |
| `add_inbox_todo(...)` (V1, already shipped) | Add to Inbox. | Inbox is designed for triage; lowest-risk list. |
| `add_today_todo(...)` (V2 step 4) | Add to Today. | User explicitly approved as low-risk. |
| `add_anytime_todo(...)`, `add_someday_todo(...)` (V2 step 4) | Add to Anytime / Someday. | Same. Tasks are easy to spot and dismiss. |

**Tier 2 — Propose/confirm pattern:**

| Propose | Confirm via | Risk class |
| --- | --- | --- |
| `propose_add_todo(list_id, ...)` (✅ shipped step 3) | `confirm_action` | Lands in a project / arbitrary list — preview valuable. |
| `propose_update_todo(todo_id, fields)` | `confirm_action` | Edits live data. |
| `propose_move_todo(todo_id, target)` | `confirm_action` | Cross-list moves can be hard to find afterward. |
| `propose_reorder_todos(list_id, order)` | `confirm_action` | **Requires AppleScript fallback (URL scheme can't reorder).** Deferred to step 5. |
| `complete_todo(todo_id)` (direct, single-target) | n/a — no airlock | Reversible (`update?completed=false`). Most common everyday op. |
| `propose_bulk_complete([todo_id, ...])` | `confirm_action` | Bulk = preview valuable; never bypassable. |
| `propose_delete_todo(todo_id)` | `confirm_action` — **never bypassable** | Destructive. Soft-delete first (URL `update?canceled=true&completed=true`); AppleScript hard-delete behind `THINGS_MCP_ALLOW_APPLESCRIPT`. |
| `propose_bulk_*(...)` | `confirm_action` — **never bypassable** | Multi-target = high blast radius. |
| `propose_add_project(...)` | `confirm_action` | Project creation supports headings via `things:///json` payload. |
| `propose_update_project(...)` | `confirm_action` | Edits live project. |
| `propose_add_heading(project_id, name)` | `confirm_action` | **Requires AppleScript** (URL scheme `json` endpoint only creates headings inside *new* projects). Deferred to step 5/6. |

**Dispatcher / inspection tools:**

| Tool | Purpose |
| --- | --- |
| `confirm_action(action_id)` | Execute a pending action. Dispatches by `kind` to the handler registry. |
| `cancel_action(action_id)` | Drop a pending action. |
| `list_pending_actions()` | Inspect the queue. |
| `undo(undo_id?: str)` | Reverse the most recent (or specified) action by ID. |

**Auto-confirm escape hatch (`THINGS_MCP_AUTO_CONFIRM`):**

When the env var `THINGS_MCP_AUTO_CONFIRM=1` is set, any tool returning a `propose_*` action_id is immediately confirmed inside the same MCP call — the preview is still surfaced to the agent (so the LLM can summarize before responding) but no second round-trip is required. **Exceptions:** `propose_delete_todo` and `propose_bulk_*` always require an explicit `confirm_action` call regardless of this flag. The "never bypassable" column above marks these.

**Why two-tier and not one or the other:**
- Pure airlock is too high-friction for everyday adds.
- Pure direct tools lose the structured preview / pre-mutation undo-log row that the airlock guarantees for destructive ops.
- Host-level permissions (Claude Desktop "ask / allow / deny" per tool) sit *on top* of both tiers and are the user's primary "I trust this MCP" knob.

### 5.3 Heading & reorder limitations — and the dummy-heading workaround

The Things URL scheme **does not support**: creating standalone headings inside existing projects, renaming/deleting headings, or reordering tasks within a list. These all require AppleScript.

What the URL scheme *does* support:
- `things:///add?heading=Name` — adds a to-do under an *existing* heading (no auto-create).
- `things:///json?data=[{type:project, items:[{type:heading,...},{type:to-do,...}]}]` — creates a new project with headings in one shot.

`propose_reorder_todos` and real-heading mutations are deferred to step 5 (AppleScript layer). **Step 4b ships a URL-scheme-only interim solution: dummy heading tasks.**

#### Dummy heading convention (step 4b)

Title format: `__HEADING_NAME__` — leading and trailing double underscore, all uppercase between. Regex: `^__[A-Z][A-Z0-9 _\-:]*__$`.

| Operation | Dummy-heading behaviour | Real-heading behaviour |
| --- | --- | --- |
| `propose_add_heading(project_id, name)` | Adds a to-do titled `__NAME__` to the project at the requested position. Position controlled by an optional `after_todo_id` param. | Deferred to step 5 (AppleScript). |
| `propose_update_heading(heading_id_or_name, new_name)` | If target is a dummy task → URL-scheme `update?title=__NEW_NAME__&auth-token=...`. | Deferred to step 5. |
| `propose_delete_heading(heading_id_or_name)` | Soft-delete the dummy task via `update?canceled=true&completed=true`. | Deferred to step 5. |
| `get_project(project_id)` extension | Returns a unified `headings: [{kind: "native" \| "dummy", id, name, position}]` array. Dummy-heading tasks are still present in the project's `items` list (the user sees them as tasks in Things), but also surfaced as headings so the agent can reason about them. | Same shape. |
| Ambiguity resolution | When the user says "edit/delete heading X" and both a native heading named X AND a dummy `__X__` exist in the same project: `propose_*` returns a preview listing both candidates and asks the user to pick. | Same. |

Visual caveat: a `__COOKING__` task in the Things UI is rendered as a regular task (with its underscores visible), not as a native section divider. The user can swap a dummy for a real heading manually via the Things UI (`File > New Heading`) at any time; the MCP recognises both forms going forward.

#### Where the workaround fails

- Native-heading rename/delete still requires AppleScript (step 5).
- Dummy headings can be inadvertently completed by the user from the Things UI, which moves them to the Logbook. The MCP should treat completed dummy-heading tasks the same way Things would — as "gone."
- Headings inside an `add-project` JSON payload (creating a new project with native headings at birth) ARE supported by the URL scheme. `propose_add_project` will use the JSON endpoint when the input includes a `headings` array — no dummy fallback needed there.

---

## 6. Implementation Roadmap

### Phase 1 — V1: Read + Inbox-Create (target: working server end-to-end)

1. **Scaffold**
   - `pyproject.toml` (Python 3.11+, deps: `mcp`, `things.py`, `aiohttp`, `pydantic`).
   - Project layout (see §7).
   - `uv venv && uv sync`.
2. **State DB bootstrap** — `state/db.py` creates `~/.things-mcp/state.db` on first run with `pending_actions` and `undo_log` tables. Idempotent.
3. **Read layer** — `services/things_repo.py` wraps `things.py` with read-only DB connection, typed return shapes (Pydantic models).
4. **Read tools** — `tools/read.py`, all 13 tools from §5.1, each ≤15 lines.
5. **URL-scheme callback service** — `services/callbacks.py`: ephemeral aiohttp listener, nonce-keyed, 5s timeout, returns parsed `x-things-id`.
6. **Inbox write tool** — `tools/write.py::add_inbox_todo`. Hard-codes `list=inbox`. Verifies via `things_repo.get(uuid)` after callback.
7. **Health tool** — `tools/meta.py::health`.
8. **MCP entrypoint** — `server.py` instantiates FastMCP, registers tools, runs on stdio.
9. **End-to-end smoke test** — start server, connect from Claude Desktop, list Inbox, create a test todo, confirm it appears in Things UI and `list_inbox()` returns it.
10. **README** — install steps, env vars, client-config snippets for Claude Desktop, Claude Code, Cursor.

**V1 done = the agent can read the user's entire Things database and create test tasks in Inbox. No risk to existing projects.**

### Phase 2 — V2: Full Parity Writes + Two-Phase Safeguards

**Step 1 ✅** — `pending_actions` + `undo_log` CRUD in `state/` with `attach_target` helper for adds. Full pytest coverage.

**Step 2 ✅** — Handler registry (`services/handlers/`) + `confirm_action`, `cancel_action`, `list_pending_actions`, `undo`. Module-level tool functions for direct testability.

**Step 3 ✅** — `propose_add_todo` end-to-end with the V2 acceptance gate proven: undo-log row written before URL-scheme call, then patched with the polled UUID. Round-trip undo test green.

**Step 4 (next) — remaining `propose_*` tools + direct shortcuts + auto-confirm:**
1. Direct shortcuts: `add_today_todo`, `add_anytime_todo`, `add_someday_todo` (mirror V1 `add_inbox_todo` pattern).
2. `complete_todo(todo_id)` direct (single-target, reversible). Undo = `update?completed=false`.
3. `THINGS_MCP_AUTO_CONFIRM` env flag + never-bypass list for destructive kinds.
4. `propose_update_todo` (first non-add handler — establishes the "before-state snapshot for undo" pattern).
5. `propose_move_todo` (between lists / into projects via URL scheme `update?list=` / `list-id=`).
6. `propose_delete_todo` — soft-delete (URL scheme `update?canceled=true&completed=true`). Undo restores via `update?canceled=false&completed=false`.
7. `propose_add_project`, `propose_update_project` — URL scheme `add-project` / `update-project` (requires `THINGS_AUTH_TOKEN` for update). `add_project` supports a `headings: [...]` array routed through `things:///json` for native heading creation at project birth.
8. `propose_bulk_*` (delete / complete / move / update) — batch wrappers. Always require explicit confirm regardless of `THINGS_MCP_AUTO_CONFIRM`.

**Step 4b — dummy-heading interim layer (URL scheme only):**
1. `propose_add_heading(project_id, name, after_todo_id?)` → creates a `__NAME__` task at the requested position.
2. `propose_update_heading(heading_id_or_name, new_name)` → renames a dummy via `update?title=...`.
3. `propose_delete_heading(heading_id_or_name)` → soft-deletes a dummy.
4. Extend `get_project(...)` and other read tools to surface dummy headings in a unified `headings` array alongside native ones.
5. Document the visual caveat (dummies look like regular tasks in Things UI) in README + tool descriptions.

**Step 5 — opt-in AppleScript layer (`THINGS_MCP_ALLOW_APPLESCRIPT=1`):**
1. `services/applescript.py` — thin `osascript` wrapper, async via `asyncio.to_thread`.
2. Upgrade `propose_delete_todo` to use real `delete theTask` when flag is set.
3. `propose_reorder_todos` — URL scheme can't do this; AppleScript-only.
4. First-run permission popup is documented; `health()` reports `applescript_enabled` + `applescript_authorized`.

**Step 6 — native heading support (also AppleScript-dependent):**
1. Upgrade `propose_add_heading` to use AppleScript when flag is set — creates a real Things native heading (not a dummy task). Dummies remain valid alongside.
2. `propose_update_heading` upgrade — rename a native heading.
3. `propose_delete_heading` upgrade — delete a native heading.
4. `convert_dummy_to_native_heading(dummy_task_id)` — utility that creates a native heading at the dummy's position, moves any sub-tasks (if conventionally grouped), then deletes the dummy task.
5. `add_todo_under_heading(...)` — uses URL scheme `heading=` param (existing headings only); when AppleScript is on, can auto-create.

Verification expands at each step:
- Each new handler gets a `test_handler_<kind>.py` with execute / undo / preview tests.
- Each new propose tool gets a round-trip test in `test_dispatcher.py`.
- Each new manual checklist item appended to `tests/things-mcp-manual-verification.md`.
- Each build chunk ends with a **handoff doc** at `tests/handoff-<chunk-name>.md` containing the preflight checklist and numbered manual verification items for the Test user to run. See existing `tests/handoff-round-4-chunks-D-and-E.md` as the template.

### Phase 3 — Hardening

1. Schema-version compatibility check on startup (compare `TMTask` schema fingerprint to known-good fingerprints; warn the agent if Things has updated).
2. Structured logging to `~/.things-mcp/logs/` with redaction of task content above a verbosity threshold.
3. Optional: backup of `main.sqlite` to `~/.things-mcp/backups/` on first run of each session (defense in depth — Things has its own backup system but it's user-invisible).
4. Optional: Things app launch / focus helper if the URL scheme call fails because the app is quit.
5. Optional: AppleScript-based `reveal_in_things(todo_id)` for UX polish.
6. **Tag pre-validation** — before firing any URL-scheme call that accepts a `tags` param, validate each tag name against `get_tags()` and return a clear error if unknown. Surfaced in Round-4 testing: Things silently ignores unknown tags with no error, making the server appear to succeed when it hasn't. Affects `add_inbox_todo`, `add_*_todo`, `propose_update_todo`, `propose_bulk_update`.

---

## 7. Critical Files (V1)

```
things-mcp/
├── pyproject.toml
├── README.md
├── src/things_mcp/
│   ├── __init__.py
│   ├── server.py                  # FastMCP entrypoint
│   ├── config.py                  # env, paths, Things DB location resolution
│   ├── tools/
│   │   ├── read.py                # 13 read tools
│   │   ├── write.py               # add_inbox_todo (V1)
│   │   └── meta.py                # health, recent_undo_log
│   ├── services/
│   │   ├── things_repo.py         # things.py wrapper, typed returns
│   │   ├── url_scheme.py          # URL builder + open() launcher
│   │   └── callbacks.py           # aiohttp one-shot listener
│   ├── state/
│   │   ├── db.py                  # SQLite bootstrap + connection
│   │   ├── pending.py             # pending_actions CRUD (scaffold V1)
│   │   └── undo_log.py            # undo_log CRUD (scaffold V1)
│   └── models.py                  # Pydantic types: Todo, Project, Area, Tag
└── tests/
    ├── test_things_repo.py
    ├── test_callbacks.py
    └── test_add_inbox_todo.py     # end-to-end, requires Things running
```

**Reused dependencies (no need to reinvent):**
- `things.py::things.todos / projects / areas / tags / get / search` — entire read API.
- `mcp.server.fastmcp.FastMCP` — tool registration, stdio transport, schema generation.
- `asyncio.to_thread` — runs blocking `subprocess.run(["open", url])` without stalling the loop.

---

## 8. Verification Plan

V1 is "done" when each of these passes:

1. **Read smoke** — From Claude Desktop, ask the agent "what's in my Things Inbox?". Server returns the list; titles match the Things UI.
2. **Read depth** — Ask "show me my projects under area X with their headings". Returns hierarchy that matches the UI.
3. **Write happy path** — Ask "add a to-do 'MCP test 1' to my Inbox". Verify (a) tool returns an `id`, (b) the to-do appears in Things UI within ~1s, (c) `list_inbox()` returns it.
4. **Write edge cases** — Special chars in title (emoji, quotes, `&`), tags array, future `when` date, deadline, multi-line notes, checklist with 3 items.
5. **Callback timeout** — Quit Things, call `add_inbox_todo`, expect a clean error (not a hang) within 5s.
6. **Concurrent reads** — Open Things, edit a task, simultaneously call `get_todo(id)`. No DB lock errors.
7. **Cross-client** — Repeat (1) and (3) from Claude Code CLI and from Cursor. Identical behaviour.
8. **Schema check** — `health()` reports the Things DB path, app-running status, and `things.py` version.
9. **No accidental Inbox bypass** — Attempt to call the URL builder with a non-Inbox list in V1; assert it raises before launching.
10. **State DB isolation** — Delete `~/.things-mcp/state.db`; server recreates it cleanly on next start.

Each test gets one line in `tests/things-mcp-manual-verification.md` initially, then we promote them to `pytest` cases as the helpers stabilise.

---

## 9. Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| `things.py` lags a Things schema update | Wrap every call in `things_repo`; pin version; `health()` reports schema fingerprint. |
| URL scheme disabled by user | `health()` flags it; `add_inbox_todo` returns an actionable error with the settings path. |
| Callback listener port collision | Use `socket.bind(('127.0.0.1', 0))` to grab an ephemeral port per request. |
| V2 destructive bug deletes user data | V1's Inbox quarantine means we ship reads + safe writes before any destructive surface exists. V2 wraps every destructive op in propose/confirm + undo snapshot. |
| Backup of `main.sqlite` is not enabled by default | Cultured Code maintains its own backups; we add an optional session-start backup in Phase 3 as defense in depth. |
| Agent loops on confirm step | `pending_actions` rows expire after 5 min; we add a per-session cap (e.g. max 10 pending). |
| Things repeating-task edits silently fail via URL scheme | V2 only; AppleScript fallback gated behind a feature flag; documented limitation in V1. |

---

## 10. What I'm Discarding from the Original Brief

- **AppleScript as the primary write path** → replaced by the URL scheme. AppleScript moves to a narrow V2+ fallback.
- **`osascript display dialog` for confirmation** → replaced by two-phase confirm. Portable, non-blocking, conversational.
- **JSON file for the undo cache** → replaced by SQLite. Indexed lookups + atomic ops with no extra dependency.
- **"Tag-as-deleted" soft-delete shim** → unnecessary once we have the undo log with full before-state snapshots and the propose/confirm gate. V2 destructive ops move to Trash (Things-native, via AppleScript when enabled) and we restore from `undo_log`.
- **HTTP `x-callback-url` listener (`aiohttp` mini-server)** → replaced by DB polling. Reason: macOS routes `http://` callbacks through the default browser, opening a Safari tab per write. Polling has no UX side effect, removes the `aiohttp` dependency, and simplifies the write path. See §4.3.

What survives from the brief: the 3-layer split (read / write / safeguards), the local-only architecture, and the principle that every destructive action must be reversible.
