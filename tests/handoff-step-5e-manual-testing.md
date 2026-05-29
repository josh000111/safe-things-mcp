# Step 5E manual testing — handoff prompt

Working directory: `/Users/Shared/things-mcp`. Branch: `main` (commit `359864f`).
Run all commands with `uv run …` (never bare `python`).

This is a **short session** — one live test to confirm `propose_delete_project`
(AppleScript → Trash) and its undo round-trip work correctly in the Test user's
Things environment.

The cancel tools (`propose_cancel_todo`, `propose_bulk_cancel`,
`propose_cancel_project`) are URL-scheme only and are fully covered by unit tests —
no live session needed for them.

---

## What was built (Step 5D + 5E)

| Tool | Mechanism | In NEVER_BYPASS_KINDS |
|---|---|---|
| `propose_cancel_todo` | URL scheme `update?canceled=true` | No |
| `propose_bulk_cancel` | URL scheme `update?canceled=true&completed=true` (N items) | Yes |
| `propose_cancel_project` | URL scheme `update-project?canceled=true` | No |
| `propose_delete_project` | AppleScript `delete (project id "X")` → Trash | Yes |

`propose_bulk_delete` was renamed to `propose_bulk_cancel` (honest semantics — it
was always URL-scheme cancel, not AppleScript delete).

Automated suite: **325 tests passing** (284 baseline → +41).

---

## Pre-flight

```bash
whoami           # must return: Test
uv run pytest -q --ignore=tests/test_step5a_live.py --ignore=tests/test_step5e_live.py
# must show 325 passed
uv run things-mcp --help   # must exit 0
```

Confirm Things 3 is running and the Test user's Things DB is active.

---

## Item 5E-1 — delete_project and undo round-trip

```bash
THINGS_AUTH_TOKEN=<Test-user-token> \
  THINGS_MCP_ALLOW_APPLESCRIPT=1 \
  uv run pytest tests/test_step5e_live.py::test_5e_delete_project_round_trip \
  -v -s
```

**Expected output** (edited for brevity):
```
PASSED tests/test_step5e_live.py::test_5e_delete_project_round_trip

  Created: id=<uuid>  title='5E-DELPROJECT-<ts>'  list=None
  execute() → {'action_kind': 'delete_project', 'undo_id': '...', 'id': '...', ...}
  Project <uuid> found in Things Trash
  undo() → {'undone': True, 'target_uuid': '...', 'restored_to': 'Anytime', ...}
  Project restored to list='Anytime' (reported restored_to='Anytime')
```

**Pass criteria:**
- Exit 0, test marked PASSED.
- `action_kind` in execute result is `"delete_project"`.
- Project appears in Things Trash after `execute()`.
- Project is no longer in Trash after `undo()`.
- Project is findable in Things DB (restored to Anytime) after `undo()`.
- `undo_log` row deleted after successful undo (asserted in test).
- Note that area membership is NOT restored — this is expected and documented.

**After the test:**
- Things Trash should be clear (undo moves the project back before test ends).
- Anytime may have a stray `5E-DELPROJECT-*` project — delete it manually from
  Things if present.

---

## Item 5E-2 — confirm Step 5A live test still passes

While in the Test user session, re-run the Step 5A test to confirm no regression:

```bash
THINGS_AUTH_TOKEN=<Test-user-token> \
  uv run pytest tests/test_step5a_live.py::test_132_133_hard_delete_and_undo \
  -v -s
```

Expected: PASSED.

---

## After verification passes

Switch back to the `joshsmith` user for source edits.

1. Open `docs/things-mcp-V2-technical-architecture-and-implementation-plan.md`.
2. In the §0 status table, update the Step 5E row's Manual Testing column to:
   `✅ Verified (Round 8 — 2026-MM-DD)` (fill in today's date).
3. Commit and push:
   ```bash
   git commit -am "Mark Step 5E manually verified (Round 8 — 2026-MM-DD)"
   git push
   ```

Once Step 5E is marked verified, consult
`docs/things-mcp-V2-technical-architecture-and-implementation-plan.md` for the
next build step (Step 5B — reorder todos, or Step 5C — checklist tools).
