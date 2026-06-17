# Test 5 — Run 14 Scoring (2026-06-17, BACKLOG #6)

Scored via `uv run things-mcp-score --pretty` against SHA `83eabe5` (BACKLOG #6
three-part instruction patch: notes-first rule, mandatory coin-flip abstain, cluster-plan
+ empty-project guard).

---

## Routing truth table (30 tasks)

| # | Title | Expected (key) | Actual | Verdict |
|---|-------|----------------|--------|---------|
| 1 | Collect dry cleaning | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 2 | Add endpoint rate-limit headers | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ |
| 3 | Preheat oven 180 | new Baking project | area:Personal | ❌ confident_wrong |
| 4 | Conf sofa collection date | Apartment Move | project:Apartment Move | ✅ |
| 5 | Separate egg yolks from whites | Carbonara (abstain also OK) | area:Personal | ❌ confident_wrong |
| 6 | Return library books | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 7 | Chase revised scope doc | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ |
| 8 | Mix ingredients | Inbox *Ambiguous Home* (coin-flip; any cluster = miss) | area:Personal | ❌ confident_wrong |
| 9 | Fix search clear field crash | Recipe App | project:Recipe App | ✅ |
| 10 | Chop guanciale into cubes | new Carbonara project | area:Personal | ❌ confident_wrong |
| 11 | Invoice client March | Inbox *Duplicate?* | inbox *Duplicate?* | ✅ |
| 12 | Line tin with parchment | new Baking project | area:Personal | ❌ confident_wrong |
| 13 | Send new DD details to agent | Apartment Move | project:Apartment Move | ✅ |
| 14 | Add back btn to onboarding | Recipe App | project:Recipe App | ✅ |
| 15 | Grate pecorino romano | new Carbonara project | area:Personal | ❌ confident_wrong |
| 16 | 🛒 | Inbox *Unclear* | inbox *Unclear* | ✅ |
| 17 | Set up client QA sandbox | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ |
| 18 | Skewer test the sponge | new Baking project | area:Personal | ❌ confident_wrong |
| 19 | Stir yolks into pasta | new Carbonara project | area:Personal | ❌ confident_wrong |
| 20 | Check utilities transfer options | Apartment Move | project:Apartment Move | ✅ |
| 21 | That thing | Inbox *Unclear* | inbox *Unclear* | ✅ |
| 22 | Add legume nutrition data | Recipe App | project:Recipe App | ✅ |
| 23 | Render guanciale fat slow | new Carbonara project | area:Personal | ❌ confident_wrong |
| 24 | Cool sponge before icing | new Baking project | area:Personal | ❌ confident_wrong |
| 25 | Chase supplier re delay | Inbox *Ambiguous Home* | inbox *Ambiguous Home* | ✅ |
| 26 | Research eco packing materials | Apartment Move (notes+deadline survive) | inbox *Ambiguous Home* | ⚠️ under_commit (not cw) |
| 27 | Tom farewell dinner org | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 28 | Check temp midway | Bake a Cake (abstain also OK; Carbonara = miss) | area:Personal | ❌ confident_wrong |
| 29 | Level the cake layers | new Baking project | area:Personal | ❌ confident_wrong |
| 30 | Kitchen reno plan | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |

---

## Scoring criteria

| Criterion | Target | Verdict |
|-----------|--------|---------|
| Routing to existing projects | ≥ 9/10 of #2,4,7,9,13,14,17,20,22,26 | ✅ 9/10 (#26 under_commit — 10th+ consecutive) |
| Carbonara cluster | all of #5,10,15,19,23 in ONE dish-specific project | ❌ no project created; all → area:Personal |
| Baking cluster | all of #3,12,18,24,29 in ONE cake-specific project | ❌ no project created; all → area:Personal |
| Clusters NOT merged | two distinct projects, not one "Cooking" | N/A (no clusters at all) |
| Coverage / yield | cooking tasks #3,5,10,12,15,18,19,23,24,29 placed in a project | ❌ 0/10 |
| Cross-cluster abstain | #8 → *Ambiguous Home*; #28 → Baking or abstain; #5 → Carbonara or abstain | ❌ all three → area:Personal (confident_wrong) |
| #25 abstain | Inbox *Ambiguous Home* | ✅ correctly abstained |
| Orphan abstains | #1,6,16,21,27,30 *Unclear* or confident Area | ✅ (all area pass or inbox tagged) |
| Duplicate detection | #11 Inbox *Duplicate?* | ✅ |
| Batch approval | one consolidated new-project list before any create | N/A (no projects created) |
| Metadata preserved | #26 notes + deadline 2026-07-15 intact in Apartment Move | N/A (#26 not moved to Apartment Move) |
| `__NEWLY ADDED BY AI__` heading | present in existing projects that received tasks | not checked |
| Transient routing tags cleaned | no routing tags left on moved tasks | not checked |
| Abstain tags survive cleanup | *Unclear* / *Duplicate?* / *Ambiguous Home* remain | ✅ |
| **group_id non-null** | undo_log rows share a group_id | not checked |

---

## Summary

- **Server restarted before run (BACKLOG #6 code live):** yes (SHA `83eabe5`)
- **Confident-wrong count: 12** ❌ — catastrophic regression. Worst since run 3 (cw=13).
  Misplaced tasks: #3, #5, #8, #10, #12, #15, #18, #19, #23, #24, #28, #29.
- **Coverage: 0/10** ❌ — zero new projects created. All 10 cluster tasks routed to
  area:Personal (novel failure mode).
- **Abstain-recall: 4/5 (80%)** ✅ — within noise floor (only #8 missed; moved to Personal
  instead of tagged *Ambiguous Home*).
- **Routing-acc: 9/10** ✅ — within noise floor (#26 over-abstained again, 10th+
  consecutive).

**Root failure:** The agent did not create any Carbonara or Baking projects. Instead of
clustering the cooking tasks into new projects, it routed all cooking/food-prep tasks to
`area:Personal` as a generic personal catch-all. This is a novel failure distinct from
prior runs:
- Run 13 (#4 skeptic) blocked all creation (cw=0, coverage=0)
- This run: no blocking, but agent substituted Personal area for the cluster projects it
  should have created (cw=12, coverage=0)

**BACKLOG #6 verdict: REVERT.** cw=12 is 4× above the noise-floor ceiling of 3. The
instruction patch (cluster-plan step + empty-project guard) appears to have interfered
with the agent's clustering behaviour. Since this is the only run of #6 and the result is
outside any plausible noise explanation, a second run is not required before reverting.

- **Overall verdict: ❌ CRITICAL REGRESSION — REVERT BACKLOG #6**
- **Regressions vs noise floor (cw=[0,1,3]):** cw=12, 4× above ceiling. New failure:
  cooking tasks → area:Personal instead of new projects.
