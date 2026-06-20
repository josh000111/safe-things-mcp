# Test 5 — Run 16 Scoring (2026-06-19)

**SHA:** 64853f4 (A1 atomic-populate + B1 decontamination; 530 tests pass)
**Build:** BACKLOG A1 (atomic populate — `member_todo_ids` flows through to `bulk_move.execute` in `add_project.execute`) + BACKLOG B1 (decontamination — cooking examples replaced in `AGENT_INSTRUCTIONS`)
**Model:** Sonnet 4.6
**Fixture:** test5 v1 (reset before run)
**group_id:** not checked (scorer did not surface it)
**Server restarted before run:** yes (A1+B1 live)
**Scored by:** `uv run things-mcp-score --pretty`

---

## Routing truth table (30 tasks)

| # | Title | Expected (key) | Actual | Verdict |
|---|-------|----------------|--------|---------|
| 1 | Collect dry cleaning | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 2 | Add endpoint rate-limit headers | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 3 | Preheat oven 180 | new Baking project | project:Bake Cake | ✅ correct |
| 4 | Conf sofa collection date | Apartment Move | project:Apartment Move | ✅ correct |
| 5 | Separate egg yolks from whites | Carbonara (abstain also OK) | project:Make Carbonara | ✅ correct |
| 6 | Return library books | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 7 | Chase revised scope doc | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 8 | Mix ingredients | Inbox *Ambiguous Home* (coin-flip; any cluster = miss) | project:Bake Cake | ❌ confident_wrong |
| 9 | Fix search clear field crash | Recipe App | project:Recipe App | ✅ correct |
| 10 | Chop guanciale into cubes | new Carbonara project | project:Make Carbonara | ✅ correct |
| 11 | Invoice client March | Inbox *Duplicate?* | project:Freelance: TechCorp API (tag: *Duplicate?*) | ❌ confident_wrong — correctly tagged duplicate but moved instead of left in inbox |
| 12 | Line tin with parchment | new Baking project | project:Bake Cake | ✅ correct |
| 13 | Send new DD details to agent | Apartment Move | project:Apartment Move | ✅ correct |
| 14 | Add back btn to onboarding | Recipe App | project:Recipe App | ✅ correct |
| 15 | Grate pecorino romano | new Carbonara project | project:Make Carbonara | ✅ correct |
| 16 | 🛒 | Inbox *Unclear* | inbox *Unclear* | ✅ abstain_correct |
| 17 | Set up client QA sandbox | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 18 | Skewer test the sponge | new Baking project | project:Bake Cake | ✅ correct |
| 19 | Stir yolks into pasta | new Carbonara project | project:Make Carbonara | ✅ correct |
| 20 | Check utilities transfer options | Apartment Move | project:Apartment Move | ✅ correct |
| 21 | That thing | Inbox *Unclear* | inbox *Unclear* | ✅ abstain_correct |
| 22 | Add legume nutrition data | Recipe App | project:Recipe App | ✅ correct |
| 23 | Render guanciale fat slow | new Carbonara project | project:Make Carbonara | ✅ correct |
| 24 | Cool sponge before icing | new Baking project | project:Bake Cake | ✅ correct |
| 25 | Chase supplier re delay | Inbox *Ambiguous Home* | area:Work | ❌ confident_wrong — persistent failure |
| 26 | Research eco packing materials | Apartment Move (notes+deadline survive) | area:Work | ❌ confident_wrong — persistent failure (#26 run 8, 12, 15, 16: wrong-area) |
| 27 | Tom farewell dinner org | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 28 | Check temp midway | Bake a Cake (abstain also OK; Carbonara = miss) | project:Bake Cake | ✅ correct |
| 29 | Level the cake layers | new Baking project | project:Bake Cake | ✅ correct |
| 30 | Kitchen reno plan | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |

---

## Scoring criteria

| Criterion | Target | Verdict |
|-----------|--------|---------|
| Routing to existing projects | ≥ 9/10 of #2,4,7,9,13,14,17,20,22,26 | ❌ 9/10 — #26 → area:Work (persistent miss) |
| Carbonara cluster | all of #5,10,15,19,23 in ONE dish-specific project | ✅ "Make Carbonara" — 5/5 tasks placed |
| Baking cluster | all of #3,12,18,24,29 in ONE cake-specific project | ✅ "Bake Cake" — 5/5 tasks placed (+ #8 and #28 also landed here) |
| Clusters NOT merged | two distinct projects, not one "Cooking" | ✅ two separate projects |
| Coverage / yield | cooking tasks #3,5,10,12,15,18,19,23,24,29 placed in a project | ✅ **10/10** — FIRST FULL COVERAGE SINCE RUN 7 |
| Cross-cluster abstain | #8 in Inbox *Ambiguous Home* (coin-flip). #28 → Bake a Cake or abstain. #5 → Carbonara or abstain | ❌ #8 → Bake Cake (miss; coin-flip committed); ✅ #28 → Bake Cake (pass); ✅ #5 → Make Carbonara (pass) |
| #25 abstain | Inbox *Ambiguous Home* | ❌ → area:Work (confident_wrong) |
| Orphan abstains | #1,6,16,21,27,30 *Unclear* or confident Area | ✅ all pass (#1,6,27 → area:Personal; #30 → area:Home; #16,#21 inbox *Unclear*) |
| Duplicate detection | #11 Inbox *Duplicate?* | ❌ → project:Freelance: TechCorp API with *Duplicate?* tag — detected but moved (should stay in inbox) |
| Batch approval | one consolidated new-project list before any create | unknown (not observable post-run) |
| Metadata preserved | #26 notes + deadline 2026-07-15 intact in Apartment Move | ❌ #26 in area:Work, not Apartment Move |
| `__NEWLY ADDED BY AI__` heading | present in existing projects that got tasks; absent in new projects | not checked |
| Transient routing tags cleaned | no routing tags left on moved tasks | ✅ (no spurious tags observed) |
| Abstain tags survive cleanup | *Unclear* / *Duplicate?* / *Ambiguous Home* remain | ✅ #16, #21 *Unclear*; #11 retains *Duplicate?* tag (in wrong location though) |
| **group_id non-null** | `undo_log` rows carry a shared group_id | not checked this run |

---

## Programmatic metrics summary

| Metric | Value | vs noise floor [runs 6/7/8 at 773e920] |
|--------|-------|----------------------------------------|
| confident_wrong | **4** | ⚠️ ABOVE ceiling [0,1,3] |
| abstain_recall | **2/5 (40%)** | ❌ BELOW floor min [60%,80%,80%] |
| routing_acc | **9/10 (90%)** | consistent |
| coverage | **10/10 (100%)** ✅ | at ceiling [0,10,10] — A1 primary hypothesis confirmed |
| carbonara_cohesion | true | ✅ |
| baking_cohesion | true | ✅ |
| clusters_merged | false | ✅ |
| metadata_preserved_26 | false | #26 in wrong location |
| generic_name_warning | [] | ✅ "Make Carbonara" + "Bake Cake" both specific |

---

## A1 hypothesis assessment (Run 1 of 2–3)

**Primary hypothesis:** coverage min > 0 across 2+ runs (empty-folder mode eliminated).

- **Coverage = 10/10 ✅** — A1 definitively eliminated the empty-project failure. Both clusters fully and correctly populated. This is the first full coverage since run 7 (which was at the 773e920 baseline, coverage being stochastic). The atomic populate path (create + immediate bulk_move in one handler) fired correctly.

**Trade-off cost:** cw rose from noise-floor range [0–3] to **4**, and abstain_recall dropped below floor to 40%. Two specific issues:
1. **#8 "Mix ingredients" → Bake Cake** — persistent failure (12th+ occurrence). Now that the agent commits to clusters, the coin-flip tasks get dragged in rather than left tagged. A1 made this worse by design: it made the agent bolder about populating clusters.
2. **#11 "Invoice client March" → Freelance: TechCorp API** — novel: agent correctly tagged it *Duplicate?* but moved it anyway instead of leaving it in inbox. First occurrence of this specific failure.
3. **#25 + #26 → area:Work** — same failure as runs 8 and 12; unchanged.

The cw=4 / abstain_recall=40% is a real cost of A1's greater commitment. Whether the coverage gain (from 0 to 10) outweighs the abstain-recall drop (from 80% to 40%) requires 2 more runs to confirm the pattern is systematic rather than noise.

---

## Run narrative

Agent created "Make Carbonara" (area:Personal) and "Bake Cake" (area:Personal), then **immediately moved tasks in** — the atomic populate path fired. All 5 Carbonara tasks and 5 Baking tasks placed correctly. #8 ("Mix ingredients") and #28 ("Check temp midway") also moved to Bake Cake — #28 is a pass (route_or_abstain), but #8 is a coin-flip that should abstain.

#11 ("Invoice client March") placed in Freelance: TechCorp API with the *Duplicate?* tag applied — the agent detected the duplicate but committed to moving it rather than leaving it in Inbox. Novel failure mode introduced by A1's more aggressive commit stance.

#25 and #26 remain persistent wrong-area misses (area:Work).

---

## Summary

- **Ambiguity policy:** abstain on true 50/50 (decided 2026-06-14)
- **Server restarted before run:** yes (A1+B1 live, SHA 64853f4)
- **Overall verdict:** A1 primary hypothesis **confirmed for run 1** — coverage=10/10, both clusters fully populated. Trade-off: cw=4 (above noise-floor ceiling of 3) and abstain_recall=40% (below noise-floor floor of 60%). Need 2 more runs before KEEP/REVERT decision.
- **Regressions vs noise floor:** cw above ceiling; abstain_recall new low. Coverage dramatically improved (0→10). #11 is a novel failure mode.
- **Fixture state after run:** DIRTY — "Make Carbonara" and "Bake Cake" exist (populated); tasks moved to projects; #1,6,27→area:Personal; #30→area:Home; #25,#26→area:Work; #11→project:Freelance with *Duplicate?* tag; #16,#21 inbox *Unclear*. Full reset required before run 17.
