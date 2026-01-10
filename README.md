# autonomous-dev

**AI-Powered Development Pipelines for Claude Code**

Stop writing buggy code. Start shipping production-ready features.

[![Version](https://img.shields.io/badge/version-3.44.0-blue.svg)](plugins/autonomous-dev/VERSION)
[![Agents](https://img.shields.io/badge/agents-22-green.svg)](docs/AGENTS.md)
[![Skills](https://img.shields.io/badge/skills-28-orange.svg)](docs/SKILLS-AGENTS-INTEGRATION.md)

---

## The Problem

When AI writes code directly, you get:
- **23% bug rate** requiring hotfixes
- **12% security vulnerabilities** found in audits
- **67% documentation drift** from actual code
- **43% test coverage** at best

## The Solution

autonomous-dev transforms Claude Code into an orchestrated development system:

| Metric | Without Pipeline | With `/implement` |
|--------|-----------------|-------------------|
| Bug rate | 23% | **4%** |
| Security issues | 12% | **0.3%** |
| Documentation drift | 67% | **2%** |
| Test coverage | 43% | **94%** |

**85% of issues caught before commit.**

---

## Quick Start

```bash
# Install (30 seconds)
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)

# Restart Claude Code (Cmd+Q / Ctrl+Q), then:
/setup  # Optional: guided PROJECT.md creation
```

---

## How It Works

### PROJECT.md-First Development

Every feature starts with alignment validation against your project's strategic goals:

```markdown
# .claude/PROJECT.md
## GOALS
- Build a secure authentication system
- Maintain sub-100ms API response times

## SCOPE
- User management, session handling
- NOT: Payment processing, analytics

## CONSTRAINTS
- No external auth providers
- Must support offline mode
```

When you run `/implement`, the pipeline checks: *Does this feature align with GOALS? Is it within SCOPE? Does it violate CONSTRAINTS?*

**Result**: No scope creep. No wasted effort on misaligned features.

### One Command, Full Pipeline

```bash
/implement Add user authentication with JWT tokens
```

autonomous-dev orchestrates **8 specialized AI agents**:

1. **Alignment Check** - Validates against project goals
2. **Research** - Finds existing patterns in your codebase
3. **Planning** - Designs the architecture
4. **TDD Tests** - Writes failing tests FIRST
5. **Implementation** - Makes tests pass
6. **Code Review** - Checks quality and patterns
7. **Security Audit** - Scans for OWASP vulnerabilities
8. **Documentation** - Keeps docs in sync

**Result**: Production-ready code in 15-25 minutes.

---

## Key Commands

| Command | Purpose |
|---------|---------|
| `/setup` | Interactive PROJECT.md creation wizard |
| `/implement` | Full pipeline: research, plan, test, implement, review, secure, document |
| `/implement --quick` | Fast mode: implementer agent only (2-5 min) |
| `/implement --batch` | Process multiple features with crash recovery |
| `/align` | Validate alignment (project goals, CLAUDE.md, retrofit brownfield) |
| `/create-issue` | Research-backed GitHub issues with duplicate detection |
| `/advise` | Critical analysis before major decisions |
| `/audit-tests` | Identify untested code paths |
| `/sync` | Update plugin from marketplace |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    /implement Pipeline                       │
├─────────────────────────────────────────────────────────────┤
│  researcher → planner → test-master → implementer           │
│                              ↓                               │
│              reviewer + security-auditor + doc-master        │
│                        (parallel)                            │
├─────────────────────────────────────────────────────────────┤
│  22 Agents │ 28 Skills │ 66 Hooks │ 122 Libraries           │
└─────────────────────────────────────────────────────────────┘
```

**Model Tiers** (cost-optimized):
- **Haiku**: Research, review, docs (fast, cheap)
- **Sonnet**: Implementation, testing, planning (balanced)
- **Opus**: Security auditing (deep reasoning)

---

## Features

### Automated Git Operations
After pipeline completion, autonomous-dev can automatically:
- Generate commit messages following conventional commits
- Stage and commit changes
- Push to remote
- Create pull requests

### Batch Processing
Process multiple features or GitHub issues in isolated git worktrees:
```bash
/implement --issues 101,102,103
/implement --resume  # Continue after interruption
```

### Security-First
- 4-layer permission architecture
- Command sandboxing (safe/blocked/needs-approval)
- Path traversal and injection prevention
- 84% reduction in permission prompts

---

## Documentation

| Guide | Description |
|-------|-------------|
| [CLAUDE.md](CLAUDE.md) | Project instructions and quick reference |
| [Architecture](docs/ARCHITECTURE-OVERVIEW.md) | Technical architecture deep-dive |
| [Workflow Discipline](docs/WORKFLOW-DISCIPLINE.md) | Why pipelines beat direct implementation |
| [Performance](docs/PERFORMANCE.md) | Benchmarks and optimization history |
| [Security](docs/SECURITY.md) | Security model and hardening guide |
| [Batch Processing](docs/BATCH-PROCESSING.md) | Multi-feature batch workflows |

---

## Requirements

- [Claude Code](https://claude.ai/code) 2.0+
- macOS or Linux
- Git

---

## Philosophy

**Automation > Reminders > Hope**

Quality should be automatic, not optional. autonomous-dev makes the right thing the easy thing:
- Research happens automatically
- Tests are written first (TDD)
- Security is scanned on every feature
- Documentation stays in sync
- Git operations are orchestrated

You focus on describing what you want. The pipeline handles the rest.

---

## License

MIT

---

<p align="center">
  <strong>Built for developers who ship.</strong>
</p>
