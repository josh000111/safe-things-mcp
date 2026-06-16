# Test 5 — Scoring Verification 2026-06-16 Run 6

**Run 6 — Baseline N=1 of 3. SHA: 773e920 (doc-reorg cleanup; same sorting code as run 5 / 3589494).**
No code changes between run 5 and run 6. Purpose: noise-floor measurement (BACKLOG #3a).

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
| 1 | Collect dry cleaning | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |
| 2 | Add endpoint rate-limit headers | Freelance: TechCorp API | Freelance: TechCorp API | ✅ correct |
| 3 | Preheat oven 180 | new Baking project | inbox (no tag) | ⚠️ under_commit |
| 4 | Conf sofa collection date | Apartment Move | Apartment Move | ✅ correct |
| 5 | Separate egg yolks from whites | Carbonara (abstain also OK) | inbox (no tag) | ⚠️ under_commit |
| 6 | Return library books | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |
| 7 | Chase revised scope doc | Freelance: TechCorp API | Freelance: TechCorp API | ✅ correct |
| 8 | Mix ingredients | Inbox *Ambiguous Home* (coin-flip; any cluster = miss) | inbox *Unclear* | ⚠️ under_commit — wrong tag type (*Unclear* instead of *Ambiguous Home*) |
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
| 26 | Research eco packing materials | Apartment Move (notes+deadline survive) | inbox *Ambiguous Home* | ⚠️ under_commit — over-abstained again (#26 persistent miss) |
| 27 | Tom farewell dinner org | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 28 | Check temp midway | Bake a Cake (abstain also OK; Carbonara = miss) | inbox *Unclear* | ⚠️ under_commit — wrong tag type |
| 29 | Level the cake layers | new Baking project | inbox (no tag) | ⚠️ under_commit |
| 30 | Kitchen reno plan | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |

---

## Scoring criteria

| Criterion | Target | Verdict | Evidence / Notes |
|-----------|--------|---------|-----------------|
| Routing to existing projects | ≥ 9/10 of #2,4,7,9,13,14,17,20,22,26 | ✅ 9/10 (90%) | Miss: #26 over-abstained again |
| Carbonara cluster | all of #5,10,15,19,23 in ONE dish-specific project | ❌ 0/5 | Agent created "Make Carbonara" project but **never moved tasks into it** — all 5 remain in inbox |
| Baking cluster | all of #3,12,18,24,29 in ONE cake-specific project | ❌ 0/5 | Agent created "Bake a Cake" project but **never moved tasks into it** — all 5 remain in inbox |
| Clusters NOT merged | two distinct projects, not one "Cooking" | ✅ n/a | Two distinct empty projects created; not merged |
| Cross-cluster abstain | #8 Inbox *Ambiguous Home*. #28 → Bake a Cake or abstain. #5 → Carbonara or abstain | ⚠️ partial | #8 in inbox *Unclear* (wrong tag, abstain miss); #28 in inbox *Unclear*; #5 in inbox without tag |
| #25 abstain | Inbox *Ambiguous Home* | ✅ | Correctly tagged *Ambiguous Home* |
| Orphan abstains | #1,6,16,21,27,30 *Unclear* or confident Area | ✅ | #1,6 → area:Home; #27 → area:Personal; #30 → area:Home; #16 *Unclear* ✅; #21 *Unclear* ✅ |
| Duplicate detection | #11 Inbox *Duplicate?* | ✅ | Correctly tagged *Duplicate?* |
| Batch approval | one consolidated new-project list before any create | ✅ | Agent presented project list before creating |
| Metadata preserved | #26 notes + deadline 2026-07-15 intact in Apartment Move | ❌ | #26 never moved to Apartment Move |
| `__NEWLY ADDED BY AI__` heading | present in existing projects that got tasks | ⚠️ not checked | Not covered by programmatic scorer |
| Transient routing tags cleaned | no routing tags left on moved tasks | ⚠️ not checked | Needs manual inspection |
| Abstain tags survive cleanup | *Unclear* / *Duplicate?* / *Ambiguous Home* remain | ✅ | All abstain tags present |
| **group_id non-null** | `recent_undo_log` rows carry a shared group_id | ⚠️ not checked | Not queried |

---

## Programmatic scorer metrics (authoritative)

```json
{
  "routing_acc":        { "correct": 9, "total": 10, "pct": 0.9 },
  "confident_wrong":    0,
  "abstain_recall":     { "correct": 4, "total": 5, "pct": 0.8 },
  "carbonara_cohesion": false,
  "baking_cohesion":    false,
  "clusters_merged":    false,
  "cluster_names":      { "carbonara": null, "baking": null },
  "generic_name_warning": [],
  "metadata_preserved_26": false
}
```

**Coverage (manual, BACKLOG #3b not yet in scorer):** 0/10 cooking tasks placed. Agent created both projects but moved zero tasks into them.

**warnings:** (none)

---

## Human judgment

### Key observation: projects created but unpopulated

Unlike run 5 (where zero projects were created), run 6 created "Make Carbonara" and "Bake a Cake" with correct dish-specific names — but the tasks were never moved in. The agent's summary claimed the moves happened, but Things state shows all 10 cooking tasks still in inbox. This is a different failure mode from run 5: the intent was there (project creation succeeded), but the execution of bulk_move failed or was never confirmed.

### #26 persistent over-abstain (3rd occurrence: runs 4, 5, 6)

Task #26 "Research eco packing materials" with bamboo wrap notes and 2026-07-15 deadline is tagged *Ambiguous Home* again. This is unambiguously Apartment Move. Consistent across all three baseline runs — this is a prompt gap, not variance.

### Abstain-recall miss: #8 tagged *Unclear* instead of *Ambiguous Home*

The agent left #8 in inbox with a tag, but the wrong tag type. The scorer counts this as a miss (4/5). This may be LLM variance or a tag-selection issue.

### #1, #6, #30 routed to area:Home (not Personal)

The key allows any existing Area for singletons. Routing to Home instead of Personal is acceptable per the singleton policy.

---

## Summary

- **Server restarted before run:** no (same SHA 773e920; BACKLOG #3a baseline measurement, no code changes)
- **Ambiguity policy:** abstain on true 50/50 (decided 2026-06-14)
- **Overall verdict:** Similar to run 5. Existing-project routing solid (9/10). confident_wrong = 0. Cluster creation partially attempted (projects created, tasks not moved). Coverage = 0/10.
- **Baseline tag:** Run 6 = Baseline N=1
