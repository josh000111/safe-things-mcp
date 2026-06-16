# Test 5 — Scoring: 2026-06-16 Run 10 (post-#5 instruction tuning, second run)

**Run context:** Second and final test of BACKLOG #5 ("COMMIT FULLY TO CLUSTERS
CREATED" + step-8 follow-through verify). SHA `f2c23b6`. Model: Sonnet 4.6.
Fixture: pristine reset prior to blind run (reset completed by Session R after run 9).

---

## ❌ HEADLINE: coverage = 0/10 — NO CLUSTERS CREATED (second consecutive zero under #5)

The agent created **zero new projects** for the second run in a row under the #5
instruction. All 10 cooking tasks (Carbonara + Baking) remain in the Inbox with no
tag. The "COMMIT FULLY TO CLUSTERS YOU CREATE" instruction did not fire.

**Pattern across #5 runs:**
- Run 9 (post-#5, first): coverage=0/10 — no projects created at all.
- Run 10 (post-#5, second): coverage=0/10 — no projects created at all.
- Baseline run 6 (pre-#5): coverage=0/10 — projects created but empty.
- Baseline runs 7/8 (pre-#5): coverage=10/10 — clusters fully populated.

The #5 instruction targeted "created but empty" (run-6 failure). Runs 9+10 show
the failure is more upstream: the agent never reaches the project-creation step.
The prose tuning did not fix — and may have slightly worsened — the hesitation.

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
| 8 | Mix ingredients | Inbox *Ambiguous Home* (coin-flip; any cluster = miss) | inbox: (no tag) | ⚠️ under_commit (missing *Ambiguous Home* tag) |
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
| 26 | Research eco packing materials | Apartment Move (notes+deadline survive) | inbox: *Ambiguous Home* | ❌ under_commit (persistent: over-abstained again) |
| 27 | Tom farewell dinner org | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 28 | Check temp midway | Bake a Cake (abstain also OK) | inbox: (no tag) | ⚠️ under_commit (missing abstain tag) |
| 29 | Level the cake layers | new Baking project | inbox: (no tag) | ⚠️ under_commit |
| 30 | Kitchen reno plan | Inbox *Unclear* (or existing Area = pass) | project:Apartment Move | ⚠️ needs_review (singleton placed in project — scorer flagged for human review; policy expects inbox or area) |

---

## Scoring criteria

| Criterion | Target | Verdict |
|-----------|--------|---------|
| Routing to existing projects | ≥ 9/10 of #2,4,7,9,13,14,17,20,22,26 | ✅ 9/10 (90%) — #26 missed |
| Carbonara cluster | all of #5,10,15,19,23 in ONE dish-specific project | ❌ NO PROJECT CREATED |
| Baking cluster | all of #3,12,18,24,29 in ONE cake-specific project | ❌ NO PROJECT CREATED |
| Clusters NOT merged | two distinct projects, not one "Cooking" | N/A (no clusters) |
| **Coverage / yield** | cooking tasks #3,5,10,12,15,18,19,23,24,29 placed (target: all 10) | ❌ **0/10 (0%)** |
| Cross-cluster abstain | #8 *Ambiguous Home*; #28 → Bake or abstain; #5 → Carbonara or abstain | ⚠️ all three in inbox without tags |
| #25 abstain | Inbox *Ambiguous Home* | ✅ |
| Orphan abstains | #1,6,16,21,27,30 *Unclear* or confident Area | ⚠️ #30 placed in project:Apartment Move (needs review) |
| Duplicate detection | #11 Inbox *Duplicate?* | ✅ |
| Batch approval | one consolidated new-project list before any create | N/A (no new projects) |
| Metadata preserved | #26 notes + deadline 2026-07-15 intact | ❌ #26 not moved (over-abstained) |
| `__NEWLY ADDED BY AI__` heading | present in existing projects that got tasks | not checked |
| Transient routing tags cleaned | no routing tags left on moved tasks | not checked |
| Abstain tags survive cleanup | *Unclear* / *Duplicate?* / *Ambiguous Home* remain | ✅ |
| **group_id non-null** | `recent_undo_log` rows carry a shared group_id | not checked |

---

## Metrics summary

| Metric | Run 10 (post-#5) | Run 9 (post-#5) | Baseline spread (runs 6/7/8) | Verdict |
|--------|------------------|-----------------|------------------------------|---------|
| **confident_wrong** | **0** | 0 | [0, 1, 3] | ✅ best case, at noise floor |
| **abstain_recall** | **4/5 (80%)** | 4/5 (80%) | [60%, 80%, 80%] | ✅ at baseline ceiling |
| **coverage** | **0/10 (0%)** | 0/10 (0%) | [0, 10, 10] | ❌ **SECOND CONSECUTIVE ZERO — below min>0 bar** |
| routing_acc | 9/10 (90%) | 9/10 (90%) | 9/10 all runs | ✅ stable |
| carbonara_cohesion | false | false | false/true/true | ❌ |
| baking_cohesion | false | false | false/true/true | ❌ |

---

## BACKLOG #5 decision — REVERT CANDIDATE

**Rule (from MISSION-CONTROL):** "Coverage = 0 again in run 10: two consecutive
zeros under #5 means the instruction did not fire. Set #5 'REVERT CANDIDATE —
coverage 0 in runs 9+10 despite commit-to-cluster prose; instruction ineffective'."

**Verdict: REVERT CANDIDATE.**

The instruction "COMMIT FULLY TO CLUSTERS YOU CREATE" (SHA `f2c23b6`) produced no
measurable lift on coverage in either #5 run:
- Run 9: 0/10 (no projects created)
- Run 10: 0/10 (no projects created)

The instruction addressed the wrong failure mode. The prose assumed the agent was
creating but not populating projects (run-6 mode). The actual failure in runs 9+10
is upstream: the agent never decides to create clusters at all. Stronger prose
about commitment to clusters that ARE created cannot fix hesitation at the
cluster-creation decision.

**Two paths forward:**
1. **Revert #5 prose** and attack the root cause differently — the agent needs a
   stronger signal to recognise when cluster evidence is sufficient to commit.
   Possible angle: explicitly enumerate the evidence threshold in instructions
   (e.g., "5 tasks that share a dish name = create the project; do not abstain").
2. **Escalate to BACKLOG #4** (two-pass router→skeptic architecture): the first
   pass commits to clusters; the skeptic only vetoes on genuine ambiguity. Stronger
   structural lever than prose tuning.

**Recommended next crank:** DEV session, Opus 4.8 (instruction/architecture
reasoning required) — either revert + re-draft #5 prose with explicit evidence
threshold, OR design and implement #4 (two-pass router) as a stronger lever.

---

## Persistent failures (every run, not variance)

- **#26 "Research eco packing materials"** — over-abstained in runs 5, 6, 7, 8, 9,
  10. The notes ("Bamboo wrap…") and the deadline (2026-07-15) plus "eco packing"
  strongly imply Apartment Move context. Agent consistently tags *Ambiguous Home*.
  Likely needs an explicit example in instructions (deadline + notes = route to the
  most plausible existing project).
- **#8 "Mix ingredients"** — coin-flip task. Agent leaves it in inbox without the
  required *Ambiguous Home* tag (missing in runs 5, 9, 10; correct in runs 6, 7, 8).
  Intermittent: may be noise rather than a systematic instruction gap.

---

## Summary

- **Ambiguity policy:** abstain on true 50/50 (decided 2026-06-14)
- **Server restarted before run (code fixes live):** yes (#5 commit f2c23b6)
- **Overall verdict:** REVERT CANDIDATE. #5 instruction tuning confirmed
  ineffective across both test runs. cw=0 and abstain_recall=80% maintained, but
  coverage=0/10 in both runs — the two-zero pattern is outside noise-floor tolerance
  for "no effect" and suggests the instruction may be adding hesitation rather than
  helping.
- **Regressions vs baseline:** cluster creation failure rate worsened (baseline:
  coverage=0 in 1/3 runs; post-#5: 0 in 2/2 runs). Not yet statistically
  conclusive (small N) but directionally concerning.
- **Next action:** DEV handoff (Opus 4.8) — revert #5 prose or escalate to #4
  two-pass router.
