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
| 2026-06-15 18:11 | 73c26a0 (auto-init live) | post-fix #1a (auto-init on bulk_move) | unconfirmed (Sonnet 4.6?) | test5 v1 (reset) | 9/10 | **2** (#8, #26) | 1/2 (50%) | **non-null ✅** "sort-inbox-20260615" | absent ❌ | ✅ BEST RUN — #1a confirmed; 2 correct new projects (Make Carbonara, Bake Sponge Cake); persistent misses: #8 over-committed (abstain failure), #26 over-abstained (should → Apartment Move), AI-heading still absent; see test5-verification-2026-06-15-run4.md |
| 2026-06-16 | 3589494 (eval harness live) | post-fix #1a | Sonnet 4.6 | test5 v1 (needs reset) | **9/10** | **0** ✅ | **4/5 (80%)** | not checked | not checked | 🆕 FIRST PROGRAMMATIC SCORE. confident_wrong=0 (north-star achieved) but zero new projects created — 10 Carbonara+Baking tasks left in inbox untagged. #26 over-abstained again (persistent). #8 in inbox but missing *Ambiguous Home* tag (abstain miss). Existing-project routing solid. Improvement vs run 4: cw 2→0, abstain-recall 50%→80%. Regression: cluster creation 2→0. See test5-verification-2026-06-16.md |
| 2026-06-16 (run6) | 773e920 (baseline N=1) | post-fix #1a | Sonnet 4.6 | test5 v1 (reset) | **9/10** | **0** ✅ | **4/5 (80%)** | not checked | not checked | 📊 BASELINE N=1/3. coverage=0/10 (agent created "Make Carbonara" + "Bake a Cake" as empty projects — tasks never moved in). #26 over-abstained again. #8 tagged *Unclear* instead of *Ambiguous Home* (abstain miss). Existing-project routing solid. See test5-verification-2026-06-16-run6.md |
| 2026-06-16 (run7) | 773e920 (baseline N=2) | post-fix #1a | Sonnet 4.6 | test5 v1 (reset) | **9/10** | **1** (#8) | **4/5 (80%)** | not checked | not checked | 📊 BASELINE N=2/3. coverage=10/10 ✅ — both clusters fully populated ("Make Carbonara" + "Bake Cake"). cw=1: #8 placed in Bake Cake (coin-flip guessed wrong). #26 over-abstained again. carbonara_cohesion=true, baking_cohesion=true. See test5-verification-2026-06-16-run7.md |
| 2026-06-16 (run8) | 773e920 (baseline N=3) | post-fix #1a | Sonnet 4.6 | test5 v1 (reset) | **9/10** | **3** (#8,#25,#26) | **3/5 (60%)** | not checked | not checked | 📊 BASELINE N=3/3. coverage=10/10 ✅ — both clusters fully populated ("Make Carbonara" + "Bake Sponge Cake"). cw=3: #8 in baking (persistent), #25+#26 routed to area:Work instead of abstaining/Apartment Move (new failure). abstain_recall lowest of baseline set. Routing tags not cleaned up (novel). See test5-verification-2026-06-16-run8.md |
