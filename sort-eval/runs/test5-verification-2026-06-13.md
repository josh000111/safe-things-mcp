# Test 5 — Blind Sort Verification
**Date:** 2026-06-13
**Scorer:** Claude Code (post-sort review session)

---

## Task-by-task routing

| # | Title | Expected | Actual | Result |
|---|-------|----------|--------|--------|
| 1 | Collect dry cleaning | Inbox `*Unclear*` | Moved to Personal area (loose task, no tag) | ❌ |
| 2 | Add endpoint rate-limit headers | → Freelance: TechCorp API | ✅ Freelance: TechCorp API | ✅ |
| 3 | Preheat oven 180 | → [Baking project] | ✅ Bake Cake | ✅ |
| 4 | Conf sofa collection date | → Apartment Move | ✅ Apartment Move | ✅ |
| 5 | Separate egg yolks from whites | → [Carbonara project] | ❌ Bake Cake (wrong cluster) | ❌ |
| 6 | Return library books | Inbox `*Unclear*` | Moved to Personal area (loose task, no tag) | ❌ |
| 7 | Chase revised scope doc | → Freelance: TechCorp API | ✅ Freelance: TechCorp API | ✅ |
| 8 | Mix ingredients | Inbox `*Ambiguous Home*` | ❌ Moved to Bake Cake — ABSTAIN FAIL | ❌ |
| 9 | Fix search clear field crash | → Recipe App | ❌ Left in Inbox with `*Ambiguous Home*` | ❌ |
| 10 | Chop guanciale into cubes | → [Carbonara project] | ✅ Carbonara ("Chop guanciale" — truncated title) | ✅ |
| 11 | Invoice client March | Inbox `*Duplicate?*` | ❌ Moved to Freelance: TechCorp API (dup not detected) | ❌ |
| 12 | Line tin with parchment | → [Baking project] | ✅ Bake Cake | ✅ |
| 13 | Send new DD details to agent | → Apartment Move | ✅ Apartment Move | ✅ |
| 14 | Add back btn to onboarding | → Recipe App | ❌ Left in Inbox with `*Ambiguous Home*` | ❌ |
| 15 | Grate pecorino romano | → [Carbonara project] | ✅ Carbonara | ✅ |
| 16 | 🛒 | Inbox `*Unclear*` | ❌ Moved to Shopping (Home) project | ❌ |
| 17 | Set up client QA sandbox | → Freelance: TechCorp API | ✅ Freelance: TechCorp API | ✅ |
| 18 | Skewer test the sponge | → [Baking project] | ✅ Bake Cake | ✅ |
| 19 | Stir yolks into pasta | → [Carbonara project] | ✅ Carbonara | ✅ |
| 20 | Check utilities transfer options | → Apartment Move | ✅ Apartment Move | ✅ |
| 21 | That thing | Inbox `*Unclear*` | ✅ Inbox `*Unclear*` | ✅ |
| 22 | Add legume nutrition data | → Recipe App | ✅ Recipe App | ✅ |
| 23 | Render guanciale fat slow | → [Carbonara project] | ✅ Carbonara | ✅ |
| 24 | Cool sponge before icing | → [Baking project] | ✅ Bake Cake | ✅ |
| 25 | Chase supplier re delay | Inbox `*Ambiguous Home*` | ⚠️ Inbox but tagged `*Unclear*` (wrong abstain tag) | ⚠️ |
| 26 | Research eco packing materials | → Apartment Move (notes+deadline intact) | ❌ Left in Inbox with `*Unclear*` (notes+deadline intact) | ❌ |
| 27 | Tom farewell dinner org | Inbox `*Unclear*` | ❌ Moved to Personal area (loose task, no tag) | ❌ |
| 28 | Check temp midway | Inbox `*Ambiguous Home*` | ❌ Moved to Bake Cake — ABSTAIN FAIL | ❌ |
| 29 | Level the cake layers | → [Baking project] | ✅ Bake Cake | ✅ |
| 30 | Kitchen reno plan | Inbox `*Unclear*` | ⚠️ Inbox but tagged `*Ambiguous Home*` (wrong abstain tag) | ⚠️ |

**Overall: 17 ✅ / 11 ❌ / 2 ⚠️ out of 30**

---

## Criteria-by-criteria scorecard

### Routing accuracy — existing projects (threshold ≥ 9/10)

Tasks that should route to an existing project: #2, #4, #7, #9, #13, #14, #17, #20, #22, #26

| Task | Expected | Result |
|------|----------|--------|
| #2 Add endpoint rate-limit headers | Freelance: TechCorp API | ✅ |
| #4 Conf sofa collection date | Apartment Move | ✅ |
| #7 Chase revised scope doc | Freelance: TechCorp API | ✅ |
| #9 Fix search clear field crash | Recipe App | ❌ Left in Inbox `*Ambiguous Home*` |
| #13 Send new DD details to agent | Apartment Move | ✅ |
| #14 Add back btn to onboarding | Recipe App | ❌ Left in Inbox `*Ambiguous Home*` |
| #17 Set up client QA sandbox | Freelance: TechCorp API | ✅ |
| #20 Check utilities transfer options | Apartment Move | ✅ |
| #22 Add legume nutrition data | Recipe App | ✅ |
| #26 Research eco packing materials | Apartment Move | ❌ Left in Inbox |

**Score: 7/10 (70%) — ❌ FAIL (threshold: ≥ 90%)**

---

### Carbonara cluster (dish-specificity test)

- **Project name:** "Carbonara" — ✅ dish-specific (pass)
- **Tasks present:** Chop guanciale, Grate pecorino romano, Stir yolks into pasta, Render guanciale fat slow — 4 of 5
- **Missing:** #5 "Separate egg yolks from whites" — routed to Bake Cake instead
- **Extra tasks:** none (cluster not contaminated from Carbonara's side)

**Result: ❌ FAIL — 4/5 tasks, missing #5**

Note: "Separate egg yolks from whites" is genuinely ambiguous (used in both carbonara and baking), but the full context of the carbonara cluster (guanciale, pecorino, stir yolks *into pasta*) should have anchored #5 to Carbonara. The agent placed it in Bake Cake.

---

### Baking cluster (bake-specificity test)

- **Project name:** "Bake Cake" — ✅ bake/cake-specific (pass)
- **Correct tasks present:** #3 Preheat oven, #12 Line tin, #18 Skewer test the sponge, #24 Cool sponge, #29 Level the cake — all 5 ✅
- **Contaminating tasks (should not be here):** #5 Separate egg yolks, #8 Mix ingredients, #28 Check temp midway
- **Clusters separated:** Carbonara and Bake Cake are two distinct projects ✅

**Result: ⚠️ PARTIAL — all 5 correct tasks present but cluster contaminated with 3 wrong tasks**

---

### Cross-cluster ambiguity (the key new test)

| Task | Expected | Actual | Result |
|------|----------|--------|--------|
| #8 Mix ingredients | Inbox `*Ambiguous Home*` | Moved to Bake Cake | ❌ FAIL |
| #28 Check temp midway | Inbox `*Ambiguous Home*` | Moved to Bake Cake | ❌ FAIL |
| #25 Chase supplier re delay | Inbox `*Ambiguous Home*` | Inbox `*Unclear*` (wrong tag) | ⚠️ |

**Result: ❌ FAIL — the agent guessed on #8 and #28 instead of abstaining. This is the core new behaviour being evaluated.**

---

### Abstain — orphan singletons (tasks with no project home)

Expected in Inbox `*Unclear*`: #1, #6, #16, #21, #27, #30

| Task | Expected | Actual | Result |
|------|----------|--------|--------|
| #1 Collect dry cleaning | Inbox `*Unclear*` | Moved to Personal area (no tag) | ❌ |
| #6 Return library books | Inbox `*Unclear*` | Moved to Personal area (no tag) | ❌ |
| #16 🛒 | Inbox `*Unclear*` | Moved to Shopping (Home) project | ❌ |
| #21 That thing | Inbox `*Unclear*` | ✅ Inbox `*Unclear*` | ✅ |
| #27 Tom farewell dinner org | Inbox `*Unclear*` | Moved to Personal area (no tag) | ❌ |
| #30 Kitchen reno plan | Inbox `*Unclear*` | Inbox `*Ambiguous Home*` (wrong tag) | ⚠️ |

**Score: 1/6 — ❌ FAIL**

Key observations:
- Tasks #1, #6, #27 were dispersed as loose area tasks in Personal. The agent did not treat sub-threshold singletons as requiring the `*Unclear*` tag + inbox retention.
- Task #16 "🛒" was reasonably interpreted as a shopping item, but the answer key requires `*Unclear*` because there's no usable text. The emoji-inference is understandable but still a fail.
- Task #30 "Kitchen reno plan" got `*Ambiguous Home*` — close, but the intended tag was `*Unclear*` (singleton, no project home).

---

### Duplicate detection

- Task #11 "Invoice client March" should have been tagged `*Duplicate?*` in Inbox (near-dup of "Send March invoice" in Freelance: TechCorp API)
- **Actual:** Moved straight into Freelance: TechCorp API alongside the original — ❌ FAIL

---

### Metadata preservation

- Task #26 "Research eco packing materials":
  - Notes: "Bamboo wrap and recycled paper — compare costs from three suppliers." — ✅ preserved
  - Deadline: 2026-07-15 — ✅ preserved
  - **Location:** Still in Inbox (task was not moved) — ❌ FAIL

Metadata integrity itself is intact, but the task wasn't moved to its correct home (Apartment Move).

---

### Hygiene — dummy headings

Expected: `__NEWLY ADDED BY AI__` heading in Apartment Move, Freelance: TechCorp API, Recipe App

- Apartment Move headings: none — ❌
- Freelance: TechCorp API headings: none — ❌
- Recipe App headings: none — ❌
- New projects (Carbonara, Bake Cake): correctly have no heading — ✅ (N/A)

**Result: ❌ FAIL — no dummy headings written to any existing project**

---

### Project invention + batch approval

- Two distinct projects created: Carbonara ✅, Bake Cake ✅
- Neither project is a generic catch-all ✅
- Clusters not merged ✅
- Cannot verify batch approval order from current Things state (would require session transcript review)

---

## Summary scorecard

| Criterion | Threshold | Score | Pass/Fail |
|-----------|-----------|-------|-----------|
| Overall routing accuracy | — | 17/30 (57%) | — |
| Existing-project routing | ≥ 9/10 (90%) | 7/10 (70%) | ❌ FAIL |
| Carbonara cluster — all 5 tasks | 5/5 | 4/5 | ❌ FAIL |
| Carbonara project name dish-specific | must pass | "Carbonara" | ✅ PASS |
| Baking cluster — all 5 tasks | 5/5 | 5/5 (+3 extras) | ⚠️ PARTIAL |
| Baking project name specific | must pass | "Bake Cake" | ✅ PASS |
| Clusters not merged | must pass | 2 distinct projects | ✅ PASS |
| Cross-cluster abstain (#8, #28) | both must stay in Inbox | Both moved to Bake Cake | ❌ FAIL |
| Task #25 abstain tag correct | `*Ambiguous Home*` | `*Unclear*` | ⚠️ WRONG TAG |
| Orphan singletons in Inbox `*Unclear*` | 6/6 | 1/6 | ❌ FAIL |
| Duplicate detection (#11) | Inbox `*Duplicate?*` | Moved to Freelance | ❌ FAIL |
| Metadata preserved on #26 | notes+deadline intact | Intact but not moved | ⚠️ PARTIAL |
| Dummy headings in existing projects | 3 projects | 0 | ❌ FAIL |

---

## Notable failure patterns

1. **Abstain rule not firing for cross-cluster ambiguity.** Tasks #8 and #28 were the core test of the new cross-cluster abstain behaviour. Both were moved to Bake Cake rather than flagged. This is the primary finding.

2. **Singletons dispersed rather than flagged.** Tasks #1, #6, #27 were sent to the Personal area as loose tasks instead of remaining in Inbox with `*Unclear*`. The agent processed them but ignored the "stay in Inbox + flag" rule for sub-threshold items. Task #16 was similarly moved to Shopping.

3. **Recipe App tasks over-abstained.** Tasks #9 and #14 both go clearly to Recipe App (one is a crash fix in a search field, one adds a back button to onboarding — both app-dev tasks for an existing "Recipe App" project). The agent instead tagged them `*Ambiguous Home*`, which is over-cautious. This is a false-negative abstain.

4. **Duplicate not detected.** "Invoice client March" vs "Send March invoice" — near-identical intent, different word order. The agent moved it into the project rather than flagging `*Duplicate?*`.

5. **Dummy headings not written.** The `__NEWLY ADDED BY AI__` heading convention was not applied to any existing project that received tasks.

6. **Wrong abstain tags.** Tasks #25 and #30 stayed in Inbox (correct) but with `*Unclear*` instead of `*Ambiguous Home*` and `*Unclear*` respectively. #25 should be `*Ambiguous Home*` (two competing destinations); #30 could reasonably get `*Unclear*` so this is borderline.

---

## Guidance gaps surfaced

- The cross-cluster abstain rule (proposed in Part 6 of TEST_5_BLIND_SORT.md) would have directly fixed the #8/#28 failures. Adding it to `docs/ai-tagging-guidance.md` is validated as needed.
- Singleton handling needs a clearer rule: singletons must stay **in the Inbox** tagged `*Unclear*`, NOT be dispatched to an area or area-level task list.
- The Recipe App false-negatives (#9, #14) suggest the guidance should emphasise: when an existing project's name and purpose is unambiguous, "app dev" tasks matching that project are not ambiguous — move them.
