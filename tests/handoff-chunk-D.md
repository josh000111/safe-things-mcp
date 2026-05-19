# Handoff: V2 Step 4 Chunk D — `propose_add_project` + `propose_update_project`

## Status coming in

| Chunk | Status |
|---|---|
| A — direct shortcuts + `complete_todo` | ✅ shipped + verified |
| B — `propose_update_todo` + `THINGS_MCP_AUTO_CONFIRM` | ✅ shipped + verified |
| C — `propose_move_todo` + `propose_delete_todo` | ✅ shipped + verified (items 56/57 target-validation bug fixed post-verification) |
| **D — `propose_add_project` + `propose_update_project`** | ⏳ **your job** |
| E — `propose_bulk_*` | ⏳ next |

**First thing:** run `git status` in `/Users/Shared/things-mcp` — there are untracked
verification/handoff files from the Test account that need committing before you
branch for chunk D.

---

## What to build

### `propose_add_project`

Creates a new Things project via the URL scheme. Two code paths depending on whether
the caller passes a `headings` array:

**No headings:**
```
things:///add-project?title=...&area-id=...&when=...&deadline=...&notes=...&tags=...
```

**With headings:**
```
things:///json?data=<url-encoded JSON>
```
where the JSON is:
```json
[{"type": "project", "title": "...", "items": [
  {"type": "heading", "title": "Design"},
  {"type": "to-do",   "title": "first task"}
]}]
```
This `things:///json` path is the **only** URL-scheme mechanism for creating native
headings. Use it whenever `headings` is non-empty. See arch doc §5.3 for details.

Does **not** require `THINGS_AUTH_TOKEN` (add-project is an unauthenticated call).

Required: `title`
Optional: `area_id`, `when` (`today`/`anytime`/`someday`), `deadline`, `notes`,
`tags`, `headings: list[str]`

### `propose_update_project`

Updates an existing project:
```
things:///update-project?id=...&auth-token=...&title=...&...
```

**Requires `THINGS_AUTH_TOKEN`** — same pattern as `propose_update_todo`.

Must take a before-state snapshot from the DB **before** the URL-scheme call, and
write the `undo_log` row before mutating — same pattern as `update_todo` handler.

Required: `project_id` + at least one field
Optional: `title`, `notes`, `when`, `deadline`, `tags`, `area_id`
Raise `ValueError` cleanly if no fields provided (same guard as `update_todo`).

---

## Key reference files

```
src/things_mcp/
  tools/propose.py                       # register the two new tools here
  services/handlers/
    add_todo.py                          # pattern: add handler, no auth token
    update_todo.py                       # pattern: update handler, auth token + before-state snapshot
  services/url_scheme.py                 # add build_add_project_url / build_update_project_url
  models.py                              # add ProjectCreate / ProjectUpdate Pydantic models
  config.py                              # no changes needed for chunk D

docs/things-mcp-V2-technical-architecture-and-implementation-plan.md   # §5.2, §5.3, §6 step 4 item 7
tests/things-mcp-manual-verification.md                                 # append chunk D items as 67+
```

---

## V2 acceptance gate (mandatory before shipping)

Each mutating tool needs: (a) inverse URL-scheme call in undo path, (b) `undo_log`
row written **before** mutation, (c) passing round-trip undo test.

- `propose_add_project` undo → soft-delete the created project
  (`update-project?canceled=true&completed=true` — **verify Things supports this on
  projects via URL scheme before wiring it up**)
- `propose_update_project` undo → re-apply before-state snapshot (same as
  `update_todo`)

---

## Manual verification items to write (append to `tests/things-mcp-manual-verification.md` as items 67+)

Write these before handing off to the Test account for sign-off:

1. `propose_add_project` (title only) → confirm → project appears in Things
2. `propose_add_project` with `area_id`, `notes`, `tags`, `when` → confirm → all
   fields present in Things
3. `propose_add_project` with `headings=['Design', 'Dev', 'QA']` → confirm → project
   opens in Things with three **native section headings** (not dummy tasks)
4. Undo `add_project` → project moves to Logbook (canceled)
5. `propose_update_project` (title change) → confirm → title updated in Things
6. Undo `update_project` → original title restored
7. `propose_update_project` with no fields → clean `ValueError`
8. `propose_update_project` without `THINGS_AUTH_TOKEN` → actionable error

---

## Gotchas

- **UUID recovery for `add_project`:** `add-todo` returns a UUID via the
  `x-callback-url` mechanism. Check whether `add-project` does the same, or whether
  you need to poll `get_projects()` by title to recover the UUID after creation.
  The arch doc is silent on this — investigate before assuming.
- **`things:///json` encoding:** the `data` param must be URL-encoded. Things is
  strict about the JSON structure — test the encoding carefully.
- **Project undo via URL scheme:** confirm `update-project?canceled=true&completed=true`
  actually works on projects (not just to-dos) before wiring the undo path.
