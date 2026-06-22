---
covers:
  - plugins/autonomous-dev/commands/drain-queue.md
  - plugins/autonomous-dev/lib/drain_queue_state.py
  - plugins/autonomous-dev/lib/drain_runner.py
  - plugins/autonomous-dev/lib/drain_pending.py
  - plugins/autonomous-dev/lib/issue_triage_analyzer.py
  - .github/workflows/drain-driver.yml
  - .github/workflows/drain-watchdog.yml
---

# ADR-002: Drain-Queue Redesign — Confidence-Based Autonomous Loop with Outcome Measurement

**Status**: Proposed
**Date**: 2026-06-21
**Tracker issue**: TBD (filed alongside this ADR)
**Bug issues**: TBD × 4 (filed alongside this ADR — severity classifier, workflow bypass, watchdog self-loop, duplicate selector)
**Supersedes**: implicit design of `/drain-queue` v1 (commits `afb9c03`, `53983cb`, `b648bdc`)

---

## Context

The `/drain-queue` system is intended to drive autonomous closure of the open `auto-improvement` issue queue per PROJECT.md's mission of "Autonomous self-improvement (closed-loop, evidence-driven) — runtime aggregation → diagnosis → fix → benchmark verify → deploy, closed loop ... HIGH confidence diagnoses applied autonomously, MEDIUM filed as issues."

**Observed reality (2026-06-21 audit)**:

- **Zero successful autonomous closures end-to-end since the system was built.** `.claude/logs/cloud-runs.jsonl` shows 15 cloud-cron fires in the past 3 days, 100% exit with `no_drainable_cluster` or `slash_command_tool_unavailable`. The GitHub Actions `drain-driver.yml` (added 2026-06-19) has 0 observed successful drains. The `drain-watchdog.yml` filed 5 `[drain-stuck]` meta-issues in 2 days but closed 0 real issues.
- **Queue at 28 open `auto-improvement` issues**; oldest is #908, 60 days old, never selected.
- **The production execution path BYPASSES `/drain-queue` entirely.** Both workflows invoke `/implement --light` directly via `claude-code-action`, skipping all six `/drain-queue` guardrails (budget, circuit-breaker, pause-flag, marker, post-push verification, history logging). The 685-line `/drain-queue` markdown command and its 1,430 LoC of state primitives are dead code in production.
- **Severity is conflated with topic.** `_infer_severity()` in `issue_triage_analyzer.py:401-429` maps any label containing the string `security` to `severity=high`. The drain selector only auto-drains `low`/`info`, so the 9 security-labeled issues in the current queue (most of which are routine `[Security advisory]` hardening tasks, not Critical CVEs) are blocked from autonomous handling.
- **Watchdog self-loop.** Filed `[drain-stuck]` meta-issues carry the `auto-improvement` label, so the selector adds them to the queue but its `is_drain_stuck_meta` filter excludes them — the queue grows by 1 per failed watchdog cycle. Net effect over 3 days: 5 watchdog alerts filed, 0 underlying issues drained, queue grew faster than it drained.
- **Selector logic is duplicated** across three locations: `drain-driver.yml:69-107`, `drain-watchdog.yml:90-137`, and the pure-function gates in `drain_queue_state.py:623-700`. The workflows inline custom Python that omits the `tag_gate` (HUMAN_GATE_TAGS check), so clusters with `breaking-change` / `auth` / `security-advisory` labels could be selected and dispatched, with the actual gate-stop happening inside `/implement` STEP 4 (where the workflow can't observe it).
- **Backwards from PROJECT.md**: the philosophy says "HIGH confidence diagnoses applied autonomously". The implementation does the opposite — only LOW severity is auto-drained. Severity (impact tier) is treated as a proxy for confidence (readiness for autonomy), but they are orthogonal dimensions. A LOW-severity finding can be HIGH-confidence (e.g., "rename variable `data` to `payload` for clarity"). A HIGH-severity finding can be LOW-confidence (e.g., "SQL injection in password reset — proposed fix may break OAuth").
- **No outcome measurement.** `DrainHistory.jsonl` is write-only by `/drain-queue` STEP 12 — but `/drain-queue` is never invoked, so the log is empty. There is no record of "drain on cluster X produced commit Y which closed issues Z". No before/after measurement. No regression detection. No auto-revert on regression. PROJECT.md's "benchmarks before/after every change, revert if regressed" is not implemented.

---

## Decision

Redesign `/drain-queue` around four invariants, structured to make each invariant testable in isolation:

### Invariant 1 — Single source of truth for cluster selection

A pure function `select_next_cluster(open_issues, state) -> Optional[Cluster]` in `drain_queue_state.py` (or a new `drain_selector.py`) becomes the only place that decides what is drainable. Both workflows and the `/drain-queue` markdown command call it directly. No inline workflow Python re-implementing selector logic.

### Invariant 2 — Workflows invoke `/drain-queue`, never `/implement` directly

The cron and watchdog workflows MUST pass through the `/drain-queue` markdown command, which is responsible for budget/breaker/pause/marker/history. `/drain-queue` then invokes `/implement --issues N` internally. Bypassing `/drain-queue` to "save a step" is forbidden; the guardrails exist specifically to prevent the silent-failure modes observed in production.

### Invariant 3 — Confidence model replaces severity model

Auto-drain eligibility is determined by **confidence** (per-finding 0.0–1.0 score), not by severity (impact tier). Severity remains useful for human triage and prioritization but is decoupled from the autonomy decision.

- New `TriageFinding.confidence: float` field, populated by the analyzer based on:
  - Explicit `confidence:high|medium|low` labels on issues (operator override)
  - Heuristic from issue body (e.g., presence of a clear proposed fix + acceptance criteria → high)
  - Defaults to `0.0` (no autonomy) when uncomputable
- `AUTO_DRAINABLE_CONFIDENCE_THRESHOLD` constant: clusters with `min(confidences) >= 0.80` are auto-drainable. Per PROJECT.md: "HIGH confidence diagnoses applied autonomously."
- Severity is retained as a separate `TriageFinding.severity` field for ranking and human dashboards but is NOT a gate.

### Invariant 4 — Outcome measurement and auto-revert

Every drain attempt produces a record in `DrainHistory` linking `cluster_id → commit_sha → closed_issues → before/after metrics`. The before/after metrics include at minimum:

- Test pass count delta (regression detector)
- Coverage delta (regression detector)
- New failing tests introduced (auto-revert trigger)

If `after.failing_tests > before.failing_tests` AND no fix is committed within 30 minutes, the system MUST automatically `git revert` the drain commit and reopen the closed issues with a `drain-reverted` label. Per PROJECT.md: "revert if regressed."

---

## Rationale

### Why these four invariants and not others

The four invariants map 1:1 to the four design flaws that the audit identified, and they are the minimum set that makes future flaws structurally impossible:

- Invariant 1 makes flaw #5 (duplicate selector) structurally impossible — only one function exists.
- Invariant 2 makes flaw #1 (workflow bypass) structurally impossible — workflows can't reach `/implement` except through `/drain-queue`.
- Invariant 3 makes flaw #2 (severity classifier mis-routing) structurally impossible — the severity classifier no longer participates in the autonomy decision.
- Invariant 4 closes the loop that PROJECT.md describes literally: aggregation → diagnosis → fix → **benchmark verify → revert if regressed**. Without it, the system is open-loop and cannot self-correct.

Flaw #4 (watchdog self-loop) is addressed as a consequence: under Invariant 2, the watchdog invokes `/drain-queue`, and `/drain-queue` writes `DrainHistory` records (Invariant 4). The watchdog's STUCK check becomes "no history records in 2h" instead of "no commits in 2h" — and meta-issues stop being filed because the watchdog can observe its own throughput directly.

### Why a confidence model and not a label-only opt-in

A pure label-only opt-in (e.g., "only drain issues with `auto-drainable` label") was considered. It is simpler but has two failures:

1. **Selection bias**: only operators paying attention add the label. The system can never learn to drain issue classes the operator hasn't pre-approved.
2. **No graceful degradation**: if the operator stops labeling for a week, the queue grows but the system has no signal that it should adjust its own thresholds.

The confidence model decouples *who decides* (operator via label override OR analyzer via heuristic) from *what is decided* (a 0.0–1.0 score that gates autonomy). It also lets future work plug in real measurement (e.g., "confidence = success rate on similar past clusters") without changing the gate.

### Why outcome measurement is non-negotiable

Without before/after measurement, the system cannot answer "is autonomous draining a net positive?" PROJECT.md says "benchmarks before/after every change, revert if regressed" — this is a load-bearing claim about the autonomous loop's safety. A loop that can introduce regressions but cannot detect or undo them is a regression-introduction engine, not a self-improvement engine.

### What this does NOT include

- **Model selection per cluster**: leaving Opus-everywhere for now. Worth revisiting after the first 10 successful autonomous closures provide cost data.
- **Per-issue cost tracking**: deferred to a Phase 2 of this redesign. Need outcome measurement first to know which costs were worth it.
- **Cross-cluster dependency ordering**: `shared_files` already exists in `TriageFinding`. Wiring it into selector priority is a Phase 2 enhancement once Invariants 1–4 are in place.
- **Replacing `/implement --light` with `--full`**: `--light` was chosen because `--full` overruns the 60-min runner budget. This is a separate problem (pipeline-step duration) and will be addressed by `/implement` profiling work, not by `/drain-queue`.

---

## Migration Plan

Sequenced so each PR is independently shippable and the system is at least as functional as today's broken state at every checkpoint.

### Phase A — Unblock the queue (1 day, 1 PR)

Targeted bug fixes that restore minimal throughput without architectural change. Without this, no further work has anything to measure.

- **Fix severity classifier**: drop `security` from `HIGH_LABEL_KEYWORDS`. Add explicit `confidence:high|medium|low` label support (no-op for now; sets up Phase C). Update `_infer_severity` docstring + unit tests.
- **Fix watchdog self-loop**: change watchdog meta-issue labels from `drain-stuck,auto-improvement` to `drain-stuck` only. Update `drain-watchdog.yml` lines 168-169. Selector already excludes `[drain-stuck]` by title prefix; the label change prevents queue inflation.
- **No selector unification yet** — Phase B handles that. Phase A keeps the duplicated logic for now (the duplication is annoying but stable).

**Exit criterion**: queue starts decreasing autonomously within 24h of merge.

### Phase B — Unify selector and route workflows through `/drain-queue` (2-3 days, 1-2 PRs)

- Extract `select_next_cluster()` as a pure function in `drain_queue_state.py`. Both workflows and the markdown command call it. Inline workflow Python is deleted.
- Modify both workflows to invoke `/drain-queue` (via `claude-code-action` + slash command) instead of `/implement --light` directly. `/drain-queue` internally invokes `/implement` with the budget/breaker/pause-flag/marker plumbing wired up.
- Workflows can keep their pre-selection step for telemetry, but the authoritative selection happens inside `/drain-queue`.

**Exit criterion**: `DrainHistory.jsonl` accumulates real records. Workflow runs are reflected in budget/breaker state.

### Phase C — Confidence model + outcome measurement (1-2 weeks, 3-4 PRs)

- Add `confidence` field to `TriageFinding`. Initial heuristic: high if issue body contains a literal `Acceptance Criteria` section + a `Proposed fix` section; medium if either present; low otherwise. Operator override via `confidence:*` label.
- Replace `AUTO_DRAINABLE_SEVERITY` with `AUTO_DRAINABLE_CONFIDENCE_THRESHOLD = 0.80`.
- Add before/after measurement: capture `pytest --co -q` count + coverage % at `PIPELINE_BASE_COMMIT`. Re-measure after drain commit. Diff → DrainHistory record.
- Add auto-revert: if regression detected AND no fix commit within 30 min, `git revert` the drain commit and reopen issues with `drain-reverted` label + ping operator.

**Exit criterion**: at least 10 autonomous drains with confidence-based selection, before/after metrics in DrainHistory, zero un-reverted regressions.

### Phase D — Cleanup and documentation (1-2 days, 1 PR)

- Retire `severity` from drain-queue documentation as an autonomy signal (keep for human dashboards).
- Update `docs/RUNBOOK.md` to reflect the new path: cron → `/drain-queue` → `/implement`.
- Migrate any remaining operator workflows from `/implement --issues` to `/drain-queue` invocations.

---

## Implementation Progress

This section tracks rolling progress against the Migration Plan phases above.

### Phase A — Unblock the Queue (COMPLETE)

- Issue #1273 (severity classifier) — CLOSED. Fix landed at `plugins/autonomous-dev/lib/issue_triage_analyzer.py:62` where `HIGH_LABEL_KEYWORDS = ("critical", "p0")` excludes `security`. The docstring at line 412 confirms: "security is a topic/area label, not a severity signal".
- Issue #1275 (watchdog self-loop) — CLOSED.
- Exit criterion ("queue size starts decreasing autonomously within 24h") status: **NOT MET** — despite both Phase A fixes shipping, the queue remains at 32+ open `auto-improvement` issues and the watchdog continues filing `[drain-stuck]` meta-issues (5+ in the last 3 days). Phase A surfaced the deeper Phase B blockers: the workflows bypass `/drain-queue` entirely (#1274), so the Phase A fixes do not flow through to operational behaviour. Phase B is now the critical path.

### Phase B — Unify selector + route workflows (IN PROGRESS)

- Issue #1274 (workflows bypass `/drain-queue`) — OPEN
- Issue #1276 (selector duplication) — OPEN

### Phase C — Confidence model + outcome measurement (IN PROGRESS)

- Issue #1290 (before/after pytest metrics capture) — SHIPPED. `drain_runner.capture_pytest_snapshot()` public function captures test count and failing-test count by running `pytest --tb=no -q` and parsing summary lines. Optional `git_ref` parameter stashes local changes, checks out the ref, runs pytest, then restores HEAD — used by `commands/drain-queue.md` STEP 4.5 to baseline test counts at `PIPELINE_BASE_COMMIT` before drain. `drain_queue_state._empty_metrics()` sentinel distinguishes "capture failed / not attempted" from zero counts (all four keys `test_count`, `failing_tests`, `coverage_pct`, `error` set to `None`). `DrainHistory.append()` records now carry `before_metrics` + `after_metrics` keys as specified by Invariant 4. Tests: 9 unit (`tests/unit/lib/test_drain_queue_history.py`) + 5 regression (`TestCapturePytestSnapshotSubprocessContract` in `tests/regression/test_drain_queue_runner_subprocess_kwargs.py`).
- Coverage delta (`coverage_pct` field): deferred — `coverage_pct` is always `None` in v1; running with `--cov` adds significant overhead and requires `pytest-cov` availability, which is not yet verified across drain targets.
- Confidence model (`TriageFinding.confidence`): not yet shipped.
- Auto-revert on regression: not yet shipped.

### Phase D — Cleanup and documentation (NOT STARTED)

Pending Phase C completion.

---

## Acceptance Criteria for the Full Redesign

The redesign is complete when ALL of the following are true (each maps to a Phase):

- [ ] Phase A: queue size on a 7-day rolling window decreases. *(BLOCKED by Phase B — see #1274; code shipped but operational flow bypassed.)*
- [ ] Phase A: zero `[drain-stuck]` meta-issues filed in any 48-hour window. *(BLOCKED by Phase B — see #1274.)*
- [ ] Phase A: tracker issues with `root-cause` label excluded from auto-drain. *(Issue #1277 demonstrated the meta-issue self-loop extends to trackers; removed `auto-improvement` label.)*
- [ ] Phase B: zero invocations of `/implement --light` from any workflow file — workflows MUST go through `/drain-queue`.
- [ ] Phase B: `DrainHistory.jsonl` records at least 1 entry per workflow run (success or failure).
- [ ] Phase C: `TriageFinding.confidence` field populated for 100% of clusters; `severity` is no longer in any drain gate condition.
- [ ] Phase C: every successful drain has a `before_metrics` + `after_metrics` record.
- [ ] Phase C: regression in test count → automatic revert with `drain-reverted` issue reopening, within 30 min.
- [ ] Phase D: `docs/RUNBOOK.md` and `plugins/autonomous-dev/docs/COMMANDS.md` reflect the new flow.
- [ ] Phase D: `grep -rn 'auto-drain.*severity' plugins/` returns zero results.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Phase A unblocks the queue but a wave of bad auto-drains happens before Phase C lands | Medium | High | Phase A also adds the `auto-drainable` opt-in label as a safety belt — only opt-in issues drain until Phase C confidence model lands. |
| Auto-revert false positives churn the queue | Medium | Medium | Auto-revert requires (a) NEW failing tests AND (b) 30-min delay so a follow-up fix commit can suppress. Conservative trigger. |
| Confidence heuristic mis-tunes and over-drains | Low | High | Phase C ships with the threshold at 0.80 (very conservative). Threshold lives as a module constant — tunable via PR. Phase C also requires the same opt-in label as Phase A for the first 30 days post-merge as a belt-and-braces. |
| Phase B `claude-code-action` integration with slash commands proves unreliable | Medium | High | `claude-code-action` supports `SlashCommand` per the existing workflow's `allowed_tools: SlashCommand`. If reliability issues emerge, fallback is to keep the workflow's inline `/implement` invocation but have it write to `DrainHistory` directly before/after (preserves Invariant 4 even if Invariant 2 partially fails). |
| Existing `DrainBudget`/`CircuitBreaker`/`PauseFlag` primitives need significant rework | Low | Medium | Audit shows these are correctly implemented but unused. Phase B wires them in; no rewrite needed. |

---

## What This Does NOT Address

- **Watchdog vs driver duplication**: the two workflows (`drain-driver.yml`, `drain-watchdog.yml`) have overlapping but distinct purposes (continuous drainer vs stuck-detector). Phase B unifies their selection logic but keeps them as separate workflows. A future ADR may consolidate them once the confidence model proves out.
- **Cloud-cron substrate**: the `.claude/logs/cloud-runs.jsonl` telemetry from a non-GH-Actions cron path is observably broken (lacks SlashCommand/gh CLI). This redesign deprecates that substrate in favor of GH Actions exclusively. A separate ADR (or this one's appendix) should document the deprecation.
- **Per-cluster cost tracking**: deferred to a follow-up after Phase C provides outcome data to attribute costs against.
- **Multi-repo drain**: this ADR is single-repo. Cross-repo drain coordination is out of scope.

---

## References

- PROJECT.md lines 88–102 — Four-layer system, autonomous self-improvement requirements.
- MEMORY.md — "Hard blocking > nudges" principle (informs Invariant 4's revert-on-regression).
- `docs/audits/20260606-state-audit.md` — prior state-management audit.
- Commits `afb9c03` (initial `/drain-queue`), `53983cb` (durability hardening), `b648bdc` (drain-driver workflow), `28f68ec` (Sonnet→Opus runner override), `28f68ec`/`a8923cf` etc. (post-hoc fixes).
- `.claude/logs/cloud-runs.jsonl` — production telemetry showing 100% failure rate.
- 4 bug issues filed alongside this ADR (severity classifier, workflow bypass, watchdog self-loop, duplicate selector).
