# autonomous-dev

Plugin for autonomous development in Claude Code. AI agents, skills, automation hooks, slash commands.

## Project Overview

Autonomous development plugin that provides:
- **8-step SDLC pipeline**: alignment → research → plan → test → implement → validate → verify → git
- **Batch processing**: Process multiple features/issues with worktree isolation
- **Git automation**: AUTO_GIT_ENABLED for commit/push workflows

## Installation

```bash
# Primary install method (sets up global hooks, libs, config)
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

Then restart Claude Code (Cmd+Q / Ctrl+Q). For subsequent updates, run `/sync` then `/reload-plugins`.

## Critical Rules

**Use the right command for every action:**

| Action | Command | Why |
|--------|---------|-----|
| Code changes | `/implement "desc"` | Tests, security review, docs |
| Any code change | `/implement "desc"` | Full pipeline always |
| GitHub issues | `/create-issue "desc"` | Research, dedup, alignment |
| Quality check | `/audit` | Coverage, security, docs |
| Alignment | `/align` | PROJECT.md validation |
| Doc updates | `/align --docs` | Sync docs with code |

**Direct editing is only for**: user-facing docs (README.md, CHANGELOG.md, docs/*.md), config (.json/.yaml), typos (1-2 lines).

**NEVER direct-edit without `/implement`**: `agents/*.md`, `commands/*.md`, `hooks/*.py`, `lib/*.py`, `skills/*/SKILL.md` — these are functional infrastructure, not documentation. Always use `/implement` even though they're `.md` files.

**After plan mode approval → use `/implement`**: When you exit plan mode with an approved implementation plan, do NOT start coding directly. Run `/implement "description"` with the plan. The plan IS the input to `/implement`, not a license to bypass it.

**Why commands exist**: Each runs specialized agents that catch problems raw actions miss — alignment, testing, security, documentation. Skipping them means skipping quality.

**Run `/improve` after `/implement` sessions.** Detects bypasses, test drift, doc staleness. Use `--auto-file` to create GitHub issues for findings.

**Use `/clear` after each feature.** Prevents context bloat.

**Use `/sync` to update.** Then run `/reload-plugins` to pick up changes to commands, agents, and skills. If hooks or settings changed, do a full restart (Cmd+Q / Ctrl+Q) instead.

## Code Navigation

**Prefer LSP over Grep for code navigation.** When LSP is available:
- `goToDefinition` - Find where functions/classes are defined
- `findReferences` - Find all usages of a symbol
- `incomingCalls` / `outgoingCalls` - Understand call hierarchies
- `documentSymbol` - Get file structure overview

Use Grep/Glob for: text patterns, file names, comments/strings.

## Commands

| Command | Purpose |
|---------|---------|
| `/implement` | Code changes (full pipeline, --batch, --issues, --resume) |
| `/create-issue` | GitHub issue with automated research (--quick) |
| `/align` | Alignment check (--project, --docs, --retrofit) |
| `/audit` | Quality audit (--quick, --security, --docs, --code, --claude, --tests) |
| `/setup` | Interactive setup wizard |
| `/sync` | Update plugin (--github, --env, --marketplace, --all, --uninstall) |
| `/health-check` | Validate plugin integrity |
| `/advise` | Critical thinking analysis |
| `/worktree` | Git worktrees (--list, --status, --merge, --discard) |
| `/scaffold-genai-uat` | Scaffold LLM-as-judge tests into any repo |
| `/status` | View PROJECT.md goal progress |
| `/improve` | Session analysis and improvement detection |
| `/mem-search` | Search claude-mem persistent memory (optional) |

## Session Continuity

The `SessionStart-batch-recovery.sh` hook automatically restores batch state after `/clear` or auto-compact. Session activity is logged to `.claude/logs/activity/` by the `session_activity_logger.py` hook.

## Project Alignment

- **Goals/Scope**: See [.claude/PROJECT.md](.claude/PROJECT.md)
- **Operations**: See [.claude/local/OPERATIONS.md](.claude/local/OPERATIONS.md) (repo-specific procedures)

### Agents

14 specialist agents for autonomous development. See [docs/AGENTS.md](docs/AGENTS.md) for details.

Key agents: researcher, planner, test-master, implementer, reviewer, security-auditor, doc-master, continuous-improvement-analyst. See agents/archived/ for 15 archived agents.

## Detailed Guides

| Topic | Location |
|-------|----------|
| Workflow discipline | [docs/WORKFLOW-DISCIPLINE.md](docs/WORKFLOW-DISCIPLINE.md) |
| Context management | [docs/CONTEXT-MANAGEMENT.md](docs/CONTEXT-MANAGEMENT.md) |
| Architecture | [docs/ARCHITECTURE-OVERVIEW.md](docs/ARCHITECTURE-OVERVIEW.md) |
| Batch processing | [docs/BATCH-PROCESSING.md](docs/BATCH-PROCESSING.md) |
| Git automation | [docs/GIT-AUTOMATION.md](docs/GIT-AUTOMATION.md) |
| Sandboxing | [docs/SANDBOXING.md](docs/SANDBOXING.md) |
| Libraries | [docs/LIBRARIES.md](docs/LIBRARIES.md) |
| Performance | [docs/PERFORMANCE.md](docs/PERFORMANCE.md) |
| Testing strategy | [docs/TESTING-STRATEGY.md](docs/TESTING-STRATEGY.md) |
| claude-mem integration | [docs/CLAUDE-MEM-INTEGRATION.md](docs/CLAUDE-MEM-INTEGRATION.md) |
| Troubleshooting | [plugins/autonomous-dev/docs/TROUBLESHOOTING.md](plugins/autonomous-dev/docs/TROUBLESHOOTING.md) |

## Component Counts

14 agents (15 archived), 16 skills, 15 active commands, 168 libraries, 21 active hooks (62 archived). See [docs/ARCHITECTURE-OVERVIEW.md](docs/ARCHITECTURE-OVERVIEW.md).

**Last Updated**: 2026-03-07
