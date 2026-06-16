# Test 5 — Scoring Verification 2026-06-16 Run 8

**Run 8 — Baseline N=3 of 3. SHA: 773e920 (same sorting code as runs 5/6/7).**
No code changes. Purpose: noise-floor measurement (BACKLOG #3a).

> Singleton policy: a confident placement of a singleton into an existing Area is a PASS.
> Ambiguity policy — DECIDED "abstain on true 50/50": **#5** → Carbonara or abstain. **#8** → *Ambiguous Home* required; any cluster/area placement = miss. **#28** → Bake a Cake or abstain.

---

## Routing truth table (30 tasks)

| # | Title | Expected (key) | Actual | Verdict |
|---|-------|----------------|--------|---------|
| 1 | Collect dry cleaning | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 2 | Add endpoint rate-limit headers | Freelance: TechCorp API | Freelance: TechCorp API | ✅ correct |
| 3 | Preheat oven 180 | new Baking project | project:Bake Sponge Cake | ✅ correct |
| 4 | Conf sofa collection date | Apartment Move | Apartment Move | ✅ correct |
| 5 | Separate egg yolks from whites | Carbonara (abstain also OK) | project:Make Carbonara | ✅ correct |
| 6 | Return library books | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 7 | Chase revised scope doc | Freelance: TechCorp API | Freelance: TechCorp API | ✅ correct |
| 8 | Mix ingredients | Inbox *Ambiguous Home* (coin-flip; any cluster = miss) | project:Bake Sponge Cake | ❌ **confident_wrong** (same miss as run 7) |
| 9 | Fix search clear field crash | Recipe App | Recipe App | ✅ correct |
| 10 | Chop guanciale into cubes | new Carbonara project | project:Make Carbonara | ✅ correct |
| 11 | Invoice client March | Inbox *Duplicate?* | inbox *Duplicate?* | ✅ abstain_correct |
| 12 | Line tin with parchment | new Baking project | project:Bake Sponge Cake | ✅ correct |
| 13 | Send new DD details to agent | Apartment Move | Apartment Move | ✅ correct |
| 14 | Add back btn to onboarding | Recipe App | Recipe App | ✅ correct |
| 15 | Grate pecorino romano | new Carbonara project | project:Make Carbonara | ✅ correct |
| 16 | 🛒 | Inbox *Unclear* | inbox *Unclear* | ✅ abstain_correct |
| 17 | Set up client QA sandbox | Freelance: TechCorp API | Freelance: TechCorp API | ✅ correct |
| 18 | Skewer test the sponge | new Baking project | project:Bake Sponge Cake | ✅ correct |
| 19 | Stir yolks into pasta | new Carbonara project | project:Make Carbonara | ✅ correct |
| 20 | Check utilities transfer options | Apartment Move | Apartment Move | ✅ correct |
| 21 | That thing | Inbox *Unclear* | inbox *Unclear* | ✅ abstain_correct |
| 22 | Add legume nutrition data | Recipe App | Recipe App | ✅ correct |
| 23 | Render guanciale fat slow | new Carbonara project | project:Make Carbonara | ✅ correct |
| 24 | Cool sponge before icing | new Baking project | project:Bake Sponge Cake | ✅ correct |
| 25 | Chase supplier re delay | Inbox *Ambiguous Home* | area:Work | ❌ **confident_wrong** — moved to Work area instead of abstaining |
| 26 | Research eco packing materials | Apartment Move (notes+deadline survive) | area:Work | ❌ **confident_wrong** — moved to Work area instead of Apartment Move project |
| 27 | Tom farewell dinner org | Inbox *Unclear* (or existing Area = pass) | area:Personal | ✅ area_pass |
| 28 | Check temp midway | Bake a Cake (abstain also OK; Carbonara = miss) | project:Bake Sponge Cake | ✅ correct |
| 29 | Level the cake layers | new Baking project | project:Bake Sponge Cake | ✅ correct |
| 30 | Kitchen reno plan | Inbox *Unclear* (or existing Area = pass) | inbox *Unclear* | ✅ abstain_correct |

---

## Scoring criteria

| Criterion | Target | Verdict | Evidence / Notes |
|-----------|--------|---------|-----------------|
| Routing to existing projects | ≥ 9/10 of #2,4,7,9,13,14,17,20,22,26 | ✅ 9/10 (90%) | Miss: #26 routed to area:Work instead of Apartment Move project (different mechanism from runs 5/6/7 which over-abstained — this time actively wrong) |
| Carbonara cluster | all of #5,10,15,19,23 in ONE dish-specific project | ✅ 5/5 | "Make Carbonara" — all 5 tasks; dish-specific name ✅ |
| Baking cluster | all of #3,12,18,24,29 in ONE cake-specific project | ✅ 5/5 | "Bake Sponge Cake" — all 5 tasks; cake-specific name ✅ |
| Clusters NOT merged | two distinct projects, not one "Cooking" | ✅ | Two distinct projects |
| Cross-cluster abstain | #8 Inbox *Ambiguous Home*. #28 → Bake a Cake or abstain. | ❌ #8 | #8 placed in Bake Sponge Cake = confident_wrong; #28 → Bake Sponge Cake ✅ |
| #25 abstain | Inbox *Ambiguous Home* | ❌ | Placed in area:Work = confident_wrong |
| Orphan abstains | #1,6,16,21,27,30 *Unclear* or confident Area | ✅ | All correct |
| Duplicate detection | #11 Inbox *Duplicate?* | ✅ | Correctly tagged |
| Batch approval | one consolidated new-project list before any create | ✅ | Agent confirmed batch approval |
| Metadata preserved | #26 notes + deadline 2026-07-15 intact | ❌ | #26 moved to area:Work (wrong destination) |
| `__NEWLY ADDED BY AI__` heading | present in existing projects that got tasks | ⚠️ not checked | Not covered by programmatic scorer |
| Transient routing tags cleaned | no routing tags left on moved tasks | ❌ | Agent left *TechCorp API*, *Personal*, *Make Carbonara*, etc. tags on moved tasks (unusual — not seen in prior runs) |
| Abstain tags survive cleanup | *Unclear* / *Duplicate?* / *Ambiguous Home* remain | ✅ | Abstain tags present where expected |
| **group_id non-null** | `recent_undo_log` rows carry a shared group_id | ⚠️ not checked | Not queried |

---

## Programmatic scorer metrics (authoritative)

```json
{
  "routing_acc":        { "correct": 9, "total": 10, "pct": 0.9 },
  "confident_wrong":    3,
  "abstain_recall":     { "correct": 3, "total": 5, "pct": 0.6 },
  "carbonara_cohesion": true,
  "baking_cohesion":    true,
  "clusters_merged":    false,
  "cluster_names":      { "carbonara": "Make Carbonara", "baking": "Bake Sponge Cake" },
  "generic_name_warning": [],
  "metadata_preserved_26": false
}
```

**Coverage (manual, BACKLOG #3b not yet in scorer):** 10/10 cooking tasks placed (5 in Make Carbonara, 5 in Bake Sponge Cake — not counting #8 which is confident_wrong).

**warnings:** (none)

---

## Human judgment

### confident_wrong = 3 — highest across baseline runs

Three misses:
1. **#8** (persistent): coin-flip "Mix ingredients" placed in baking cluster (same direction as run 7). Agent treats "Mix ingredients" as baking-specific.
2. **#25** (new): "Chase supplier re delay" moved to area:Work instead of abstaining. The "supplier" wording read as work-related. A different failure mode from runs 5/6/7 where #25 was correctly abstained.
3. **#26** (different mechanism): "Research eco packing materials" moved to area:Work instead of Apartment Move project. Prior runs abstained; this run guessed Work area instead. Both are wrong but this is a novel error type.

### Transient routing tag hygiene failure

This run left tags like `*TechCorp API*`, `*Personal*`, `*Make Carbonara*`, `*Bake Sponge Cake*` on all moved tasks. These appear to be routing tags the agent applied but never cleaned up. This behavior differs from runs 5/6/7. Not captured in the programmatic scorer but worth noting as a hygiene regression.

### abstain_recall = 3/5 (60%) — lowest across baseline runs

Both #8 (placed in cluster) and #25 (placed in Work area) are abstain misses. Only #11, #16, #21 correctly abstained.

---

## Summary

- **Server restarted before run:** no (SHA 773e920; BACKLOG #3a baseline measurement)
- **Ambiguity policy:** abstain on true 50/50 (decided 2026-06-14)
- **Overall verdict:** Clusters created and populated (routing solid), but worst abstain performance of the baseline set. cw=3 driven by: #8 coin-flip guessed baking (consistent with run 7), #25 routed to Work area (new), #26 routed to Work area instead of Apartment Move (new mechanism for a persistent miss).
- **Baseline tag:** Run 8 = Baseline N=3
