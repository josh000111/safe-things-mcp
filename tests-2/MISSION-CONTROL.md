# things-mcp Sort Quality — Mission Control

**Purpose:** single source of truth for the iterative loop that improves the things-mcp AI
inbox-sort. **Any fresh Claude session can resume from this file alone.** Do not
rely on a long-lived chat session — durable state lives here and in
`eval-ledger.md`.

**Last updated:** 2026-06-15 (post-run-4 scoring)

---

## North-star metric (DECIDED 2026-06-14)

**Precision-first, NOT strict-answer-key match.** A confidently *wrong* placement
is the only true failure — it erodes user trust and creates manual hunt-for-the-task work for the user.
Abstaining (leaving a task in the Inbox with an explanatory tag) is graceful
degradation, not a failure. An Inbox with 12 tasks left and zero misplacements
beats an empty Inbox with 4 misplacements.

Track two numbers per run:
- **Confident-wrong count** → drive to **0**.
- **Abstain-recall** = of the genuinely ambiguous tasks, % correctly left in the
  Inbox with an abstain tag.

Routing accuracy on the unambiguous majority is secondary (should stay ~95%+).
Rationale + full analysis: `test5-verification-2026-06-14.md`.

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
5. **SCORE** (fresh session, HAS key): fill a copy of `test5-scoring-template.md`
   → `test5-verification-<date>.md`; append one row to `eval-ledger.md`; set the
   BACKLOG item to **KEPT** or **REVERTED** based on whether confident-wrong /
   abstain-recall improved.
6. Next crank.

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
  Remaining north-star issues: #8 over-committed (abstain miss), #26 over-abstained,
  AI-heading still absent (separate Class B gap).

---

## Backlog (ordered)

| # | Change | Type | Status | Hypothesis (metric it should move) |
|---|--------|------|--------|-----------------------------------|
| 1 | group_id DB-persistence + AI-heading robustness | code invariant | DONE — live (7bb8853); bypass gap discovered (see #1a) | group_id non-null 100%; heading present 100% |
| 1a | Auto-init sort session on first `propose_bulk_move` if none active | code invariant | DONE — KEPT (73c26a0); group_id non-null confirmed run 4 | closed bypass gap; group_id now non-null across all bulk_moves |
| 2 | <3-task project guard | code invariant | DONE — live; not triggered (0 new projects in run 3) | kills spurious sub-3 projects (e.g. Eco Packaging) |
| 3 | Eval harness: programmatic scorer (state vs key → JSON) + scripted fixture reset | tooling | TODO | makes N≥5 runs cheap; removes scorer drift; fixes stray-task problem |
| 4 | Two-pass router→skeptic abstention | architecture | TODO | confident-wrong → 0 (demote unevidenced placements to abstain) |
| 5 | Abstain-vs-guess instruction tuning (#5/#8/#28/#26) | prose | TODO (after baseline) | abstain-recall up without tanking routing |
| 6 | Standardize `validation_error` shape (raise vs dict) | cleanup | TODO | consistency with rest of propose layer |

---

## Fixture

**Pristine** = 30 test tasks in Inbox (canonical list: `test5-answer-key.md` /
`test5-blind-harness.md`), original projects in pre-test state, no AI-created
projects, tasks interleaved so no two tasks from the same cluster are adjacent.

**Current state (2026-06-15 post-run-4): NEEDS RESET.**
Run 4 complete. Two new projects (Make Carbonara, Bake Sponge Cake) need deletion;
tasks need returning to Inbox; abstain tags on #25/#26 need stripping; shuffle required.

**Fixture reset procedure (for future runs):**

1. Call `recent_undo_log()` and identify the bulk_moves + bulk_updates from the
   completed run. Note their undo_ids.
2. Undo each entry **newest-first** via `undo(undo_id)`. group_id is often null
   (bypass gap — BACKLOG #1a), so `undo_group()` may not work; undo individually.
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

Reset is **not yet automated** (BACKLOG #3).

---

## Open issues

- Fixture reset not automated; stray-task contamination recurring.
- Parallel-session collision risk on shared Things / state DB.
- Run 1 / Run 2 sorting model unconfirmed (Sonnet 4.6?).

## Key files

- `test5-blind-prompt.txt` — the blind sort prompt (key-free).
- `test5-blind-harness.md` / `test5-rerun-runbook-2026-06-14.md` — run protocol.
- `test5-answer-key.md` — scoring key (**DO NOT load in a blind-run session**).
- `test5-scoring-template.md` — copy per scored run.
- `eval-ledger.md` — append-only results.

---

## Session playbook (one fresh session per phase — copy-paste the opener)

**Manual steps only the human can do:** commit (`.git` is owned by joshsmith —
Test can't write it), restart the MCP server (Claude Desktop manages it), start
each fresh session with its opener, ensure ONE session at a time (concurrent runs
collide on the shared DB), trigger the blind run.

**Agent-handled once pointed at the docs:** scoring vs. key, ledger append,
backlog status, fixture reset (as Test), code changes (via coder-sonnet).

### Session A — Blind run (MUST stay blind)
> Run the inbox sort in `tests-2/test5-blind-prompt.txt`. Follow it exactly. Do
> NOT read any other `tests-2/` files.

⚠️ Never let Session A read the answer key, scoring template, this file, the
ledger, or any verification doc — they reveal the expected answers.

### Session B — Scoring (may use the key)
> Score the inbox sort just run. Read `MISSION-CONTROL.md` (metric defs + loop),
> `test5-answer-key.md`, `test5-scoring-template.md`. Read live Things state via
> things-mcp, fill `test5-verification-<today>.md` from the template, append one
> row to `eval-ledger.md`, and set BACKLOG status in MISSION-CONTROL.

### Session C — Dev (one backlog item)
> Read `MISSION-CONTROL.md` and `eval-ledger.md`. Implement the next TODO backlog
> item. Delegate code to coder-sonnet, run the gates (`uv run pytest`, `--help`,
> `health()`), mark it READY-TO-TEST, and tell me to commit + restart.

### Between cycles (human)
Commit the change → restart the MCP server → ask the agent to reset the fixture
(Fixture section) → start Session A again.
