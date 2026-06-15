# Eval Ledger — things-mcp sort runs (append-only)

One row per blind sort run, newest at bottom. See `MISSION-CONTROL.md` for the
loop and the north-star metric.

**Metric defs**
- **routing-acc** — correct placements among the *unambiguous* tasks.
- **confident-wrong** — tasks confidently placed in a project/area with a
  wrong/unjustified home (the count to drive to 0). Abstains do NOT count here.
- **abstain-recall** — correctly-abstained ambiguous tasks / total genuinely
  ambiguous tasks.

**Config columns** — SHA = git HEAD at run; instr = AGENT_INSTRUCTIONS version/note;
model = sorting model; fixture = fixture version.

| Date | SHA | instr | model | fixture | routing-acc | confident-wrong | abstain-recall | group_id | AI-heading | Notes |
|------|-----|-------|-------|---------|-------------|-----------------|----------------|----------|-----------|-------|
| 2026-06-14 18:20 | pre-fix (~fa62ede) | pre-rev | unconfirmed | test5 v1 | 9/10 | 3 (#5,#8,#28) | low (#8,#25,#28 missed) | null ❌ | absent ❌ | contaminated baseline; see test5-verification-2026-06-14.md |
| 2026-06-14 20:27 | pre-fix | pre-rev | unconfirmed (Sonnet 4.6?) | test5 v1 + strays | 7/10 | 6 (#5,#8,#9,#25,#26,#30) | low | partial (apply only) | absent ❌ | spurious 2-task Eco Packaging; Recipe-App routing collapsed (1/3) |
| 2026-06-15 13:26 | 7bb8853 (fix live) | post-fix (apply_ai_tags skipped by agent) | unconfirmed (Sonnet 4.6?) | test5 v1 (reset) | 9/10 | **13** (#3,5,8,10,12,15,18,19,23,24,26,28,29) | 1/3 (low) | null ❌ (agent skipped apply_ai_tags → no session opened) | absent ❌ (same bypass) | ❌ REGRESSION — all 12 cooking tasks dumped to Recipe App; 0 new projects; fix bypass gap discovered: sort session must also auto-init on first bulk_move; see test5-verification-2026-06-15.md |
| _(pending)_ | _commit the fix_ | DB-session + <3 guard | _TBD_ | test5 v1 (needs reset) | | | | expect non-null | expect present | **CLEAN BASELINE** — first post-fix blind run (requires commit + MCP restart + fixture reset first) |
