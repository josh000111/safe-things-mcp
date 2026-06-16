# Test 5 — Blind Sort: corrected harness (rerun)

The first Test 5 run (scored in `test5-verification-2026-06-13.md`) was
**contaminated** and is invalid. This file defines the corrected, production-
faithful harness for the rerun. Read this instead of Part 3 of
`TEST_5_BLIND_SORT.md`.

---

## Why the previous run was invalid

Two separate leaks meant the "blind" agent was not actually blind:

1. **Repo + doc access.** The Part 3 prompt set `Working directory:
   /Users/Shared/things-mcp` *and* told the agent to "follow the full workflow
   from `docs/ai-tagging-guidance.md`." That doc **does not ship** to real users
   (`server.py` only ships the `instructions=` string), yet the test handed the
   agent the full doc — including the exact `"Mix the ingredients"` cross-cluster
   worked example and the answer-key-shaped routing rules.

2. **The `instructions=` example named the answer.** The shipped instructions
   used `"Spaghetti Carbonara"` vs `"Cooking"` as its project-naming example —
   handing the agent the exact dish-specific name and anti-pattern that the
   dish-specificity criterion is supposed to *test*. (Fixed: the example is now a
   non-food domain, "Bathroom Remodel" vs "House".)

A real user's agent sees **only** the `instructions=` string injected over MCP —
never the repo, never the doc, never the answer key. The rerun must reproduce
exactly that.

---

## Pre-flight (run as the SCORER, before handing off)

In this (informed) session, confirm the fixture is clean:

1. `whoami` → `Test`
2. `list_inbox` → exactly **30 tasks, no abstain tags** on any
3. `get_projects` → only the **5 survivors**: Freelance: TechCorp API,
   Apartment Move, Recipe App, Shopping (in Area 'Home'), Shopping (standalone).
   No "Carbonara" / "Bake Cake" from a prior run.
4. Task "Research eco packing materials" still carries its notes + deadline
   2026-07-15.

> As of 2026-06-14 the fixture has been reset to this clean state via undo of the
> prior (invalid) sort. The two prior-run projects were soft-undone to the
> Logbook; they do not appear in `get_projects`.

## CRITICAL — restart the MCP server first

The `instructions=` string was changed on 2026-06-14. **The running things-mcp
server process still holds the OLD instructions in memory.** Before the rerun,
**restart / reconnect the things-mcp MCP server** (e.g. quit and relaunch the
client, or toggle the server connection) so the agent receives the updated
guidance. If you skip this, you are testing the old instructions.

---

## Running the blind session

1. Open a **completely fresh** Claude Code session — no shared context with this
   one.
2. **Working directory: `/Users/Test/Documents/Dev Tests/things-mcp-testing`**
   (NOT the things-mcp repo). The things-mcp MCP tools are available there; the
   repo's docs and the answer key are not reachable. Confirm the `mcp__things-mcp__*`
   tools are connected in that session.
3. Confirm `THINGS_MCP_ALLOW_APPLESCRIPT=1` is set for that session (the AI
   tagging tools need it).
4. Paste the prompt from **`test5-blind-prompt.txt`** verbatim as the opening
   message. It contains no file paths, no working-dir hint, no `uv` instruction,
   and no reference to any workflow doc or the `sort-eval/` directory — the agent
   must rely solely on the injected `instructions=`.
5. Do not coach the agent. Approve its new-project list when it asks (that is the
   one interaction the prompt invites), but do not steer naming or routing.

What makes this blind, checklist:
- [ ] Session cwd is the testing folder, not the repo
- [ ] Agent cannot read `docs/ai-tagging-guidance.md` (outside its cwd)
- [ ] Agent cannot read `sort-eval/` (answer key, this file)
- [ ] MCP server restarted so new `instructions=` is live
- [ ] Prompt is the verbatim `test5-blind-prompt.txt`

---

## Scoring the rerun

After the blind session completes, return to an informed session and score
against `test5-answer-key.md`, recording results in
`test5-verification-<rerun-date>.md`. Pay special attention to the items the
updated `instructions=` now targets:

- **Project contents read** — did the agent `get_project` on each candidate
  before routing? (New "build context first" rule.)
- **Duplicate detection** — "Invoice client March" should be flagged
  `*Duplicate?*` against existing "Send March invoice".
- **Recipe App routing** — "Fix search clear field crash" and "Add back btn to
  onboarding" should reach Recipe App (vocabulary echo), not be over-abstained.
- **Cross-cluster abstain** — "Mix ingredients" and "Check temp midway" should
  stay in Inbox `*Ambiguous Home*`. (Note: a bare "Mix ingredients" with no
  contrastive partner is genuinely unresolvable — abstaining is the *correct*
  outcome, not a miss.)
- **Singletons** — under the agreed policy, a singleton may go to a confident
  **existing** Area; it should NOT spawn a new Area, and should fall back to
  Inbox `*Unclear*` if no existing Area fits.
- **🛒** — lone emoji → `*Unclear*` (no parseable text), regardless of the two
  "Shopping" projects.
- **Duplicate-named "Shopping"** — if a task DID belong in Shopping, the agent
  should pick the most recently created one, not abstain.
- **`__NEWLY ADDED BY AI__` heading** — present in existing projects that
  received tasks (via `propose_move_under_ai_heading`); absent from any new
  project.
- **group_id** — must be generated and surfaced; `recent_undo_log` rows should
  carry it (the prior run left `group_id=null`, which itself was a failure).

---

## Note on the answer key vs the agreed singleton policy

`test5-answer-key.md` predates the singleton-policy decision (file singletons
into a confident existing Area; never create Areas; else Inbox `*Unclear*`).
Under that policy, tasks like "Collect dry cleaning" / "Return library books" /
"Tom farewell dinner org" routed into the existing **Personal** Area are
**acceptable**, not failures — even though the key marks them `*Unclear*`. When
scoring the rerun, treat a confident existing-Area placement of a singleton as a
pass; only flag new-Area creation or a weak/ambiguous Area guess.
