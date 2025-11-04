# Claude Code Bootstrap - Project Instructions

**Last Updated**: 2025-11-05
**Project**: Autonomous Development Plugin for Claude Code 2.0
**Version**: v3.4.0 (Auto-Update PROJECT.md Goal Progress - SubagentStop Hook)

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
# Done! All commands work: /auto-implement, /align-project, /align-claude, /setup, /sync-dev, /status, /health-check, /pipeline-status, /uninstall
```

**Commands (18 active, expanded per GitHub #44)**:

**Core Workflow (8)**:
- `/auto-implement` - Autonomous feature development (Claude coordinates 7 agents)
- `/align-project` - Fix PROJECT.md conflicts (alignment-analyzer agent)
- `/align-claude` - Fix documentation drift (validation script)
- `/setup` - Interactive setup wizard (project-bootstrapper agent)
- `/sync-dev` - Sync development environment (sync-validator agent)
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

**Utility Commands (3)**:
- `/test` - Run automated tests (pytest wrapper)
- `/uninstall` - Remove or disable plugin features
- `/update-plugin` - Update plugin from marketplace

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
2. **Research**: researcher agent finds patterns
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

---

## Architecture

### Agents (18 specialists)

Located: `plugins/autonomous-dev/agents/`

**Core Workflow Agents (9)** (orchestrator removed v3.2.2 - Claude coordinates directly):
- **researcher**: Web research for patterns and best practices
- **planner**: Architecture planning and design
- **test-master**: TDD specialist (writes tests first)
- **implementer**: Code implementation (makes tests pass)
- **reviewer**: Quality gate (code review)
- **security-auditor**: Security scanning and vulnerability detection
- **doc-master**: Documentation synchronization
- **advisor**: Critical thinking and validation (v3.0+)
- **quality-validator**: GenAI-powered feature validation (v3.0+)

**Utility Agents (9)**:
- **alignment-validator**: PROJECT.md alignment checking
- **commit-message-generator**: Conventional commit generation
- **pr-description-generator**: Pull request descriptions
- **project-progress-tracker**: Track progress against goals
- **alignment-analyzer**: Detailed alignment analysis
- **project-bootstrapper**: Tech stack detection and setup (v3.0+)
- **setup-wizard**: Intelligent setup - analyzes tech stack, recommends hooks (v3.1+)
- **project-status-analyzer**: Real-time project health - goals, metrics, blockers (v3.1+)
- **sync-validator**: Smart dev sync - detects conflicts, validates compatibility (v3.1+)

**Note on Orchestrator Removal (v3.2.2)**:
The "orchestrator" agent was removed because it created a logical impossibility - it was Claude coordinating Claude. When `/auto-implement` invoked the orchestrator agent, it just loaded orchestrator.md as Claude's system prompt, but it was still the same Claude instance making decisions. This allowed Claude to skip agents by reasoning they weren't needed.

**Solution**: Moved all coordination logic directly into `commands/auto-implement.md`. Now Claude explicitly coordinates the 7-agent workflow without pretending to be a separate orchestrator. Same checkpoints, simpler architecture, more reliable execution. See `agents/archived/orchestrator.md` for history.

### Skills (19 Active - Progressive Disclosure)

**Status**: 19 active skill packages using Claude Code 2.0+ progressive disclosure architecture

**Why Active**:
- Skills are **first-class citizens** in Claude Code 2.0+ (not anti-pattern)
- Progressive disclosure solves context bloat elegantly
- Metadata stays in context, full content loads only when needed
- Can scale to 100+ skills without performance issues

**19 Active Skills** (organized by category):
- **Core Development** (6): api-design, architecture-patterns, code-review, database-design, testing-guide, security-patterns
- **Workflow & Automation** (4): git-workflow, github-workflow, project-management, documentation-guide
- **Code & Quality** (4): python-standards, observability, consistency-enforcement, file-organization
- **Validation & Analysis** (5): research-patterns, semantic-validation, cross-reference-validation, documentation-currency, advisor-triggers

**How It Works**: Skills auto-activate based on task keywords. Claude loads full SKILL.md content only when relevant, keeping context efficient.

See `docs/SKILLS-AGENTS-INTEGRATION.md` for complete architecture details.

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
- Command counts match installed commands (currently 18 active commands per GitHub #44)
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

**For code standards**: See CLAUDE.md best practices and agent prompts for guidance (skills directory removed per Anthropic anti-pattern guidance v2.5+)

**For security**: See `docs/sessions/SECURITY_AUDIT_SYNC_DEV.md` for `/sync-dev` command security audit findings and remediation guidance

**Last Updated**: 2025-11-05
