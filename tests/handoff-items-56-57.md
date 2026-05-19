# Handoff: Fix `propose_move_todo` target validation (items 56 & 57)

## Context

Working directory: `/Users/Shared/things-mcp`
Account: Test (verify with `whoami` before any writes — must print `Test`)

This is a V2 chunk C bug found during manual verification on 2026-05-19.
Full results are in `tests/V2-chunkC-verification-2026-05-19.md`.

---

## The bugs

`propose_move_todo` accepts `"inbox"` and `"upcoming"` as targets when it should
raise an actionable error immediately (before writing to the pending-actions table).

**Item 56** — `propose_move_todo(todo_id=<any>, target="inbox")` returns a valid
proposal. Expected: `ValueError` (or equivalent) with a message like
*"move-to-inbox not supported in V2 first cut; use today/anytime/someday/UUID"*.

**Item 57** — `propose_move_todo(todo_id=<any>, target="upcoming")` returns a valid
proposal. Expected: `ValueError` with a message pointing at `when='<future date>'`
(same pattern as the `build_add_url_v2` upcoming guard — see item 37 in the
verification doc for reference wording).

Both are the same root cause: no early validation of the `target` argument in the
`propose_move_todo` handler.

---

## Where to fix

The handler lives at:

```
src/things_mcp/tools/propose.py
```

Look for `propose_move_todo` (the function registered as the MCP tool). It currently
passes `target` straight through to `_enqueue_and_maybe_auto_confirm` without
checking for illegal values.

Add a validation block at the top of the handler — before any DB writes — that:

1. Rejects `"inbox"` with a clear message (move-to-inbox is deferred).
2. Rejects `"upcoming"` with the same message style as `build_add_url_v2` uses for
   that computed view (see `src/things_mcp/services/url_scheme.py` for reference
   wording).
3. Leaves `"today"`, `"anytime"`, `"someday"`, and any UUID-shaped string alone.

A `ValueError` is the right exception type — FastMCP surfaces it as a clean tool
error to the caller.

---

## Acceptance criteria

1. `uv run pytest -q` — still 134 passed (or more if you add new tests).
2. New unit tests covering the two rejection cases in `tests/test_propose_move.py`
   (or wherever move-todo tests live — check `tests/` for the right file).
3. Live MCP smoke test (as Test user):
   - `propose_move_todo(todo_id=<any inbox uuid>, target="inbox")` → clean error,
     no pending action created (`list_pending_actions()` empty / unchanged).
   - `propose_move_todo(todo_id=<any inbox uuid>, target="upcoming")` → clean error,
     no pending action created.
   - `propose_move_todo(todo_id=<any inbox uuid>, target="today")` → valid proposal
     (regression check — happy path still works).
4. Re-run items 56, 57, and 53 from
   `tests/things-mcp-manual-verification.md` and record results.

---

## Verification gate reminder (from CLAUDE.md)

Before claiming done:
- `uv run pytest` all green
- `uv run things-mcp --help` exits 0
- `health()` returns `things_app_running=true`, `state_db_exists=true`
- Write-path change → run the relevant manual verification items above as Test user
