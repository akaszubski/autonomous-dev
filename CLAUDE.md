# autonomous-dev

Plugin for autonomous development in Claude Code. AI agents, skills, automation hooks, slash commands.

## Project Overview

Autonomous development plugin that provides:
- **8-agent SDLC pipeline**: researcher → planner → test-master → implementer → reviewer → security-auditor → doc-master
- **Batch processing**: Process multiple features/issues with worktree isolation
- **Git automation**: AUTO_GIT_ENABLED for commit/push workflows

## Installation

```bash
/plugin install akaszubski/autonomous-dev
```

Then restart Claude Code (Cmd+Q / Ctrl+Q).

## Critical Rules

**Use `/implement` for all code changes.** Exceptions: docs (.md), config (.json/.yaml), typos (1-2 lines).

**Use `/clear` after each feature.** Prevents context bloat (50K+ tokens → system fails).

**Use `/sync` to update.** Then restart Claude Code (Cmd+Q / Ctrl+Q).

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
| `/implement` | Code changes (full pipeline, --quick, --batch, --issues, --resume) |
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

At session start, read `.claude/local/SESSION_STATE.json` for:
- **Active tasks**: Current work and next steps
- **Key conventions**: Repo-specific patterns and rules
- **Recent context**: Files modified, workflows completed

Update state after completing significant work. State survives `/clear` operations.

## Project Alignment

- **Goals/Scope**: See [.claude/PROJECT.md](.claude/PROJECT.md)
- **Operations**: See [.claude/local/OPERATIONS.md](.claude/local/OPERATIONS.md) (repo-specific procedures)
- **Session State**: See [.claude/local/SESSION_STATE.json](.claude/local/SESSION_STATE.json) (machine-readable context)

### Agents

17 specialist agents for autonomous development. See [docs/AGENTS.md](docs/AGENTS.md) for details.

Key agents: researcher, planner, test-master, implementer, reviewer, security-auditor, doc-master, data-curator, continuous-improvement-analyst. See agents/archived/ for 13 archived agents.

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
| claude-mem integration | [docs/CLAUDE-MEM-INTEGRATION.md](docs/CLAUDE-MEM-INTEGRATION.md) |
| Troubleshooting | [plugins/autonomous-dev/docs/TROUBLESHOOTING.md](plugins/autonomous-dev/docs/TROUBLESHOOTING.md) |

## Component Counts

17 agents, 40 skills, 15 active commands (12 archived), 160 libraries, 17 active hooks (62 archived). See [docs/ARCHITECTURE-OVERVIEW.md](docs/ARCHITECTURE-OVERVIEW.md).

**Last Updated**: 2026-02-16
