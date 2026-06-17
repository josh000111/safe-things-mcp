# things-mcp Sort Quality — Mission Control

**Purpose:** single source of truth for the iterative loop that improves the things-mcp AI
inbox-sort. **Any fresh Claude session can resume from this file alone.** Do not
rely on a long-lived chat session — durable state lives here and in
`eval-ledger.md`.

**Last updated:** 2026-06-17 (Run 12 scored — Session B. FIRST run on BACKLOG #4 build (SHA 2bd582c). coverage=10/10 ✅ (skeptic COMMIT duty fired), cw=3 (at noise-floor ceiling; DEMOTE duty not evident), abstain_recall=3/5 (60%, at noise-floor min). Single run — #4 cannot be judged yet; 2–3 more runs needed. #5 functionally closed (no creation-hesitation). See test5-verification-2026-06-17-run12.md. Prior: BACKLOG #4 two-pass router→skeptic implemented & gates green — Session C.)

---

## North-star metric (DECIDED 2026-06-14)

**Precision-first, NOT strict-answer-key match.** A confidently *wrong* placement
is the only true failure — it erodes user trust and creates manual hunt-for-the-task work for the user.
Abstaining (leaving a task in the Inbox with an explanatory tag) is graceful
degradation, not a failure. An Inbox with 12 tasks left and zero misplacements
beats an empty Inbox with 4 misplacements.

Track three numbers per run:
- **Confident-wrong count** → drive to **0**.
- **Abstain-recall** = of the genuinely ambiguous tasks, % correctly left in the
  Inbox with an abstain tag.
- **Coverage / yield** = of the tasks that DO have a confident home (the
  unambiguous majority + the well-evidenced clusters), % actually placed.

⚠️ **Refinement (2026-06-16): confident-wrong is gameable by inaction.** A sort
that places *nothing* scores confident_wrong = 0 and high abstain-recall — yet is
useless. Run 5 is close to this failure mode (0 clusters created, 10 cluster
tasks left untagged in the Inbox, cw = 0). Precision-first still holds — a wrong
placement is worse than an abstain — but **abstaining has a cost too.** Read the
three numbers together: drive cw→0 *without* letting coverage collapse.

Routing accuracy on the unambiguous majority is secondary (should stay ~95%+).
Rationale + full analysis: `sort-eval/runs/test5-verification-2026-06-14.md`.

---

## The loop (one crank per change)

1. **DEV** (fresh session): read this file → implement the next BACKLOG item
   (delegate to `coder-sonnet`) → run gates (`uv run pytest`,
   `uv run things-mcp --help`, `health()`) → set item status to READY-TO-TEST →
   **commit** so the run pins to a git SHA.
2. **ACTIVATE**: restart the MCP server (Claude Desktop). Confirm new code is live
   (process start time; `sqlite3 <state.db> ".tables"`).
3. **RESET FIXTURE**: restore the pristine 30-task Inbox (see Fixture section);
   remove stray tasks.
4. **BLIND RUN** (fresh session, **NO answer key**): run `test5-blind-prompt.txt`.
5. **SCORE** (fresh session, HAS key): run `uv run things-mcp-score --pretty`;
   fill a copy of `sort-eval/harness/test5-scoring-template.md` →
   `sort-eval/runs/test5-verification-<date>.md`; append one row to
   `sort-eval/harness/eval-ledger.md`.
6. **JUDGE vs the noise floor, NOT vs one prior run.** ✅ Noise floor established
   (BACKLOG #3a, runs 6/7/8, SHA 773e920): cw=[0,1,3], abstain=[60%,80%,80%],
   coverage=[0,10,10]/10. A single before/after run cannot distinguish a real
   effect from sampling noise. Set a BACKLOG item to **KEPT/REVERTED** only when
   the change moves a metric **beyond the noise-floor spread**: cw sustainably=0
   across 2+ runs, or abstain >80%, or coverage min > 0 across all runs.
7. Next crank.

**Rules:** ONE test at a time against the Test Things DB — concurrent
sessions/runs collide on the shared DB and corrupt the fixture (observed: stray
tasks 2026-06-14). Always run write-path work as the `Test` user (`whoami`).

---

## Current system state

- **DB-backed `sort_session`** (group_id + tagged + AI-created-project) — **LIVE &
  smoke-verified 2026-06-14.** Fixes recurring null group_id + missing AI heading
  (root cause: in-memory state across 2 server processes).
- **<3-task project guard** in `propose_add_project` (`member_todo_ids >= 3`
  during a sort) — **LIVE & smoke-verified.**
- Agent files (`~/.claude/agents/`) model aliases fixed.
- ✅ Fix committed (HEAD `73c26a0`) and confirmed live: auto-init on first
  `propose_bulk_move` (BACKLOG #1a). Run 4 (2026-06-15 18:11 UTC) shows
  group_id = "sort-inbox-20260615" across all bulk_move + apply_ai_tags entries.
  **First run with non-null group_id.** Confident-wrong: 2 (best to date).
- ✅ Eval harness (BACKLOG #3) committed (HEAD `3589494`) and live. Run 5
  (2026-06-16) scored programmatically: **confident_wrong = 0**, abstain_recall
  4/5 (80%) — BUT **zero new projects created**, both cooking clusters left
  untagged in the Inbox (#26 over-abstained again; #8 missing its tag). Existing-
  project routing solid (9/10).
- ⚠️ **First-principles finding (2026-06-16): runs 4 and 5 are the SAME build.**
  The only code between them (`73c26a0`→`3589494`) was the read-only eval harness,
  which never executes during a sort; the blind prompt was unchanged. So the
  2-clusters→0 / cw 2→0 swing is **run-to-run LLM variance, not a regression.**
  Consequence: the programmatic *scorer* is deterministic, but a **single run is
  NOT a deterministic baseline** of the system.
- ✅ **Noise-floor baseline ESTABLISHED (2026-06-16, BACKLOG #3a DONE).**
  Runs 6/7/8 — same SHA `773e920`, no code changes, pristine fixture reset each time.

  | Metric | min | median | max |
  |--------|-----|--------|-----|
  | **confident_wrong** | 0 | 1 | 3 |
  | **abstain_recall** | 3/5 (60%) | 4/5 (80%) | 4/5 (80%) |
  | **coverage** (cooking tasks placed) | 0/10 | 10/10 | 10/10 |

  **Interpretation:** Run-to-run variance is LARGE. A change must move a metric
  *outside* this spread across multiple runs to count as a real effect:
  - **cw**: single-run result of 0–3 is within noise; improvement requires
    sustained cw=0 across k≥2 runs, or driving below 0 (impossible, so the
    practical bar is: cw=0 in 2/3 runs is a candidate improvement).
  - **abstain_recall**: single-run 60–80% is noise; >80% sustained is a true gain.
  - **coverage**: 0–10/10 within noise; a change is real only when coverage is
    non-zero across ALL runs (min > 0).
  - **Systematic findings** (appeared in every run, not variance):
    - #26 "Research eco packing materials" fails consistently — over-abstained (runs 5/6/7)
      or wrong area (run 8). Fix target: BACKLOG #5 instruction tuning.
    - #8 "Mix ingredients" consistently not abstained (guessed baking in runs 7 and 8).

- ⚠️ **Run 9 (2026-06-16, SHA `f2c23b6`, first #5 test):** coverage=0/10 — the agent created **no new projects** (worse than run-6 which created empty projects). cw=0 ✅, abstain_recall=4/5 (80%) ✅. #5 instruction "COMMIT FULLY TO CLUSTERS YOU CREATE" did not visibly fire. Within noise-floor variance (run-6 also coverage=0), so this single run cannot confirm a regression.
- ❌ **Run 10 (2026-06-16, SHA `f2c23b6`, second #5 test):** coverage=0/10 again — **NO projects created for the second consecutive run**. cw=0 ✅, abstain_recall=4/5 (80%) ✅. Two zeros confirm the instruction did not fire. This meets the REVERT CANDIDATE threshold (coverage min=0 across BOTH #5 runs, which is below the noise-floor bar of min>0 across all runs). Novel: #30 "Kitchen reno plan" placed in project:Apartment Move instead of staying in Inbox/*Unclear* or being routed to an area. **#5 declared REVERT CANDIDATE.**
- ⚠️ **Run 11 (2026-06-17, SHA `6fc83f2`, post-#5-revert): OFF-PROMPT** (used "right projects and areas" vs canonical "correct"). coverage=0/10 — no cluster projects created, within noise floor but no recovery signal. cw=1 (#16 🛒→Shopping). abstain_recall=2/5 (40%) — new low, below noise-floor minimum of 60%; likely a prompt-wording artifact but cannot rule out a true regression. #26 over-abstained (7+ consecutive runs). #30→Apartment Move (borderline, same as run-10). Not pooled with noise floor.
- 📊 **Run 12 (2026-06-17, SHA `2bd582c`, BACKLOG #4 build, verbatim prompt):** coverage=10/10 ✅ — both clusters created AND fully populated ("Carbonara" 5 tasks, "Sponge Cake" 5+1 tasks). cw=3 (#8→Sponge Cake persistent, #25/#26→area:Work). abstain_recall=3/5 (60%). All metrics within noise-floor spread — single run; #4 cannot be judged yet. Skeptic COMMIT duty appears to have fired (contrast: runs 9/10 coverage=0). DEMOTE duty not evident (cw at noise-floor ceiling). #5 revert functionally confirmed (no creation-hesitation). See test5-verification-2026-06-17-run12.md.
- 📂 Docs reorganized 2026-06-16 into `sort-eval/{harness,runs,archive}`
  (was the flat `tests-2/`). See `sort-eval/README.md`. Scorer key path updated
  in `scorer.py`.

---

## BACKLOG #4 — two-pass router→skeptic (FIRST RUN SCORED — run 12, 2026-06-17)

**Status:** committed (SHA `2bd582c`), live. Run 12 scored: coverage=10/10 ✅ (COMMIT duty fired — both clusters created and populated), cw=3 / abstain_recall=60% (at noise-floor ceiling/min; DEMOTE duty not evident). Single run — CANNOT YET JUDGE. 2–3 more runs required to confirm whether coverage is sustained and whether cw improves. Gates green: `uv run pytest` 532 passed / 1 skipped, `--help` exit 0, `health()` returns all required fields.

**Design rationale (why this is "architecture", not a repeat of #5):** the MCP server
cannot spawn a second LLM, so the skeptic is a *self-administered* second pass by the
same blind Sonnet agent. The only two channels are (1) `AGENT_INSTRUCTIONS` (read once
at session start — attention decays, which is why #5's front-loaded exhortation didn't
fire) and (2) **tool-response text** (high-salience, injected mid-workflow). #4 uses
BOTH: prose defines the two-pass discipline, and a structured `skeptic_review` block is
attached to the `propose_apply_ai_tags` RESPONSE so the discipline is re-surfaced right
before the irreversible move.

**The skeptic has TWO symmetric duties** (this is what guards coverage):
- **DEMOTE** (precision → cw to 0): any confident placement whose evidence can't be
  named in one phrase → demote to an abstain tag.
- **COMMIT** (coverage → prevents the run-6/9/10 collapse): any ≥3-task cluster sharing
  specific vocabulary left untagged / scattered as *Unclear* is *under*-commitment —
  create the project and route it. Over-abstaining is explicitly framed as a failure.

**Files changed (uncommitted):**
- `src/things_mcp/server.py` — AGENT_INSTRUCTIONS: new TWO-PASS DISCIPLINE paragraph +
  new mandatory SKEPTIC step in SORT WORKFLOW (steps renumbered 1..9).
- `src/things_mcp/sort_skeptic.py` (new) — pure `build_skeptic_review(items) -> dict`,
  no I/O, fully unit-tested.
- `src/things_mcp/tools/propose.py` — `propose_apply_ai_tags` attaches `skeptic_review`
  to its return dict. Purely additive: no mutation behaviour changes, no write-path
  touch, no new V2 gate (logs/mutates nothing).
- `tests/test_sort_skeptic.py` (new) — 7 pure tests.

**Scope note:** the skeptic block is injected at the `propose_apply_ai_tags` checkpoint
ONLY (the natural point after a draft plan but before the move). Reinforcing it on
`propose_bulk_move` too is a possible follow-up if coverage still collapses, deliberately
left out to keep a clean signal vs. the noise floor.

**NEXT (human):** commit (joshsmith — `.git` not writable by Test) → restart the MCP
server (Claude Desktop) → confirm new code live (process start time) → Session R fixture
reset → Session A blind run. Judge against the noise floor (runs 6/7/8), not one prior run.

---

## BACKLOG #3 — what shipped (KEPT — programmatic scorer in use)

Programmatic eval harness, all unit-tested + gates green (pytest 521 passed/1 skipped, ruff clean, `--help` ok). **Committed `3589494`; KEPT** — first programmatic score was run 5 (2026-06-16).

- `sort-eval/harness/test5-key.json` — canonical machine-readable key. **Reconciles the authoritative `test5-scoring-template.md` over 3 stale-number bugs in `test5-answer-key.md`** (the markdown's "New projects expected" cluster lists, its "Routing accuracy: 1–9, 29" set, and its "Task 29" metadata check all use wrong task numbers; correct values live in the per-task routing table + scoring template). The answer-key markdown should be corrected separately.
- `src/things_mcp/eval/scorer.py` — pure `score(key, states) → JSON` (decoupled from Things, unit-tested) + `collect_live_states()` live adapter + `things-mcp-score` CLI.
- `src/things_mcp/eval/fixture_reset.py` — pure `plan_reset(...)` (diagnosis + deterministic interleaved shuffle order) + `things-mcp-fixture-reset` dry-run CLI. `--apply` is hard-guarded to refuse unless `whoami == Test`, and currently prints "execute manually per Fixture procedure" (live apply intentionally out of scope this crank).
- `tests/test_eval_scorer.py`, `tests/test_eval_fixture_reset.py` — 20 tests on synthetic state.
- `pyproject.toml` — 2 new console scripts.

**Scoring-policy decisions baked in (review when scoring next run):**
- `confident-wrong` (the drive-to-0 metric) = any task placed in a project/area when the key expects a different project, the wrong cluster, or an abstain. Inbox under-commit is NOT confident-wrong.
- `abstain-recall` denominator = the 5 strict-abstain tasks only {#8, #11, #16, #21, #25}. The "abstain-or-area" tasks (#1,6,27,30) are scored on a separate axis (inbox OR confident existing Area = pass) and `route_or_abstain` (#5,#28) on the cluster axis — neither counts toward abstain-recall. This makes the denominator stable (prior manual runs drifted: "low"/"1/3"/"1/2").
- Cluster name specificity judged by a generic-name denylist + cohesion + not-merged, since new-project names are non-deterministic.

Smoke-run against the current (un-reset run-4) live state gave routing 9/10, confident_wrong 1, abstain_recall 3/5 — differs from the manual run-4 score (cw 2, abstain 1/2), which is the scorer drift this item removes.

## Backlog (ordered)

| # | Change | Type | Dev model | Status | Hypothesis (metric it should move) |
|---|--------|------|-----------|--------|-----------------------------------|
| 1 | group_id DB-persistence + AI-heading robustness | code invariant | — | DONE — live (7bb8853); bypass gap discovered (see #1a) | group_id non-null 100%; heading present 100% |
| 1a | Auto-init sort session on first `propose_bulk_move` if none active | code invariant | — | DONE — KEPT (73c26a0); group_id non-null confirmed run 4 | closed bypass gap; group_id now non-null across all bulk_moves |
| 2 | <3-task project guard | code invariant | — | DONE — live; not triggered (0 new projects in run 3) | kills spurious sub-3 projects (e.g. Eco Packaging) |
| 3 | Eval harness: programmatic scorer (state vs key → JSON) + scripted fixture reset | tooling | — | **KEPT** (3589494; first programmatic score = run 5 2026-06-16) | makes N≥5 runs cheap; removes scorer drift; fixes stray-task problem |
| **3a** | **Noise-floor baseline: run the CURRENT build k≥3× (no code change) and record the spread of cw / abstain-recall / coverage** | **measurement** | — | **DONE (2026-06-16, runs 6/7/8, SHA 773e920): cw=[0,1,3], abstain=[60%,80%,80%], coverage=[0,10,10]/10** | establishes how big an effect must be to count as real; converts single runs from "anecdote" to "signal" |
| **3b** | **Add coverage/yield metric to the scorer** (so abstaining isn't free; see north-star refinement) | **code (scorer)** | Sonnet 4.6 | **READY-TO-TEST** | makes "placed nothing" score badly; closes the gameable-by-inaction hole |
| **3c** | **Log rejected `propose_add_project` attempts** (guard returns a dict, writes nothing) | **code (observability)** | Sonnet 4.6 | **READY-TO-TEST** | distinguishes "agent gave up clustering" from "agent never tried" — currently untraceable post-hoc |
| 4 | Two-pass router→skeptic abstention | architecture | **Opus 4.8** | **READY-TO-TEST** (Session C 2026-06-17, uncommitted) — see #4 detail below | confident-wrong → 0 **without** coverage collapse (skeptic DEMOTEs weak placements *and* COMMITs under-served ≥3 clusters) |
| 5 | Abstain-vs-guess instruction tuning — **re-scope toward *committing* to well-evidenced clusters** (#5/#8/#26/#28) | prose | **Opus 4.8** | **REVERTED & CLOSED — wrong failure mode + suspected creation-hesitation; coverage 0/10 in runs 9+10. Prose (SHA f2c23b6) backed out; AGENT_INSTRUCTIONS restored to 773e920 baseline. Run 11 OFF-PROMPT (confound). Run 12 (2026-06-17, SHA 2bd582c, #4 build, verbatim): coverage=10/10, cw=3, abstain_recall=60% — no creation-hesitation observed. Revert functionally confirmed. #5 CLOSED.** | recover cluster coverage without raising confident-wrong |
| 6 | Standardize `validation_error` shape (raise vs dict) | cleanup | Sonnet 4.6 | TODO | consistency with rest of propose layer |

---

## Fixture

**Pristine** = 30 test tasks in Inbox (canonical list: `test5-answer-key.md` /
`test5-blind-harness.md`), original projects in pre-test state, no AI-created
projects, tasks interleaved so no two tasks from the same cluster are adjacent.

**Current state (2026-06-17): NEEDS RESET — run 12 complete.**
Run 12 (SHA `2bd582c`) used the fixture. Must reset before run 13:
projects "Carbonara" + "Sponge Cake" exist; tasks moved out of Inbox; abstain tags present.
Follow Fixture reset procedure; interleave shuffle after restoring all 30 tasks to Inbox.

**Fixture reset procedure (for future runs):**

1. Call `recent_undo_log()` and identify the bulk_moves + bulk_updates from the
   completed run. Note their undo_ids.
2. Undo each entry **newest-first** via `undo(undo_id)`. If the run used
   auto-init (post-73c26a0), `undo_group(group_id)` may work; otherwise undo
   individually.
3. Verify all 30 tasks are back in Inbox (`list_inbox`, cross-check against
   `test5-answer-key.md`). Re-add any that were deleted rather than moved.
4. Strip any remaining abstain tags (*Unclear*, *Ambiguous Home*, *Duplicate?*)
   via `propose_cleanup_ai_tags` or `propose_bulk_update` + `confirm_action`.
5. Confirm no AI-created projects remain (`get_projects`).
6. **Shuffle the Inbox** — tasks are always restored in cluster order (all cooking
   together, all Freelance together, etc.) which makes the sort trivially easy.
   Call `propose_reorder_todos(container="inbox", new_order=[…])` with the UUIDs
   in an interleaved order (no two tasks from the same thematic cluster adjacent).
   Obtain UUIDs from `list_inbox`; generate a shuffled order that alternates
   across: Carbonara, Baking, Freelance, Apartment, Recipe App, and singletons/ambiguous.

Reset *planning* is automated (`uv run things-mcp-fixture-reset` dry-run, shipped
in #3); live `--apply` is still manual (out of scope that crank).

---

## Open issues

- Fixture reset not automated; stray-task contamination recurring.
- Parallel-session collision risk on shared Things / state DB.
- Run 1 / Run 2 sorting model unconfirmed (Sonnet 4.6?).

## Key files (all under `sort-eval/`)

**`harness/` — persistent apparatus (reused every round):**
- `MISSION-CONTROL.md` — this file (plan + loop + backlog + fixture + playbook).
- `eval-ledger.md` — append-only results, one row per run.
- `test5-answer-key.md` — human-readable scoring key (**DO NOT load in a blind run**).
- `test5-key.json` — machine key consumed by `scorer.py` (path hard-wired there).
- `test5-scoring-template.md` — copied per scored run.
- `test5-blind-prompt.txt` — the one-line blind sort prompt.
- `test5-blind-harness.md` / `test5-rerun-runbook-2026-06-14.md` — run protocol.
- `TEST_5_BLIND_SORT.md` — original test-design rationale.

**`runs/` — write-once records:** `test5-verification-<date>.md`, one per run.
**`archive/` — superseded Test 4 generation.**
See `sort-eval/README.md` for the full map.

---

## Model guide

Different session types need different amounts of reasoning. Use the right model
to avoid wasting Opus tokens on mechanical work and Sonnet tokens on hard problems.

| Session | Model | Why |
|---------|-------|-----|
| **R — Fixture reset** | **Sonnet 4.6** | Mechanical undo + shuffle; no judgment needed |
| **A — Blind sort** | **Sonnet 4.6** | Must match the noise-floor model — changing it requires a new baseline |
| **B — Scoring** | **Sonnet 4.6** | Runs CLI, fills template; mechanical |
| **C — Dev, code to clear spec** (#3b/#3c/#6-style) | **Sonnet 4.6** | Delegates to coder-sonnet anyway |
| **C — Dev, architecture** (#4 two-pass router) | **Opus 4.8** | Requires reasoning about multi-pass prompt design and tradeoff analysis |
| **C — Dev, instruction/prose tuning** (#5) | **Opus 4.8** | Requires reasoning about LLM behavior and crafting effective instructions |

Per-item model assignments are also noted in the backlog table below (Model column).

⚠️ **Changing the Session A model is a controlled experiment, not a free upgrade.**
If you swap Sonnet→Opus for sorting, the noise-floor spread no longer applies and
you must run k≥3 runs at the new model before interpreting results. Keep the sort
model pinned at Sonnet 4.6 until a model-swap experiment is deliberately planned.

---

## Session playbook (one fresh session per phase — copy-paste the opener)

**Manual steps only the human can do:** commit (`.git` is owned by joshsmith —
Test can't write it), restart the MCP server (Claude Desktop manages it), start
each fresh session with its opener, ensure ONE session at a time (concurrent runs
collide on the shared DB), trigger the blind run.

**Agent-handled once pointed at the docs:** scoring vs. key, ledger append,
backlog status, fixture reset (as Test), code changes (via coder-sonnet).

### Session R — Fixture reset [Sonnet 4.6]
> Reset the Things test fixture to pristine state. Read
> `sort-eval/harness/MISSION-CONTROL.md` (Fixture section) for the current state
> and reset procedure. Working directory: `/Users/Shared/things-mcp`. Use the
> things-mcp MCP tools. Do not touch the answer key or ledger.

### Session A — Blind run (MUST stay blind) [Sonnet 4.6]
Set up per `sort-eval/harness/test5-blind-harness.md` §"Running the blind session":
a **fresh** session whose **working directory is the testing folder
`/Users/Test/Documents/Dev Tests/things-mcp-testing` — NOT the things-mcp repo**
(the repo's `docs/` and `sort-eval/` answer key must be unreachable), with
`mcp__things-mcp__*` connected and `THINGS_MCP_ALLOW_APPLESCRIPT=1` set. Paste the
**verbatim text** of `test5-blind-prompt.txt` as the opener — do NOT give the
agent a file path, a working-dir hint, or any reference to `sort-eval/`:
> Use things-mcp. Organise my Inbox into the correct projects and areas.

⚠️ Never let Session A read the answer key, scoring template, this file, the
ledger, or any verification doc — they reveal the expected answers.

### Session B — Scoring (may use the key) [Sonnet 4.6]
> Score the inbox sort just run. Read `sort-eval/harness/MISSION-CONTROL.md`
> (metric defs + loop), `sort-eval/harness/test5-answer-key.md`,
> `sort-eval/harness/test5-scoring-template.md`. Run `uv run things-mcp-score
> --pretty`, fill `sort-eval/runs/test5-verification-<today>.md` from the
> template, append one row to `sort-eval/harness/eval-ledger.md`, and set BACKLOG
> status in MISSION-CONTROL.

### Session C — Dev (one backlog item) [see Model guide above]
> Read `sort-eval/harness/MISSION-CONTROL.md` and `sort-eval/harness/eval-ledger.md`.
> Implement the next TODO backlog item. Delegate code to coder-sonnet, run the
> gates (`uv run pytest`, `--help`, `health()`), mark it READY-TO-TEST, and tell
> me to commit + restart.

### Between cycles (human)
Commit the change → restart the MCP server → ask the agent to reset the fixture
(Session R) → start Session A again.
