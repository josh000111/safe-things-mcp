# Handoff — close Step 5E and start Step 5B or 5C

Working directory: `/Users/Shared/things-mcp`. Branch: `main` (1 commit ahead of `origin/main`).
Run all commands as `joshsmith`.

---

## Context

Step 5E (`propose_delete_project` + `propose_cancel_project`) was built and verified by the
Test user in Round 8 (2026-05-30). Two bugs were found and fixed in the live test file during
that session — not in production code. Those fixes are sitting as an **unstaged change** on
`main`.

---

## Step 1 — Commit the test file fixes

`tests/test_step5e_live.py` has two fixes made by the Test user:

1. **Unconditional `pytestmark` skip** — was `pytest.mark.skip(...)` so the test always skipped
   even with `THINGS_AUTH_TOKEN` set. Changed to
   `pytest.mark.skipif(not os.environ.get("THINGS_AUTH_TOKEN"), ...)`.

2. **Broken Trash check** — `_in_trash_via_applescript` used `projects of list "Trash"` which
   throws Things error -1728. Changed to use `things_repo.trash()` (Python / SQLite read).

```bash
git add tests/test_step5e_live.py
git commit -m "Fix test_step5e_live: conditional skip + use things_repo.trash() for Trash check"
```

---

## Step 2 — Update the architecture doc status table

In `docs/things-mcp-V2-technical-architecture-and-implementation-plan.md` (line 26), change the
Step 5E Manual Testing column from:

```
⏳ Manual Testing Pending: `propose_delete_project` smoke-test needs Test user session
```

to:

```
✅ Verified (Round 8 — 2026-05-30)
```

Then commit and push:

```bash
git commit -am "Mark Step 5E manually verified (Round 8 — 2026-05-30)"
git push
```

---

## Step 3 — Preflight

```bash
uv run pytest -q --ignore=tests/test_step5a_live.py --ignore=tests/test_step5e_live.py
# expect: 325 passed
uv run things-mcp --help   # must exit 0
```

---

## Step 4 — Start the next build step

Per the §0 status table the two remaining unbuilt steps are:

| Step | What | Complexity |
|------|------|-----------|
| **5C** | `get_checklist_items` + `propose_append/prepend/replace_checklist` — URL scheme only, no AppleScript | Lower |
| **5B** | `propose_reorder_todos` — AppleScript reorder with native-heading auto-conversion to dummies | Higher |

**Recommendation:** build Step 5C first (URL-scheme only, self-contained, no AppleScript
complexity), then 5B. But consult `docs/things-mcp-V2-technical-architecture-and-implementation-plan.md`
§5.3 (reorder) and §5.4 (checklists) and decide.

Full implementation spec for both steps is in that doc. A detailed session plan may also exist
at `/Users/joshsmith/.claude/plans/` — check there before re-deriving.
