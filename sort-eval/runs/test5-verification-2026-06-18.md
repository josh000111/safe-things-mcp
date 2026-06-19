# Test 5 — Run 15 Scoring (2026-06-18)

**SHA:** f446582 (post-#6-revert = #5-revert baseline, same AGENT_INSTRUCTIONS as 773e920)
**Build:** BACKLOG #6 reverted; no code change since run 14 revert
**Model:** Sonnet 4.6
**Fixture:** test5 v1 (reset before run)
**group_id:** 18875e44-e873-4805-a412-f58152f5abaa ✅ (non-null)
**Server restarted before run:** yes
**Scored by:** `uv run things-mcp-score --pretty`

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
| 26 | Research eco packing materials | Apartment Move (notes+deadline survive) | area:Work | ❌ confident_wrong |
| 27 | Tom farewell dinner org | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 28 | Check temp midway | Bake a Cake (abstain also OK; Carbonara = miss) | inbox (no tag) | ⚠️ under_commit — missing abstain tag |
| 29 | Level the cake layers | new Baking project | inbox (no tag) | ⚠️ under_commit |
| 30 | Kitchen reno plan | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |

---

## Scoring criteria

| Criterion | Target | Verdict |
|-----------|--------|---------|
| Routing to existing projects | ≥ 9/10 of #2,4,7,9,13,14,17,20,22,26 | ❌ 9/10 — #26 → area:Work (miss) |
| Carbonara cluster | all of #5,10,15,19,23 in ONE dish-specific project | ❌ projects created ("Make Carbonara") but **empty** — all tasks remain in Inbox |
| Baking cluster | all of #3,12,18,24,29 in ONE cake-specific project | ❌ projects created ("Bake Sponge Cake") but **empty** — all tasks remain in Inbox |
| Clusters NOT merged | two distinct projects, not one "Cooking" | ✅ two separate projects created |
| Coverage / yield | cooking tasks #3,5,10,12,15,18,19,23,24,29 placed in a project | ❌ 0/10 — both cluster projects empty |
| Cross-cluster abstain | #8 in Inbox *Ambiguous Home*. #28 → Bake a Cake or abstain. #5 → Carbonara or abstain | ⚠️ #8 in inbox but no tag (miss); #5 in inbox no tag (under-commit); #28 in inbox no tag (under-commit) |
| #25 abstain | Inbox *Ambiguous Home* | ✅ |
| Orphan abstains | #1,6,16,21,27,30 *Unclear* or confident Area | ✅ all pass (#1,6,27 → area:Personal; #30 → area:Home; #16,#21 correctly tagged *Unclear*) |
| Duplicate detection | #11 Inbox *Duplicate?* | ✅ |
| Batch approval | one consolidated new-project list before any create | unknown (not observable post-run) |
| Metadata preserved | #26 notes + deadline 2026-07-15 intact in Apartment Move | ❌ #26 in area:Work, not Apartment Move |
| `__NEWLY ADDED BY AI__` heading | present in existing projects that got tasks | ⚠️ partial — present in Apartment Move ✅ and Recipe App ✅; **absent in Freelance: TechCorp API** ❌ |
| Transient routing tags cleaned | no routing tags left on moved tasks | ✅ no tags on moved tasks |
| Abstain tags survive cleanup | *Unclear* / *Duplicate?* / *Ambiguous Home* remain | ✅ #11, #16, #21, #25 all correct |
| **group_id non-null** | `undo_log` rows carry a shared group_id | ✅ 18875e44-e873-4805-a412-f58152f5abaa |

---

## BACKLOG #3c first live data point

`sort_guard_rejected` table: **0 rows** for this run. The agent did not attempt to create any sub-threshold (< 3 task) project during this sort. The guard was never triggered. This is informative: in runs where the agent creates projects, it tends to use ≥ 3 tasks, so the guard may rarely fire. Not enough to draw conclusions from one run.

---

## Programmatic metrics summary

| Metric | Value | vs noise floor [runs 6/7/8] |
|--------|-------|-----------------------------|
| confident_wrong | **1** | within [0,1,3] |
| abstain_recall | **4/5 (80%)** | at ceiling [60%,80%,80%] |
| routing_acc | **9/10 (90%)** | consistent |
| coverage | **0/10 (0%)** | at floor min [0,10,10] |
| carbonara_cohesion | false | — |
| baking_cohesion | false | — |
| metadata_preserved_26 | false | — |

---

## Run narrative

Projects "Make Carbonara" (area:Personal) and "Bake Sponge Cake" (area:Personal) were created — **both empty**. All 10 cluster tasks remained in the Inbox without tags. This is the same "empty projects" failure mode as run 6: agent creates the shell but never executes the follow-through bulk_move into them. The 6 bulk_moves in the undo log all went to existing projects and areas, not to the two new projects.

#26 ("Research eco packing materials") placed in area:Work — the same confident-wrong miss as run 8 and run 12. Persistent failure: 11+ consecutive misses, alternating between over-abstain and wrong-area.

#8 ("Mix ingredients") stayed in Inbox but without its *Ambiguous Home* tag — same near-miss as runs 5, 6, 9, 10, 11, 13.

All within noise floor. No metric moved outside the established spread.

---

## Summary

- **Ambiguity policy:** abstain on true 50/50 (decided 2026-06-14)
- **Server restarted before run:** yes
- **Overall verdict:** within noise floor. cw=1, abstain_recall=80%, coverage=0/10. Empty-project failure (same as run 6). All three primary metrics within the noise-floor spread [cw=[0,1,3], abstain=[60%,80%,80%], coverage=[0,10,10]].
- **Regressions vs best runs:** none new. Confirms revert of #6 returned system to baseline. Persistent known issues: #26 wrong-area, #8 missing tag, cluster projects created but empty.
- **Fixture state after run:** DIRTY — "Make Carbonara" and "Bake Sponge Cake" projects exist (empty); 10 cluster tasks in Inbox; #1,6,27,30 in areas; #11,16,21,25 have abstain tags. Reset needed before run 16.
