# Claude Code Bootstrap - Project Instructions

**Last Updated**: 2025-11-16
**Project**: Autonomous Development Plugin for Claude Code 2.0
**Version**: v3.26.0 (Phase 8.6 Complete: Extract skill-integration-templates skill)

> **📘 Maintenance Guide**: See `docs/MAINTAINING-PHILOSOPHY.md` for how to keep the core philosophy active as you iterate

---

## Project Overview

**autonomous-dev** - Plugin repository for autonomous development in Claude Code.

**Core Plugin**: `autonomous-dev` - 20 AI agents, 27 skills, automation hooks, and slash commands for autonomous feature development

**Install**:
```bash
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
# Exit and restart Claude Code (Cmd+Q or Ctrl+Q)
# Done! All commands work: /auto-implement, /batch-implement, /align-project, /align-claude, /setup, /sync, /status, /health-check, /pipeline-status, /update-plugin, /create-issue
```

**Commands (20 active, includes /align-project-retrofit for brownfield adoption and /batch-implement for sequential processing)**:

**Core Workflow (11)**:
- `/auto-implement` - Autonomous feature development (Claude coordinates 7 agents)
- `/batch-implement <file>` - Sequential feature processing with automatic context management (prevents context bloat) - GitHub #74
- `/align-project` - Fix PROJECT.md conflicts (alignment-analyzer agent)
- `/align-claude` - Fix documentation drift (validation script)
- `/align-project-retrofit` - Retrofit brownfield projects for autonomous development (5-phase process) - GitHub #59
- `/setup` - Interactive setup wizard (project-bootstrapper agent)
- `/sync` - Unified sync command (smart auto-detection: dev environment, marketplace, or plugin dev) - GitHub #47
- `/status` - Track project progress (project-progress-tracker agent)
- `/health-check` - Validate plugin integrity and marketplace version (Python validation) - GitHub #50
- `/pipeline-status` - Track /auto-implement workflow (Python script)
- `/update-plugin` - Interactive plugin update with backup and rollback (Python CLI) - GitHub #50 Phase 2

**Individual Agents (8)** - GitHub #44, #58:
- `/research <feature>` - Research patterns and best practices (2-5 min)
- `/plan <feature>` - Architecture and implementation planning (3-5 min)
- `/test-feature <feature>` - TDD test generation (2-5 min)
- `/implement <feature>` - Code implementation to make tests pass (5-10 min)
- `/review` - Code quality review and feedback (2-3 min)
- `/security-scan` - Security vulnerability scan and OWASP compliance (1-2 min)
- `/update-docs` - Documentation synchronization (1-2 min)
- `/create-issue <request>` - Create GitHub issue with research integration (3-8 min) - GitHub #58

**Utility Commands (1)**:
- `/test` - Run automated tests (pytest wrapper)

**Removed Commands** (deprecated/archived):
- `/uninstall` - Archived to commands/archive/ (use /plugin uninstall autonomous-dev instead)

---

## Context Management (CRITICAL!)

### Why This Matters

- ❌ Without clearing: Context bloats to 50K+ tokens after 3-4 features → System fails
- ✅ With clearing: Context stays under 8K tokens → Works for 100+ features

### After Each Feature: Clear Context

```bash
/clear
```

**What this does**: Clears conversation (not files!), resets context budget, maintains performance

**When to clear**:
- ✅ After each feature completes (recommended for optimal performance)
- ✅ Before starting unrelated feature
- ✅ If responses feel slow

### Session Files Strategy

Agents log to `docs/sessions/` instead of context:

```bash
# Log action
python scripts/session_tracker.py agent_name "message"

# View latest session
cat docs/sessions/$(ls -t docs/sessions/ | head -1)
```

**Result**: Context stays small (200 tokens vs 5,000+ tokens)

---

## PROJECT.MD - Goal Alignment

[`.claude/PROJECT.md`](.claude/PROJECT.md) defines GOALS, SCOPE, CONSTRAINTS, ARCHITECTURE

**Before starting work**:

```bash
# Check alignment
cat .claude/PROJECT.md | grep -A 5 "## GOALS"

# Verify:
# - Does feature serve GOALS?
# - Is feature IN SCOPE?
# - Does feature respect CONSTRAINTS?
```

**Update when strategic direction changes**:
```bash
vim .claude/PROJECT.md
git add .claude/PROJECT.md
git commit -m "docs: Update project goals"
```

---

## Autonomous Development Workflow

1. **Alignment Check**: Verify feature aligns with PROJECT.md
2. **Research**: researcher agent finds patterns (Haiku model - optimized for speed)
3. **Planning**: planner agent creates plan
4. **TDD Tests**: test-master writes failing tests FIRST
5. **Implementation**: implementer makes tests pass
6. **Parallel Validation (3 agents simultaneously)**:
   - reviewer checks code quality
   - security-auditor scans for vulnerabilities
   - doc-master updates documentation
   - Execution: Three Task tool calls in single response enables parallel execution
   - Performance: 5 minutes → 2 minutes (60% faster)
7. **Automated Git Operations (SubagentStop hook - consent-based)**:
   - Triggers when quality-validator agent completes
   - Check environment variables for consent: `AUTO_GIT_ENABLED`, `AUTO_GIT_PUSH`, `AUTO_GIT_PR`
   - Invoke commit-message-generator agent (creates conventional commit)
   - Automatically stage changes, create commit, push, and optionally create PR
   - Graceful degradation: If prerequisites fail (git not available, config missing), feature is still successful
   - Hook file: `plugins/autonomous-dev/hooks/auto_git_workflow.py` (SubagentStop lifecycle)
8. **Context Clear (Optional)**: `/clear` for next feature (recommended for performance)

**Performance Baseline** (see [docs/PERFORMANCE.md](docs/PERFORMANCE.md) for complete details):
- **Phase 4 (Model Optimization - COMPLETE)**: Researcher agent switched to Haiku model (25-39 min baseline)
  - Savings: 3-5 minutes from 28-44 minute baseline
  - Quality: No degradation - Haiku excels at pattern discovery tasks
  - File: `plugins/autonomous-dev/agents/researcher.md` (model: haiku)
- **Phase 5 (Prompt Simplification - COMPLETE)**: Streamlined researcher and planner prompts (22-36 min baseline)
  - Researcher: 59 significant lines (40% reduction from 99 lines)
  - Planner: 73 significant lines (39% reduction from 119 lines)
  - Savings: 2-4 minutes per workflow through faster token processing
  - Quality: Essential guidance preserved, PROJECT.md alignment maintained
- **Phase 6 (Profiling Infrastructure - COMPLETE)**: Performance measurement and bottleneck detection
  - New library: `plugins/autonomous-dev/lib/performance_profiler.py` (539 lines)
  - Features: PerformanceTimer context manager, JSON logging, aggregate metrics, bottleneck detection
  - Test coverage: 71/78 tests passing (91%)
  - Integration: Agents wrapped in PerformanceTimer for automatic timing
  - Enables Phase 7+ optimization decisions based on real data
- **Phase 7 (Parallel Validation Checkpoint - COMPLETE)**: Validates reviewer, security-auditor, doc-master parallel execution
  - New method: `AgentTracker.verify_parallel_validation()` in `scripts/agent_tracker.py`
  - Parallel detection: 5-second window for agent start times
  - Metrics: sequential_time, parallel_time, time_saved_seconds, efficiency_percent
  - Helper methods: `_detect_parallel_execution_three_agents()`, `_record_incomplete_validation()`, `_record_failed_validation()`
  - Integration: CHECKPOINT 4.1 added to `plugins/autonomous-dev/commands/auto-implement.md`
  - Test coverage: 23 unit tests covering success, parallelization detection, incomplete/failed agents
  - Infrastructure: Validation checkpoints enable Phase 8+ bottleneck detection
- **Phase 8 (Agent Output Format Cleanup - COMPLETE)**: Streamlined agent output format sections across 20 agents
  - Issue #72: Token measurement infrastructure created (Phase 1)
  - Phase 1 cleanup: 5 agents streamlined (test-master, quality-validator, advisor, alignment-validator, project-progress-tracker) - saved ~1,183 tokens
  - Phase 2 cleanup: 16 agents streamlined (planner, security-auditor, brownfield-analyzer, sync-validator, alignment-analyzer, issue-creator, pr-description-generator, project-bootstrapper, reviewer, commit-message-generator, project-status-analyzer, researcher, implementer, doc-master, setup-wizard, and 1 core workflow agent) - saved ~1,700 tokens
  - All 20 agents now reference agent-output-formats skill for standardized output formatting
  - Combined Phase 1+2 savings: ~2,900 tokens (11.7% reduction)
  - Scripts: measure_agent_tokens.py, measure_output_format_sections.py
  - Test coverage: 137 tests (104 unit + 30 integration + 3 skill tests)
- **Phase 8.5 (Profiler Integration - COMPLETE)**: Real-time performance analysis API
  - Issue #46 Phase 8.5: Integrated profiling analysis into workflow
  - New function: `analyze_performance_logs()` in performance_profiler.py (81 lines)
  - Features: Load metrics, aggregate by agent, detect top 3 slowest agents
  - Enhanced PerformanceTimer: ISO 8601 timestamps with Z suffix, backward compatible
  - Enhanced Metrics: calculate_aggregate_metrics() now includes count field
  - Path validation: Flexible logs/ directory detection for cross-platform test compatibility
  - Test coverage: 27/27 tests passing (100%) - PerformanceTimer, metrics, bottleneck detection, CWE-22 validation
  - Documentation: Comprehensive docstrings with examples, security notes, performance characteristics
  - Foundation: Enables Phase 9 model optimization and Phase 10 smart agent selection
- **Phase 9 (Model Downgrade Strategy - INVESTIGATIVE)**: Cost optimization through model analysis
  - Issue #46 Phase 9: Investigative phase for model downgrade feasibility
  - Test coverage: 11/19 tests passing (58%) - Investigation mode
  - Focus areas: Researcher (Haiku verified optimal), Planner (Sonnet analysis), Other agents (cost-benefit pending)
  - Framework: Performance impact analysis, quality metrics, cost-benefit calculation
  - Timeline: Complete investigation by 2025-11-30
- **Cumulative Improvement** (Issues #63, #64, #72, #46 Phase 8.5): 5-10 minutes saved per workflow (15-35% faster, 25-30% overall improvement)
  - Combined token savings: ~11,980 tokens (20-28% reduction in agent/library prompts)
  - Quality: Preserved via progressive disclosure (skills load on-demand)
  - Scalability: Support for 50-100+ skills without context bloat
  - Profiling: Real-time metrics enable Phase 9+ data-driven optimizations

---

## Batch Feature Processing (Enhanced in v3.24.0)

**Command**: `/batch-implement <features-file>` or `/batch-implement --issues <issue-numbers>` or `/batch-implement --resume <batch-id>`

Process multiple features sequentially with intelligent state management and automatic context clearing.

**Input Options**:

1. **File-based** (plain text file, one feature per line):
```text
# Authentication
Add user login with JWT
Add password reset flow
```

2. **GitHub Issues** (fetch titles directly from GitHub - NEW in v3.24.0):
```bash
/batch-implement --issues 72 73 74
# Fetches: "Issue #72: [title]", "Issue #73: [title]", "Issue #74: [title]"

# Requires gh CLI v2.0+ and authentication (one-time setup):
gh auth login
```

**Workflow**: Parse input → Create batch state → For each: `/auto-implement` + auto-clear at 150K tokens → Summary

**State Management** (Enhanced in v3.24.0):
- **Persistent state**: `.claude/batch_state.json` tracks progress across crashes
- **Auto-clear threshold**: Automatically clears context at 150K tokens (no manual intervention)
- **Crash recovery**: Resume from last completed feature with `--resume` flag
- **Progress tracking**: Completed features, failed features, auto-clear events, issue_numbers, source_type
- **50+ feature support**: State management prevents context bloat at scale
- **GitHub integration**: Tracks original issue numbers for --issues flag workflows

**Resume Operations**:
```bash
# If batch crashes or context exceeds threshold
/batch-implement --resume batch-20251116-123456

# System automatically:
# 1. Loads state from .claude/batch_state.json
# 2. Skips completed features
# 3. Continues from current_index
# 4. Maintains progress across auto-clear events
```

**Use Cases**: Sprint backlogs (10-50 features), overnight processing, technical debt cleanup, large-scale migrations (50+ features)

**Performance**: ~20-30 min per feature (same as `/auto-implement`), automatic state-based context clearing maintains <8K tokens indefinitely

---

## Git Automation Control

Automatic git operations (commit, push, PR creation) are **enabled by default** after `/auto-implement` completes (v3.12.0+). See [docs/GIT-AUTOMATION.md](docs/GIT-AUTOMATION.md) for complete documentation.

**Status**: Default feature (enabled by default with first-run consent, opt-out available)

**First-Run Consent** (v3.12.0+):
- On first `/auto-implement` run, displays interactive consent prompt
- User chooses to enable/disable (default: yes)
- Choice stored in `~/.autonomous-dev/user_state.json`
- Skipped in non-interactive sessions (CI/CD)

**Environment Variables** (opt-out via `.env` file):

```bash
# Master switch - disables automatic git operations after /auto-implement
AUTO_GIT_ENABLED=false       # Default: true (enabled by default)

# Disable automatic push to remote (requires AUTO_GIT_ENABLED=true)
AUTO_GIT_PUSH=false          # Default: true (enabled by default)

# Disable automatic PR creation (requires AUTO_GIT_ENABLED=true and gh CLI)
AUTO_GIT_PR=false            # Default: true (enabled by default)
```

**How It Works**:

1. `/auto-implement` completes STEP 6 (parallel validation)
2. quality-validator agent completes (last validation agent)
3. SubagentStop hook triggers `auto_git_workflow.py`
4. On first run: displays consent prompt; subsequent runs: checks user state + environment variables
5. If enabled (default), invokes commit-message-generator agent to create conventional commit message
6. Stages changes, commits with agent-generated message, optionally pushes and creates PR
7. If any prerequisite fails (git not configured, merge conflicts, etc.), provides manual fallback instructions
8. Feature is successful regardless of git operation outcome (graceful degradation)

**Opt-Out Consent Design** (v3.12.0+):

- Enabled by default - seamless zero-manual-git-operations workflow out of the box
- First-run consent - interactive prompt on first `/auto-implement` run
- User state persistence - choice stored in `~/.autonomous-dev/user_state.json`
- Environment override - `.env` variables override user state preferences
- Validates all prerequisites before attempting operations
- Non-blocking - git automation failures don't affect feature completion
- Always provides manual fallback instructions if automation fails

**Security**:

- Uses `security_utils.validate_path()` for all file path validation (CWE-22, CWE-59)
- Audit logs all operations to `logs/security_audit.log`
- No credential logging - never exposes API keys or passwords
- Subprocess calls prevent command injection attacks
- Safe JSON parsing (no arbitrary code execution)

**Implementation**: `auto_git_workflow.py` hook, `auto_implement_git_integration.py` library, `user_state_manager.py`, `first_run_warning.py`. See `docs/GIT-AUTOMATION.md` and README.md for details.

---


## MCP Auto-Approval Control (v3.21.0+)

Automatic tool approval for trusted subagent operations. Reduces permission prompts from 50+ to 0 during `/auto-implement` workflows.

**Enable**:
```bash
# In .env file
MCP_AUTO_APPROVE=true  # Default: false (opt-in)
```

**Security**: 6 layers of defense (subagent isolation, agent whitelist, tool whitelist, command/path validation, audit logging, circuit breaker). See `docs/TOOL-AUTO-APPROVAL.md` for complete documentation.

**Hook**: `auto_approve_tool.py` (PreToolUse lifecycle)

---
## Architecture

### Agents (20 specialists with active skill integration - GitHub Issue #35, #58, #59)

Located: `plugins/autonomous-dev/agents/`

**Core Workflow Agents (9)** with skill references (orchestrator deprecated v3.2.2 - Claude coordinates directly):
- **researcher**: Web research for patterns and best practices - Uses research-patterns skill
- **planner**: Architecture planning and design - Uses architecture-patterns, api-design, database-design, testing-guide skills
- **test-master**: TDD specialist (writes tests first) - Uses testing-guide, security-patterns skills
- **implementer**: Code implementation (makes tests pass) - Uses python-standards, observability skills
- **reviewer**: Quality gate (code review) - Uses code-review, consistency-enforcement, python-standards skills
- **security-auditor**: Security scanning and vulnerability detection - Uses security-patterns, python-standards skills
- **doc-master**: Documentation synchronization - Uses documentation-guide, consistency-enforcement, git-workflow, cross-reference-validation, documentation-currency skills
- **advisor**: Critical thinking and validation (v3.0+) - Uses semantic-validation, advisor-triggers, research-patterns skills
- **quality-validator**: GenAI-powered feature validation (v3.0+) - Uses testing-guide, code-review skills

**Utility Agents (11)** with skill references:
- **alignment-validator**: PROJECT.md alignment checking - Uses semantic-validation, file-organization skills
- **commit-message-generator**: Conventional commit generation - Uses git-workflow, code-review skills
- **pr-description-generator**: Pull request descriptions - Uses github-workflow, documentation-guide, code-review skills
- **issue-creator**: Generate well-structured GitHub issue descriptions (v3.10.0+, GitHub #58) - Uses github-workflow, documentation-guide, research-patterns skills
- **brownfield-analyzer**: Analyze brownfield projects for retrofit readiness (v3.11.0+, GitHub #59) - Uses research-patterns, semantic-validation, file-organization, python-standards skills
- **project-progress-tracker**: Track progress against goals - Uses project-management skill
- **alignment-analyzer**: Detailed alignment analysis - Uses research-patterns, semantic-validation, file-organization skills
- **project-bootstrapper**: Tech stack detection and setup (v3.0+) - Uses research-patterns, file-organization, python-standards skills
- **setup-wizard**: Intelligent setup - analyzes tech stack, recommends hooks (v3.1+) - Uses research-patterns, file-organization skills
- **project-status-analyzer**: Real-time project health - goals, metrics, blockers (v3.1+) - Uses project-management, code-review, semantic-validation skills
- **sync-validator**: Smart dev sync - detects conflicts, validates compatibility (v3.1+) - Uses consistency-enforcement, file-organization, python-standards, security-patterns skills

**Note on Orchestrator Removal (v3.2.2)**:
The "orchestrator" agent was removed because it created a logical impossibility - it was Claude coordinating Claude. When `/auto-implement` invoked the orchestrator agent, it just loaded orchestrator.md as Claude's system prompt, but it was still the same Claude instance making decisions. This allowed Claude to skip agents by reasoning they weren't needed.

**Solution**: Moved all coordination logic directly into `commands/auto-implement.md`. Now Claude explicitly coordinates the 7-agent workflow without pretending to be a separate orchestrator. Same checkpoints, simpler architecture, more reliable execution. See `agents/archived/orchestrator.md` for history.

### Skills (27 Active - Progressive Disclosure + Agent Integration)

**Status**: 27 active skill packages using Claude Code 2.0+ progressive disclosure architecture

**Why Active**:
- Skills are **first-class citizens** in Claude Code 2.0+ (fully supported pattern)
- Progressive disclosure solves context bloat elegantly
- Metadata stays in context, full content loads only when needed
- Can scale to 100+ skills without performance issues
- **NEW (v3.5+)**: All 18 agents explicitly reference relevant skills for enhanced decision-making (Issue #35)
- **NEW (v3.14.0+)**: Agents reference agent-output-formats and error-handling-patterns skills for 18-25% token reduction (Issues #63, #64)
- **NEW (v3.15.0+)**: All 20 agents reference agent-output-formats skill for standardized output formatting (Issue #72)

**27 Active Skills** (organized by category):
- **Core Development** (7): api-design, architecture-patterns, code-review, database-design, testing-guide, security-patterns, error-handling-patterns
- **Workflow & Automation** (7): git-workflow, github-workflow, project-management, documentation-guide, agent-output-formats, skill-integration, skill-integration-templates
- **Code & Quality** (4): python-standards, observability, consistency-enforcement, file-organization
- **Validation & Analysis** (6): research-patterns, semantic-validation, cross-reference-validation, documentation-currency, advisor-triggers, project-alignment-validation
- **Library Design** (3): library-design-patterns, state-management-patterns, api-integration-patterns

**How It Works**:
1. **Progressive Disclosure**: Skills auto-activate based on task keywords. Claude loads full SKILL.md content only when relevant, keeping context efficient.
2. **Agent Integration** (NEW): Each agent's prompt includes a "Relevant Skills" section listing specialized knowledge available for that agent's domain. This helps agents recognize when to apply specialized skills.
3. **Combined Effect**: Agent + skill integration prevents hallucination while scaling to 100+ skills without context bloat.

**Agent-Skill Mapping** (all 18 agents now have skill references):
- See agent prompts in `plugins/autonomous-dev/agents/` for "Relevant Skills" sections
- See `docs/SKILLS-AGENTS-INTEGRATION.md` for comprehensive mapping table

**Token Reduction Benefits** (Issues #63, #64, #72):
- agent-output-formats skill: 20 agents reference standardized output formats
- error-handling-patterns skill: 22 libraries reference standardized error handling
- **NEW (v3.17.0+)**: Enhanced testing-guide skill with comprehensive testing patterns (Issue #65)
  - 4 new documentation files: pytest-patterns.md, coverage-strategies.md, arrange-act-assert.md, plus skill metadata enhancements
  - 3 Python templates: unit-test-template.py, integration-test-template.py, fixture-examples.py
  - Progressive disclosure: ~10,000 tokens available on-demand, only ~50 tokens context overhead
  - implementer agent now references testing-guide skill for TDD guidance
  - Total: 2,557 lines of comprehensive testing guidance
  - Test coverage: 27/28 tests passing (96.4%)
  - test-master agent streamlined (Phase 8.3): Removed inline "Test Quality" section, now references testing-guide skill (~18 tokens saved)
- **NEW (v3.18.0+)**: Enhanced documentation-guide skill with documentation standards (Issue #66 Phase 8.4)
  - 4 new documentation files: parity-validation.md, changelog-format.md, readme-structure.md, docstring-standards.md
  - 3 template files: docstring-template.py, readme-template.md, changelog-template.md
  - Progressive disclosure: ~15,000+ tokens available on-demand, only ~50 tokens context overhead
  - 9 agents now reference documentation-guide skill: doc-master, reviewer, implementer, issue-creator, pr-description-generator, alignment-analyzer, project-bootstrapper, project-status-analyzer, setup-wizard
  - Total: 1,709 lines of documentation standards guidance
  - Test coverage: 48 tests passing (38 unit + 10 integration)
  - Token savings: ~280 tokens (4-6% reduction across 9 agents)
- **NEW (v3.19.0+)**: New skill-integration skill for standardized skill architecture patterns (Issue #67-68)
  - **Phase 1 (Skill Infrastructure - COMPLETE - v3.19.0)**:
    - Skill composition, discovery, and progressive disclosure architecture
    - 3 documentation files: progressive-disclosure.md, skill-discovery.md, skill-composition.md
    - 3 example templates: agent-skill-reference-template.md, progressive-disclosure-diagram.md, skill-composition-example.md
    - Progressive disclosure: ~3,000 tokens available on-demand, only ~40 tokens context overhead
    - Total: 385 lines of skill integration guidance
    - Enhanced git-workflow skill with advanced workflow patterns (Issue #67)
    - Enhanced github-workflow skill v1.1.0 with PR and issue automation patterns (Issue #68)
    - Combined enhancements: ~1,200+ additional tokens of guidance via progressive disclosure
  - **Phase 2 (Agent Streamlining - COMPLETE - v3.19.0)**:
    - Streamlined commit-message-generator agent: ~702 tokens saved (references git-workflow skill)
    - Streamlined issue-creator agent: ~271 tokens saved (references github-workflow skill)
    - Combined Phase 2 savings: ~973 tokens (5-8% reduction in git/github-related agents)
    - Test coverage: 30 unit tests passing in test_git_github_workflow_enhancement.py
    - Integration tests: token_reduction_workflow.py validates savings targets
  - **Phase 3 (github-workflow Documentation Expansion - COMPLETE - v3.20.1)**:
    - Enhanced github-workflow skill to v1.2.0 with comprehensive automation documentation
    - 4 new documentation files: pr-automation.md (~2,907 tokens), issue-automation.md (~3,922 tokens), github-actions-integration.md (~2,842 tokens), api-security-patterns.md (~3,430 tokens)
    - 3 new example files: pr-automation-workflow.yml (~776 tokens), issue-automation-workflow.yml (~1,347 tokens), webhook-handler.py (~2,175 tokens)
    - Total: 3,813 lines (2,251 docs + 562 examples) = ~17,399 tokens of automation guidance
    - Progressive disclosure: ~17,400 tokens on-demand, only ~50 tokens SKILL.md overhead
    - Keywords expanded: Added pr-automation, issue-automation, webhook, auto-labeling, auto-merge, automation, api-security
    - Covers: PR automation workflows, issue automation patterns, GitHub Actions integration, webhook security, API best practices
    - Test coverage: 16 new tests validating documentation, examples, and SKILL.md synchronization
- **NEW (v3.26.0+)**: Phase 8.6 - Extract skill-integration-templates skill (Issue #72 continuation)
  - **1 New Skill**: skill-integration-templates
  - **Skill-integration-templates skill** (11 files, ~1,200 tokens):
    - 4 documentation files: skill-reference-syntax.md, agent-action-verbs.md, progressive-disclosure-usage.md, integration-best-practices.md
    - 3 template files: skill-section-template.md, intro-sentence-templates.md, closing-sentence-templates.md
    - 3 example files: planner-skill-section.md, implementer-skill-section.md, minimal-skill-reference.md
    - Covers: Skill reference syntax, action verbs, progressive disclosure usage, integration patterns
  - **20 Agents Enhanced**: All 20 agents now reference skill-integration-templates skill for standardized skill section formatting
  - **Token Reduction**: ~800 tokens saved (~3.5% reduction across all agents)
  - **Test Coverage**: 30 tests (23 unit + 7 integration) validating skill structure, documentation, templates
  - **Progressive Disclosure**: ~1,200 tokens of integration patterns available on-demand, only ~50 tokens SKILL.md overhead
  - **Impact**: Standardizes skill reference formatting across all agents, enables consistent progressive disclosure usage
- **NEW (v3.25.0+)**: Phase 8.7 - Extract project-alignment-validation skill (Issue #72 continuation)
  - **1 New Skill**: project-alignment-validation
  - **Project-alignment-validation skill** (11 files, ~2,200 tokens):
    - 4 documentation files: gap-assessment-methodology.md, semantic-validation-approach.md, conflict-resolution-patterns.md, alignment-checklist.md
    - 3 template files: gap-assessment-template.md, alignment-report-template.md, conflict-resolution-template.md
    - 3 example files: project-md-structure-example.md, alignment-scenarios.md, misalignment-examples.md
    - Covers: Gap assessment, semantic validation, conflict resolution, alignment checklists, PROJECT.md structure patterns
  - **12 Files Enhanced**: alignment-validator, alignment-analyzer, validate_project_alignment hook, and 9 libraries now reference project-alignment-validation skill
  - **Token Reduction**: ~800-1,200 tokens saved (2-4% reduction across alignment agents and libraries)
  - **Test Coverage**: 86 tests (65 unit + 21 integration) in 3 test files
  - **Progressive Disclosure**: ~2,200 tokens of alignment patterns available on-demand, only ~50 tokens SKILL.md overhead
  - **Agents Updated**: alignment-validator, alignment-analyzer, project-bootstrap, brownfield-analyzer, sync-validator, detect_feature_request hook, enforce_pipeline_complete hook, validate_project_alignment hook, validate_documentation_alignment hook
- **NEW (v3.24.1+)**: Phase 8.8 - Library audit and pattern extraction (Issue #72 continuation)
  - **3 New Skills**: library-design-patterns, state-management-patterns, api-integration-patterns
  - **Library-design-patterns skill** (532 lines):
    - 4 documentation files: progressive-enhancement.md, two-tier-design.md, security-patterns.md, docstring-standards.md
    - 3 template files: library-template.py, cli-template.py, docstring-template.py
    - 3 example files: progressive-enhancement-example.py, two-tier-example.py, security-validation-example.py
    - Covers: Progressive enhancement pattern, two-tier architecture, security validation, docstring standards
  - **State-management-patterns skill** (289 lines):
    - 1 documentation file: json-persistence.md
    - 3 template files: state-manager-template.py, atomic-write-template.py, file-lock-template.py
    - Covers: JSON state persistence, atomic write operations, file locking patterns
  - **API-integration-patterns skill** (357 lines):
    - 4 template files: github-api-template.py, retry-decorator-template.py, subprocess-executor-template.py
    - 1 example file: safe-subprocess-example.py
    - Covers: GitHub API integration, retry logic, subprocess security, command injection prevention
  - **35 Libraries Enhanced**: All libraries now reference relevant skills for standardized patterns
  - **Token Reduction**: ~1,880 tokens saved (6-8% reduction across library docstrings)
  - **Test Coverage**: 181 tests (147 unit + 34 integration) in 4 test files
  - **Progressive Disclosure**: ~3,500 tokens of library patterns available on-demand, only ~150 tokens SKILL.md overhead
- **Agent Output Format Cleanup** (v3.16.0+): Phase 2 - removed verbose Output Format sections from 16 additional agents (Issue #72)
  - Phase 1 agents (v3.15.0): test-master, quality-validator, advisor, alignment-validator, project-progress-tracker (saved ~1,183 tokens)
  - Phase 2 agents (v3.16.0): planner, security-auditor, brownfield-analyzer, sync-validator, alignment-analyzer, issue-creator, pr-description-generator, project-bootstrapper, reviewer, commit-message-generator, project-status-analyzer, researcher, implementer, doc-master, setup-wizard, and 1 core workflow agent (saved ~1,700 tokens)
  - Output Format sections streamlined to reference agent-output-formats skill
  - Combined Phase 1+2 token savings: ~2,900 tokens (11.7% reduction across all agents)
  - No sections exceed 30-line threshold after cleanup
- Combined token savings: ~16,833-17,233 tokens (26-35% reduction in agent/library prompts)
  - v3.26.0 Phase 8.6: ~800 tokens (skill-integration-templates skill)
  - v3.25.0 Phase 8.7: ~800-1,200 tokens (project-alignment-validation skill)
  - v3.24.1 Phase 8.8: ~1,880 tokens (library-design-patterns, state-management-patterns, api-integration-patterns skills)
  - v3.19.0 Phase 2: ~973 tokens (commit-message-generator + issue-creator streamlining)
  - Previous phases: ~11,980 tokens (agent-output-formats, error-handling-patterns, testing-guide, documentation-guide, skill-integration)
- Tests: 624 passing (245 base + 65 documentation-guide + 30 git/github-workflow + 181 library-design + 86 alignment-validation + 30 skill-integration-templates skill tests)

See `docs/SKILLS-AGENTS-INTEGRATION.md` for complete architecture details and agent-skill mapping table.

### Libraries (21 Documented Libraries)

**Location**: `plugins/autonomous-dev/lib/`

**Purpose**: Reusable Python libraries for security, validation, automation, and brownfield retrofit

**Note**: 21 key user-facing libraries documented below and in `docs/LIBRARIES.md` (15 core/utility + 6 brownfield). All libraries reference relevant skills (library-design-patterns, state-management-patterns, api-integration-patterns, project-alignment-validation) for standardized patterns and token reduction (Phase 8.7-8.8 - v3.25.0)

**Core Libraries (15)**:
1. **security_utils.py** - Security validation and audit logging (CWE-22, CWE-59, CWE-117)
2. **project_md_updater.py** - Atomic PROJECT.md updates with merge conflict detection
3. **version_detector.py** - Semantic version comparison for marketplace sync
4. **orphan_file_cleaner.py** - Orphaned file detection and cleanup
5. **sync_dispatcher.py** - Intelligent sync orchestration (marketplace/env/plugin-dev)
6. **validate_marketplace_version.py** - CLI script for version validation
7. **plugin_updater.py** - Interactive plugin update with backup/rollback
8. **update_plugin.py** - CLI interface for plugin updates
9. **hook_activator.py** - Automatic hook activation during updates
10. **validate_documentation_parity.py** - Documentation consistency validation
11. **auto_implement_git_integration.py** - Automatic git operations (commit/push/PR)
12. **github_issue_automation.py** - GitHub issue creation with research
13. **batch_state_manager.py** - State-based auto-clearing for /batch-implement (v3.23.0)
14. **github_issue_fetcher.py** - GitHub issue fetching via gh CLI (v3.24.0)
15. **math_utils.py** - Fibonacci calculator with multiple algorithms (iterative, recursive, matrix exponentiation)

**Brownfield Retrofit Libraries (6)** - 5-phase retrofit system for existing projects:
16. **brownfield_retrofit.py** - Phase 0: Project analysis and tech stack detection
17. **codebase_analyzer.py** - Phase 1: Deep codebase analysis (multi-language)
18. **alignment_assessor.py** - Phase 2: Gap assessment and 12-Factor compliance
19. **migration_planner.py** - Phase 3: Migration plan with dependency tracking
20. **retrofit_executor.py** - Phase 4: Step-by-step execution with rollback
21. **retrofit_verifier.py** - Phase 5: Verification and readiness assessment

**Design Pattern**: Progressive enhancement (string → path → whitelist) for graceful error recovery. Non-blocking enhancements don't block core operations. Two-tier design (core logic + CLI interface) enables reuse and testing.

**For detailed API documentation**: See `docs/LIBRARIES.md`

### Hooks (42 total automation)

Located: `plugins/autonomous-dev/hooks/`

**Core Hooks (11)**:
- `auto_format.py`: black + isort (Python), prettier (JS/TS)
- `auto_test.py`: pytest on related tests
- `security_scan.py`: Secrets detection, vulnerability scanning
- `validate_project_alignment.py`: PROJECT.md validation
- `validate_claude_alignment.py`: CLAUDE.md alignment checking (v3.0.2+)
- `enforce_file_organization.py`: Standard structure enforcement
- `enforce_pipeline_complete.py`: Validates all 7 agents ran (v3.2.2+)
- `enforce_tdd.py`: Validates tests written before code (v3.0+)
- `detect_feature_request.py`: Auto-detect feature requests
- `auto_git_workflow.py`: Automatic git operations after /auto-implement (v3.9.0+, SubagentStop lifecycle)
- `auto_approve_tool.py`: MCP auto-approval for subagent tool calls (v3.21.0+, PreToolUse lifecycle)

**Optional/Extended Hooks (20)**:
- `auto_enforce_coverage.py`: 80% minimum coverage
- `auto_fix_docs.py`: Documentation consistency
- `auto_add_to_regression.py`: Regression test tracking
- `auto_track_issues.py`: GitHub issue tracking
- `auto_generate_tests.py`: Auto-generate test boilerplate
- `auto_sync_dev.py`: Sync development changes
- `auto_tdd_enforcer.py`: Strict TDD enforcement
- `auto_update_docs.py`: Auto-update documentation
- `auto_update_project_progress.py`: Auto-update PROJECT.md goals after /auto-implement (v3.4.0+)
- `detect_doc_changes.py`: Detect documentation changes
- `enforce_bloat_prevention.py`: Prevent context bloat
- `enforce_command_limit.py`: Command count limits
- `post_file_move.py`: Post-move validation
- `validate_documentation_alignment.py`: Doc alignment checking
- `validate_session_quality.py`: Session quality validation
- Plus 5 others for extended enforcement and validation

**Lifecycle Hooks**:
- `UserPromptSubmit`: Display project context
- `SubagentStop`: Log agent completion to session; auto-update PROJECT.md progress (v3.4.0+); auto-detect Task tool agents (v3.8.3+)

---

## CLAUDE.md Alignment (New in v3.0.2)

**What it is**: System to detect and prevent drift between documented standards and actual codebase

**Why it matters**: CLAUDE.md defines development practices. If it drifts from reality, new developers follow outdated practices.

**Check alignment**:
```bash
# Automatic (via hook)
git commit -m "feature"  # Hook validates CLAUDE.md is in sync

# Manual check
python .claude/hooks/validate_claude_alignment.py
```

**What it validates**:
- Version consistency (global vs project CLAUDE.md vs PROJECT.md)
- Agent counts match reality (currently 18 agents, orchestrator removed v3.2.2)
- Command counts match installed commands (currently 17 active commands per GitHub #47 /sync unification)
- Documented features actually exist
- Security requirements documented
- Best practices are up-to-date

**If drift detected**:
1. Run validation to see specific issues
2. Update CLAUDE.md with actual current state
3. Commit the alignment fix
4. Hooks ensure all features stay in sync

## Troubleshooting

### "Context budget exceeded"

```bash
/clear  # Then retry
```

### "Feature doesn't align with PROJECT.md"

1. Check goals: `cat .claude/PROJECT.md | grep GOALS`
2. Either: Modify feature to align
3. Or: Update PROJECT.md if direction changed

### "CLAUDE.md alignment drift detected"

This means CLAUDE.md is outdated. Fix it:
```bash
# See what's drifted
python .claude/hooks/validate_claude_alignment.py

# Update CLAUDE.md based on findings
vim CLAUDE.md  # Update version, counts, descriptions

# Commit the fix
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md alignment"
```

### "Agent can't use tool X"

Tool restrictions are intentional (security). If genuinely needed:
```bash
vim plugins/autonomous-dev/agents/[agent].md
# Add to tools: [...] list in frontmatter
```

### "Commands not updating after plugin changes"

**CRITICAL**: `/exit` does NOT reload commands! You need a full restart.

**The Problem**:
- `/exit` - Only ends the current conversation, process keeps running
- Closing window - Process may still run in background
- `/clear` - Only clears conversation history

**The Solution**:
1. **Fully quit Claude Code** - Press `Cmd+Q` (Mac) or `Ctrl+Q` (Linux/Windows)
2. **Verify it's dead**: `ps aux | grep claude | grep -v grep` should return nothing
3. **Wait 5 seconds** for process to fully exit
4. **Restart Claude Code**
5. **Verify**: Commands should now be updated

**Why**: Claude Code caches command definitions in memory at startup. The only way to reload commands is to completely restart the application process.

**When you need a full restart**:
- After installing/updating plugins
- After modifying command files
- After syncing plugin changes
- When new commands don't appear in autocomplete

---

## MCP Server (Optional)

For enhanced Claude Desktop integration, configure the MCP server:

**Location**: `.mcp/config.json`

**Provides**:
- Filesystem access (read/write repository files)
- Shell commands (git, python, npm, etc.)
- Git operations (status, diff, commit)
- Python interpreter (with virtualenv)

**Setup**:
```bash
# See .mcp/README.md for full setup instructions
```

---

## Quick Reference

### Installation
```bash
# 1. Add marketplace
/plugin marketplace add akaszubski/autonomous-dev

# 2. Install plugin
/plugin install autonomous-dev

# 3. Exit and restart Claude Code (REQUIRED!)
# Press Cmd+Q (Mac) or Ctrl+Q (Linux/Windows)
```

**Done!** All commands immediately work.

### Optional Setup
```bash
# Only if you want automatic hooks (auto-format on save, etc.)
python .claude/hooks/setup.py
```

### Updating
```bash
# 1. Uninstall
/plugin uninstall autonomous-dev

# 2. Exit and restart Claude Code (REQUIRED!)

# 3. Reinstall
/plugin install autonomous-dev

# 4. Exit and restart again
```

### Daily Workflow
```bash
# Start feature
# (describe feature to Claude)

# After feature completes (optional - for optimal performance)
/clear
```

### Check Session Logs
```bash
cat docs/sessions/$(ls -t docs/sessions/ | head -1)
```

### Update Goals
```bash
vim .claude/PROJECT.md
```

---

## Philosophy

**Automation > Reminders > Hope**

- Automate repetitive tasks (formatting, testing, security, docs)
- Use agents, skills, hooks to enforce quality automatically
- Focus on creative work, not manual checks

**Research First, Test Coverage Required**

- Always research before implementing
- Always write tests first (TDD)
- Always document changes
- Make quality automatic, not optional

**Context is Precious**

- Clear context after features (`/clear` - recommended for optimal performance)
- Use session files for communication
- Stay under 8K tokens per feature
- Scale to 100+ features

---

**For detailed guides**:
- **Users**: See `plugins/autonomous-dev/README.md` for installation and usage
- **Contributors**: See `docs/DEVELOPMENT.md` for dogfooding setup and development workflow

**For code standards**: See CLAUDE.md best practices, agent prompts, and skills for guidance

**For security**: See `docs/SECURITY.md` for security audit and hardening guidance

**Last Updated**: 2025-11-16 (Enhanced testing-guide skill - GitHub Issue #65, Skill-Based Token Reduction - GitHub Issues #63, #64, #72)
