# things-mcp Sort Quality — Mission Control

**Purpose:** single source of truth for the iterative loop that improves the things-mcp AI
inbox-sort. **Any fresh Claude session can resume from this file alone.** Do not
rely on a long-lived chat session — durable state lives here and in
`eval-ledger.md`.

**Last updated:** 2026-06-19 (run 17 scored: A1 coverage=10/10 ✅ in BOTH A1 runs; cw=2 within noise-floor; abstain_recall=80% recovered; A1 KEEP recommended — win condition met)

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
    - #26 "Research eco packing materials" fails consistently — over-abstained (runs 5/6/7/9/10/11/12/13/14)
      or wrong area (run 8). 10+ consecutive misses.
    - #8 "Mix ingredients" consistently not abstained — guessed baking (runs 7/8/12), moved to Personal (run 14).
- ❌ **BACKLOG #6 REVERTED (2026-06-17, run 14, SHA 83eabe5).** cw=12, worst since run 3
  (cw=13). The three-part instruction patch caused the agent to dump ALL 10 cluster tasks
  into area:Personal instead of creating new projects. Novel failure: agent treated
  area:Personal as a generic personal catch-all, bypassing cluster-project creation entirely.
  Abstain-recall (4/5) and routing-acc (9/10) unaffected. Single run was sufficient to
  revert given cw=12 is 4× above noise-floor ceiling of 3. See
  test5-verification-2026-06-17-run14.md.
- 📊 **Run 15 (2026-06-18, SHA f446582 = 773e920 baseline).** Post-#6-revert confirmation
  run. cw=1 (#26→area:Work), abstain_recall=4/5 (80%), coverage=0/10. All within noise
  floor. Empty-project failure again (same as run 6): "Make Carbonara" + "Bake Sponge Cake"
  created but both empty; all 10 cluster tasks left in Inbox untagged. group_id non-null ✅.
  #3c first live data: sort_guard_rejected=0 (guard never triggered this run). See
  test5-verification-2026-06-18.md.
- 📊 **Run 16 (2026-06-19, SHA 64853f4 = A1+B1 live).** FIRST A1 RUN.
  coverage=**10/10** ✅ — atomic populate fired; "Make Carbonara" (5 tasks) + "Bake Cake"
  (5 tasks + #8 + #28) fully populated. First full coverage since run 7. cw=**4** ⚠️ ABOVE
  noise-floor ceiling of 3: #8→Bake Cake (persistent coin-flip committed), #11→Freelance
  with *Duplicate?* tag (novel: dupe detected but moved anyway), #25+#26→area:Work
  (persistent). abstain_recall=**2/5 (40%)** ❌ NEW LOW (below noise-floor min 60%).
  A1 primary hypothesis confirmed for 1 run. cw/abstain spikes were 1-run noise (confirmed by run 17).
  See test5-verification-2026-06-19-run16.md.
- ✅ **Run 17 (2026-06-19, SHA 64853f4 = A1+B1, same build).** SECOND A1 RUN — **WIN CONDITION MET.**
  coverage=**10/10** ✅ in both A1 runs. cw=**2** ✅ within noise floor [0,1,3]. abstain_recall=**4/5 (80%)**
  ✅ recovered to baseline. #11 correctly left inbox *Duplicate?* (recovered from run 16 miss). #25 correctly
  abstained (recovered from run 16 miss). Only persistent failures: #8 (coin-flip committed, 13th+ miss)
  and #26 (area:Work, 12th+ miss) — both pre-existing, unrelated to A1. Coverage min across both A1 runs
  = 10/10 definitively above pre-A1 noise floor min of 0. **A1 KEEP recommended.**
  See test5-verification-2026-06-19-run17.md.

- 📂 Docs reorganized 2026-06-16 into `sort-eval/{harness,runs,archive}`
  (was the flat `tests-2/`). See `sort-eval/README.md`. Scorer key path updated
  in `scorer.py`.

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

| # | Change | Type | Status | Hypothesis (metric it should move) |
|---|--------|------|--------|-----------------------------------|
| 1 | group_id DB-persistence + AI-heading robustness | code invariant | DONE — live (7bb8853); bypass gap discovered (see #1a) | group_id non-null 100%; heading present 100% |
| 1a | Auto-init sort session on first `propose_bulk_move` if none active | code invariant | DONE — KEPT (73c26a0); group_id non-null confirmed run 4 | closed bypass gap; group_id now non-null across all bulk_moves |
| 2 | <3-task project guard | code invariant | DONE — live; not triggered (0 new projects in run 3) | kills spurious sub-3 projects (e.g. Eco Packaging) |
| 3 | Eval harness: programmatic scorer (state vs key → JSON) + scripted fixture reset | tooling | **KEPT** (3589494; first programmatic score = run 5 2026-06-16) | makes N≥5 runs cheap; removes scorer drift; fixes stray-task problem |
| **3a** | **Noise-floor baseline: run the CURRENT build k≥3× (no code change) and record the spread of cw / abstain-recall / coverage** | **measurement** | **DONE (2026-06-16, runs 6/7/8, SHA 773e920): cw=[0,1,3], abstain=[60%,80%,80%], coverage=[0,10,10]/10** | establishes how big an effect must be to count as real; converts single runs from "anecdote" to "signal" |
| **3b** | **Add coverage/yield metric to the scorer** (so abstaining isn't free; see north-star refinement) | **code (scorer)** | **DONE — already fully implemented** (`score()` metrics.coverage dict; ledger rows already show it; no code change needed) | makes "placed nothing" score badly; closes the gameable-by-inaction hole |
| **3c** | **Log rejected `propose_add_project` attempts** (guard returns a dict, writes nothing) | **code (observability)** | **READY-TO-TEST** — `sort_guard_rejected` table now stores `task_ids_json` (JSON array of submitted UUIDs) alongside `group_id`, `title`, `member_count`, `rejected_at`; migration added for existing DBs; call site in `propose.py` passes `member_todo_ids`; 525 tests pass. **First live data (run 15): sort_guard_rejected=0 rows** — guard was not triggered; agent created 2 projects with the intention of ≥3 tasks (correct), then failed to populate them. Consistent with "agent never moved tasks in" being the root-cause failure, not "guard blocked creation." | distinguishes "agent gave up clustering" from "agent never tried" — currently untraceable post-hoc |
| **A1** | **Atomic populate: `propose_add_project` + `bulk_move` in one handler step** | **code invariant** | **✅ KEEP (runs 16+17, 2026-06-19)** — coverage=10/10 in BOTH A1 runs (noise-floor min was 0). cw=[4,2] with run 16's spike a 1-run anomaly; run 17 cw=2 within noise floor. abstain_recall=[40%,80%] — run 16 spike recovered. Win condition met: coverage min > 0 across all A1 runs. Persistent failures (#8, #26) are pre-existing and unrelated to A1. | coverage min > 0 across 2+ runs (empty-folder mode eliminated) |
| **B1** | **Decontaminate `AGENT_INSTRUCTIONS` in `server.py`** — cooking examples leaked fixture task names verbatim (6 of 30 test tasks named; `server.py:50-60` contradicted the answer key for #28) | **code (test validity)** | **DONE (2026-06-19)** — cooking-cluster example replaced with neutral garden/pool domain; "onboarding"/"March invoice" and the two-Shopping-lists decoy also rewritten; `CONTAMINATION GUARD` comment added above `AGENT_INSTRUCTIONS`. 530 tests pass. Sub-task **B1b** pending: `docs/ai-tagging-guidance.md` still uses old cooking examples — decontaminate before next sync. | precision/abstain numbers now trustworthy; #28 self-contradiction removed |
| 4 | Two-pass router→skeptic abstention | architecture | **REVERTED — bimodal oscillation (cw=[3,0], coverage=[10,0]/10 across runs 12/13); no metric moved outside noise floor; skeptic had no per-task veto, caused all-or-nothing behaviour. SHA 2bd582c reverted.** | confident-wrong → 0 (demote unevidenced placements to abstain) |
| 5 | Abstain-vs-guess instruction tuning — **re-scope toward *committing* to well-evidenced clusters** (#5/#8/#26/#28) | prose | **CLOSED — superseded.** A1 fixed cluster coverage via code. #8 accepted as irreducible coin-flip variance (A3 closed). Prose tuning has a poor track record (BACKLOG #4/#5/#6 all reverted). | recover cluster coverage without raising confident-wrong |
| **6** | **Three-part instruction patch** (notes-first rule; mandatory coin-flip abstain; cluster-plan + empty-project guard in workflow) | **prose** | **REVERTED — cw=12 (run 14, 83eabe5), 4× above noise-floor ceiling of 3. Novel failure: agent used area:Personal as catch-all for all 10 cluster tasks instead of creating projects. Zero projects created. Abstain-recall + routing unaffected. Single run sufficient to revert given magnitude.** | #26 fix: notes resolve title ambiguity; #8 fix: BOTH-clusters → mandatory *Ambiguous Home*; coverage fix: cluster plan forces commit-or-tag, step-6 guard prevents empty projects |
| 7 | Standardize `validation_error` shape (raise vs dict) | cleanup | TODO | consistency with rest of propose layer |
| **A2** | **`inbox_for_sort()` signal-paired sort read** — focused read tool that projects each inbox task to `{uuid, title, notes, tags, deadline, checklist}` and strips the noise fields, so routing signals sit paired/undiluted next to the title. SORT WORKFLOW step 1 now reads via `inbox_for_sort` instead of `list_inbox`. Presentation-only lever (no keyword rule, no prose nudge — both ruled out). Targets #26 "Research eco packing materials". | **code (presentation)** | **READY-TO-TEST (2026-06-19)** — `inbox_for_sort()` added to `things_repo.py` + `read.py` (uses `include_items=True` so `checklist` is items not a bool); `list_inbox` unchanged; one neutral one-word swap in `server.py` step 1. Gates pass: 535 tests pass (+ 6 new projection tests), 1 skipped, 1 pre-existing live-AppleScript failure (`test_step5a_live`, fails identically on clean HEAD); `things-mcp --help` clean; `health()` OK (app running, py 1.0.1, state db exists); live read smoke test projected 439 inbox tasks to the six keys with no noise. Falsifiable experiment — judge #26 over 2+ blind runs. | #26 routing_acc miss eliminated → attention fixed; OR #26 still misses → proven a judgment limit, justifies C1 |
| **B2** | **Automate fixture reset** — finish the `things-mcp-fixture-reset --apply` live path (currently prints "execute manually"). Dry-run planner exists; live apply is hard-guarded to `Test` user. | tooling | TODO — after A2 | reduces cycle time; eliminates manual-reset errors |
| **C1** | **Try Opus for the sort** — swap the sorting model from Sonnet 4.6 to Opus. Hard judgments (notes, ambiguity, #8/#26) may improve. No code change needed; one test round (2 runs). | experiment | TODO — after A2 measured | abstain_recall and #26 routing may improve on a stronger model |
| **C2** | **Deterministic clustering pre-pass** — code identifies obvious task clusters (shared nouns, shared project signals) before the AI runs; AI only confirms/names. Bigger architectural change. | architecture | TODO — later | eliminates remaining coverage + cluster-naming variance; biggest potential gain |

---

## Fixture

**Pristine** = 30 test tasks in Inbox (canonical list: `test5-answer-key.md` /
`test5-blind-harness.md`), original projects in pre-test state, no AI-created
projects, tasks interleaved so no two tasks from the same cluster are adjacent.

**Current state (2026-06-19 post-run-17): DIRTY — needs reset before run 18.**
Run 17 created "Make Carbonara" (5 tasks: #5,10,15,19,23) and "Bake Sponge Cake" (7 tasks:
#3,12,18,24,29,#8,#28). Tasks #2,7,17→Freelance: TechCorp API; #4,13,20→Apartment Move;
#9,14,22→Recipe App. #1,#30→area:Home; #6,#27→area:Personal; #26→area:Work.
#11 inbox *Duplicate?*; #16 inbox *Unclear*; #21 inbox *Unclear*; #25 inbox *Ambiguous Home*.
Must undo all run-17 moves (undo_group preferred), delete both AI projects, and strip
abstain tags before next run.

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

## Session playbook (one fresh session per phase — copy-paste the opener)

**Manual steps only the human can do:** commit (`.git` is owned by joshsmith —
Test can't write it), restart the MCP server (Claude Desktop manages it), start
each fresh session with its opener, ensure ONE session at a time (concurrent runs
collide on the shared DB), trigger the blind run.

**Agent-handled once pointed at the docs:** scoring vs. key, ledger append,
backlog status, fixture reset (as Test), code changes (via coder-sonnet).

### Session A — Blind run (MUST stay blind)
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

### Session B — Scoring (may use the key)
> Score the inbox sort just run. Read `sort-eval/harness/MISSION-CONTROL.md`
> (metric defs + loop), `sort-eval/harness/test5-answer-key.md`,
> `sort-eval/harness/test5-scoring-template.md`. Run `uv run things-mcp-score
> --pretty`, fill `sort-eval/runs/test5-verification-<today>.md` from the
> template, append one row to `sort-eval/harness/eval-ledger.md`, and set BACKLOG
> status in MISSION-CONTROL.

### Session C — Dev (one backlog item)
> Read `sort-eval/harness/MISSION-CONTROL.md` and `sort-eval/harness/eval-ledger.md`.
> Implement the next TODO backlog item. Delegate code to coder-sonnet, run the
> gates (`uv run pytest`, `--help`, `health()`), mark it READY-TO-TEST, and tell
> me to commit + restart.

### Between cycles (human)
Commit the change → restart the MCP server → ask the agent to reset the fixture
(Fixture section) → start Session A again.
