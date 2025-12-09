# Autonomous Development Plugin for Claude Code

**Structured, autonomous, aligned AI development using PROJECT.md as the source of truth.**

> *"Trust the model, enforce via hooks, enhance via agents"*

---

## Why autonomous-dev?

### The Core Philosophy

- **Trust the model** — Claude coordinates 20 specialized agents, not a rigid script
- **Enforce via hooks** — Quality gates are 100% reliable (hooks can't be bypassed)
- **Enhance via agents** — Agents provide expertise, not rigid control

### Unique Capabilities

**1. TDD with Context Isolation**
Most frameworks run test-writing and implementation in the same context. The implementer "knows" what the tests expect and overfits.

We use **file-based handoff**: test-master writes tests to disk, implementer reads only test files (not reasoning). This prevents context pollution and enforces true TDD discipline.

**2. Hook-Enforced Quality Gates**
Agent-only systems can be "convinced" to skip steps. Hooks can't.

```python
# PreCommit hook - runs on EVERY commit, no exceptions
validate_project_alignment()  # Blocks if out of scope
security_scan()               # Blocks if vulnerabilities found
enforce_tdd()                 # Blocks if tests missing
```

**3. GenAI-Powered Semantic Decisions**
Other frameworks use regex patterns. We use Claude Haiku for semantic understanding:

```python
# Static pattern (others): if "password" in code: flag()
# GenAI pattern (us): "Is this a real secret or a test fixture?"
```

This reduces false positives by ~90% while catching real issues.

**4. Batch Processing with Crash Recovery**
Process 50+ features with automatic state persistence:
- Pauses at ~150K tokens, you run `/clear`, resume with `--resume <batch-id>`
- Intelligent retry for transient failures (network, rate limits)
- Per-feature git automation (commit, push, optional PR)

**5. Brownfield Retrofit**
Adopt autonomous-dev in existing projects with `/align-project-retrofit`:
- Analyzes existing codebase structure
- Infers PROJECT.md from current state
- Migrates incrementally (5-phase process)

---

## What Does It Do?

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

## The Problem We Solve

**Without autonomous-dev**:
- You ask Claude to build a feature
- Claude makes assumptions about your architecture
- You review, find issues, ask for fixes (repeat 3-5 times)
- Tests? Maybe. Security scan? Probably not. Docs? Definitely not.
- Hope nothing is out of scope

**With autonomous-dev**:
- You define your project once (PROJECT.md)
- You run `/auto-implement "issue #X"`
- Out-of-scope requests are **blocked before any code is written**
- Every feature gets: tests (TDD), security scan, documentation
- You review a complete, tested, documented pull request

**The difference**: Claude stops guessing and starts following your rules.

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

| Requirement | Install Command |
|-------------|-----------------|
| **Claude Code 2.0+** | [Download](https://claude.ai/download) |
| **Python 3.9+** | `python3 --version` to verify |
| **gh CLI** (GitHub) | `brew install gh && gh auth login` |

### One-Liner Install (Recommended)

```bash
cd /path/to/your/project
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

Then **fully quit Claude Code** (Cmd+Q on Mac, Ctrl+Q on Windows/Linux) and reopen it.

### Alternative: Plugin System

```
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
```

Restart Claude Code after installation.

### Update / Repair

```bash
# Check for updates
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh) --check

# Update (preserves customizations)
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh) --update

# Repair broken installation
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh) --sync
```

### Intelligent Installation (v3.41.0+)

The installer uses **GenAI-first installation** with protected file detection:

| Scenario | What Happens |
|----------|--------------|
| **Fresh Install** (no `.claude/`) | Copies all plugin files, runs `/setup` wizard |
| **Brownfield** (existing project) | Detects and **preserves** your PROJECT.md, .env, custom hooks |
| **Upgrade** (existing plugin) | Updates plugin files, **preserves** your customizations |

**Protected Files** (never overwritten):
- `PROJECT.md` - Your project definition
- `.env`, `.env.local` - Your secrets
- Custom hooks with your modifications
- State files (batch_state.json, etc.)

The installer analyzes your project and asks before touching anything you've customized.

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

Copy and paste into Claude Code:

```
I want to set up autonomous-dev for this project. Please help me:

1. Verify plugin is installed:
   - Check if .claude/hooks/ and .claude/lib/ exist
   - If NOT: Run the installer first

2. Run: python3 .claude/hooks/setup.py

3. Help me create .claude/PROJECT.md with GOALS, SCOPE, CONSTRAINTS, ARCHITECTURE

4. Verify gh CLI: gh --version

5. Run /health-check

My project is: [DESCRIBE YOUR PROJECT HERE]
```

### Existing Project (Brownfield)

```
I want to add autonomous-dev to this existing project:

1. Verify plugin installed (check .claude/hooks/ exists)

2. Run: /align-project-retrofit --dry-run (preview changes)

3. Help me create PROJECT.md based on existing code

4. Run: /align-project-retrofit (step-by-step)

5. Run /health-check
```

---

## What You Get

| Component | Count | Purpose |
|-----------|-------|---------|
| **Commands** | 21 | Slash commands for workflows |
| **Agents** | 20 | Specialized AI for each SDLC stage |
| **Skills** | 28 | Domain knowledge (progressive disclosure) |
| **Hooks** | 44 | Automatic validation on commits |
| **Libraries** | 33 | Reusable Python utilities |

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
- [Commands](plugins/autonomous-dev/commands/) - All 21 commands
- [Hooks](docs/HOOKS.md) - 44 automation hooks
- [Skills](docs/SKILLS-AGENTS-INTEGRATION.md) - 28 knowledge packages
- [Libraries](docs/LIBRARIES.md) - 29 Python utilities

### Troubleshooting
- [Troubleshooting Guide](plugins/autonomous-dev/docs/TROUBLESHOOTING.md)
- [Development Guide](docs/DEVELOPMENT.md)

**[Full Documentation Index](docs/DOCUMENTATION_INDEX.md)**

---

## Quick Reference

```bash
# Install
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
# Restart Claude Code (Cmd+Q / Ctrl+Q)

# Daily workflow
/auto-implement "issue #72"     # Single feature
/batch-implement --issues 1 2 3 # Multiple features
/clear                          # Reset context between batches

# Check status
/health-check                   # Verify installation
/status                         # View alignment

# Update
/update-plugin                  # Get latest version
```

---

## Support

- **Issues**: [github.com/akaszubski/autonomous-dev/issues](https://github.com/akaszubski/autonomous-dev/issues)
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)

---

## License

MIT License - See [LICENSE](LICENSE) for details.
