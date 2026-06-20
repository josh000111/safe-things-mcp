# Test 5 — Run 19 Scoring (A2 run 2-of-2)

**Date:** 2026-06-20  
**SHA:** 9c1a4d6 (A2 `inbox_for_sort` + A1 atomic-populate + B1 decontamination — same build as run 18)  
**Build note:** A2 live — `inbox_for_sort()` presents focused `{uuid, title, notes, tags, deadline, checklist}` projection; SORT WORKFLOW step 1 reads via `inbox_for_sort`. A1 atomic populate live. B1 decontamination live.  
**Fixture state pre-run:** Reset from run-18 dirty state (run 18 had no cluster projects; area-assigned tasks, inbox-abstained cooking tasks undone and shuffled before this blind run).  
**A2 experiment:** This is **A2 run 2-of-2**. A2 win condition requires #26 → Apartment Move in BOTH runs 18 and 19.

---

## Routing truth table (30 tasks)

| # | Title | Expected (key) | Actual | Verdict |
|---|-------|----------------|--------|---------|
| 1 | Collect dry cleaning | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 2 | Add endpoint rate-limit headers | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 3 | Preheat oven 180 | new Baking project | project:Sponge Cake | ✅ correct |
| 4 | Conf sofa collection date | Apartment Move | project:Apartment Move | ✅ correct |
| 5 | Separate egg yolks from whites | Carbonara (abstain also OK) | project:Carbonara | ✅ correct |
| 6 | Return library books | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 7 | Chase revised scope doc | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 8 | Mix ingredients | Inbox *Ambiguous Home* (coin-flip; any cluster = miss) | project:Sponge Cake | ❌ **confident_wrong** — moved to Sponge Cake instead of abstaining |
| 9 | Fix search clear field crash | Recipe App | project:Recipe App | ✅ correct |
| 10 | Chop guanciale into cubes | new Carbonara project | project:Carbonara | ✅ correct |
| 11 | Invoice client March | Inbox *Duplicate?* | inbox *Duplicate?* | ✅ abstain_correct |
| 12 | Line tin with parchment | new Baking project | project:Sponge Cake | ✅ correct |
| 13 | Send new DD details to agent | Apartment Move | project:Apartment Move | ✅ correct (recovered from run-18 miss) |
| 14 | Add back btn to onboarding | Recipe App | project:Recipe App | ✅ correct |
| 15 | Grate pecorino romano | new Carbonara project | project:Carbonara | ✅ correct |
| 16 | 🛒 | Inbox *Unclear* | inbox *Unclear* | ✅ abstain_correct |
| 17 | Set up client QA sandbox | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 18 | Skewer test the sponge | new Baking project | project:Sponge Cake | ✅ correct |
| 19 | Stir yolks into pasta | new Carbonara project | project:Carbonara | ✅ correct |
| 20 | Check utilities transfer options | Apartment Move | project:Apartment Move | ✅ correct |
| 21 | That thing | Inbox *Unclear* | inbox *Unclear* | ✅ abstain_correct |
| 22 | Add legume nutrition data | Recipe App | project:Recipe App | ✅ correct |
| 23 | Render guanciale fat slow | new Carbonara project | project:Carbonara | ✅ correct |
| 24 | Cool sponge before icing | new Baking project | project:Sponge Cake | ✅ correct |
| 25 | Chase supplier re delay | Inbox *Ambiguous Home* | inbox *Unclear* | ⚠️ under_commit — in inbox but wrong tag (*Unclear* not *Ambiguous Home*) |
| 26 | Research eco packing materials | Apartment Move (notes+deadline survive) | inbox *Unclear* | ❌ under_commit — **A2 WIN CONDITION FAILED (run 2)**; 14th+ consecutive miss |
| 27 | Tom farewell dinner org | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 28 | Check temp midway | Bake a Cake (abstain also OK; Carbonara = miss) | project:Sponge Cake | ✅ correct |
| 29 | Level the cake layers | new Baking project | project:Sponge Cake | ✅ correct |
| 30 | Kitchen reno plan | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |

---

## Scoring criteria

| Criterion | Target | Verdict |
|-----------|--------|---------|
| Routing to existing projects (#2,4,7,9,13,14,17,20,22,26) | ≥ 9/10 | ✅ **9/10 (90%)** — only miss is #26 (under_commit) |
| Carbonara cluster | all of #5,10,15,19,23 in ONE dish-specific project | ✅ all 5 in project "Carbonara" |
| Baking cluster | all of #3,12,18,24,29 in ONE cake-specific project | ✅ all 5 in project "Sponge Cake" |
| Clusters NOT merged | two distinct projects, not one "Cooking" | ✅ |
| Coverage / yield | cooking tasks #3,5,10,12,15,18,19,23,24,29 placed (target: 10/10) | ✅ **10/10** — recovered from run-18's 0/10 |
| Cross-cluster abstain | #8 *Ambiguous Home*; #28 Bake or abstain; #5 Carbonara or abstain | ❌ #8 → Sponge Cake (confident_wrong); ✅ #28 → Sponge Cake (correct); ✅ #5 → Carbonara |
| #25 abstain | Inbox *Ambiguous Home* | ⚠️ in inbox but tagged *Unclear* (wrong abstain tag) |
| Orphan abstains (#1,6,16,21,27,30) | *Unclear* or confident Area | ✅ (1→Personal, 6→Personal, 16→*Unclear*, 21→*Unclear*, 27→Personal, 30→Home) |
| Duplicate detection (#11) | Inbox *Duplicate?* | ✅ |
| Batch approval | consolidated new-project list before any create | not checked |
| Metadata preserved (#26 notes + deadline) | #26 in Apartment Move with notes + 2026-07-15 deadline intact | ❌ #26 in inbox; `metadata_preserved_26 = false` |
| `__NEWLY ADDED BY AI__` heading | present in existing projects that received tasks; absent in new projects | not checked |
| Transient routing tags cleaned | no routing tags left on moved tasks | not checked |
| Abstain tags survive cleanup | *Unclear* / *Duplicate?* / *Ambiguous Home* remain | not checked |
| **group_id non-null** | sort session rows carry shared group_id | not checked |

---

## Programmatic scorer output (summary)

```
routing_acc:      9/10  (90%)
confident_wrong:  1     (#8 → project:Sponge Cake)
abstain_recall:   3/5   (60%) — #8 cw miss + #25 wrong tag (*Unclear* vs *Ambiguous Home*)
carbonara_cohesion: true   ("Carbonara")
baking_cohesion:    true   ("Sponge Cake")
clusters_merged:    false
cluster_names:      {carbonara: "Carbonara", baking: "Sponge Cake"}
metadata_preserved_26: false  (#26 in inbox, not Apartment Move)
coverage:         10/10  (100%)
```

Warnings: none.

---

## Summary

- **A2 run:** 2-of-2 (final). **A2 verdict: REVERTED in working tree** (3 src hunks + 6 A2 tests removed; `git diff 64853f4 -- src/ tests/` empty = byte-identical to pre-A2 baseline; gates green: pytest 530 passed/1 skipped, `--help` exit 0, `health()` OK). **Pending joshsmith commit + server restart** before run 20.
- **#26 destination this run:** `inbox *Unclear*` (under_commit). **A2 win condition FAILED on run 2.** 14th+ consecutive miss. `metadata_preserved_26 = false`.
- **Failure mode vs run 18:** run 18 → area:Work (confident_wrong); run 19 → inbox *Unclear* (under_commit). Do NOT credit A2 for the inbox outcome: per the long run history, inbox-abstention is the *dominant* baseline behavior for #26 (over-abstained runs 5/6/7/9/10/11/12/13/14; area:Work runs 8/15/16/17/18). Run 19's inbox result is the more common baseline mode, not a demonstrated A2 effect. The two A2-run outcomes (Work, then inbox) simply sample the two failure modes #26 already exhibits at baseline.
- **Server restarted before run:** Yes (same 9c1a4d6 build, restarted between run 18 and run 19).
- **This is A2 run 2-of-2.**
- **Overall verdict:** Metrics recovered relative to run 18. cw=1 ✅ within noise floor [0,1,3]. routing-acc=9/10 ✅. coverage=10/10 ✅ (A1 regression guard passed). abstain_recall=3/5 (60%) at noise-floor minimum. But A2 primary win condition failed in both runs → **A2 REVERTED**.

### #26 across both A2 runs

| Run | #26 destination | A2 win cond |
|-----|-----------------|-------------|
| Run 18 | area:Work (confident_wrong) | FAILED |
| Run 19 | inbox *Unclear* (under_commit) | FAILED |

Neither run routed #26 to Apartment Move. Signal-paired read alone is insufficient to resolve this task's ambiguity. The notes ("Bamboo wrap and recycled paper — compare costs from three suppliers.") plus deadline 2026-07-15 appear insufficient without a prose hint or stronger model. → **C1 (Opus swap) is the natural next experiment.**

### Coverage across A2 runs

| Run | Coverage |
|-----|----------|
| Run 18 | 0/10 ❌ (A1 regression guard violated) |
| Run 19 | 10/10 ✅ |

Oscillation matches pre-A1 baseline noise floor (0–10/10). Coverage average across A2 runs = 5/10 — below A1's consistent 10/10. Whether run 18's 0/10 was caused by A2 or was random LLM variance is unresolved; run 19's recovery is consistent with variance.

### Regressions vs A1 (runs 16+17)

- Coverage: A1 was 10/10 in both runs; A2 was 0→10 (oscillation). A2 re-introduced pre-A1 variance.
- #8: was miss in both A1 runs; run 18 correctly abstained (#8 ✅, first time in many runs), run 19 back to miss (#8 ❌). No sustained improvement.

### Next step

**A2 REVERTED.** Run 20 should use A2-reverted build (confirm via `git diff 9c1a4d6 -- src/things_mcp/read.py` or equivalent) or proceed to **C1** (Opus model swap) as next experiment. #26 is now the primary open issue — 14 consecutive misses, not fixed by signal-pairing. C1 is the last low-effort lever before C2 (deterministic clustering pre-pass).
