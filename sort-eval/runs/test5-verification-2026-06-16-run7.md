# Test 5 — Scoring Verification 2026-06-16 Run 7

**Run 7 — Baseline N=2 of 3. SHA: 773e920 (same sorting code as runs 5/6).**
No code changes. Purpose: noise-floor measurement (BACKLOG #3a).

> Singleton policy: a confident placement of a singleton into an existing Area is a PASS.
> Ambiguity policy — DECIDED "abstain on true 50/50": **#5** → Carbonara or abstain. **#8** → *Ambiguous Home* required; any cluster placement = miss. **#28** → Bake a Cake or abstain; Carbonara = miss.

---

## Routing truth table (30 tasks)

| # | Title | Expected (key) | Actual | Verdict |
|---|-------|----------------|--------|---------|
| 1 | Collect dry cleaning | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |
| 2 | Add endpoint rate-limit headers | Freelance: TechCorp API | Freelance: TechCorp API | ✅ correct |
| 3 | Preheat oven 180 | new Baking project | project:Bake Cake | ✅ correct |
| 4 | Conf sofa collection date | Apartment Move | Apartment Move | ✅ correct |
| 5 | Separate egg yolks from whites | Carbonara (abstain also OK) | project:Make Carbonara | ✅ correct |
| 6 | Return library books | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |
| 7 | Chase revised scope doc | Freelance: TechCorp API | Freelance: TechCorp API | ✅ correct |
| 8 | Mix ingredients | Inbox *Ambiguous Home* (coin-flip; any cluster = miss) | project:Bake Cake | ❌ **confident_wrong** — placed in baking cluster instead of abstaining |
| 9 | Fix search clear field crash | Recipe App | Recipe App | ✅ correct |
| 10 | Chop guanciale into cubes | new Carbonara project | project:Make Carbonara | ✅ correct |
| 11 | Invoice client March | Inbox *Duplicate?* | inbox *Duplicate?* | ✅ abstain_correct |
| 12 | Line tin with parchment | new Baking project | project:Bake Cake | ✅ correct |
| 13 | Send new DD details to agent | Apartment Move | Apartment Move | ✅ correct |
| 14 | Add back btn to onboarding | Recipe App | Recipe App | ✅ correct |
| 15 | Grate pecorino romano | new Carbonara project | project:Make Carbonara | ✅ correct |
| 16 | 🛒 | Inbox *Unclear* | inbox *Unclear* | ✅ abstain_correct |
| 17 | Set up client QA sandbox | Freelance: TechCorp API | Freelance: TechCorp API | ✅ correct |
| 18 | Skewer test the sponge | new Baking project | project:Bake Cake | ✅ correct |
| 19 | Stir yolks into pasta | new Carbonara project | project:Make Carbonara | ✅ correct |
| 20 | Check utilities transfer options | Apartment Move | Apartment Move | ✅ correct |
| 21 | That thing | Inbox *Unclear* | inbox *Unclear* | ✅ abstain_correct |
| 22 | Add legume nutrition data | Recipe App | Recipe App | ✅ correct |
| 23 | Render guanciale fat slow | new Carbonara project | project:Make Carbonara | ✅ correct |
| 24 | Cool sponge before icing | new Baking project | project:Bake Cake | ✅ correct |
| 25 | Chase supplier re delay | Inbox *Ambiguous Home* | inbox *Ambiguous Home* | ✅ abstain_correct |
| 26 | Research eco packing materials | Apartment Move (notes+deadline survive) | inbox *Ambiguous Home* | ⚠️ under_commit — #26 persistent over-abstain (4th occurrence) |
| 27 | Tom farewell dinner org | Inbox *Unclear* (or existing Area = pass) | area:Home | ✅ area_pass |
| 28 | Check temp midway | Bake a Cake (abstain also OK; Carbonara = miss) | project:Bake Cake | ✅ correct |
| 29 | Level the cake layers | new Baking project | project:Bake Cake | ✅ correct |
| 30 | Kitchen reno plan | Inbox *Unclear* (or existing Area = pass) | inbox *Ambiguous Home* | ✅ abstain_correct (scorer: in inbox with tag, bonus tag type) |

---

## Scoring criteria

| Criterion | Target | Verdict | Evidence / Notes |
|-----------|--------|---------|-----------------|
| Routing to existing projects | ≥ 9/10 of #2,4,7,9,13,14,17,20,22,26 | ✅ 9/10 (90%) | Miss: #26 over-abstained (persistent) |
| Carbonara cluster | all of #5,10,15,19,23 in ONE dish-specific project | ✅ 5/5 | "Make Carbonara" — all 5 tasks present; dish-specific name ✅ |
| Baking cluster | all of #3,12,18,24,29 in ONE cake-specific project | ✅ 5/5 | "Bake Cake" — all 5 tasks present; cake-specific name ✅ |
| Clusters NOT merged | two distinct projects, not one "Cooking" | ✅ | "Make Carbonara" and "Bake Cake" are distinct |
| Cross-cluster abstain | #8 Inbox *Ambiguous Home*. #28 → Bake a Cake or abstain. #5 → Carbonara or abstain | ❌ #8 | #8 placed in Bake Cake = confident_wrong; #28 → Bake Cake ✅; #5 → Make Carbonara ✅ |
| #25 abstain | Inbox *Ambiguous Home* | ✅ | Correctly tagged *Ambiguous Home* |
| Orphan abstains | #1,6,16,21,27,30 *Unclear* or confident Area | ✅ | #1,6,27 → area:Home; #16,#21 *Unclear*; #30 *Ambiguous Home* (scorer counts as pass) |
| Duplicate detection | #11 Inbox *Duplicate?* | ✅ | Correctly tagged *Duplicate?* |
| Batch approval | one consolidated new-project list before any create | ✅ | Agent confirmed batch approval before creation |
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
  "confident_wrong":    1,
  "abstain_recall":     { "correct": 4, "total": 5, "pct": 0.8 },
  "carbonara_cohesion": true,
  "baking_cohesion":    true,
  "clusters_merged":    false,
  "cluster_names":      { "carbonara": "Make Carbonara", "baking": "Bake Cake" },
  "generic_name_warning": [],
  "metadata_preserved_26": false
}
```

**Coverage (manual, BACKLOG #3b not yet in scorer):** 10/10 cooking tasks placed (5 in Make Carbonara, 5 in Bake Cake — not counting #8 which is confident_wrong).

**warnings:** (none)

---

## Human judgment

### Best routing run to date (clusters fully populated)

Both cooking clusters created with correct dish-specific names and fully populated. Existing-project routing 9/10 (same persistent #26 miss). This is the first run where carbonara_cohesion AND baking_cohesion = true simultaneously.

### confident_wrong = 1: #8 "Mix ingredients" → Bake Cake

The coin-flip task (#8) was confidently placed in the baking project rather than abstained. This is the single confident_wrong for this run. Run 4 also had cw=1 for #8 (placed in Carbonara) — the agent guessed baking this time, Carbonara last time. This is a consistent failure point.

### #26 persistent over-abstain (4th occurrence: runs 4, 5, 6, 7)

"Research eco packing materials" tagged *Ambiguous Home* again. This is not LLM variance — it is a systematic prompt gap that affects every run regardless of cluster creation behavior.

### #8 abstain-recall miss

#8 is in a project (not inbox), so it counts as confident_wrong AND abstain miss simultaneously. abstain_recall = 4/5 (80%).

---

## Summary

- **Server restarted before run:** no (SHA 773e920; BACKLOG #3a baseline measurement)
- **Ambiguity policy:** abstain on true 50/50 (decided 2026-06-14)
- **Overall verdict:** BEST ROUTING RUN — both clusters fully populated with correct names. confident_wrong = 1 (#8 guessed baking). Coverage = 10/10 (including the confident_wrong). #26 persistent over-abstain.
- **Baseline tag:** Run 7 = Baseline N=2
