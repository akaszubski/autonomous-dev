# Claude Code Bootstrap - Project Instructions

**Last Updated**: 2025-11-09
**Project**: Autonomous Development Plugin for Claude Code 2.0
**Version**: v3.10.0 (Automatic GitHub Issue Creation with Research - Issue #58)

> **📘 Maintenance Guide**: See `docs/MAINTAINING-PHILOSOPHY.md` for how to keep the core philosophy active as you iterate

---

## Project Overview

**autonomous-dev** - Plugin repository for autonomous development in Claude Code.

**Core Plugin**: `autonomous-dev` - 20 AI agents, 19 skills, automation hooks, and slash commands for autonomous feature development

**Install**:
```bash
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
# Exit and restart Claude Code (Cmd+Q or Ctrl+Q)
# Done! All commands work: /auto-implement, /align-project, /align-claude, /setup, /sync, /status, /health-check, /pipeline-status, /update-plugin, /create-issue, /uninstall
```

**Commands (20 active, includes /align-project-retrofit for brownfield adoption - Issue #59)**:

**Core Workflow (10)**:
- `/auto-implement` - Autonomous feature development (Claude coordinates 7 agents)
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

**Utility Commands (2)**:
- `/test` - Run automated tests (pytest wrapper)
- `/uninstall` - Remove or disable plugin features (advanced)

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
- **Cumulative Improvement**: 5-9 minutes saved per workflow (15-32% faster, 24% overall improvement)

---

## Git Automation Control

Automatic git operations (commit, push, PR creation) can be optionally enabled after `/auto-implement` completes. See [docs/GIT-AUTOMATION.md](docs/GIT-AUTOMATION.md) for complete documentation.

**Status**: Optional feature (disabled by default for safety)

**Environment Variables** (set in `.env` file):

```bash
# Master switch - enables automatic git operations after /auto-implement
AUTO_GIT_ENABLED=true        # Default: false

# Enable automatic push to remote (requires AUTO_GIT_ENABLED=true)
AUTO_GIT_PUSH=true           # Default: false

# Enable automatic PR creation (requires AUTO_GIT_ENABLED=true and gh CLI)
AUTO_GIT_PR=true             # Default: false
```

**How It Works**:

1. `/auto-implement` completes STEP 6 (parallel validation)
2. quality-validator agent completes (last validation agent)
3. SubagentStop hook triggers `auto_git_workflow.py`
4. Hook checks consent via environment variables (non-blocking if disabled)
5. If enabled, invokes commit-message-generator agent to create conventional commit message
6. Stages changes, commits with agent-generated message, optionally pushes and creates PR
7. If any prerequisite fails (git not configured, merge conflicts, etc.), provides manual fallback instructions
8. Feature is successful regardless of git operation outcome (graceful degradation)

**Consent-Based Design**:

- Disabled by default - no behavior change without explicit opt-in
- Validates all prerequisites before attempting operations
- Non-blocking - git automation failures don't affect feature completion
- Always provides manual fallback instructions if automation fails

**Security**:

- Uses `security_utils.validate_path()` for all file path validation (CWE-22, CWE-59)
- Audit logs all operations to `logs/security_audit.log`
- No credential logging - never exposes API keys or passwords
- Subprocess calls prevent command injection attacks
- Safe JSON parsing (no arbitrary code execution)

**Implementation Files**:

- Hook: `/plugins/autonomous-dev/hooks/auto_git_workflow.py` (588 lines) - SubagentStop lifecycle hook
- Library: `/plugins/autonomous-dev/lib/auto_implement_git_integration.py` (1,466 lines) - Core integration logic
  - Functions: `execute_step8_git_operations()` (main entry point), `check_consent_via_env()`, `validate_git_state()`, `create_commit_with_agent_message()`, `push_and_create_pr()`
  - Validation: `validate_agent_output()`, `validate_git_state()`, `validate_branch_name()`, `validate_commit_message()`, `check_git_credentials()`, `check_git_available()`, `check_gh_available()`
  - Agents: Invokes commit-message-generator and pr-description-generator agents with workflow context

**Related GitHub Issues**:
- Issue #58: Automatic git operations integration (feature implementation)

**For detailed usage**: See `plugins/autonomous-dev/README.md` "Enable automatic git operations in /auto-implement workflow" section

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

### Skills (19 Active - Progressive Disclosure + Agent Integration)

**Status**: 19 active skill packages using Claude Code 2.0+ progressive disclosure architecture

**Why Active**:
- Skills are **first-class citizens** in Claude Code 2.0+ (fully supported pattern)
- Progressive disclosure solves context bloat elegantly
- Metadata stays in context, full content loads only when needed
- Can scale to 100+ skills without performance issues
- **NEW (v3.5+)**: All 18 agents explicitly reference relevant skills for enhanced decision-making (Issue #35)

**19 Active Skills** (organized by category):
- **Core Development** (6): api-design, architecture-patterns, code-review, database-design, testing-guide, security-patterns
- **Workflow & Automation** (4): git-workflow, github-workflow, project-management, documentation-guide
- **Code & Quality** (4): python-standards, observability, consistency-enforcement, file-organization
- **Validation & Analysis** (5): research-patterns, semantic-validation, cross-reference-validation, documentation-currency, advisor-triggers

**How It Works**:
1. **Progressive Disclosure**: Skills auto-activate based on task keywords. Claude loads full SKILL.md content only when relevant, keeping context efficient.
2. **Agent Integration** (NEW): Each agent's prompt includes a "Relevant Skills" section listing specialized knowledge available for that agent's domain. This helps agents recognize when to apply specialized skills.
3. **Combined Effect**: Agent + skill integration prevents hallucination while scaling to 100+ skills without context bloat.

**Agent-Skill Mapping** (all 18 agents now have skill references):
- See agent prompts in `plugins/autonomous-dev/agents/` for "Relevant Skills" sections
- See `docs/SKILLS-AGENTS-INTEGRATION.md` for comprehensive mapping table

See `docs/SKILLS-AGENTS-INTEGRATION.md` for complete architecture details and agent-skill mapping table.

### Libraries (18 Shared Libraries)

**Location**: `plugins/autonomous-dev/lib/`

**Purpose**: Reusable Python libraries for security, validation, automation, and brownfield retrofit

**Core Libraries (12)**:
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

**Brownfield Retrofit Libraries (6)** - 5-phase retrofit system for existing projects:
13. **brownfield_retrofit.py** - Phase 0: Project analysis and tech stack detection
14. **codebase_analyzer.py** - Phase 1: Deep codebase analysis (multi-language)
15. **alignment_assessor.py** - Phase 2: Gap assessment and 12-Factor compliance
16. **migration_planner.py** - Phase 3: Migration plan with dependency tracking
17. **retrofit_executor.py** - Phase 4: Step-by-step execution with rollback
18. **retrofit_verifier.py** - Phase 5: Verification and readiness assessment

**Design Pattern**: Progressive enhancement (string → path → whitelist) for graceful error recovery. Non-blocking enhancements don't block core operations. Two-tier design (core logic + CLI interface) enables reuse and testing.

**For detailed API documentation**: See `docs/LIBRARIES.md`

### Hooks (41 total automation)

Located: `plugins/autonomous-dev/hooks/`

**Core Hooks (10)**:
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

**Last Updated**: 2025-11-09 (Documentation Parity Validation Added - GitHub Issue #56)
