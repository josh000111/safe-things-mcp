# sort-eval — things-mcp inbox-sort quality lab

This folder holds the **iterative evaluation loop** that measures and improves the
AI inbox-sort (the behaviour where a user says "sort my inbox" and the MCP routes
tasks into projects/areas, clusters related tasks into new projects, and abstains
on the ambiguous ones).

**Start here:** [`harness/MISSION-CONTROL.md`](harness/MISSION-CONTROL.md) — the
single source of truth. A fresh session can resume from that file alone.

---

## How the folders are organised

```
sort-eval/
├── README.md          ← you are here
├── harness/           ← PERSISTENT apparatus — reused every test round
├── runs/              ← TRANSIENT records — one write-once file per run
└── archive/           ← superseded generations (Test 4) — reference only
```

### `harness/` — the test apparatus (carries between sessions)

| File | What it is |
|------|-----------|
| `MISSION-CONTROL.md` | The hub: north-star metrics, the loop, the backlog, fixture spec, session playbook. **Read this first.** |
| `eval-ledger.md` | Append-only results table — one row per run, newest at bottom. |
| `test5-answer-key.md` | Human-readable scoring key (the fixture's ground truth). **Never load this in a blind run.** |
| `test5-key.json` | Machine-readable key consumed by the `things-mcp-score` CLI. Its path is hard-wired in `src/things_mcp/eval/scorer.py` — **move it and you must update that constant.** |
| `test5-scoring-template.md` | Blank scoring sheet; copy one per run into `runs/`. |
| `test5-blind-prompt.txt` | The one-line, key-free prompt fed to the blind sorting session. |
| `test5-blind-harness.md` | The corrected (uncontaminated) run protocol. |
| `test5-rerun-runbook-2026-06-14.md` | Step-by-step runbook for executing a run. |
| `TEST_5_BLIND_SORT.md` | Original test-design rationale. ⚠️ Its "Part 3" prompt is **superseded/contaminated** — use `test5-blind-prompt.txt` instead. |

### `runs/` — result records (write-once)

One `test5-verification-<date>.md` per scored run. These are historical records:
read for reference, never reused or edited after the run. Created by copying
`harness/test5-scoring-template.md`.

### `archive/` — dead generations

Test 4 (`TEST_4_*`, `test4-*`) — superseded by the blind Test 5 redesign. Kept for
provenance only; not part of the active loop.

---

## The loop in one breath

**DEV** (implement one backlog item) → **ACTIVATE** (commit + restart MCP server)
→ **RESET FIXTURE** (pristine 30-task Inbox) → **BLIND RUN** (fresh session, no key)
→ **SCORE** (`uv run things-mcp-score --pretty`, fill a `runs/` verification doc,
append a ledger row). Each phase is its own fresh session — see the **Session
playbook** in `MISSION-CONTROL.md`. Run **one** test at a time against the Test
Things DB (concurrent runs corrupt the shared fixture).

## Tooling

- `uv run things-mcp-score [--pretty] [--key PATH]` — scores live Things state
  against `harness/test5-key.json` and prints metrics JSON.
- `uv run things-mcp-fixture-reset` — dry-run reset planner (live `--apply` is
  still manual and guarded to the `Test` user).

## ⚠️ Read before trusting a single run

Runs 4 and 5 executed **identical sorting code** yet produced opposite results
(2 new clusters vs 0). Run-to-run LLM variance is large. A single before/after run
**cannot** tell a real improvement from noise — establish the noise floor
(BACKLOG #3a) before declaring any change KEPT or REVERTED. The *scorer* is
deterministic; a *single run* is not a baseline.
