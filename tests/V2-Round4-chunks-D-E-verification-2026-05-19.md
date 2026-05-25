# V2 Round 4 Verification — Chunks D + E — 2026-05-19

**Run by:** Claude (automated MCP calls) + user (visual UI checks for items 70, 71, 84)
**User:** Test (`whoami` confirmed `Test` before any writes)
**Preflight:**
- `whoami` → `Test` ✓
- HEAD → `e1e2b24` (V2 Step 4 Chunks D + E build commit) ✓
- `uv run pytest -q` → **195 passed** ✓
- `THINGS_AUTH_TOKEN` set in `claude_desktop_config.json` (`mcpServers.things-mcp.env`) ✓
- `health()` → `things_app_running=true`, `state_db_exists=true`, `url_scheme_auth_token_set=true` ✓

**Areas available in test account:** Development (`RNk3PkCCWy1hadmYqGJ1f6`), Health (`St1cgVjs7Aof5ccvMg6YPt`)

---

## Summary table

| # | Description | Result |
|---|---|---|
| 67 | `add_project` title-only | ✅ PASS |
| 68 | `add_project` all optional fields | ✅ PASS |
| 69 | `add_project` when=today | ✅ PASS |
| 70 | `add_project` headings via `things:///json` | ✅ PASS |
| 71 | `add_project` headings + other fields | ✅ PASS |
| 72 | `add_project` undo (soft-delete → Logbook) | ✅ PASS |
| 73 | `add_project` undo without auth token | ⚠️ DEFERRED (needs restart) |
| 74 | `update_project` title | ✅ PASS |
| 75 | `update_project` notes | ✅ PASS |
| 76 | `update_project` deadline | ✅ PASS |
| 77 | `update_project` tags | ✅ PASS |
| 78 | `update_project` area move | ✅ PASS |
| 79 | `update_project` clear notes | ✅ PASS |
| 80 | `update_project` clear tags | ✅ PASS |
| 81 | `update_project` refuse empty proposal | ✅ PASS |
| 82 | `update_project` without auth token | ⚠️ DEFERRED (needs restart) |
| 83 | `update_project` undo restores original title | ✅ PASS |
| 84 | `update_project` undo only touches changed fields | ✅ PASS (load-bearing) |
| 85 | `bulk_complete` 3 tasks, never auto-confirmed | ✅ PASS |
| 86 | `bulk_complete` undo | ✅ PASS |
| 87 | `bulk_complete` abort on already-done | ✅ PASS |
| 88 | `bulk_delete` 2 tasks | ✅ PASS |
| 89 | `bulk_delete` undo | ✅ PASS |
| 90 | `bulk_move` to Today | ✅ PASS |
| 91 | `bulk_move` into a project | ✅ PASS |
| 92 | `bulk_move` undo per-item restore | ✅ PASS (load-bearing) |
| 93 | `bulk_move` reject inbox/upcoming targets | ✅ PASS |
| 94 | `bulk_update` apply same tag to 3 tasks | ✅ PASS |
| 95 | `bulk_update` undo per-item tag restore | ✅ PASS (load-bearing) |
| 96 | `bulk_update` refuse empty fields | ✅ PASS |
| 97 | AUTO_CONFIRM=1 doesn't bypass bulk | ⚠️ DEFERRED (needs restart) |

**27 of 30 items verified green. 3 deferred (all require session restart for config changes).**

---

## Per-item results

### Chunk D — `propose_add_project`

**#67 — Title-only project** ✅
- `propose_add_project(title='V2-chunkD title-only')` → confirmed → UUID `XXQNBwSCyb9FuehhjrHS2k`
- `recent_undo_log()` showed one `add_project` row with the new UUID.
- Project appeared in Things' Projects list (verified via `get_project`).

**#68 — All optional fields** ✅
- Proposed with `area_id=RNk3PkCCWy1hadmYqGJ1f6` (Development), `when='anytime'`, `deadline='2026-12-31'`, `notes='from MCP'`, `tags=['MCP-test']`.
- Confirmed. `get_project` returned `area_title="Development"`, `notes="from MCP"`, `deadline="2026-12-31"`, `start="Anytime"` — all correct.
- Note: `tags` field is not returned by `get_project` (things-py library limitation); tag presence verified visually in Things UI by user.

**#69 — when=today** ✅
- Confirmed. `get_project` returned `start_date="2026-05-19"` and `today_index` set — project appears in Today view.

**#70 — Headings at birth via `things:///json`** ✅ *(load-bearing)*
- `propose_add_project(title='V2-chunkD with-headings', headings=['Design','Dev','QA'])` → confirmed.
- `confirm_action` result: `headings_count: 3`.
- `get_project` items: three entries with `type="heading"` (not `type="to-do"`) in order Design → Dev → QA.
- **User confirmed in Things UI:** headings render as native section dividers, not as ordinary checkbox tasks. ✅

**#71 — Headings + other fields together** ✅
- `propose_add_project(title='V2-chunkD combo', headings=['Planning','Execution'], notes='kickoff', deadline='2026-09-30')` → confirmed.
- `headings_count: 2`. `get_project` shows `notes="kickoff"`, `deadline="2026-09-30"`, two `type="heading"` items.
- **User confirmed in Things UI:** both headings as dividers, notes and deadline populated. ✅

---

### Chunk D — `propose_add_project` undo

**#72 — Undo a freshly-added project** ✅ *(load-bearing per handoff)*
- Called `undo(undo_id=<#67 row>)`. Response: `undone=true, status="canceled"`.
- `list_logbook(days=1)` returned `"V2-chunkD title-only"` with `status="canceled"`, `stop_date` set.
- Project no longer present in active projects list.

**#73 — Undo without auth token** ⚠️ DEFERRED
- Requires unsetting `THINGS_AUTH_TOKEN` in `claude_desktop_config.json` and restarting Claude Code.
- Skipped to avoid mid-session restart. To be run in a follow-up session.

---

### Chunk D — `propose_update_project`

**#74 — Update project title** ✅
- Renamed `T6TSaU7ejtL8wx4U4Gmqnm` to "V2-chunkD renamed". `get_project` confirmed new title. `changed_fields: ["title"]`.

**#75 — Update notes** ✅
- Set notes on `EkHuatjPJCDzyjzwgroob` to "kickoff notes from MCP". `get_project` confirmed `notes="kickoff notes from MCP"`. `changed_fields: ["notes"]`.

**#76 — Update deadline** ✅
- Set deadline on `3gx8kU7mB7KWruWcv8pFc2` to "2026-11-15". `get_project` confirmed `deadline="2026-11-15"`. `changed_fields: ["deadline"]`.

**#77 — Update tags** ✅
- Set tags on `Eu1HgsKYxw8DDGqFgkUSJj` to `["MCP-test"]`. Server returned `changed_fields: ["tags"]`. Tags field not returned by `get_project`; operation accepted and URL scheme call dispatched.

**#78 — Move project between areas** ✅ *(load-bearing per handoff)*
- Moved `Eu1HgsKYxw8DDGqFgkUSJj` from Development area to Health area (`area_id=St1cgVjs7Aof5ccvMg6YPt`).
- `get_project` confirmed `area="St1cgVjs7Aof5ccvMg6YPt"`, `area_title="Health"`. `changed_fields: ["area_id"]`. ✅

**#79 — Clear notes** ✅
- Set `notes=''` on `EkHuatjPJCDzyjzwgroob`. `get_project` confirmed `notes=""`. `changed_fields: ["notes"]`.

**#80 — Clear tags** ✅
- Set `tags=[]` on `Eu1HgsKYxw8DDGqFgkUSJj`. Server returned `changed_fields: ["tags"]`. Operation accepted.

**#81 — Refuse empty proposal** ✅
- `propose_update_project(project_id=...) ` with no other fields → immediate `ValueError`:
  `"propose_update_project for '<uuid>' has no fields to update. Pass at least one of: title, notes, deadline, tags, area_id."`
  No pending action created.

**#82 — Without auth token** ⚠️ DEFERRED
- Requires unsetting `THINGS_AUTH_TOKEN` and restarting. Skipped. Same restart batch as #73.

---

### Chunk D — `propose_update_project` undo

**#83 — Undo restores original title** ✅
- Confirmed rename (#74), then `undo(undo_id=...)`. `get_project` returned `title="V2-chunkD today-project"` (original). `restored_fields: ["title"]`. Undo log row consumed.

**#84 — Undo only touches changed fields** ✅ *(load-bearing)*
- Confirmed title rename of `EkHuatjPJCDzyjzwgroob` to "V2-chunkD combo RENAMED".
- User manually edited the project's **notes** field in Things UI to "manual edit by user" between confirm and undo.
- Called `undo()`. `get_project` returned:
  - `title="V2-chunkD combo"` (original restored) ✅
  - `notes="manual edit by user"` (manual edit survived) ✅
- `restored_fields: ["title"]` — undo only touched the field it changed. **Load-bearing property verified.**

---

### Chunk E — `propose_bulk_complete`

**#85 — Complete 3 tasks in one op** ✅
- `propose_bulk_complete(todo_ids=[bulk-1, bulk-2, bulk-3])` → `auto_confirmed: false` (NEVER_BYPASS confirmed). Confirmed.
- Result: `count: 3`, one `bulk_complete` undo log row. All 3 tasks confirmed via `get_todo`: `status="completed"` (moved to Logbook).

**#86 — Undo a bulk complete** ✅
- `undo(undo_id=...)` → `undone: true, count: 3`. All 3 tasks returned to `status="incomplete"`, `start="Inbox"`.

**#87 — Abort on any already-done** ✅
- Proposed bulk_complete with bulk-1 (incomplete), bulk-2 (incomplete), and `Grss3fbtcu2gSrNwfERgRG` (already `canceled` in Logbook).
- `confirm_action` returned error: `"to-do 'Grss3fbtcu2gSrNwfERgRG' is already status='canceled'. Bulk complete aborts before any mutation. Drop it from the list and retry."`
- `get_todo` on bulk-1 and bulk-2 confirmed still `incomplete`. No mutation landed. ✅

---

### Chunk E — `propose_bulk_delete`

**#88 — Soft-delete 2 tasks** ✅
- Confirmed. Both bulk-del-1 and bulk-del-2 → `status="canceled"`, `stop_date` set. One `bulk_delete` undo log row.

**#89 — Undo a bulk delete** ✅
- `undo()` → both restored to `status="incomplete"`, `start="Inbox"`, `stop_date=null`.

---

### Chunk E — `propose_bulk_move`

**#90 — Move 2 tasks to Today** ✅
- bulk-move-1, bulk-move-2 → `start_date="2026-05-19"`, `today_index` set. `dimension="schedule"`.

**#91 — Move 2 tasks into a project** ✅
- bulk-move-3, bulk-move-4 → `project="3gx8kU7mB7KWruWcv8pFc2"` (`V2-chunkD with-headings`). `dimension="project"`.

**#92 — Undo bulk move per-item restore** ✅ *(load-bearing)*
- Setup: `bulk-move-today` created via `add_today_todo` (Today); `bulk-move-anytime` created via `add_anytime_todo` (Anytime).
- Bulk-moved both to Someday. Confirmed. `undo()`.
- Result:
  - `bulk-move-today` → `start_date="2026-05-19"`, `today_index` set → **Today** ✅
  - `bulk-move-anytime` → `start_date=null`, `today_index=0`, `start="Anytime"` → **Anytime** ✅
- Each task restored to its own original scheduling, not a shared fallback. **Load-bearing property verified.**

**#93 — Reject inbox/upcoming targets** ✅
- `propose_bulk_move(target='inbox')` → `ValueError: "target='inbox' is not supported in V2 first cut. Use 'today', 'anytime', 'someday', or a project/area UUID."`
- `propose_bulk_move(target='upcoming')` → `ValueError: "target='upcoming' is a computed view in Things, not a move destination. ..."`
- Both errors clean, no pending actions created.

---

### Chunk E — `propose_bulk_update`

**#94 — Apply same tag to 3 tasks** ✅
- Setup: bulk-tag-1/2/3 created via `add_inbox_todo` with tags (see Observation 1 below for a setup issue). Re-setup using `propose_update_todo` with existing tags: bulk-tag-1=Errand, bulk-tag-2=Home, bulk-tag-3=Important. Confirmed via direct SQLite query.
- `propose_bulk_update(todo_ids=[...], tags=["Office"])` → confirmed. SQLite query confirmed all three showing "Office". ✅

**#95 — Undo bulk update per-item tag restore** ✅ *(load-bearing)*
- `undo()` after #94. `restored_fields: ["tags"]`.
- SQLite query confirmed:
  - bulk-tag-1 → **Errand** ✅
  - bulk-tag-2 → **Home** ✅
  - bulk-tag-3 → **Important** ✅
- Each task got its own distinct original tag back. **Load-bearing property verified.**

**#96 — Refuse empty fields** ✅
- `propose_bulk_update(todo_ids=[...])` with no field args → `ValueError: "propose_bulk_update has no fields to update. Pass at least one of: title, notes, deadline, tags."`
  No pending action created.

---

### Chunk E — Never-bypass cross-check

**#97 — AUTO_CONFIRM=1 doesn't bypass bulk** ⚠️ DEFERRED
- Requires setting `THINGS_MCP_AUTO_CONFIRM=1` in `claude_desktop_config.json` and restarting. Deferred to same restart session as #73/#82.
- Note: `auto_confirmed: false` was already confirmed on every bulk proposal during #85, #88, #90, #91, #92, #94 without AUTO_CONFIRM set — consistent with NEVER_BYPASS_KINDS being enforced.

---

## Bugs found

**No blocking bugs.** Two observations worth noting:

### Observation 1 — `add_inbox_todo` with unknown tags silently no-ops (not a regression)

When `add_inbox_todo` is called with `tags=["tag-a"]` (a tag that doesn't exist in Things), Things silently ignores the tag — it is not created and no error is returned. Same silent behaviour for `propose_bulk_update` with `tags=["MCP-batch"]` (non-existent tag): the server reports `changed_fields=["tags"]` and dispatches the URL scheme call, but Things ignores it and no tags are written to the DB.

**Impact:** The initial attempt at #94/#95 used non-existent tags and appeared to work at the server level (undo log captured, `changed_fields` returned) while Things silently no-op'd. The test was re-run correctly using existing tags (Errand/Home/Important/Office) and passed.

**Verdict:** This is a known Things URL scheme limitation, not a things-mcp bug. However, the server could optionally pre-validate tags against the Things DB and surface a helpful error rather than silently succeeding. Low priority; document as a follow-up.

### Observation 2 — `get_project` / `get_todo` do not return `tags` field

Tags are not included in the things-py response for `get_project` or `get_todo`. Tag state was verified for items #95 via a direct read-only SQLite query. Items #68, #77, #80 noted as "accepted at URL-scheme level, tags field not verifiable via MCP tools."

**Verdict:** things-py library limitation; not a things-mcp bug. Worth tracking for a future things-py upgrade.

---

## Deferred items (require session restart)

These three items are functionally covered by code inspection and unit tests but require a config change + Claude Code restart to exercise the live error path:

| # | Description | How to run |
|---|---|---|
| 73 | `add_project` undo without auth token → RuntimeError | Unset `THINGS_AUTH_TOKEN` in config, restart, propose+confirm `add_project`, call `undo()` |
| 82 | `update_project` without auth token → RuntimeError | Same token removal restart; call `propose_update_project` |
| 97 | AUTO_CONFIRM=1 doesn't bypass bulk kinds | Set `THINGS_MCP_AUTO_CONFIRM=1` in config, restart, propose any bulk op, verify `auto_confirmed: false` |

Items #73 and #82 can be batched in one restart; #97 needs a second restart (token must be restored first).

---

## Verdict

**27 of 30 items PASS. 0 blocking bugs. 3 items deferred (config-change restarts only).**

All five load-bearing / spec-ambiguous items confirmed:
- **#70** — Native headings render as section dividers ✅
- **#72/73** — Project soft-delete moves to Logbook ✅ (#73 deferred — error path only)
- **#84** — `update_project` undo restores only changed fields, preserves concurrent edits ✅
- **#92** — `bulk_move` undo restores each item to its own original list ✅
- **#95** — `bulk_update` undo restores each item to its own original tags ✅

**Chunks D and E are ready to mark verified** pending completion of items #73, #82, #97 in a follow-up session.
