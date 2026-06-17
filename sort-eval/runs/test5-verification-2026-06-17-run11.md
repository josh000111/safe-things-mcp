# Test 5 — Scoring: Run 11 (2026-06-17)

**⚠️ OFF-PROMPT CONFOUND:** Blind session used "Use things-mcp. Organise my Inbox into the
**right** projects and areas" — canonical prompt says "**correct** projects and areas". The
difference is minimal in meaning but this is NOT verbatim `test5-blind-prompt.txt`. Do NOT
pool this run with the noise floor (runs 6/7/8) or treat it as sufficient to close BACKLOG
#5. A verbatim-prompt confirmation run is still owed.

**SHA at run:** 6fc83f2 (post-#5 revert = 773e920 baseline)
**AGENT_INSTRUCTIONS:** restored to 773e920 baseline (verified `git diff 773e920 -- src/things_mcp/server.py` empty)
**Model:** Sonnet 4.6
**Fixture:** test5 v1 — reset to pristine 30 tasks before run (confirmed by Session R,
2026-06-17; all 30 tasks accounted for in scorer output)
**Server restarted before run:** yes (post-revert)

---

## Routing truth table (30 tasks)

| # | Title | Expected (key) | Actual | Verdict |
|---|-------|----------------|--------|---------|
| 1 | Collect dry cleaning | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |
| 2 | Add endpoint rate-limit headers | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 3 | Preheat oven 180 | new Baking project | inbox (untagged) | ⚠️ under_commit |
| 4 | Conf sofa collection date | Apartment Move | project:Apartment Move | ✅ correct |
| 5 | Separate egg yolks from whites | Carbonara (abstain also OK) | inbox (untagged) | ⚠️ under_commit |
| 6 | Return library books | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |
| 7 | Chase revised scope doc | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 8 | Mix ingredients | Inbox *Ambiguous Home* (coin-flip; any cluster = miss) | inbox (untagged, no *Ambiguous Home*) | ❌ abstain miss |
| 9 | Fix search clear field crash | Recipe App | project:Recipe App | ✅ correct |
| 10 | Chop guanciale into cubes | new Carbonara project | inbox (untagged) | ⚠️ under_commit |
| 11 | Invoice client March | Inbox *Duplicate?* | inbox + *Duplicate?* | ✅ abstain_correct |
| 12 | Line tin with parchment | new Baking project | inbox (untagged) | ⚠️ under_commit |
| 13 | Send new DD details to agent | Apartment Move | project:Apartment Move | ✅ correct |
| 14 | Add back btn to onboarding | Recipe App | project:Recipe App | ✅ correct |
| 15 | Grate pecorino romano | new Carbonara project | inbox (untagged) | ⚠️ under_commit |
| 16 | 🛒 | Inbox *Unclear* | project:Shopping | ❌ **confident_wrong** |
| 17 | Set up client QA sandbox | Freelance: TechCorp API | project:Freelance: TechCorp API | ✅ correct |
| 18 | Skewer test the sponge | new Baking project | inbox (untagged) | ⚠️ under_commit |
| 19 | Stir yolks into pasta | new Carbonara project | inbox (untagged) | ⚠️ under_commit |
| 20 | Check utilities transfer options | Apartment Move | project:Apartment Move | ✅ correct |
| 21 | That thing | Inbox *Unclear* | inbox + *Unclear* | ✅ abstain_correct |
| 22 | Add legume nutrition data | Recipe App | project:Recipe App | ✅ correct |
| 23 | Render guanciale fat slow | new Carbonara project | inbox (untagged) | ⚠️ under_commit |
| 24 | Cool sponge before icing | new Baking project | inbox (untagged) | ⚠️ under_commit |
| 25 | Chase supplier re delay | Inbox *Ambiguous Home* | inbox + *Unclear* (wrong tag) | ❌ abstain miss (wrong tag) |
| 26 | Research eco packing materials | Apartment Move (notes+deadline survive) | inbox + *Unclear* | ❌ under_commit (persistent over-abstain, run 7 of ≥7) |
| 27 | Tom farewell dinner org | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 28 | Check temp midway | Bake a Cake (abstain also OK; Carbonara = miss) | inbox (untagged) | ⚠️ under_commit |
| 29 | Level the cake layers | new Baking project | inbox (untagged) | ⚠️ under_commit |
| 30 | Kitchen reno plan | Inbox *Unclear* (or existing Area = pass) | project:Apartment Move | ⚠️ needs_review (existing project, not new; borderline — same as run 10) |

---

## Scoring criteria

| Criterion | Target | Verdict |
|-----------|--------|---------|
| Routing to existing projects | ≥ 9/10 of #2,4,7,9,13,14,17,20,22,26 | ✅ 9/10 (miss: #26 over-abstained) |
| Carbonara cluster | all of #5,10,15,19,23 in ONE dish-specific project | ❌ no Carbonara project created |
| Baking cluster | all of #3,12,18,24,29 in ONE cake-specific project | ❌ no Baking project created |
| Clusters NOT merged | two distinct projects, not one "Cooking" | N/A (no projects) |
| Coverage / yield | cooking tasks #3,5,10,12,15,18,19,23,24,29 placed | ❌ 0/10 |
| Cross-cluster abstain | #8 → *Ambiguous Home*; #28 → baking or abstain; #5 → carbonara or abstain | ❌ all three untagged in inbox |
| #25 abstain | Inbox *Ambiguous Home* | ❌ in inbox with *Unclear* (wrong tag) |
| Orphan abstains | #1,6,16,21,27,30 *Unclear* or confident Area | ❌ #16 placed in Shopping (cw); #30 → Apartment Move (borderline) |
| Duplicate detection | #11 Inbox *Duplicate?* | ✅ |
| Batch approval | one consolidated new-project list before any create | N/A (no projects created) |
| Metadata preserved | #26 notes + deadline 2026-07-15 intact in Apartment Move | ❌ #26 stayed in Inbox |
| `__NEWLY ADDED BY AI__` heading | present in existing projects that got tasks | not checked |
| Transient routing tags cleaned | no routing tags left on moved tasks | ✅ (none present in scorer output) |
| Abstain tags survive cleanup | *Unclear* / *Duplicate?* / *Ambiguous Home* remain | ✅ (#11 *Duplicate?*, #21 *Unclear* survived) |
| **group_id non-null** | `recent_undo_log` rows carry shared group_id | not checked |

---

## Programmatic metric summary

| Metric | Run 11 | Noise floor [min, med, max] | Inside floor? |
|--------|--------|-----------------------------|---------------|
| confident_wrong | **1** (#16 🛒→Shopping) | [0, 1, 3] | ✅ yes |
| abstain_recall | **2/5 (40%)** (#11, #21 correct; #8, #25, #16 missed) | [3/5, 4/5, 4/5] = [60%, 80%, 80%] | ❌ BELOW minimum |
| coverage | **0/10 (0%)** | [0, 10, 10] | ✅ yes (matches low end) |
| routing_acc | **9/10** | [9/10, 9/10, 9/10] | ✅ yes |

---

## Notable observations

- **#16 "🛒" → Shopping:** The lone emoji task was placed in the existing Shopping project
  rather than abstained. This is the sole confident_wrong. The Shopping project exists as a
  named hook; the agent matched on it. Expected: `*Unclear*` (no parseable text).
- **#26 over-abstained again:** Left in inbox with `*Unclear*` for the 7th+ consecutive run
  (runs 5–11). This is the most persistent systematic failure.
- **#30 "Kitchen reno plan" → Apartment Move:** Same borderline placement seen in run 10.
  Scorer marks `needs_review` — placing a sub-threshold singleton into an *existing* project
  is questionable but not a clean confident_wrong since Apartment Move is a plausible context.
  Not escalated to cw here; treat as a recurring soft miss.
- **Zero clusters created:** No new projects for Carbonara or Baking — same failure mode as
  runs 5, 6, 9, 10. Coverage 0/10 is within the noise floor (runs 6 and 5 also had 0/10)
  but does not constitute recovery evidence for post-#5 revert.
- **abstain_recall 40% is a new low** across all scored runs, pulling BELOW the noise-floor
  minimum of 60%. Primary driver: #16 moved to Shopping (new cw) + #8 and #25 untagged
  (same misses as runs 6 and 9). Caution: this may reflect the off-prompt confound rather
  than a real regression.

---

## Summary

- **Ambiguity policy:** abstain on true 50/50 (decided 2026-06-14)
- **Server restarted before run:** yes
- **Overall verdict:** Weak — zero clusters created (coverage 0/10), abstain_recall 40%
  (new low, below noise floor). However, this run is OFF-PROMPT and therefore not comparable
  to runs 6–10 or the noise floor.
- **Regressions vs noise floor:** abstain_recall 40% < floor min 60%. All other metrics
  within floor.
- **Do NOT pool with noise floor or use to close BACKLOG #5.** A verbatim-prompt run
  (run 12) is required to confirm whether the revert actually recovered coverage.
