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

## Commands

| Command | Purpose |
|---------|---------|
| `/implement` | Code changes (full pipeline, --quick, --batch) |
| `/sync` | Update plugin |
| `/create-issue` | GitHub issue with research |
| `/audit-claude` | Validate this file |
| `/health-check` | Validate plugin integrity |

## Project Alignment

- **Goals/Scope**: See [.claude/PROJECT.md](.claude/PROJECT.md)
- **Operations**: See [.claude/local/OPERATIONS.md](.claude/local/OPERATIONS.md) (repo-specific procedures)

### Agents

22 specialist agents for autonomous development. See [docs/AGENTS.md](docs/AGENTS.md) for details.

Key agents: researcher, planner, test-master, implementer, reviewer, security-auditor, doc-master.

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
| Troubleshooting | [plugins/autonomous-dev/docs/TROUBLESHOOTING.md](plugins/autonomous-dev/docs/TROUBLESHOOTING.md) |

## Component Counts

22 agents, 28 skills, 26 commands, 144 libraries, 71 hooks. See [docs/ARCHITECTURE-OVERVIEW.md](docs/ARCHITECTURE-OVERVIEW.md).
