# Handoff — Step 5B Manual Verification (propose_reorder_todos)

Working directory: `/Users/Shared/things-mcp`. Branch: `main`.
Run all commands as `joshsmith` (read steps) and `Test` user (write/verify steps).

---

## Context

Step 5B (`propose_reorder_todos`) was built at commit `5e99345` and all
401 unit tests pass. This session manually verifies the feature using the
Test user's Things library, following the same pattern as Step 5A (Round 7)
and Step 5E (Round 8).

Do NOT update the architecture doc status table until all items below pass.

---

## Preflight (run as `joshsmith`)

```bash
uv run pytest -q --ignore=tests/test_step5a_live.py --ignore=tests/test_step5e_live.py
# expect: 401 passed
uv run things-mcp --help
# expect: exits 0
whoami
# expect: joshsmith — STOP if this returns Test (wrong user for preflight)
```

---

## Setup — switch to Test user

Switch to the `Test` macOS user. Open Things 3. Start the MCP server pointed
at the **Test user's** Things library with both AppleScript flags set:

```bash
THINGS_AUTH_TOKEN=<test-user-token> \
THINGS_MCP_ALLOW_APPLESCRIPT=1 \
THINGS_MCP_ALLOW_EXPERIMENTAL_REORDER=1 \
uv --directory /Users/Shared/things-mcp run things-mcp
```

Or set env vars in the Test user's MCP client config as usual.

---

## Manual test items

### 5B-1: Full reorder in Today (no native headings)

1. Add 5 to-dos to Today via Things (titles: Task-A, Task-B, Task-C, Task-D, Task-E).
2. Read their UUIDs: `get_today_todos` or equivalent.
3. Call `propose_reorder_todos(container="today", new_order=[<E>, <D>, <C>, <B>, <A>])`.
4. Confirm the action.
5. Open Things → Today.
6. Verify order is E, D, C, B, A from top to bottom.

**Pass:** order matches. **Fail:** order unchanged or wrong.

---

### 5B-2: Partial reorder in Today (swap two, others keep position)

Using the same 5 tasks from 5B-1 (or create fresh ones):

1. Note current order: E D C B A.
2. Call `propose_reorder_todos(container="today", new_order=[<A>, <D>])`.
   - A is at position 4 (0-based), D is at position 1.
   - Expected result: D goes to position 1's slot, A goes to position 4's slot
     → order stays E A C B D (A and D swap with each other among the slots they
     originally occupied: slots 1 and 4 → D→slot1, A→slot4... wait).
   
   Actually: requested=[A, D]. A originally at index 4, D at index 1.
   Sorted slots: [1, 4]. requested[0]=A → slot 1. requested[1]=D → slot 4.
   Result: E A C B D.

3. Confirm the action.
4. Verify Things shows E, A, C, B, D.

**Pass:** only A and D moved, others unchanged. **Fail:** wrong order.

---

### 5B-3: Undo restores original order

After 5B-2:

1. Call `undo()` (using the undo_id from the confirm result).
2. Verify Things → Today shows the order from before 5B-2 (E D C B A).

**Pass:** original order restored. **Fail:** order wrong or undo errors.

---

### 5B-4: Reorder in a project (no native headings)

1. Create a project with 3 to-dos (titles: P1, P2, P3).
2. Read their UUIDs.
3. Call `propose_reorder_todos(container=<project_uuid>, new_order=[<P3>, <P2>, <P1>])`.
4. Confirm.
5. Open Things → project.
6. Verify order is P3, P2, P1.

**Pass:** order reversed. **Fail:** unchanged or error.

---

### 5B-5: Race-window detection

1. Call `propose_reorder_todos(container="today", new_order=[<some_uuids>])` to get
   an `action_id` (AUTO_CONFIRM must be OFF).
2. BEFORE calling `confirm_action`, add a new task to Today in Things directly.
3. Call `confirm_action(action_id)`.
4. Verify you get a RuntimeError mentioning "stale" or "re-propose required".

**Pass:** RuntimeError with "stale". **Fail:** confirms silently (race not detected).

---

### 5B-6: Reorder in a project WITH native headings (dummy conversion)

1. Create a project with a native heading (Things → Add Heading) dividing tasks:
   - Task-X (before heading)
   - [Heading: "Phase 1"]
   - Task-Y, Task-Z (after heading)
   
2. Read project UUID and task UUIDs (heading UUID will appear in items as type=heading).

3. Call `propose_reorder_todos(container=<project_uuid>, new_order=[<Z>, <Y>, <X>])`.

4. Read the preview — it should warn about native heading conversion and undo
   limitations.

5. Confirm the action.

6. Open Things → project. Verify:
   - Tasks appear in order Z, Y, X (possibly with a dummy heading task visible).
   - A dummy task titled `__Phase 1__` appears at the original heading position.
   - The original empty native heading "Phase 1" appears somewhere (likely bottom).

7. Note the `undo_id` from the result.

**Pass:** tasks reordered, dummy created, native heading at bottom.
**Fail:** error during execute, or tasks not reordered.

---

### 5B-7: Undo with native headings — dummies soft-deleted

After 5B-6:

1. Call `undo()` using the undo_id from 5B-6.
2. Verify:
   - Tasks in the project return to their original order (X, Y, Z).
   - The dummy `__Phase 1__` task is moved to Logbook (canceled+completed).
   - The original native heading is still at the bottom (undo cannot restore it).

**Pass:** order restored, dummy gone to Logbook.
**Fail:** undo errors, or dummy not soft-deleted.

---

## After all items pass

### 1. Update the architecture doc status table

In `docs/things-mcp-V2-technical-architecture-and-implementation-plan.md`
(line 23, Step 5B row), change the Manual Testing column from:

```
⏳ Manual Testing Pending
```

to:

```
✅ Verified (Round 10 — 2026-05-30)
```

(Adjust the round number and date to match when you actually run it.)

### 2. Commit and push

```bash
git commit -am "Mark Step 5B manually verified (Round N — YYYY-MM-DD)"
git push
```

### 3. Write closing notes

Note any deviations, partial failures, or follow-up issues in a brief
comment committed alongside the status update.

---

## If items fail

- Fix in implementation, add a failing unit test first (TDD discipline).
- Re-run full suite: `uv run pytest -q --ignore=tests/test_step5a_live.py --ignore=tests/test_step5e_live.py`
- Only mark verified after all items pass in a single Test-user session.
