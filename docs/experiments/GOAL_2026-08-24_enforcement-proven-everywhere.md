# GOAL — Enforcement Proven Everywhere, and Smaller

**Created**: 2026-08-24 · **Revised**: 2026-08-24 (v2, after critical evaluation against stated intent)
**Status**: ACTIVE
**Owner**: Andrew Kaszubski (solo dev)
**Supersedes**: `GOAL_2026-07-31.md`

---

## 1. Mission

The product's claim is that its guarantees hold. Measured 2026-08-24, they do not: **4 of 8
block-capable guards fail open silently** under fault injection *in this repo with the full
install*, and realign and spektiv have 27 hooks apiece with **0 proof artifacts**. Meanwhile
the system carries **142,869 lines** of enforcement code, 1,733 lines of agent-improvement
machinery invoked by nothing, a `SoftFailureTracker` requested by 0 tests but advertised in 2
docs, 414 tests that have never run in CI, and 262 open issues.

Both halves are the same disease. Unproven guards create false security; unused machinery
creates the impression of coverage. This goal makes enforcement **provable** and the system
**smaller** — and treats an increase in enforcement code without a matching increase in proven
guards as a failure, not progress.

Five properties, from the stated intent: **effective** (guards demonstrably fire), **simple**
(less code, no dead mechanisms), **accurate** (both arms, measured error rates), **durable**
(holds in every repo), **consistent** (one canonical mechanism per rule).

## 2. Definition of Done

**Effective — guards demonstrably fire**
- [ ] `proof_of_block.py` reports **0 guards failing open silently** (baseline: 4 of 8)
- [ ] Every guard shows a **REFUSES and a PERMITS** row — one arm does not count (#1617)
- [ ] Committed proof artifacts in **realign AND spektiv** (baseline: 0 in both)

**Simple — fewer mechanisms, not fewer lines**
- [ ] **Count MECHANISMS, not lines.** Line count is the wrong denominator — `lib/*.py` is
      120,001 of the 142,869 and is mostly non-enforcement code, so "net lines down" is
      satisfiable by deleting unrelated library code. The metric is the **named dead-mechanism
      list**, each item resolved to `WIRED` or `DELETED`, no item left `UNRESOLVED`:
      | Mechanism | Baseline | Target |
      |---|---|---|
      | Dead guards (#1612) | 5 unwired | 0 |
      | `SoftFailureTracker` | 0 tests request it, 2 docs advertise it | 0 unresolved |
      | Reviewer improvement machinery | 1,733 lines, 0 invocations | 0 unresolved |
      | genai tests calling no judge | 176 | 0 unresolved |
      | Dark test files | 95 across 7 dirs | 0 unresolved |
- [ ] **No net new mechanism without a retirement.** Each mechanism added under this goal names
      one retired or wired in the same change. Enforced by review, recorded in the ledger.
- [ ] Every deletion **names what it removed and why** — a bulk removal does not satisfy this

**Accurate — claims are measured**
- [ ] `test-master` cannot emit a test without an **observed failure against a mutated
      target**, enforced by hook (#1660 at the agent boundary)
- [ ] The improvement loop produces a **first weakness report** for at least one agent using
      **deterministic checks only** — cited `file:line` resolves, claimed commands were
      actually run, verdict stability across identical input. No LLM, no cost, not blocked.
      **Threshold: ≥3 findings, each independently confirmed true by re-running the check.**
      "≥1 finding" is satisfiable without doing the work — the #1660 defect, and it was in
      v2 of this document.
- [ ] Every mechanism shipped under this goal has a **bypass-hunt record**.
      **Threshold: ≥5 distinct evasion shapes attempted, each with a recorded outcome, and at
      least one drawn from a category the mechanism's author did not anticipate.** Ships when
      the successful-evasion list is empty or the survivors are named and accepted.

**Outcome — did the system get better at its job, not just better guarded**

Every other criterion here is internal (guards fire, mechanisms resolved, tiers bounded). This
one asks whether the product improved. Without it the goal can be fully met while the tool is
no more useful than today.

- [ ] **Rework-per-fix falls below the 2026-08-24 baseline.** MEASURED from existing git
      history, no new instrumentation: a `fix(...)` commit re-touching a production file that
      another `fix(...)` touched ≤7 days earlier, excluding `CHANGELOG.md`, `docs/`, `tests/`,
      `.claude/` and all `*.md` (those are touched by convention on every fix — counting them
      measures hygiene, not rework, and doing so inflated the raw figure from 66 to 180).
      | Window | Fixes | Rework | Rework-per-fix |
      |---|---|---|---|
      | 60→30 days ago | 40 | 15 | **37.5%** |
      | last 30 days | 76 | 66 | **86.8%** |
      Concentrated in `unified_pre_tool.py` (10×), `pipeline_completion_state.py` (6×),
      `agent_dispatch_sentinel.py` (5×).
- [ ] **The metric is controlled before it gates anything.** It currently discriminates between
      periods, which is a positive control. It still lacks a negative control: it cannot
      distinguish "fixed badly, three times" from "fixed deliberately in three passes." Until
      that is resolved the number is *tracked and reported*, never used to block.
- [ ] **Remediation cycles per pipeline run** are recorded per run and trend down. Baseline
      2026-08-24: three remediation cycles on a two-line comment fix.

**GenAI transport — standing constraint**
- [ ] **All GenAI in this system runs via `claude -p`.** Not OpenRouter, not a paid
      `ANTHROPIC_API_KEY`. Known call sites that violate this today:
      `scripts/run_reviewer_benchmark.py:69` (`Anthropic(api_key=...)`),
      `plugins/autonomous-dev/lib/genai_validate.py:82-118`, `tests/genai/conftest.py:224-232`.
- [ ] The `claude -p` invocation is **one shared helper**, not copied per call site — extending
      the proven one at `scripts/extract_and_label_intent_corpus.py:717-790`
      (`--output-format json`, `--max-turns 1`, `cwd=Path.home()` for #1064, fence stripping
      for #1065, envelope error checks)
- [ ] Design assumes the **measured** cost: 7.6s median per judgement, sequential. Any GenAI
      gate must fit that — nightly or sampled, never per-push (137 judges × 5 trials = 87 min
      against a 10-min job cap)

**Durable — it holds outside this repo**
- [ ] Every tier reports **EXECUTED=N**; a tier reporting success over zero **fails**
- [ ] `.claude/.bypass` is no longer all-or-nothing (#1647)
- [ ] Every rule discovered during this goal ends as a **hook, a shipped script, or an
      explicitly-recorded known gap** — never as prose alone
- [ ] #1663 answered with a measurement: does `claude -p` authenticate in Actions, at what
      latency, does concurrency corrupt credentials

**Consistent**
- [ ] No rule has two mechanisms; no mechanism has two divergent copies (the duplicate
      `GenAIClient` in `templates/genai-uat/` is the known instance)

**Self-applying — the detector is subject to its own rules**
- [ ] Every mechanism built under this goal is **itself** subject to the rules it enforces: it
      has both arms observed, a bypass-hunt record, and an entry in the dead-mechanism ledger
      if it stops being invoked. No mechanism is exempt because it is the one doing the checking.
- [ ] **When the detector misses something, that becomes a filed finding against the detector.**
      Concretely: any defect found by a human, an agent, or a later session that a shipped gate
      *should* have caught results in an issue naming the gate that missed it — not only the
      defect. Baseline evidence this is needed: the four silent fail-opens were found by fault
      injection, not by any gate; the #1620 fix was flagged as undeployed four times by a
      findings store nobody read; and this goal's own v2 contained the exact tautology defect
      filed as #1660 four hours earlier.

## 3. Scope Boundaries

**In scope** — the 4 silent fail-opens; cross-repo proof in realign and spektiv; deletion of
dead mechanisms; `test-master` output enforcement; the deterministic half of the agent
improvement loop; tier-execution honesty; bypass granularity (#1647); the #1663 spike.

**Out of scope, with reasons** — draining the 262 backlog (volume is the symptom; it grew from
108 while guards rotted). The genai tier's LLM half and agent calibration corpora (#1566,
#1664): gated on #1663, and the measured 7.6s/judgement → 87 min against a 10-min cap means
redesign, not migration. anyclaude: no install detected.

## 4. Success Criteria

| Criterion | Verification | Threshold | Source |
|---|---|---|---|
| No silent fail-open | `python3 plugins/autonomous-dev/scripts/proof_of_block.py` | 0 silent fail-opens | MEASURED: 4 of 8 |
| Both arms per guard | same | every guard REFUSES **and** PERMITS | #1617 |
| Proof in consumer repos | run in `~/Dev/realign`, `~/Dev/spektiv` | artifact committed, exit 0 | MEASURED: 0 |
| System smaller | `cat plugins/autonomous-dev/{hooks,lib}/*.py \| wc -l` | **< 142,869** | MEASURED 2026-08-24 |
| Dead mechanisms resolved | per-item check | 0 remaining unwired | 5 guards, tracker, 1,733 lines, 176 tests |
| test-master enforcement | write a test with no failure-proof | REFUSED; proven one PERMITTED | #1660 |
| First weakness report | the deterministic loop | ≥1 agent, ≥1 finding, no LLM invoked | new |
| Bypass-hunt per mechanism | the record | evasions listed with outcomes | new |
| Tier honesty | CI on master | every tier prints EXECUTED=N; N=0 fails | integration precedent |

## 5. Milestones

| Date | Deliverable | Verification |
|---|---|---|
| **2026-08-27** | **`test-master` failure-proof enforcement** — mechanics before tests | Both arms observed; bypass-hunt recorded |
| 2026-08-29 | Deterministic weakness report for one agent | Report exists, ≥1 finding, 0 LLM calls |
| 2026-08-31 | 4 silent fail-opens fixed; #1663 answered | `proof_of_block` → 0; spike numbers recorded |
| 2026-09-03 | Dead mechanisms deleted or wired | Enforcement line count below baseline |
| **2026-09-07** | **MID-POINT ABORT REVIEW (§7)** | ≥1 consumer proof artifact; line count down |
| 2026-09-14 | Collected-floor generalised; dark tiers resolved | EXECUTED=N per tier; 95 → stated |
| 2026-09-21 | Cross-repo proof in realign and spektiv | Committed artifacts, both repos |

## 6. Tracking

**Must close**: #1612, #1617, #1636, #1647, #1660, #1661, #1662, #1663
**Re-scope or defer**: #1566, #1664 (gated on #1663)
**Artifacts**: this document; `tests/proofs/` in realign and spektiv; the bypass-hunt records;
the first deterministic weakness report
**Memory**: `feedback_enforcement_not_memory.md`, `project_pipeline_gate_history.md`

## 7. Abort Conditions

1. **Mid-point stall (2026-09-07)** — no consumer-repo proof artifact by this date. Pivot:
   re-scope to autonomous-dev only; file the cross-repo work as its own goal.
2. **Transport dead-end** — #1663 returns no $0 path. Pivot: stop the calibration and genai
   threads; re-scope around what is possible at $0. Do not design against a transport that
   does not exist.
3. **Enforcement regression** — `proof_of_block.py` reports more than 4 silent fail-opens at
   any milestone. Pivot: freeze feature work, fix the regression first.
4. **Complexity regression** — the dead-mechanism list has **more UNRESOLVED items** at the
   mid-point than at baseline, or a mechanism was added without a retirement. Pivot: stop
   adding, resolve first. Adding to a system already carrying 142k lines of unproven
   enforcement is how this state was reached.
5. **Schedule abort (v3 — the time-box must bite).** If **two or more milestones** slip past
   their dates, STOP and re-scope. v2 said slip "is expected and is not itself an abort
   trigger," which neutered the time-box that was chosen as the kill switch — a schedule with
   no consequence is decoration. Velocity evidence for the scepticism: on 2026-08-24 a
   **two-line comment fix** consumed a full pipeline and three remediation cycles. Milestone
   dates below are estimates against that observed rate, not aspirations.

## 7a. Known-red CI is in scope, not deferred

"Consistent" cannot hold while tiers that DO run fail constantly. Baseline MEASURED
2026-08-24: unit **104** failures, regression **205**, integration **521** (ratcheted).
- [ ] Every running tier has a **pinned failure ceiling that may only decrease** — the
      integration ratchet generalised, so a tier that runs and fails 205 times is bounded
      rather than ignored
- [ ] No tier is left both running and unbounded. A permanently-red unbounded tier trains
      dismissal of the whole class, which is how the integration tier stayed dark for months.

## 8. Progress Ledger

- `proof_of_block.py` — headline metric, on demand
- `cat plugins/autonomous-dev/{hooks,lib}/*.py | wc -l` — the simplicity metric
- `gh issue list --state open | wc -l` — 262 at baseline (MEASURED 2026-08-24)
- `collect_cia_findings()` over `.claude/logs/findings/` — readable since #1658
- This document, updated per milestone with deltas named

---

**Risks stated at creation.** (a) The headline metric depends on two repos whose roadmaps this
goal does not own — abort 1 catches that at the mid-point. (b) The net-DOWN criterion can be
gamed by deleting tests rather than dead code; every deletion must name what it removed and
why, and the dark-tier item requires a stated reason per file rather than a bulk removal.
(c) Seven milestones in four weeks against a 262-issue backlog and a red CI is aggressive;
milestone slip is expected and is not itself an abort trigger — only the four conditions above are.
