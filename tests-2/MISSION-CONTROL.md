# things-mcp Sort Quality — Mission Control

**Purpose:** single source of truth for the iterative loop that improves the things-mcp AI
inbox-sort. **Any fresh Claude session can resume from this file alone.** Do not
rely on a long-lived chat session — durable state lives here and in
`eval-ledger.md`.

**Last updated:** 2026-06-15

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
- ⚠️ The fix is in the **working tree, uncommitted** (HEAD `fa62ede`). **Commit
  before the baseline run** so the ledger can pin a SHA.

---

## Backlog (ordered)

| # | Change | Type | Status | Hypothesis (metric it should move) |
|---|--------|------|--------|-----------------------------------|
| 1 | group_id DB-persistence + AI-heading robustness | code invariant | DONE — smoke-verified; awaiting blind confirm | group_id non-null 100%; heading present 100% |
| 2 | <3-task project guard | code invariant | DONE — smoke-verified | kills spurious sub-3 projects (e.g. Eco Packaging) |
| 3 | Eval harness: programmatic scorer (state vs key → JSON) + scripted fixture reset | tooling | TODO | makes N≥5 runs cheap; removes scorer drift; fixes stray-task problem |
| 4 | Two-pass router→skeptic abstention | architecture | TODO | confident-wrong → 0 (demote unevidenced placements to abstain) |
| 5 | Abstain-vs-guess instruction tuning (#5/#8/#28/#26) | prose | TODO (after baseline) | abstain-recall up without tanking routing |
| 6 | Standardize `validation_error` shape (raise vs dict) | cleanup | TODO | consistency with rest of propose layer |

---

## Fixture

**Pristine** = 30 test tasks in Inbox (canonical list: `test5-answer-key.md` /
`test5-blind-harness.md`), original projects in pre-test state, no AI-created
projects.

**Current state (2026-06-15): PRISTINE — reset complete, ready for the blind run.**
All 30 fixture tasks in the Inbox, untagged; #26 (`Research eco packing
materials`) notes + deadline 2026-07-15 intact; the 3 AI-created projects
cancelled to Logbook; strays removed; state-DB tracking tables (`sort_session*`,
`ai_tag_routing`) cleared. The fix is LIVE (smoke-verified).

Reset is **not yet automated** (BACKLOG #3). Method used this time: Run-2 moves
had null group_id (pre-fix) so `undo_group` couldn't reverse them — instead undid
Run 2's 11 individual undo-log entries newest-first (7 bulk_moves → 3
add_projects → 1 apply_ai_tags) via `undo(undo_id)`, then deleted the 2 strays.

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
