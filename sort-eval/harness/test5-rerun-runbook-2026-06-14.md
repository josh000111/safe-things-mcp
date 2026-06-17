# Test 5 — Blind Sort Rerun Runbook (handoff)

**Created:** 2026-06-14 by the scoring/dev session.
**Purpose:** self-contained instructions to run and score the NEXT Test 5 blind
sort. A fresh session should need only this file plus `test5-answer-key.md`,
`test5-scoring-template.md`, and `test5-blind-prompt.txt`.

---

## 0. Status — what happened before this runbook

- The 2026-06-14 blind run was scored in `test5-verification-2026-06-14.md`.
- Verified finding: the updated `instructions=` **were live** during that run
  (server processes started 18:16/18:18 > the 14:15 file edit). So the failures
  were genuine agent non-compliance, not stale instructions.
- Two **invariant** failures (group_id always null; `__NEWLY ADDED BY AI__`
  marker never created) were fixed **in code** this session — see §4.
- Two **judgment** items (cross-cluster abstain on #8/#28; ambiguous #5/#26) were
  left to a product decision and are NOT yet changed — see §5.

---

## 1. CRITICAL — restart the MCP server before the next run

The code fixes (§4) live in the working tree but the **running things-mcp server
still holds the pre-fix code** (and the pre-fix instructions, if it was started
earlier). Before the next blind run you MUST restart / reconnect the things-mcp
MCP server so both the new code and the current `instructions=` string are live.
If you skip this, you are testing the old build.

Confirm live after restart: a brand-new sort should produce `recent_undo_log`
rows with a non-null `group_id`, and moves into existing projects should create a
`__NEWLY ADDED BY AI__` heading.

---

## 2. Fixture state (as left by this session)

Reset was done via `undo` of the 2026-06-14 sort (no seed script exists). Current
state:

| Pre-flight check | Status |
|---|---|
| 5 survivor projects (Freelance: TechCorp API, Apartment Move, Recipe App, Shopping×2) | ✅ |
| No Carbonara / Bake a Cake projects (soft-undone to Logbook) | ✅ |
| 30 Test-5 tasks back in Inbox, **no abstain tags** | ✅ |
| "Research eco packing materials" notes + deadline 2026-07-15 intact | ✅ |
| Inbox contains **exactly 30** tasks | ❌ **see warning** |

### ⚠️ Blocking issue — 2 stray tasks in the Inbox

The Inbox currently holds **32** tasks: the 30 Test-5 tasks **plus** two
unrelated strays from a different test (a "5A hard-delete" run), created
2026-06-14 ~19:45–19:46:

- `5A-HARDDELETE-1781462807`
- `5A-HARDDELETE-1781462723`

These were NOT created by the Test 5 reset and may belong to a concurrent
session, so they were left in place. **Before a strict rerun, remove or relocate
them** so the Inbox is exactly the 30 Test-5 tasks. (Confirm they are not in use
elsewhere first.)

---

## 3. Running the blind session (unchanged from the corrected harness)

Follow `test5-blind-harness.md` §"Running the blind session". Essentials:

1. Fresh Claude Code session, **no shared context** with the dev/scoring session.
2. Working directory **`/Users/Test/Documents/Dev Tests/things-mcp-testing`**
   (NOT the repo — keeps the agent away from docs and the answer key).
3. `THINGS_MCP_ALLOW_APPLESCRIPT=1` set; `mcp__things-mcp__*` tools connected.
4. Paste `test5-blind-prompt.txt` verbatim ("Use things-mcp. Organise my Inbox
   into the correct projects and areas.").
5. Do not coach. Approve the new-project list when asked; do not steer naming or
   routing.
6. `whoami` must be `Test` (never `joshsmith`).

---

## 4. Code fixes shipped this session (need server restart to go live)

New module `src/things_mcp/state/sort_session.py` (process-scoped sort state).

- **group_id never null:** `propose_apply_ai_tags` opens a sort session and
  generates a `group_id` if the agent omits one; `propose_bulk_move`,
  `propose_move_under_ai_heading`, `propose_cleanup_ai_tags` inherit it;
  `propose_cleanup_ai_tags` closes the session.
- **AI heading enforced:** during an active sort, `propose_bulk_move` into a
  pre-existing **user** project is auto-promoted to the `move_under_ai_heading`
  path (creates `__NEWLY ADDED BY AI__`). AI-created projects (tracked in
  `add_project`) and Areas are excluded.

Trigger boundary (verified): the session is opened ONLY by `apply_ai_tags`.
`propose_move_todo` (single move), `propose_reorder_todos`, `propose_bulk_update`
and `propose_update_todo` do NOT touch it — so "schedule task X for Sunday" and
"reorder list X" never trigger the marker or grouping.

**Membership-gated (tightened):** a `bulk_move` is treated as part of the sort
(inherits group_id, can auto-promote to the marker) ONLY when *every* moved task
was tagged by the active sort (`sort_session.is_sort_move`). So even if a sort is
left open without cleanup, a later unrelated `bulk_move` of untagged tasks will
NOT inherit the group or get the marker. Multiple `apply_ai_tags` calls in one
sort reuse the same group and accumulate membership.

Tests: `tests/test_sort_session.py` (12). Full suite 490 passed, 1 skipped.

---

## 5. Ambiguity policy — DECIDED 2026-06-14: "abstain on true 50/50"

Policy: the agent should **guess when there is a real, evidence-backed lean**
(via a more-specific complementary task OR the weight of a cluster's surrounding
context) and **abstain (`*Ambiguous Home*`) only on a genuine coin-flip**. A
slight/hunch-only preference abstains. The `instructions=` CONTRASTIVE
DISAMBIGUATION paragraph was tuned to match this (needs server restart to go
live — see §1).

Grading the three contested tasks under this policy:

| # | Task | Real lean? | Expected (acceptable) | Miss |
|---|------|-----------|----------------------|------|
| 5 | Separate egg yolks from whites | Yes → Carbonara (cluster has "Stir yolks into pasta") | Carbonara *(abstain also OK)* | Bake a Cake |
| 8 | Mix ingredients | No — genuine coin-flip (both recipes mix) | `*Ambiguous Home*` (Inbox) | any cluster placement |
| 28 | Check temp midway | Yes → Bake a Cake (cluster has oven/sponge context) | Bake a Cake *(abstain also OK)* | Carbonara |

Net effect vs. the prior strict-abstain grading: #8 still requires abstain; #5
and #28 now accept the leaning cluster (or abstain). See
`test5-verification-2026-06-14.md` → "Caveats on the answer key".

---

## 6. Scoring the next run

1. Read actual state: `list_inbox`, `get_projects`, `get_project` on each.
2. Score against `test5-answer-key.md` using `test5-scoring-template.md` (copy it
   to `test5-verification-<date>.md` and fill in verdicts).
3. Pay special attention to the items in `test5-blind-harness.md` §"Scoring the
   rerun": project-contents-read, duplicate detection, Recipe App routing,
   cross-cluster abstain, singleton policy, lone-emoji, duplicate-named Shopping,
   `__NEWLY ADDED BY AI__` heading presence, and **group_id non-null**.
4. The singleton policy (harness §"Note on the answer key") still applies: a
   confident existing-Area placement of a singleton is a PASS, not a miss.
