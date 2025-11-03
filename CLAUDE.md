# Claude Code Bootstrap - Project Instructions

**Last Updated**: 2025-11-03
**Project**: Autonomous Development Plugin for Claude Code 2.0
**Version**: v3.1.0 (Agent-Skill Integration Architecture)

> **📘 Maintenance Guide**: See `docs/MAINTAINING-PHILOSOPHY.md` for how to keep the core philosophy active as you iterate

---

## Project Overview

**autonomous-dev** - Plugin repository for autonomous development in Claude Code.

**Core Plugin**: `autonomous-dev` - 19 AI agents, automation hooks, and slash commands for autonomous feature development

**Install**:
```bash
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
# Exit and restart Claude Code (Cmd+Q or Ctrl+Q)
# Done! All commands work: /auto-implement, /align-project, /align-claude, /setup, /test, /status, /health-check, /uninstall
```

**Note**: Commands `/test`, `/format`, `/commit` were archived in v3.1.0. Use `/auto-implement` for full feature development.

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
- ✅ After each feature completes (mandatory)
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
6. **Review**: reviewer checks quality
7. **Security**: security-auditor scans
8. **Documentation**: doc-master updates docs
9. **Context Clear**: `/clear` for next feature

---

## Architecture

### Agents (19 specialists)

Located: `plugins/autonomous-dev/agents/`

**Core Workflow Agents (10)**:
- **orchestrator**: PROJECT.md gatekeeper, validates alignment before proceeding
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

### Skills (0 - Removed Per Anti-Pattern Guidance)

**Status**: Skills directory removed per Anthropic anti-pattern guidance (v2.5+)

**Why Removed**:
- Skills caused context bloat in Claude Code plugins
- Anthropic recommended consolidating specialist knowledge into agent system prompts
- Progressive disclosure (loading skills on-demand) was considered but ultimately removed for simplicity

**Previous 19 Skills** (now consolidated into agents):
- **Core Development**: api-design, architecture-patterns, code-review, database-design, testing-guide, security-patterns
- **Workflow & Automation**: git-workflow, github-workflow, project-management, documentation-guide
- **Code & Quality**: python-standards, observability, consistency-enforcement, file-organization
- **Validation & Analysis**: research-patterns, semantic-validation, cross-reference-validation, documentation-currency, advisor-triggers

**How It Works Now**: Specialist knowledge embedded directly in agent system prompts (no separate skills/ directory).

### Hooks (28 total automation)

Located: `plugins/autonomous-dev/hooks/`

**Core Hooks (9)**:
- `auto_format.py`: black + isort (Python), prettier (JS/TS)
- `auto_test.py`: pytest on related tests
- `security_scan.py`: Secrets detection, vulnerability scanning
- `validate_project_alignment.py`: PROJECT.md validation
- `validate_claude_alignment.py`: CLAUDE.md alignment checking (v3.0.2+)
- `enforce_file_organization.py`: Standard structure enforcement
- `enforce_orchestrator.py`: Validates orchestrator ran (v3.0+)
- `enforce_tdd.py`: Validates tests written before code (v3.0+)
- `detect_feature_request.py`: Auto-detect feature requests

**Optional/Extended Hooks (19)**:
- `auto_enforce_coverage.py`: 80% minimum coverage
- `auto_fix_docs.py`: Documentation consistency
- `auto_add_to_regression.py`: Regression test tracking
- `auto_track_issues.py`: GitHub issue tracking
- `auto_generate_tests.py`: Auto-generate test boilerplate
- `auto_sync_dev.py`: Sync development changes
- `auto_tdd_enforcer.py`: Strict TDD enforcement
- `auto_update_docs.py`: Auto-update documentation
- `detect_doc_changes.py`: Detect documentation changes
- `enforce_bloat_prevention.py`: Prevent context bloat
- `enforce_command_limit.py`: Command count limits
- `post_file_move.py`: Post-move validation
- `validate_documentation_alignment.py`: Doc alignment checking
- `validate_session_quality.py`: Session quality validation
- Plus 5 others for extended enforcement and validation

**Lifecycle Hooks**:
- `UserPromptSubmit`: Display project context
- `SubagentStop`: Log agent completion to session

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
- Agent counts match reality (currently 19, not 7 or 16)
- Command counts match installed commands (currently 8)
- Documented features actually exist
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

# After feature completes
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

- Clear context after features (`/clear`)
- Use session files for communication
- Stay under 8K tokens per feature
- Scale to 100+ features

---

**For detailed guides**:
- **Users**: See `plugins/autonomous-dev/README.md` for installation and usage
- **Contributors**: See `docs/DEVELOPMENT.md` for dogfooding setup and development workflow

**For code standards**: See CLAUDE.md best practices and agent prompts for guidance (skills directory removed per Anthropic anti-pattern guidance v2.5+)

**Last Updated**: 2025-10-27
