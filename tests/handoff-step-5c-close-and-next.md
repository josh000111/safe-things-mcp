# Handoff — close Step 5C and start Step 5B

Working directory: `/Users/Shared/things-mcp`. Branch: `main`.
Run all commands as `joshsmith`.

---

## Context

Step 5C (`get_checklist_items`, `propose_append_checklist_items`,
`propose_prepend_checklist_items`, `propose_replace_checklist`) was built at
commit `d64588d` and manually verified by the Test user in Round 9 (2026-05-30).
All 11 items (136–146) passed. One new unit test was added during verification
(`test_propose_append_auto_confirms_when_flag_set`). Suite is now **354 tests**.

The test file change is an **unstaged modification** on `main`.

---

## Step 1 — Commit the new test

`tests/test_step5c_checklist.py` has one new test added by the Test user:
`test_propose_append_auto_confirms_when_flag_set` — verifies that
`AUTO_CONFIRM=True` produces `auto_confirmed: True` for append (was untested).

```bash
git add tests/test_step5c_checklist.py
git commit -m "Add AUTO_CONFIRM=True unit test for propose_append_checklist_items"
```

---

## Step 2 — Update the architecture doc status table

In `docs/things-mcp-V2-technical-architecture-and-implementation-plan.md`
(line 24), change the Step 5C Manual Testing column from:

```
⏳ Manual Testing Pending: Test user session needed
```

to:

```
✅ Verified (Round 9 — 2026-05-30)
```

Then commit and push:

```bash
git commit -am "Mark Step 5C manually verified (Round 9 — 2026-05-30)"
git push
```

---

## Step 3 — Preflight

```bash
uv run pytest -q --ignore=tests/test_step5a_live.py --ignore=tests/test_step5e_live.py
# expect: 354 passed
uv run things-mcp --help   # must exit 0
```

---

## Step 4 — Start Step 5B

The only remaining unbuilt step is **5B** (`propose_reorder_todos` with
native-heading auto-conversion). This is the most complex remaining piece:

- AppleScript reorder command
- Native-heading detection and dummy-conversion at propose time
- Race-window detection at execute time

Full spec is in `docs/things-mcp-V2-technical-architecture-and-implementation-plan.md`
§5.3. A detailed session plan may also exist at
`/Users/joshsmith/.claude/plans/` — check for a Step 5B subsection before
re-deriving from scratch.
