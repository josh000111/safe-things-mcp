# things-mcp — manual verification checklist

Live-app verification against Things 3 on macOS. Items here cover behaviour the automated pytest suite can't reach: real URL-scheme launches, the Things UI state, the Logbook, Cloud Sync interaction, AppleScript permission dialogs, etc.

**Run from an MCP client** (Claude Desktop / Claude Code / Cursor) **on the `Test` macOS user account** — never `joshsmith`. The project [CLAUDE.md](../CLAUDE.md) hard rule applies: `whoami` first; the `Test` user has its own isolated Things 3 install and its own Things Cloud account, so nothing here can touch real data.

Sections are numbered cumulatively in build order. V1 (1–10) → V2 step 1–3 (11–28) → step 4 Chunk A (29–38) → Chunk B (39–52) → Chunk C (53–66) → Chunk D (67–84) → Chunk E (85–97) → and so on.

---

## V1 — Read + Inbox-create

1. **Read smoke** — `list_inbox()` titles match the Things UI.
2. **Read depth** — `get_projects(area_id=...)` then `get_project(project_id)` returns the project's headings + items, matching the UI.
3. **Write happy path** — `add_inbox_todo(title='MCP test 1')` returns an `id`; task appears in the Inbox within ~1s and shows up in a follow-up `list_inbox()` call.
4. **Write edge cases** — title with emoji, `"`, `&`, multi-line notes, `tags=['a','b']`, `checklist=['x','y','z']`, `when='today'`, `deadline='2026-12-31'`. All round-trip correctly.
5. **Callback timeout** — Quit Things, call `add_inbox_todo`. Expect a clean error within `THINGS_MCP_CALLBACK_TIMEOUT` seconds (default 5), not a hang.
6. **Concurrent reads** — Edit a task in the Things UI while calling `get_todo(id)`. No DB lock errors.
7. **Cross-client** — Repeat (1) and (3) from a second MCP client. Identical results.
8. **Schema check** — `health()` reports `things_db_path`, `things_app_running=true`, `things_py_version`.
9. **No Inbox bypass** — Internal: `services.url_scheme.build_add_url(list_id='today', ...)` raises `ValueError`.
10. **State DB isolation** — `rm ~/.things-mcp/state.db`; restart server; `health()` shows `state_db_exists=true` again.

# V2 manual verification checklist (steps 1–3 only)

These must run as the **Test** user, not the main `joshsmith` account. Per CLAUDE.md: `whoami` first. If the session needs to touch the real DB, run `backup_things3.sh` and confirm a fresh `.thingsdatabase` backup landed in `~/Documents/Things DB Backups (Cultured Code)/`.

### Propose → cancel
11. **Propose preview** — `propose_add_todo(title='V2 cancel-me', list_id='today')` returns `{action_id, preview, expires_at, next_step}`. No task appears in Things.
12. **Cancel drops it** — `cancel_action(action_id)` returns `{cancelled: true}`. `list_pending_actions()` is empty. Still no task in Things.

### Propose → confirm (each target list)
13. **Inbox** — propose then confirm `list_id='inbox'`. Task appears in Inbox, `id` is returned, `recent_undo_log()` shows a new `add_todo` row.
14. **Today** — propose then confirm `list_id='today'`. Task appears under Today.
15. **Anytime / Someday** — same with `list_id='anytime'` and `list_id='someday'`.
16. **Project UUID** — pick a real project UUID from `get_projects()`. Propose with that as `list_id`; task lands under the project.

### Propose → confirm with full payload
17. **All fields populated** — propose with `notes`, `when='today'`, `deadline=<future>`, `tags=['a','b']`, `checklist=['x','y']`. Confirm and verify the task in Things has all metadata.

### Pending action lifecycle
18. **List pending** — `propose_add_todo` twice without confirming. `list_pending_actions()` returns both rows, newest first.
19. **TTL expiry** — propose, wait 5 minutes 30 seconds, call `confirm_action(action_id)`. Expect a "Pending action … expired" error and the row swept.

### Undo round-trip — REQUIRES `THINGS_AUTH_TOKEN`
20. **Token check** — export `THINGS_AUTH_TOKEN=<token from Things → Settings → General → Enable Things URLs → Manage>`. Restart the MCP server. `health().url_scheme_auth_token_set == true`.
21. **Undo most recent** — propose + confirm a task. Call `undo()` with no args. Returns `{undone: true, note: 'Soft-undo: …'}`. Task is now status=`completed` / `canceled` and no longer in active lists (visible in Logbook).
22. **Undo by id** — same flow but call `undo(undo_id=<id from recent_undo_log()>)`.
23. **Undo with no history** — fresh state, call `undo()`. Expect "No reversible actions" error.
24. **Undo without auth token** — unset `THINGS_AUTH_TOKEN`, restart, propose + confirm, then call `undo()`. Expect actionable error pointing to the Settings path.

### Cross-cutting safety
25. **No-bypass regression** — internal: `services.url_scheme.build_add_url(list_id='today', ...)` *still* raises `ValueError` (V1 guard intact). `build_add_url_v2(list_id='today', ...)` does not.
26. **State persists across restarts** — propose without confirming; restart the MCP server; `list_pending_actions()` still returns it (within TTL).
27. **Concurrent V2 + V1** — `propose_add_todo(list_id='inbox')` *then* `add_inbox_todo(title='x')` *then* `confirm_action(action_id from step 1)`. All three succeed; both Inbox tasks present.
28. **Pre-mutation undo_log row** — kill the Things app between `propose_add_todo` and `confirm_action`, then call confirm. Expect the timeout error, but `recent_undo_log()` should still show an `add_todo` row with `target_uuid=null` — the forensic breadcrumb.

# V2 manual verification checklist — Step 4 Chunk A (direct shortcuts + complete_todo)

Same ground rules: must run as the **Test** user. `whoami` first. Restart Claude Desktop to reload the MCP server after pulling the new code.

### Direct add shortcuts (no airlock)
29. **`add_today_todo`** — ask: *"Use add_today_todo to add a task titled 'V2-chunkA today' to my Today list."* Task appears in Today within ~1s. `recent_undo_log()` shows a new `add_todo` row with the new UUID. (Note: V2 direct adds DO write undo log rows, unlike V1 `add_inbox_todo`.)
30. **`add_anytime_todo`** — same with title `'V2-chunkA anytime'`. Task appears under Anytime.
31. **`add_someday_todo`** — same with title `'V2-chunkA someday'`. Task appears under Someday.
32. **Undo a direct add** — after task 29 lands, ask: *"Undo the most recent action."* Task disappears from Today, lands in Logbook with `canceled` status. `recent_undo_log()` is one row shorter.

### `complete_todo` (single-target direct) — REQUIRES `THINGS_AUTH_TOKEN`
33. **Token check** — `health().url_scheme_auth_token_set == true`. If not, set `THINGS_AUTH_TOKEN` in Claude Desktop config and restart.
34. **Complete a real task** — first ask: *"List my Inbox so I can pick a task to complete."* Pick one. Ask: *"Call complete_todo with id `<uuid>`."* Verify in Things: task is now ticked / strikethrough, moves to Logbook within a second.
35. **Undo the completion** — call `undo()`. Task returns to its original state (incomplete, back in its list). `recent_undo_log()` is shorter.
36. **`complete_todo` on a missing id** — ask: *"Call complete_todo with id 'this-uuid-does-not-exist'."* Expect a clean error: *"No to-do found with id…"*. No mutation should land.

### `upcoming` rejection (code-level safety net)
37. **Internal check** — ask Claude Code: *"Run `uv run python -c 'from things_mcp.services import url_scheme; url_scheme.build_add_url_v2(title=\"t\", list_id=\"upcoming\")'`."* Expect a `ValueError` with the message containing "computed view in Things" and pointing at `when='<future date>'`. (This is the bug flagged at the end of step 1–3 verification.)
38. **Propose to Upcoming via the agent** — ask: *"Propose adding 'V2-chunkA upcoming test' to my Upcoming list."* The agent's call should bubble up the `ValueError` cleanly. (If it silently succeeds with `list-id=upcoming`, the bug is back — file a report.)

# V2 manual verification checklist — Step 4 Chunk B (`propose_update_todo` + `THINGS_MCP_AUTO_CONFIRM`)

Same ground rules: **Test** user only. Restart Claude Desktop to pick up the new code. `THINGS_AUTH_TOKEN` must be set (every test below uses `update`).

### `propose_update_todo` — basic edits
39. **Update a title** — first ask the agent to *"List my Inbox and pick a task id"*. Then: *"Propose updating to-do `<uuid>` to title 'V2-chunkB updated title', then confirm."* In Things, that task's title now shows the new value. `recent_undo_log()` shows an `update_todo` row.
40. **Update notes** — pick a task. *"Propose updating to-do `<uuid>` so notes='new notes from MCP', then confirm."* Open the task in Things — notes field replaced.
41. **Update deadline** — pick a task. *"Propose updating to-do `<uuid>` so deadline='2026-12-31', then confirm."* Things shows the new deadline badge.
42. **Update tags** — pick a task that has some tags. *"Propose updating to-do `<uuid>` so tags=['MCP-test'], then confirm."* (Assumes the tag 'MCP-test' exists. Otherwise pick one of your real tags.) Task now has only that tag.
43. **Clear a field** — pick a task with notes. *"Propose updating to-do `<uuid>` so notes='', then confirm."* Notes field empty in Things.
44. **Clear all tags** — pick a tagged task. *"Propose updating to-do `<uuid>` so tags=[], then confirm."* Task has no tags.
45. **Refuse empty proposal** — *"Propose updating to-do `<uuid>` (no fields specified)."* Expect a clean ValueError about needing at least one field. (You may need to phrase this as "propose update with only the todo_id" depending on how the agent interprets your request.)

### Undo of `propose_update_todo`
46. **Undo restores the original title** — propose+confirm a title change as in #39, then `undo()`. Old title comes back in Things. `recent_undo_log()` shrinks by 1.
47. **Undo only touches changed fields** — propose+confirm a title change. Before calling undo, manually edit the task's NOTES in the Things UI (any change). Then `undo()`. After undo: title is restored to original, but YOUR manual notes edit survives intact. **This is the load-bearing property — verify carefully.**

### `THINGS_MCP_AUTO_CONFIRM` flag
48. **Off → propose just enqueues** — confirm `THINGS_MCP_AUTO_CONFIRM` is NOT set in your Claude Desktop config. Ask: *"Propose adding 'V2-chunkB autoconfirm-off' to my Inbox."* Response has `auto_confirmed: False`. No task in Things. Cancel via `cancel_action`.
49. **On → propose runs inline** — add `"THINGS_MCP_AUTO_CONFIRM": "1"` to the things-mcp `env` block in `claude_desktop_config.json`. Restart Claude Desktop. Ask: *"Propose adding 'V2-chunkB autoconfirm-on' to my Inbox."* Response has `auto_confirmed: True` AND a `result` field containing the new task id. Task IS in Things — no separate confirm call needed.
50. **On + never-bypass kind** (placeholder until chunk C ships delete) — verify the wiring is correct via code inspection only. Ask Claude Code (in dev): *"Run `uv run python -c 'from things_mcp import config; print(config.NEVER_BYPASS_KINDS)'`."* Expected output: `frozenset({'delete_todo', 'bulk_delete', 'bulk_complete', 'bulk_move', 'bulk_update'})`. Full runtime test of never-bypass behaviour comes with chunk C.
51. **On + handler fails** — with auto-confirm still on, force a failure: temporarily set `THINGS_AUTH_TOKEN=` (empty) in the config, restart, then propose an `update_todo` (which needs auth). Expect a RuntimeError about the missing token AND a leftover pending row visible via `list_pending_actions`. Restore the real token afterward.

### Tear-down
52. **Remove `THINGS_MCP_AUTO_CONFIRM`** from your Claude Desktop config and restart. Default behaviour resumes.

# V2 manual verification checklist — Step 4 Chunk C (`propose_move_todo` + `propose_delete_todo`)

Same ground rules: **Test** user only. Restart Claude Desktop to reload. `THINGS_AUTH_TOKEN` must be set (both tools use `update`).

### `propose_move_todo` — scheduling dimension
53. **Move to Today** — *"List my Inbox, pick a task uuid, then propose moving it to today."* Confirm. In Things: task now appears in Today view. Its project membership (if any) is preserved.
54. **Move to Anytime** — pick an Inbox task. *"Propose moving `<uuid>` to anytime."* Confirm. Task now under Anytime.
55. **Move to Someday** — pick a task. *"Propose moving `<uuid>` to someday."* Confirm. Task under Someday.
56. **Reject Inbox target** — *"Propose moving `<uuid>` to inbox."* Expect a ValueError mentioning "not supported in V2 first cut" with a hint that today/anytime/someday/UUID are the supported targets.
57. **Reject Upcoming target** — *"Propose moving `<uuid>` to upcoming."* Expect the same actionable rejection.

### `propose_move_todo` — project dimension
58. **Move into a real project** — *"List my projects, pick one, then propose moving an Inbox task into project `<UUID>`."* Confirm. Task now appears inside that project in Things. Its scheduling (Today/Anytime/etc.) is preserved.
59. **Move between projects** — pick a task that's already in a project. Propose moving it to a different project UUID. Confirm. Task now under the new project, no longer under the old one.

### Undo of `propose_move_todo`
60. **Undo a scheduling move** — propose+confirm a today move as in #53. Call `undo()`. Task returns to its original list (Inbox/Anytime/wherever). **Critical:** if you manually edited the task's TITLE in Things between confirm and undo, that title edit must survive — undo only restores the scheduling dimension.
61. **Undo a project move** — propose+confirm #58 (move to project). Call `undo()`. Task returns to its original project (or to no-project if it had none). Verify in Things.

### `propose_delete_todo` (soft-delete) — REQUIRES explicit confirm even with AUTO_CONFIRM=1
62. **Soft-delete a task** — pick an expendable inbox task you can lose. *"Propose deleting `<uuid>`."* Response shows the preview ("Soft-delete to-do … moves to Logbook"). Call `confirm_action`. In Things: task no longer in Inbox; appears in Logbook with strikethrough/canceled badge.
63. **Undo the soft-delete** — call `undo()` after #62. Task returns to Inbox (or wherever it was), status incomplete. `recent_undo_log()` is one row shorter.
64. **Refuse to delete an already-canceled task** — pick a task already in your Logbook (status canceled or completed). *"Propose deleting `<that uuid>`."* Expect an actionable error ("already status canceled/completed"), no mutation.
65. **AUTO_CONFIRM still won't bypass delete** — set `THINGS_MCP_AUTO_CONFIRM=1` in Claude Desktop config, restart. *"Propose deleting `<uuid of a throwaway task>`."* Response has `auto_confirmed: False` and a note containing "never auto-confirmed". Task is **not** deleted — you have to call `confirm_action` explicitly. Unset AUTO_CONFIRM after.
66. **AUTO_CONFIRM still works for safe kinds** — with AUTO_CONFIRM=1, *"Propose adding 'V2-chunkC autoconfirm-still-on' to Inbox."* Response has `auto_confirmed: True` and the result inline. Restore AUTO_CONFIRM off for the next chunks.

# V2 manual verification checklist — Step 4 Chunk D (`propose_add_project` + `propose_update_project`)

Same ground rules: **Test** user only. `whoami` first. Restart Claude Desktop to reload the MCP server. `THINGS_AUTH_TOKEN` must be set (`update_project` needs it; `add_project` undo needs it too).

### `propose_add_project` — basic
67. **Title-only project** — *"Propose adding a project titled 'V2-chunkD title-only'."* Confirm. New project appears in Things' Projects list within ~1s. `recent_undo_log()` shows an `add_project` row with the new project's UUID.
68. **All optional fields** — *"List my areas, pick one uuid, then propose adding a project titled 'V2-chunkD all-fields' with that area_id, when='anytime', deadline='2026-12-31', notes='from MCP', tags=['MCP-test']."* Confirm. Open the new project — area, notes, deadline, and tag all present.
69. **Schedule a project for Today** — *"Propose adding 'V2-chunkD today-project' with when='today'."* Confirm. Project appears in Today.

### `propose_add_project` — native headings via `things:///json`
70. **Headings at birth** — *"Propose adding a project titled 'V2-chunkD with-headings' with headings=['Design', 'Dev', 'QA']."* Confirm. Open the project in Things — there are THREE native section headings (rendered as dividers, NOT as `__DESIGN__`-style dummy tasks). The headings appear in the order Design → Dev → QA.
71. **Headings + other fields together** — *"Propose adding 'V2-chunkD combo' with headings=['Planning','Execution'], notes='kickoff', deadline='2026-09-30'."* Confirm. Both headings present AND the notes/deadline fields populated.

### `propose_add_project` — undo (soft-delete)
72. **Undo a freshly-added project** — after #67 lands, call `undo()`. The project disappears from Projects and appears in the Logbook with canceled badge. `recent_undo_log()` shrinks by 1.
73. **Undo without auth token** — temporarily unset `THINGS_AUTH_TOKEN` in Claude Desktop config, restart, repeat #67 + confirm, then call `undo()`. Expect a clean RuntimeError pointing at the Things → Settings → Manage URL. Restore the token after.

### `propose_update_project` — basic edits
74. **Update project title** — pick a real project uuid. *"Propose updating project `<uuid>` to title 'V2-chunkD renamed', then confirm."* The project shows the new title in Things.
75. **Update notes** — *"Propose updating project `<uuid>` so notes='kickoff notes from MCP'."* Confirm. Open the project — notes replaced.
76. **Update deadline** — *"Propose updating project `<uuid>` so deadline='2026-11-15'."* Confirm. Things shows the new deadline.
77. **Update tags** — pick a project that has some tags. *"Propose updating project `<uuid>` so tags=['MCP-test']."* Confirm. Tags replaced.
78. **Move project between areas** — pick a project in one area + an area uuid for a different area. *"Propose updating project `<uuid>` so area_id='<other-area-uuid>'."* Confirm. Project now sits under the new area.
79. **Clear notes** — *"Propose updating project `<uuid>` so notes=''."* Confirm. Notes field empty.
80. **Clear tags** — *"Propose updating project `<uuid>` so tags=[]."* Confirm. No tags.
81. **Refuse empty proposal** — *"Propose updating project `<uuid>` (no fields specified)."* Expect a clean ValueError listing the valid fields.
82. **Without auth token** — unset `THINGS_AUTH_TOKEN`, restart, propose an update. Expect actionable RuntimeError pointing at Settings → Manage. Restore.

### Undo of `propose_update_project`
83. **Undo restores original title** — propose+confirm #74. Call `undo()`. Old title comes back. `recent_undo_log()` shrinks.
84. **Undo only touches changed fields** — propose+confirm a title change. Before calling undo, manually edit the project's NOTES in Things UI. Then `undo()`. After undo: title is restored, but YOUR manual notes edit survives. (Load-bearing property — same as #47 for to-dos.)

# V2 manual verification checklist — Step 4 Chunk E (`propose_bulk_*` tools)

Same ground rules: **Test** user only. `THINGS_AUTH_TOKEN` must be set. **All four bulk tools are NEVER_BYPASS** — they require explicit `confirm_action` even with `THINGS_MCP_AUTO_CONFIRM=1`.

Setup: ensure you have 3+ throwaway Inbox tasks (titles like `bulk-1`, `bulk-2`, `bulk-3`) before starting.

### `propose_bulk_complete`
85. **Complete 3 tasks in one op** — gather 3 inbox task uuids. *"Propose bulk completing these 3 to-dos: [uuid1, uuid2, uuid3]."* Response has `auto_confirmed: False` (even if AUTO_CONFIRM=1). `confirm_action`. In Things: all 3 tasks now in Logbook with completed status. `recent_undo_log()` shows ONE `bulk_complete` row covering all 3.
86. **Undo a bulk complete** — call `undo()` after #85. All 3 tasks return to incomplete status in their original location.
87. **Abort on any already-done** — pick 2 incomplete tasks + 1 task already in your Logbook. *"Propose bulk completing these 3."* Expect a clean ValueError about the already-completed task. **No mutation lands** — verify the 2 still-incomplete tasks are still incomplete in Things.

### `propose_bulk_delete`
88. **Soft-delete 2 tasks** — gather 2 throwaway inbox uuids. *"Propose bulk deleting [uuid1, uuid2]."* Auto-confirmed must be False. `confirm_action`. Both tasks now in Logbook with canceled status. One undo_log row.
89. **Undo a bulk delete** — `undo()` after #88. Both tasks restored to incomplete status in their original location.

### `propose_bulk_move`
90. **Move 2 tasks to Today** — gather 2 inbox uuids. *"Propose bulk moving these to today."* Confirm. Both tasks now in Today.
91. **Move 2 tasks into a project** — gather 2 inbox uuids + a project uuid. *"Propose bulk moving these into project `<uuid>`."* Confirm. Both tasks under the project.
92. **Undo a bulk move (per-item restore)** — propose+confirm a move where the source tasks had DIFFERENT original scheduling (one in Today, one in Anytime). After undo, each returns to its OWN original list, not a common one. **Load-bearing.**
93. **Reject inbox/upcoming targets** — *"Propose bulk moving [<uuid>] to inbox."* Expect ValueError. Same for `target='upcoming'`.

### `propose_bulk_update`
94. **Apply same tag to 3 tasks** — gather 3 uuids with different existing tags. *"Propose bulk updating these to tags=['MCP-batch']."* Confirm. All 3 now have only that tag.
95. **Undo a bulk update (per-item restore)** — `undo()` after #94. Each task gets its ORIGINAL set of tags back (different per task, not a common set). **Load-bearing.**
96. **Refuse empty fields** — *"Propose bulk updating [uuids] with no fields."* Clean ValueError.

### Never-bypass cross-check
97. **AUTO_CONFIRM=1 doesn't bypass bulk** — set `THINGS_MCP_AUTO_CONFIRM=1` in Claude Desktop config, restart. Propose any bulk op. Response has `auto_confirmed: False` and a note about "never auto-confirmed". Confirm + undo as usual. Unset AUTO_CONFIRM after.

# V2 manual verification checklist — Step 4b (dummy-heading layer)

Same ground rules: **Test** user only. `whoami` first. Restart Claude Desktop to reload the MCP server. `THINGS_AUTH_TOKEN` must be set (update and delete heading need it; add_heading undo also needs it).

**Background:** The Things URL scheme cannot create standalone headings inside existing projects. Step 4b ships a URL-scheme-only workaround: headings are represented as regular to-dos with the title format `__NAME__` (leading and trailing double underscores, all-caps name between). These are visible in the Things UI as ordinary tasks. Real native headings (rendered as section dividers) are created at project birth via the JSON endpoint (`propose_add_project` with `headings=[...]`), or via AppleScript in step 5.

Setup: ensure you have one or more projects with a few to-dos. Create a dedicated scratch project (e.g. "4b-test") via `propose_add_project` for write tests.

### `propose_add_heading` — basic
98. **Add a dummy heading** — pick a project uuid (e.g. your "4b-test" project). *"Propose adding a heading named 'Design' to project `<uuid>`."* Confirm. In Things: a task titled `__DESIGN__` appears in the project. `recent_undo_log()` shows one `add_heading` row.
99. **Name with spaces and special chars** — *"Propose adding heading 'Phase 1' to project `<uuid>`."* Confirm. Task titled `__PHASE 1__` appears.
100. **Invalid name (starts with digit)** — *"Propose adding heading '1st Sprint' to project `<uuid>`."* Expect a clean ValueError (name after uppercasing must start with a letter). No mutation.
101. **Project not found** — *"Propose adding heading 'Test' to project 'FAKE-UUID'."* Expect ValueError about project not found.
102. **after_todo_id hint acknowledged** — *"Propose adding heading 'Backend' to project `<uuid>` after_todo_id='<some-task-uuid>'."* Confirm. Task `__BACKEND__` created. The result includes an `after_todo_id_note` acknowledging the hint was received but not honoured. Position may not match the hint — that's expected.

### `propose_add_heading` — undo
103. **Undo a heading add** — after #98, call `undo()`. The `__DESIGN__` task moves to the Logbook (canceled+completed). `recent_undo_log()` shrinks by 1.
104. **Undo without auth token** — temporarily unset `THINGS_AUTH_TOKEN`, restart. Add a heading (confirm). Then call `undo()`. Expect clean RuntimeError pointing at Things → Settings → Manage. Restore the token after.

### `get_project` — unified headings overlay
105. **Headings array in get_project** — use `get_project('<uuid>')` on the "4b-test" project that now has at least one dummy heading (from #99, or re-add one). Response includes a `headings` key containing a list. Each entry has `kind`, `id`, `name`, `position`. The dummy heading shows `kind: "dummy"`.
106. **Native + dummy headings together** — create a project with native headings at birth: `propose_add_project('4b-mixed', headings=['Native A', 'Native B'])`. Confirm. Then add a dummy heading to it (`propose_add_heading`). Confirm. Call `get_project(<uuid>)`. The `headings` array includes both: entries with `kind: "native"` (for Native A, Native B) and `kind: "dummy"` (for the one you added). The `items` list still contains all tasks plus the `__NAME__` dummy task as a regular to-do. **Load-bearing.**
107. **Empty project** — `get_project` on a project with no items returns `headings: []`.

### `propose_update_heading`
108. **Rename by name** — *"Propose updating heading 'Design' in project `<uuid>` to new name 'UX'."* (The project must have a `__DESIGN__` dummy heading from a prior step, or add one.) Confirm. Task title changes from `__DESIGN__` to `__UX__` in Things.
109. **Rename by UUID** — *"Propose updating heading `<dummy-task-uuid>` in project `<uuid>` to new name 'Backend'."* Confirm. Title updated.
110. **Heading not found** — *"Propose updating heading 'NonExistent' in project `<uuid>`."* Expect ValueError about no heading with that name found.
111. **Target is not a dummy** — look up the UUID of a regular task in the project. *"Propose updating heading `<regular-task-uuid>` in project `<uuid>` to new name 'Foo'."* Expect ValueError saying the target is not a dummy heading.
112. **Ambiguous — native and dummy share name** — (complex setup: use `propose_add_project` to create a project that has a native heading named "Planning", then `propose_add_heading` for "Planning" on the same project to create `__PLANNING__`). *"Propose updating heading 'Planning' in project `<uuid>`."* Expect ValueError listing both candidates (native UUID + dummy UUID) and asking you to retry with the specific UUID.
113. **Undo a rename** — after #108, call `undo()`. Title reverts to `__DESIGN__`. Manually verify in Things.

### `propose_delete_heading`
114. **Delete by name** — *"Propose deleting heading 'UX' from project `<uuid>`."* (Must exist as `__UX__` from #108 or add a fresh one.) Response has `auto_confirmed: False` (never auto-confirmed). `confirm_action`. The `__UX__` task moves to the Logbook with canceled status.
115. **Delete by UUID** — find a dummy heading UUID via `get_project`. *"Propose deleting heading `<dummy-uuid>` from project `<uuid>`."* Confirm. Task soft-deleted.
116. **Undo a delete** — after #114, `undo()`. The `__UX__` task returns to the project with incomplete status.
117. **Refuse to delete native heading** — look up the UUID of a native heading in a project. *"Propose deleting heading `<native-uuid>` from project `<uuid>`."* Expect ValueError saying native headings require AppleScript (step 5).
118. **Refuse to delete already-canceled** — try to delete a dummy heading task already in the Logbook (from a prior test, or re-complete one manually in the Things UI). Expect ValueError about already canceled/completed.
119. **Never auto-confirmed** — set `THINGS_MCP_AUTO_CONFIRM=1`, restart. *"Propose deleting heading `<dummy-uuid>` from project `<uuid>`."* Response must have `auto_confirmed: False`. Unset `THINGS_MCP_AUTO_CONFIRM` after.

### Round-4 deferred items (close at top of this session)
These items from Round 4 require a config-change + restart. Run them before the step 4b checklist above if possible:
120. **(Item #73 deferred)** Unset `THINGS_AUTH_TOKEN` → restart → call `undo()` on a recent `add_project` action (create one first if needed). Expect clean RuntimeError pointing at Things → Settings → Manage.
121. **(Item #82 deferred)** Still without auth token → propose an `update_project`. Expect actionable RuntimeError.
122. **(Item #97 deferred)** Restore `THINGS_AUTH_TOKEN` → restart → set `THINGS_MCP_AUTO_CONFIRM=1` → restart → propose any bulk op (e.g. `propose_bulk_complete`). Response must have `auto_confirmed: False`. Unset `THINGS_MCP_AUTO_CONFIRM` after.

---

## Pre-release fix A — Tag pre-validation

### `add_inbox_todo` with unknown tag
123. **Unknown tag rejected** — *"Add a to-do to the Inbox titled 'Tag validation test' with tags ['NonExistentTag999']."* Expect a `ValueError` naming `NonExistentTag999` and listing the available tags from Things. No task appears in the Things Inbox.
124. **Known tag accepted** — *"Add a to-do to the Inbox titled 'Tag validation success' with tags ['Errand']."* (Use a tag that actually exists in the Test account's Things.) Succeeds. Task appears in Inbox with the Errand tag applied — confirm in Things UI.
125. **Propose-time rejection for propose tools** — *"Propose updating to-do `<any-valid-uuid>` with tags ['FakeTag']."* Expect `ValueError` returned immediately at propose stage — no pending action is created. Confirm `list_pending_actions()` does not include a new entry.
126. **`propose_bulk_update` with mixed tags** — *"Propose bulk updating todos `[<uuid1>, <uuid2>]` with tags=['Errand', 'GhostTag']."* Expect `ValueError` at propose stage naming `GhostTag` and listing available tags. No pending action created.

---

## Pre-release fix B — Tags in read responses

### `get_todo` tag field
127. **Tag round-trip via `get_todo`** — In the Things UI, open the Test account and tag a to-do (e.g. the task you created in #124) with a tag (e.g. "Errand"). Call `get_todo(<uuid>)`. Response must include `"tags": ["Errand"]` (or similar list). The field must be present and populated.
128. **Task with no tags returns empty list** — Find (or create) a to-do in the Test account with no tags. Call `get_todo(<uuid>)`. Response must include `"tags": []` — the key must be present, not absent.

### `get_project` tag field
129. **Project with tags** — In the Things UI, assign a tag to a project in the Test account. Call `get_project(<project_uuid>)`. The response's top-level dict must include `"tags": [...]` with the tag name(s). Confirm they match what the Things UI shows.
130. **Project with no tags** — Call `get_project` on an untagged project. Response must include `"tags": []` at the top level.
