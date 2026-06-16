# Test 5 — Scoring Template (copy to test5-verification-<date>.md and fill in)

Score the blind sort's resulting Things state against `test5-answer-key.md`.
Read state first: `list_inbox`, `get_projects`, then `get_project` on every
candidate project. Mark each row ✅ / ❌ / ⚠️ and add a note.

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
| 1 | Collect dry cleaning | Inbox *Unclear* (or existing Area = pass) | | |
| 2 | Add endpoint rate-limit headers | Freelance: TechCorp API | | |
| 3 | Preheat oven 180 | new Baking project | | |
| 4 | Conf sofa collection date | Apartment Move | | |
| 5 | Separate egg yolks from whites | Carbonara (abstain also OK) | | |
| 6 | Return library books | Inbox *Unclear* (or existing Area = pass) | | |
| 7 | Chase revised scope doc | Freelance: TechCorp API | | |
| 8 | Mix ingredients | Inbox *Ambiguous Home* (coin-flip; any cluster = miss) | | |
| 9 | Fix search clear field crash | Recipe App | | |
| 10 | Chop guanciale into cubes | new Carbonara project | | |
| 11 | Invoice client March | Inbox *Duplicate?* | | |
| 12 | Line tin with parchment | new Baking project | | |
| 13 | Send new DD details to agent | Apartment Move | | |
| 14 | Add back btn to onboarding | Recipe App | | |
| 15 | Grate pecorino romano | new Carbonara project | | |
| 16 | 🛒 | Inbox *Unclear* | | |
| 17 | Set up client QA sandbox | Freelance: TechCorp API | | |
| 18 | Skewer test the sponge | new Baking project | | |
| 19 | Stir yolks into pasta | new Carbonara project | | |
| 20 | Check utilities transfer options | Apartment Move | | |
| 21 | That thing | Inbox *Unclear* | | |
| 22 | Add legume nutrition data | Recipe App | | |
| 23 | Render guanciale fat slow | new Carbonara project | | |
| 24 | Cool sponge before icing | new Baking project | | |
| 25 | Chase supplier re delay | Inbox *Ambiguous Home* | | |
| 26 | Research eco packing materials | Apartment Move (notes+deadline survive) | | |
| 27 | Tom farewell dinner org | Inbox *Unclear* (or existing Area = pass) | | |
| 28 | Check temp midway | Bake a Cake (abstain also OK; Carbonara = miss) | | |
| 29 | Level the cake layers | new Baking project | | |
| 30 | Kitchen reno plan | Inbox *Unclear* (or existing Area = pass) | | |

---

## Scoring criteria (fill verdict + evidence)

| Criterion | Target | Verdict |
|-----------|--------|---------|
| Routing to existing projects | ≥ 9/10 of #2,4,7,9,13,14,17,20,22,26 | |
| Carbonara cluster | all of #5,10,15,19,23 in ONE dish-specific project | |
| Baking cluster | all of #3,12,18,24,29 in ONE cake-specific project | |
| Clusters NOT merged | two distinct projects, not one "Cooking" | |
| Coverage / yield | cooking tasks #3,5,10,12,15,18,19,23,24,29 placed in a project (target: all 10) | |
| Cross-cluster abstain | #8 in Inbox *Ambiguous Home* (coin-flip). #28 → Bake a Cake or abstain. #5 → Carbonara or abstain | |
| #25 abstain | Inbox *Ambiguous Home* | |
| Orphan abstains | #1,6,16,21,27,30 *Unclear* or confident Area | |
| Duplicate detection | #11 Inbox *Duplicate?* | |
| Batch approval | one consolidated new-project list before any create | |
| Metadata preserved | #26 notes + deadline 2026-07-15 intact in Apartment Move | |
| `__NEWLY ADDED BY AI__` heading | present in existing projects that got tasks; absent in new projects | |
| Transient routing tags cleaned | no routing tags left on moved tasks | |
| Abstain tags survive cleanup | *Unclear* / *Duplicate?* / *Ambiguous Home* remain | |
| **group_id non-null** | `recent_undo_log` rows for the run carry a shared group_id | |

---

## Summary

- **Ambiguity policy:** abstain on true 50/50 (decided 2026-06-14; see header note)
- **Server restarted before run (code fixes live):** yes / no
- **Overall verdict:**
- **Regressions vs 2026-06-14 run:**
