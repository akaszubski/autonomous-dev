# Plan: move plan storage out of `.claude/plans/`

**Status:** DRAFT — awaiting review
**Issue:** #1516
**Date:** 2026-08-17

> This document is itself the demonstration: written to `docs/plans/`, it produced no permission prompt.

---

## WHY + SCOPE

### Why — the prompt cannot be fixed with permissions

Every `/plan` run in a consumer repo interrupts the user:

```
Do you want to create watchdog-consolidation-and-migration-gate.md?
```

The obvious fix — grant the path — has already been tried and does not work. Measured across all five repos, **every one already has both forms**:

```
Write(.claude/plans/**)
Write(/Users/akaszubski/Dev/<repo>/.claude/plans/**)
Edit(.claude/plans/**)
Edit(/Users/akaszubski/Dev/<repo>/.claude/plans/**)
```

The prompt fires regardless. It originates in Claude Code's built-in sensitivity protection for `.claude/` paths, which the permission allow-list does not override. The accumulated one-off rules in these repos (8 in spektiv, several elsewhere) are the fossil record of people trying this and failing.

**Any fix that stays inside `.claude/` is dead on arrival.**

### Why — plans are also being discarded

```
.gitignore:147:  .claude/*    .claude/plans
```

`.claude/plans/` is gitignored. Every plan ever written by `/plan` has been thrown away: not reviewable, not diffable, absent from history, gone after a clean checkout. This works directly against the reason plans exist — carrying intent across sessions.

Meanwhile `docs/plans/` already exists, is tracked, and contains real plans (`codex-plugin-port.md`, `PLAN_1023_non_swe_intent_classes.md`).

So there are **two plan locations already**, and the wired-up one is the worse of the two: it prompts *and* discards. This is the same duplicated-location defect as #1521 (three code copies) and #1522 (four registration surfaces).

### IN scope

Move the plan storage location for all components that read or write it, together, in one change. Migrate existing content. Add a guard so the location cannot silently diverge again.

### OUT of scope

- **Plan content, structure, or the required sections.** Only the location changes.
- **The plan-critic loop and its verdict handling** (#1454, #1457). Untouched.
- **`.claude/local/`, `.claude/logs/`, `.claude/state/`.** They are correctly ignored and correctly not prompted-on, because nothing writes them via the Write tool.
- **Un-gitignoring `.claude/`.** Rejected below.

### Success criteria

- `/plan` in a fresh consumer repo writes a plan with **zero permission prompts**
- `plan_gate.py` validates the new location **and still blocks when no plan exists**
- Plans appear in `git status` — they persist
- Exactly one plan location exists across the codebase, enforced by a test

---

## Existing Solutions

**Searched:** `plan.md`, `implement.md`, `plan-to-issues.md`, `drain-queue.md`, `plan_gate.py`, `.gitignore`, all five repos' `settings.local.json`, and the tracked contents of `docs/plans/`.

`docs/plans/` is an existing, working convention in this repo — tracked, populated, and prompt-free. **Nothing new needs inventing; the destination already exists and is proven.**

`.claude/plans/` is referenced in 5 components:

```
commands/plan.md            :13, :273, :275, :278, :316, :330, :350, :360
commands/implement.md       STEP 5.5a pre-validated plan search
commands/plan-to-issues.md
commands/drain-queue.md
hooks/plan_gate.py          :6, :16   <- validates plan location
```

---

## Minimal Path

Ordered so that no intermediate state is broken.

### Step 1 — Make the gate accept BOTH locations

Change `plan_gate.py` to look in `docs/plans/` **and** `.claude/plans/`. Nothing else changes yet.

This is deliberately first and deliberately additive: after it, a plan in either place satisfies the gate, so the writer can move without a flag day and repos mid-migration keep working.

### Step 2 — Move the writer

Point `plan.md` at `docs/plans/`. From here new plans stop prompting and start persisting.

### Step 3 — Move the readers

`implement.md` STEP 5.5a, `plan-to-issues.md`, `drain-queue.md` read the new location first, falling back to the old.

### Step 4 — Migrate existing content

Move any `.claude/plans/*.md` in each repo into `docs/plans/`. Content is unchanged; only the path moves. Report what moved rather than doing it silently.

### Step 5 — Drop the fallback, add the guard

Once no repo has `.claude/plans/` content, remove the dual-read from step 1 and add a test asserting no component references `.claude/plans/`. Converts the migration into a ratchet.

---

## Files to Create/Modify

| # | File | Action |
|---|---|---|
| 1 | `plugins/autonomous-dev/hooks/plan_gate.py` | MODIFY — accept both, then new-only |
| 2 | `plugins/autonomous-dev/commands/plan.md` | MODIFY — write to `docs/plans/` |
| 3 | `plugins/autonomous-dev/commands/implement.md` | MODIFY — STEP 5.5a search path |
| 4 | `plugins/autonomous-dev/commands/plan-to-issues.md` | MODIFY — input path |
| 5 | `plugins/autonomous-dev/commands/drain-queue.md` | MODIFY — input path |
| 6 | `tests/regression/test_issue_1516_plan_location.py` | CREATE — location invariant + gate-still-blocks control |
| 7 | `.gitignore` | MODIFY — only if `.claude/plans` entry becomes dead |

Estimated: 6–7 files.

---

## Test Scenarios

1. `/plan` in a fresh consumer repo writes to `docs/plans/` with **no permission prompt**.
2. `plan_gate.py` accepts a plan in `docs/plans/`.
3. **Negative control — the load-bearing one:** `plan_gate.py` still BLOCKS when no plan exists anywhere. A location move that quietly turns the gate into a no-op is far worse than the prompt it fixes.
4. During transition, a plan in the old location still satisfies the gate.
5. `/implement` STEP 5.5a finds a pre-validated plan in the new location.
6. Written plans appear in `git status` — the persistence property.
7. **Negative control:** no new blanket `.claude/**` permission grant is introduced.
8. After step 5, no component references `.claude/plans/`.

---

## Risks and Unknowns

1. **The gate becoming a no-op is the real danger.** `plan_gate.py` blocks implementation until a validated plan exists. If the writer moves and the gate does not — or the gate's path check silently matches nothing — the gate stops gating and nobody notices, because a gate that never fires produces no output. Mitigated by ordering (gate first, additive) and by test scenario 3, which must fail if the gate stops blocking.

2. **Tracked plans are a visible change for consumer repos.** Plans currently vanish; afterwards they appear in `git status` and in review. That is the intent, but it is a behaviour change for repos that did not ask for it. **Open question for the maintainer:** is `docs/plans/` right for every consumer, or should the location be configurable with `docs/plans/` as the default? A repo that considers plans working notes may not want them in `docs/`.

3. **Cross-repo migration is five repos plus a machine that is currently off.** The Mac Studio cannot be updated until it is on, so it will run the old location for a while. The dual-read in step 1 is what makes that safe; step 5 must not land until every repo is migrated.

4. **`.claude/plans` may be referenced outside these five components** — scripts, docs, or the archived surface. The step-5 guard is what proves the list was complete; until it passes, "5 components" is a claim rather than a fact.

5. **UNVERIFIED:** I have not tested whether `docs/plans/` is prompt-free in a repo where `docs/` itself carries unusual permission rules. This document being written without a prompt is evidence for autonomous-dev only.

---

## Alternatives Rejected

- **More permission rules.** Measured: already present in all five repos, prompt fires anyway.
- **Un-gitignoring `.claude/plans/`.** Fixes persistence, not the prompt, and drags a directory whose siblings should stay ignored into version control.
- **Keeping both locations.** Two plan directories is the defect, not the remedy.
- **`plans/` at the repo root.** Also prompt-free and works; rejected only because `docs/plans/` already exists and is populated, so it needs no new convention. Trivially swappable if preferred.

---

## Critique History

_(to be filled by plan-critic rounds)_

## Linked Issues

- #1516 — the defect and the corrected diagnosis
- #1521, #1522 — same duplicated-location class
