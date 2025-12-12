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

```bash
# Install (30 seconds)
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)

# Restart Claude Code (Cmd+Q / Ctrl+Q), then:
/setup
```

That's it. Run `/auto-implement "your feature"` and watch 7 agents build it.

> Need more install options? See [Install](#install) for prerequisites, plugin system, and troubleshooting.

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
| **gh CLI** (GitHub) | `brew install gh && gh auth login` |
| **Network** | HTTPS access to github.com (for curl installer) |

### One-Liner Install

```bash
cd /path/to/your/project
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

Then:
1. **Restart Claude Code** (Cmd+Q on Mac, Ctrl+Q on Windows/Linux)
2. Run `/setup` to complete installation

That's it! Works for both fresh installs and updates.

### Why Not Just Use the Marketplace?

autonomous-dev **outgrew the simple plugin model**. It requires:
- Global hooks in `~/.claude/hooks/` (auto-approval, security validation)
- Python libraries in `~/.claude/lib/` (agent dependencies)
- Specific `~/.claude/settings.json` format (permission patterns)

The marketplace can download files, but can't configure global `~/.claude/` infrastructure. That's why `install.sh` exists — it handles everything.

### How It Works

The installer uses a **two-phase architecture**:

```
install.sh → Downloads files to ~/.autonomous-dev-staging/
           → Installs /setup command to .claude/commands/
           → You restart Claude Code

/setup     → Detects: FRESH, BROWNFIELD, or UPGRADE
           → Installs plugin files intelligently
           → Preserves your customizations
           → Cleans up staging
```

**Why two phases?** Claude Code caches commands at startup. The installer bootstraps `/setup` directly so it works even on fresh installs.

### Installation Types

| Type | Detection | What Happens |
|------|-----------|--------------|
| **FRESH** | No `.claude/` directory | Copies all plugin files, guides PROJECT.md creation |
| **BROWNFIELD** | Has `.claude/` but no plugin | Preserves your existing files, adds plugin around them |
| **UPGRADE** | Has existing plugin | Updates plugin files, preserves all customizations |

### Protected Files (Never Overwritten)

- `PROJECT.md` - Your project definition
- `.env`, `.env.local` - Your secrets
- Custom hooks with your modifications
- State files (`batch_state.json`, etc.)

The `/setup` wizard analyzes each file and asks before touching anything you've customized.

### Installation Troubleshooting

| Problem | Solution |
|---------|----------|
| `/setup` command not found | Fully restart Claude Code (Cmd+Q / Ctrl+Q), not just close window |
| Network download failed | Check HTTPS access to github.com, or use plugin system instead |
| Permission denied | Ensure `.claude/` directory is writable |
| Staging directory stuck | Delete `~/.autonomous-dev-staging/` and re-run installer |

For debugging, use verbose mode:
```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh) --verbose
```

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
| **Commands** | 20 | Slash commands for workflows |
| **Agents** | 20 | Specialized AI for each SDLC stage |
| **Skills** | 28 | Domain knowledge (progressive disclosure) |
| **Hooks** | 44 | Automatic validation on commits |
| **Libraries** | 40+ | Reusable Python utilities |

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
- [Commands](plugins/autonomous-dev/commands/) - All 20 commands
- [Hooks](docs/HOOKS.md) - 44 automation hooks
- [Skills](docs/SKILLS-AGENTS-INTEGRATION.md) - 28 knowledge packages
- [Libraries](docs/LIBRARIES.md) - 40+ Python utilities

### Troubleshooting
- [Troubleshooting Guide](plugins/autonomous-dev/docs/TROUBLESHOOTING.md)
- [Development Guide](docs/DEVELOPMENT.md)

**[Full Documentation Index](docs/DOCUMENTATION_INDEX.md)**

---

## Quick Reference

```bash
# Install (one-liner)
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
# Restart Claude Code (Cmd+Q / Ctrl+Q), then run /setup

# Daily workflow
/auto-implement "issue #72"     # Single feature
/batch-implement --issues 1 2 3 # Multiple features
/clear                          # Reset context between batches

# Check status
/health-check                   # Verify installation
/status                         # View alignment

# Update (same as install - /setup detects upgrade)
/update-plugin                  # Or re-run install.sh + /setup
```

---

## Support

- **Issues**: [github.com/akaszubski/autonomous-dev/issues](https://github.com/akaszubski/autonomous-dev/issues)
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)

---

## License

MIT License - See [LICENSE](LICENSE) for details.
