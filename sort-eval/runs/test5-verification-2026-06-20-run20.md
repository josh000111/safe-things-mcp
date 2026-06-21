# Test 5 — Run 20 Scoring (C1 run 1-of-2, Opus 4.8 Extra)

**Date:** 2026-06-20  
**SHA:** 4c45237 (post-A2-revert; code byte-identical to A1+B1 baseline 64853f4)  
**Build note:** A2 reverted (d32849b). A1 atomic-populate + B1 decontamination live. Sorting code = 64853f4 equivalent.  
**Model:** Opus 4.8 "Extra" (one level above High, one below Max thinking effort)  
**Fixture state pre-run:** Reset from run-19 dirty state (run-19 had 2 cluster projects; all moved tasks undone and shuffled before this blind run).  
**C1 experiment:** This is **C1 run 1-of-2**. C1 pre-registered win condition: #26 "Research eco packing materials" → Apartment Move. C1 hypothesis: stronger model improves hard judgment calls (#8, #25, #26).

---

## Routing truth table (30 tasks)

| # | Title | Expected (key) | Actual | Verdict |
|---|-------|----------------|--------|---------|
| 1 | Collect dry cleaning | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 2 | Add endpoint rate-limit headers | Freelance: TechCorp API | inbox *Ambiguous Home* | ⚠️ under_commit — **novel miss**: #2 has a clear Freelance home; Opus over-abstained |
| 3 | Preheat oven 180 | new Baking project | project:Bake Sponge Cake | ✅ correct |
| 4 | Conf sofa collection date | Apartment Move | project:Apartment Move | ✅ correct |
| 5 | Separate egg yolks from whites | Carbonara (abstain also OK) | project:Make Carbonara | ✅ correct |
| 6 | Return library books | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 7 | Chase revised scope doc | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 8 | Mix ingredients | Inbox *Ambiguous Home* (coin-flip; any cluster = miss) | inbox *Unclear* | ⚠️ under_commit — in inbox but wrong tag (*Unclear* not *Ambiguous Home*) |
| 9 | Fix search clear field crash | Recipe App | project:Recipe App | ✅ correct |
| 10 | Chop guanciale into cubes | new Carbonara project | project:Make Carbonara | ✅ correct |
| 11 | Invoice client March | Inbox *Duplicate?* | inbox *Duplicate?* | ✅ abstain_correct |
| 12 | Line tin with parchment | new Baking project | project:Bake Sponge Cake | ✅ correct |
| 13 | Send new DD details to agent | Apartment Move | project:Apartment Move | ✅ correct |
| 14 | Add back btn to onboarding | Recipe App | project:Recipe App | ✅ correct |
| 15 | Grate pecorino romano | new Carbonara project | project:Make Carbonara | ✅ correct |
| 16 | 🛒 | Inbox *Unclear* | inbox *Unclear* | ✅ abstain_correct |
| 17 | Set up client QA sandbox | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 18 | Skewer test the sponge | new Baking project | project:Bake Sponge Cake | ✅ correct |
| 19 | Stir yolks into pasta | new Carbonara project | project:Make Carbonara | ✅ correct |
| 20 | Check utilities transfer options | Apartment Move | project:Apartment Move | ✅ correct |
| 21 | That thing | Inbox *Unclear* | inbox *Unclear* | ✅ abstain_correct |
| 22 | Add legume nutrition data | Recipe App | project:Recipe App | ✅ correct |
| 23 | Render guanciale fat slow | new Carbonara project | project:Make Carbonara | ✅ correct |
| 24 | Cool sponge before icing | new Baking project | project:Bake Sponge Cake | ✅ correct |
| 25 | Chase supplier re delay | Inbox *Ambiguous Home* | inbox *Unclear* | ⚠️ under_commit — in inbox but wrong tag (*Unclear* not *Ambiguous Home*) |
| 26 | Research eco packing materials | Apartment Move (notes+deadline survive) | inbox *Unclear* | ❌ under_commit — **C1 WIN CONDITION FAILED (run 1)**; 15th+ consecutive miss |
| 27 | Tom farewell dinner org | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 28 | Check temp midway | Bake a Cake (abstain also OK; Carbonara = miss) | inbox *Unclear* | ⚠️ under_commit — in inbox but missing abstain tag (acceptable placement) |
| 29 | Level the cake layers | new Baking project | project:Bake Sponge Cake | ✅ correct |
| 30 | Kitchen reno plan | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |

---

## Scoring criteria

| Criterion | Target | Verdict |
|-----------|--------|---------|
| Routing to existing projects (#2,4,7,9,13,14,17,20,22,26) | ≥ 9/10 | ❌ **8/10 (80%)** — misses: #2 (inbox *Ambiguous Home*, novel), #26 (inbox *Unclear*, persistent) |
| Carbonara cluster | all of #5,10,15,19,23 in ONE dish-specific project | ✅ all 5 in "Make Carbonara" |
| Baking cluster | all of #3,12,18,24,29 in ONE cake-specific project | ✅ all 5 in "Bake Sponge Cake" |
| Clusters NOT merged | two distinct projects, not one "Cooking" | ✅ |
| Coverage / yield | cooking tasks #3,5,10,12,15,18,19,23,24,29 placed (target: 10/10) | ✅ **10/10** |
| Cross-cluster abstain | #8 *Ambiguous Home*; #28 Bake or abstain; #5 Carbonara or abstain | ⚠️ #8 in inbox but *Unclear* tag (not *Ambiguous Home*); ✅ #28 in inbox (acceptable abstain); ✅ #5 → Make Carbonara |
| #25 abstain | Inbox *Ambiguous Home* | ⚠️ in inbox but tagged *Unclear* (wrong abstain tag; not a cw) |
| Orphan abstains (#1,6,16,21,27,30) | *Unclear* or confident Area | ✅ (#1→Personal, #6→Personal, #16→*Unclear*, #21→*Unclear*, #27→Personal, #30→Home) |
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
routing_acc:      8/10  (80%)  ⚠️ below 9/10 baseline — #2 novel miss, #26 persistent
confident_wrong:  0     ✅     perfect; no task placed in wrong location
abstain_recall:   3/5   (60%)  — #8 wrong tag (*Unclear* vs *Ambiguous Home*), #25 wrong tag
carbonara_cohesion: true        ("Make Carbonara")
baking_cohesion:    true        ("Bake Sponge Cake")
clusters_merged:    false
cluster_names:      {carbonara: "Make Carbonara", baking: "Bake Sponge Cake"}
metadata_preserved_26: false    (#26 in inbox, not Apartment Move)
coverage:         10/10  ✅     all 10 cooking tasks placed
```

Warnings: none.

---

## Vs. noise floor

| Metric | Run 20 | Noise floor (runs 6/7/8) | Status |
|--------|--------|--------------------------|--------|
| confident_wrong | **0** | [0, 1, 3] | ✅ AT FLOOR MIN (tied with runs 5/6/9/10/13) |
| abstain_recall | **3/5 (60%)** | [60%, 80%, 80%] | ✅ AT FLOOR MIN |
| coverage | **10/10** | [0/10, 10/10, 10/10] | ✅ AT FLOOR MAX |
| routing_acc | **8/10 (80%)** | 9/10 in all baseline runs | ⚠️ BELOW BASELINE (also seen run 18) |

---

## Summary

- **#26 destination this run:** `inbox *Unclear*` (under_commit). **C1 win condition FAILED (run 1).** 15th+ consecutive miss across all models and builds.
- **#8 destination this run:** `inbox *Unclear*` — in inbox ✅, wrong tag ⚠️. Not a confident_wrong.
- **#25 destination this run:** `inbox *Unclear*` — in inbox ✅, wrong tag ⚠️. Not a confident_wrong.
- **Server restarted before run:** Yes (post-A2-revert commit 4c45237 / d32849b; confirmed running A1+B1 code).
- **This is C1 run 1-of-2.** DO NOT mark C1 KEEP/REVERT until run 2.
- **Ambiguity policy:** abstain on true 50/50 (decided 2026-06-14).
- **Overall verdict:** cw=0 (perfect), coverage=10/10, but routing_acc=8/10 (below 9/10 baseline) due to novel #2 miss + persistent #26. abstain_recall=3/5 (60%) at floor minimum. No metric moved beyond noise floor on this run. C1 win condition failed run 1.

### #26 history across C1 runs so far

| Run | Model | #26 destination | C1 win cond |
|-----|-------|-----------------|-------------|
| Run 20 | Opus 4.8 Extra | inbox *Unclear* (under_commit) | FAILED |

### Notable Opus-specific observations (run 1 only — may be sampling noise)

1. **#2 novel over-abstain**: "Add endpoint rate-limit headers" tagged *Ambiguous Home* and left in inbox. This task has an unambiguous Freelance: TechCorp API home (API, TechCorp context clear). No prior Sonnet run missed #2. Suggests Opus may be more conservative about routing (broader abstain radius).
2. **Consistent cluster creation**: Both clusters populated 10/10, same as A1 runs 16+17. A1's atomic-populate benefit holds under Opus.
3. **Abstain tag precision gap**: #8 and #25 correctly identified as inbox-worthy but tagged *Unclear* instead of the correct specific tag (*Ambiguous Home*). Sonnet had the same issue in runs 18/19. Not an Opus-specific regression.
4. **cw=0**: Zero confident-wrong placements — same as the best Sonnet runs. Stronger model did not reduce cw further (it was already at 0 in multiple Sonnet runs).

### What run 2 should clarify

- Whether routing_acc=8/10 (the #2 miss) is Opus sampling noise or a systematic over-abstain tendency.
- Whether #26 remains inbox or finally reaches Apartment Move.
- Whether abstain tag precision (#8/*Ambiguous Home* vs #8/*Unclear*) is consistent.

### Regressions vs A1 (runs 16+17)

- routing_acc: A1 was 9/10 in both runs; run 20 is 8/10 (novel #2 miss). One data point — may be noise.
- No regressions in coverage, cw, or clustering.
