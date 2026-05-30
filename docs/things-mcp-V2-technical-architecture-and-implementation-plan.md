# Things 3 MCP Server — Technical Architecture & Implementation Plan

> **Master copy.** This file lives at `/Users/Shared/things-mcp/docs/things-mcp-V2-technical-architecture-and-implementation-plan.md`. Edit here, not in `~/.claude/plans/`.

## 0. Implementation Status (as of 2026-05-27)

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
| V2 step 4 chunk C — `propose_move_todo`, ~~`propose_delete_todo` (soft — removed, see Step 5A)~~ | ✅ Done | ✅ Verified (Round 3 — items 56/57 target-validation fix landed post-run) |
| V2 step 4 chunk D — `propose_add_project` (with headings via `things:///json`), `propose_update_project` | ✅ Done | ✅ Verified (Round 4 — 27/30 pass, 3 deferred; 0 blocking bugs; see `tests/V2-Round4-chunks-D-E-verification-2026-05-19.md`) |
| V2 step 4 chunk E — `propose_bulk_*` tools (complete/delete/move/update) | ✅ Done | ✅ Verified (Round 4 — same session; 0 blocking bugs) |
| V2 step 4b — dummy-heading interim layer (URL-scheme only) | ✅ Done | ✅ Verified (Round 5 — 227 tests pass; items 98–122 all pass; see tests/V2-step-4b-verification-2026-05-25.md) |
| V2 step 5A — opt-in AppleScript foundation + `propose_delete_todo` (hard-delete → Trash); soft-delete removed | ✅ Done (280 tests pass; `applescript.py`, `hard_delete_todo` handler renamed to `propose_delete_todo`, `health()` extended) | ✅ Verified (Round 7 — 2026-05-29; all items 131–135 pass incl. live delete+undo round-trip) |
| V2 step 5B — reorder todos in lists/projects (with native-heading auto-conversion to dummies at original positions) | ✅ Done (400 tests pass) | ✅ Verified (Round 10 — 2026-05-30; all items 5B-1 through 5B-7 pass) |
| V2 step 5C — checklist tools (`get_checklist_items`, append/prepend/replace via URL scheme) | ✅ Done (322→353 tests, +31) | ✅ Verified (Round 9 — 2026-05-30) |
| V2 step 5D — `propose_cancel_todo` + `propose_bulk_cancel` (renamed from bulk_delete) | ✅ Done (284→325 tests, +41) | n/a — unit tests only |
| V2 step 5E — `propose_cancel_project` (URL-scheme) + `propose_delete_project` (AppleScript → Trash) | ✅ Done (284→325 tests, +41) | ✅ Verified (Round 8 — 2026-05-30) |
| ~~V2 step 6~~ — native heading support via AppleScript | ❌ **Cancelled** — SDEF inspection confirmed Things 3 AppleScript has no `heading` class. Native-heading CRUD is impossible by any mechanism. Dummy headings (Step 4b) are the permanent solution. See §5.3 and §10. | n/a |
| **Pre-release fix A** — tag pre-validation for all write tools (see §11) | ✅ Done | ✅ Verified (Round 6 — 2026-05-26) |
| **Pre-release fix B** — tags missing from `get_project` / `get_todo` responses (see §11) | ✅ Done | ✅ Verified (Round 6 — 2026-05-26) |
| Round-4 deferred items #73, #82, #97 — error-path manual verification | n/a — no build needed | ⏳ Run during Round-5 preflight (config-change + restart sequence) |

Automated suite: 280 tests, ~1.9s, hermetic (no real Things DB / URL launches).

### Round-4 deferred items — how to close them
Items #73, #82, #97 require a config-change + session restart (token removal or `AUTO_CONFIRM` flag toggle). All three test error paths already covered by unit tests. Run at the top of the Round-5 Test-user session before the main 4b checklist:
1. Unset `THINGS_AUTH_TOKEN` → restart MCP server → run items #73 + #82.
2. Restore `THINGS_AUTH_TOKEN` → restart → set `THINGS_MCP_AUTO_CONFIRM=1` → restart → run item #97 → restore flag.

### Pre-release requirements surfaced in Round 4
Both items below **must ship before public release**. They are not blockers for steps 4b / 5A / 5B / 5C, but they must be fixed and manually verified before the server is published. Full implementation detail is in §11.

- **Fix A — Unknown tags silently no-op:** `add_inbox_todo` and `propose_bulk_update` (and all other write tools accepting `tags`) report success even when a supplied tag name doesn't exist in Things — Things URL scheme silently ignores unknown tags. A public user has no way to know their tag was dropped. Fix: pre-validate every tag name against `get_tags()` before firing the URL scheme and return a clear error listing available tags if any are unknown.
- **Fix B — Tags missing from read responses:** `get_project` and `get_todo` return no tag data, meaning an agent cannot tell the user what tags a task has. Root cause is either a `things-py` gap or a missing field in our `things_repo` response shaping — needs diagnosis. Fix: augment responses with a direct read-only SQLite tag lookup if `things-py` doesn't supply them.

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
| `propose_reorder_todos(container, new_order)` (step 5B) | `confirm_action` | Single tool with smart container routing: built-in list name (`"Today"`) → `list "Today"`; otherwise project UUID → `project id "X"`. Uses the hidden AppleScript reorder command (see §12). Native-heading projects auto-convert natives to dummies at their original positions; empty natives left at bottom for manual user cleanup. |
| `complete_todo(todo_id)` (direct, single-target) | n/a — no airlock | Reversible (`update?completed=false`). Most common everyday op. |
| `propose_bulk_complete([todo_id, ...])` | `confirm_action` | Bulk = preview valuable; never bypassable. |
| `propose_delete_todo(todo_id)` (step 5A) | `confirm_action` — **never bypassable** | AppleScript `delete (to do id "X")` → moves to Things Trash (recoverable from Trash for 30 days). Requires `THINGS_MCP_ALLOW_APPLESCRIPT=1`. Replaces the old URL-scheme soft-delete (removed). |
| `propose_cancel_todo(todo_id)` (step 5D) | `confirm_action` | URL scheme `update?canceled=true` → moves to Logbook without deleting. Reversible. No AppleScript required. |
| `propose_bulk_*(...)` | `confirm_action` — **never bypassable** | Multi-target = high blast radius. |
| `propose_add_project(...)` | `confirm_action` | Project creation supports headings via `things:///json` payload. |
| `propose_update_project(...)` | `confirm_action` | Edits live project. |
| `propose_cancel_project(project_id)` (step 5E) | `confirm_action` | URL scheme `update-project?canceled=true` → project moves to Logbook. Reversible. No AppleScript required. |
| `propose_delete_project(project_id)` (step 5E) | `confirm_action` — **never bypassable** | AppleScript `delete (project id "X")` → project (and all its tasks) moves to Things Trash. Requires `THINGS_MCP_ALLOW_APPLESCRIPT=1`. |
| `propose_add_heading(project_id, name)` (dummy-only, **permanent**) | `confirm_action` | Creates a `__NAME__` dummy task. Native headings inside an *existing* project are not creatable by any scripted mechanism — AppleScript has no `heading` class. See §5.3 and §10. |
| `propose_update_heading(...)`, `propose_delete_heading(...)` (dummy-only, **permanent**) | `confirm_action` | Operate only on dummy `__NAME__` tasks via URL scheme. Native headings are not mutable by any scripted mechanism. |
| `propose_append_checklist_items(todo_id, items)` (step 5C) | `confirm_action` | URL scheme `&append-checklist-items=...`. Reversible via `propose_replace_checklist` to prior snapshot. |
| `propose_prepend_checklist_items(todo_id, items)` (step 5C) | `confirm_action` | URL scheme `&prepend-checklist-items=...`. Same undo strategy. |
| `propose_replace_checklist(todo_id, items)` (step 5C) | `confirm_action` — **never bypassable** | URL scheme `update?checklist-items=...` overwrites entire checklist. Undo restores prior snapshot. |

**Dispatcher / inspection tools:**

| Tool | Purpose |
| --- | --- |
| `confirm_action(action_id)` | Execute a pending action. Dispatches by `kind` to the handler registry. |
| `cancel_action(action_id)` | Drop a pending action. |
| `list_pending_actions()` | Inspect the queue. |
| `undo(undo_id?: str)` | Reverse the most recent (or specified) action by ID. |

**Auto-confirm escape hatch (`THINGS_MCP_AUTO_CONFIRM`):**

When the env var `THINGS_MCP_AUTO_CONFIRM=1` is set, any tool returning a `propose_*` action_id is immediately confirmed inside the same MCP call — the preview is still surfaced to the agent (so the LLM can summarize before responding) but no second round-trip is required. **Exceptions:** `propose_delete_todo`, `propose_bulk_*`, and `propose_replace_checklist` always require an explicit `confirm_action` call regardless of this flag. The "never bypassable" column above marks these.

**Why two-tier and not one or the other:**
- Pure airlock is too high-friction for everyday adds.
- Pure direct tools lose the structured preview / pre-mutation undo-log row that the airlock guarantees for destructive ops.
- Host-level permissions (Claude Desktop "ask / allow / deny" per tool) sit *on top* of both tiers and are the user's primary "I trust this MCP" knob.

### 5.3 Heading & reorder & checklist limitations — and the dummy-heading permanent layer

**Settled facts from SDEF inspection (2026-05-27):** Things 3 AppleScript has **no `heading` class and no `checklist item` class.** Native-heading CRUD and granular checklist-item operations are therefore impossible by any scripted mechanism — neither URL scheme nor AppleScript exposes them. The dummy heading layer shipped in Step 4b is **the permanent solution, not an interim**; the previously-planned Step 6 has been cancelled.

#### What IS possible (and how)

| Capability | Mechanism |
| --- | --- |
| Create a native heading inside a *new* project (at project birth) | URL scheme `things:///json` payload — already used by `propose_add_project`. |
| Read native heading titles + positions | `things-py` SQLite read — `things_repo.get_project_with_headings` returns unified `[{kind, id, name, position}]`. |
| Add a to-do under an *existing* native heading | URL scheme `things:///add?heading=Name`. |
| Reorder todos within a list or project | Hidden AppleScript command (see §12). Gated behind `THINGS_MCP_ALLOW_APPLESCRIPT=1` AND `THINGS_MCP_ALLOW_EXPERIMENTAL_REORDER=1`. |
| Hard-delete a todo (move to Things Trash) | AppleScript `delete <todo>`. Recoverable from Trash for 30 days. |
| Read a task's checklist items | `things-py` SQLite read — surfaced by `get_checklist_items`. |
| Append / prepend / replace an entire checklist | URL scheme `&append-checklist-items=` / `&prepend-checklist-items=` / `update?checklist-items=`. |

#### Hard limitations — NOT possible by any mechanism

- **Native heading CRUD inside an existing project** — create, rename, delete. AppleScript has no `heading` class.
- **Checklist item granular operations** — edit one item's title, complete/uncomplete one item, delete one item, reorder items. No `checklist item` class in AppleScript; URL scheme is all-or-nothing.
- **Project reorder within an area** — projects have no positional property in the SDEF.
- **Area reorder in the sidebar** — same.
- **Empty native heading cleanup after reorder** — when reorder runs on a project containing native headings, the natives are displaced to the bottom of the project and left empty. We can't delete them; the user must remove them manually in the Things UI.

#### Dummy heading convention (permanent — Step 4b)

Title format: `__HEADING_NAME__` — leading and trailing double underscore, all uppercase between. Regex: `^__[A-Z][A-Z0-9 _\-:]*__$`.

| Operation | Dummy-heading behaviour | Native-heading behaviour |
| --- | --- | --- |
| `propose_add_heading(project_id, name)` | Adds a to-do titled `__NAME__` to the project. Position can be set via Step 5B reorder after creation. | Not possible — no `heading` class in AppleScript. |
| `propose_update_heading(heading_id_or_name, new_name)` | If target is a dummy task → URL-scheme `update?title=__NEW_NAME__&auth-token=...`. | Not possible. |
| `propose_delete_heading(heading_id_or_name)` | Soft-delete the dummy task via `update?canceled=true&completed=true`. | Not possible. |
| `get_project(project_id)` extension | Returns a unified `headings: [{kind: "native" \| "dummy", id, name, position}]` array. | Same shape. |
| Ambiguity resolution | When user says "edit/delete heading X" and both a native heading X AND a dummy `__X__` exist in the same project: `propose_*` returns a preview listing both and asks the user to pick. Only the dummy is actionable; selecting the native returns an explanatory error. | Same. |

Visual caveat: a `__COOKING__` task in the Things UI is rendered as a regular task (with its underscores visible), not as a native section divider. The user can swap a dummy for a real heading manually via the Things UI (`File > New Heading`) at any time; the MCP recognises both forms going forward.

#### Reorder + native headings — the auto-conversion flow (Step 5B)

When `propose_reorder_todos` targets a project containing native headings:

1. **Propose-time:** detect the natives, build a `dummy_creation_plan` of `[{name, target_position}]` — one entry per native at the native's original position in the project's items array.
2. **Execute-time:** create one dummy `__NAME__` task per native at the appropriate slot, splice into the master UUID list, then run the hidden reorder command.
3. **Side effect:** the natives are displaced to the bottom of the project, empty. The MCP cannot delete them; the user removes them manually.
4. **Undo:** restores the original task order and soft-deletes the dummies, but cannot reinstate the natives' inline positions. The propose preview must surface this irreversibility caveat before the user confirms.

#### Where the dummy approach still leaks

- Dummy headings can be inadvertently completed by the user from the Things UI, which moves them to the Logbook. The MCP should treat completed dummy-heading tasks the same way Things would — as "gone."
- Headings inside an `add-project` JSON payload (creating a new project with native headings at birth) ARE supported by the URL scheme. `propose_add_project` will use the JSON endpoint when the input includes a `headings` array — no dummy fallback needed there. The resulting natives are then read-only forever (no rename/delete via script).

### 5.4 Checklist support (Step 5C)

Things 3 task checklists are surfaced read-only via `things-py` and mutable via URL scheme at the *whole-checklist* granularity. Per-item editing, completion, deletion, and reordering are **not supported by Things' scripting surface** and therefore not exposed by the MCP.

| Tool | Mechanism | Notes |
| --- | --- | --- |
| `get_checklist_items(todo_id)` | `things-py` SQLite read | Direct read tool (no airlock). Returns `[{title, completed, position}]` in order. |
| `propose_append_checklist_items(todo_id, items)` | URL scheme `&append-checklist-items=` | Items joined with `\n`. URL-encoded. Undo via `replace_checklist` to prior snapshot. |
| `propose_prepend_checklist_items(todo_id, items)` | URL scheme `&prepend-checklist-items=` | Same. |
| `propose_replace_checklist(todo_id, items)` | URL scheme `update?checklist-items=...` | **Never bypassable** (overwrites entire list). Undo restores prior snapshot. |

Tool docstrings + README must explicitly state: *"To change a single item, replace the entire checklist."*

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
6. ~~`propose_delete_todo` — soft-delete (URL scheme `update?canceled=true&completed=true`)~~ — **removed in Step 5A**. Replaced by AppleScript hard-delete (→ Trash). Cancel-without-delete arrives in Step 5D.
7. `propose_add_project`, `propose_update_project` — URL scheme `add-project` / `update-project` (requires `THINGS_AUTH_TOKEN` for update). `add_project` supports a `headings: [...]` array routed through `things:///json` for native heading creation at project birth.
8. `propose_bulk_*` (delete / complete / move / update) — batch wrappers. Always require explicit confirm regardless of `THINGS_MCP_AUTO_CONFIRM`.

**Step 4b — dummy-heading interim layer (URL scheme only):**
1. `propose_add_heading(project_id, name, after_todo_id?)` → creates a `__NAME__` task at the requested position.
2. `propose_update_heading(heading_id_or_name, new_name)` → renames a dummy via `update?title=...`.
3. `propose_delete_heading(heading_id_or_name)` → soft-deletes a dummy.
4. Extend `get_project(...)` and other read tools to surface dummy headings in a unified `headings` array alongside native ones.
5. Document the visual caveat (dummies look like regular tasks in Things UI) in README + tool descriptions.

**Step 5 — opt-in AppleScript layer + checklist tools. Split into three sub-chunks for incremental Test-user verification rounds.** Detailed implementation plan in `/Users/joshsmith/.claude/plans/review-docs-things-mcp-v2-technical-arch-declarative-hennessy.md`.

**Step 5A — AppleScript foundation + `propose_delete_todo` (hard-delete → Trash):** ✅ Done
1. `services/applescript.py` — thin async `osascript` wrapper with hardened escaping (`"` → `\"`, `\` → `\\`, reject control chars). `verify_authorization()` runs a no-op script, caches result.
2. Two env flags in `config.py`: `THINGS_MCP_ALLOW_APPLESCRIPT` (gates all AppleScript) and `THINGS_MCP_ALLOW_EXPERIMENTAL_REORDER` (gates the hidden reorder command — see §12). Both default off.
3. `services/handlers/hard_delete_todo.py` (KIND `"delete_todo"`) — propose snapshots current state, execute runs AppleScript `delete (to do id "X")` (moves to Things Trash), undo runs multi-line AppleScript `move (to do id "X") to list/project`. Always on `NEVER_BYPASS_KINDS`.
4. `propose_delete_todo(todo_id)` in `tools/propose.py` — replaces the old URL-scheme soft-delete (Step 4C) which is now removed. This is the canonical delete tool.
5. `health()` extended with `applescript_enabled`, `experimental_reorder_enabled`, `applescript_authorized`, `reorder_command_available` (SDEF grep for `THGSreot`, cached).
6. **Soft-delete removed:** `propose_delete_todo` formerly marked tasks `canceled+completed` (→ Logbook). That tool and its handler are now tombstoned. To cancel (not delete) a task, see Step 5D.

**Step 5D — `propose_cancel_todo` + `propose_bulk_delete` cleanup (URL-scheme only):**
Cancel a task natively (Things "Cancel" action) without deleting it. Also fixes `propose_bulk_delete` which still uses the old soft-delete approach.
1. `services/url_scheme.py` — add `build_cancel_url(id, auth_token)` that sets `canceled=True` only (not `completed=True`).
2. `services/handlers/cancel_todo.py` — execute sets `canceled=True`; undo restores `canceled=False`. Snapshot before-state so undo is clean. NOT in `NEVER_BYPASS_KINDS` (cancelling is reversible and low-risk).
3. `propose_cancel_todo(todo_id)` in `tools/propose.py`.
4. **`propose_bulk_delete` fix:** the `bulk_delete` handler currently uses the old soft-delete mechanism (marks `canceled+completed` → Logbook). Decide and implement one of: (a) update it to use the AppleScript hard-delete path (requires `ALLOW_APPLESCRIPT=1`, moves batch to Trash) — consistent with `propose_delete_todo`; or (b) rename/re-describe it as `propose_bulk_cancel` to honestly reflect the behaviour. Whichever is chosen, the handler, tests, and tool docstring must all agree.
5. Unit tests sufficient for both — no manual testing session needed. Add to automated suite.

**Step 5E — `propose_delete_project` + `propose_cancel_project` (URL-scheme only):**
Currently there is no way to delete or cancel a whole project through the MCP. Things URL scheme supports both operations.
1. `propose_cancel_project(project_id)` — sets `canceled=True` on the project via URL scheme → project moves to Logbook. Undo restores `canceled=False`. NOT in `NEVER_BYPASS_KINDS`.
2. `propose_delete_project(project_id)` — AppleScript `delete (project id "X")` → project moves to Things Trash (same mechanics as `propose_delete_todo`). Requires `THINGS_MCP_ALLOW_APPLESCRIPT=1`. Always `NEVER_BYPASS_KINDS`. Undo uses `move (project id "X") to list "X"`.
3. Note: deleting a project via AppleScript moves the project *and all its tasks* to Trash as a unit. Confirm this behaviour in Things SDEF before implementing; document clearly in the tool preview.
4. Unit tests sufficient for both — no manual testing session needed for cancel (URL scheme). The hard-delete (AppleScript) path should be smoke-tested in the Test account as part of the same session that closes Step 5A (add item to `test_step5a_live.py` or a new `test_step5e_live.py`).

**Step 5B — reorder todos (with native-heading auto-conversion):**
1. `services/reorder.py` — `build_master_order()` for the Unified Master List Overwrite strategy (partial reorders preserve surrounding positions); `detect_native_headings()`; `resolve_container()` for smart list-vs-project routing.
2. `services/handlers/reorder_todos.py` — propose-time heading detection (NOT execute-time), dummy_creation_plan built into the payload, race-window check on execute, verification re-read after AppleScript runs.
3. `propose_reorder_todos(container, new_order)` in `tools/write.py` — single tool, smart routing.
4. Hidden AppleScript reorder command used internally; never named in user-facing surfaces (see §12).

**Step 5C — checklist tools (URL scheme only, no AppleScript needed):**
1. `services/url_scheme.py` — add `build_append_checklist_url`, `build_prepend_checklist_url`, `build_replace_checklist_url`.
2. `services/things_repo.py::get_checklist_items(todo_id)`.
3. Three handlers (`append_checklist.py`, `prepend_checklist.py`, `replace_checklist.py`) — undo strategy is snapshot-then-replace.
4. Tools: direct `get_checklist_items`, plus `propose_append_checklist_items`, `propose_prepend_checklist_items`, `propose_replace_checklist` (last is `NEVER_BYPASS_KINDS`).
5. README and tool docstrings explicitly document the per-item-edit/delete/reorder limitations.

**Step 6 — CANCELLED.** Originally planned for AppleScript-based native heading CRUD + dummy→native converter. SDEF inspection on 2026-05-27 confirmed Things 3 AppleScript has no `heading` class; native heading creation/rename/deletion inside an existing project is impossible by any scripted mechanism. Dummy headings (Step 4b) are therefore the permanent solution. See §5.3 and §10.

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
- **Native heading CRUD via AppleScript (originally Step 6)** → cancelled. SDEF inspection on 2026-05-27 confirmed Things 3 AppleScript has no `heading` class — creating, renaming, or deleting native headings inside an existing project is impossible by any scripted mechanism. The dummy heading layer shipped in Step 4b is the permanent solution. See §5.3.
- **Granular checklist item operations (per-item edit / delete / completion / reorder)** → not buildable. Things 3 AppleScript has no `checklist item` class, and the URL scheme operates at whole-checklist granularity only. Step 5C exposes append/prepend/replace + read; document the limitation in tool descriptions.

What survives from the brief: the 3-layer split (read / write / safeguards), the local-only architecture, and the principle that every destructive action must be reversible.

---

## 11. Pre-release Fixes (must ship before public release)

Both fixes are self-contained and can be built together in one session after step 5C, or pulled forward into an earlier session if convenient. Neither touches the propose/confirm plumbing.

---

### Fix A — Tag pre-validation for write tools

**Problem:** All write tools that accept a `tags` parameter (`add_inbox_todo`, `add_today_todo`, `add_anytime_todo`, `add_someday_todo`, `propose_update_todo`, `propose_bulk_update`) silently succeed even when a supplied tag name doesn't exist in Things. The Things URL scheme drops unknown tags without any error signal. A public user who misspells a tag name or uses a tag that hasn't been created yet receives a success response but their tag is never applied.

**Root cause:** The URL scheme itself — not a things-mcp bug. The fix must live in things-mcp as a pre-flight validation step.

**Fix — implementation steps:**

1. Add a helper to `services/things_repo.py`:
   ```python
   def get_tag_names() -> set[str]:
       """Return the set of all tag names currently in Things (case-sensitive)."""
       return {t["title"] for t in things.tags()}
   ```

2. Add a validator in `services/url_scheme.py` (or a new `services/validators.py`):
   ```python
   def validate_tags(requested: list[str]) -> None:
       """Raise ValueError with actionable message if any tag doesn't exist."""
       known = things_repo.get_tag_names()
       unknown = [t for t in requested if t not in known]
       if unknown:
           raise ValueError(
               f"Unknown tag(s): {unknown}. "
               f"Available tags: {sorted(known)}. "
               "Create the tag in Things first, then retry."
           )
   ```

3. Call `validate_tags(tags)` in every write tool that accepts a `tags` param, **before** the URL is built and fired. For `propose_*` tools, validate at propose time (not confirm time) so the user gets the error immediately.

4. Add unit tests in a new `tests/test_tag_validation.py`:
   - `validate_tags([])` → no-op.
   - `validate_tags(["Errand"])` with `Errand` in mocked `get_tag_names()` → no-op.
   - `validate_tags(["Errand", "FakeTag"])` → raises `ValueError` naming `FakeTag` and listing known tags.
   - Integration: call `add_inbox_todo` with an unknown tag → error returned before URL fires (assert `subprocess.run` not called).

**Manual verification items to add to `tests/things-mcp-manual-verification.md`:**
- Call `add_inbox_todo` with `tags=["NonExistentTag"]` → server returns a clear error naming the bad tag and listing available ones. Things UI unchanged.
- Call `add_inbox_todo` with `tags=["Errand"]` (real tag) → succeeds, tag appears on task in Things UI.
- Call `propose_bulk_update` with a mix of real and fake tags → error returned at propose stage, no pending action created.

---

### Fix B — Tags missing from `get_project` / `get_todo` read responses

**Problem:** `get_project` and `get_todo` return no tag data. When a user asks "what tags does this task have?", the agent cannot answer. In Round-4 testing, tag verification required falling back to direct SQLite reads — meaning the data is in the DB, but things-mcp isn't surfacing it.

**Diagnosis step (do this first):**

Check whether `things-py` already provides tags and we're just not forwarding them, or whether the library genuinely omits them:

```python
import things
task = things.get("SOME_TASK_UUID")
print(task)  # does "tags" key appear? is it populated?

todos = things.todos(start="Inbox")
print(todos[0])  # same check
```

Run this against the Test account Things DB. Two outcomes:

- **Outcome A — `things-py` does return tags:** The fix is purely in `things_repo.py` — ensure the `tags` field is included in the dict we return from `get_todo()` and `get_project()` item lists. Add it to the relevant Pydantic model in `models.py`.

- **Outcome B — `things-py` doesn't return tags:** Augment with a direct read-only SQLite query. The Things 3 DB schema stores tags via a join table. Query pattern (adapt column names by inspecting schema with `.schema TMTask` etc.):

  ```python
  import sqlite3, things

  def _fetch_tags_for_uuid(db_path: str, uuid: str) -> list[str]:
      """Read-only supplementary tag lookup for a single task UUID."""
      sql = """
          SELECT t.title
          FROM TMTag t
          JOIN TMTaskTag tt ON tt.tags = t.uuid
          WHERE tt.tasks = ?
          ORDER BY t.title
      """
      with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
          conn.execute("PRAGMA query_only = ON")
          rows = conn.execute(sql, (uuid,)).fetchall()
      return [r[0] for r in rows]
  ```

  > **Note:** Verify exact table and column names by running `SELECT name FROM sqlite_master WHERE type='table'` and `.schema TMTag` / `.schema TMTaskTag` against the real Things DB before writing the query. The names above are best-guess from community schema references and may differ between Things versions.

  Call `_fetch_tags_for_uuid` inside `things_repo.get_todo()` and inside the item-iteration loop in `things_repo.get_project()` to annotate each task with its tags before returning.

**Unit tests to add:**
- Mock the SQLite tag-lookup (or `things.get`) to return tags → assert `get_todo` response includes `tags: ["Errand", "Home"]`.
- Task with no tags → `tags: []` (not absent, not `None`).
- `get_project` → each item in the returned task list includes a `tags` field.

**Manual verification items to add to `tests/things-mcp-manual-verification.md`:**
- Tag a task in Things UI with "Errand". Call `get_todo(uuid)` → response includes `tags: ["Errand"]`.
- Call `get_project(project_uuid)` where one task has tags → that task's entry includes its tags.
- Task with no tags → `get_todo` returns `tags: []`.

---

### Scheduling these fixes

Suggested sequencing:

| When | What |
| --- | --- |
| After step 5C is verified | Build Fix A + Fix B together in one session |
| Same session | Add unit tests for both |
| Same session | Produce handoff doc `tests/handoff-pre-release-fixes.md` |
| Test-user session | Manual verification of Fix A + Fix B items |
| On pass | Mark both rows ✅ in status table → server is release-ready |

> **Note (2026-05-27):** Fixes A and B were originally listed as Round-6 verified in the §0 status table. They are already done — this section is retained for historical context. If a blocking bug surfaces during steps 5A–5C that touches the tag or read layer, treat it as a regression and patch immediately.

---

## 12. Internal-only implementation notes (NOT for README, NOT for public tool docs)

This section is for contributors who clone and audit the repo. **Do not surface any of this in the README, public tool descriptions, log messages, or user-facing error strings.** It is the project's competitive differentiator versus other public Things-MCP implementations on GitHub.

### The hidden reorder command

Things 3's AppleScript dictionary contains a hidden, experimental command that is the only known mechanism for reordering todos within a list or project:

```
_private_experimental_ reorder to dos in <list|project> with ids "<UUID1>,<UUID2>,..."
```

- SDEF event code: `THGSreot`. `hidden="yes"`. `responds-to` declared on both `list` and `project` classes.
- The command accepts a comma-separated string of todo UUIDs and pins them to the top of the container in the supplied order. Unlisted todos fall to the bottom in their existing relative order.
- Empirically verified to write the new order persistently (survives Things restart) and to fire Things Cloud sync.
- Discoverable via `sdef /Applications/Things3.app | grep -A 5 reorder`.

### Why we keep this internal

- Cultured Code has not documented this command and has not stated an intent to expose reorder publicly. The `_private_experimental_` prefix and `hidden="yes"` flag make removal at any future Things release a realistic possibility.
- Multiple competing public Things-MCP repos do not implement reorder; the convention in that ecosystem is "reorder is not possible." Keeping the mechanism internal preserves a meaningful capability differentiator.
- The MCP gates the command behind `THINGS_MCP_ALLOW_EXPERIMENTAL_REORDER=1` (in addition to the base `THINGS_MCP_ALLOW_APPLESCRIPT=1`) and runs a startup SDEF grep for `THGSreot` so that disappearance in a future Things release surfaces immediately as a `reorder_command_available: false` field in `health()`, not as a silent failure.

### What may be said publicly

- README: "The MCP can reorder todos within Things lists and projects when AppleScript is enabled." That is the entire public statement on the mechanism.
- Tool docstrings: same — describe the *capability*, not the *implementation*.
- Log messages and error strings: name only the high-level tool (`propose_reorder_todos`), not the AppleScript command. Avoid `_private_experimental_` and `THGSreot` anywhere a user could see them.

### Where the command is referenced in code

To be populated by the implementation session(s). Expected sites: `services/applescript.py` (the call site), `services/handlers/reorder_todos.py`, `tools/meta.py` (health-check grep). Internal code comments may name the command freely; user-facing strings must not.

### Migration plan if/when Cultured Code adds an official reorder API

1. Verify the new API behaviour matches our existing semantics (or document differences).
2. Swap the call site in `services/applescript.py` to the public command.
3. Retire the `THINGS_MCP_ALLOW_EXPERIMENTAL_REORDER` flag and the SDEF grep.
4. README can then describe the capability without caveat; this section can be retired.
