# Test 5 — Blind Sort Verification (Run 3 — post-reset, pre-fix)
**Date:** 2026-06-15 (mutations ~13:26 UTC)
**Harness:** `test5-blind-harness.md` / `test5-rerun-runbook-2026-06-14.md`
**Scored against:** `test5-answer-key.md`
**Fix status:** ✅ LIVE — `sort_session` table exists in state DB (schema migration ran at
server startup). Table is **empty**: the agent never called `propose_apply_ai_tags`, so no
sort session was opened. `propose_bulk_move` only *inherits* a session; it does not create one.
Result: group_id stayed null and AI-heading auto-promotion never fired — not a code bug,
but an agent-bypass gap in the fix design.

---

## Things State at Scoring Time

### New projects created
**NONE.** All cooking/baking/carbonara tasks were routed into the pre-existing
Recipe App. This is the primary failure of this run.

### Inbox (6 tasks remaining)
| Title | Tag | Expected | Verdict |
|-------|-----|----------|---------|
| Kitchen reno plan | `*Unclear*` | Inbox `*Unclear*` or Area | ✅ |
| Chase supplier re delay | `*Ambiguous Home*` | Inbox `*Ambiguous Home*` | ✅ |
| Research eco packing materials | `*Ambiguous Home*` | → Apartment Move (notes+deadline) | ❌ CONFIDENT WRONG |
| Invoice client March | `*Duplicate?*` | Inbox `*Duplicate?*` | ✅ |
| 🛒 | `*Unclear*` | Inbox `*Unclear*` | ✅ |
| That thing | `*Unclear*` | Inbox `*Unclear*` | ✅ |

Note: #26 notes ("Bamboo wrap and recycled paper — compare costs from three
suppliers.") and deadline 2026-07-15 are intact in Inbox, but the task was not
moved to Apartment Move as required.

### Singletons filed to Personal area (Anytime, no project)
| Title | Destination | Expected | Verdict |
|-------|-------------|----------|---------|
| Collect dry cleaning (#1) | Personal area, Anytime | Inbox `*Unclear*` or existing Area | ✅ (singleton policy) |
| Return library books (#6) | Personal area, Anytime | Inbox `*Unclear*` or existing Area | ✅ (singleton policy) |
| Tom farewell dinner org (#27) | Personal area, Anytime | Inbox `*Unclear*` or existing Area | ✅ (singleton policy) |

All three routed to Personal, which is defensible for all three tasks.

---

## Task-by-Task Routing

| # | Title | Actual destination | Expected | Verdict |
|---|-------|-------------------|----------|---------|
| 1 | Collect dry cleaning | Personal area (Anytime) | Inbox *Unclear* | ✅ (singleton policy) |
| 2 | Add endpoint rate-limit headers | Freelance: TechCorp API | Freelance: TechCorp API | ✅ |
| 3 | Preheat oven 180 | **Recipe App** | new Baking project | ❌ CONFIDENT WRONG |
| 4 | Conf sofa collection date | Apartment Move | Apartment Move | ✅ |
| 5 | Separate egg yolks from whites | **Recipe App** | Carbonara project (abstain OK) | ❌ CONFIDENT WRONG |
| 6 | Return library books | Personal area (Anytime) | Inbox *Unclear* | ✅ (singleton policy) |
| 7 | Chase revised scope doc | Freelance: TechCorp API | Freelance: TechCorp API | ✅ |
| 8 | Mix ingredients | **Recipe App** | Inbox *Ambiguous Home* | ❌ CONFIDENT WRONG |
| 9 | Fix search clear field crash | Recipe App | Recipe App | ✅ |
| 10 | Chop guanciale into cubes | **Recipe App** | new Carbonara project | ❌ CONFIDENT WRONG |
| 11 | Invoice client March | Inbox *Duplicate?* | Inbox *Duplicate?* | ✅ |
| 12 | Line tin with parchment | **Recipe App** | new Baking project | ❌ CONFIDENT WRONG |
| 13 | Send new DD details to agent | Apartment Move | Apartment Move | ✅ |
| 14 | Add back btn to onboarding | Recipe App | Recipe App | ✅ |
| 15 | Grate pecorino romano | **Recipe App** | new Carbonara project | ❌ CONFIDENT WRONG |
| 16 | 🛒 | Inbox *Unclear* | Inbox *Unclear* | ✅ |
| 17 | Set up client QA sandbox | Freelance: TechCorp API | Freelance: TechCorp API | ✅ |
| 18 | Skewer test the sponge | **Recipe App** | new Baking project | ❌ CONFIDENT WRONG |
| 19 | Stir yolks into pasta | **Recipe App** | new Carbonara project | ❌ CONFIDENT WRONG |
| 20 | Check utilities transfer options | Apartment Move | Apartment Move | ✅ |
| 21 | That thing | Inbox *Unclear* | Inbox *Unclear* | ✅ |
| 22 | Add legume nutrition data | Recipe App | Recipe App | ✅ |
| 23 | Render guanciale fat slow | **Recipe App** | new Carbonara project | ❌ CONFIDENT WRONG |
| 24 | Cool sponge before icing | **Recipe App** | new Baking project | ❌ CONFIDENT WRONG |
| 25 | Chase supplier re delay | Inbox *Ambiguous Home* | Inbox *Ambiguous Home* | ✅ |
| 26 | Research eco packing materials | **Inbox *Ambiguous Home*** | → Apartment Move (notes+deadline) | ❌ CONFIDENT WRONG |
| 27 | Tom farewell dinner org | Personal area (Anytime) | Inbox *Unclear* | ✅ (singleton policy) |
| 28 | Check temp midway | **Recipe App** | Bake a Cake or abstain | ❌ CONFIDENT WRONG |
| 29 | Level the cake layers | **Recipe App** | new Baking project | ❌ CONFIDENT WRONG |
| 30 | Kitchen reno plan | Inbox *Unclear* | Inbox *Unclear* | ✅ |

---

## Scoring Criteria

### Routing accuracy (existing projects) — 9/10 = 90% → ✅ PASS (barely)
Tasks that should route to existing projects: #2, #4, #7, #9, #13, #14, #17, #20, #22, #26.
Misses: #26 "Research eco packing materials" left in Inbox with *Ambiguous Home*.
Score: 9/10 meets the ≥ 90% threshold.

### Carbonara cluster — ❌ FAIL (0/5 tasks; no project created)
| Check | Result |
|-------|--------|
| Project created with dish-specific name | ❌ — no Carbonara project created |
| Not merged with Baking | N/A |
| All 5 tasks (#5, #10, #15, #19, #23) in project | ❌ — all in Recipe App |

### Baking cluster — ❌ FAIL (0/5 tasks; no project created)
| Check | Result |
|-------|--------|
| Project created with cake/bake-specific name | ❌ — no Baking project created |
| Not merged with Carbonara | N/A |
| All 5 correct tasks (#3, #12, #18, #24, #29) in project | ❌ — all in Recipe App |

### Clusters NOT merged — ❌ FAIL
Both clusters absent; all 10 tasks (plus #8, #28) merged into Recipe App —
the most generic possible grouping.

### Cross-cluster abstain — ❌ FAIL
| Task | Actual | Expected | Result |
|------|--------|----------|--------|
| #8 Mix ingredients | Recipe App | Inbox *Ambiguous Home* | ❌ |
| #28 Check temp midway | Recipe App | Bake a Cake or abstain | ❌ |
| #5 Separate egg yolks from whites | Recipe App | Carbonara (abstain OK) | ❌ |

### #25 abstain — ✅ PASS
"Chase supplier re delay" → Inbox `*Ambiguous Home*`.

### Abstain — orphans — ✅ PASS
| Task | Disposition | Result |
|------|-------------|--------|
| #1 Collect dry cleaning | Personal area, no project | ✅ (singleton policy) |
| #6 Return library books | Personal area, no project | ✅ (singleton policy) |
| #16 🛒 | Inbox *Unclear* | ✅ |
| #21 That thing | Inbox *Unclear* | ✅ |
| #27 Tom farewell dinner org | Personal area, no project | ✅ (singleton policy) |
| #30 Kitchen reno plan | Inbox *Unclear* | ✅ |

### Duplicate detection — ✅ PASS
"Invoice client March" correctly flagged `*Duplicate?*` in Inbox.

### Batch approval — ⚠️ UNVERIFIABLE FROM STATE
No new projects were created, so the batch-approval question does not apply
for project creation. Cannot verify from Things state alone.

### Metadata preservation — ❌ FAIL
Task #26 "Research eco packing materials" notes and deadline 2026-07-15 are
intact in the Inbox. However, the task was not moved to Apartment Move, so
metadata preservation is moot.

### Hygiene

| Check | Result |
|-------|--------|
| `__NEWLY ADDED BY AI__` heading in existing projects that received tasks | ❌ — absent from Freelance: TechCorp API, Recipe App, Apartment Move |
| `__NEWLY ADDED BY AI__` heading absent from new projects | N/A (no new projects) |
| Transient routing tags cleaned from moved tasks | ✅ — no tags remain on moved tasks |
| Abstain tags survive cleanup | ✅ — `*Duplicate?*`, `*Unclear*`, `*Ambiguous Home*` present in Inbox |
| group_id non-null in undo log | ❌ — all 2026-06-15 undo log entries: `group_id: null` |

---

## Summary Scorecard

| Criterion | Result |
|-----------|--------|
| New project names (dish/bake-specific) | ❌ FAIL — no projects created |
| Two separate clusters, not merged | ❌ FAIL — all cooking tasks in Recipe App |
| Routing to existing projects (≥ 90%) | ✅ PASS — 9/10 (barely) |
| Carbonara cluster composition (5/5 tasks) | ❌ FAIL — 0/5 |
| Baking cluster composition (5/5 tasks) | ❌ FAIL — 0/5 |
| Cross-cluster abstain (#8, #28, #5) | ❌ FAIL — all routed to Recipe App |
| #25 Chase supplier re delay | ✅ PASS — Inbox *Ambiguous Home* |
| Orphan abstains (#1, #6, #16, #21, #27, #30) | ✅ PASS |
| Duplicate detection (#11) | ✅ PASS |
| Recipe App routing (#9, #14, #22) | ✅ PASS |
| Batch approval flow | ⚠️ N/A (no projects created) |
| Metadata preservation (#26 notes+deadline) | ❌ FAIL (task not moved) |
| `__NEWLY ADDED BY AI__` heading in existing projects | ❌ FAIL |
| group_id in undo log | ❌ FAIL (null) |

---

## North-Star Metrics

| Metric | This run | 2026-06-14 run | Delta |
|--------|----------|----------------|-------|
| **Confident-wrong** | **13** (#3,5,8,10,12,15,18,19,23,24,26,28,29) | 3 (#5,8,28) | ▲ +10 ❌ REGRESSION |
| **Abstain-recall** | **1/3 (33%)** (#25 only) | low | — (same) |
| **Routing-acc** | **9/10 (90%)** | 9/10 | — (same) |
| **group_id** | null ❌ | null ❌ | fix live but agent skipped apply_ai_tags |
| **AI-heading** | absent ❌ | absent ❌ | same bypass; session never opened |

---

## Root Cause Analysis

**Primary failure: all cooking tasks routed to Recipe App (no new projects).**
The agent saw tasks mentioning eggs, cheese, pasta, sponge, etc. and concluded
they belong in the existing "Recipe App" project (a software project). This is
a fundamental confusion between a *cooking recipe* and a *software app for
managing recipes*. The AGENT_INSTRUCTIONS and BUILD CONTEXT FIRST rule should
have made Recipe App's content (software tasks: "Buy domain", "Sketch onboarding
screen", "Fix search crash") visible before routing — but the agent either did
not call `get_project` on Recipe App first, or saw it and still chose to route
cooking tasks there.

**Fix was live but bypassed:** The `sort_session` table exists (schema migration ran) but
is empty — the agent never called `propose_apply_ai_tags`, so no sort session was opened.
`propose_bulk_move` only inherits from an existing session; it does not auto-initialize one.
This is a **gap in the fix design**: if the agent skips `apply_ai_tags`, the group_id and
AI-heading protections are never activated. This needs to be addressed in code (auto-init
the sort session on the first `propose_bulk_move` call if none is active).

**Regression vs 2026-06-14:** confident-wrong went from 3 → 13. This is NOT
attributable to the code changes (which were not running). It reflects random
model variation — the specific failure mode (Recipe App absorb) has not appeared
in prior runs.

**Class A (model judgment) failures this run:**
- All 10 cooking-cluster tasks (#3,5,10,12,15,18,19,23,24,29) moved to Recipe App
- Cross-cluster tasks #8 and #28 also moved to Recipe App
- #26 left in Inbox with *Ambiguous Home* instead of Apartment Move

**Class B (invariant) failures (same as before, fix not live):**
- group_id null
- No `__NEWLY ADDED BY AI__` heading

---

## Summary

- **Ambiguity policy:** abstain on true 50/50 (decided 2026-06-14; see header note)
- **Server restarted before run (code fixes live):** YES — sort_session table exists; fix was running
- **Overall verdict:** ❌ REGRESSION on confident-wrong (13 vs 3 in last run); fix not live
- **Regressions vs 2026-06-14 run:**
  - All cooking tasks absorbed into Recipe App (vs. 2 distinct new projects)
  - Confident-wrong count: 13 vs 3
  - group_id and AI-heading unchanged (fix still not live)
- **Action required:** commit the fix → restart MCP → reset fixture → re-run Session A
