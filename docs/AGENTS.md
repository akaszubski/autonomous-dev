---
covers:
  - plugins/autonomous-dev/agents/
---

# Agent Architecture

**Last Updated**: 2026-04-14
**Location**: `plugins/autonomous-dev/agents/`

This document describes the agent architecture, including core workflow agents, utility agents, model tier assignments, and their skill integrations.

---

## Overview

16 active agents with skill integration. Each agent has specific responsibilities and references relevant skills.

**Active Agents**: continuous-improvement-analyst, doc-master, implementer, issue-creator, mobile-tester, plan-critic, planner, researcher, researcher-local, retrospective-analyst, reviewer, security-auditor, spec-validator, test-coverage-auditor, test-master, ui-tester

**Archived Agents** (20, in `agents/archived/`): advisor, alignment-analyzer, alignment-validator, brownfield-analyzer, commit-message-generator, data-curator, data-quality-validator, distributed-training-coordinator, experiment-critic, orchestrator, postmortem-analyst, pr-description-generator, project-bootstrapper, project-progress-tracker, project-status-analyzer, quality-validator, setup-wizard, sync-validator

**Which agents run in which pipeline mode**: See [docs/PIPELINE-MODES.md](PIPELINE-MODES.md) for the full mode matrix (full / `--tdd-first` / `--light` / `--fix` / `--batch`).

---

## Model Tier Strategy (Issue #108, Updated #147)

Agent model assignments optimized for cost-performance balance (16 active agents):

### Tier 1: Haiku (3 agents)

Fast, cost-effective for pattern matching:

- **researcher-local**: Search codebase patterns
- **test-coverage-auditor**: AST-based coverage analysis
- **issue-creator**: GitHub issue creation

### Tier 2: Sonnet (8 agents)

Balanced reasoning for judgment tasks:

- **researcher**: Web research and synthesis
- **reviewer**: Code quality gate
- **doc-master**: Semantic documentation drift detection
- **continuous-improvement-analyst**: Pipeline QA and gaming detection
- **security-auditor**: OWASP security scanning
- **retrospective-analyst**: Intent evolution and session drift detection
- **ui-tester**: E2E browser testing via Playwright MCP (optional, frontend only)
- **mobile-tester**: iOS/Android E2E testing via Appium MCP + Maestro (optional, mobile only)

### Tier 3: Opus (5 agents)

Deep reasoning for complex synthesis:

- **planner**: Architecture planning
- **implementer**: Code implementation
- **test-master**: Quality Diamond test generation
- **spec-validator**: Spec-blind behavioral validation (STEP 8.5) — validates implementation against acceptance criteria without seeing implementation details
- **plan-critic**: Adversarial plan reviewer — challenges assumptions, detects scope creep, enforces minimalism before implementation begins. Scores each axis on a 1-5 Likert scale; composite mean >=3.0 with no axis below 2 yields PROCEED, <3.0 or any axis at 1 yields REVISE, <2.0 or 2+ axes at 1 yields BLOCKED. Delta tracking added to Scores table from round 2 onward. Budget mode (single-pass) evaluates only 4 axes. **Verdict Persistence** (Issue #927): at the end of every critique round (including REVISE and BLOCKED), plan-critic MUST write `.claude/plan_critic_verdict.json` containing `verdict`, `composite_score`, and `timestamp`. This file is the HARD GATE read by `_advance_plan_mode_stage()` in `unified_session_tracker.py` — stage advance from `plan_exited` to `critique_done` only occurs when `verdict == "PROCEED"` and the timestamp is not stale. The verdict file is consumed (deleted) on successful advance. (Issue #814, Issue #880, Issue #927)

### Rationale

- **Tier 1 (Haiku)**: Cost optimization for well-defined tasks (40-60% cost reduction vs Opus) - pattern matching, coverage analysis
- **Tier 2 (Sonnet)**: Balanced reasoning for tasks requiring judgment — code review, documentation drift detection, research synthesis
- **Tier 3 (Opus)**: Reserved for complex synthesis and high-risk decisions

**Performance Impact**: Optimized tier assignments reduce costs by 40-60% while maintaining quality.

**Behavioral Compensation**: Each tier has specific prompt compensation blocks addressing known behavioral tendencies. See [docs/model-behavior-notes.md](model-behavior-notes.md) for details.

---

## Token Budget Audit (Issue #175)

**Target**: Under 3,000 tokens per agent
**Last Audit**: 2026-01-01
**Total Active Agents**: 16
**Note**: 16 active agents; plan-critic not yet measured (added Issue #814)

### Agents by Token Count

| Status | Agent | Tokens | Notes |
|--------|-------|--------|-------|
| ✅ | doc-master | 2,517 | OK (updated: Issue #744 added Step 4.6 minimum output HARD GATE) |
| ✅ | security-auditor | 1,231 | OK |
| ✅ | issue-creator | 1,113 | OK |
| ✅ | researcher-local | 1,104 | OK |
| ✅ | planner | 1,025 | OK |
| ✅ | researcher | 898 | OK |
| ✅ | implementer | 830 | OK |
| ✅ | test-master | 677 | OK |
| ✅ | reviewer | 623 | OK |
| ✅ | continuous-improvement-analyst | 580 | OK |
| ✅ | test-coverage-auditor | 450 | OK |

### Summary

- **Run audit**: `python3 scripts/measure_agent_tokens.py --baseline`
- All 15 previously audited agents under 3,000 token target; plan-critic (added Issue #814) not yet measured

---

## Archived Agents (Issue #331, #411, #471)

18 agents have been archived and moved to `plugins/autonomous-dev/agents/archived/`:

- **orchestrator**: Meta-agent for workflow coordination (consolidated into unified /implement command)
- **advisor**: Critical thinking and validation (consolidated, Issue #331)
- **alignment-analyzer**: Detailed alignment analysis (consolidated, Issue #331)
- **alignment-validator**: PROJECT.md alignment checking (ghost registration removed, Issue #411)
- **brownfield-analyzer**: Brownfield project analysis (consolidated, Issue #331)
- **commit-message-generator**: Conventional commit generation (archived)
- **data-curator**: A-grade data pipeline orchestration (consolidated, Issue #331)
- **data-quality-validator**: LLM training data quality assessment (ghost registration removed, Issue #411)
- **distributed-training-coordinator**: Distributed LLM training orchestration (ghost registration removed, Issue #411)
- **experiment-critic**: Experiment evaluation (consolidated, Issue #331)
- **postmortem-analyst**: Pipeline session log analysis (consolidated, Issue #331)
- **project-bootstrapper**: Tech stack detection and setup (consolidated, Issue #331)
- **project-progress-tracker**: Goal progress tracking (archived, Issue #471)
- **project-status-analyzer**: Real-time project health analysis (consolidated, Issue #331)
- **quality-validator**: GenAI-powered feature validation (archived)
- **pr-description-generator**: Pull request description generation (archived, Issue #471)
- **setup-wizard**: Intelligent interactive setup (consolidated, Issue #331)
- **sync-validator**: Smart dev sync validation (consolidated, Issue #331)

---

## Core Workflow Agents

These agents execute the main autonomous development workflow and provide specialized functionality.

### researcher-local

**Purpose**: Search codebase for existing patterns and similar implementations
**Model**: Haiku (Tier 1 - cost optimized for pattern matching)
**Skills**: research-patterns
**Tools**: Read, Grep, Glob (local filesystem access only)
**Execution**: Step 1A of /implement workflow (parallel with researcher-web)
**Output Format**: JSON schema with similar_implementations array plus implementation_guidance and testing_guidance sections
  - **similar_implementations**: Existing patterns matching the feature request
  - **implementation_guidance**: Reusable functions, import patterns, error handling patterns
    - reusable_functions: Functions with file location, purpose, and usage examples
    - import_patterns: Recommended imports with context for when to use
    - error_handling_patterns: Error handling approaches with file/line references
  - **testing_guidance**: Testing patterns found in the codebase
    - test_file_patterns: Structure of tests, pytest patterns, common fixtures
    - edge_cases_to_test: Edge cases identified in similar code with expected behavior
    - mocking_patterns: Mocking approaches used in existing tests with examples
**Research Persistence** (Issue #151): Optionally persists significant research findings to `docs/research/` for future reuse

### researcher-web

**Purpose**: Research web best practices and industry standards
**Model**: Haiku (Tier 1 - cost optimized for pattern matching)
**Skills**: research-patterns, documentation-guide
**Tools**: WebSearch, WebFetch (external research only)
**Execution**: Step 1B of /implement workflow (parallel with researcher-local)
**Output Format**: JSON schema with antipatterns array plus implementation_guidance and testing_guidance sections
  - **antipatterns**: Industry-standard pitfalls and how to avoid them
  - **implementation_guidance**: Best practices for design and performance
    - design_patterns: Patterns like Factory, Strategy, Decorator with usage context and examples
    - performance_tips: Optimization techniques with impact assessment
    - library_integration_tips: Best practices for popular libraries (requests, async, etc)
  - **testing_guidance**: Industry best practices for testing
    - testing_frameworks: Framework recommendations (pytest, unittest) with key features
    - coverage_recommendations: Coverage targets by area (error handling 100%, happy path 80%)
    - testing_antipatterns: Common testing mistakes and preferred alternatives
**Research Persistence** (Issue #151): Persists substantial research findings (2+ best practices, 3+ sources) to `docs/research/` with SCREAMING_SNAKE_CASE naming (e.g., JWT_AUTHENTICATION_RESEARCH.md)
**Related**: Deprecated researcher.md combined functionality split into local/web agents (Issue #128); output expanded in Issue #130

### planner

**Purpose**: Architecture planning and design
**Model**: Opus (Tier 3 - deep reasoning for complex planning)
**Skills**: architecture-patterns, api-design, database-design, testing-guide
**Execution**: Step 2 of /implement workflow (after merging research findings from Step 1.1)

### test-master

**Purpose**: TDD specialist (writes tests first)
**Model**: Sonnet (Tier 2 - strong reasoning for comprehensive test design)
**Skills**: testing-guide, security-patterns
**Execution**: Step 3 of /implement workflow
**Research Context**: Receives testing_guidance from researcher-local and researcher-web (Issue #130)
  - Uses test_file_patterns, edge_cases_to_test, mocking_patterns from researchers
  - Falls back to Grep/Glob pattern discovery if research context not provided
**Context Isolation**: Runs in separate context. Writes tests to disk for implementer. See testing-guide skill for context isolation patterns.

### implementer

**Purpose**: Code implementation (makes tests pass)
**Model**: Opus (Tier 3 - deep reasoning for code implementation)
**Skills**: python-standards, testing-guide, error-handling, refactoring-patterns, debugging-workflow
**Execution**: Step 4 of /implement workflow
**Research Context**: Receives implementation_guidance from researcher-local and researcher-web (Issue #130)
  - Uses reusable_functions, import_patterns, error_handling_patterns from researchers
  - Uses design_patterns, performance_tips, library_integration_tips from web research
  - Falls back to Grep/Glob pattern discovery if research context not provided
**Context Isolation**: Runs in separate context. Reads only test files from disk, not test-master's reasoning. See testing-guide skill for context isolation patterns.
**Remediation Mode**: Re-invoked by the STEP 6.5 Remediation Gate when the reviewer or security-auditor return BLOCKING findings. In this mode the implementer fixes only the cited BLOCKING findings (verbatim from the gate), runs pytest to confirm 0 failures, and reports what changed. WARNING findings are out of scope during remediation.
**Output Self-Validation** (Issue #707): After tests pass, the implementer MUST run a semantic validation: smoke test with realistic input, output format check, boundary check for numeric/string values, and error path check with invalid input. FORBIDDEN: declaring completion without smoke test, accepting empty/placeholder outputs, skipping validation because tests pass.
**Error Recovery with Retry Budget** (Issue #708): Max 2 retries per approach — if the same error appears twice, the implementer MUST pivot to a different strategy (simplify, alternative library, decompose, or escalate). FORBIDDEN: retrying the same approach after 2 failures, silent error loops, giving up without trying 2+ approaches.
**Mini-Replan on Blocking Signals** (Issue #730): When a tool execution returns a recoverable error (ModuleNotFoundError, FileNotFoundError, ImportError, AttributeError, command not found), the implementer MUST perform a mini-replan cycle (max 2) instead of retrying blindly. Each cycle: classify error → determine corrective action → apply fix → re-run. Mini-replan cycles are separate from the retry budget. After 2 failed mini-replan cycles, escalate to the coordinator. Supported by `blocking_signal_classifier.py` library. FORBIDDEN: retrying the same command without a corrective action, ignoring recoverable error signals, exceeding 2 mini-replan cycles.
**Pre-Execution Tool Documentation Research** (Issue #706): Before using an unfamiliar CLI tool, the implementer MUST read its `--help` output. Known-safe tools (git, python, pytest, pip, npm, etc.) are exempt. Graceful fallback if help unavailable.
**Evidence Manifest Output** (Issue #727): After all tests pass, the implementer MUST output a structured Markdown table listing every file created or modified, its state (CREATED/MODIFIED/DELETED), and a verifiable signal (e.g., "contains class Foo", "contains 6 test functions"). Required in full pipeline mode; recommended in --fix and --light modes. FORBIDDEN: declaring "implementation complete" without an evidence manifest in full pipeline mode.
**Root Cause Analysis HARD GATE** (Issue #856): In fix mode (`--fix` or fixing a known bug), the implementer MUST produce a `## Root Cause Analysis` section before declaring the fix complete. The section MUST include: (1) root cause statement (1 sentence — the underlying cause, not the symptom), (2) mechanism chain (how the root cause propagated to the observable failure, e.g., A → B → C → failure), (3) 5 Whys (minimum 3 levels, each level MUST introduce new information), and (4) root cause category (Wrong type / Wrong state / Race condition / Missing check / Stale data / Wrong assumption). The coordinator (implement-fix.md STEP F3) checks for `## Root Cause Analysis` in the output — if absent on first completion, the implementer is re-invoked once; if still absent, the pipeline is BLOCKED. FORBIDDEN: tautological 5 Whys, claiming the bug is "obvious" and skipping analysis, fixing the symptom without identifying the root cause, omitting the section in fix mode.
**Mechanical Test Counting HARD GATE** (Issues #988, #1117): When any acceptance criterion specifies a minimum test count, the implementer MUST invoke the canonical counter `bugfix_detector.get_test_count()` (from `plugins/autonomous-dev/lib/bugfix_detector.py`) rather than estimating from memory. The counter uses a whitespace-tolerant regex (`^\s*def\s+test_`) that handles both top-level and indented class-method tests. FORBIDDEN: self-reporting test counts from memory; using the anchored shell variant `grep -cE "^def test_"` which returns 0 for class-method tests (the common pattern in `tests/regression/`).
**Document Output Cleanliness HARD GATE** (Issue #921): When producing research notes, ADRs, design docs, or any Markdown artifact during `/implement`, the document MUST be free of plan-critic process metadata. Section headers and revision annotations from the plan-critic REVISE cycle are working artifacts — they MUST NOT leak into the final document. FORBIDDEN: embedding plan-critic revision annotations in section headers (e.g., `## Security Model (Revised: sandboxing clarified)`), REVISE cycle notes or revision-history parentheticals in headings (e.g., `## API Surface (REVISE pass 2)`), or critic-feedback prefixes such as `(Revised:`, `(REVISE`, `(revision:`, `(per critic feedback)`. Section headers must be clean prose titles only. Revision history (if retained at all) belongs in a document footer or metadata block.

### reviewer

**Purpose**: Quality gate (code review) — read-only; reports issues, never modifies files
**Model**: Sonnet (Tier 2 - balanced reasoning for judgment-based code review)
**Skills**: python-standards, code-review, security-patterns, refactoring-patterns
**Execution**: STEP 10 of /implement workflow — in parallel mode (default, low-risk changesets), runs simultaneously with security-auditor and doc-master in a single Agent call; in sequential mode (security-sensitive files detected), runs first (STEP 10a) before security-auditor (STEP 10b), ensuring the STEP 11 Remediation Gate has the full reviewer verdict before security-auditor begins. In both modes, the reviewer consumes STEP 8 test results passed in context — it does NOT re-run pytest
**Read-Only Enforcement** (Issue #461): Reviewer MUST NOT use Write or Edit tools on any file. When issues are found, they are reported as FINDINGS with file:line references and the verdict is set to REQUEST_CHANGES. The coordinator relays findings to the implementer. This prevents post-review edits that bypass the STEP 5 test gate and introduce unreviewed changes.
**Minimum File Read Requirement** (Issue #659): Reviewer MUST use the Read tool to read EACH changed file before issuing any verdict. Ghost reviews (reviewing only from prompt context) produce no verification value. Minimum tool use thresholds: 1-50 lines changed → 2 tool uses; 51-200 lines changed → 3 tool uses; 200+ lines changed → 5 tool uses. FORBIDDEN: issuing any verdict (APPROVE or REQUEST_CHANGES) with 0 tool uses.
**Evidence Manifest Verification** (Issue #727): Before issuing any verdict, reviewer MUST locate the `## Evidence Manifest` table in the implementer's output and verify each entry using Read/Grep/Glob tools: file exists (Tier 1 blocking), file is non-empty (Tier 1 blocking), verification signal matches (Tier 2 blocking). Missing or empty manifest → BLOCKING finding, REQUEST_CHANGES. Required in full pipeline mode; recommended in --fix and --light modes.
**Test Deletion Detection** (Issue #711): Reviewer MUST flag when behavioral tests are deleted or replaced with weaker structural absence-checks. Flags: test file deletions or >50% line reduction; deleted tests referencing issue numbers (regression tests); behavioral tests replaced with structural absence-checks (e.g., `assert "X" not in source_code`). Absence checks verify that code text lacks a string — they do NOT verify the code works correctly. FORBIDDEN: APPROVE when issue-traced tests are deleted without a behavioral replacement, or when test count drops >20% without flagging as a finding.
**FINDINGS Format**: Each finding uses a structured `FINDING-{N}` schema with mandatory `file:line` reference, severity (`BLOCKING` or `WARNING`), category, issue description, detail, and suggested fix. BLOCKING findings trigger the STEP 6.5 Remediation Gate; WARNING findings are advisory only.
**Verdict**: `APPROVE` (all findings WARNING or none) or `REQUEST_CHANGES` (any BLOCKING finding present). STEP 6.5 parses this verdict to determine whether to enter the remediation loop.
**Runtime Verification (Opt-In, Issue #564)**: After completing static code review with NO BLOCKING findings, the reviewer MAY perform targeted runtime checks when changed files include frontend (HTML/TSX/Vue/Svelte), API routes, or CLI tools. Uses Playwright MCP for frontend, curl for API endpoints, and subprocess for CLI tools. HARD GATE: runtime verification MUST NOT run when BLOCKING findings are present; total time capped at 60 seconds; all subprocess commands MUST use `timeout 30` wrapper. Skips gracefully when the required tool or server is unavailable.

### security-auditor

**Purpose**: Security scanning and vulnerability detection
**Model**: Sonnet (Tier 2 - balanced reasoning for OWASP security analysis)
**Skills**: security-patterns, python-standards
**Execution**: STEP 10 of /implement workflow — in parallel mode (default, low-risk changesets), runs simultaneously with reviewer and doc-master; in sequential mode (security-sensitive files detected), runs as STEP 10b strictly after reviewer (STEP 10a) has returned its verdict, enabling the STEP 11 Remediation Gate to have complete information before deciding to re-invoke the implementer
**Security Test Integrity Check** (Issue #711): When the changeset includes test file deletions or modifications, the security-auditor MUST check whether security-related tests are affected (tests referencing `security`, `auth`, `injection`, `XSS`, `CSRF`, `SSRF`, `sanitiz`, `secret`, `credential`, `token`, `password`, `permission`, `access control`, `privilege`). Deleted or weakened security tests — including structural-only replacements — are flagged as HIGH severity. Rationale: a structural absence-check does not verify that input sanitization actually works; only a behavioral test that passes malicious input and verifies rejection can do that.
**ADVISORY-FINDINGS Output Contract** (Issue #1180): Every security audit output MUST end with an `ADVISORY-FINDINGS:` block. Low and Medium severity findings that do not block PASS are enumerated here (one line per finding: `- [Low|Medium] <summary>: <file>:<line> — <recommendation>`). When no advisory findings exist, the agent MUST emit the literal `ADVISORY-FINDINGS: none`. Absent block = malformed output; the coordinator re-invokes once, then BLOCKS the pipeline. Critical and High findings MUST NOT appear in this block — they cause FAIL and are tracked through the remediation loop. FORBIDDEN: deferring a Low/Medium finding to "follow-up" without emitting it in the advisory block. The coordinator parses this block after STEP 11 and files a dedup-checked `gh issue create --label security --label auto-improvement` for each Low/Medium finding before STEP 12.

### doc-master

**Purpose**: Semantic documentation drift detection — reads changed source files and compares prose descriptions against actual code behavior to find and fix factual drift
**Model**: Sonnet (Tier 2 - judgment required for comparing prose against code semantics)
**Skills**: documentation-guide
**Execution**: STEP 10 of /implement workflow — runs in background (non-blocking). In parallel mode, launched simultaneously with reviewer and security-auditor. In sequential mode, launched alongside STEP 10a (reviewer), not waiting for security-auditor to finish. Collected at STEP 12. If STEP 11 remediation occurred, the STEP 10 background result is discarded as stale; STEP 12 re-invokes doc-master BLOCKING with a fresh post-remediation file list (#624)
**Drift Detection**: Uses `covers:` YAML frontmatter in `docs/*.md` files to map source paths to docs, then applies LLM judgment to detect factual drift, behavioral drift, structural drift, and missing coverage
**CHANGELOG Scope Boundary**: Only writes CHANGELOG entries for files present in the current commit's `git diff --name-only`. Prior-commit drift discovered during a run is reported as a `DOC-DRIFT-FOUND (prior commit)` finding and must not be silently folded into the current commit's CHANGELOG section. A standalone doc-fix commit is recommended for prior-commit gaps (Issue #741)
**Minimum Output Enforcement** (Issue #744): doc-master's total response MUST contain at least 100 words. Outputs under 100 words indicate the `covers:` scan or semantic comparison was skipped. The coordinator (implement-batch.md STEP B3, implement-fix.md STEP F4) counts the words in the doc-master output and treats sub-100-word responses as `DOC-VERDICT-SHALLOW`, logging the shortfall and retrying once with reduced context. If the retry also produces fewer than 100 words, it records `doc-drift-verdict: SHALLOW` with a warning rather than blocking.

### ui-tester

**Purpose**: E2E browser testing specialist — writes persistent test files in `tests/e2e/` using Playwright MCP tools (Issue #656)
**Model**: Sonnet (Tier 2 - balanced reasoning for test writing and browser interaction)
**Skills**: testing-guide, python-standards
**Tools**: Read, Write, Edit, Bash, Grep, Glob, Playwright MCP
**Execution**: STEP 9.7 of /implement workflow — OPTIONAL; invoked only when (1) changed files include frontend patterns (`*.html`, `*.tsx`, `*.jsx`, `*.vue`, `*.svelte`, `*.css`) AND (2) Playwright MCP tools are available. Skipped silently otherwise.
**Security**: Hard gate restricts navigation to `localhost`, `127.0.0.1`, `0.0.0.0`, or user-provided domains. Page content is treated as adversarial (prompt injection risk). `browser_evaluate` limited to read-only diagnostics.
**Timeout**: 60 seconds per test case. Time-based waits (sleep, setTimeout) forbidden — condition-based waits only.
**Verdict**: `UI-TESTER-VERDICT: PASS` or `UI-TESTER-VERDICT: SKIP`. E2E testing is ADVISORY — the verdict never blocks the pipeline.

### mobile-tester

**Purpose**: iOS/Android E2E testing specialist — runs interactive tests via Appium MCP, writes persistent Maestro YAML flows in `.maestro/`, and validates native builds via xcodebuild/Gradle (Issue #657)
**Model**: Sonnet (Tier 2 - balanced reasoning for test writing and device interaction)
**Skills**: testing-guide, python-standards
**Tools**: Read, Write, Edit, Bash, Grep, Glob, Appium MCP
**Execution**: STEP 9.8 of /implement workflow — OPTIONAL; invoked only when (1) changed files include mobile patterns (`*.swift`, `*.kt`, `*.dart`, `ios/`, `android/`, `Podfile`, `build.gradle`, `pubspec.yaml`) AND (2) Appium MCP or Maestro CLI is available. Skipped silently otherwise.
**Three-Layer Stack**:
  1. **Appium MCP** (interactive): Real-time element interaction via `mcp__appium__find_element`, `mcp__appium__tap`, `mcp__appium__type`, `mcp__appium__screenshot`
  2. **Maestro CLI** (regression): Persistent YAML flow files in `.maestro/test_<feature>.yaml` — runnable via `maestro test`
  3. **xcodebuild/Gradle** (native): Build verification for `*.swift`, `*.kt`, `*.m`, `*.java` changes
**Security**: Hard gate restricts execution to iOS Simulator and Android Emulator only. Physical production devices forbidden. All app content treated as adversarial. Screenshots saved only to designated directories.
**Timeout**: 60 seconds per test case. Time-based waits (sleep, Thread.sleep) forbidden — element wait conditions only.
**Verdict**: `MOBILE-TESTER-VERDICT: PASS` or `MOBILE-TESTER-VERDICT: SKIP`. Mobile testing is ADVISORY — the verdict never blocks the pipeline.

### data-curator

**Purpose**: Orchestrate 9-stage A-grade data pipeline for LLM training (Issue #311)
**Model**: Haiku (Tier 1 - cost optimized for data processing orchestration)
**Skills**: quality-scoring
**Tools**: Bash, Read, Write, Grep, Glob (filesystem and processing access)
**Execution**: Utility agent for training data preparation workflows
**Pipeline Stages** (9-stage orchestration):
  1. **Extract**: Persona-driven extraction from diverse formats (JSONL, Parquet, CSV)
  2. **Prefilter**: KenLM perplexity filtering for language quality (threshold <500)
  3. **Score**: IFD quality scoring using training_metrics.calculate_ifd_score()
  4. **Dedup**: Exact + fuzzy deduplication (MinHash/LSH, threshold 0.85)
  5. **Decontaminate**: Benchmark contamination removal (MMLU, HumanEval, GSM8K, 13-gram threshold)
  6. **Filter**: Quality threshold filtering (IFD ≥0.6, length constraints)
  7. **Generate**: DPO pair generation and RLVR trace creation
  8. **Mix**: Weighted dataset mixing for domain balance
  9. **Validate**: Final quality checks and data poisoning detection
**Checkpoint Integration**: Load/save pipeline state via CheckpointManager for resume capability across interruptions
**Training Metrics**: Integrates with training_metrics.py library (IFD scoring, DPO validation, RLVR assessment)
**Security**: Path validation (CWE-22), log injection prevention (CWE-117), input validation (CWE-20)
**Output**: Structured JSON pipeline report with stage metrics, quality summary, and checkpoint state

### quality-validator

**Purpose**: GenAI-powered feature validation (v3.0+)
**Model**: Sonnet (Tier 2 - balanced reasoning for comprehensive validation)
**Skills**: testing-guide, code-review
**Execution**: Step 6 of /implement workflow (Final validation step, triggers SubagentStop hook)

---

## Utility Agents

These agents provide specialized functionality for alignment, git operations, project management, training best practices, and pipeline diagnostics.

### alignment-validator

**Purpose**: PROJECT.md alignment checking
**Model**: Haiku (Tier 1 - cost optimized for validation)
**Skills**: semantic-validation, file-organization
**Command**: Invoked during /implement for feature alignment

### commit-message-generator

**Purpose**: Conventional commit generation
**Model**: Haiku (Tier 1 - cost optimized for structured formatting)
**Skills**: git-workflow, code-review
**Hook**: Auto-invoked by auto_git_workflow.py (SubagentStop lifecycle)

### issue-creator

**Purpose**: Generate well-structured GitHub issue descriptions (v3.10.0+, GitHub #58)
**Model**: Sonnet (Tier 2 - balanced reasoning for structured issues)
**Skills**: github-workflow, documentation-guide, research-patterns
**Command**: /create-issue

### brownfield-analyzer

**Purpose**: Analyze brownfield projects for retrofit readiness (v3.11.0+, GitHub #59)
**Model**: Sonnet (Tier 2 - balanced reasoning for complex analysis)
**Skills**: research-patterns, semantic-validation, file-organization, python-standards
**Command**: /align --retrofit

### project-bootstrapper

**Purpose**: Tech stack detection and setup (v3.0+)
**Model**: Sonnet (Tier 2 - balanced reasoning for tech analysis)
**Skills**: research-patterns, file-organization, python-standards
**Command**: /setup

### setup-wizard

**Purpose**: Intelligent setup - analyzes tech stack, recommends hooks (v3.1+)
**Model**: Sonnet (Tier 2 - balanced reasoning for interactive setup)
**Skills**: research-patterns, file-organization
**Status**: Archived — /setup command now runs without agent invocation (Issue #470)

### project-status-analyzer

**Purpose**: Real-time project health - goals, metrics, blockers (v3.1+)
**Model**: Sonnet (Tier 2 - balanced reasoning for health assessment)
**Skills**: project-management, code-review, semantic-validation
**Command**: /status

### sync-validator

**Purpose**: Smart dev sync - detects conflicts, validates compatibility (v3.1+)
**Model**: Haiku (Tier 1 - cost optimized for validation and sync)
**Skills**: consistency-enforcement, file-organization, python-standards, security-patterns
**Command**: /sync

### data-quality-validator

**Purpose**: LLM training data quality assessment and validation (v3.44+, Issue #274)
**Model**: Sonnet (Tier 2 - balanced reasoning for quality assessment)
**Skills**: data-distillation, preference-data-quality, testing-guide
**Command**: /assess-training-data
**Training Metrics**: IFD scoring, DPO validation, RLVR assessment via training_metrics.py library

### distributed-training-coordinator

**Purpose**: Distributed LLM training orchestration and optimization (v3.44+, Issue #274)
**Model**: Sonnet (Tier 2 - balanced reasoning for distributed systems)
**Skills**: mlx-performance, data-distillation, performance-optimization
**Implementation**: Coordinates multi-node training, validates data distribution, monitors performance
**Related**: Works with data-quality-validator for end-to-end training pipeline

### postmortem-analyst

**Purpose**: Analyze `/implement` pipeline session logs to identify plugin bugs (Issue #328)
**Model**: Haiku (Tier 1 - cost optimized for log analysis and classification)
**Skills**: github-workflow, error-handling-patterns
**Tools**: Read, Bash, Grep (log and filesystem access)
**Execution**: Utility agent for pipeline diagnostics and bug detection
**Features**:
  - Reads session telemetry using session_telemetry_reader.py library
  - Classifies findings into plugin bugs vs user code issues
  - Detects duplicate issues via GitHub API
  - Auto-files GitHub issues for actionable plugin bugs
  - Generates postmortem summary reports
**Input**: Optional date parameter (YYYY-MM-DD) and dry-run mode
**Output**: Structured postmortem report with findings, bug count, and filed issues

### continuous-improvement-analyst

**Purpose**: QA automation — verify autonomous-dev's pipeline, hooks, and enforcement working correctly (Issue #394)
**Model**: Sonnet (Tier 2 - balanced reasoning for quality analysis)
**Skills**: github-workflow, error-handling-patterns
**Tools**: Read, Bash, Grep (log and filesystem access)
**Execution**: Two-mode utility agent for automation quality assurance
**Two-Mode Architecture**:
  - **Batch mode** (3-5 tool calls, <30s): Fast per-issue check during batch processing
    - Verifies required agents ran from context provided (no log parsing)
    - Flags suspicious agents completing in <10s with zero file reads
    - Reports findings without filing GitHub issues
  - **Full mode** (10-15 tool calls): Comprehensive post-batch or standalone analysis
    - Parses session logs using `pipeline_intent_validator` library
    - Detects HARD GATE violations, missing agents, hook layer failures, rule bypasses
    - Routes each finding to the correct repo (`autonomous-dev`, `consumer`, or `both`) based on where the fix lives, then files deduped GitHub issues for actionable findings (severity >= warning)
**Detection Coverage**:
  - Pipeline completeness (all required agents ran)
  - Gate integrity (test gates passed, no stubs)
  - Suspicious agents (timing anomalies, zero operations)
  - Hook health (errors, missing layers, silent failures)
  - Rule bypasses (steps skipped, raw edits, nudges ignored)
  - Pipeline timing analysis (slow, wasteful, ghost invocations via `pipeline_timing_analyzer.py`; check #11)
  - Test lifecycle health (pruning candidates, untraced tests, tier imbalance; check #12)
  - Token efficiency analysis (tokens-per-word ratio, per-invocation budget; check #13)
  - Pipeline efficiency analysis (cross-run model tier recommendations, token trend detection, IQR outlier detection via `pipeline_efficiency_analyzer.py`; check #14)
  - Validator diversity (Jaccard overlap between reviewer and security-auditor findings; `[VALIDATOR-OVERLAP]` when Jaccard > 0.8 AND total findings ≥ 6; `[VALIDATOR-BLIND-SPOT]` when both validators return zero findings with artifacts present; info severity, never blocks; check #15)
  - Cross-repo finding routing (Issue #739): each finding is annotated with `target_repo: autonomous-dev | consumer | both` based on where the fix lives; issues are filed to the correct repo using `-R akaszubski/autonomous-dev` for framework findings or no `-R` flag for consumer findings; `both` findings produce two cross-referenced issues
**Excluded**: Feature code quality, security vulnerabilities, documentation completeness (handled by other agents)
**Mission**: "Is autonomous-dev's automation working correctly?"

---

## Agent-Skill Integration

Active agents reference relevant skills via `skills:` frontmatter (Issue #35, #143, #147). Claude Code 2.0 auto-loads skills when agents are spawned.

**How It Works**:
1. Each agent's prompt includes a "Relevant Skills" section
2. Skills auto-activate based on task keywords
3. Claude loads full SKILL.md content only when relevant
4. Context stays efficient while providing specialized knowledge

**See Also**: [ARCHITECTURE-OVERVIEW.md](ARCHITECTURE-OVERVIEW.md) for skills overview.

---

## Validation Modes (STEP 10, Phase 7)

STEP 10 of /implement routes to one of two modes based on changeset risk:

**Parallel mode** (default — low-risk changesets, no security-sensitive files):
- reviewer, security-auditor, and doc-master all launched in a single Agent call
- Performance: 60% faster — ~5 min sequential → ~2 min parallel

**Sequential mode** (security-sensitive files detected — hooks/*, lib/*auth*, lib/*token*, config/auto_approve_policy.json, etc.):
- STEP 10a: reviewer runs first
- STEP 10b: security-auditor runs only after reviewer returns its verdict
- STEP 10c: doc-master runs in background (can start with 10a)

**Implementation**: Parallel mode uses three Agent tool calls in a single message; sequential mode uses separate messages.

---

## See Also

- [ARCHITECTURE-OVERVIEW.md](ARCHITECTURE-OVERVIEW.md) - Overall system architecture
- [ARCHITECTURE-OVERVIEW.md](ARCHITECTURE-OVERVIEW.md) - Skills and agent integration
- [commands/implement.md](/plugins/autonomous-dev/commands/implement.md) - Workflow coordination
- [agents/](/plugins/autonomous-dev/agents/) - Individual agent prompts
