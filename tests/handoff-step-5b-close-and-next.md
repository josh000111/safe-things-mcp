# Step 5B close-out — handoff prompt

Working directory: `/Users/Shared/things-mcp`. Branch: `main` (commit `e5bd8cb`).
Run all commands with `uv run …` (never bare `python`).

---

## Context

Step 5B (`propose_reorder_todos`) was manually verified by the Test user on 2026-05-30
(Round 10). All 7 items passed in a single session. 400 unit tests pass.

The only remaining task is updating the architecture doc status row and committing.

---

## What was verified (Round 10 — 2026-05-30)

| Item | Description | Result |
|------|-------------|--------|
| 5B-1 | Full reorder in Today (E→D→C→B→A) | ✅ PASS |
| 5B-2 | Partial reorder — swap A & D → E,A,C,B,D; C and B unmoved | ✅ PASS |
| 5B-3 | Undo of 5B-2 restores pre-swap order (E,D,C,B,A) | ✅ PASS |
| 5B-4 | Full reorder in project P1,P2,P3 → P3,P2,P1 | ✅ PASS |
| 5B-5 | Race-window detection: stale UUID error fires when Today changes between propose and confirm | ✅ PASS |
| 5B-6 | Native-heading project: dummy `__Phase 1__` created, warning present in preview | ✅ PASS |
| 5B-7 | Undo of 5B-6: tasks restored to original order; dummy task canceled to Logbook | ✅ PASS |

Notes:
- 5B-5 was simulated by adding a task programmatically between `propose` and `confirm`
  (no manual timing needed). The error message named the unexpected UUID explicitly.
- 5B-6/5B-7: the native heading landed at the project bottom before reorder (URL scheme
  adds new tasks above it). Dummy heading `__Phase 1__` still correctly created and
  soft-deleted on undo. Behavior matches spec.
- Preflight: 400 tests pass (handoff expected 401 — one test was consolidated before
  this session; not a blocker). `uv run things-mcp --help` exits 0.

---

## Action required

### 1. Update the architecture doc

File: `docs/things-mcp-V2-technical-architecture-and-implementation-plan.md`, line 23.

Change:
```
| V2 step 5B — reorder todos in lists/projects (with native-heading auto-conversion to dummies at original positions) | ⏳ Not built | ⏳ Manual Testing Session: Not yet run |
```

To:
```
| V2 step 5B — reorder todos in lists/projects (with native-heading auto-conversion to dummies at original positions) | ✅ Done (400 tests pass) | ✅ Verified (Round 10 — 2026-05-30; all items 5B-1 through 5B-7 pass) |
```

### 2. Commit and push

```bash
git add docs/things-mcp-V2-technical-architecture-and-implementation-plan.md
git commit -m "Mark Step 5B manually verified (Round 10 — 2026-05-30)"
git push
```

Do **not** stage `README.md` — it has a pre-existing uncommitted change unrelated to
Step 5B.

---

## What's next

Refer to the architecture doc status table for the next unverified or unbuilt step.
As of this handoff the known outstanding items include:
- Soft/hard-delete terminology cleanup (internal rename + docstring pass) — tracked
  separately in `tests/handoff-delete-terminology-cleanup.md`.
