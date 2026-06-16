# Test 5 — Scoring Verification 2026-06-16

**Run 5 — first run scored by the programmatic scorer (`uv run things-mcp-score`).**
SHA: 3589494 (eval harness live). Scorer JSON is the authoritative source of truth for all numbers.

> Singleton policy (harness): a confident placement of a singleton into an
> existing Area is a PASS even though the key says `*Unclear*`. Only flag
> new-Area creation or a weak/ambiguous Area guess.

> Ambiguity policy — DECIDED "abstain on true 50/50" (runbook §5). Grade the
> three contested tasks as: **#5** → Carbonara expected (abstain also OK), Bake a
> Cake = miss. **#8** → `*Ambiguous Home*` expected (genuine coin-flip), any
> cluster placement = miss. **#28** → Bake a Cake expected (abstain also OK),
> Carbonara = miss.

---

## Routing truth table (30 tasks)

| # | Title | Expected (key) | Actual | Verdict |
|---|-------|----------------|--------|---------|
| 1 | Collect dry cleaning | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 2 | Add endpoint rate-limit headers | Freelance: TechCorp API | Freelance: TechCorp API | ✅ correct |
| 3 | Preheat oven 180 | new Baking project | inbox (no tag) | ⚠️ under_commit |
| 4 | Conf sofa collection date | Apartment Move | Apartment Move | ✅ correct |
| 5 | Separate egg yolks from whites | Carbonara (abstain also OK) | inbox (no tag) | ⚠️ under_commit — missing abstain tag if staying in inbox |
| 6 | Return library books | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 7 | Chase revised scope doc | Freelance: TechCorp API | Freelance: TechCorp API | ✅ correct |
| 8 | Mix ingredients | Inbox *Ambiguous Home* (coin-flip; any cluster = miss) | inbox (no tag) | ⚠️ under_commit — in inbox but missing *Ambiguous Home* tag (abstain MISS) |
| 9 | Fix search clear field crash | Recipe App | Recipe App | ✅ correct |
| 10 | Chop guanciale into cubes | new Carbonara project | inbox (no tag) | ⚠️ under_commit |
| 11 | Invoice client March | Inbox *Duplicate?* | inbox *Duplicate?* | ✅ abstain_correct |
| 12 | Line tin with parchment | new Baking project | inbox (no tag) | ⚠️ under_commit |
| 13 | Send new DD details to agent | Apartment Move | Apartment Move | ✅ correct |
| 14 | Add back btn to onboarding | Recipe App | Recipe App | ✅ correct |
| 15 | Grate pecorino romano | new Carbonara project | inbox (no tag) | ⚠️ under_commit |
| 16 | 🛒 | Inbox *Unclear* | inbox *Unclear* | ✅ abstain_correct |
| 17 | Set up client QA sandbox | Freelance: TechCorp API | Freelance: TechCorp API | ✅ correct |
| 18 | Skewer test the sponge | new Baking project | inbox (no tag) | ⚠️ under_commit |
| 19 | Stir yolks into pasta | new Carbonara project | inbox (no tag) | ⚠️ under_commit |
| 20 | Check utilities transfer options | Apartment Move | Apartment Move | ✅ correct |
| 21 | That thing | Inbox *Unclear* | inbox *Unclear* | ✅ abstain_correct |
| 22 | Add legume nutrition data | Recipe App | Recipe App | ✅ correct |
| 23 | Render guanciale fat slow | new Carbonara project | inbox (no tag) | ⚠️ under_commit |
| 24 | Cool sponge before icing | new Baking project | inbox (no tag) | ⚠️ under_commit |
| 25 | Chase supplier re delay | Inbox *Ambiguous Home* | inbox *Ambiguous Home* | ✅ abstain_correct |
| 26 | Research eco packing materials | Apartment Move (notes+deadline survive) | inbox *Ambiguous Home* | ❌ routing miss — over-abstained again (same as run 4) |
| 27 | Tom farewell dinner org | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 28 | Check temp midway | Bake a Cake (abstain also OK; Carbonara = miss) | inbox (no tag) | ⚠️ under_commit — missing abstain tag if staying in inbox |
| 29 | Level the cake layers | new Baking project | inbox (no tag) | ⚠️ under_commit |
| 30 | Kitchen reno plan | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |

---

## Scoring criteria

| Criterion | Target | Verdict | Evidence / Notes |
|-----------|--------|---------|-----------------|
| Routing to existing projects | ≥ 9/10 of #2,4,7,9,13,14,17,20,22,26 | ✅ 9/10 (90%) | Miss: #26 over-abstained (tagged *Ambiguous Home* in inbox) |
| Carbonara cluster | all of #5,10,15,19,23 in ONE dish-specific project | ❌ 0/5 | No Carbonara project created; all 5 tasks left in inbox untagged |
| Baking cluster | all of #3,12,18,24,29 in ONE cake-specific project | ❌ 0/5 | No Baking project created; all 5 tasks left in inbox untagged |
| Clusters NOT merged | two distinct projects, not one "Cooking" | ✅ n/a | No projects created at all; clusters_merged = false by vacuous truth |
| Cross-cluster abstain | #8 Inbox *Ambiguous Home*. #28 → Bake a Cake or abstain. #5 → Carbonara or abstain | ⚠️ partial | #8 in inbox but no tag (abstain miss); #28 in inbox but no tag; #5 in inbox but no tag — all under_commit not confident_wrong |
| #25 abstain | Inbox *Ambiguous Home* | ✅ | Correctly tagged *Ambiguous Home* |
| Orphan abstains | #1,6,16,21,27,30 *Unclear* or confident Area | ✅ | #1,6,27 → area:Personal (area_pass); #30 → area:Home (area_pass); #16 *Unclear* ✅; #21 *Unclear* ✅ |
| Duplicate detection | #11 Inbox *Duplicate?* | ✅ | Correctly tagged *Duplicate?* |
| Batch approval | one consolidated new-project list before any create | n/a | No new projects created; criterion vacuously satisfied |
| Metadata preserved | #26 notes + deadline 2026-07-15 intact in Apartment Move | ❌ | #26 never moved to Apartment Move; metadata_preserved_26 = false |
| `__NEWLY ADDED BY AI__` heading | present in existing projects that got tasks; absent in new projects | ⚠️ not checked | Not covered by programmatic scorer; needs manual verification via get_project |
| Transient routing tags cleaned | no routing tags left on moved tasks | ⚠️ not checked | Not covered by scorer; visual inspection needed |
| Abstain tags survive cleanup | *Unclear* / *Duplicate?* / *Ambiguous Home* remain | ✅ (partial) | #11, #16, #21, #25 retain tags; #8, #28, #5 never received tags |
| **group_id non-null** | `recent_undo_log` rows for the run carry a shared group_id | ⚠️ not checked | Scorer does not query undo_log; verify manually if needed |

---

## Programmatic scorer metrics (authoritative)

```json
{
  "routing_acc":       { "correct": 9, "total": 10, "pct": 0.9 },
  "confident_wrong":   0,
  "abstain_recall":    { "correct": 4, "total": 5, "pct": 0.8 },
  "carbonara_cohesion": false,
  "baking_cohesion":   false,
  "clusters_merged":   false,
  "cluster_names":     { "carbonara": null, "baking": null },
  "generic_name_warning": [],
  "metadata_preserved_26": false
}
```

**warnings:** (none)

---

## Human judgment

### What changed vs run 4

Run 4 (73c26a0) created two correct new projects (Make Carbonara, Bake Sponge Cake) but had confident_wrong = 2 (#8 placed in Carbonara, #26 over-abstained). This run has **confident_wrong = 0** — the north-star metric — but paid for it with **zero new project creation**. The agent sorted existing-project routing correctly (9/10), handled duplicate and orphan abstains well, but declined to synthesize either cooking cluster.

### Pattern: over-abstained on cluster creation

All 10 Carbonara + Baking tasks left in Inbox without tags. This isn't confident_wrong (no misplacements), but it's a clear gap: the agent detected the clusters (it sorted existing projects correctly and didn't contaminate Recipe App), yet chose not to commit to creating new projects. Likely cause: the `<3-task guard` or the batch-approval flow raised the bar and the agent's confidence threshold shifted too far toward abstention.

### #26 over-abstained (persistent across run 4 and run 5)

Task #26 "Research eco packing materials" is unambiguously Apartment Move — it has notes referencing bamboo wrap and a 2026-07-15 deadline. Yet the agent tagged it *Ambiguous Home* again. This is a prompt gap, not a guard issue. Candidate fix: BACKLOG #5 instruction tuning.

### #8 abstain tag missing

Task #8 "Mix ingredients" is correctly left in Inbox (genuine coin-flip between Carbonara and Baking), but without the *Ambiguous Home* tag. The abstain-recall scorer counts this as a miss (4/5). Tags were left on #25 and #11, so the cleanup step ran — this tag was simply never applied. Minor but worth tracking.

### Abstain-recall improvement

4/5 (80%) vs 1/2 (50%) in run 4. The improvement is real: #25 correctly tagged this run (was confident_wrong in run 4), and the prior confident_wrong misses (#8, #28) are now at worst under_commits rather than harmful placements.

### AI-heading and transient tag hygiene

Not measurable from scorer output alone; would require `get_project` calls on Freelance: TechCorp API, Apartment Move, Recipe App. Deferred.

---

## Summary

- **Server restarted before run (code fixes live):** yes — SHA 3589494 (eval harness)
- **Ambiguity policy:** abstain on true 50/50 (decided 2026-06-14)
- **Overall verdict:** MIXED — north-star metric achieved (confident_wrong = 0, first time ever), but at the cost of zero new project creation. The agent under-committed on both cooking clusters; 10 tasks left unplaced in inbox without tags.
- **Regressions vs run 4:** cluster creation dropped from 2/2 to 0/2; metadata_preserved_26 remains false; #8 tag missing (was also missing in run 4 but as an over-commit, now as an under-commit)
- **Improvements vs run 4:** confident_wrong 2→0 ✅ (north star); abstain_recall 50%→80% ✅; #25 correctly abstained this run (was confident_wrong in run 4)
- **Next BACKLOG:** #4 (router→skeptic) addresses the over-abstention on cluster creation; #5 (instruction tuning) addresses #26 and cluster-creation confidence
