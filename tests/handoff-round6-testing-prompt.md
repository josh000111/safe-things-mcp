# Round 6 testing session — handoff prompt

Paste the block below as the opening message to a new Claude Code session running as the `Test` macOS user.

---

## Prompt to paste

You are picking up a manual testing session for the `things-mcp` project. Working directory: `/Users/Shared/things-mcp`. Run all commands with `uv run …` (never bare `python`).

### What was just built (commit `78a5f32` on `main`)

**Fix A — tag pre-validation:** Every write tool that accepts a `tags` parameter now calls `validate_tags()` (in `src/things_mcp/services/url_scheme.py`) before firing the URL scheme. Unknown tag names raise `ValueError` with an actionable message listing available tags. For `propose_*` tools, validation fires before the pending action is enqueued — so `list_pending_actions()` stays unchanged on a bad tag. Direct write tools (`add_inbox_todo`, `add_today_todo`, `add_anytime_todo`, `add_someday_todo`) validate before URL construction.

**Fix B — tags in read responses:** `things_repo.todo()` and `things_repo.project()` now use `things.tasks()` instead of `things.get()`, so the `tags` field is present in `get_todo` and `get_project` responses. `get_todo()` and `get_project_row()` delegate to these functions (DRY cleanup — no behaviour change for callers).

Automated suite: **245 tests passing** (18 new in `tests/test_tag_validation.py` and `tests/test_tag_read.py`).

---

### Your task — manual verification: Round 6, items 123–130

Full runbook is in `tests/handoff-fixes-ab-testing.md`. Items to walk:

| # | What | Pass criterion |
|---|------|----------------|
| 123 | Unknown tag rejected (`add_inbox_todo`) | `ValueError` naming `NonExistentTag999`; nothing in Things Inbox |
| 124 | Known tag accepted (`add_inbox_todo`) | Task appears in Inbox; Things UI tag panel shows the tag |
| 125 | Propose-time rejection (`propose_update_todo`) | `ValueError` before pending action; `list_pending_actions()` unchanged |
| 126 | `propose_bulk_update` with mixed tags | `ValueError` naming `GhostTag`; no pending action created |
| 127 | `get_todo` returns `tags` for tagged task | Response includes `"tags": ["Errand"]` (or whatever tag was applied) |
| 128 | `get_todo` returns `tags: []` for untagged task | Response includes `"tags": []`; key present |
| 129 | `get_project` returns project-level tags | Top-level dict includes `"tags": [...]` matching Things UI |
| 130 | `get_project` returns `tags: []` for untagged project | Top-level dict includes `"tags": []` |

Items 123, 124, and 127 are **load-bearing** — if any fail, stop and write a bug handoff.

---

### Pre-flight (do this first)

1. `whoami` → must print `Test`. If it prints `joshsmith`, stop immediately.
2. `git pull origin main` to get commit `78a5f32` (or confirm with `git log --oneline -1`).
3. `uv run pytest -q` → 245 tests, all green.
4. `uv run things-mcp --help` → clean exit.
5. `health()` → `things_app_running=true`, `state_db_exists=true`, `url_scheme_auth_token_set=true`.
6. Confirm at least one tag exists in the Test account's Things (e.g. "Errand"). If none, create one in the Things UI before starting.

---

### Recording results

Create `tests/fixes-ab-verification-<YYYY-MM-DD>.md` as you go. Record each item as ✅ / ⚠️ / ❌ plus any surprises. Use `tests/bug-handoff-4b-name-resolution.md` as the format template if you need to write a bug handoff.

---

### Acceptance criteria for closing Round 6

- Items 123–130 walked and recorded.
- Items 123, 124, 127 all ✅.
- Results doc committed and pushed to `main`.
- `docs/things-mcp-V2-technical-architecture-and-implementation-plan.md` §0 status table updated:
  - **Pre-release fix A** Manual Testing column → `✅ Verified (Round 6 — <date>)`
  - **Pre-release fix B** Manual Testing column → `✅ Verified (Round 6 — <date>)`

If both fixes pass: the server is feature-complete for pre-release. Next up is V2 step 5 (opt-in AppleScript layer for hard-delete + reorder).

---

### Debugging quick-reference

- **Fix A not firing:** Check `src/things_mcp/tools/propose.py` — `url_scheme.validate_tags(tags)` must appear before `_enqueue_and_maybe_auto_confirm`. Check `src/things_mcp/tools/write.py` for `add_inbox_todo` and `_direct_add`.
- **Fix B still missing tags:** Verify `things_repo.todo()` calls `things.tasks(uuid)` not `things.get(uuid)` in `src/things_mcp/services/things_repo.py`.
- **Quick Python trace:** `uv run python -c "import things; print(things.tasks('<uuid>', filepath='/path/to/Things Database.thingsdatabase').get('tags'))"`
- **Pending action audit:** `list_pending_actions()` and `recent_undo_log(limit=5)`.
