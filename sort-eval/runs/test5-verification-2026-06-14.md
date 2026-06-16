# Test 5 — Blind Sort Verification (Rerun)
**Date:** 2026-06-14  
**Harness:** `test5-blind-harness.md` (corrected rerun)  
**Scored against:** `test5-answer-key.md`

---

## Things State at Scoring Time

### New projects created (2)
| Title | Area | Created |
|-------|------|---------|
| Pasta Carbonara | Personal | 2026-06-14 18:20:50 |
| Bake a Cake | Personal | 2026-06-14 18:20:50 |

### Inbox (5 tasks remaining)
| Title | Tag | Expected |
|-------|-----|----------|
| Invoice client March | `*Duplicate?*` | `*Duplicate?*` ✅ |
| 🛒 | `*Unclear*` | `*Unclear*` ✅ |
| Research eco packing materials | `*Unclear*` | → Apartment Move ❌ |
| Chase supplier re delay | `*Unclear*` | `*Ambiguous Home*` ⚠️ (wrong tag) |
| That thing | `*Unclear*` | `*Unclear*` ✅ |

### Singletons filed to Home area (Anytime, no project)
| Title | Destination | Expected |
|-------|-------------|----------|
| Collect dry cleaning | Home area, Anytime | Inbox `*Unclear*` or existing area ✅ (singleton policy) |
| Return library books | Home area, Anytime | Inbox `*Unclear*` or existing area ✅ (singleton policy) |
| Tom farewell dinner org | Home area, Anytime | Inbox `*Unclear*` or existing area ✅ (singleton policy) |
| Kitchen reno plan | Home area, Anytime | Inbox `*Unclear*` or existing area ✅ (singleton policy) |

> Per the harness note: "treat a confident existing-Area placement of a singleton as a pass." All four went to the existing **Home** area, which is defensible for all four tasks.

---

## Task-by-Task Routing

| # | Title | Actual destination | Expected | Verdict |
|---|-------|-------------------|----------|---------|
| 1 | Collect dry cleaning | Home area (Anytime) | Inbox *Unclear* | ✅ (singleton policy) |
| 2 | Add endpoint rate-limit headers | Freelance: TechCorp API | Freelance: TechCorp API | ✅ |
| 3 | Preheat oven 180 | Bake a Cake | Baking project | ✅ |
| 4 | Conf sofa collection date | Apartment Move | Apartment Move | ✅ |
| 5 | Separate egg yolks from whites | **Bake a Cake** | Carbonara project | ❌ |
| 6 | Return library books | Home area (Anytime) | Inbox *Unclear* | ✅ (singleton policy) |
| 7 | Chase revised scope doc | Freelance: TechCorp API | Freelance: TechCorp API | ✅ |
| 8 | Mix ingredients | **Bake a Cake** | Inbox *Ambiguous Home* | ❌ |
| 9 | Fix search clear field crash | Recipe App | Recipe App | ✅ |
| 10 | Chop guanciale into cubes | Pasta Carbonara | Carbonara project | ✅ |
| 11 | Invoice client March | Inbox *Duplicate?* | Inbox *Duplicate?* | ✅ |
| 12 | Line tin with parchment | Bake a Cake | Baking project | ✅ |
| 13 | Send new DD details to agent | Apartment Move | Apartment Move | ✅ |
| 14 | Add back btn to onboarding | Recipe App | Recipe App | ✅ |
| 15 | Grate pecorino romano | Pasta Carbonara | Carbonara project | ✅ |
| 16 | 🛒 | Inbox *Unclear* | Inbox *Unclear* | ✅ |
| 17 | Set up client QA sandbox | Freelance: TechCorp API | Freelance: TechCorp API | ✅ |
| 18 | Skewer test the sponge | Bake a Cake | Baking project | ✅ |
| 19 | Stir yolks into pasta | Pasta Carbonara | Carbonara project | ✅ |
| 20 | Check utilities transfer options | Apartment Move | Apartment Move | ✅ |
| 21 | That thing | Inbox *Unclear* | Inbox *Unclear* | ✅ |
| 22 | Add legume nutrition data | Recipe App | Recipe App | ✅ |
| 23 | Render guanciale fat slow | Pasta Carbonara | Carbonara project | ✅ |
| 24 | Cool sponge before icing | Bake a Cake | Baking project | ✅ |
| 25 | Chase supplier re delay | Inbox *Unclear* | Inbox *Ambiguous Home* | ⚠️ (right location, wrong tag) |
| 26 | Research eco packing materials | **Inbox *Unclear*** | → Apartment Move | ❌ |
| 27 | Tom farewell dinner org | Home area (Anytime) | Inbox *Unclear* | ✅ (singleton policy) |
| 28 | Check temp midway | **Bake a Cake** | Inbox *Ambiguous Home* | ❌ |
| 29 | Level the cake layers | Bake a Cake | Baking project | ✅ |
| 30 | Kitchen reno plan | Home area (Anytime) | Inbox *Unclear* | ✅ (singleton policy) |

---

## Scoring Criteria

### Routing accuracy (existing projects) — 9/10 = 90% → ✅ PASS
Tasks that should route to existing projects: #2, #4, #7, #9, #13, #14, #17, #20, #22, #26.  
Misses: #26 "Research eco packing materials" left in Inbox instead of Apartment Move.  
Score: 9/10 meets the ≥ 90% threshold.

### Carbonara cluster — ❌ FAIL (4/5 tasks)
| Check | Result |
|-------|--------|
| Project name dish-specific ("Pasta Carbonara") | ✅ |
| Not merged with Baking (separate projects) | ✅ |
| All 5 tasks present (#5, #10, #15, #19, #23) | ❌ — #5 "Separate egg yolks from whites" routed to Bake a Cake instead |

### Baking cluster — ⚠️ PARTIAL (name/separation pass; composition fail)
| Check | Result |
|-------|--------|
| Project name cake/bake-specific ("Bake a Cake") | ✅ |
| Not merged with Carbonara | ✅ |
| Correct 5 tasks (#3, #12, #18, #24, #29) | ✅ all 5 correct tasks present |
| No extra tasks | ❌ — also contains #5 (Carbonara task), #8, #28 (cross-cluster abstains) = 8 tasks total |

### Cross-cluster abstain — ❌ FAIL
| Task | Actual | Expected | Result |
|------|--------|----------|--------|
| #8 Mix ingredients | Bake a Cake | Inbox *Ambiguous Home* | ❌ |
| #28 Check temp midway | Bake a Cake | Inbox *Ambiguous Home* | ❌ |
| #25 Chase supplier re delay | Inbox *Unclear* | Inbox *Ambiguous Home* | ⚠️ (right location, wrong tag) |

This is the primary failure mode identified in the harness: the agent confidently routed both cross-cluster ambiguous tasks into Baking when it should have abstained.

### Abstain — orphans — ✅ PASS
| Task | Disposition | Result |
|------|-------------|--------|
| #1 Collect dry cleaning | Home area, no project | ✅ (singleton policy) |
| #6 Return library books | Home area, no project | ✅ (singleton policy) |
| #16 🛒 | Inbox *Unclear* | ✅ |
| #21 That thing | Inbox *Unclear* | ✅ |
| #27 Tom farewell dinner org | Home area, no project | ✅ (singleton policy) |
| #30 Kitchen reno plan | Home area, no project | ✅ (singleton policy) |

### Duplicate detection — ✅ PASS
"Invoice client March" correctly flagged `*Duplicate?*` in Inbox.

### Batch approval — ⚠️ UNVERIFIABLE FROM STATE
Cannot determine from Things state alone. Would require transcript review. The two projects were created in the same second (18:20:50), consistent with a single batch create, but this cannot confirm the approval flow was used.

### Metadata preservation — ❌ FAIL
"Research eco packing materials" (#26): notes ("Bamboo wrap and recycled paper — compare costs from three suppliers.") and deadline (2026-07-15) are intact in Inbox — but the task was not moved to Apartment Move as required. Preservation of metadata is moot if the task was misrouted.

### Hygiene

| Check | Result |
|-------|--------|
| `__NEWLY ADDED BY AI__` heading in existing projects that received tasks | ❌ — absent from Freelance: TechCorp API, Recipe App, Apartment Move |
| `__NEWLY ADDED BY AI__` heading absent from new projects | ✅ |
| Transient routing tags cleaned from moved tasks | ✅ — no tags remain on any moved task |
| Abstain tags survive cleanup | ✅ — `*Duplicate?*` and `*Unclear*` present in Inbox |
| group_id surfaced on undo log | ❌ — all 2026-06-14 undo log entries show `group_id: null` (same failure as prior run) |

---

## Summary Scorecard

| Criterion | Result |
|-----------|--------|
| New project names (dish/bake-specific) | ✅ PASS |
| Two separate clusters, not merged | ✅ PASS |
| Routing to existing projects (≥ 90%) | ✅ PASS — 9/10 |
| Carbonara cluster composition (5/5 tasks) | ❌ FAIL — 4/5 (#5 misrouted to Baking) |
| Baking cluster composition (correct 5 tasks only) | ❌ FAIL — 3 spurious tasks added (#5, #8, #28) |
| Cross-cluster abstain (#8, #28) | ❌ FAIL — both moved to Baking |
| #25 Chase supplier re delay tag | ⚠️ PARTIAL — right inbox, wrong tag |
| Orphan abstains (#1, #6, #16, #21, #27, #30) | ✅ PASS |
| Duplicate detection (#11) | ✅ PASS |
| Recipe App routing (#9, #14, #22) | ✅ PASS |
| Batch approval flow | ⚠️ UNVERIFIABLE |
| Metadata preservation (#26 notes+deadline) | ❌ FAIL (task not moved) |
| `__NEWLY ADDED BY AI__` heading in existing projects | ❌ FAIL |
| group_id in undo log | ❌ FAIL (null) |

---

## Post-scoring code investigation — were the new instructions live?

**Yes, confirmed live.** This rules out stale-instruction contamination (the harness's CRITICAL risk):

- `src/things_mcp/server.py` last modified **2026-06-14 14:15:48** (the new `instructions=` string).
- Both running `things-mcp` server processes started **2026-06-14 18:16:44 / 18:18:00** — *after* the file edit.
- The run's mutations are timestamped **18:20:50 → 18:22:18**.

A process started at 18:16 loads the file as it stood at 14:15, i.e. the updated instructions. The agent therefore saw BUILD CONTEXT FIRST, CONTRASTIVE DISAMBIGUATION, the `propose_move_under_ai_heading` directive, and "Generate ONE group_id … REQUIRED, not optional." All failures below are **genuine non-compliance with live instructions**, not contamination.

> Superficially, the all-`bulk_move` / null-`group_id` pattern *looks* like the old instructions (the committed fa62ede step 6 used `propose_bulk_move` for everything). The process-start-time check is what distinguishes "old instructions ran" from "new instructions ran and were ignored." It was the latter.

## Root Cause Analysis

Two distinct classes of failure:

**A. Model-judgment failures (instruction-sensitive, probabilistic):**
- **Over-confident cross-cluster routing.** "Mix ingredients" (#8) and "Check temp midway" (#28) were moved to Baking instead of abstaining. CONTRASTIVE DISAMBIGUATION was live and explicitly says "if both competing steps are equally generic, abstain" — the agent did not apply it. (Note: #28 leans baking and #5 "Separate egg yolks" is genuinely 50/50 — see caveats below; the answer key is itself somewhat arbitrary on which generic steps it "assigns" vs. flags.)
- **#26 conservative abstain.** "Research eco packing materials" → Inbox `*Unclear*` instead of Apartment Move. Routing it requires the semantic hop packing → moving; BUILD CONTEXT FIRST should have surfaced the moving-logistics theme but the agent did not connect it. A defensible-but-conservative miss.

**B. Invariant failures (should NOT depend on the model — belong in code):**
- **Missing `__NEWLY ADDED BY AI__` heading.** The agent used `propose_bulk_move` for all moves, including into existing projects, despite the live instruction to use `propose_move_under_ai_heading` for those. The handler (`services/handlers/move_under_heading.py`) exists and works — it simply wasn't called.
- **Null `group_id`.** The agent never supplied a group_id. The code persists it correctly when passed (`bulk_move.py:69,105`; `apply_ai_tags.py:50,79`), so null means the agent omitted it on every call — defeating `undo_group()`.

Both class-B failures recurred across both runs *despite* the instructions explicitly requiring them. Prose is the wrong enforcement layer for invariants; per the project's own principle ("Runtime safety must live in the code"), group_id assignment and the AI-heading marker for existing-project moves should be **code-enforced**, not left to the agent to remember.

## Caveats on the answer key (raised during review)

- **#8 "Mix ingredients"** — genuinely 50/50; the harness itself says abstaining is correct here. Solid miss.
- **#28 "Check temp midway"** — defensible either way: oven temp (cake) or egg-sauce temp (carbonara, to avoid scrambling). The key marks it abstain; the agent's Baking guess is not unreasonable, though still a guess on an ambiguous item.
- **#5 "Separate egg yolks from whites"** — done in BOTH dishes. The key assigns it to Carbonara, which is itself a guess. By the key's own abstain logic this arguably should be `*Ambiguous Home*`. Agent (Baking) and key (Carbonara) are both guessing; neither is clearly "right."
- **#26 "Research eco packing materials"** — notes/deadline never say "moving"; a moderate-confidence routing the key treats as unambiguous.

---

## Remediation implemented (2026-06-14)

The two **invariant** failures (class B) were fixed in code, since prose-level
instructions demonstrably failed to enforce them across two runs.

**New module:** `src/things_mcp/state/sort_session.py` — process-scoped tracking
of the active sort (group_id) and AI-created project UUIDs.

| Fix | Change |
|-----|--------|
| **group_id never null** | `propose_apply_ai_tags` opens a sort session and generates a `group_id` when the agent omits one; `propose_bulk_move` / `propose_move_under_ai_heading` / `propose_cleanup_ai_tags` inherit it; `propose_cleanup_ai_tags` closes the session. One sort → one group, automatically. |
| **`__NEWLY ADDED BY AI__` heading enforced** | During an active sort, `propose_bulk_move` into a pre-existing **user** project is auto-promoted to the `move_under_ai_heading` path (delivers the marker in code). AI-created projects (tracked via `add_project`) and Areas are excluded, so new sort projects never get the marker. |

**Tests:** `tests/test_sort_session.py` (9 new). Full suite **487 passed, 1
skipped**. `move_under_ai_heading` undo round-trip (18 tests) still green — the
inverse path the auto-promote relies on. `things-mcp --help` exits 0; `health()`
returns all required fields.

**Not addressed (by design — judgment, not invariant):** the abstain-vs-guess
behaviour for #8/#28/#5/#26 is instruction/philosophy tuning and depends on a
product decision (strict abstention vs. plausible-guess). No instruction changes
were made pending that decision.

> **Live activation:** the running MCP server (PID started 18:16/18:18) still
> holds the *pre-fix* code. These changes require an MCP server restart to take
> effect in a live sort; they are proven at the unit level only.

---

## Comparison with Prior (Invalid) Run

The prior run (2026-06-13, contaminated) cannot be directly scored. However the key regressions to flag in the rerun vs the new targets:

| Target (harness §scoring) | Rerun outcome |
|--------------------------|---------------|
| Cross-cluster abstain (#8, #28) | ❌ FAIL (guessed Baking for both) |
| Recipe App routing (#9, #14) | ✅ PASS |
| Duplicate detection (#11) | ✅ PASS |
| `__NEWLY ADDED BY AI__` heading | ❌ FAIL (same as before) |
| group_id | ❌ FAIL (same as before) |
| Carbonara cluster fully populated | ❌ FAIL (#5 leaked to Baking) |
