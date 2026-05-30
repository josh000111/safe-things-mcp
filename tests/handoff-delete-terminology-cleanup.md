# Delete terminology cleanup — handoff prompt

Working directory: `/Users/Shared/things-mcp`. Branch: `main`.
Run all commands with `uv run …` (never bare `python`).

---

## Background

The codebase grew through two design generations:

- **Gen 1 (removed):** "soft-delete" — cancel + complete via URL scheme, moved task to
  Logbook. This was the original `delete_todo` handler. It has been removed.
- **Gen 2 (current):** "hard-delete" — AppleScript `delete` → moves to Things Trash.
  This is what `propose_delete_todo` and `propose_delete_project` do today.

The gen-1 terminology was never fully purged. The agreed naming going forward is:
- **"delete"** (or "move to Trash") for the AppleScript Trash operation.
- **"cancel"** / "move to Logbook" for the cancel+complete undo path used by
  `add_todo`, `add_project`, and `add_heading` undos.
- No more "soft-delete" or "hard-delete" in any user-visible surface.

---

## Required changes

### 1. Delete the orphan files

```
tests/delete_todo_new.py   # first line says "Accidental copy — do not import"
src/things_mcp/services/handlers/delete_todo.py  # tombstone stub, no live code
```

Verify nothing imports either before deleting:
```bash
grep -r "delete_todo_new\|from.*delete_todo import" src/ tests/ --include="*.py"
```

### 2. Rename `hard_delete_todo` → `delete_todo` throughout

Files to update:
- `src/things_mcp/services/handlers/hard_delete_todo.py` → rename file to `delete_todo.py`
- `src/things_mcp/services/handlers/__init__.py` — update import and registry key
- `src/things_mcp/tools/propose.py` — update two references
- `src/things_mcp/config.py` — update the `APPLESCRIPT_KINDS` list entry and comment

The `KIND` string inside `hard_delete_todo.py` is `"delete_todo"` — confirm it is
already correct before renaming (the public kind string never used "hard"). If so,
no migration of the state DB is needed.

### 3. Scrub user-visible docstrings

| File | Current text | Replace with |
|------|-------------|--------------|
| `src/things_mcp/tools/undo.py` line ~20 | `"Soft-undo: the task is marked completed and canceled). True hard-delete arrives with propose_delete_todo."` | `"Undo is a soft-cancel: the task is marked completed and canceled, moving it to Logbook. To permanently delete a task use propose_delete_todo (moves to Trash)."` |
| `src/things_mcp/services/handlers/add_todo.py` line ~10 | reference to "hard-delete" | rephrase to "move to Trash" |
| `src/things_mcp/services/url_scheme.py` lines ~291-292 | "soft-delete shape" | "cancel-to-Logbook shape" |
| `src/things_mcp/config.py` lines ~27, 38, 40 | "hard-delete" in comments | "→ Trash" or "delete (Trash)" |

### 4. Verify no regressions

```bash
uv run pytest -q
# expect: all tests pass (400 baseline)
uv run things-mcp --help
# expect: exits 0
```

---

## What NOT to change

- **Historical handoff and verification `.md` files in `tests/`** — leave as-is.
  They are historical records; rewriting them would be misleading.
- **The undo mechanism itself** — `add_todo`, `add_project`, and `add_heading` undos
  legitimately cancel+complete to Logbook. This behaviour is not changing, only the
  label applied to it.
- **`propose_cancel_todo` / `propose_bulk_cancel` / `propose_cancel_project`** —
  these are correctly named and are not part of this cleanup.

---

## Acceptance criteria

- [ ] `grep -r "hard.delete\|soft.delete" src/ --include="*.py"` returns zero hits
- [ ] `hard_delete_todo.py` no longer exists; `delete_todo.py` exists in its place
- [ ] `delete_todo_new.py` deleted
- [ ] Old tombstone `delete_todo.py` stub deleted (replaced by the real handler)
- [ ] All tests pass
- [ ] `git diff --stat` shows only the files listed above touched

---

## Commit message

```
Rename hard_delete_todo → delete_todo; scrub soft/hard-delete terminology

No behaviour change. Internal handler renamed to match the agreed
user-facing language: "delete" (→ Trash) and "cancel" (→ Logbook).
Orphan files delete_todo_new.py and the old soft-delete stub removed.
```
