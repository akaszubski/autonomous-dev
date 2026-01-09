# Claude Code Bootstrap - Project Instructions

**Last Updated**: 2026-01-09 (Issue #206 - Simplify version tracking - single source of truth)
**Last Validated**: 2026-01-09
**Project**: Autonomous Development Plugin for Claude Code 2.0
**Version**: See `plugins/autonomous-dev/VERSION` for current version

> **Maintenance Guide**: See `docs/MAINTAINING-PHILOSOPHY.md` for how to keep the core philosophy active as you iterate

___

## Component Versions

| Component | Count | Status |
|-----------|-------|--------|
| Skills | 28 | ✅ Compliant |
| Commands | 9 | ✅ Compliant |
| Agents | 22 | ✅ Compliant |
| Hooks | 64 | ✅ Compliant |
| Settings | 5 templates | ✅ Compliant |

**Last Compliance Check**: 2026-01-09 (Issue #203 - Consolidate /implement commands)

___

## Installation (Bootstrap-First)

```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
# Restart Claude Code (Cmd+Q / Ctrl+Q)
```

**What install.sh does**: Downloads components, installs global infrastructure (`~/.claude/hooks/`, `~/.claude/lib/`, `~/.claude/settings.json`), installs to `.claude/`

**Optional**: Run `/setup` for guided PROJECT.md creation. See [docs/BOOTSTRAP_PARADOX_SOLUTION.md](docs/BOOTSTRAP_PARADOX_SOLUTION.md).

___

## Project Overview

**autonomous-dev** - Plugin for autonomous development in Claude Code. AI agents, skills, automation hooks, slash commands.

## Commands

- /implement: Smart code implementation with three modes (full pipeline, quick, batch). See `/implement` command.
  - Full pipeline (default): `research → plan → test → implement → review → security → docs`
  - Quick mode: `--quick` flag for implementer agent only
  - Batch mode: `--batch`, `--issues`, `--resume` for multiple features
- /advise: Critical thinking analysis (validates alignment, challenges assumptions, identifies risks). See `/advise` command.
- /audit-tests: Analyze test coverage and identify gaps. See `/audit-tests` command.
- /create-issue: Create GitHub issue with research and blocking duplicate check. See `/create-issue` command.
- /align: Alignment command with three modes (project, claude, retrofit). See `/align` command.
- /setup: Interactive setup wizard for PROJECT.md creation. See `/setup` command.
- /sync: Sync command with six modes (github, env, marketplace, plugin-dev, all, uninstall). See `/sync` command.
- /health-check: Validate plugin integrity and marketplace version. See `/health-check` command.
- /worktree: Manage git worktrees for isolated feature development. See `/worktree` command.

**Security**: All commands use `allowed-tools:` frontmatter for least privilege.

___

## Workflow Discipline

**Philosophy**: Prefer pipelines. Choose quality over speed.

**Key Metrics**: /implement (full pipeline) catches 85% of issues before commit (4% bug rate vs 23%, 0.3% security issues vs 12%, 94% test coverage vs 43%)

**When to Use**:
- **Direct Implementation**: Documentation updates, config changes, typo fixes
- **/implement**: New code, bug fixes, features, API changes (choose mode: full pipeline for tests, quick for docs, batch for bulk)

**See**: [docs/WORKFLOW-DISCIPLINE.md](docs/WORKFLOW-DISCIPLINE.md) for complete data, enforcement philosophy, and 4-layer consistency architecture.

___

## Context Management (CRITICAL!)

**Why This Matters**:
- Without clearing: Context bloats to 50K+ tokens after 3-4 features → System fails
- With clearing: Context stays under 8K tokens → Works for 100+ features

**After Each Feature**:
```bash
/clear
```

**When to clear**: After each feature completes (recommended for optimal performance), before starting unrelated feature, if responses feel slow

**Session Files**: Agents log to `docs/sessions/` instead of context (200 tokens vs 5,000+ tokens)

**See**: [docs/CONTEXT-MANAGEMENT.md](docs/CONTEXT-MANAGEMENT.md) for complete context management strategy, session files, and portable library design.

___

## Documentation Principles

**Principle**: Documentation must reflect reality, not aspirations.

**Standards**: State real-world limits, include failure modes, use hedging language, avoid marketing speak.

**Test**: "If a new user follows the docs exactly, will their experience match what's written?"

**Philosophy**: Under-promise, over-deliver.

___

## PROJECT.MD - Goal Alignment

[`.claude/PROJECT.md`](.claude/PROJECT.md) defines GOALS, SCOPE, CONSTRAINTS, ARCHITECTURE

**Check alignment**: `cat .claude/PROJECT.md | grep -A 5 "## GOALS"`

**Update**: Edit PROJECT.md when strategic direction changes

**Strategic vs tactical**: PROJECT.md (strategy) vs GitHub Issues (tasks). Forbidden in PROJECT.md: TODO, Roadmap, Future

___

## Autonomous Development Workflow

Three modes via `/implement` command:

**Full Pipeline Mode** (15-25 minutes per feature):
1. Alignment Check
2. Complexity Assessment
3. Research (Haiku model)
4. Planning
5. Pause Control (optional)
6. TDD Tests (failing tests FIRST)
7. Implementation
8. Parallel Validation (reviewer + security-auditor + doc-master)
9. Memory Recording (optional)
10. Automated Git Operations (consent-based)
11. Context Clear (optional)

**Quick Mode** (2-5 minutes): Direct implementer agent invocation, no pipeline overhead

**Batch Mode** (20-30 min per feature): Process multiple features sequentially with state management, crash recovery, per-feature git automation

**Performance**: 25-30% improvement from 28-44 min baseline. See [docs/PERFORMANCE.md](docs/PERFORMANCE.md) for benchmarks.

See [docs/BATCH-PROCESSING.md](docs/BATCH-PROCESSING.md) for batch mode documentation (file-based input, GitHub Issues, resume capability, automatic retry).

___

## Git Automation Control

Automatic git operations enabled by default after `/implement` (full pipeline) completes. See [docs/GIT-AUTOMATION.md](docs/GIT-AUTOMATION.md) for complete documentation.

**Control**:
- First-run consent (interactive prompt)
- Environment variables: `AUTO_GIT_ENABLED`, `AUTO_GIT_PUSH`, `AUTO_GIT_PR`
- State persistence: `~/.autonomous-dev/user_state.json`

**Workflow**: doc-master completes → auto_git_workflow.py hook → commit-message-generator → stage/commit/push/PR

___

## MCP Auto-Approval Control

Automatic tool approval for trusted operations. Reduces permission prompts from 50+ to 8-10 (84% reduction). See [docs/SANDBOXING.md](docs/SANDBOXING.md) for complete documentation.

**Enable**:
```bash
# In .env file
MCP_AUTO_APPROVE=true  # Auto-approves everywhere (main + subagents)
SANDBOX_ENABLED=true   # Command classification and sandboxing
SANDBOX_PROFILE=development  # Options: development, testing, production
```

**4-Layer Permission Architecture**:
1. **Sandbox Enforcer**: Command classification (SAFE/BLOCKED/NEEDS_APPROVAL)
2. **MCP Security Validator**: Path traversal, injection, SSRF prevention
3. **Agent Authorization**: Pipeline agent detection
4. **Batch Permission Approver**: Caches user consent for identical operations

**See**: [docs/SANDBOXING.md](docs/SANDBOXING.md), [docs/MCP-SECURITY.md](docs/MCP-SECURITY.md), [docs/LIBRARIES.md](docs/LIBRARIES.md) Section 66

___

## Architecture

### Agents

**22 Agents** (8 pipeline, 14 utility):
- Pipeline: researcher-local, planner, test-master, implementer, reviewer, security-auditor, doc-master, issue-creator
- Native skill integration via `skills:` frontmatter

**28 Skills**: Progressive disclosure pattern, `allowed-tools:` for least privilege

**69 Libraries**: Security, validation, automation, infrastructure (Issue #204: doc-master auto-apply integration)

**64 Hooks**: Dispatcher pattern, graceful degradation, env var control

**Model Tiers**: Haiku (pattern matching), Sonnet (implementation), Opus (security)

**See**: [docs/ARCHITECTURE-OVERVIEW.md](docs/ARCHITECTURE-OVERVIEW.md) for complete architecture, [docs/AGENTS.md](docs/AGENTS.md), [docs/SKILLS-AGENTS-INTEGRATION.md](docs/SKILLS-AGENTS-INTEGRATION.md), [docs/LIBRARIES.md](docs/LIBRARIES.md), [docs/HOOKS.md](docs/HOOKS.md)

___

## CLAUDE.md Alignment

System to detect drift between documented standards and actual codebase.

**Check**: `git commit` (automatic via hook) or `python .claude/hooks/validate_claude_alignment.py` (manual)

**Validates**: Version consistency, feature existence, security requirements, best practices

**Fix drift**: Run validation → Update CLAUDE.md → Commit

___

## Troubleshooting

**Common Issues**:
- **ModuleNotFoundError**: Create symlink `cd plugins && ln -s autonomous-dev autonomous_dev`
- **Context budget exceeded**: Run `/clear` and retry
- **Alignment issues**: Check `cat .claude/PROJECT.md | grep GOALS`
- **Commands not updating**: Fully quit (`Cmd+Q`/`Ctrl+Q`), wait 5s, restart (not `/exit`)

**See**: [TROUBLESHOOTING.md](plugins/autonomous-dev/docs/TROUBLESHOOTING.md) for complete guide.

___

## MCP Server (Optional)

Enhanced Claude Desktop integration via `.mcp/config.json`

**Provides**: Filesystem, shell, git, Python interpreter

**Security**: Permission-based with whitelist/blacklist. See [docs/MCP-SECURITY.md](docs/MCP-SECURITY.md) and `.mcp/README.md`

___

## Quick Reference

Common commands and workflows for daily use.

### Updating

`/sync` (auto-detects context), then restart Claude Code

### Daily Workflow

Describe feature to Claude, implement, then `/clear` (optional, recommended for performance)

### Check Session Logs

```bash
cat docs/sessions/$(ls -t docs/sessions/ | head -1)
```

### Update Goals

```bash
vim .claude/PROJECT.md
```

___

## Philosophy

**Automation > Reminders > Hope**: Automate quality (formatting, testing, security, docs). Use agents, skills, hooks. Focus on creative work.

**Research First, Test Coverage Required**: Research before implementing, write tests first (TDD), document changes. Make quality automatic.

**Context is Precious**: Clear after features (`/clear`), use session files, stay under 8K tokens, scale to 100+ features.

___

**For detailed guides**:
- **Users**: See `plugins/autonomous-dev/README.md` for installation and usage
- **Contributors**: See `docs/DEVELOPMENT.md` for dogfooding setup and development workflow

**For code standards**: See CLAUDE.md best practices, agent prompts, and skills for guidance

**For security**: See `docs/SECURITY.md` for security audit and hardening guidance

**Last Updated**: 2026-01-03 (Reduced from 832 to under 300 lines, extracted to docs/WORKFLOW-DISCIPLINE.md, docs/CONTEXT-MANAGEMENT.md, docs/ARCHITECTURE-OVERVIEW.md)
