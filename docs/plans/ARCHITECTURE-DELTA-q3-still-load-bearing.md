# Architecture delta — Q3: is this still load-bearing?

**Status**: PROPOSED, awaiting sign-off. Not implemented.
**Date**: 2026-09-01
**Requires sign-off because**: PROJECT.md ARCHITECTURE/INVARIANTS — "a proposed change that
contradicts one is an architecture delta and requires explicit user sign-off before
implementation (#1467)." This adds a third question to DEFINITION OF DONE and a constraint on
the system's own growth. Both are architecture, not scope.

---

## 1. The problem, measured

The active goal is **"Enforcement Proven Everywhere, and Smaller."** The first half has
mechanisms. The second half has none — nothing measures size, so it only grows.

Measured on 2026-08-31/09-01:

| Signal | Value | Source |
|---|---|---|
| Checks in one hook behind one 5s timeout | **51** | `docs/audits/unified-pre-tool-51-check-audit.md` |
| Hook-timeout breaches in one week, each silently dropping **all 51** | **266** | active goal §v4 baseline |
| Gates that ship and cannot fire | **5 of 9** | #1612 |
| Failing tests in `tests/unit tests/integration` | **582** (was 592) | this session, measured |
| Prunable test candidates against a <500 target | **2,394** | `/improve` digest, TEST-PRUNING |
| Open issues; filing vs resolving | **290; 4.5x** | active goal §2 |
| `sessions_v2.db` size / staleness / `enforcement_events` rows | **123 MB / 4 months / 0** | this session, measured |
| Guards found dead this session | **3** | protect-sensitive (4 ways), pre-commit (293 days), 4 unreachable message blocks |

Three artefacts shipped and did nothing. One had its own test suite agreeing with it. One
could not refuse for 293 days in the repository where all enforcement is developed. A full
event schema for `enforcement_events` exists with zero rows.

**The signature**: this system grew by accretion. Every failure added a control; nothing ever
removed one; almost nothing proves a control still works. Dead checks are not merely inert —
they consume the shared 5-second budget and take the live checks down with them.

## 2. Why the existing DEFINITION OF DONE does not catch this

PROJECT.md asks two questions of every artefact:

- **Q1 — is it CONNECTED?** A machine-checkable route must invoke it.
- **Q2 — does it WORK AS DESIGNED?** Both arms, on the real thing.

Both are asked **once, at ship time**. Neither is ever asked again. An artefact that satisfied
Q1 and Q2 in March and has refused nothing since is indistinguishable, today, from one that
refuses weekly. That is exactly how 51 checks accumulate behind one timeout.

## 3. The change

**Add Q3 to DEFINITION OF DONE — and ratchet it.**

> **Q3 — Is this still load-bearing?**
> Every mechanism must, within a rolling window, either show a refusal receipt, or be
> explicitly PINNED as dormant with a stated reason, or be deleted. The count of unproven
> mechanisms is pinned and may only decrease.

This is deliberately shaped as an **extension of an existing corpus**, per PROJECT.md's own
rule ("extending an existing corpus beats adding a mechanism"), and it reuses the ratchet
pattern that PROJECT.md already calls "the only thing that has ever caught one of these
automatically."

### Why a ratchet and not a rule

A rule is prose. This session recorded prose failing in both directions within one hour. The
two existing ratchets — `test_hook_reachability_ratchet.py` (`REACHABILITY_CEILING`,
`CEILING_HIGH_WATER_MARK`, `PINNED_UNREACHABLE`) and `test_refusal_sink_ratchet.py`
(`SANCTIONED_SINKS`) — are the only mechanisms here with a track record of catching this class
unprompted. Q3 follows their vocabulary and their failure-message style rather than inventing a
third.

## 4. Three parts, in order. Each independently revertable.

### Part 1 — Turn on what is already free (0 lines of code)

Claude Code ships OpenTelemetry (`CLAUDE_CODE_ENABLE_TELEMETRY=1`) and instruments its own hook
dispatcher: `Hook execution start`, `Hook execution complete`, `Hook registered`. The `console`
exporter writes to stdout with **no collector and no network call**.

- Configure `console` exporter, redirect to a file under `.claude/logs/`.
- **INV-8 safe**: this is observability, never a gate. Nothing refuses on it. If it is absent,
  nothing degrades.
- **Known limits, stated up front**: it reports which hook ran, when, and its exit code. It
  cannot see what a hook's own code does internally, and Claude Code does **not** propagate
  `OTEL_*` to hook subprocesses. This narrows an investigation to a hook and a time window; it
  does not attribute a file mutation.

### Part 2 — The Q3 ratchet (the architecture delta proper)

Pin, and refuse growth on, the counts that measure size:

- checks registered in `unified_pre_tool.py`
- mechanisms with no refusal receipt in the window (the Q3 count)
- prunable test candidates
- failing tests in the canonical scope

Each gets a `CEILING` and a `HIGH_WATER_MARK` in the established idiom. Growth fails; reduction
requires lowering the pin. Dormant-but-wanted mechanisms go in an explicit `PINNED_DORMANT`
list with a reason, exactly as `PINNED_UNREACHABLE` works today — so "we know it hasn't fired
and we want it anyway" is a recorded decision rather than an absence.

### Part 3 — The mutation chokepoint (subtraction, not addition)

Shared gating state is currently mutated through **five** unaudited paths in
`pipeline_completion_state.py`: `clear_session` (:2542), `_write_state` (:731),
`_atomic_write_state` (:668), `_locked_rmw` (:2587), `_gc_stale_states` (:3025). None records
who, when, or before/after. Verified this session: when a ledger was destroyed mid-run,
**nothing recorded it**, and four candidate mechanisms were refuted without identifying the
cause.

Consolidate to **one** `flock`-guarded chokepoint that appends
`{ts, pid, hook, session, action, before_hash, after_hash}` before applying any mutation.

- Five entry points become one. **Net surface decreases.**
- Reuses `hook_telemetry.py`'s existing atomic-append + scrubbing machinery (727 lines already
  shipped) rather than adding a format.
- `_in_locked_rmw()` (:663) already exists to detect nested-lock reentry — the deadlock hazard
  is already solved in-house.
- ~100–150 lines. External research rejected every off-the-shelf option: `agents-observe`
  (Docker + Node + React — minimalism), Langfuse/Braintrust (hosted — INV-8), `eslogger` (root
  + prospective-only, cannot answer after the fact).

## 5. Which invariants this touches

| Invariant | Effect |
|---|---|
| **INV-1** enforcement is hooks not nudges | **Reinforced.** Q3 is a ratchet that refuses, not prose. |
| **INV-7** gating state fails closed | **Touched by Part 3.** The chokepoint changes *how* gating state is written. It must preserve the existing fail-open-on-lock-failure behaviour; a telemetry failure must never block a mutation. |
| **INV-8** local-first and free | **Must be preserved.** Part 1 is observability only; no gate may ever depend on it. |
| **INV-5** one topic, one home | **Reinforced.** Part 3 collapses five mutation homes into one. |
| ARCHITECTURE four-layer model | **Extended, not replaced.** Q3 sits in DEFINITION OF DONE alongside Q1/Q2. |

## 6. The honest risk

**Adding a control to fight having too many controls is recursive, and I cannot fully dismiss
it.** The counter-argument is that the two existing ratchets are ~50-line test modules that
constrain hundreds of artefacts, and PROJECT.md names the reachability ratchet as the only
thing that has ever caught this class automatically. The leverage is real but the irony is
also real, and it should be recorded rather than argued away.

**Mitigation**: Part 2 ships with its own abort condition. If the Q3 count does not decrease
within two cycles, the ratchet is the wrong instrument and should be deleted rather than
tuned.

**Second risk**: pinning a count invites satisfying the count rather than the intent — deleting
cheap checks to make room for new ones. `PINNED_DORMANT` requires a stated reason per entry,
which makes that visible, but does not prevent it.

## 7. What this does NOT propose

- No change to the 8-step pipeline shape (INV-3).
- No change to the agent roster (INV-2, and CLAUDE.md's explicit protection).
- No new hosted service, no new dependency, no Docker, no daemon.
- No deletion of any check as part of this change. Part 2 *measures and pins*; the subtraction
  it forces is separate, reviewable work.

## 8. Acceptance criteria

- [ ] 1. Part 1 emits hook-execution events to a local file with **no network call** — proven by
      running with the network path unavailable, not by assuming.
- [ ] 2. No gate anywhere reads the telemetry file. Proven by grep, and by deleting the file and
      observing every gate still function.
- [ ] 3. The Q3 ratchet fails when an unproven mechanism is added, and passes at the pinned
      ceiling. Both arms, shown red before green.
- [ ] 4. Lowering the pin below the current count fails — the pin may only be tightened after
      real reduction, never loosened to accommodate growth.
- [ ] 5. Part 3: all five mutation paths route through the chokepoint. Proven by driving each
      one and observing a journal entry with correct before/after hashes.
- [ ] 6. Part 3 preserves fail-open: a telemetry write failure does not block the mutation, and
      a lock-acquisition failure behaves exactly as it does today. Both proven by fault injection.
- [ ] 7. Deleting the journal file does not change any gate's verdict.
- [ ] 8. The count of state-mutation entry points decreases from 5 to 1 — measured, stated in the
      commit.

## 9. Sequencing and cost

| Part | Cost | Reversible by |
|---|---|---|
| 1 — free telemetry | minutes, 0 lines | unsetting an env var |
| 2 — Q3 ratchet | one pipeline | deleting one test module |
| 3 — chokepoint | one pipeline | reverting one commit |

Part 1 first because it is free and immediately narrows the next investigation. Part 2 next
because it makes every subsequent decision self-correcting. Part 3 last because it is the only
one that touches gating-state code paths, and it benefits from Part 1 being live while it is
built.

## 10. What I need from you

Sign-off on the delta itself — specifically on **Q3 entering DEFINITION OF DONE**, since that
changes what may SHIP, and on **Part 3 touching INV-7 gating-state write paths**.

Parts 1 and 2 are additive and reversible. Part 3 modifies code that guards every commit in
five repositories and should not proceed on implied consent.
