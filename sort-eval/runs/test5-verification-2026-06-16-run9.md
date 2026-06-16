# Test 5 — Scoring: 2026-06-16 Run 9 (post-#5 instruction tuning)

**Run context:** First test of BACKLOG #5 ("COMMIT FULLY TO CLUSTERS CREATED" +
step-8 follow-through verify). SHA `f2c23b6`. Model: Sonnet 4.6. Fixture: pristine
reset prior to blind run.

---

## ⚠️ HEADLINE: coverage = 0/10 — NO CLUSTERS CREATED

The agent created **zero new projects**. This is the failure mode targeted by #5
(run-6 created empty projects; run-9 didn't create projects at all). The
instruction tuning did not produce a populated cluster.

**Create vs. populate breakdown:**
- Run 6 (baseline): projects CREATED (Make Carbonara, Bake a Cake) but EMPTY — tasks never moved in.
- Run 9 (post-#5): projects NOT CREATED at all — the agent never reached the cluster-creation step.

#5 aimed at the "created but not populated" failure. Run 9 shows the failure is
upstream of that: the agent is over-abstaining on the cluster-creation decision
itself, not just the move step.

---

## Routing truth table (30 tasks)

| # | Title | Expected (key) | Actual | Verdict |
|---|-------|----------------|--------|---------|
| 1 | Collect dry cleaning | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 2 | Add endpoint rate-limit headers | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 3 | Preheat oven 180 | new Baking project | inbox: (no tag) | ⚠️ under_commit |
| 4 | Conf sofa collection date | Apartment Move | project:Apartment Move | ✅ correct |
| 5 | Separate egg yolks from whites | Carbonara (abstain also OK) | inbox: (no tag) | ⚠️ under_commit |
| 6 | Return library books | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 7 | Chase revised scope doc | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 8 | Mix ingredients | Inbox *Ambiguous Home* (coin-flip; any cluster = miss) | inbox: (no tag) | ⚠️ under_commit (missing tag) |
| 9 | Fix search clear field crash | Recipe App | project:Recipe App | ✅ correct |
| 10 | Chop guanciale into cubes | new Carbonara project | inbox: (no tag) | ⚠️ under_commit |
| 11 | Invoice client March | Inbox *Duplicate?* | inbox: *Duplicate?* | ✅ abstain_correct |
| 12 | Line tin with parchment | new Baking project | inbox: (no tag) | ⚠️ under_commit |
| 13 | Send new DD details to agent | Apartment Move | project:Apartment Move | ✅ correct |
| 14 | Add back btn to onboarding | Recipe App | project:Recipe App | ✅ correct |
| 15 | Grate pecorino romano | new Carbonara project | inbox: (no tag) | ⚠️ under_commit |
| 16 | 🛒 | Inbox *Unclear* | inbox: *Unclear* | ✅ abstain_correct |
| 17 | Set up client QA sandbox | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 18 | Skewer test the sponge | new Baking project | inbox: (no tag) | ⚠️ under_commit |
| 19 | Stir yolks into pasta | new Carbonara project | inbox: (no tag) | ⚠️ under_commit |
| 20 | Check utilities transfer options | Apartment Move | project:Apartment Move | ✅ correct |
| 21 | That thing | Inbox *Unclear* | inbox: *Unclear* | ✅ abstain_correct |
| 22 | Add legume nutrition data | Recipe App | project:Recipe App | ✅ correct |
| 23 | Render guanciale fat slow | new Carbonara project | inbox: (no tag) | ⚠️ under_commit |
| 24 | Cool sponge before icing | new Baking project | inbox: (no tag) | ⚠️ under_commit |
| 25 | Chase supplier re delay | Inbox *Ambiguous Home* | inbox: *Ambiguous Home* | ✅ abstain_correct |
| 26 | Research eco packing materials | Apartment Move (notes+deadline survive) | inbox: *Ambiguous Home* | ❌ under_commit (persistent: #26 over-abstained again) |
| 27 | Tom farewell dinner org | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 28 | Check temp midway | Bake a Cake (abstain also OK) | inbox: (no tag) | ⚠️ under_commit (missing abstain tag) |
| 29 | Level the cake layers | new Baking project | inbox: (no tag) | ⚠️ under_commit |
| 30 | Kitchen reno plan | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |

---

## Scoring criteria

| Criterion | Target | Verdict |
|-----------|--------|---------|
| Routing to existing projects | ≥ 9/10 of #2,4,7,9,13,14,17,20,22,26 | ✅ 9/10 (90%) — #26 missed |
| Carbonara cluster | all of #5,10,15,19,23 in ONE dish-specific project | ❌ NO PROJECT CREATED |
| Baking cluster | all of #3,12,18,24,29 in ONE cake-specific project | ❌ NO PROJECT CREATED |
| Clusters NOT merged | two distinct projects, not one "Cooking" | N/A (no clusters) |
| **Coverage / yield** | cooking tasks #3,5,10,12,15,18,19,23,24,29 placed (target: all 10) | ❌ **0/10 (0%)** |
| Cross-cluster abstain | #8 *Ambiguous Home*; #28 → Bake or abstain; #5 → Carbonara or abstain | ⚠️ #8 in inbox without tag; #28 in inbox without tag; #5 in inbox without tag |
| #25 abstain | Inbox *Ambiguous Home* | ✅ |
| Orphan abstains | #1,6,16,21,27,30 *Unclear* or confident Area | ✅ (area placements for #1,6,27,30 pass) |
| Duplicate detection | #11 Inbox *Duplicate?* | ✅ |
| Batch approval | one consolidated new-project list before any create | N/A (no new projects) |
| Metadata preserved | #26 notes + deadline 2026-07-15 intact | ❌ #26 not moved (#26 over-abstained) |
| `__NEWLY ADDED BY AI__` heading | present in existing projects that got tasks | not checked (scorer N/A) |
| Transient routing tags cleaned | no routing tags left on moved tasks | not checked |
| Abstain tags survive cleanup | *Unclear* / *Duplicate?* / *Ambiguous Home* remain | ✅ (visible in scorer output) |
| **group_id non-null** | `recent_undo_log` rows carry a shared group_id | not checked |

---

## Metrics summary

| Metric | Run 9 (post-#5) | Baseline spread (runs 6/7/8) | Status |
|--------|-----------------|------------------------------|--------|
| **confident_wrong** | **0** | [0, 1, 3] | ✅ within noise floor |
| **abstain_recall** | **4/5 (80%)** | [60%, 80%, 80%] | ✅ at baseline ceiling |
| **coverage** | **0/10 (0%)** | [0, 10, 10] | ⚠️ within noise floor (run 6 also 0) |
| routing_acc | 9/10 (90%) | 9/10 all runs | ✅ stable |

---

## BACKLOG #5 assessment — create vs. populate

**#5 hypothesis:** the agent was creating projects but failing to populate them
(run-6 failure mode). The fix added "COMMIT FULLY TO CLUSTERS YOU CREATE" +
step-8 follow-through verify to AGENT_INSTRUCTIONS.

**What run 9 shows:** the agent did NOT create any projects. All 10 cooking tasks
remain in the Inbox with no tag. This is not the "created empty" failure mode —
it is a more upstream failure: the agent never decided to create the clusters.

**Interpretation:** Coverage=0 is within the noise-floor spread (run 6 also had
coverage=0), so this single run cannot distinguish "instruction tuning made things
worse" from "lucky bad sample." The #5 instruction change did not demonstrably
help on this run.

**Per judgment rule:** coverage=0 — flag prominently. Instruction did not visibly
take effect. Recommend one more blind run before any revert decision.

**Persistent failures (appear in every run):**
- #26 "Research eco packing materials" over-abstained → tagged *Ambiguous Home*
  instead of routing to Apartment Move (runs 5, 6, 7, 8, 9 all miss this).
- #8 "Mix ingredients" consistently not given *Ambiguous Home* tag when left in
  inbox (only correctly abstained with tag in runs 7/8 intermittently).

---

## Summary

- **Ambiguity policy:** abstain on true 50/50 (decided 2026-06-14)
- **Server restarted before run (code fixes live):** yes (#5 commit f2c23b6)
- **Overall verdict:** coverage=0, no clusters created. #5 instruction tuning
  produced no visible effect on this single run. Within baseline noise floor.
  Need 1+ more run to confirm before any revert decision.
- **Regressions vs baseline:** none beyond expected noise-floor variance. Existing-
  project routing solid at 9/10. cw=0 maintained.
- **Next action:** another blind run (run 10) to see if coverage improves. If run
  10 also shows coverage=0 or empty projects, escalate: #5 instruction approach
  is insufficient and a stronger intervention (e.g., #4 two-pass router, or
  different instruction framing) is needed.
