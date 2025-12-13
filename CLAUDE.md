# Claude Code Bootstrap - Project Instructions

**Last Updated**: 2025-12-09
**Project**: Autonomous Development Plugin for Claude Code 2.0
**Version**: v3.40.0

> **📘 Maintenance Guide**: See `docs/MAINTAINING-PHILOSOPHY.md` for how to keep the core philosophy active as you iterate

---

## Installation (Bootstrap-First)

```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
# Restart Claude Code (Cmd+Q / Ctrl+Q)
/setup
```

**Why not marketplace alone?** autonomous-dev requires global infrastructure that the marketplace cannot configure: `~/.claude/hooks/`, `~/.claude/lib/`, and `~/.claude/settings.json`. See [docs/BOOTSTRAP_PARADOX_SOLUTION.md](docs/BOOTSTRAP_PARADOX_SOLUTION.md) for complete explanation.

## Project Overview

**autonomous-dev** - Plugin repository for autonomous development in Claude Code.

**Core Plugin**: `autonomous-dev` - 20 AI agents, 28 skills, automation hooks, and slash commands for autonomous feature development

**Commands (20 active, includes /align-project-retrofit for brownfield adoption and /batch-implement for sequential processing)**:

**Core Workflow (11)**:
- `/auto-implement` - Autonomous feature development (Claude coordinates 7 agents, auto-close GitHub issues v3.22.0)
- `/batch-implement <file>` - Sequential feature processing with automatic context management and intelligent retry for transient failures (prevents context bloat) - GitHub #74, #89
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
# Log action (works from any directory, including user projects)
python plugins/autonomous-dev/scripts/session_tracker.py agent_name "message"

# View latest session
cat docs/sessions/$(ls -t docs/sessions/ | head -1)
```

**Result**: Context stays small (200 tokens vs 5,000+ tokens)

**Note**: Issue #79 (v3.28.0+) moved session tracking to portable library-based design:
- `plugins/autonomous-dev/lib/path_utils.py` (section 15) - Dynamic project root detection
- `plugins/autonomous-dev/lib/validation.py` (section 16) - Security validation for paths
- `plugins/autonomous-dev/lib/session_tracker.py` (section 25) - Core logging library
- `plugins/autonomous-dev/lib/agent_tracker.py` (section 24) - Agent checkpoint tracking with `save_agent_checkpoint()` class method (NEW v3.36.0)
- `plugins/autonomous-dev/scripts/session_tracker.py` - CLI wrapper (current location)
- `scripts/session_tracker.py` - DEPRECATED (removed v4.0.0), delegates to lib version
- Works from any directory (user projects, subdirectories) via `path_utils.get_session_dir()` and `AgentTracker.save_agent_checkpoint()`
- See `docs/LIBRARIES.md` (sections 15, 16, 24, 25) and GitHub Issue #79 for complete details

**Enhanced** (v3.36.0): Added `AgentTracker.save_agent_checkpoint()` class method:
- Convenience method for agents to save checkpoints without managing instances
- Solves dogfooding bug where hardcoded paths caused 7+ hour stalls
- Portable path detection works from any directory
- Graceful degradation in user projects (returns False, doesn't block workflow)
- No subprocess calls (uses Python imports instead)
- See `docs/DEVELOPMENT.md` Scenario 2.5 for integration pattern

**Related**: Issue #85 (v3.30.0+) fixed `/auto-implement` checkpoints to use portable path detection:
- CHECKPOINT 1 (line 109) and CHECKPOINT 4.1 (line 390) replaced hardcoded paths with dynamic detection
- Same portable path detection strategy as tracking infrastructure (path_utils and fallback)
- Works from any directory on any machine (not just developer's path)
- See `plugins/autonomous-dev/commands/auto-implement.md` for checkpoint implementation details

**Enhanced**: Issue #82 (v3.33.0+, Unreleased) made checkpoint verification optional with graceful degradation:
- Checkpoints work in both user projects (skips verification) and autonomous-dev repo (full verification)
- **User projects**: AgentTracker unavailable → silent skip with informational message (ℹ️)
- **Dev repo**: AgentTracker available → full verification with efficiency metrics (✅/❌)
- **Broken scripts**: Never blocks workflow, always shows clear warning (⚠️) and continues
- Enables `/auto-implement` to work anywhere without requiring plugins/ directory structure
- See `plugins/autonomous-dev/commands/auto-implement.md` for graceful degradation pattern

---

## Documentation Principles

### Honesty Over Marketing

**Principle**: Documentation must reflect reality, not aspirations. Users who follow docs exactly should experience what's written.

**Standards**:

1. **State real-world limits, not aspirational targets**
   - ✅ Good: "4-5 features per session (context limit)"
   - ❌ Bad: "50+ features" (without mentioning resume workflow is required)

2. **Include failure modes and workarounds**
   - ✅ Good: "Context typically fills at 4-5 features. Use `--resume` to continue."
   - ❌ Bad: "Supports unlimited features" (hiding the context limit)

3. **Use hedging language for variable outcomes**
   - Use: "typically", "expect", "usually", "often", "may"
   - Avoid: "always", "guaranteed", "never fails", "unlimited"

4. **Prohibited practices**:
   - Unvalidated claims (no "up to X" without typical case)
   - Hiding known limitations
   - Marketing speak without disclaimers
   - Best-case scenarios without typical-case context

**Test**: "If a new user follows the docs exactly, will their experience match what's written? If not, fix the docs."

**Metrics That Matter**:
- Lead with typical case, not best case
- State conditions (hardware, context size, feature complexity)
- Include what happens at limits and recovery path

**Examples**:

```markdown
# Good
**Typical batch**: 4-5 features (~2 hours) before context reset needed
Context limits (be realistic): Each feature consumes ~25-35K tokens.

# Bad
**50+ feature support** (proven with state management)
Process unlimited features with automatic context management
```

**Philosophy**: Under-promise, over-deliver. We're not selling — we're documenting reality. The value proposition is strong enough without inflating claims.

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

**Performance Baseline**: 15-25 minutes per workflow (25-30% overall improvement from 28-44 min baseline)

**Optimization History** (10 phases complete - see [docs/PERFORMANCE-HISTORY.md](docs/PERFORMANCE-HISTORY.md) for details):
- **Phase 4**: Haiku model for researcher (3-5 min saved)
- **Phase 5**: Prompt simplification (2-4 min saved)
- **Phase 6**: Profiling infrastructure (PerformanceTimer, JSON logging)
- **Phase 7**: Parallel validation (60% faster - 5 min → 2 min)
- **Phase 8**: Agent output cleanup (~2,900 tokens saved)
- **Phase 8.5**: Real-time performance analysis API
- **Phase 9**: Model downgrade strategy (investigative)
- **Phase 10**: Smart agent selection (Issue #120 - 95% faster for typos/docs, TDD red phase complete)
- **Cumulative**: ~11,980 tokens saved, 50-100+ skills supported

See [docs/PERFORMANCE.md](docs/PERFORMANCE.md) for benchmarks and [docs/PERFORMANCE-HISTORY.md](docs/PERFORMANCE-HISTORY.md) for complete phase details.

---

## Batch Feature Processing (Enhanced in v3.24.0, Simplified in v3.32.0 - Issue #88, Automatic retry v3.33.0 - Issue #89, Git automation v3.36.0 - Issue #93)

Process multiple features sequentially with intelligent state management, automatic context management, and per-feature git automation. See [docs/BATCH-PROCESSING.md](docs/BATCH-PROCESSING.md) for complete documentation.

**Command**: `/batch-implement <features-file>` or `/batch-implement --issues <issue-numbers>` or `/batch-implement --resume <batch-id>`

**Key Features**:
- **File-based input**: Plain text file, one feature per line
- **GitHub Issues**: Fetch titles via `--issues` flag (requires gh CLI v2.0+)
- **State management**: `.claude/batch_state.json` tracks progress across crashes
- **Git automation** (v3.36.0, Issue #93): Per-feature commits with conventional messages, optional push/PR
  - **Automatic commits**: Each feature gets individual commit with agent-generated message
  - **Optional push**: Use `AUTO_GIT_PUSH=false` for local commits only
  - **Optional PR**: Use `AUTO_GIT_PR=false` to skip pull request creation
  - **No prompts**: Batch mode skips interactive consent prompts (uses `.env` configuration)
  - **Audit trail**: All git operations recorded in batch_state.json for debugging
  - **Non-blocking failures**: Git errors don't stop batch processing
- **Hybrid context management**: Auto-pause at ~150K tokens, manual `/clear` + `--resume` to continue
- **Resume support**: `--resume <batch-id>` continues from last completed feature
- **Automatic retry** (v3.33.0, Issue #89): Intelligent classification and retry for transient failures
  - **Transient**: Network errors, timeouts, API rate limits (automatically retried up to 3x)
  - **Permanent**: Syntax errors, import errors, type errors (never retried)
  - **Safety limits**: Max 3 retries per feature, circuit breaker after 5 consecutive failures
  - **Consent-based**: First-run prompt (can be overridden via `BATCH_RETRY_ENABLED` env var)
- **Unattended**: 4-5 features run without intervention (~2 hours)
- **Extended batches**: 50+ features via pause/resume cycles (manual `/clear` needed)

**Performance**: ~20-30 min per feature

**Typical workflows**:
- **Short batches (4-5 features)**: Fully unattended (~2 hours)
- **Extended batches (50+ features)**: System pauses at ~150K tokens, you run `/clear`, then `--resume <batch-id>`

**Context Reality**: Each feature consumes ~25-35K tokens across full pipeline. After 4-5 features (~150K tokens), system pauses for manual context reset. This is intentional design, not a limitation — enables unlimited batch sizes via pause/resume workflow.

---

## Git Automation Control

Automatic git operations (commit, push, PR creation, issue closing) are **enabled by default** after `/auto-implement` completes (v3.12.0+, issue closing added v3.22.0). See [docs/GIT-AUTOMATION.md](docs/GIT-AUTOMATION.md) for complete documentation.

**Control**:
- **First-run consent**: Interactive prompt on first use (default: enabled)
- **Environment variables**: `AUTO_GIT_ENABLED`, `AUTO_GIT_PUSH`, `AUTO_GIT_PR` (opt-out via `.env`)
- **State persistence**: Choice stored in `~/.autonomous-dev/user_state.json`

**Workflow**:
1. quality-validator completes → triggers `auto_git_workflow.py` hook
2. commit-message-generator creates conventional commit
3. Stages, commits, optionally pushes and creates PR
4. Graceful degradation if prerequisites fail

**Security**: Path validation (CWE-22, CWE-59), audit logging, no credential exposure, injection prevention

---


## MCP Auto-Approval Control (v3.40.0+)

Automatic tool approval for trusted operations in both **main conversation** and **subagent workflows**. Reduces permission prompts from 50+ to 0 during development.

**Enable**:
```bash
# In .env file
MCP_AUTO_APPROVE=true  # Default: false (opt-in) - Auto-approves everywhere (main + subagents)
# OR
MCP_AUTO_APPROVE=subagent_only  # Legacy mode - Only auto-approve in subagents
```

**Policy v2.0 (Permissive Mode)**:
- **Blacklist-first**: Approves all commands by default, blocks only dangerous patterns
- **Zero friction**: No manual whitelist additions needed for standard dev commands
- **Comprehensive blacklist**: Covers destructive ops, privilege escalation, shell injection, force push, publishing

**Security**: 6 layers of defense (MCP security validation, user consent, tool whitelist, command/path validation, audit logging, circuit breaker). See `docs/TOOL-AUTO-APPROVAL.md` for complete documentation.

**Hook**: `pre_tool_use.py` (PreToolUse lifecycle standalone script, chains MCP security + auto-approval)
**Policy**: `plugins/autonomous-dev/config/auto_approve_policy.json` (v2.0 permissive mode)

---
## Architecture

### Agents (20 specialists with active skill integration - GitHub Issue #35, #58, #59)

20 specialized agents with skill integration for autonomous development. See [docs/AGENTS.md](docs/AGENTS.md) for complete details.

**Core Workflow Agents (9)** (orchestrator deprecated v3.2.2 - Claude coordinates directly):
researcher, planner, test-master, implementer, reviewer, security-auditor, doc-master, advisor, quality-validator

**Utility Agents (11)**:
alignment-validator, commit-message-generator, pr-description-generator, issue-creator, brownfield-analyzer, project-progress-tracker, alignment-analyzer, project-bootstrapper, setup-wizard, project-status-analyzer, sync-validator

**Key Features**:
- Each agent references relevant skills (progressive disclosure)
- Parallel validation: reviewer + security-auditor + doc-master (60% faster)
- Orchestrator removed v3.2.2 (Claude coordinates directly from auto-implement.md)

### Model Tier Strategy

Agent model assignments are optimized for cost-performance balance based on task complexity:

**Tier 1: 8 Haiku agents** - Fast, cost-effective for pattern matching and structured output
- researcher - Pattern discovery and codebase search
- reviewer - Code quality checks against style guide
- doc-master - Documentation synchronization
- commit-message-generator - Conventional commit formatting
- alignment-validator - PROJECT.md validation
- project-progress-tracker - Progress tracking and reporting
- sync-validator - Development environment sync validation
- pr-description-generator - PR description formatting

**Tier 2: 10 Sonnet agents** - Balanced reasoning for implementation and planning
- implementer - Code implementation to make tests pass
- test-master - TDD test generation with comprehensive coverage
- planner - Architecture and implementation planning
- issue-creator - GitHub issue creation with research
- setup-wizard - Interactive project setup
- project-bootstrapper - Project initialization
- brownfield-analyzer - Legacy codebase analysis
- quality-validator - Final validation orchestration
- alignment-analyzer - PROJECT.md conflict resolution
- project-status-analyzer - Project status assessment

**Tier 3: 2 Opus agents** - Deep reasoning for critical analysis
- security-auditor - OWASP security scanning and vulnerability detection
- advisor - Critical thinking, trade-off analysis, risk identification

**Rationale**:
- **Tier 1 (Haiku)**: Tasks with clear patterns, structured output, or simple validation (research, formatting, sync checks)
- **Tier 2 (Sonnet)**: Complex implementation, test design, and planning requiring strong reasoning (TDD, architecture, code)
- **Tier 3 (Opus)**: Critical security and architectural decisions requiring maximum depth (security audits, trade-off analysis)

**Performance Impact**: Optimized tier assignments reduce costs by 40-60% while maintaining quality standards across all workflows.

### Skills (28 Active - Progressive Disclosure + Agent Integration - Issue #110)

28 specialized skill packages using progressive disclosure to prevent context bloat while scaling to 100+ skills.

**Issue #110 Completion (v3.41.0)**: All 28 skills now under 500-line official limit. 16 skills refactored with progressive disclosure pattern: compact SKILL.md files (87-315 lines) with detailed content moved to docs/ subdirectories (~6,000+ lines of detailed guides, examples, and references).

**Categories**:
- **Core Development** (7): api-design, architecture-patterns, code-review, database-design, testing-guide, security-patterns, error-handling-patterns
- **Workflow & Automation** (7): git-workflow, github-workflow, project-management, documentation-guide, agent-output-formats, skill-integration, skill-integration-templates
- **Code & Quality** (4): python-standards, observability, consistency-enforcement, file-organization
- **Validation & Analysis** (6): research-patterns, semantic-validation, cross-reference-validation, documentation-currency, advisor-triggers, project-alignment-validation
- **Library Design** (3): library-design-patterns, state-management-patterns, api-integration-patterns

**How It Works**:
- **Progressive Disclosure**: Skills auto-activate based on keywords, full content loads only when needed
- **Agent Integration**: Each agent references relevant skills in their prompts (no agent changes needed for Issue #110)
- **Token Reduction**: ~16,833-17,233 tokens saved across 28 skills (26-35% reduction) plus ~6,000+ lines moved to docs/
- **Refactored Skills** (16 of 28): All now under 500 lines with detailed content in docs/ subdirectories

**Key Benefits**:
- All 20 agents explicitly reference relevant skills (Issue #35)
- All 28 skills now satisfy official 500-line limit (Issue #110)
- Prevents hallucination while maintaining scalability
- Supports 50-100+ skills without context bloat
- Test coverage: 328/355 tests passing

See `docs/SKILLS-AGENTS-INTEGRATION.md` for complete architecture details and agent-skill mapping table. See `docs/SKILLS.md` for refactoring summary.

### Libraries (35 Documented Libraries)

34 reusable Python libraries for security, validation, automation, installation, brownfield retrofit, git hook utilities, and CLI wrappers. See [docs/LIBRARIES.md](docs/LIBRARIES.md) for complete API documentation.

**Core Libraries** (17): security_utils, project_md_updater, version_detector, orphan_file_cleaner, sync_dispatcher, validate_marketplace_version, plugin_updater, update_plugin, hook_activator, validate_documentation_parity, auto_implement_git_integration, batch_state_manager, github_issue_fetcher, path_utils, validation, settings_merger, settings_generator

**Installation Libraries** (8): file_discovery, copy_system, installation_validator, install_orchestrator, staging_manager, protected_file_detector, installation_analyzer, install_audit

**Utility Libraries** (2): math_utils, git_hooks

**Script Utilities** (1): genai_install_wrapper (CLI wrapper for setup-wizard Phase 0 - Issue #109)

**Brownfield Retrofit Libraries** (6): brownfield_retrofit, codebase_analyzer, alignment_assessor, migration_planner, retrofit_executor, retrofit_verifier

**Design Pattern**: Progressive enhancement (string → path → whitelist), two-tier design (core logic + CLI), non-blocking enhancements

### Hooks (44 total automation - unified PreToolUse hook eliminates collision)

44 automation hooks for quality enforcement and workflow automation. See [docs/HOOKS.md](docs/HOOKS.md) for complete reference.

**Core Hooks** (12): auto_format, auto_test, security_scan, validate_project_alignment, validate_claude_alignment, enforce_file_organization, enforce_pipeline_complete, enforce_tdd, detect_feature_request, auto_git_workflow, pre_tool_use, session_tracker

**Optional Hooks** (30): auto_enforce_coverage, auto_fix_docs, auto_add_to_regression, auto_track_issues, auto_generate_tests, auto_sync_dev, auto_tdd_enforcer, auto_update_docs, auto_update_project_progress, detect_doc_changes, enforce_bloat_prevention, enforce_command_limit, post_file_move, validate_documentation_alignment, validate_session_quality, plus 15 additional hooks for extended enforcement and validation

**Lifecycle Hooks** (2): UserPromptSubmit (display context), SubagentStop (log completion, auto-update progress)


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
- Agent counts match reality (currently 20 agents, orchestrator removed v3.2.2)
- Command counts match installed commands (currently 20 active commands)
- Documented features actually exist
- Security requirements documented
- Best practices are up-to-date

**If drift detected**:
1. Run validation to see specific issues
2. Update CLAUDE.md with actual current state
3. Commit the alignment fix
4. Hooks ensure all features stay in sync

## Troubleshooting

### "ModuleNotFoundError: No module named 'autonomous_dev'"

**Symptom**: When running tests or importing from the plugin:
```python
ModuleNotFoundError: No module named 'autonomous_dev'
```

**Solution**: Create a development symlink for Python imports.

See [TROUBLESHOOTING.md](plugins/autonomous-dev/docs/TROUBLESHOOTING.md) for complete instructions:
- macOS/Linux: `cd plugins && ln -s autonomous-dev autonomous_dev`
- Windows: `cd plugins && mklink /D autonomous_dev autonomous-dev` (Command Prompt as Admin)
- Then test: `python -c "from autonomous_dev.lib import security_utils; print('OK')"`

This is a one-time setup issue specific to Python import requirements.

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

For enhanced Claude Desktop integration, configure the MCP server with optional security policy.

**Location**: `.mcp/config.json`

**Provides**:
- Filesystem access (read/write repository files)
- Shell commands (git, python, npm, etc.)
- Git operations (status, diff, commit)
- Python interpreter (with virtualenv)

### MCP Security (v3.37.0+, Issue #95)

Permission-based security system for MCP server operations (prevents path traversal, command injection, SSRF).

**Security Features**:
- Whitelist-based permission system (allowlist + denylist)
- Glob pattern matching for flexible permissions
- Prevents CWE-22 (path traversal), CWE-59 (symlinks), CWE-78 (injection), SSRF
- Blocks sensitive files (.env, .git, .ssh, secrets)
- Audit logging for all operations

**Configuration**:
- Policy file: `.mcp/security_policy.json`
- Profiles: development (permissive), testing (moderate), production (strict)
- Fallback: Development profile if policy file not found

**Validation Hooks**:
- `pre_tool_use.py` - PreToolUse hook standalone script that intercepts and validates all MCP operations (replaced `unified_pre_tool_use.py`, `auto_approve_tool.py`, `mcp_security_enforcer.py`)

**Documentation**: See [MCP-SECURITY.md](docs/MCP-SECURITY.md) for comprehensive guide

**Setup**:
```bash
# See .mcp/README.md for full MCP setup instructions
```

---

## Quick Reference

## Updating
```bash
# Use the built-in update command
/update-plugin

# Or manually:
# 1. Use /update-plugin for interactive update with backup/rollback
# 2. Exit and restart Claude Code (REQUIRED!)
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

**Last Updated**: 2025-11-18 (Added automatic failure recovery for /batch-implement - GitHub Issue #89, intelligent retry with transient classification and circuit breaker)
