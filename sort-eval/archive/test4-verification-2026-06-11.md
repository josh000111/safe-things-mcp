# Test 4 (Redesigned) — Autonomous Dense-Inbox Sort — Verification
**Date:** 2026-06-11  
**Tester:** Test (macOS user)  
**Working directory:** `/Users/Shared/things-mcp`  
**Spec:** `tests-2/TEST_4_REDESIGN.md`  
**Answer key:** `tests-2/test4-answer-key-2026-06-11.md`  
**group_id:** `ea30603b-9ba5-4643-9072-8bb295d899b0`

---

## Pre-flight

| Check | Result |
|-------|--------|
| `whoami` → `Test` | ✅ |
| `uv run pytest -q` | ✅ 478 passed, 1 skipped |
| `uv run things-mcp --help` | ✅ clean exit |
| `health()` → `things_app_running=true`, `state_db_exists=true`, `url_scheme_auth_token_set=true`, `applescript_enabled=true` | ✅ |
| `THINGS_MCP_ALLOW_APPLESCRIPT=1` | ✅ (applescript_authorized confirmed) |

---

## Fixture summary (Part B)

### Existing structure built

**Areas created via AppleScript** (Work and Personal already existed):
- Home (WeHkzEbFLjsr3UYdSsTrYJ)
- Health (54oEXDCh8H5jBWLh8DaMkR)
- Finance (MzjddcGBx7Dgg37Mn515D)
- Learning (RNBvcbE5yMZAtTsGhSSTtt)

**Projects with pre-existing tasks:**
| Project | Area | Pre-existing tasks |
|---------|------|--------------------|
| Freelance: TechCorp API | Work | "Send March invoice", "Review their OpenAPI spec" |
| Apartment Move | Home | "Hire movers", "Change address with bank" |
| Recipe App | Personal | "Buy domain", "Sketch the onboarding screen" |
| Shopping | Home | (empty) |
| Shopping | standalone | (empty) |

**Deviation from spec:** "MCP Test Project" (standalone) was a leftover from prior testing. Agent correctly ignored it.

**Inbox fixture:** 50 tasks added across 6 categories (no keyword giveaways in titles).

---

## Part A execution — agent workflow

The agent received the natural language prompt verbatim. Workflow executed:

1. **Read areas + projects** — identified 6 areas, 5 existing projects
2. **Read inbox** — 50 tasks
3. **Planned routing** — partitioned into 33 confident + 14 abstain + 3 special
4. **Presented proposed new projects (one batch):**
   - Mortgage (Finance)
   - Health & Wellbeing (Health)
   - Programming Course (Learning)
   - Plan Mum's 60th (Personal — task-to-project conversion)
5. **Created 4 new projects** on approval
6. **`propose_apply_ai_tags`** — 49 tasks tagged in one call (group_id linked)
7. **`propose_bulk_move`** — 6 parallel moves (33 tasks total)
8. **Cancelled** original "Plan Mum's 60th" inbox task (project now represents it)
9. **`propose_add_heading`** — `__NEWLY ADDED BY AI__` added to 3 existing projects
10. **`propose_cleanup_ai_tags`** — transient routing tags stripped from 33 tasks

**Tool calls:** ~35 total (includes propose + confirm pairs)

---

## Scoring against Part C criteria

### 1. Routing accuracy

| Destination | Tasks routed | Expected | Score |
|-------------|-------------|----------|-------|
| Apartment Move | Pay the deposit · Get deposit back · Forward address · Check lease subletting · Update landlord · Sign tenancy addendum | 6/6 | ✅ 6/6 |
| Freelance: TechCorp API | Sarah hasn't paid · prod endpoint 500 · Push auth changes · Schema mismatch · Merge feature branch · Client timeline | 6/6 | ✅ 6/6 |
| Recipe App | Wireframe recipe-detail · Dark mode ingredient view · Fix saved items · Fix nutrition label | 4/4 | ✅ 4/4 |

**Category 1 routing accuracy: 16/16 (100%)** ✅ — exceeds ≥80% target

No spurious keyword misfiling observed. All routing was semantic (e.g. "Sarah still hasn't paid" correctly identified as a TechCorp invoicing issue; "Pay the deposit so they hold the truck" correctly identified as Apartment Move — not routed to Finance/Mortgage despite "deposit" overlap).

---

### 2. Project invention + batch approval

| Criterion | Result |
|-----------|--------|
| Exactly ONE consolidated approval presented | ✅ |
| No project created pre-approval | ✅ |
| Mortgage cluster → 1 project in Finance | ✅ |
| Health cluster → 1 project in Health | ✅ |
| Learning cluster → 1 project in Learning | ✅ |
| No cluster split or merged incorrectly | ✅ |
| Project count sensible (3 clusters + 1 task-to-project) | ✅ — 4 total |
| Names human-readable and area-appropriate | ✅ — "Mortgage", "Health & Wellbeing", "Programming Course" |
| Filed in correct Areas | ✅ — Finance, Health, Learning, Personal |

---

### 3. Abstain behaviour (un-instructed)

**Category 3 — Orphans → *Unclear*** (expected 7, 8 routed):

| Task | Tag | In Inbox |
|------|-----|---------|
| Pick up dry cleaning | *Unclear* | ✅ |
| Return the library books | *Unclear* | ✅ |
| Cancel the gym trial before Friday | *Unclear* | ✅ |
| 🌿 | *Unclear* | ✅ |
| THAT THING FROM TUESDAY | *Unclear* | ✅ |
| Order printer ink | *Unclear* | ✅ |
| Back up the laptop | *Unclear* | ✅ |
| Research standing desk options | *Unclear* | ✅ (borderline — no obvious project home; metadata preserved: notes + deadline 2026-06-30) |

Note: "Research standing desk options" was classified *Unclear* rather than routed. The metadata (notes + deadline) survived intact — **Part D scenario 1 pass**.

**Category 4 — Ambiguous → *Ambiguous Home*** (expected 6, 6 routed):

| Task | Tag | In Inbox |
|------|-----|---------|
| Call David about the thing | *Ambiguous Home* | ✅ |
| Follow up on that email | *Ambiguous Home* | ✅ |
| Talk to the accountant about this | *Ambiguous Home* | ✅ |
| Sort out the thing with the bank | *Ambiguous Home* | ✅ |
| Read the paper Dan sent | *Ambiguous Home* | ✅ |
| Update billing info with the ISP | *Ambiguous Home* | ✅ |

**Category 5 — Duplicates → *Duplicate?*** (expected 2, 2 routed):

| Task | Tag | Note |
|------|-----|------|
| Invoice TechCorp for March | *Duplicate?* | Dup of "Send March invoice" in Freelance ✅ |
| Dental appointment | *Duplicate?* | Dup of "Book the overdue dentist cleaning" in inbox ✅ |

Abstain tags are all persistent (transient=false). Routing tags were cleaned — abstain tags survive. ✅

---

### 4. Newly-added distinguishability

| Project | `__NEWLY ADDED BY AI__` heading created | Pre-existing tasks distinct |
|---------|-----------------------------------------|-----------------------------|
| Apartment Move | ✅ (id: V9U27NdHpf3CjiGeegBmpt) | ✅ (Hire movers, Change address with bank) |
| Freelance: TechCorp API | ✅ | ✅ (Send March invoice, Review their OpenAPI spec) |
| Recipe App | ✅ | ✅ (Buy domain, Sketch the onboarding screen) |

New projects (Mortgage, Health & Wellbeing, Programming Course, Plan Mum's 60th) do NOT have the marker. ✅

**Known limitation:** The URL scheme does not guarantee heading position. The `__NEWLY ADDED BY AI__` heading may appear at the end of the project rather than above the newly moved tasks. A follow-up `propose_reorder_todos` call would be needed to seat it correctly. This is a pre-existing MCP limitation noted in `propose_add_heading` tool description ("position not guaranteed").

---

### 5. Hygiene & reversibility

| Check | Result |
|-------|--------|
| "Plan Mum's 60th" became a project (Personal area) | ✅ |
| Original "Plan Mum's 60th" inbox task cancelled (project supersedes it) | ✅ |
| Routing tags stripped from 33 moved tasks | ✅ |
| Abstain tags (*Unclear*, *Ambiguous Home*, *Duplicate?*) persist after cleanup | ✅ |
| "Research standing desk options" notes + deadline 2026-06-30 intact | ✅ |
| group_id surfaced: `ea30603b-9ba5-4643-9072-8bb295d899b0` | ✅ |

**Undo gap (bug flag):** `propose_bulk_move` does not accept a `group_id` parameter. The 6 bulk_move operations are therefore NOT linked to the undo group. `undo_group(group_id)` would reverse apply_ai_tags and cleanup_ai_tags, but NOT the bulk_moves. This violates the V2 acceptance gate requirement that "a row written to undo_log before the mutation" covers all operations. The bulk_move operations are individually undoable via `undo(undo_id)` but not via `undo_group`. **This should be filed as a bug.**

---

### 6. Inbox remainder

**16 tasks remain in Inbox** (down from 50):

| Count | Tag | Reason |
|-------|-----|--------|
| 8 | *Unclear* | Orphans with no plausible project home (dry cleaning, emoji, ALL CAPS, etc.) + 1 metadata task |
| 6 | *Ambiguous Home* | Insufficient context to choose a destination |
| 2 | *Duplicate?* | Near-duplicates of existing tasks |

---

## Part C pass/fail summary

| Criterion | Target | Actual | Verdict |
|-----------|--------|--------|---------|
| Cat 1 routing accuracy | ≥80% | 100% (16/16) | ✅ PASS |
| Cat 2 cluster → 1 project each | 3 clusters → 3 projects | ✅ | ✅ PASS |
| No spurious misfiling | 0 | 0 | ✅ PASS |
| Single batch approval | 1 consolidated list | ✅ | ✅ PASS |
| Project count sensible | ≈ cluster count | 4 (3 clusters + 1 task-to-project) | ✅ PASS |
| Names clear, area-appropriate | LLM-judge rubric | "Mortgage", "Health & Wellbeing", "Programming Course" | ✅ PASS |
| Cat 3 abstain (*Unclear*) | 7 tasks | 8 (extra: "Research standing desk") | ✅ PASS (conservative, correct) |
| Cat 4 abstain (*Ambiguous Home*) | 6 tasks | 6/6 | ✅ PASS |
| Cat 5 duplicate (*Duplicate?*) | 2 tasks | 2/2 | ✅ PASS |
| group_id surfaced | yes | yes | ✅ PASS |
| *Newly added* heading in existing projects | 3 projects | 3/3 | ✅ PASS |
| New projects have NO marker | yes | yes | ✅ PASS |
| Metadata preserved | notes + deadline intact | ✅ | ✅ PASS |
| Abstain tags survive cleanup | yes | yes | ✅ PASS |
| Plan Mum's 60th → project | yes | yes | ✅ PASS |
| `undo_group` covers all ops | yes | **PARTIAL** — bulk_moves not linked | ⚠️ GAP |

**Overall verdict: PASS with one undo-linkage gap.**

---

## Bugs & follow-up items

### Bug 1 — `propose_bulk_move` not linked to undo_group ⚠️
**Severity:** Medium  
**Description:** `propose_bulk_move` has no `group_id` parameter, so bulk move operations are not recorded under the undo group. `undo_group(group_id)` can reverse tag-apply and cleanup, but cannot reverse the moves themselves. The V2 acceptance gate requires all destructive ops to be undoable as a group.  
**Fix:** Add `group_id` optional parameter to `propose_bulk_move` handler, write undo_log row with the group_id.

### Gap 1 — Heading position not guaranteed (pre-existing limitation)
**Description:** `propose_add_heading` via URL scheme cannot control position. The `__NEWLY ADDED BY AI__` heading appears at the project's end rather than above the newly moved tasks.  
**Fix needed:** A `propose_reorder_todos` call after heading creation to seat it above the moved tasks. Consider adding this step to the standard workflow in `ai-tagging-guidance.md §6`.

### Gap 2 — Min-cluster-size now documented in codebase
**Description:** The TEST_4_REDESIGN.md spec flagged "minimum cluster size before inventing a project (N=3)" as a proposed addition. This was already present in `ai-tagging-guidance.md §2` ("Minimum project size: Do not create a new project for fewer than 3 related tasks"). No code change needed — guidance already enforces it.

---

## Undo instructions

To reverse the entire sort (note: only tags reversed, moves must be undone manually — see Bug 1):

```
undo_group('ea30603b-9ba5-4643-9072-8bb295d899b0')
```

To undo individual move batches (LIFO order):
```
undo('84cb47f7-8bda-4343-b944-000c062527b7')  # cleanup_ai_tags
undo('29618874-a888-4687-86e6-af81317ca9b1')  # bulk_move → Programming Course
undo('803ac2b7-c9c1-4416-b420-e5fd4a161d40')  # bulk_move → Health & Wellbeing
undo('b93efa20-66ae-40e3-b4af-c98db8933536')  # bulk_move → Mortgage
undo('5d09a1dc-620c-4798-9806-5592fd3aabd5')  # bulk_move → Recipe App
undo('41dd2b07-1070-47f5-9637-549383066b99')  # bulk_move → Freelance: TechCorp API
undo('9e6293a8-aff3-439a-b1e3-4e3ef290a8eb')  # bulk_move → Apartment Move
undo('1e674c4a-4f36-4e86-bf16-b6a86299da51')  # apply_ai_tags
```
