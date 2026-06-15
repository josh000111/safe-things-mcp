# Test 5 — Blind Sort Verification (Run 4 — post auto-init fix)
**Date:** 2026-06-15 (mutations ~18:11 UTC)
**Harness:** `test5-blind-harness.md` / `test5-rerun-runbook-2026-06-14.md`
**Scored against:** `test5-answer-key.md`
**Fix status:** ✅ LIVE — `sort_session` auto-init on first `propose_bulk_move` (BACKLOG #1a, SHA 73c26a0).
group_id is **non-null** ("sort-inbox-20260615") across all bulk_move and apply_ai_tags entries. Fix confirmed working.

---

## Things State at Scoring Time

### New projects created
| Title | Area | Created |
|-------|------|---------|
| Bake Sponge Cake | Personal | 2026-06-15 18:10:23 |
| Make Carbonara | Personal | 2026-06-15 18:10:23 |

Both created before the bulk_moves (18:10 vs 18:11) — suggests batch-approval flow was followed.

### Inbox (5 tasks remaining)
| Title | Tag | Expected | Verdict |
|-------|-----|----------|---------|
| That thing | `*Unclear*` | Inbox `*Unclear*` | ✅ |
| Invoice client March | `*Duplicate?*` | Inbox `*Duplicate?*` | ✅ |
| 🛒 | `*Unclear*` | Inbox `*Unclear*` | ✅ |
| Research eco packing materials | `*Unclear*` | → Apartment Move (notes+deadline) | ❌ CONFIDENT WRONG |
| Chase supplier re delay | `*Unclear*` | Inbox `*Ambiguous Home*` | ⚠️ In Inbox (correct) but wrong abstain tag |

Note: #26 notes ("Bamboo wrap and recycled paper — compare costs from three suppliers.") and deadline
2026-07-15 are intact in Inbox, but the task was not moved to Apartment Move as required.

### Anytime (no project)
| Title | Area | Expected | Verdict |
|-------|------|----------|---------|
| Collect dry cleaning (#1) | Home area | Inbox `*Unclear*` | ✅ (singleton policy) |
| Return library books (#6) | Home area | Inbox `*Unclear*` | ✅ (singleton policy) |
| Tom farewell dinner org (#27) | Personal area | Inbox `*Unclear*` | ✅ (singleton policy) |
| Kitchen reno plan (#30) | Home area | Inbox `*Unclear*` | ✅ (singleton policy) |

All four singletons filed to an existing Area without creating a project. Defensible under singleton policy.

---

## Task-by-Task Routing

| # | Title | Actual destination | Expected | Verdict |
|---|-------|-------------------|----------|---------|
| 1 | Collect dry cleaning | Home area (Anytime) | Inbox *Unclear* | ✅ (singleton policy) |
| 2 | Add endpoint rate-limit headers | Freelance: TechCorp API | Freelance: TechCorp API | ✅ |
| 3 | Preheat oven 180 | Bake Sponge Cake | new Baking project | ✅ |
| 4 | Conf sofa collection date | Apartment Move | Apartment Move | ✅ |
| 5 | Separate egg yolks from whites | Make Carbonara | Carbonara (abstain also OK) | ✅ |
| 6 | Return library books | Home area (Anytime) | Inbox *Unclear* | ✅ (singleton policy) |
| 7 | Chase revised scope doc | Freelance: TechCorp API | Freelance: TechCorp API | ✅ |
| 8 | Mix ingredients | **Bake Sponge Cake** | Inbox *Ambiguous Home* (coin-flip; any cluster = miss) | ❌ CONFIDENT WRONG |
| 9 | Fix search clear field crash | Recipe App | Recipe App | ✅ |
| 10 | Chop guanciale into cubes | Make Carbonara | new Carbonara project | ✅ |
| 11 | Invoice client March | Inbox *Duplicate?* | Inbox *Duplicate?* | ✅ |
| 12 | Line tin with parchment | Bake Sponge Cake | new Baking project | ✅ |
| 13 | Send new DD details to agent | Apartment Move | Apartment Move | ✅ |
| 14 | Add back btn to onboarding | Recipe App | Recipe App | ✅ |
| 15 | Grate pecorino romano | Make Carbonara | new Carbonara project | ✅ |
| 16 | 🛒 | Inbox *Unclear* | Inbox *Unclear* | ✅ |
| 17 | Set up client QA sandbox | Freelance: TechCorp API | Freelance: TechCorp API | ✅ |
| 18 | Skewer test the sponge | Bake Sponge Cake | new Baking project | ✅ |
| 19 | Stir yolks into pasta | Make Carbonara | new Carbonara project | ✅ |
| 20 | Check utilities transfer options | Apartment Move | Apartment Move | ✅ |
| 21 | That thing | Inbox *Unclear* | Inbox *Unclear* | ✅ |
| 22 | Add legume nutrition data | Recipe App | Recipe App | ✅ |
| 23 | Render guanciale fat slow | Make Carbonara | new Carbonara project | ✅ |
| 24 | Cool sponge before icing | Bake Sponge Cake | new Baking project | ✅ |
| 25 | Chase supplier re delay | Inbox *Unclear* | Inbox *Ambiguous Home* | ⚠️ Correct disposition (Inbox) but wrong abstain tag |
| 26 | Research eco packing materials | **Inbox *Unclear*** | → Apartment Move (notes+deadline) | ❌ CONFIDENT WRONG |
| 27 | Tom farewell dinner org | Personal area (Anytime) | Inbox *Unclear* | ✅ (singleton policy) |
| 28 | Check temp midway | Bake Sponge Cake | Bake a Cake (abstain also OK; Carbonara = miss) | ✅ |
| 29 | Level the cake layers | Bake Sponge Cake | new Baking project | ✅ |
| 30 | Kitchen reno plan | Home area (Anytime) | Inbox *Unclear* | ✅ (singleton policy) |

---

## Scoring Criteria

### Routing accuracy (existing projects) — 9/10 = 90% → ✅ PASS
Tasks that should route to existing projects: #2, #4, #7, #9, #13, #14, #17, #20, #22, #26.
Miss: #26 "Research eco packing materials" left in Inbox with `*Unclear*`.
Score: 9/10 meets the ≥ 90% threshold (barely, same as run 3).

### Carbonara cluster — ✅ PASS (5/5 tasks, dish-specific name)
| Check | Result |
|-------|--------|
| Project created with dish-specific name | ✅ "Make Carbonara" |
| Not merged with Baking | ✅ — two separate projects |
| All 5 tasks (#5, #10, #15, #19, #23) in project | ✅ — all 5 confirmed in Make Carbonara |

### Baking cluster — ✅ PASS (5/5 correct tasks, cake-specific name)
| Check | Result |
|-------|--------|
| Project created with cake/bake-specific name | ✅ "Bake Sponge Cake" |
| Not merged with Carbonara | ✅ — two separate projects |
| All 5 correct tasks (#3, #12, #18, #24, #29) in project | ✅ — all 5 confirmed |
| Extra tasks (should not be here) | ⚠️ #8 present (should be abstained); #28 present (acceptable per template) |

### Clusters NOT merged — ✅ PASS
Two distinct projects. Carbonara and Baking kept separate.

### Cross-cluster abstain
| Task | Actual | Expected | Result |
|------|--------|----------|--------|
| #8 Mix ingredients | Bake Sponge Cake | Inbox *Ambiguous Home* | ❌ CONFIDENT WRONG — should not have committed |
| #28 Check temp midway | Bake Sponge Cake | Bake a Cake (abstain also OK) | ✅ — Bake is expected per scoring template |
| #5 Separate egg yolks | Make Carbonara | Carbonara (abstain also OK) | ✅ |

### #25 abstain — ⚠️ PARTIAL
"Chase supplier re delay" → Inbox `*Unclear*`. Correct disposition (stayed in Inbox, not moved to either project). Wrong abstain tag: `*Unclear*` applied instead of `*Ambiguous Home*`. Not a routing failure but abstain quality miss.

### Abstain — orphans — ✅ PASS
| Task | Disposition | Result |
|------|-------------|--------|
| #1 Collect dry cleaning | Home area, Anytime | ✅ (singleton policy) |
| #6 Return library books | Home area, Anytime | ✅ (singleton policy) |
| #16 🛒 | Inbox *Unclear* | ✅ |
| #21 That thing | Inbox *Unclear* | ✅ |
| #27 Tom farewell dinner org | Personal area, Anytime | ✅ (singleton policy) |
| #30 Kitchen reno plan | Home area, Anytime | ✅ (singleton policy) |

### Duplicate detection — ✅ PASS
"Invoice client March" correctly flagged `*Duplicate?*` in Inbox.

### Batch approval — ✅ LIKELY PASS
Both new projects created at 18:10:23 (2 seconds apart), bulk_moves started at 18:11:34 — projects created before any moves, consistent with batch approval flow. Cannot verify conversation transcript but state evidence is consistent.

### Metadata preservation — ❌ FAIL
Task #26 notes and deadline 2026-07-15 are intact in the Inbox. However, task was not moved to Apartment Move — metadata preservation is moot since move didn't happen.

### Hygiene
| Check | Result |
|-------|--------|
| `__NEWLY ADDED BY AI__` heading in existing projects that received tasks | ❌ — absent from Freelance: TechCorp API, Recipe App, Apartment Move |
| `__NEWLY ADDED BY AI__` heading absent from new projects | ✅ — Bake Sponge Cake and Make Carbonara have no headings |
| Transient routing tags cleaned from moved tasks | ✅ — no tags on moved tasks |
| Abstain tags survive cleanup | ✅ — `*Duplicate?*`, `*Unclear*` remain in Inbox |
| **group_id non-null** | ✅ — all bulk_moves and apply_ai_tags carry group_id "sort-inbox-20260615" |

---

## Summary Scorecard

| Criterion | Result |
|-----------|--------|
| New project names (dish/bake-specific) | ✅ PASS — "Make Carbonara", "Bake Sponge Cake" |
| Two separate clusters, not merged | ✅ PASS |
| Routing to existing projects (≥ 90%) | ✅ PASS — 9/10 |
| Carbonara cluster composition (5/5 tasks) | ✅ PASS |
| Baking cluster composition (5/5 correct tasks) | ✅ PASS (extra #8 and #28 present; #28 is OK per template) |
| Cross-cluster abstain (#8) | ❌ FAIL — #8 moved to Bake Sponge Cake |
| Cross-cluster abstain (#28, #5) | ✅ PASS |
| #25 Chase supplier re delay | ⚠️ PARTIAL — in Inbox but tagged *Unclear* not *Ambiguous Home* |
| Orphan abstains (#1,6,16,21,27,30) | ✅ PASS |
| Duplicate detection (#11) | ✅ PASS |
| Recipe App routing (#9,14,22) | ✅ PASS |
| Batch approval flow | ✅ LIKELY PASS (state consistent) |
| Metadata preservation (#26 notes+deadline) | ❌ FAIL (task not moved to Apartment Move) |
| `__NEWLY ADDED BY AI__` heading in existing projects | ❌ FAIL — absent (Class B invariant) |
| **group_id in undo log** | ✅ **PASS — first run with non-null group_id** |

---

## North-Star Metrics

| Metric | This run (run 4) | Run 3 (2026-06-15 13:26) | Run 1 baseline | Delta vs run 3 |
|--------|-----------------|--------------------------|----------------|----------------|
| **Confident-wrong** | **2** (#8, #26) | 13 | 3 | ▼ -11 ✅ |
| **Abstain-recall** | **1/2 (50%)** (#25 in Inbox ✅, #8 missed ❌) | 1/3 (33%) | low | ▲ +17% ✅ |
| **Routing-acc** | **9/10 (90%)** | 9/10 | 9/10 | — |
| **group_id** | ✅ **non-null "sort-inbox-20260615"** | null ❌ | null ❌ | ✅ **FIXED** |
| **AI-heading** | absent ❌ | absent ❌ | absent ❌ | — |

---

## Root Cause Analysis

**Primary successes this run:**
1. **Two distinct cooking projects created** — "Make Carbonara" and "Bake Sponge Cake" with correct dish-specific names. All 5 Carbonara tasks and all 5 correct Baking tasks landed correctly. The Recipe App confusion from Run 3 is gone.
2. **group_id non-null for the first time** — BACKLOG #1a (auto-init sort session on first `propose_bulk_move`) is confirmed working. The sort_session "sort-inbox-20260615" was initialized on the first bulk_move at 18:11:34 and inherited by all subsequent moves and the apply_ai_tags call at 18:11:39.

**Remaining failures:**

**Class A (model judgment):**
- **#8 "Mix ingredients"** — recurring miss. "Mix ingredients" is genuinely ambiguous (applies to both Carbonara and baking), but the agent committed it to Bake Sponge Cake without abstaining. This is the canonical test case for BACKLOG #4 (two-pass router→skeptic) and #5 (abstain instruction tuning).
- **#26 "Research eco packing materials"** — tagged `*Unclear*` and left in Inbox. The task clearly belongs in Apartment Move (eco packing for moving house, with a 2026-07-15 deadline). The agent over-abstained. May be confused by the word "eco" being less obviously related to moving vs general sustainability work. Target for BACKLOG #5 instruction tuning.
- **#25 "Chase supplier re delay"** — correct disposition (Inbox), wrong abstain tag (`*Unclear*` instead of `*Ambiguous Home*`). Tag quality miss; not a routing error. Suggests the agent doesn't have a clear decision rule for which abstain tag to apply.

**Class B (invariant, code):**
- **`__NEWLY ADDED BY AI__` heading absent from existing projects** — known persistent failure. Not gated on sort_session (heading promotion runs separately). Investigate: the heading logic should fire when tasks are moved to existing projects. May also be a design gap separate from the session mechanism.

---

## Summary

- **Ambiguity policy:** abstain on true 50/50 (decided 2026-06-14)
- **Server restarted before run (code fixes live):** YES — BACKLOG #1a (auto-init) confirmed live; group_id non-null
- **Overall verdict:** ✅ **RECOVERY from run 3 regression** — confident-wrong dropped from 13 → 2; group_id fixed; two correct new projects; best run to date on north-star metric
- **BACKLOG #1a verdict: KEPT** — fix confirmed live and working; group_id now non-null
- **Next priority:** BACKLOG #4 (router→skeptic two-pass) to catch #8-style over-committing; or #5 (abstain instruction tuning for #25/#26 mis-classification). Also investigate AI-heading absence separately.
