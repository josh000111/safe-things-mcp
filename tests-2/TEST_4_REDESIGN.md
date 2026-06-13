# Test 4 (Redesigned) — Autonomous Dense-Inbox Sort

> **Status:** spec reconciled against the actual `things-mcp` codebase at
> `/Users/Shared/things-mcp` (read `docs/ai-tagging-guidance.md`,
> `src/.../handlers/dummy_heading.py`, and the `tests/handoff-*` runbooks before
> implementing). Earlier draft assumptions that conflicted with the code have been
> corrected — see "Reconciliation notes" at the bottom.

## Why this redesign

The original Test 4 was a *scripted* test: it named the projects to create, dictated every
edge-case rule, and pre-listed the orphan's destination. That tests obedience, not judgment.
The product goal is different:

> An agent + things-mcp that takes a **dense, semi-ambiguous inbox** (~400 tasks from a
> user's first processing session) and sorts it accurately into **existing** lists,
> **inventing new projects** where a real cluster exists, while leaving genuinely
> un-routable tasks visible (and flagged) in the Inbox — with **no per-edge-case
> hand-holding** in the prompt.

The redesign moves intelligence out of the prompt and relies on the MCP's **already-built**
machinery (the Unified Abstain Rule, the tag-first→review→move→cleanup workflow, dummy
headings, `undo_group`). The prompt collapses to what a real user would type.

### The four required changes, and how each lands against the real MCP

1. **Don't name the new projects.** Agent decides count + names. → **Resolved model: one
   batch approval.** The MCP guidance (`ai-tagging-guidance.md §6 Step 2`) mandates explicit
   user approval before *any* new list. So the agent autonomously *designs* the whole project
   set, presents it **once** for a single approval, then executes. Hands-off in spirit,
   compatible with the approval rule. We score project **count** and **naming quality**.
2. **Don't instruct edge-case handling.** → **Already built.** The **Unified Abstain Rule**
   (§1–3) means un-routable/ambiguous tasks are left in the Inbox **tagged** (`*Unclear*`,
   `*Ambiguous Home*`, `*Duplicate?*`), not silently. We don't add new MCP defaults; we
   **verify the abstain behaviour fires without being prompted.**
3. **Vague task titles** — no project name / keyword in the title; routing must be semantic.
4. **Distinguish newly-added tasks** in existing projects. → **Mechanism already exists:**
   the dummy-heading convention (`dummy_heading.py`, format `__NAME__`, uppercase,
   regex `^__[A-Z][A-Z0-9 _\-:]*__$`). Marker label: **`__NEWLY ADDED BY AI__`**.

---

## Part A — The prompt the agent receives

The entire instruction. Minimal and natural. **Do not add steps, project names, group_ids,
tag vocabulary, or edge-case rules** — the agent and MCP supply those.

> My Things Inbox has gotten out of control — a big pile of tasks I've dumped in over the
> last few months and never sorted. Can you process the whole thing for me?
>
> Read my existing areas and projects first so you know what I already have. Then go through
> every Inbox task and put it where it belongs — into one of my existing projects if it fits,
> or group related tasks into new projects. You decide how many new projects make sense and
> what to call them; show me the proposed new projects in one list and I'll approve them in
> one go before you move anything. When you're done, give me a short summary of what you did,
> and tell me what's left in the Inbox and why.

That's it. The one concession to the MCP's approval rule is "show me the proposed new
projects… I'll approve them in one go" — a single batch approval, not per-task or per-project
nagging.

### What the MCP / agent supplies on its own (verify, don't instruct)

These come from `docs/ai-tagging-guidance.md` — the test confirms they happen unprompted:

- **Agent-generated `group_id`.** One UUID for the whole run, passed to every tool, and
  **surfaced to the user at the end** for `undo_group`. (Not MCP-auto-generated, not hidden.)
- **Tag-first → review → move → cleanup workflow** (§6): `propose_apply_ai_tags` (routing +
  abstain tags, transient where appropriate) → `list_ai_tags` review → `propose_bulk_move`
  → `propose_cleanup_ai_tags` (strips only `transient=1` routing tags; abstain tags persist).
- **Unified Abstain Rule** (§1): low-confidence tasks get `*Unclear*` / `*Ambiguous Home*` /
  `*Duplicate?*`, `routing=null`, and stay in the Inbox. One unclear task never blocks the
  batch (§5 partial-execution).
- **Reuse bias** (§6 Step 2): existing lists preferred; new lists only when nothing fits.
- **Newly-added marker:** moved tasks land under a `__NEWLY ADDED BY AI__` dummy heading in
  any *existing* project that already had content. (Orchestration: `propose_add_heading` to
  create the marker, `propose_bulk_move` to move, `propose_reorder_todos` to seat them under
  it — confirm the exact ordering mechanics during implementation.) New projects need no marker.
- **Metadata preservation** on move: notes, tags, due date, deadline, checklist intact.

### Proposed *new* heuristic (NOT yet in the MCP — flag for the implementation session)

- **Minimum cluster size before inventing a project (suggest N=3).** The MCP today has no
  such threshold; its only over-creation guard is the soft abstain rule. If we want to prevent
  singleton-project sprawl on a 400-task inbox, this needs to be **added** (handler logic or
  agent guidance). Until then, the test should observe whether the agent over-fragments.

---

## Part B — Seed dataset (built by the test author before running the prompt)

The prompt is half the test; the other half is a realistic, **labelled** inbox so accuracy is
measurable. Seed it via script with a separate answer key (`expected_destination` +
`expected_abstain_tag` per task) the scorer reads. The agent never sees the key.

> **Environment rules (from `CLAUDE.md`):** run as the **`Test`** macOS user (`whoami` must
> print `Test`, not `joshsmith`). If the main user's real DB is ever touched, run
> `backup_things3.sh` first. AI-tag tools require `THINGS_MCP_ALLOW_APPLESCRIPT=1`.

### Existing structure (so "route to existing" is a real option)

Areas: **Work**, **Personal**, **Home**, **Health**, **Finance**, **Learning**.

Existing projects, each pre-populated with 2–4 *already-present* tasks (needed to test the
newly-added-marker distinguishability):

| Area | Existing project | Pre-existing tasks already inside |
|------|------------------|------------------------------------|
| Work | Freelance: TechCorp API | "Send March invoice", "Review their OpenAPI spec" |
| Home | Apartment Move | "Hire movers", "Change address with bank" |
| Personal | Recipe App | "Buy domain", "Sketch the onboarding screen" |

Include at least one **same-name** pair (e.g. a "Shopping" project inside Area "Home" *and* a
standalone "Shopping" project) to exercise the §7 disambiguation terminology.

### Inbox tasks — calibrated ambiguity, no keyword giveaways

Titles must read like brain-dump fragments and must **not** contain the destination's name.
Categories (with the hidden labels the scorer checks):

1. **Semantic match → existing project** (no shared keyword).
   - `Pay the deposit so they hold the truck` → Apartment Move
   - `Sarah still hasn't paid for last month` → Freelance: TechCorp API
   - `Why does the prod endpoint 500 on empty body?` → Freelance: TechCorp API
   - `Wireframe the recipe-detail page` → Recipe App

2. **New cluster → invent a project** (≥3 related; agent names it; batch-approved).
   - Mortgage: `Compare fixed vs variable rates`, `Dig out last year's tax return for the broker`, `Book the valuation`, `Ask about early-repayment penalties`
   - Health: `Book the overdue dentist cleaning`, `Refill the blood-pressure script`, `Schedule the eye test`, `Find a new GP near the flat`
   - Learning: `Finish the Rust ownership chapter`, `Do the async exercises`, `Set up the project repo for the course`

3. **Genuine orphan → stays in Inbox, tagged `*Unclear*`** (single, unrelated, no cluster).
   - `Pick up dry cleaning`, `Return the library books`, `Cancel the gym trial before Friday`

4. **Ambiguous → stays in Inbox, tagged `*Ambiguous Home*` or `*Unclear*`**.
   - `Call David about the thing`, `Follow up on that email`

5. **Duplicate → tagged `*Duplicate?*`** (dup of an existing or another inbox task).
   - `Invoice TechCorp for March` (dup of existing "Send March invoice")

6. **A task that is really a project** (multi-step) → becomes its own project.
   - `Plan Mum's 60th`

Sizes: **~50–60 hand-labelled tasks** for the measurable run; a **separate ~400-task
generated fixture** (Part E) for the scale/performance run.

---

## Part C — Pass / scoring criteria

Run the Part A prompt against the Part B fixture, then check:

**Routing accuracy**
- ≥ X% of category-1 tasks reach the correct existing project (semantic, not keyword).
- Each category-2 cluster becomes exactly one new project; no split, no merge.
- **No spurious keyword misfiling** (a task saying "rate" must not be dumped into Mortgage).

**Project invention + batch approval**
- Agent presents **one** consolidated list of proposed new projects and waits for a single
  approval — no per-task or per-project nagging, and no project created pre-approval.
- Project count is sensible (≈ number of real clusters; not 1 mega-project, not 15 singletons).
- Names are clear, area-appropriate, human (rubric / LLM-judge); filed in the right Area.

**Abstain behaviour (un-instructed)**
- Category-3/4/5 tasks remain in the Inbox **with the correct abstain tag** (`*Unclear*` /
  `*Ambiguous Home*` / `*Duplicate?*`), `routing=null` — and this happens though the prompt
  never mentions tags, abstain, or Inbox policy.
- The closing summary explains what's left and why; `group_id` is surfaced for undo.

**Newly-added distinguishability**
- Each existing project that received tasks has a `__NEWLY ADDED BY AI__` dummy heading, with
  moved tasks under it and the pre-existing tasks still distinguishable.
- Brand-new projects do **not** get the marker.

**Hygiene & reversibility**
- `Plan Mum's 60th` became a project, not a buried todo.
- Moved tasks kept notes/tags/dates/checklists.
- `cleanup_ai_tags` stripped only `transient=1` routing tags; abstain tags survived.
- `undo_group(group_id)` reverses cleanup → move → tags in LIFO and restores the original
  Inbox count.

**Idempotency**
- Re-running on the sorted state creates no duplicate projects and re-moves nothing.

---

## Part D — Additional real-world scenarios worth testing

Beyond the four required edits (fixture variants / smaller tests):

1. **Rich-metadata tasks** — due dates, deadlines, tags, notes, checklists survive the move.
2. **Already-scheduled items** in Today/Upcoming — dates left alone.
3. **Area-level, project-less tasks** — agent parks at area level instead of over-forcing a project.
4. **Over-fragmentation guard** — near-singletons that look clusterable stay in Inbox (tests the proposed min-cluster rule).
5. **Wrong-project keyword traps** — semantic routing beats string overlap into an existing project.
6. **Todo-vs-project detection** — multi-step "tasks" become projects.
7. **Sequential ordering** — within an invented project with an obvious order, tasks ordered sensibly (`propose_reorder_todos`).
8. **Duplicate detection across scopes** — dups within the inbox *and* against tasks already in existing projects → `*Duplicate?*`.
9. **Noisy titles** — emoji-only, single word (`Dentist`), ALL CAPS, multi-line brain-dumps, a couple non-English. Robustness, not crashes.
10. **Recurring/repeating tasks** — recognised and left alone vs. routed.
11. **Scale & performance (400 run)** — batching, token budget, AppleScript/URL-scheme throughput, plan coherence across 400 items; measure wall-clock, tool-call count, accuracy drift vs. the 60-task run.
12. **Resumability / partial failure** — kill mid-run (or simulate a failed move) and re-issue; resumes without double-creating or double-moving. (`recent_undo_log`, `list_pending_actions` help here.)
13. **Batch-approval UX at scale** — one plan/approval for 400 moves, not 400 confirms.
14. **Summary quality** — skimmable: projects created, counts moved per destination, Inbox leftovers with reasons, the `group_id`.
15. **Empty / trivial inbox** — 0–2 tasks: agent invents nothing.
16. **Same-name destinations** — §7 disambiguation wording ("— in Area 'Home'" vs "— a standalone project") appears in previews/`list_ai_tags`.

---

## Part E — Building the 400-task stress fixture

- Generate from the Part B category templates; parameterise names/objects so titles vary but
  the hidden `expected_destination` / `expected_abstain_tag` is known by construction.
- Keep a **hand-written ambiguous subset (~30)** mixed in — pure templated data is too easy.
- Target mix: ~55% route-to-existing-or-new-cluster, ~25% orphan/ambiguous (Inbox + abstain
  tag), ~10% duplicates, ~10% noise/metadata edge cases.
- Store the answer key separately; the scorer diffs final Things state against it. The agent
  never sees the key, the category labels, or the expected project names.

---

## Test-harness conventions (match the repo's existing style)

The `tests/` folder uses numbered manual-verification runbooks with pass-criterion tables,
recorded in dated `tests/<name>-verification-<YYYY-MM-DD>.md` files, run as the `Test` user
(see `tests/handoff-round6-testing-prompt.md` for the template). The implementation session
should write Test 4 in that format, not as free-form prose. Pre-flight: `whoami`=`Test`,
`uv run pytest`, `uv run things-mcp --help`, `health()`, and `THINGS_MCP_ALLOW_APPLESCRIPT=1`.

---

## Reconciliation notes (what changed after reading the codebase)

| Earlier draft assumption | Codebase reality | Fix applied |
|---|---|---|
| MCP auto-generates `group_id`, hidden from user | Agent generates one UUID, **surfaces it** for `undo_group` (§6 Step 4/9) | Prompt/criteria now expect an agent-generated, surfaced id |
| Orphans **silently** stay in Inbox; bake in new default | **Unified Abstain Rule** already leaves them tagged `*Unclear*`/`*Ambiguous Home*`/`*Duplicate?*` | Reframed as *verify existing behaviour*, not add a default |
| Invent `__ NEWLY ADDED BY AI __` heading | `dummy_heading.py` already defines the convention; format is uppercase `__NAME__` | Label corrected to `__NEWLY ADDED BY AI__` |
| Agent freely creates/names projects, no approval | §6 Step 2 requires **explicit approval** before any new list | **One batch approval** model adopted |
| Min-cluster-size already a guard | No such threshold exists in the MCP | Marked as a **proposed addition**, not an existing feature |
