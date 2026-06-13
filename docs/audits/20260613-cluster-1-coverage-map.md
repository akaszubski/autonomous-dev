# Cluster [1] CI#1 — Coverage Map + Drain Sequence

**Date**: 2026-06-13
**Source**: `/triage --auto-improvement` output (29 issues, rank 28.5, shared_files: `commands/implement.md`, `agents/implementer.md`)
**Goal**: Map each cluster issue to existing plan coverage; sequence the drain; surface residual issues that need new plans.

## Verdict

The cluster is **not** a design problem. Of 29 issues, **15 are covered by existing plans** (5 plans, 1 PROCEED'd, 4 drafted-without-critique). The remaining **14 issues** group into **5 small structural-change themes** that need new (smaller) plans.

The bottleneck is implementation drain + plan-critic completion, not new design.

## Coverage Map

### Bucket A — Covered by PROCEED'd plan, ready to /implement now

**Verified 2026-06-13: M0 is SHIPPED. The 4 cluster issues are NOT retired by it.**

| Plan | Status | Reality |
|---|---|---|
| [`m0-pipeline-state-isolation.md`](../../.claude/plans/m0-pipeline-state-isolation.md) | SHIPPED 2026-05 | Sub-issues #1045/#1046/#1047/#1048 all CLOSED. Umbrella #1041 still OPEN but the work is at HEAD: `run_id` kwarg in pipeline_completion_state.py, `acquire_run_lock`/`release_run_lock` in pipeline_state.py:965/990, `secrets.token_hex(8)` at implement.md:304, `_gc_stale_states` at pipeline_completion_state.py:1446, all 5 new test files exist. |

**The 4 sentinel cluster issues post-date or describe surfaces M0 explicitly SCOPED OUT:**
- #989 (2026-04-26) — legacy sentinel cleared mid-pipeline. M0 kept legacy sentinel touched (R7, intentional cross-run signal). Residual bug.
- #1206 (2026-06-11, post-ship) — cross-repo /tmp collision on legacy sentinel. M0 created per-run paths but legacy sentinel is still machine-global.
- #1184 (2026-06-09, post-ship) — implementer self-validation, consecutive-run regressions from shared /tmp test state. Different surface.
- #1139 (2026-05-31, post-ship) — git stash mid-pipeline (coordinator state-manipulation pattern). Not state-isolation.

**Bucket A is empty.** These 4 issues need their own plans — moved to Bucket C themes below.

### Bucket B — Drafted plan exists; needs plan-critic loop to PROCEED before /implement

| Plan | Cluster issues it covers | Critique gap |
|---|---|---|
| `phase2-classifier-robustness.md` | #983, #986, #1149 | No status line — needs Round 1-3 |
| `root-cause-hard-gate-fix-pipeline.md` | #1210 | No status line — needs Round 1-3 |
| `macro-first-continuous-improvement.md` | #1002, #1031, #1178, #1195 | No status line — needs Round 1-3 |
| `mode-gating-rollout.md` | #1073, #1106 | No status line — needs Round 1-3 |

11 issues covered. Each plan needs `/plan` resumed to drive critique to PROCEED, then `/implement`.

### Bucket C — NOT covered by any existing plan — need NEW plans

14 residual issues grouping into 5 themes:

#### C1: STEP_ORDER registry — coherence between code, hook, spec, and validation

**Issues**: #1148 (parallel decided, sequential run), #1181 (doc-master before security-auditor in --light), #1211 (CIA STEP 13 vs STEP 15 drift), #1213 (commit-gate `issue_number=0`), #1214 (`set_validation_mode` rejects `issue_number` kwarg)

**Root cause**: `STEP_ORDER` registry exists in `lib/pipeline_intent_validator.py:74` and `lib/agent_ordering_gate.py:17`. The spec markdown (`commands/implement.md`), the agent-completeness commit gate (`lib/pipeline_completion_state.py`), and the function signatures (`set_validation_mode`, `verify_pipeline_agent_completions`) drift from it independently. The registry is a single source — its consumers are not.

**Fix shape**: Extend STEP_ORDER consumers; align kwarg signatures; ratify CIA at the step the spec actually places it.

**Size estimate**: 4-5 files.

#### C2: Coordinator pre-pipeline discipline

**Issues**: #936 (coordinator pipeline starts before verifying issue is not already merged), #1129 (file exploration before STEP 1 — FORBIDDEN pre-pipeline investigation)

**Root cause**: Coordinator does work BEFORE STEP 1 (file reads, merge-status checks, baseline diffs) that is supposed to be inside the pipeline. The HARD GATE is prose-advisory in `commands/implement.md`; no hook detects pre-STEP-1 tool use.

**Fix shape**: PreToolUse hook that, between session-start and STEP-1-active-sentinel, blocks Read/Grep/Glob/Bash unless explicitly allowlisted (status checks). Pairs with a documented STEP 0 phase for the legitimate pre-pipeline operations (merge status, issue body fetch).

**Size estimate**: 2-3 files (hook addition + spec STEP 0 clarification + regression test).

#### C3: HARD GATE prose → hook backing retrofit

**Issues**: #1055 (Evidence Manifest HARD GATE prompt-advisory only), #1209 (CIA subagent Bash write to `.claude/local/` silently fails — coordinator must use Write)

**Root cause**: 43 "HARD GATE" / "FORBIDDEN:" strings in `commands/implement.md` + `agents/implementer.md`. Of these, an unknown subset is prompt-advisory only — no JSON `{decision: "block"}` enforcement. Memory rule already established: "Hard blocking > nudges" (2025 hypersensitivity paper).

**Fix shape**: Audit pass — inventory every HARD GATE/FORBIDDEN string; for each, label as `(enforced)` with hook reference, or `(advisory — backed by output gate at <coordinator check>)`, or remove. Add hooks where backing is feasible and the gate is load-bearing.

**Size estimate**: 1 audit doc + ~3-5 hook additions + tests.

#### C4: Plan-critic policy registry

**Issues**: #1145 (security-sensitive changes need more rounds), #1155 (plan-critic skip fires on self-assessed provisional verdict — adversarial review bypassed)

**Root cause**: Plan-critic rounds count and skip conditions are decided ad-hoc by the coordinator. `commands/plan.md` says minimum 3 / maximum 5, but the skip-on-provisional path (#1155) lets the coordinator bypass the loop entirely.

**Fix shape**: Declarative critique policy table: signals → rounds. `has_security_changes ⇒ min 4 rounds`, `complexity ≥ N ⇒ min 4 rounds`. Remove skip-on-self-assessed-provisional; PROCEED must come from the critic, not the planner.

**Size estimate**: 2-3 files (`commands/plan.md`, `agents/plan-critic.md`, regression test).

#### C5: spec-validator depth + planner enumeration gaps

**Issues**: #1147 (spec-validator does not detect tautological `parametrize` assertions), #1182 (planner prompt missing call-boundary enumeration step)

**Root cause**: spec-validator and planner have known prompt/logic gaps. Each is small, but they share the meta-pattern: the gate doesn't check what it claims to check.

**Fix shape**: Two independent micro-plans, NOT one structural change. Best filed as standard fix issues + small targeted PRs, not a redesign.

**Size estimate**: 1-2 files each, separate PRs.

#### C6: result_word_count race (singleton)

**Issue**: #1179 (`result_word_count` undercount persists after #872 fix — transcript partial-flush race)

**Root cause**: Race between agent output flush and transcript read. Singleton, no structural angle.

**Fix shape**: Fix the race (add flush barrier or read-after-completion signal). Not part of a redesign.

**Size estimate**: 1-2 files.

## Drain Sequence (recommended) — UPDATED 2026-06-13 after closure session

| Order | Action | Retires | Status |
|---|---|---|---|
| 1 | M0 already shipped at HEAD; close umbrella | #1041 umbrella | DONE (commit pre-session) |
| 2 | Cluster singletons (set_validation_mode, multi-scope writer) | #1213, #1214, #1106 | DONE (`fb0455b`) |
| 3 | gh-issue-create argv-position-aware | #1215 | DONE (`f0c4467`) |
| 4 | Planner call-boundary + spec-validator tautology | #1147, #1182 | DONE (`8520fea`) |
| 5 | CIA moved to STEP 12.5 (gate↔spec coherence) | #1211 | DONE (`70adbd9`) |
| 6 | CIA persistence (Bash writes silently fail) | #1209 | DONE (`d1acd65`) |
| 7 | STEP 10 single-message + LIGHT security escalation | #1148, #1181 | DONE (`f68b952`) |
| 8 | implement-fix STEP F4.7 PROD verification | #1210 | DONE (`13a46fa`) |
| 9 | Plan-critic policy registry | #1073, #1145, #1155 | DONE (`7a102ef`) |
| 10 | Resume protocol + bypass docs | #1149, #1040 | DONE (`2592989`) |
| 11 | Evidence Manifest gate (advisory → mechanical) | #1055 | DONE (`ce682ab`) |
| 12 | Prompt-integrity context-aware threshold | #1002, #1031 | DONE (`744c5a9`) |
| 13 | STEP 0a Pre-Flight Reconnaissance | #936, #1129 | DONE (`6f8b0af`) |

### Residuals remaining

Cluster [1] reduced 29 → 8. Remaining issues each need significant code work or a separate plan:

| Issue | Type | Why heavier |
|---|---|---|
| #989 | sentinel residual | M0 SCOPE OUT (R7: legacy sentinel preserved as cross-run signal). Needs new design for the cross-run signal mechanism. |
| #1206 | sentinel residual | Legacy `/tmp/implement_pipeline_state.json` is machine-global by design. Cross-repo collision needs per-repo prefix. |
| #1139 | bypass detection | git stash mid-pipeline as coordinator state manipulation. Needs hook detection. |
| #1184 | test state isolation | Consecutive-run regressions from shared /tmp. Needs per-run test fixture isolation. |
| #983 | classifier accuracy | bugfix_detector misclassifies gh_issue_create_block flakiness. Covered by `phase2-classifier-robustness` plan — needs critique to PROCEED. |
| #986 | classifier accuracy | Timing analyzer emits false WASTEFUL findings on user-pause spans. Same plan as #983. |
| #990 | test scope | Coordinator vs implementer use different test scope at STEP 5. Needs shared `get_test_scope()` lib. |
| #1178 | observability | prompt-integrity recovery latency invisible. Needs structured PromptIntegrityBlock/Recovery events + timing_analyzer integration. |
| #1179 | race condition | result_word_count undercount from transcript partial-flush race. Needs SubagentStop settling delay + supplemental log. |

## Deferred / Out of Scope

These are in the broader queue but **not** in Cluster [1] and should be addressed separately:

- **Test pyramid health** (#908, [ROOT-CAUSE]) — separate refactor, own audit
- **Trends aggregate** (#1112) — analytical, not pipeline-structural
- **Feature requests** (#1160 `/goal`, #1161 file-placement, #1162-#1165 CC-native redundancy) — roadmap, not bugfix
- **Singletons rank ≤1** that don't touch `commands/implement.md` or `agents/implementer.md` — handled by their own surface

## Dogfooding Constraint Preserved

Every action in the drain sequence is itself a pipeline run (`/plan` then `/implement`). Self-maintenance mode (cwd inside `plugins/autonomous-dev/.claude-plugin/marketplace.json` tree) handles the routine path. `.claude/.bypass` is reserved for emergencies. No proposed change relies on either for normal operation.

## Linked Issues

N/A — this is an audit/coverage document, not an implementation plan. Each item in the drain sequence has its own existing plan or will get a new plan when its turn comes up.
