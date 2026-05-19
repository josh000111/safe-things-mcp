# Handoff: V2 Round 4 manual verification — Chunks D + E

## Context

Working directory: `/Users/Shared/things-mcp`
Account: **Test** (verify with `whoami` before any writes — must print `Test`)
This is the live-app verification round for V2 step 4 chunks D and E, bundled
into one Round 4 per the 4-round plan.

What landed this build session (on `main`):

- **Chunk D** — `propose_add_project` + `propose_update_project`
  - `add_project` supports a `headings=[...]` array → uses `things:///json`
    endpoint (the only URL-scheme path for native section headings at
    project birth).
  - `update_project` uses auth-gated `things:///update-project`; first-cut
    fields are title / notes / deadline / tags / area_id.
  - Undo paths match the existing patterns: `add_project` soft-deletes
    via `update-project?canceled=true&completed=true`; `update_project`
    re-applies a per-field inverse snapshot.
- **Chunk E** — `propose_bulk_complete` / `bulk_delete` / `bulk_move` /
  `bulk_update`.
  - All four are in `NEVER_BYPASS_KINDS` — they require explicit
    `confirm_action` even with `THINGS_MCP_AUTO_CONFIRM=1`.
  - Each bulk op writes ONE `undo_log` row covering N targets, with
    per-item inverse params so one `undo()` reverses the whole batch.
  - bulk_move and bulk_update capture per-item original state (each task
    has its own scheduling / tags / etc.) — undo restores each item to
    ITS OWN original values, not a shared one.

Automated suite: **195 passing** at handoff (was 138 at end of chunk C
verification + the items-56/57 fix).

---

## Required pre-flight

1. `whoami` → must print `Test`.
2. `git pull origin main` to grab the build commit.
3. Confirm `THINGS_AUTH_TOKEN` is set in Claude Desktop config — every
   item below except #67/68/69/70/71 needs it. (#67–71 don't need it to
   create the project, but the matching undo items #72–73 do.)
4. Restart Claude Desktop to reload the MCP server.
5. `health()` returns `things_app_running=true`, `state_db_exists=true`,
   `url_scheme_auth_token_set=true`.

---

## What to run

Walk items **67 through 97** in `tests/things-mcp-manual-verification.md`,
in order. As you go:

- For each item, record the outcome (✅ / ⚠️ / ❌) and any surprises in a
  results doc, similar to `tests/V2-chunkC-verification-2026-05-19.md`.
- Name the results doc `tests/V2-Round4-chunks-D-E-verification-<YYYY-MM-DD>.md`.
- If a write doesn't land as expected within ~3s, screenshot Things, run
  `recent_undo_log()`, and note both in the results doc before retrying.

The checklist is grouped:

- **67–71** — `propose_add_project` basic + headings via JSON endpoint.
- **72–73** — `add_project` undo (soft-delete).
- **74–82** — `propose_update_project` field edits + error cases.
- **83–84** — `update_project` undo, including the "only-changed-fields"
  load-bearing property (same pattern as item 47 for to-dos).
- **85–87** — `propose_bulk_complete` + undo + abort-on-invalid.
- **88–89** — `propose_bulk_delete` + undo.
- **90–93** — `propose_bulk_move`, including a per-item inverse-restore
  check that the load-bearing dimension-preservation property holds.
- **94–96** — `propose_bulk_update` + undo + empty-fields error.
- **97** — never-bypass cross-check: `THINGS_MCP_AUTO_CONFIRM=1` does NOT
  bypass any bulk kind.

---

## Specific things to watch closely

These are the items where the spec is ambiguous or where I made a design
call that needs live confirmation:

- **Item 70 (native headings)** — confirm Things renders the headings as
  real section dividers (not dummy `__DESIGN__` tasks). The URL builder
  uses Things' documented JSON structure:
  `[{type:"project", attributes:{title:..., items:[{type:"heading", attributes:{title:...}}]}}]`.
  If headings come through as ordinary tasks instead of dividers, the
  JSON shape may need adjustment.
- **Item 72/73 (project soft-delete)** — verify `update-project?completed=true&canceled=true`
  actually moves the project to the Logbook (not just toggles status).
  Things' docs are slightly ambiguous on project-level soft-delete; the
  arch doc §6 step 4 item 7 implies it works, but live confirmation is
  the gate.
- **Item 78 (area move)** — confirm `area-id=<new>` on `update-project`
  changes the area. `_normalize_for_undo` reads from the `area` field on
  the project row (things.py exposes the area UUID as `area`, not
  `area_id`); if undo doesn't restore the original area, that's the
  field name to investigate.
- **Item 84 (update_project selective undo)** — same load-bearing
  property as item 47 for to-dos. Critical to verify.
- **Item 92 (bulk_move per-item undo)** — gather tasks with genuinely
  different original scheduling first; if they're all from the same list
  the property is untestable.
- **Item 95 (bulk_update per-item tag restore)** — each task must have
  DIFFERENT original tags before the bulk update for this to be a real
  test of the property.

---

## Acceptance criteria for closing Round 4

- All items 67–97 walked, every result recorded.
- Items #70, #72/73, #84, #92, #95 confirmed working (the load-bearing
  / spec-ambiguous ones).
- Any unexpected failures captured as bug-handoff docs in `tests/`
  alongside the results file, in the same shape as
  `handoff-items-56-57.md`.
- No mutations on the real `joshsmith` Things DB at any point.

When the round closes:

1. Push the results doc + any bug handoffs to `main`.
2. Update the spec §0 status table — flip chunks D and E from
   "awaiting Round-4 manual verification" to "manually verified" (or
   amend with a follow-up if anything's pending).

---

## If something looks wrong

- Don't keep mutating. Run `cancel_action(action_id)` or undo if a
  proposal has already confirmed, then inspect.
- For URL-scheme behaviour mismatches, capture the exact URL that
  launched (visible from `confirm_action`'s response when verbose) and
  compare against the URL-scheme builder source in
  `src/things_mcp/services/url_scheme.py`.
- For undo-log shape questions, query `recent_undo_log(limit=5)` and
  paste the JSON into the results doc. The shape is the contract.

The build session is happy to take a follow-up handoff if any item
needs a code-side fix — same shape as `handoff-items-56-57.md`.
