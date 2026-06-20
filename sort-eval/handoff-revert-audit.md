# Handoff — Audit: did every "REVERT" actually land in git before the next change built on top?

**Paste this whole file (or "Read `sort-eval/handoff-revert-audit.md` and carry out the audit it describes") as the opener of a FRESH Claude Code session in the `things-mcp` repo.**

---

## The worry to resolve

Across the sort-eval rounds, **scoring sessions frequently say "revert"** in their docs. Some of those were *recommendations* ("the next crank should revert X"), not *executed code changes*. Some were executed only **in the working tree** and depended on a human (joshsmith) to actually commit them — Test can't write `.git`. The risk:

> A later implementation round may have been built **on top of a change that was supposed to be reverted but never actually was** — so a "reverted" experiment is silently still live in the code the subsequent runs scored against.

Your job: for **every backlog item ever marked REVERTED**, determine *whether* and *exactly when (which commit)* the revert landed in git, and *whether every run that came after it actually executed code that contained the revert*. Produce a findings report. **Do not change any code or re-run sorts** — this is a read-only forensic audit.

## Why this is checkable

- The **ledger** (`sort-eval/harness/eval-ledger.md`) pins **one git SHA per run** (the `SHA` column).
- **MISSION-CONTROL** (`sort-eval/harness/MISSION-CONTROL.md`) records each backlog item's introduce-commit and revert claim.
- Git is the durable record. The repo already uses the gold-standard test for a clean revert: **`git diff <pre-introduce-baseline> <later-sha> -- <affected files>` is empty** ⟹ those files are byte-identical to baseline at `<later-sha>`.
- Ancestry is decidable: **`git merge-base --is-ancestor <revert-commit> <run-sha>`** (exit 0 = the run's code contains the revert).

## Anchors and the seed map (VERIFY — do not trust these blindly)

These come from the docs and may be wrong or incomplete — confirm each against `git log`/`git show`:

| Item | Type | Introduced @ | Revert claim in docs | Runs that used it |
|------|------|--------------|----------------------|-------------------|
| Noise-floor **baseline** | — | `773e920` | n/a (the anchor many reverts claim to restore to) | 6,7,8 |
| **#4** two-pass skeptic | code | `2bd582c` | "REVERTED — SHA 2bd582c reverted" — **revert commit NOT named in docs; FIND IT** | 12,13 |
| **#5** commit-to-cluster prose | prose (server.py) | `f2c23b6` | "REVERTED → restore to 773e920 exactly; next runs pin `6fc83f2`" | 9,10 |
| **#6** three-part instruction patch | prose (server.py) | `83eabe5` | "REVERTED" — commit **`f446582`** "Revert BACKLOG #6 server.py instruction patch (83eabe5)" | 14 |
| **A2** inbox_for_sort | code (server/read/repo + tests) | `9c1a4d6` | **REVERTED in WORKING TREE 2026-06-20, UNCOMMITTED at time of writing** — must confirm it got committed | 18,19 |
| (context) **KEPT** changes — do NOT expect these gone | — | #1a `73c26a0`, harness#3 `3589494`, A1+B1 `64853f4`/`570b419` | KEPT | — |

⚠️ **Chronology trap to untangle:** the round order is NOT the commit order you'd guess. Per the ledger, #5 (`f2c23b6`, runs 9/10) was reverted → run 11 pinned `6fc83f2` → THEN #4 (`2bd582c`, runs 12/13) → reverted → THEN #6 (`83eabe5`, run 14) → reverted (`f446582`). So `2bd582c` should be a **descendant** of the #5 revert, and the #6 work a descendant of the #4 revert. Build the real linear order from `git log --oneline --graph` first.

⚠️ **KEPT-change confound:** HEAD's `server.py` is legitimately **NOT** equal to `773e920` because **B1 decontamination** (KEPT) intentionally rewrote the `AGENT_INSTRUCTIONS` examples, and **A1** (KEPT) changed propose/handler code. So "diff vs 773e920 is non-empty" does **not** by itself prove a bad revert — you must attribute every surviving difference to a *known KEPT change*. The failure signal is a surviving difference that traces to a **REVERTED** item.

## Method (per reverted item: #4, #5, #6, A2)

1. **Establish the linear commit order** of all relevant SHAs: `git log --oneline --graph --all` and `git log --oneline 773e920..HEAD`.
2. **Find the introduce-commit and the revert-commit.** For each item, `git show --stat <introduce-sha>` to see which files/hunks it touched. For the revert, search history: `git log --oneline --all | grep -i revert` and `git log -S'<a distinctive string the change added>' --oneline` (e.g. the skeptic prose, the `inbox_for_sort` token). If no revert commit exists, that's a RED FLAG — record it.
3. **Verify the revert is content-complete.** Diff the *affected files only* between the item's pre-introduce parent and the revert commit:
   `git diff <introduce-sha>^ <revert-sha> -- <affected files>` → expect **empty** (modulo intervening KEPT changes to the same file — if so, compare against the appropriate post-KEPT baseline instead and reason explicitly).
4. **Verify ordering safety.** Confirm the revert is an ancestor of every later feature commit, so nothing built on un-reverted code:
   `git merge-base --is-ancestor <revert-sha> <next-feature-sha>` (exit 0 = safe).
5. **Verify every subsequent RUN executed reverted code.** For each ledger run dated after the revert, take its `SHA` and check `git merge-base --is-ancestor <revert-sha> <run-sha>` (exit 0 = that run's pinned code contained the revert). Flag any run whose pinned SHA does **not** contain a revert it should have.
6. **Cross-check the run docs' "Server restarted before run: yes/no"** field (in each `sort-eval/runs/test5-verification-*.md`). Git ancestry proves the *source* was reverted; the restart field is the only signal that the *running server* matched. Note any run where the SHA contained the revert but the doc says the server wasn't restarted (source-correct but possibly ran stale binary).

## Special case — the A2 revert (most recent, highest risk)

As of 2026-06-20 the A2 revert was done **in the working tree only and not yet committed** (joshsmith commits; Test cannot). Steps:
- Check whether HEAD (or any commit after `9c1a4d6`) actually contains the A2 revert: `git log --oneline 9c1a4d6..HEAD` and `git diff 64853f4 -- src/ tests/` (should be **empty** if A2 is gone from the working tree/HEAD; recall `64853f4` is the pre-A2 baseline).
- Check working-tree vs HEAD: `git status` + `git diff --stat`. If the A2 revert is still uncommitted, the **next** implementation round must start from a commit that includes it — verify that when it happens.
- Confirm there is **no** lingering `inbox_for_sort` token anywhere: `git grep -n inbox_for_sort $(git rev-parse HEAD)` and in the working tree `grep -rn inbox_for_sort src/ tests/`.
- Note the stale untracked `docs/handoff-A2-inbox-for-sort.md` (A2 design doc, never committed, now obsolete).

## Deliverable

Write findings to **`sort-eval/runs/revert-audit-2026-06-20.md`** (adjust date) with a table:

| Item | Introduced @ | Revert commit (or ❌ none) | Revert content-complete? (diff empty / attributed) | Ancestor of all later features? | Every later run's SHA contains it? | Verdict |
|------|--------------|----------------------------|----------------------------------------------------|---------------------------------|-------------------------------------|---------|

End with a plain-English **"Did anything build on un-reverted code?"** answer:
- ✅ **All clear** — every revert landed in git before the next change, and every subsequent run's pinned SHA contained it; OR
- ⚠️ **Found a gap** — name the item, the run(s) affected, and exactly what was still live. If a gap exists, also state whether it changes any KEEP/REVERT conclusion in MISSION-CONTROL (and flag it there with a dated note — do not silently rewrite history).

Also add a one-line pointer to the audit doc in MISSION-CONTROL's "Open issues" or "Current system state" so future sessions can find it.

## Guardrails

- **Read-only.** No code edits, no sorts, no fixture changes, no commits. Pure git + docs forensics.
- `whoami` should be `Test`; you won't be writing to Things or `.git`, so no backup needed.
- If you hit a claim in the docs that git contradicts, **trust git** and record the discrepancy — the docs are secondary evidence.
