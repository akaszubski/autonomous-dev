# autonomous-dev

[![Claude Code 2.0+](https://img.shields.io/badge/Claude%20Code-2.0+-blueviolet)](https://claude.ai/download)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)

**Turn Claude Code into a complete engineering team.**

One command. Full pipeline: research → plan → tests → code → review → security scan → docs → PR.

```bash
/auto-implement "issue #72"
```

15-30 minutes later: tested, reviewed, documented pull request ready for merge.

<!-- TODO: Add demo GIF here showing /auto-implement in action -->
<!-- ![Demo](docs/assets/demo.gif) -->

## Quick Start

**Step 1: Install**
```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

**Step 2: Restart Claude Code**
- Press `Cmd+Q` (Mac) or `Ctrl+Q` (Windows/Linux)
- Reopen Claude Code

**Done!** All 7 commands and 22 agents are ready. Try:
```bash
/auto-implement "your feature description"
```

> **Optional**: Run `/setup` to create PROJECT.md with your project goals and constraints.

---

## Claude Code vs Claude Code + autonomous-dev

| Aspect | Vanilla Claude Code | With autonomous-dev |
|--------|---------------------|---------------------|
| **Workflow** | You guide each step manually | 7 agents run automatically |
| **Tests** | Maybe, if you remember to ask | Always. TDD enforced by hooks |
| **Security** | Hope you catch issues | OWASP scan on every feature |
| **Documentation** | Usually forgotten | Auto-updated every commit |
| **Scope creep** | Claude makes assumptions | Out-of-scope requests blocked |
| **Quality gates** | Trust-based | Hook-enforced (can't bypass) |
| **Git workflow** | Manual commits/PRs | Auto-commit, push, PR, issue close |
| **Batch processing** | One feature at a time | 50+ features with crash recovery |

**The difference**: Claude stops guessing and starts following your rules.

---

## How It Works

When you type `/auto-implement "issue #72"`, Claude runs a 7-agent pipeline:

| Step | Agent | What It Does | Model |
|------|-------|--------------|-------|
| 1 | **researcher** | Searches for patterns, best practices | Haiku (fast) |
| 2 | **planner** | Designs architecture, integration plan | Sonnet |
| 3 | **test-master** | Writes tests FIRST (TDD) | Sonnet |
| 4 | **implementer** | Writes code to make tests pass | Sonnet |
| 5 | **reviewer** | Reviews code quality (parallel) | Haiku |
| 6 | **security-auditor** | OWASP vulnerability scan (parallel) | Haiku |
| 7 | **doc-master** | Updates documentation (parallel) | Haiku |

**Performance**: 1-30 minutes per feature depending on complexity (see [Benchmarks](#honest-benchmarks)). Steps 5-7 run in parallel (60% faster than sequential).

After completion:
- Code committed with conventional commit message
- Changes pushed to your branch
- Pull request created
- GitHub issue auto-closed with summary

---

## Why It's Different

Other AI coding tools give you **one context** where everything happens. We give you **isolated agents** that can't cheat.

| Feature | How We Do It Differently |
|---------|-------------------------|
| **TDD** | Test-master and implementer run in **separate contexts**. The implementer can't see test logic—only test files. No overfitting. |
| **Quality Gates** | Hooks run on every commit. Claude can't be "convinced" to skip security scans or tests. |
| **Scope Control** | PROJECT.md defines what's in/out. Out-of-scope requests are blocked before code is written. |
| **Semantic Analysis** | We use Claude Haiku for validation, not regex. "Is this a real secret or a test fixture?" reduces false positives by ~90%. |

<details>
<summary><b>Technical deep-dive: Context isolation</b></summary>

Most frameworks run test-writing and implementation in the same context. The implementer "knows" what tests expect and overfits.

We use **file-based handoff**: test-master writes tests to disk. The implementer runs in its own context and reads only test files (not test-master's reasoning). This prevents context pollution and enforces true TDD.

See [docs/TDD-CONTEXT-ISOLATION.md](docs/TDD-CONTEXT-ISOLATION.md) for details.
</details>

---

## PROJECT.md: Your Source of Truth

```markdown
# .claude/PROJECT.md

## GOALS
- Build a REST API for user management
- Achieve 80% test coverage
- Ship MVP by end of Q1

## SCOPE
IN: User CRUD, authentication, password reset
OUT: Admin dashboard, analytics, billing

## CONSTRAINTS
- Python 3.11+ with FastAPI
- PostgreSQL database
- JWT authentication (no sessions)

## ARCHITECTURE
- src/api/ - FastAPI routes
- src/models/ - SQLAlchemy models
- src/services/ - Business logic
- tests/ - Pytest test suite
```

**When you request something IN scope**: Claude follows your constraints and architecture.

**When you request something OUT of scope**: Blocked immediately. No code written, no time wasted.

This is how Claude stays aligned — it reads PROJECT.md before every feature.

---

## Install

### Prerequisites

| Requirement | Details |
|-------------|---------|
| **Claude Code 2.0+** | [Download](https://claude.ai/download) |
| **Python 3.9+** | `python3 --version` to verify |
| **gh CLI** (optional) | For GitHub automation: `brew install gh && gh auth login` |

### Installation

```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

Then restart Claude Code (`Cmd+Q` / `Ctrl+Q`).

**What gets installed:**
- `~/.claude/hooks/` - 48 automation hooks (global)
- `~/.claude/lib/` - 68 Python libraries (global)
- `.claude/commands/` - 7 slash commands (project)
- `.claude/agents/` - 22 AI agents (project)
- `.claude/scripts/`, `.claude/config/`, `.claude/templates/` - Supporting files

### Updating

Same command as install - it detects existing installation and updates:
```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

Or use `/sync` from within Claude Code to fetch latest from GitHub.

### Troubleshooting

| Problem | Solution |
|---------|----------|
| Commands not found | Fully restart Claude Code (`Cmd+Q` / `Ctrl+Q`), not just close window |
| Network error | Check HTTPS access to github.com |
| Permission denied | Ensure `~/.claude/` and `.claude/` are writable |

<details>
<summary><b>Technical details</b></summary>

autonomous-dev requires global infrastructure that the marketplace can't configure. The installer:
1. Downloads all files to `~/.autonomous-dev-staging/`
2. Installs global components to `~/.claude/` (hooks, libs, settings)
3. Installs project components to `.claude/` (commands, agents, scripts, config, templates)
4. Preserves existing files (PROJECT.md, .env, custom hooks)

See [docs/BOOTSTRAP_PARADOX_SOLUTION.md](docs/BOOTSTRAP_PARADOX_SOLUTION.md) for why marketplace-only installation doesn't work.
</details>

---

## Usage

### Single Feature

```bash
/auto-implement "issue #72"
```

### Batch Processing (50+ Features)

```bash
# From GitHub issues
/batch-implement --issues 72 73 74 75

# From a file (one feature per line)
/batch-implement sprint-backlog.txt

# Resume after context reset
/batch-implement --resume batch-20251209-143022
```

**Context Management**: Each feature uses 15-35K tokens (depends on complexity). After 4-8 features, the system pauses. Run `/clear`, then resume with `--resume`.

### Individual Pipeline Stages

```bash
/research "JWT authentication patterns"   # Research best practices
/plan "Add JWT to API"                     # Plan architecture
/test-feature "JWT authentication"         # Write tests (TDD)
/implement "Make JWT tests pass"           # Implement code
/review                                    # Review quality
/security-scan                             # Scan vulnerabilities
/update-docs                               # Sync documentation
```

### Project Management

```bash
/status                    # View PROJECT.md alignment and progress
/align-project             # Fix alignment issues
/align-project-retrofit    # Retrofit existing project
/create-issue "..."        # Create GitHub issue with research
/health-check              # Verify plugin installation
```

---

## Project Setup Prompts

### New Project (Greenfield)

After installing the plugin, run `/setup` which will:
1. Detect your project type (FRESH/BROWNFIELD/UPGRADE)
2. Guide you through creating PROJECT.md with GOALS, SCOPE, CONSTRAINTS, ARCHITECTURE
3. Configure hooks and validate the installation

Or copy this prompt into Claude Code for manual guidance:

```
Help me set up autonomous-dev for this new project:
1. Run /health-check to verify plugin installation
2. Help me create .claude/PROJECT.md with GOALS, SCOPE, CONSTRAINTS, ARCHITECTURE
3. Verify gh CLI works: gh --version

My project is: [DESCRIBE YOUR PROJECT HERE]
```

### Existing Project (Brownfield)

For projects with existing `.claude/` configuration:

```
I want to add autonomous-dev to this existing project:

1. Run /health-check to verify plugin installation
2. Run /align-project-retrofit --dry-run (preview changes)
3. Help me create PROJECT.md based on existing code
4. Run /align-project-retrofit (apply changes step-by-step)
5. Run /health-check to verify
```

---

## What You Get

| Component | Count | Purpose |
|-----------|-------|---------|
| **Commands** | 7 | Slash commands for workflows |
| **Agents** | 22 | Specialized AI for each SDLC stage |
| **Skills** | 28 | Domain knowledge (progressive disclosure) |
| **Hooks** | 48 | Automatic validation on commits |
| **Libraries** | 68 | Reusable Python utilities |

### Key Agents

| Agent | Purpose | Model |
|-------|---------|-------|
| researcher | Find patterns, best practices | Haiku |
| planner | Design architecture | Sonnet |
| test-master | Write tests first (TDD) | Sonnet |
| implementer | Make tests pass | Sonnet |
| reviewer | Code quality review | Haiku |
| security-auditor | OWASP vulnerability scan | Haiku |
| doc-master | Documentation sync | Haiku |
| advisor | Critical thinking, risk analysis | Sonnet |

### Key Hooks

| Hook | Trigger | What It Does |
|------|---------|--------------|
| validate_project_alignment | PreCommit | Blocks out-of-scope changes |
| enforce_tdd | PreCommit | Blocks commits without tests |
| security_scan | PreCommit | Blocks security vulnerabilities |
| auto_git_workflow | SubagentStop | Auto-commit, push, PR after pipeline |

---

## Honest Benchmarks

We document **typical performance**, not best-case marketing claims:

### Time Per Feature (from session data)

| Complexity | Time | Example |
|------------|------|---------|
| **Simple** (existing patterns) | 1-5 min | Add validation to existing API |
| **Medium** (new feature) | 10-15 min | New endpoint with tests |
| **Complex** (security, architecture) | 25-30 min | MCP security system, major refactor |

### Per-Phase Timing

| Phase | Typical | Notes |
|-------|---------|-------|
| Research + Planning | 2-5 min | Haiku model, fast |
| Test-master (TDD) | 5-12 min | Biggest variable - depends on scope |
| Implementer | 5-12 min | Making tests pass |
| Validation (parallel) | 3-5 min | reviewer + security + docs |

### Session Limits

| Metric | Typical | Notes |
|--------|---------|-------|
| Features per session | 4-8 | Depends on complexity |
| Token usage per feature | 15-35K | Simple=15K, Complex=35K |

**Context resets are intentional design**, not bugs. They force review checkpoints and prevent degraded AI performance.

---

## Documentation

### Core Concepts
- [Architecture](docs/ARCHITECTURE.md) - Two-layer system (hooks + agents)
- [Agents](docs/AGENTS.md) - 20 specialized AI agents
- [Philosophy](docs/MAINTAINING-PHILOSOPHY.md) - Why alignment-first works

### Workflows
- [Batch Processing](docs/BATCH-PROCESSING.md) - Multi-feature workflows
- [Git Automation](docs/GIT-AUTOMATION.md) - Auto-commit, push, PR
- [Brownfield Adoption](docs/BROWNFIELD-ADOPTION.md) - Retrofit existing projects

### Reference
- [Commands](plugins/autonomous-dev/commands/) - All 7 commands
- [Hooks](docs/HOOKS.md) - 45 automation hooks
- [Skills](docs/SKILLS-AGENTS-INTEGRATION.md) - 28 knowledge packages
- [Libraries](docs/LIBRARIES.md) - 40+ Python utilities

### Troubleshooting
- [Troubleshooting Guide](plugins/autonomous-dev/docs/TROUBLESHOOTING.md)
- [Development Guide](docs/DEVELOPMENT.md)

**[Full Documentation Index](docs/DOCUMENTATION_INDEX.md)**

---

## Quick Reference

```bash
# Install
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
# Then restart Claude Code (Cmd+Q / Ctrl+Q)

# Daily workflow
/auto-implement "issue #72"     # Single feature
/batch-implement --issues 1 2 3 # Multiple features
/clear                          # Reset context between batches

# Maintenance
/health-check                   # Verify installation
/sync                           # Update to latest version
```

---

## Support

- **Issues**: [github.com/akaszubski/autonomous-dev/issues](https://github.com/akaszubski/autonomous-dev/issues)
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)

---

## License

MIT License - See [LICENSE](LICENSE) for details.
