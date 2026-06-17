# Test 5 — Scoring: 2026-06-17 Run 13

**Run:** 13 (second run on BACKLOG #4 build, two-pass router→skeptic)
**SHA:** 2bd582c
**Model:** Sonnet 4.6
**Fixture:** test5 v1 (reset before run)
**Server restarted before run:** yes

---

## Routing truth table (30 tasks)

| # | Title | Expected (key) | Actual | Verdict |
|---|-------|----------------|--------|---------|
| 1 | Collect dry cleaning | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 2 | Add endpoint rate-limit headers | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 3 | Preheat oven 180 | new Baking project | inbox (no tag) | ⚠️ under_commit |
| 4 | Conf sofa collection date | Apartment Move | project:Apartment Move | ✅ correct |
| 5 | Separate egg yolks from whites | Carbonara (abstain also OK) | inbox (no tag) | ⚠️ under_commit |
| 6 | Return library books | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 7 | Chase revised scope doc | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 8 | Mix ingredients | Inbox *Ambiguous Home* (coin-flip; any cluster = miss) | inbox (no tag) | ⚠️ under_commit — missing *Ambiguous Home* tag |
| 9 | Fix search clear field crash | Recipe App | project:Recipe App | ✅ correct |
| 10 | Chop guanciale into cubes | new Carbonara project | inbox (no tag) | ⚠️ under_commit |
| 11 | Invoice client March | Inbox *Duplicate?* | inbox *Duplicate?* | ✅ abstain_correct |
| 12 | Line tin with parchment | new Baking project | inbox (no tag) | ⚠️ under_commit |
| 13 | Send new DD details to agent | Apartment Move | project:Apartment Move | ✅ correct |
| 14 | Add back btn to onboarding | Recipe App | project:Recipe App | ✅ correct |
| 15 | Grate pecorino romano | new Carbonara project | inbox (no tag) | ⚠️ under_commit |
| 16 | 🛒 | Inbox *Unclear* | inbox *Unclear* | ✅ abstain_correct |
| 17 | Set up client QA sandbox | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 18 | Skewer test the sponge | new Baking project | inbox (no tag) | ⚠️ under_commit |
| 19 | Stir yolks into pasta | new Carbonara project | inbox (no tag) | ⚠️ under_commit |
| 20 | Check utilities transfer options | Apartment Move | project:Apartment Move | ✅ correct |
| 21 | That thing | Inbox *Unclear* | inbox *Unclear* | ✅ abstain_correct |
| 22 | Add legume nutrition data | Recipe App | project:Recipe App | ✅ correct |
| 23 | Render guanciale fat slow | new Carbonara project | inbox (no tag) | ⚠️ under_commit |
| 24 | Cool sponge before icing | new Baking project | inbox (no tag) | ⚠️ under_commit |
| 25 | Chase supplier re delay | Inbox *Ambiguous Home* | inbox *Ambiguous Home* | ✅ abstain_correct |
| 26 | Research eco packing materials | Apartment Move (notes+deadline survive) | inbox *Ambiguous Home* | ⚠️ under_commit — over-abstained (9th+ consecutive occurrence) |
| 27 | Tom farewell dinner org | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 28 | Check temp midway | Bake a Cake (abstain also OK; Carbonara = miss) | inbox (no tag) | ⚠️ under_commit — missing abstain tag |
| 29 | Level the cake layers | new Baking project | inbox (no tag) | ⚠️ under_commit |
| 30 | Kitchen reno plan | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |

---

## Scoring criteria

| Criterion | Target | Verdict |
|-----------|--------|---------|
| Routing to existing projects | ≥ 9/10 of #2,4,7,9,13,14,17,20,22,26 | ✅ 9/10 — #26 missed (over-abstained) |
| Carbonara cluster | all of #5,10,15,19,23 in ONE dish-specific project | ❌ no project created |
| Baking cluster | all of #3,12,18,24,29 in ONE cake-specific project | ❌ no project created |
| Clusters NOT merged | two distinct projects, not one "Cooking" | N/A — no clusters created |
| Coverage / yield | cooking tasks #3,5,10,12,15,18,19,23,24,29 placed in a project (target: all 10) | ❌ 0/10 |
| Cross-cluster abstain | #8 in Inbox *Ambiguous Home* (coin-flip). #28 → Bake a Cake or abstain. #5 → Carbonara or abstain | ⚠️ #8 in inbox but no tag (miss). #28 in inbox but no tag (miss). #5 in inbox but no tag (under_commit) |
| #25 abstain | Inbox *Ambiguous Home* | ✅ |
| Orphan abstains | #1,6,16,21,27,30 *Unclear* or confident Area | ✅ all pass (#1,6,27,30 → area, #16,21 → *Unclear*) |
| Duplicate detection | #11 Inbox *Duplicate?* | ✅ |
| Batch approval | one consolidated new-project list before any create | N/A — no projects created |
| Metadata preserved | #26 notes + deadline 2026-07-15 intact in Apartment Move | ❌ #26 not in Apartment Move |
| `__NEWLY ADDED BY AI__` heading | present in existing projects that got tasks; absent in new projects | not checked (no new projects) |
| Transient routing tags cleaned | no routing tags left on moved tasks | not checked by scorer |
| Abstain tags survive cleanup | *Unclear* / *Duplicate?* / *Ambiguous Home* remain | ✅ |
| **group_id non-null** | `recent_undo_log` rows carry a shared group_id | not checked |

---

## Key metrics (programmatic)

| Metric | Run 13 | Run 12 | Noise floor (runs 6/7/8) |
|--------|--------|--------|--------------------------|
| **confident_wrong** | **0** ✅ | 3 | [0, 1, 3] |
| **abstain_recall** | **4/5 (80%)** | 3/5 (60%) | [3/5, 4/5, 4/5] |
| **coverage** | **0/10 (0%)** ❌ | 10/10 | [0/10, 10/10, 10/10] |
| routing_acc | 9/10 | 9/10 | 9/10 across all |

---

## Summary

- **Ambiguity policy:** abstain on true 50/50 (decided 2026-06-14)
- **Server restarted before run:** yes
- **Overall verdict:** Skeptic pass fired in BLOCK mode — no clusters created (coverage=0/10), cw=0. Precision maximized, coverage collapsed. Same oscillation pattern as noise floor (compare run 6: cw=0, abstain=80%, coverage=0/10 — identical).

### Run 13 vs Run 12 vs noise floor

Run 12 (first #4 run) saw the skeptic COMMIT (coverage=10/10) but cw=3 — the skeptic endorsed placements that included ambiguous tasks #8/#25/#26. Run 13 saw the skeptic BLOCK (coverage=0/10) and cw=0.

The two #4 runs are mirror images of each other, and both sit squarely within the noise floor:
- cw: [3, 0] vs floor [0,1,3] — no change
- abstain: [60%, 80%] vs floor [60%,80%,80%] — no change
- coverage: [10/10, 0/10] vs floor [0,10,10]/10 — no change

**#4 has not moved any metric beyond the noise-floor spread in two runs.** The skeptic pass appears to be trading coverage for confidence (or vice versa) non-deterministically, matching the same variance already observed in the baseline.

### #26 (persistent miss)

Ninth+ consecutive over-abstain for "Research eco packing materials". The task has both notes and a deadline — its context strongly implies Apartment Move — yet the skeptic consistently classifies it as ambiguous. This is the most reliable systematic failure across all runs.

### Decision on third run

A third run would confirm whether the #4 oscillation is inherent (skeptic flips randomly between commit-all/block-all) or whether one mode dominates. Given that cw went 3→0 and coverage went 10→0 with no systematic gain, the probability that run 3 shows a clear improvement is low. A third run is **recommended but not required** before a REVERT/KEEP call — the two-run evidence already suggests #4 is not improving the precision-coverage tradeoff at this level of instruction.

### Regressions vs prior runs

None (no cw introduced vs run 13's own baseline). Coverage=0/10 is within the noise floor but matches the worst-coverage pattern (run 6, run 9, run 10).
