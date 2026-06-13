# Test 5 — Blind Inbox Sort (True Accuracy Assessment)

> **Why this test exists:** Test 4 was contaminated — the same session that wrote
> the inbox fixture also executed the sort, so the agent had implicit knowledge of
> the intended clusters. This test separates those roles completely.
>
> **The rule:** The fixture setup session and the sorting agent session must be
> **completely separate Claude Code sessions with no shared context.**

---

## Design principles

1. **Blind agent.** The sorting session knows only: "you have a Things inbox, sort
   it." It does not see this document, the answer key, or any cluster names.
2. **Vague titles.** No task title contains a keyword that names its destination
   project. Routing must be purely semantic.
3. **Carbonara specificity test.** A cluster of recipe tasks must route to a
   *specific* project (e.g. "Spaghetti Carbonara") rather than a generic
   "Cooking" or "Recipes" catch-all. This tests whether the agent invents
   meaningfully specific project names.
4. **Cross-cluster ambiguity test.** At least one task could plausibly belong to
   two different new clusters. The correct answer is `*Ambiguous Home*`, not a
   50/50 guess. This tests whether the abstain rule fires as designed.
5. **Sub-threshold cluster.** One task implies a project but stands alone (only
   1 task). Min-cluster-size rule should leave it in Inbox tagged `*Unclear*`.
6. **Metadata preservation.** One task has notes + a deadline. Both must survive
   the move intact.

---

## Roles

| Role | Who | When |
|------|-----|------|
| **Fixture author** | You (or another informed session) | Before the sort session |
| **Sorting agent** | A fresh Claude Code session — no memory of this doc | After fixture is built |
| **Scorer** | You, comparing Things state against the answer key | After the sort session |

---

## Part 1 — Cleanup (run in the CURRENT or a setup session)

### 1a. Delete projects from Test 4

These projects were created by Test 4 and must be removed before building the new fixture:

| Project to delete | UUID |
|-------------------|------|
| Mortgage | UXUPMGgczhP7qJwXC8BmNJ |
| Health & Wellbeing | Qibi1uzMyDY9cHQ9mKaQJN |
| Programming Course | KfmHarYr32BVx6JNL5wDrY |
| Plan Mum's 60th | 4v8uE53ep8i8kdVHuhkZTg |

Use `propose_delete_project` for each, or cancel them via `propose_cancel_project`
if hard-delete is not desired. Confirm that all four are gone with `get_projects`.

Also cancel/delete the stray "MCP Test Project" (VWRpjowj3LnBnEG8Y5KNWr) if still present.

### 1b. Clear the inbox

Run `list_inbox`. Any remaining tasks from Test 4 (abstain-tagged or otherwise)
should be bulk-cancelled via `propose_bulk_cancel`. Confirm inbox is empty.

### 1c. Verify surviving structure

After cleanup, `get_projects` and `get_areas` should show exactly:

**Areas:** Work, Personal, Home, Health, Finance, Learning

**Projects (with their pre-existing tasks — do NOT remove these):**

| Project | Area | Pre-existing tasks |
|---------|------|--------------------|
| Freelance: TechCorp API | Work | "Send March invoice", "Review their OpenAPI spec" |
| Apartment Move | Home | "Hire movers", "Change address with bank" |
| Recipe App | Personal | "Buy domain", "Sketch the onboarding screen" |
| Shopping | Home | (empty) |
| Shopping | standalone | (empty) |

If the pre-existing tasks were lost during Test 4 cleanup, re-add them now via
`propose_add_todo` before proceeding.

---

## Part 2 — Build the fixture (run in the setup session, NOT the sorting session)

Add the following **30 tasks to the Inbox** using `add_inbox_todo`. The titles
are intentionally vague — no task title names its destination.

The answer key is in a **separate file** (`test5-answer-key.md`) which the sorting
session must never see.

### Fixture tasks

```
1.  "Collect dry cleaning"
2.  "Add endpoint rate-limit headers"
3.  "Preheat oven 180"
4.  "Conf sofa collection date"
5.  "Separate egg yolks from whites"
6.  "Return library books"
7.  "Chase revised scope doc"
8.  "Mix ingredients"
9.  "Fix search clear field crash"
10. "Chop guanciale into cubes"
11. "Invoice client March"
12. "Line tin with parchment"
13. "Send new DD details to agent"
14. "Add back btn to onboarding"
15. "Grate pecorino romano"
16. "🛒"
17. "Set up client QA sandbox"
18. "Skewer test the sponge"
19. "Stir yolks into pasta"
20. "Check utilities transfer options"
21. "That thing"
22. "Add legume nutrition data"
23. "Render guanciale fat slow"
24. "Cool sponge before icing"
25. "Chase supplier re delay"
26. "Research eco packing materials"
    [add with notes: "Bamboo wrap and recycled paper — compare costs from three suppliers." and deadline: 2026-07-15]
27. "Tom farewell dinner org"
28. "Check temp midway"
29. "Level the cake layers"
30. "Kitchen reno plan"
```

### Notes for the setup person (do not share with the sorting session)

The expected routing for every task is in `tests-2/test5-answer-key.md`.
Do not show that file, or this document, to the sorting session.
The sorting session receives only the prompt in Part 3 below.

---

## Part 3 — The sorting prompt (paste into the NEW blind session)

> **IMPORTANT:** Open a completely fresh Claude Code session. Do not continue this
> session. The agent must have zero knowledge of this document, the cluster names,
> or the answer key.

Paste this as the opening message of the new session:

---

```
My Things Inbox has gotten out of control — a pile of tasks I've dumped in over
the last few weeks and never sorted. Can you process the whole thing for me?

Read my existing areas and projects first so you know what structure I already
have. Then go through every Inbox task and put it where it belongs — into one
of my existing projects if it fits, or group related tasks into new projects if
a clear cluster exists. You decide how many new projects make sense and what to
call them; show me the proposed new projects in one list and I'll approve them
before you move anything.

Please follow the full tag-first → review → move → cleanup workflow from
docs/ai-tagging-guidance.md — generate a group_id for this run so I can undo
if needed. When you're done, give me a short summary: what went where, what's
still in the Inbox and why, and the group_id.

Working directory: /Users/Shared/things-mcp
Run all Python with: uv run …

Do not read or explore any files in the tests-2/ directory.
```

---

## Part 4 — Answer key

The answer key lives in a completely separate file:

**`tests-2/test5-answer-key.md`**

Open it only AFTER the blind sort session is complete. Never share it with, or
mention it to, the sorting session.

---

## Part 5 — Scoring criteria

Run after the blind session completes. Compare Things state against the answer key.

### Routing accuracy
- **Existing projects:** ≥ 9/10 tasks reach the correct existing project (≥90%) ✅
- **Recipe cluster A:** all 5 related tasks in ONE project; project name is dish-specific (not a generic catch-all) ✅
- **Recipe cluster B:** all 5 related tasks in ONE project; project name is bake-specific (not generic) ✅
- **Clusters not merged:** the two recipe clusters are separate projects ✅
- Full pass/fail rubric for cluster names is in `tests-2/test5-answer-key.md`

### Cross-cluster ambiguity (the key new test)
- "Mix ingredients" and "Check temp midway" remain in Inbox with `*Ambiguous Home*` — NOT moved to either recipe cluster ✅
- "Chase supplier re delay" remains in Inbox with `*Ambiguous Home*` ✅
- **If the agent moved either ambiguous task into a recipe cluster → FAIL** (guessed instead of abstaining)

### Abstain behaviour
- Tasks 22–26, 30 remain in Inbox tagged `*Unclear*` ✅
- Task 27 remains in Inbox tagged `*Duplicate?*` ✅
- Abstain tags survive `cleanup_ai_tags` (persistent, transient=false) ✅

### Project invention + batch approval
- One consolidated approval list presented before any project is created ✅
- Each recipe cluster is exactly 1 project ✅
- No cluster split (e.g. 3 + 2 tasks from one cluster in different projects) ✅
- No over-generalisation (a single generic project swallowing both clusters) ✅

### Metadata
- "Research eco packing materials" lands in Apartment Move with notes and deadline 2026-07-15 intact ✅

### Hygiene
- `__NEWLY ADDED BY AI__` dummy heading in Apartment Move, Freelance: TechCorp API,
  Recipe App (existing projects that received tasks) ✅
- New projects (Carbonara, Baking) do NOT get the heading ✅
- Routing tags cleaned; abstain tags survive ✅
- group_id surfaced in closing summary ✅

---

## Part 6 — Guidance gap: cross-cluster ambiguity within a batch

The existing `docs/ai-tagging-guidance.md` abstain rule (§2) covers "ambiguous
destination — two or more plausible projects/areas." However it does not explicitly
address the case where **both competing destinations are themselves being created
in the same batch** (i.e. two new projects invented in the same run, and one task
could belong to either).

### Proposed addition to ai-tagging-guidance.md §2

Add under "Criteria that trigger abstain":

> **Cross-cluster ambiguity within the batch:** When two new projects are being
> created in the same sort run and a task could plausibly belong to either, apply
> the same 90% confidence threshold. If the task is "slightly more likely" to
> belong to one cluster, that is still below the threshold — apply `*Ambiguous Home*`
> and note the competing clusters in the closing summary. Do NOT pick the slightly
> more likely option; the user owns that call.
>
> *Example:* "Mix the ingredients" in a batch containing both a Carbonara cluster
> and a Baking cluster. Even if you believe "mix" is more baking-adjacent than
> carbonara-adjacent (carbonara technique uses stirring/folding, not mixing), the
> difference is not decisive — flag it.
>
> *When you CAN resolve within-batch ambiguity:* if examining the other tasks in
> the cluster makes the correct assignment clear (e.g. the task immediately follows
> "pipe the carbonara onto the plate" and clearly continues the same recipe step),
> act. The bar for within-batch resolution is the same 90% threshold — use the
> surrounding context as evidence, not as permission to guess.

### Whether to add this now
This is a doc change, not a code change. Flag this for the next documentation
session; do not modify `ai-tagging-guidance.md` during the test run itself.

---

## Pre-flight for the sorting session

Before the blind agent starts sorting, verify:

1. `whoami` → `Test`
2. `uv run pytest -q` → all green
3. `uv run things-mcp --help` → clean exit
4. `health()` → `things_app_running=true`, `state_db_exists=true`,
   `url_scheme_auth_token_set=true`, `applescript_enabled=true`
5. `THINGS_MCP_ALLOW_APPLESCRIPT=1` is set in the session environment
6. `list_inbox` → exactly 30 tasks, no abstain tags on any of them
7. `get_projects` → only the 5 surviving projects (Freelance, Apartment Move,
   Recipe App, Shopping×2); no Test 4 projects remain

---

## Recording results

Create `tests-2/test5-verification-YYYY-MM-DD.md` during or after the blind session.
Record each answer-key item as ✅ / ⚠️ / ❌ with observations.

Pay special attention to:
- **Carbonara project name** (the whole point of the dish-specificity test)
- **Tasks 20 and 21** (the cross-cluster abstain test — this is the new behaviour being evaluated)
- **Any tasks the agent moved that the answer key says should be abstained**
  (these are false positives — the agent was overconfident)
- **Any abstain-tagged tasks that the answer key says should have been moved**
  (false negatives — the agent was underconfident)
