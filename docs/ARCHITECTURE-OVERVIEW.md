---
covers:
  - plugins/autonomous-dev/agents/
  - plugins/autonomous-dev/skills/
  - plugins/autonomous-dev/lib/
  - plugins/autonomous-dev/hooks/
  - plugins/autonomous-dev/commands/
---

# Architecture Overview

Complete technical architecture for the autonomous-dev plugin, including agents, skills, libraries, hooks, and model tier strategy.

**Component Counts**: 16 agents (18 archived), 20 skills, 24 active commands, 224 libraries, 31 active hooks (62 archived).

**Last Updated**: 2026-04-25

---

## Agents

Specialized agents with skill integration for autonomous development. See [AGENTS.md](AGENTS.md) for complete details. See component counts at the top of this file.

**Key Features**:
- Native skill integration (Issue #143): Agents declare skills via `skills:` frontmatter field - Claude Code 2.0 auto-loads skills when agent spawned
- Adaptive STEP 10 validation: parallel mode by default (all three agents launched simultaneously for low-risk changesets); sequential mode for security-sensitive files (reviewer → security-auditor strict ordering, doc-master in background alongside reviewer)
- Pipeline agents used in `/implement`, utility agents for specialized tasks

---

## Model Tier Strategy

Agent model assignments optimized for cost-performance balance (16 active agents):

**Tier 1 (Haiku)** - Fast, cost-effective for pattern matching
- researcher-local - Search codebase patterns
- test-coverage-auditor - AST-based coverage analysis
- issue-creator - GitHub issue creation

**Tier 2 (Sonnet)** - Balanced reasoning for judgment tasks
- researcher - Web research and synthesis
- reviewer - Code quality gate (correctness, test coverage, security, performance, maintainability, observability)
- security-auditor - OWASP security scanning
- doc-master - Semantic documentation drift detection
- continuous-improvement-analyst - Pipeline QA and gaming detection
- retrospective-analyst - Intent evolution and session drift detection
- ui-tester - E2E browser testing via Playwright MCP (optional, STEP 9.7)
- mobile-tester - iOS/Android E2E testing via Appium MCP + Maestro (optional, STEP 9.8)

**Tier 3 (Opus)** - Deep reasoning for complex synthesis
- planner - Architecture planning
- implementer - Code implementation
- test-master - Quality Diamond test generation
- spec-validator - Spec-blind behavioral validation (STEP 8.5)
- plan-critic - Adversarial plan reviewer; challenges assumptions, scope creep, and minimalism before implementation (Issue #814)

**Performance Impact**: Optimized tier assignments reduce costs by 40-60% while maintaining quality.

**Prompt Engineering**: Agent prompts follow empirically-grounded patterns — constraint budgets (MOSAIC), register shifting, persona anti-pattern avoidance (PRISM), and HARD GATE structure. See [docs/PROMPT-ENGINEERING.md](PROMPT-ENGINEERING.md) and [docs/model-behavior-notes.md](model-behavior-notes.md) for the full reference.

---

## Skills

Specialized skill packages using progressive disclosure to prevent context bloat. See component counts at the top of this file.

**How It Works**:
- Agents declare skills in `skills:` frontmatter field, auto-loaded when spawned
- Each skill declares `allowed-tools:` for least privilege
- Compact SKILL.md files with detailed content in docs/ subdirectories

**Active Skills** (20 total):
- **Core**: python-standards, testing-guide, api-design, documentation-guide
- **Code Quality**: code-review, refactoring-patterns
- **Error & Debugging**: error-handling, debugging-workflow
- **Security & Observability**: security-patterns, observability
- **Integration & Design**: library-design-patterns, api-integration-patterns, state-management-patterns, architecture-patterns
- **Workflow & Research**: git-github, research-patterns, planning-workflow
- **Validation**: scientific-validation
- **Prompt Engineering**: prompt-engineering (constraint budgets, register shifting, HARD GATE patterns — see [docs/PROMPT-ENGINEERING.md](PROMPT-ENGINEERING.md))
- **Content Allocation**: content-allocation (one-topic-one-home routing, size budgets, CLAUDE.md/PROJECT.md/MEMORY.md de-dup — used by `/align --content`)

---

## Libraries

Reusable Python libraries for security, validation, automation, and more. See [LIBRARIES.md](LIBRARIES.md) for complete API documentation.

**Design Pattern**: Progressive enhancement, two-tier design (core logic + CLI), non-blocking enhancements

**Key Libraries**:
- **Security**: security_utils.py, mcp_security.py, sandbox_enforcer.py, agent_ordering_gate.py (pure-logic pipeline ordering decisions — no I/O), secret_patterns.py (shared credential/OWASP patterns — single source of truth for hooks and active scanner), active_security_scanner.py (dependency audit, credential history scan, OWASP pattern scan — used by security-auditor STEP 0)
- **Validation**: validation.py, alignment_validator.py, project_validator.py
- **Automation**: unified_git_automation.py (git operations), batch_processor.py, session_tracker.py
- **State Management**: session_state_manager.py (session persistence), batch_state_manager.py, user_state_manager.py, session_resource_manager.py (resource tracking), pipeline_state.py (pipeline progression tracking), pipeline_completion_state.py (agent ordering enforcement state — completions written by session tracker, launches written by pre-tool hook, both read by pre-tool hook for ordering decisions)
- **Infrastructure**: path_utils.py, performance_timer.py, agent_tracker.py, pipeline_timing_analyzer.py, pipeline_efficiency_analyzer.py (cross-run efficiency analysis — model tier recommendations, token trend detection, IQR outlier detection; CIA check #14), test_pruning_analyzer.py (AST-based test hygiene — detects orphaned imports, archived refs, zero-assertion tests, duplicate coverage, and stale regressions; used by `/sweep --tests`), test_issue_tracer.py (test-to-issue traceability — maps tests to GitHub issues, flags untested issues, orphaned pairs, and untraced tests; used by `/audit --test-tracing` and STEP 13 non-blocking warning), test_lifecycle_manager.py (composition layer — orchestrates TestIssueTracer, TestPruningAnalyzer, tier_registry, and coverage_baseline into a unified `TestHealthReport`; used by `/improve` STEP 2.7 and continuous-improvement-analyst check #12), dependabot_tracker.py (Dependabot security issue tracker — queries GitHub Dependabot API for open vulnerability alerts and auto-creates deduplicated tracking issues for critical/high severity and weekly batch issues for medium severity; invoked non-blocking at STEP 13 in `/implement`; Issue #767), coordinator_log.py (coordinator-side fallback for background agent completion logging — writes JSONL activity entries tagged `"source": "coordinator_fallback"` when SubagentStop hook fails to fire for background agents; convenience wrapper `ensure_doc_master_logged()` for the most common case; Issue #868), hook_recovery.py (hook recovery telemetry and stale-state cleanup — `log_block_with_recovery()` is now a **deprecated shim** (Issue #972) that delegates to `hook_telemetry.log_block_event()`; calls still work but emit a `DeprecationWarning` — new code should use `hook_telemetry.log_block_event` directly; `clear_stale_state()` removes sentinel files owned by different sessions; `can_user_recover()` checks the exemption registry; `is_recovery_disabled()` reads `HOOK_RECOVERY_DISABLED` env var; Issue #970), hook_telemetry.py (unified hook block telemetry — single canonical surface for all three deny shapes; writes to `.claude/logs/hook-blocks.jsonl`; `block_event_decorator` wraps `output_decision` in `unified_pre_tool.py`; `HOOK_TELEMETRY_DISABLED=1` rollback; Issue #972), hard_floor.py (hard-floor hook registry — declarative always-on enforcement list; `is_hard_floor(hook_name, function_name=None)` and `get_observability_hooks()` public API; dual-source with fallback to in-module constants when JSON config is missing or malformed; Phase C of hooks architecture refactor — Phase D will wire session-mode logic to consume the registry; Issue #997), hook_timing.py (per-hook invocation timing telemetry — `HookTimer` context manager wraps every hook's `__main__` block; writes daily-rotated JSONL to `~/.claude/logs/hook_timings_YYYY-MM-DD.jsonl`; `HOOK_TIMING_DISABLED` rollback; `HOOK_TIMING_DIR` redirect for tests; sibling of `hook_telemetry.py` — separate files, independent evolution; security-hardened in Issue #1056: `MAX_HOOK_NAME_LENGTH=128` cap prevents oversized JSONL rows, log files created with `LOG_FILE_MODE=0o600` (owner-only) to prevent exposure on multi-user systems, `_sanitize_os_error()` strips absolute paths from OSError messages before writing to stderr; Issue #1012)
- **See**: [LIBRARIES.md](LIBRARIES.md) for complete API reference

**Note on auto_git_workflow.py**: A backward compatibility shim exists at `.claude/hooks/auto_git_workflow.py` (56 lines) that redirects to `unified_git_automation.py`. The original hook was consolidated in Issue #144. Duplicate resolution completed in Issue #212. See `plugins/autonomous-dev/hooks/archived/README.md` for details.

---

## Hooks

Unified hooks using dispatcher pattern for quality enforcement. See [HOOKS.md](HOOKS.md) for complete reference.

**Hook Registration**: Hooks declare lifecycle events and configurations via `.hook.json` sidecar files (Issue #551). See [HOOK-SIDECAR-SCHEMA.md](HOOK-SIDECAR-SCHEMA.md) for the declarative metadata schema (lifecycle events, matchers, timeouts, environment variables, type semantics).

**Key Features**: Dispatcher pattern (env var control), graceful degradation (non-blocking), backward compatible

**Hook Output Visibility** (Issue #660): `permissionDecisionReason` on deny is model-visible — block messages include `REQUIRED NEXT ACTION:` carrots that the model reads and acts on. `systemMessage` is user-visible (injected into the conversation). These are distinct channels: enforcement directives belong in `permissionDecisionReason`; user notifications belong in `systemMessage`. See [HOOKS.md](HOOKS.md) for full output format specification.

**Active Hooks**:
- **PreToolUse**: unified_pre_tool.py (6-layer enforcement: Sandbox → MCP Security → Agent Auth → Batch Permission → Pipeline Ordering Gate → Prompt Quality Gate; native tools bypass MCP layers — Issues #625, #629, #632, #842; **Plan-Exit Gate** (Issue #926): staged plan-exit 2-state machine — `plan_exited` blocks Write/Edit/off-allowlist Bash until plan-critic runs; `critique_done` allows `gh issue create` and `Task(implementer|issue-creator|cia)` and consumes the marker), plan_gate.py (blocks complex Write/Edit without validated plan in .claude/plans/ — Issue #814)
- **UserPromptSubmit**: unified_prompt_validator.py (compaction recovery re-injection, workflow bypass detection, quality nudges; plan-exit enforcement removed per Issue #926 — moved to PreToolUse)
- **PostToolUse**: auto_format.py, auto_test.py, security_scan.py, auto_fix_docs.py
- **PreCommit**: validate_project_alignment.py, enforce_orchestrator.py, enforce_tdd.py, validate_session_quality.py, enforce_prunable_threshold.py (opt-in via `settings.strict-mode.json` — blocks commits when prunable test count exceeds 100)
- **SessionStart**: SessionStart-batch-recovery.sh (auto-restores batch state after `/clear` or auto-compact)
- **SubagentStop / Stop**: unified_session_tracker.py (advances plan-exit stage marker on plan-critic completion; emits post-PROCEED systemMessage suggesting `/plan-to-issues --quick` or `/implement`), conversation_archiver.py (writes session transcript + SQLite index for long-term analytics)
- **See**: [HOOKS.md](HOOKS.md) and [HOOK-REGISTRY.md](HOOK-REGISTRY.md) for complete reference

---

## Workflow Pipeline

**Autonomous Development Workflow** (15 steps):

1. **Alignment Check**: Verify feature aligns with PROJECT.md
2. **Complexity Assessment** (v3.45.0): complexity_assessor determines pipeline scaling
   - Recommends agent count (3/6/8) and time (8/15/25 min)
   - Based on SIMPLE/STANDARD/COMPLEX classification
3. **Research**: researcher agent finds patterns (Haiku model)
3.5. **Research Self-Critique** (STEP 4.5, inline — no agent): One FEEDBACK pass on merged research output before passing to planner; implements Self-Refine pattern (GENERATE → FEEDBACK → REFINE). Also applied at `/advise` STEP 4.5 (post-analysis critique) and `/refactor --deep` STEP 1.5 (findings critique).
4. **Planning**: planner agent creates architecture plan
4.5. **Plan Validation Gate** (STEP 5.5, HARD GATE — Issues #855, #878, #880, #889-#893): Adversarial plan review before acceptance tests. Checks `.claude/plans/` for a pre-validated plan (Verdict: PROCEED); if absent, invokes plan-critic with a constrained budget (1 round, 3 axes: Assumption Audit, Existing Solution Search, Minimalism Pressure). When invoked from `/plan` (multi-round mode), plan-critic iterates planner with verbatim feedback until convergence at composite ≥3.0. Scoring is a 1-5 Likert scale per-axis; verdict mapping is deterministic (≥3.0 with no axis below 2 → PROCEED; <3.0 or any axis at 1 → REVISE; <2.0 or 2+ axes at 1 → BLOCKED). plan-critic is in `SEQUENTIAL_REQUIRED` ordering pairs (`planner → plan-critic`, `plan-critic → implementer`); skip is recorded via `record_plan_critic_skipped()` so the agent completeness gate excludes plan-critic when a pre-validated plan exists. Structural validation always runs: plan must contain ≥1 file path, an acceptance-criteria section, and a testing-strategy section.
5. **Pause Control** (v3.45.0): Optional human-in-the-loop after planning
6. **Acceptance Tests** (Issue #404, default): test-master writes specification-driven acceptance tests
   - Default mode: validation-first approach (specification → acceptance tests → implementation)
   - Optional `--tdd-first` flag reverts to legacy TDD-first (failing unit tests first)
7. **Implementation**: implementer makes tests pass
7.25. **Plan-Implementation Alignment Gate** (OUTPUT VALIDATION GATE, Issue #857): After tests pass, coordinator compares STEP 5 planned files (CREATE/MODIFY) against `git diff --name-only HEAD`. Test and doc files excluded. Files present in plan but absent in implementation → WARNING. Files implemented but not planned → WARNING. If >50% of non-excluded implemented files are unplanned → BLOCK.
7.5. **Spec-Blind Validation** (STEP 8.5, HARD GATE): spec-validator validates implementation against acceptance criteria only — without seeing implementation details — and emits a binary PASS/FAIL verdict (Issue #931: no file writes; verdict-only output)
   - Strict context boundary: spec-validator receives ONLY acceptance criteria, feature description, and changed file paths (no implementer output, no code diffs, no research)
   - PASS → proceed to E2E testing / validation; FAIL → implementer remediation (max 2 cycles)
7.6. **E2E UI Testing** (STEP 9.7, Issue #656, optional): ui-tester writes Playwright MCP browser tests
   - Only invoked when changed files include frontend patterns AND Playwright MCP is available
   - Advisory only — PASS or SKIP, never blocks the pipeline
7.7. **Mobile E2E Testing** (STEP 9.8, Issue #657, optional): mobile-tester runs Appium MCP + Maestro YAML + native build checks
   - Only invoked when changed files include mobile patterns AND Appium MCP or Maestro CLI is available
   - Advisory only — PASS or SKIP, never blocks the pipeline
8. **Validation** (implement.md STEP 10) — mode selected based on changeset risk:
   - **Parallel mode** (default): reviewer, security-auditor, and doc-master launched simultaneously in one message (low-risk changesets with no security-sensitive files)
   - **Sequential mode** (security-sensitive files): reviewer runs first (10a), security-auditor runs only after reviewer returns (10b), doc-master runs in background alongside reviewer (10c)
   - reviewer consumes STEP 8 test artifact (pytest results passed in context) — does NOT re-run pytest
   - doc-master runs non-blocking in both modes; result collected at STEP 12 — unless remediation occurred (see 8.5 below)
8.5. **Remediation Gate** (HARD GATE): If reviewer or security-auditor return findings, auto-loop:
   - Re-invokes implementer in Remediation Mode with BLOCKING findings verbatim (max 2 cycles)
   - Re-runs only the failing validators after each cycle (doc-master excluded from remediation loop)
   - Files GitHub issues and blocks pipeline if findings persist after 2 cycles
   - **Remediation-Aware Doc-Drift (STEP 12)**: If remediation occurred, the STEP 10 background doc-master result is discarded as stale; STEP 12 discards it and re-invokes doc-master BLOCKING with a fresh `git diff` file list reflecting post-remediation changes (#624)
9. **Memory Recording** (v3.45.0): Cross-session context after validation
10. **Automated Git Operations**: SubagentStop hook handles commit/push/PR
11. **Context Clear** (Optional): `/clear` for next feature

**Performance Baseline**: 15-25 minutes per workflow

---

## Testing Architecture

autonomous-dev uses a **Diamond Model** — not the traditional TDD pyramid. Acceptance criteria drive testing; unit tests are regression locks, not specifications. See [TESTING-STRATEGY.md](TESTING-STRATEGY.md) for full details with research citations.

### The Six Layers

| Layer | What | Directory | Determinism | CI Gate? |
|-------|------|-----------|-------------|----------|
| 1. Type/Lint | Static analysis, formatting | Pre-commit hooks | 100% | Yes |
| 2. Unit Tests | Individual functions in isolation | `tests/unit/`, `tests/regression/smoke/` | 100% | Yes |
| 3. Property Invariants | Universal properties across all inputs (Hypothesis) | `tests/property/` (13 test files) | 100% | Yes |
| 4. Integration/Contract | Components working together, API contracts | `tests/integration/`, `tests/regression/` | 100% | Yes |
| 5. LLM-as-Judge | Semantic validation — does code match intent? | `tests/genai/` (52 test files) | ~85% | Optional (`--genai`) |
| 6. Acceptance Criteria | Business intent, user-defined "done" | PROJECT.md, issue criteria | Human-defined | Per feature |

### Key Design Decisions

- **Acceptance-first by default** (Issue #404): test-master writes specification-driven acceptance tests before implementation. `--tdd-first` flag reverts to legacy TDD.
- **Spec-blind validation** (STEP 8.5, HARD GATE): spec-validator validates acceptance criteria against observable behavior *without seeing the implementation*, emitting a binary PASS/FAIL verdict. Strict context boundary — no implementer output, no code diffs, no research. No file writes permitted (Issue #931): if a criterion cannot be evaluated without writing a test file, the criterion is marked FAIL.
- **LLM-as-judge infrastructure**: `GenAIClient` in `tests/genai/conftest.py` — OpenRouter-backed, dual model (Gemini Flash + Haiku 4.5), 24h response caching, ~$0.02/run. Judge methods: `judge()` (holistic), `judge_analytic()` (per-criterion MET/UNMET), `judge_consistent()` (multi-round consensus).
- **Property-based invariants**: Hypothesis library with profile-based example counts (50 default, 200 CI). Tier registry (`tier_registry.py`) is canonical source of truth for marker-to-directory mapping.
- **Coverage Gap Assessment** (HARD GATE): test-master classifies changes into 8 categories, outputs gap summary showing required test types before writing any tests. Prevents over-testing and under-testing.
- **Soft-failure thresholds**: `SoftFailureTracker` + `thresholds.json` + `--strict-genai` flag for GenAI tests (Issue #351).

### GenAI Evaluation Types

- **Congruence**: Do file pairs agree? (e.g., `implement.md` ↔ `implementer.md`)
- **Architecture**: Do components match docs?
- **Security posture**: No secrets, proper exit codes
- **Doc completeness**: All components documented?
- **Scaffold**: `/scaffold-genai-uat` generates LLM-as-judge test infrastructure for any repo

### Why Not TDD?

| Aspect | Traditional TDD (Pyramid) | Diamond Model |
|--------|--------------------------|---------------|
| Primary driver | Unit tests | Acceptance criteria |
| Unit test role | Specification | Regression lock |
| Generation order | Tests first → code | Criteria first → code + tests |
| Agent gaming risk | High (agents game unit tests) | Low (can't game acceptance criteria) |
| Determinism | 100% required | Mixed (deterministic floor + probabilistic middle) |

---

## Performance Optimization

**10 Phases Complete**:

- **Phase 4**: Haiku model for researcher (3-5 min saved)
- **Phase 5**: Prompt simplification (2-4 min saved)
- **Phase 6**: Profiling infrastructure (PerformanceTimer, JSON logging)
- **Phase 7**: Parallel validation (60% faster - 5 min → 2 min)
- **Phase 8**: Agent output cleanup (~2,900 tokens saved)
- **Phase 8.5**: Real-time performance analysis API
- **Phase 9**: Model downgrade strategy (investigative)
- **Phase 10**: Smart agent selection (95% faster for typos/docs)

**Cumulative Impact**:
- ~11,980 tokens saved per workflow
- 25-30% overall improvement from 28-44 min baseline
- 50-100+ skills supported without context bloat

**See**: [PERFORMANCE.md](PERFORMANCE.md) for complete benchmarks

---

## Security Architecture

**Multi-Layer Defense**:

1. **Native Tool Fast Path** (v4.1.0+): Built-in tools bypass validation
   - Native Claude Code tools (Read, Write, Bash, Task, etc.) skip all validation layers
   - Governed by settings.json permissions instead
   - Prevents permission prompts for standard tools

2. **MCP Security** (v3.37.0+): Permission-based validation
   - Path traversal prevention (CWE-22)
   - Command injection blocking (CWE-78)
   - SSRF prevention (CWE-918)

3. **Sandboxing** (v4.0.0+): Command classification
   - Safe commands auto-approved
   - Blocked patterns denied
   - Shell injection detection

4. **Auto-Approval** (v3.40.0+): Batch permission caching
   - Reduces prompts from 50+ to 8-10 (84% reduction)
   - 4-layer permission architecture

**See**:
- [SANDBOXING.md](SANDBOXING.md) - Complete sandboxing guide
- [MCP-SECURITY.md](MCP-SECURITY.md) - MCP security reference
- [SECURITY.md](SECURITY.md) - Security audit guide

---

## Configuration

**Key Configuration Files**:
- `.claude/PROJECT.md` - Strategic goals and constraints
- `.env` - Environment variables and feature flags
- `plugins/autonomous-dev/config/sandbox_policy.json` - Sandboxing rules
- `plugins/autonomous-dev/config/auto_approve_policy.json` - Auto-approval rules
- `plugins/autonomous-dev/config/test_routing_config.json` - Smart test routing rules: per-category tier enable/disable, marker mappings, always_smoke and docs_only_skip_all flags
- `~/.autonomous-dev/user_state.json` - User consent persistence

**Feature Flags**:
- `AUTO_GIT_ENABLED` - Enable automatic git operations
- `MCP_AUTO_APPROVE` - Enable auto-approval
- `SANDBOX_ENABLED` - Enable command sandboxing
- `ENABLE_PAUSE_CONTROLLER` - Enable human-in-the-loop
- `ENABLE_MEMORY_LAYER` - Enable cross-session memory

---

## Cross-References

**Related Documentation**:
- [AGENTS.md](AGENTS.md) - Complete agent reference
- [LIBRARIES.md](LIBRARIES.md) - Library API documentation
- [HOOKS.md](HOOKS.md) - Hook reference
- [HOOK-REGISTRY.md](HOOK-REGISTRY.md) - Sidecar metadata schema
- [PIPELINE-MODES.md](PIPELINE-MODES.md) - `/implement` mode matrix (full / light / fix / batch) with per-mode agent sets
- [SESSION-ANALYTICS.md](SESSION-ANALYTICS.md) - sessions.db schema and queries (Layer 3 observability)
- [EVALUATION.md](EVALUATION.md) - Effectiveness measurement and self-improvement closed loop (Layer 4)
- [PERFORMANCE.md](PERFORMANCE.md) - Performance benchmarks
- [SECURITY.md](SECURITY.md) - Security guide
- [PLANNING-WORKFLOW.md](PLANNING-WORKFLOW.md) - 7-step `/plan` + plan-critic adversarial review
- [PROMPT-ENGINEERING.md](PROMPT-ENGINEERING.md) - Constraint budgets, register shifting, HARD GATE patterns
- [model-behavior-notes.md](model-behavior-notes.md) - Production-validated patterns for prompt design
- [WORKFLOW-DISCIPLINE.md](WORKFLOW-DISCIPLINE.md) - Two-tier ordering enforcement (coordinator + hook)
- [HARNESS-EVOLUTION.md](HARNESS-EVOLUTION.md) - How the harness has evolved across releases
