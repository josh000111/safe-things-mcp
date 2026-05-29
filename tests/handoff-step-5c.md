# Handoff — Step 5C manual verification

Working directory: `/Users/Shared/things-mcp`. Branch: `main`.
Run all commands as `joshsmith`. All manual testing as the **Test** user.

---

## Context

Step 5C (`get_checklist_items`, `propose_append_checklist_items`,
`propose_prepend_checklist_items`, `propose_replace_checklist`) was built
in this session and committed at `d64588d`. 353 automated tests pass.

---

## Step 1 — Preflight (run as `joshsmith`)

```bash
uv run pytest -q --ignore=tests/test_step5a_live.py --ignore=tests/test_step5e_live.py
# expect: 353 passed
uv run things-mcp --help   # must exit 0
```

---

## Step 2 — Manual verification (run as Test user)

**Before starting:** `whoami` → must return `Test` (not `joshsmith`).
`THINGS_AUTH_TOKEN` must be set in Claude Desktop config. Restart Claude
Desktop after any config change.

Work through items **136–146** in
`tests/things-mcp-manual-verification.md`. Each item is self-contained.

### Quick summary of what each item covers

| # | What |
|---|------|
| 136 | `get_checklist_items` returns 3 items in order |
| 137 | `get_checklist_items` on no-checklist todo → `[]` |
| 138 | `propose_append_checklist_items` adds to end; undo_log row created |
| 139 | Undo of append restores 3 items |
| 140 | AUTO_CONFIRM works for append |
| 141 | `propose_prepend_checklist_items` inserts at front |
| 142 | Undo of prepend restores original |
| 143 | `propose_replace_checklist` overwrites; never auto-confirmed |
| 144 | Undo of replace restores original |
| 145 | Replace with `items=[]` clears checklist; undo restores |
| 146 | AUTO_CONFIRM cannot bypass replace (NEVER_BYPASS_KINDS guard) |

---

## Step 3 — Mark verified and update doc

After all 11 items pass, update the §0 status table in
`docs/things-mcp-V2-technical-architecture-and-implementation-plan.md`
(line ~24):

```
⏳ Manual Testing Pending: Test user session needed
```
→
```
✅ Verified (Round 9 — <date>)
```

Commit and push:

```bash
git commit -am "Mark Step 5C manually verified (Round 9 — <date>)"
git push
```

---

## Step 4 — Next build step

The only remaining unbuilt step is **5B** (`propose_reorder_todos` with
native-heading auto-conversion). Full spec is in
`docs/things-mcp-V2-technical-architecture-and-implementation-plan.md`
§5.3 and the plan file at
`/Users/joshsmith/.claude/plans/review-docs-things-mcp-v2-technical-arch-declarative-hennessy.md`
(§5B subsection, lines 81–108).

Step 5B is the most complex remaining piece: AppleScript reorder command,
native-heading detection and dummy-conversion at propose time, race-window
detection at execute time. Recommend a fresh session with the plan file
loaded as context.
