# Test 5 — Run 18 Scoring (A2 run 1-of-2)

**Date:** 2026-06-20  
**SHA:** 9c1a4d6 (A2 `inbox_for_sort` + A1 atomic-populate + B1 decontamination)  
**Build note:** A2 is live — `inbox_for_sort()` added to `things_repo.py` + `read.py`; SORT WORKFLOW step 1 now reads via `inbox_for_sort` instead of `list_inbox`. A1 atomic populate also live. B1 cooking-example decontamination live.  
**Fixture state pre-run:** Reset from run-17 dirty state (run 17 had full coverage + many moves; fixture was undone and shuffled before this blind run).  
**A2 experiment:** This is **A2 run 1-of-2**. The A2 win condition requires #26 "Research eco packing materials" to route to project:Apartment Move in BOTH A2 runs (runs 18 and 19). After run 18 alone, A2 status remains READY-TO-TEST (1/2 done).

---

## Routing truth table (30 tasks)

| # | Title | Expected (key) | Actual | Verdict |
|---|-------|----------------|--------|---------|
| 1 | Collect dry cleaning | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |
| 2 | Add endpoint rate-limit headers | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 3 | Preheat oven 180 | new Baking project | inbox *Ambiguous Home* | ⚠️ under_commit |
| 4 | Conf sofa collection date | Apartment Move | project:Apartment Move | ✅ correct |
| 5 | Separate egg yolks from whites | Carbonara (abstain also OK) | inbox *Ambiguous Home* | ✅ abstain_correct |
| 6 | Return library books | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 7 | Chase revised scope doc | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 8 | Mix ingredients | Inbox *Ambiguous Home* (coin-flip; any cluster = miss) | inbox *Ambiguous Home* | ✅ abstain_correct |
| 9 | Fix search clear field crash | Recipe App | project:Recipe App | ✅ correct |
| 10 | Chop guanciale into cubes | new Carbonara project | inbox *Ambiguous Home* | ⚠️ under_commit |
| 11 | Invoice client March | Inbox *Duplicate?* | inbox *Duplicate?* | ✅ abstain_correct |
| 12 | Line tin with parchment | new Baking project | inbox *Ambiguous Home* | ⚠️ under_commit |
| 13 | Send new DD details to agent | Apartment Move | inbox *Ambiguous Home* | ❌ routing miss (under_commit; novel — was correct in runs 16+17) |
| 14 | Add back btn to onboarding | Recipe App | project:Recipe App | ✅ correct |
| 15 | Grate pecorino romano | new Carbonara project | inbox *Ambiguous Home* | ⚠️ under_commit |
| 16 | 🛒 | Inbox *Unclear* | inbox *Unclear* | ✅ abstain_correct |
| 17 | Set up client QA sandbox | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 18 | Skewer test the sponge | new Baking project | inbox *Ambiguous Home* | ⚠️ under_commit |
| 19 | Stir yolks into pasta | new Carbonara project | inbox *Ambiguous Home* | ⚠️ under_commit |
| 20 | Check utilities transfer options | Apartment Move | project:Apartment Move | ✅ correct |
| 21 | That thing | Inbox *Unclear* | inbox *Unclear* | ✅ abstain_correct |
| 22 | Add legume nutrition data | Recipe App | project:Recipe App | ✅ correct |
| 23 | Render guanciale fat slow | new Carbonara project | inbox *Ambiguous Home* | ⚠️ under_commit |
| 24 | Cool sponge before icing | new Baking project | inbox *Ambiguous Home* | ⚠️ under_commit |
| 25 | Chase supplier re delay | Inbox *Ambiguous Home* | area:Work | ❌ confident_wrong |
| 26 | Research eco packing materials | Apartment Move (notes+deadline survive) | area:Work | ❌ confident_wrong — **A2 WIN CONDITION FAILED (run 1)** |
| 27 | Tom farewell dinner org | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 28 | Check temp midway | Bake a Cake (abstain also OK; Carbonara = miss) | inbox *Ambiguous Home* | ✅ abstain_correct |
| 29 | Level the cake layers | new Baking project | inbox *Ambiguous Home* | ⚠️ under_commit |
| 30 | Kitchen reno plan | Inbox *Unclear* (or existing Area = pass) | project:Apartment Move | ⚠️ needs_review (plausible but wrong per key; same as runs 10–13) |

---

## Scoring criteria

| Criterion | Target | Verdict |
|-----------|--------|---------|
| Routing to existing projects (#2,4,7,9,13,14,17,20,22,26) | ≥ 9/10 | ❌ **8/10 (80%)** — #13 miss (inbox *Ambiguous Home*) + #26 wrong area; below prior noise-floor consistent result of 9/10 |
| Carbonara cluster | all of #5,10,15,19,23 in ONE dish-specific project | ❌ no project created; all in inbox |
| Baking cluster | all of #3,12,18,24,29 in ONE cake-specific project | ❌ no project created; all in inbox |
| Clusters NOT merged | two distinct projects, not one "Cooking" | ✅ (no projects = not merged) |
| Coverage / yield | cooking tasks #3,5,10,12,15,18,19,23,24,29 placed (target: 10/10) | ❌ **0/10** ⚠️ A1 REGRESSION GUARD VIOLATION — both A1 runs had 10/10 |
| Cross-cluster abstain | #8 *Ambiguous Home*; #28 Bake or abstain; #5 Carbonara or abstain | ✅ all three abstained correctly |
| #25 abstain | Inbox *Ambiguous Home* | ❌ area:Work (confident_wrong) |
| Orphan abstains (#1,6,16,21,27,30) | *Unclear* or confident Area | ✅ (1→Home, 6→Personal, 16→*Unclear*, 21→*Unclear*, 27→Personal, 30→Apartment Move ⚠️ needs_review) |
| Duplicate detection (#11) | Inbox *Duplicate?* | ✅ |
| Batch approval | consolidated new-project list before any create | N/A (no new projects created) |
| Metadata preserved (#26 notes + deadline) | #26 in Apartment Move with notes + 2026-07-15 deadline intact | ❌ #26 in area:Work; not checked |
| `__NEWLY ADDED BY AI__` heading | present in existing projects that received tasks; absent in new projects | ✅ confirmed in all 3 projects: Freelance (created run 18), Apartment Move (pre-existing from run 17, not cleaned during fixture reset), Recipe App (same) |
| Transient routing tags cleaned | no routing tags left on moved tasks | ❌ tasks in Freelance / Apartment Move / Recipe App retain routing tags (*TechCorp API*, *Apartment Move*, *Recipe App*) |
| Abstain tags survive cleanup | *Unclear* / *Duplicate?* / *Ambiguous Home* remain | ✅ |
| **group_id non-null** | sort session rows carry shared group_id | ⚠️ **partial** — move_under_ai_heading + apply_ai_tags carry group_id `9916dbe1`; 5 area-assignment move_todo entries are null (individual area moves bypass propose_bulk_move auto-init) |

---

## Programmatic scorer output (summary)

```
routing_acc:      8/10  (80%)
confident_wrong:  2     (#25→area:Work, #26→area:Work)
abstain_recall:   4/5   (80%)
carbonara_cohesion: false
baking_cohesion:    false
clusters_merged:    false
cluster_names:      {carbonara: null, baking: null}
metadata_preserved_26: false
coverage:         0/10  (0%)
```

Warnings: task #30 ('Kitchen reno plan') placed in project 'Apartment Move' — needs human review.

---

## Summary

- **A2 run:** 1-of-2 (this run). A2 status remains **READY-TO-TEST** — need run 19 before KEPT/REVERTED.
- **#26 destination this run:** `area:Work` (tagged *Work*). **A2 win condition FAILED on run 1.** 13th+ consecutive miss. `metadata_preserved_26 = false`.
- **Server restarted before run:** Yes (A2+A1+B1 build, SHA 9c1a4d6).
- **Overall verdict:** Mixed. cw=2 ✅ within noise floor. abstain_recall=80% ✅. But coverage=0/10 is a **regression guard violation** vs A1 (runs 16+17 both had 10/10). Agent mass-tagged all 10 cooking tasks *Ambiguous Home* and left them in inbox — creation-hesitation variant not seen since pre-A1 baseline runs. routing-acc=8/10 is a new low for recent runs (prior 15 runs were all 9/10); novel miss: #13 tagged *Ambiguous Home* instead of Apartment Move.

### Notable positives
- **#8 correctly abstained ✅** — "Mix ingredients" got *Ambiguous Home* as expected. First clean hit for #8 in many runs (runs 16+17 still got this wrong).
- **#28 correctly abstained ✅** — consistent.
- **#11, #16, #21 correctly abstained ✅** — consistent.

### Concerns
- **Coverage regression:** 0/10 in run 18 vs 10/10 in both A1 runs (16+17). The regression guard says coverage must stay 10/10. This run breaks that guard. Cause unknown — could be A2's signal-paired read changing attention away from clustering, or could be run-to-run LLM variance (the pre-A1 baseline also showed 0/10 in some runs). Run 19 will clarify.
- **routing-acc 8/10:** #13 "Send new DD details to agent" was correctly routed in runs 16+17 but got *Ambiguous Home* this run. This correlates with the agent over-abstracting on all apartment-related tasks.
- **group_id partial:** Area-assignment moves still bypass the group_id tracking. Low-priority (A1 auto-init covers bulk_moves correctly).

### Regressions vs A1
- Coverage: 10/10 → 0/10 ❌
- routing-acc: 9/10 → 8/10 ❌
- #8: recovered ✅ (was wrong in both A1 runs)

### Open question for run 19
Does A2 (`inbox_for_sort`) help or hurt? The signal-paired read may have helped with #8 (finally abstained correctly) but may be suppressing cluster creation by not showing the full inbox-list context that previously triggered clustering. Or this is pure LLM variance. Run 19 will determine which.
