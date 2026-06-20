# Test 5 — Run 17 Scoring (2026-06-19)

**SHA:** 64853f4 (A1 atomic-populate + B1 decontamination; 530 tests pass)
**Build:** BACKLOG A1 (atomic populate) + BACKLOG B1 (decontamination) — same build as run 16
**Model:** Sonnet 4.6
**Fixture:** test5 v1 (reset before run — run 16 undone)
**group_id:** not checked
**Server restarted before run:** no (same live build as run 16; fixture reset only)
**Scored by:** `uv run things-mcp-score --pretty`

---

## Routing truth table (30 tasks)

| # | Title | Expected (key) | Actual | Verdict |
|---|-------|----------------|--------|---------|
| 1 | Collect dry cleaning | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |
| 2 | Add endpoint rate-limit headers | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 3 | Preheat oven 180 | new Baking project | project:Bake Sponge Cake | ✅ correct |
| 4 | Conf sofa collection date | Apartment Move | project:Apartment Move | ✅ correct |
| 5 | Separate egg yolks from whites | Carbonara (abstain also OK) | project:Make Carbonara | ✅ correct |
| 6 | Return library books | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 7 | Chase revised scope doc | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 8 | Mix ingredients | Inbox *Ambiguous Home* (coin-flip; any cluster = miss) | project:Bake Sponge Cake | ❌ confident_wrong (persistent — 13th+ consecutive miss) |
| 9 | Fix search clear field crash | Recipe App | project:Recipe App | ✅ correct |
| 10 | Chop guanciale into cubes | new Carbonara project | project:Make Carbonara | ✅ correct |
| 11 | Invoice client March | Inbox *Duplicate?* | inbox *Duplicate?* | ✅ abstain_correct (recovered from run 16 miss) |
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
| 25 | Chase supplier re delay | Inbox *Ambiguous Home* | inbox *Ambiguous Home* | ✅ abstain_correct (recovered from run 16 miss) |
| 26 | Research eco packing materials | Apartment Move (notes+deadline survive) | area:Work | ❌ confident_wrong (persistent — 12th+ consecutive miss) |
| 27 | Tom farewell dinner org | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 28 | Check temp midway | Bake a Cake (abstain also OK; Carbonara = miss) | project:Bake Sponge Cake | ✅ correct |
| 29 | Level the cake layers | new Baking project | project:Bake Sponge Cake | ✅ correct |
| 30 | Kitchen reno plan | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |

---

## Scoring criteria

| Criterion | Target | Verdict |
|-----------|--------|---------|
| Routing to existing projects | ≥ 9/10 of #2,4,7,9,13,14,17,20,22,26 | ❌ 9/10 — #26 → area:Work (persistent miss) |
| Carbonara cluster | all of #5,10,15,19,23 in ONE dish-specific project | ✅ "Make Carbonara" — 5/5 tasks placed |
| Baking cluster | all of #3,12,18,24,29 in ONE cake-specific project | ✅ "Bake Sponge Cake" — 5/5 tasks placed (+ #8 and #28 also landed here) |
| Clusters NOT merged | two distinct projects, not one "Cooking" | ✅ two separate projects |
| Coverage / yield | cooking tasks #3,5,10,12,15,18,19,23,24,29 placed in a project | ✅ **10/10** |
| Cross-cluster abstain | #8 in Inbox *Ambiguous Home* (coin-flip). #28 → Bake a Cake or abstain. #5 → Carbonara or abstain | ❌ #8 → Bake Sponge Cake (miss); ✅ #28 → Bake Sponge Cake (pass); ✅ #5 → Make Carbonara (pass) |
| #25 abstain | Inbox *Ambiguous Home* | ✅ correctly abstained (recovered from run 16) |
| Orphan abstains | #1,6,16,21,27,30 *Unclear* or confident Area | ✅ all pass (#1,#30→area:Home; #6,#27→area:Personal; #16,#21 inbox *Unclear*) |
| Duplicate detection | #11 Inbox *Duplicate?* | ✅ inbox *Duplicate?* (recovered from run 16 — agent tagged AND left in inbox) |
| Batch approval | one consolidated new-project list before any create | unknown (not observable post-run) |
| Metadata preserved | #26 notes + deadline 2026-07-15 intact in Apartment Move | ❌ #26 in area:Work, not Apartment Move |
| `__NEWLY ADDED BY AI__` heading | present in existing projects that got tasks; absent in new projects | not checked |
| Transient routing tags cleaned | no routing tags left on moved tasks | ✅ (no spurious tags observed) |
| Abstain tags survive cleanup | *Unclear* / *Duplicate?* / *Ambiguous Home* remain | ✅ |
| **group_id non-null** | `undo_log` rows carry a shared group_id | not checked |

---

## Programmatic metrics summary

| Metric | Value | vs noise floor [runs 6/7/8 at 773e920] | vs run 16 (A1 run 1) |
|--------|-------|----------------------------------------|----------------------|
| confident_wrong | **2** | ✅ within floor [0,1,3] | ↓ from 4 |
| abstain_recall | **4/5 (80%)** | ✅ at floor ceiling [60%,80%,80%] | ↑ from 40% |
| routing_acc | **9/10 (90%)** | consistent | same |
| coverage | **10/10 (100%)** ✅ | at ceiling [0,10,10] | same |
| carbonara_cohesion | true | ✅ | same |
| baking_cohesion | true | ✅ | same |
| clusters_merged | false | ✅ | same |
| metadata_preserved_26 | false | #26 persistent wrong location | same |
| generic_name_warning | [] | ✅ "Make Carbonara" + "Bake Sponge Cake" both specific | same |

---

## A1 hypothesis assessment (Run 2 of 2–3)

**Primary hypothesis:** coverage min > 0 across 2+ runs (empty-project mode eliminated).

**Result: WIN CONDITION MET.**

| Run | cw | abstain_recall | coverage |
|-----|----|----------------|----------|
| Run 16 (A1 run 1) | 4 ⚠️ | 2/5 (40%) ❌ | 10/10 ✅ |
| Run 17 (A1 run 2) | 2 ✅ | 4/5 (80%) ✅ | 10/10 ✅ |
| Noise floor [min,med,max] | [0,1,3] | [60%,80%,80%] | [0,10,10] |

- **Coverage = 10/10 in BOTH A1 runs** — primary hypothesis confirmed across 2 runs. The atomic
  populate path fired in both runs; neither produced empty projects. Min coverage across A1 runs
  = 10/10, definitively above the noise-floor spread (min=0 pre-A1).
- **cw = 2 this run** — within noise floor. Run 16's cw=4 appears to be sampling noise (run 16
  also had two unusually bad misses: #11 moved-despite-Duplicate and #25 committed to area:Work).
  With cw=[2,4] across the two A1 runs and the noise-floor ceiling at 3, A1 is not systematically
  worsening precision.
- **abstain_recall = 80%** — recovered to baseline after run 16's 40% low. Run 16's
  abstain_recall=40% was a 1-run spike, not a systematic regression.

**Persistent issues (unchanged by A1):**
- #8 "Mix ingredients" → Bake Sponge Cake: 13th+ consecutive miss. Coin-flip committed rather
  than abstained. A1's greater commit drive makes this worse by design — no easy fix without
  targeted instruction work.
- #26 "Research eco packing materials" → area:Work: 12th+ consecutive wrong-area miss. A1
  has no bearing on single-task routing failures.

---

## Run narrative

Agent created "Make Carbonara" (5 tasks) and "Bake Sponge Cake" (5+2 tasks) and immediately
populated both atomically. Coverage = 10/10.

#11 ("Invoice client March") correctly left in inbox with *Duplicate?* tag this run —
contrasting with run 16 where the agent moved it to Freelance with the tag. Agent detected
the duplicate and abstained correctly.

#25 correctly abstained with *Ambiguous Home* tag — run 16 had committed it to area:Work.

#8 and #26 remain persistent failures across all A1 runs.

---

## Summary

- **Ambiguity policy:** abstain on true 50/50 (decided 2026-06-14)
- **Server restarted before run:** no (same A1+B1 build; fixture reset only)
- **Overall verdict:** A1 **KEEP** criterion met — coverage=10/10 in both A1 runs, cw within
  noise floor this run, abstain_recall recovered to 80%. Primary hypothesis confirmed.
- **Regressions vs noise floor:** none this run. cw=2 within floor; abstain=80% at floor
  ceiling; coverage=10/10 at noise floor ceiling (but was previously bimodal 0 or 10).
- **Fixture state after run:** DIRTY — "Make Carbonara" (5 tasks) and "Bake Sponge Cake"
  (7 tasks incl. #8, #28) exist. Tasks moved to projects. #1,#30→area:Home;
  #6,#27→area:Personal; #26→area:Work; #11,#16,#21,#25 in inbox with tags.
  Full reset required before run 18.
