# Test 5 — Run 21 Scoring (C1 run 2-of-2, Opus 4.8 Extra)

**Date:** 2026-06-20  
**SHA:** 4c45237 (post-A2-revert; code byte-identical to A1+B1 baseline 64853f4)  
**Build note:** A2 reverted (d32849b). A1 atomic-populate + B1 decontamination live. Sorting code = 64853f4 equivalent.  
**Model:** Opus 4.8 "Extra" (one level above High, one below Max thinking effort)  
**Fixture state pre-run:** Reset from run-20 dirty state (run-20 had 2 cluster projects; all moved tasks undone and shuffled before this blind run).  
**C1 experiment:** This is **C1 run 2-of-2**. C1 pre-registered win condition: #26 "Research eco packing materials" → Apartment Move with notes + deadline intact. C1 hypothesis: stronger model improves hard judgment calls (#8, #25, #26).

---

## Routing truth table (30 tasks)

| # | Title | Expected (key) | Actual | Verdict |
|---|-------|----------------|--------|---------|
| 1 | Collect dry cleaning | Inbox *Unclear* (or existing Area = pass) | inbox *Ambiguous Home* | ✅ abstain_correct (in inbox; bonus-tag-only note) |
| 2 | Add endpoint rate-limit headers | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct (recovered from run-20 novel miss) |
| 3 | Preheat oven 180 | new Baking project | project:Bake Sponge Cake | ✅ correct |
| 4 | Conf sofa collection date | Apartment Move | project:Apartment Move | ✅ correct |
| 5 | Separate egg yolks from whites | Carbonara (abstain also OK) | project:Make Carbonara | ✅ correct |
| 6 | Return library books | Inbox *Unclear* (or existing Area = pass) | inbox *Ambiguous Home* | ✅ abstain_correct (in inbox; bonus-tag-only note) |
| 7 | Chase revised scope doc | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 8 | Mix ingredients | Inbox *Ambiguous Home* (coin-flip; any cluster = miss) | inbox *Ambiguous Home* | ✅ abstain_correct — **correct tag, 14th+ run, first correct tag in many runs** |
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
| 25 | Chase supplier re delay | Inbox *Ambiguous Home* | inbox *Ambiguous Home* | ✅ abstain_correct — **correct tag** (run-20 had *Unclear*) |
| 26 | Research eco packing materials | Apartment Move (notes+deadline survive) | project:Apartment Move | ✅ **C1 WIN CONDITION MET** — notes + deadline 2026-07-15 intact (`metadata_preserved_26=true`) |
| 27 | Tom farewell dinner org | Inbox *Unclear* (or existing Area = pass) | inbox *Ambiguous Home* | ✅ abstain_correct (in inbox; bonus-tag-only note) |
| 28 | Check temp midway | Bake a Cake (abstain also OK; Carbonara = miss) | inbox *Ambiguous Home* | ✅ abstain_correct (with correct tag) |
| 29 | Level the cake layers | new Baking project | project:Bake Sponge Cake | ✅ correct |
| 30 | Kitchen reno plan | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |

---

## Scoring criteria

| Criterion | Target | Verdict |
|-----------|--------|---------|
| Routing to existing projects (#2,4,7,9,13,14,17,20,22,26) | ≥ 9/10 | ✅ **10/10 (100%)** — perfect |
| Carbonara cluster | all of #5,10,15,19,23 in ONE dish-specific project | ✅ all 5 in "Make Carbonara" |
| Baking cluster | all of #3,12,18,24,29 in ONE cake-specific project | ✅ all 5 in "Bake Sponge Cake" |
| Clusters NOT merged | two distinct projects, not one "Cooking" | ✅ |
| Coverage / yield | cooking tasks #3,5,10,12,15,18,19,23,24,29 placed (target: 10/10) | ✅ **10/10** |
| Cross-cluster abstain | #8 *Ambiguous Home*; #28 Bake or abstain; #5 Carbonara or abstain | ✅ #8 → inbox *Ambiguous Home* (correct tag); ✅ #28 → inbox *Ambiguous Home*; ✅ #5 → Make Carbonara |
| #25 abstain | Inbox *Ambiguous Home* | ✅ inbox *Ambiguous Home* (correct tag) |
| Orphan abstains (#1,6,16,21,27,30) | *Unclear* or confident Area | ✅ (#1→inbox, #6→inbox, #16→*Unclear*, #21→*Unclear*, #27→inbox, #30→area:Home) |
| Duplicate detection (#11) | Inbox *Duplicate?* | ✅ |
| Batch approval | consolidated new-project list before any create | not checked |
| Metadata preserved (#26 notes + deadline) | #26 in Apartment Move with notes + 2026-07-15 deadline intact | ✅ **metadata_preserved_26=true** |
| `__NEWLY ADDED BY AI__` heading | present in existing projects that received tasks; absent in new projects | not checked |
| Transient routing tags cleaned | no routing tags left on moved tasks | not checked |
| Abstain tags survive cleanup | *Unclear* / *Duplicate?* / *Ambiguous Home* remain | not checked |
| **group_id non-null** | sort session rows carry shared group_id | not checked |

---

## Programmatic scorer output (summary)

```
routing_acc:         10/10  (100%) ✅  perfect — all unambiguous tasks routed correctly
confident_wrong:     0              ✅  zero confident misplacements
abstain_recall:      5/5    (100%) ✅  ABOVE NOISE FLOOR MAX (floor max was 80%)
carbonara_cohesion:  true           ("Make Carbonara")
baking_cohesion:     true           ("Bake Sponge Cake")
clusters_merged:     false
cluster_names:       {carbonara: "Make Carbonara", baking: "Bake Sponge Cake"}
metadata_preserved_26: true        ✅  #26 in Apartment Move, notes + deadline intact
coverage:            10/10  (100%) ✅  all 10 cooking tasks placed
warnings:            []
```

---

## Vs. noise floor

| Metric | Run 21 | Noise floor (runs 6/7/8) | Status |
|--------|--------|--------------------------|--------|
| confident_wrong | **0** | [0, 1, 3] | ✅ AT FLOOR MIN |
| abstain_recall | **5/5 (100%)** | [60%, 80%, 80%] | ✅ **ABOVE FLOOR MAX** |
| coverage | **10/10** | [0/10, 10/10, 10/10] | ✅ AT FLOOR MAX |
| routing_acc | **10/10 (100%)** | 9/10 in all baseline runs | ✅ ABOVE BASELINE |

---

## C1 verdict (both runs now complete)

| Metric | C1 run 1 (run 20) | C1 run 2 (run 21) | vs. noise floor |
|--------|-------------------|-------------------|-----------------|
| confident_wrong | 0 ✅ | 0 ✅ | Both at floor min — **consistent 0 across C1; no cw≥1 in either run** |
| abstain_recall | 3/5 (60%) | 5/5 (100%) | Run 1 at floor min; run 2 above floor max — **high variance** |
| coverage | 10/10 ✅ | 10/10 ✅ | Both at floor max — consistent (same as A1 under Sonnet) |
| routing_acc | 8/10 ⚠️ | 10/10 ✅ | Run 1 below baseline (novel #2 miss); run 2 perfect |
| **#26 win cond** | FAILED (inbox *Unclear*) | **MET** (Apartment Move + metadata) | Non-deterministic — 1-of-2 |

**Assessment:** C1 delivers **consistent cw=0 and coverage=10/10** across both runs — matching the best Sonnet results but not exceeding them. The #26 win condition was met in 1-of-2 runs (non-deterministic). abstain_recall showed extreme variance (60% vs 100%). routing_acc oscillated (80% vs 100%). No metric moved *consistently* outside the noise floor spread in both runs.

The run 2 result (10/10/10/10, perfect abstain tags) is the best single run in the entire evaluation. But the run 1 result (routing_acc 8/10, #2 novel miss, abstain tags wrong) shows Opus still has non-determinism — the same judgment variance that plagues Sonnet, just possibly shifted toward fewer confident-wrong outcomes.

**C1 judgment: INCONCLUSIVE / see MISSION-CONTROL for KEEP/REVERT decision.** The pre-registered win condition is satisfied (run 2 met it), but failed run 1 means #26 is still non-deterministic under Opus. Cost difference between Opus and Sonnet is material. Recommend KEEP only if #26 routing in run 2 is deemed sufficient evidence; otherwise REVERT and try C2.

---

## Summary

- **#26 destination this run:** `project:Apartment Move` with metadata intact ✅ — **C1 WIN CONDITION MET (run 2)**. First correct #26 placement in 16+ runs across all models.
- **#8 destination this run:** `inbox *Ambiguous Home*` ✅ — **correct tag**, first time in many runs.
- **#25 destination this run:** `inbox *Ambiguous Home*` ✅ — correct tag (run-20 had *Unclear*).
- **#2 destination this run:** `project:Freelance: TechCorp API` ✅ — recovered from run-20 novel over-abstain.
- **Server restarted before run:** Yes (same 4c45237 build; fixture reset from run-20 dirty state).
- **Ambiguity policy:** abstain on true 50/50 (decided 2026-06-14).
- **Overall verdict:** Near-perfect run. All metrics at or above noise floor. cw=0, routing_acc=10/10, abstain_recall=5/5 (all with correct tags), coverage=10/10, #26 metadata preserved. Best single run in the entire evaluation history.

### #26 history across C1 runs

| Run | Model | #26 destination | C1 win cond |
|-----|-------|-----------------|-------------|
| Run 20 (C1 run 1) | Opus 4.8 Extra | inbox *Unclear* (under_commit) | FAILED |
| Run 21 (C1 run 2) | Opus 4.8 Extra | project:Apartment Move + metadata ✅ | **MET** |

### Notable observations (run 2)

1. **#26 finally routed correctly**: After 15+ consecutive misses across all models (Sonnet and Opus), #26 landed in Apartment Move with notes and deadline intact. This is the first time the pre-registered C1 win condition has been met. Cause uncertain — may reflect Opus's deeper reasoning on note content ("Bamboo wrap and recycled paper — compare costs from three suppliers" + deadline 2026-07-15 = planning/logistics), or run-to-run variance.
2. **Abstain tags precise**: #8, #25, #28 all got *Ambiguous Home* (not *Unclear*). Contrast with run-20 where #8 and #25 had wrong tag. This is consistent with Opus paying more attention to abstain-category semantics — or it's run variance.
3. **#2 recovered**: Run-20's novel miss (#2 left in inbox *Ambiguous Home*) did not repeat. Confirms the run-20 #2 miss was LLM variance, not a systematic Opus over-abstain.
4. **cw=0 consistent across C1**: Both Opus runs had zero confident-wrong placements. This matches the best Sonnet runs but does not move beyond the noise floor ceiling.

### Regressions vs A1 (runs 16+17)

None in run 21. All metrics at or above A1 levels.

### Comparison to run-20 (C1 run 1)

| Metric | Run 20 (C1 r1) | Run 21 (C1 r2) | Δ |
|--------|----------------|----------------|---|
| cw | 0 | 0 | = |
| routing_acc | 8/10 | 10/10 | +2 |
| abstain_recall | 3/5 (60%) | 5/5 (100%) | +40pp |
| coverage | 10/10 | 10/10 | = |
| #26 | inbox *Unclear* | Apt Move ✅ | **WIN** |
| metadata_26 | false | true ✅ | **WIN** |
