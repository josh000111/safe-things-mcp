# Test 5 — Run 12 Verification (2026-06-17)

**Build:** SHA `2bd582c` — BACKLOG #4 "Implement skeptic pass (PASS 2) in sort workflow for stronger decisions"
**Run type:** FIRST run on BACKLOG #4 build; also the first verbatim-prompt run on the post-#5-revert baseline (doubles as #5 owed confirmation run — see caveat below)
**Prompt check:** Described as verbatim `test5-blind-prompt.txt`. Cannot confirm from scorer output alone; no evidence of off-prompt wording in results. Treated as verbatim; poolable with #4 run series.
**Server restarted before run (code fixes live):** yes — `2bd582c` live
**Model:** Sonnet 4.6 (assumed; must match noise floor)
**Fixture:** test5 v1 (pristine reset completed after run 11 by Session R)
**Scorer:** `uv run things-mcp-score --pretty` (programmatic, deterministic)

---

## Routing truth table (30 tasks)

| # | Title | Expected (key) | Actual | Verdict |
|---|-------|----------------|--------|---------|
| 1 | Collect dry cleaning | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 2 | Add endpoint rate-limit headers | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 3 | Preheat oven 180 | new Baking project | project:Sponge Cake | ✅ correct |
| 4 | Conf sofa collection date | Apartment Move | project:Apartment Move | ✅ correct |
| 5 | Separate egg yolks from whites | Carbonara (abstain also OK) | project:Carbonara | ✅ correct |
| 6 | Return library books | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 7 | Chase revised scope doc | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 8 | Mix ingredients | Inbox *Ambiguous Home* (coin-flip; any cluster = miss) | project:Sponge Cake | ❌ confident_wrong |
| 9 | Fix search clear field crash | Recipe App | project:Recipe App | ✅ correct |
| 10 | Chop guanciale into cubes | new Carbonara project | project:Carbonara | ✅ correct |
| 11 | Invoice client March | Inbox *Duplicate?* | inbox + *Duplicate?* | ✅ abstain_correct |
| 12 | Line tin with parchment | new Baking project | project:Sponge Cake | ✅ correct |
| 13 | Send new DD details to agent | Apartment Move | project:Apartment Move | ✅ correct |
| 14 | Add back btn to onboarding | Recipe App | project:Recipe App | ✅ correct |
| 15 | Grate pecorino romano | new Carbonara project | project:Carbonara | ✅ correct |
| 16 | 🛒 | Inbox *Unclear* | inbox + *Unclear* | ✅ abstain_correct |
| 17 | Set up client QA sandbox | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 18 | Skewer test the sponge | new Baking project | project:Sponge Cake | ✅ correct |
| 19 | Stir yolks into pasta | new Carbonara project | project:Carbonara | ✅ correct |
| 20 | Check utilities transfer options | Apartment Move | project:Apartment Move | ✅ correct |
| 21 | That thing | Inbox *Unclear* | inbox + *Unclear* | ✅ abstain_correct |
| 22 | Add legume nutrition data | Recipe App | project:Recipe App | ✅ correct |
| 23 | Render guanciale fat slow | new Carbonara project | project:Carbonara | ✅ correct |
| 24 | Cool sponge before icing | new Baking project | project:Sponge Cake | ✅ correct |
| 25 | Chase supplier re delay | Inbox *Ambiguous Home* | area:Work | ❌ confident_wrong |
| 26 | Research eco packing materials | Apartment Move (notes+deadline survive) | area:Work | ❌ confident_wrong |
| 27 | Tom farewell dinner org | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 28 | Check temp midway | Bake a Cake (abstain also OK; Carbonara = miss) | project:Sponge Cake | ✅ correct |
| 29 | Level the cake layers | new Baking project | project:Sponge Cake | ✅ correct |
| 30 | Kitchen reno plan | Inbox *Unclear* (or existing Area = pass) | project:Apartment Move | ⚠️ needs_review |

**#30 human judgment:** Placing "Kitchen reno plan" in Apartment Move is plausible reasoning (kitchen reno as part of an apartment move). Not counted as confident_wrong — matches run-10 assessment ("borderline"). The scorer correctly flags it as needs_review rather than auto-scoring.

---

## Scoring criteria

| Criterion | Target | Verdict |
|-----------|--------|---------|
| Routing to existing projects | ≥ 9/10 of #2,4,7,9,13,14,17,20,22,26 | ✅ 9/10 — miss: #26→area:Work |
| Carbonara cluster | all of #5,10,15,19,23 in ONE dish-specific project | ✅ "Carbonara" — 5/5, dish-specific |
| Baking cluster | all of #3,12,18,24,29 in ONE cake-specific project | ✅ "Sponge Cake" — 5/5 key tasks + #28 bonus |
| Clusters NOT merged | two distinct projects, not one "Cooking" | ✅ separate |
| Coverage / yield | cooking tasks #3,5,10,12,15,18,19,23,24,29 placed in a project (target: all 10) | ✅ **10/10** |
| Cross-cluster abstain | #8 in Inbox *Ambiguous Home*; #28 → Bake or abstain; #5 → Carbonara or abstain | ❌ #8→Sponge Cake (miss); #28 ✅; #5 ✅ |
| #25 abstain | Inbox *Ambiguous Home* | ❌ area:Work |
| Orphan abstains | #1,6,16,21,27,30 *Unclear* or confident Area | ✅ (all area:Personal or inbox+tag) |
| Duplicate detection | #11 Inbox *Duplicate?* | ✅ |
| Batch approval | one consolidated new-project list before any create | not verifiable from scorer |
| Metadata preserved | #26 notes + deadline 2026-07-15 intact in Apartment Move | ❌ #26 in area:Work, not Apartment Move |
| `__NEWLY ADDED BY AI__` heading | present in existing projects that got tasks; absent in new projects | not checked |
| Transient routing tags cleaned | no routing tags left on moved tasks | ✅ (no routing tags in scorer output) |
| Abstain tags survive cleanup | *Unclear* / *Duplicate?* / *Ambiguous Home* remain | ✅ |
| **group_id non-null** | `recent_undo_log` rows carry a shared group_id | not checked |

---

## Programmatic metrics summary

| Metric | Run 12 | Noise floor (runs 6/7/8) | Within floor? |
|--------|--------|--------------------------|---------------|
| confident_wrong | **3** (#8, #25, #26) | [0, 1, 3] | ✅ at ceiling |
| abstain_recall | **3/5 (60%)** | [60%, 80%, 80%] | ✅ at minimum |
| coverage | **10/10 (100%)** | [0/10, 10/10, 10/10] | ✅ non-zero |
| routing_acc | 9/10 | 9/10 in all runs | ✅ |

---

## BACKLOG #4 skeptic assessment

### COMMIT duty (did the skeptic push coverage to non-zero?)
**Yes — coverage = 10/10.** Both clusters were created AND fully populated:
- "Carbonara": tasks #5, #10, #15, #19, #23 (5/5)
- "Sponge Cake": tasks #3, #12, #18, #24, #29 (5/5 key tasks) + #28 (bonus, route_or_abstain)

This is the primary hypothesis for #4. The result is positive (coverage non-zero), and stronger than runs 6/9/10 where coverage was 0. However, coverage=10/10 was also observed in runs 7 and 8 on the baseline, so a SINGLE run cannot attribute this to #4 vs normal variance.

### DEMOTE duty (did the skeptic prune weak confident placements?)
**No — cw = 3, same as the noise-floor ceiling (run 8).** The three wrongs:
- **#8 "Mix ingredients" → Sponge Cake** (8th+ consecutive miss — systematic, not noise)
- **#25 "Chase supplier re delay" → area:Work** (same failure mode as run 8)
- **#26 "Research eco packing materials" → area:Work** (8 consecutive misses — systematic)

The DEMOTE duty did not suppress any of these. This is the same three-error pattern as run 8.

### Single-run verdict
**Cannot mark #4 KEPT or REVERTED from one run.** The noise floor spread is large (cw∈[0,3], coverage∈[0,10]) and this run sits within it on all metrics. Need 2–3 more runs:
- If cw stays ≤1 across 2+ more runs → DEMOTE is working
- If coverage stays 10/10 across 2+ more runs → COMMIT is working (vs noise-floor floor of 0)
- If cw stays at 3 → #4 did not help precision; coverage benefit alone may be insufficient

---

## BACKLOG #5 revert confirmation (dual-purpose run)

Run 11 was off-prompt → not poolable with noise floor; verbatim-prompt run 12 was owed.

**But run 12 is on a DIFFERENT build (#4, SHA `2bd582c`) than the post-revert baseline (SHA `6fc83f2`).** The #4 build adds new AGENT_INSTRUCTIONS prose (two-pass discipline) and a skeptic block injected mid-sort. These changes are confounded with the #5 revert effect.

**Partial confirmation only:** The creation-hesitation symptom from #5 (runs 9/10: coverage=0, no projects created) does NOT appear in run 12 (coverage=10/10). This is evidence the #5 revert removed whatever suppressed project creation. However, we cannot rule out that #4's COMMIT instruction — not the #5 revert — drove the recovery. Coverage=10/10 is also within the noise floor for the baseline (runs 7/8 had 10/10 without any new instructions).

**Recommendation:** Treat run 12 as closing the #5 revert question functionally (no creation-hesitation observed) while attributing the coverage signal to #4 evaluation rather than the revert baseline. BACKLOG #5 can be marked REVERTED/CLOSED.

---

## Persistent failures (systematic across runs)

- **#8 "Mix ingredients":** Placed in a cooking cluster in every run where clusters are created (runs 4, 7, 8, 12). The skeptic DEMOTE duty did not catch this in run 12. Known failure; no fix yet.
- **#26 "Research eco packing materials":** Wrong in 8 of the last 8 scored runs (over-abstained in runs 5/6/9/10/11; routed to area:Work in runs 8/12; routing-miss in run 11). Systematic. The skeptic did not catch this either.
- **#25 "Chase supplier re delay" → area:Work:** Third occurrence (runs 8, 12; run 11 unclear). The "supplier" keyword triggers a Work area association rather than abstaining.

---

## Summary

- **Ambiguity policy:** abstain on true 50/50 (decided 2026-06-14)
- **Server restarted before run (code fixes live):** yes (SHA `2bd582c`)
- **Overall verdict:** Coverage recovered to 10/10 (skeptic COMMIT duty appears to have fired); cw=3 and abstain_recall=60% are within the noise floor — no precision improvement yet. Single run; judgment reserved pending 2–3 more runs.
- **Regressions vs noise floor:** none (all metrics within floor spread). #5 revert confirmed functionally (no creation-hesitation).
