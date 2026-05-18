# V1 manual verification checklist

Run from an MCP client (Claude Desktop / Claude Code / Cursor) unless noted.

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
