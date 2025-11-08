# Claude Code Bootstrap - Project Instructions

**Last Updated**: 2025-11-08
**Project**: Autonomous Development Plugin for Claude Code 2.0
**Version**: v3.7.1 (Marketplace Update UX + Version Detection)

> **📘 Maintenance Guide**: See `docs/MAINTAINING-PHILOSOPHY.md` for how to keep the core philosophy active as you iterate

---

## Project Overview

**autonomous-dev** - Plugin repository for autonomous development in Claude Code.

**Core Plugin**: `autonomous-dev` - 18 AI agents, 19 skills, automation hooks, and slash commands for autonomous feature development

**Install**:
```bash
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
# Exit and restart Claude Code (Cmd+Q or Ctrl+Q)
# Done! All commands work: /auto-implement, /align-project, /align-claude, /setup, /sync, /status, /health-check, /pipeline-status, /uninstall
```

**Commands (17 active, unified /sync command per GitHub #44)**:

**Core Workflow (8)**:
- `/auto-implement` - Autonomous feature development (Claude coordinates 7 agents)
- `/align-project` - Fix PROJECT.md conflicts (alignment-analyzer agent)
- `/align-claude` - Fix documentation drift (validation script)
- `/setup` - Interactive setup wizard (project-bootstrapper agent)
- `/sync` - Unified sync command (smart auto-detection: dev environment, marketplace, or plugin dev) - GitHub #47
- `/status` - Track project progress (project-progress-tracker agent)
- `/health-check` - Validate plugin integrity (Python validation)
- `/pipeline-status` - Track /auto-implement workflow (Python script)

**Individual Agents (7)** - GitHub #44:
- `/research <feature>` - Research patterns and best practices (2-5 min)
- `/plan <feature>` - Architecture and implementation planning (3-5 min)
- `/test-feature <feature>` - TDD test generation (2-5 min)
- `/implement <feature>` - Code implementation to make tests pass (5-10 min)
- `/review` - Code quality review and feedback (2-3 min)
- `/security-scan` - Security vulnerability scan and OWASP compliance (1-2 min)
- `/update-docs` - Documentation synchronization (1-2 min)

**Utility Commands (2)**:
- `/test` - Run automated tests (pytest wrapper)
- `/uninstall` - Remove or disable plugin features

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
7. **Git Operations**: Auto-commit and push to feature branch (consent-based)
8. **Context Clear (Optional)**: `/clear` for next feature (recommended for performance)

**Performance Baseline (Issue #46 - Multi-Phase Optimization - Phases 4, 5, 6 Complete)**:
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
- **Cumulative Improvement**: 5-9 minutes saved per workflow (15-32% faster, 24% overall improvement)

---

## Architecture

### Agents (18 specialists with active skill integration - GitHub Issue #35)

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

**Utility Agents (9)** with skill references:
- **alignment-validator**: PROJECT.md alignment checking - Uses semantic-validation, file-organization skills
- **commit-message-generator**: Conventional commit generation - Uses git-workflow, code-review skills
- **pr-description-generator**: Pull request descriptions - Uses github-workflow, documentation-guide, code-review skills
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

### Libraries (4 Shared Libraries - v3.4.0+)

**Location**: `plugins/autonomous-dev/lib/`

**Core Libraries**:

1. **security_utils.py** (628 lines, v3.4.3+) - Centralized security validation and audit logging
   - Functions: `validate_path()`, `validate_pytest_path()`, `validate_input_length()`, `validate_agent_name()`, `validate_github_issue()`, `audit_log()`
   - Security coverage: CWE-22 (path traversal), CWE-59 (symlink resolution), CWE-117 (log output neutralization)
   - Path validation: 4-layer whitelist defense (string checks → symlink detection → path resolution → whitelist validation)
   - Test mode support: Auto-detects pytest, allows system temp while blocking system directories
   - Audit logging: Thread-safe JSON logging to `logs/security_audit.log` (10MB rotation, 5 backups)
   - Used by: agent_tracker.py, project_md_updater.py, version_detector.py, orphan_file_cleaner.py, and all security-critical operations
   - Test coverage: 638 unit tests (98.3% coverage)
   - Documentation: See `docs/SECURITY.md` for comprehensive guide

2. **project_md_updater.py** (247 lines, v3.4.0+) - Atomic PROJECT.md updates with security validation
   - Functions: `update_goal_progress()`, `_atomic_write()`, `_validate_update()`, `_backup_before_update()`, `_detect_merge_conflicts()`
   - Security: Uses security_utils.validate_path() for whitelist validation, mkstemp() for atomic writes
   - Atomic writes: Temp file creation (mkstemp) → content writing → atomic rename
   - Merge conflict detection: Prevents data loss if PROJECT.md changed during update
   - Test coverage: 24 unit tests (95.8% coverage)
   - Used by: auto_update_project_progress.py hook (SubagentStop)

3. **version_detector.py** (531 lines, v3.7.1+) - Semantic version detection and comparison
   - Classes: `Version` (semantic version object with comparison operators), `VersionComparison` (result dataclass)
   - Functions: `VersionDetector` class (low-level API), `detect_version_mismatch()` (convenience function)
   - Features: Parse semantic versions, compare marketplace vs project versions, detect upgrades/downgrades, handle pre-release versions
   - Security: Path validation via security_utils, audit logging (CWE-22, CWE-59 protection)
   - Error handling: Clear error messages with context and expected format
   - Pre-release support: Correctly handles `MAJOR.MINOR.PATCH` and `MAJOR.MINOR.PATCH-PRERELEASE` patterns
   - Test coverage: 20 unit tests (version parsing, comparison, edge cases)
   - Used by: sync_dispatcher.py for marketplace version detection
   - Related: GitHub Issue #50

4. **orphan_file_cleaner.py** (514 lines, v3.7.1+) - Orphaned file detection and cleanup
   - Classes: `OrphanFile` (orphan representation), `CleanupResult` (result with summary), `OrphanFileCleaner` (low-level API)
   - Functions: `detect_orphans()` (detection only), `cleanup_orphans()` (cleanup with mode control)
   - Features: Detect orphans in commands/hooks/agents, dry-run mode (safe), confirm mode (user approval), auto mode (non-interactive)
   - Security: Path validation via security_utils, audit logging to `logs/orphan_cleanup_audit.log` (JSON format)
   - Error handling: Graceful per-file failures (one orphan failure doesn't block others)
   - Modes: `dry_run=True` (report only), `confirm=True` (ask per file), auto-delete (no prompts)
   - Test coverage: 22 unit tests (detection, cleanup, permissions, dry-run)
   - Used by: sync_dispatcher.py for marketplace sync cleanup
   - Related: GitHub Issue #50

**Design Pattern**: Progressive enhancement (string → path → whitelist) allows graceful error recovery.

### Hooks (29 total automation)

Located: `plugins/autonomous-dev/hooks/`

**Core Hooks (9)**:
- `auto_format.py`: black + isort (Python), prettier (JS/TS)
- `auto_test.py`: pytest on related tests
- `security_scan.py`: Secrets detection, vulnerability scanning
- `validate_project_alignment.py`: PROJECT.md validation
- `validate_claude_alignment.py`: CLAUDE.md alignment checking (v3.0.2+)
- `enforce_file_organization.py`: Standard structure enforcement
- `enforce_pipeline_complete.py`: Validates all 7 agents ran (v3.2.2+)
- `enforce_tdd.py`: Validates tests written before code (v3.0+)
- `detect_feature_request.py`: Auto-detect feature requests

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
- `SubagentStop`: Log agent completion to session; auto-update PROJECT.md progress (v3.4.0+)

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

**Last Updated**: 2025-11-08
