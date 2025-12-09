# Autonomous Development Plugin for Claude Code

**Structured, autonomous, aligned AI development using PROJECT.md as the source of truth.**

---

## What Is This?

**The problem**: When you use Claude Code to build features, Claude doesn't know your project's goals, what's in or out of scope, or your architectural decisions. So it makes assumptions. You end up with code that works but doesn't fit your project - scope creep, wrong patterns, missing tests.

**The solution**: This plugin adds structure to AI-assisted development:

1. **You define your project** in a file called PROJECT.md - your goals, what's in/out of scope, constraints, architecture
2. **You track work in GitHub Issues** - each feature or bug is an issue
3. **You run one command** - `/auto-implement "issue #72"`
4. **Claude executes a full development pipeline** - research, planning, TDD, implementation, code review, security scan, documentation
5. **Claude stays aligned** - if a feature doesn't fit your PROJECT.md scope, it's blocked before any code is written

**In short**: You define the rules once. Claude follows them for every feature.

---

## What Does It Actually Do?

When you type `/auto-implement "issue #72"`, Claude runs 7 specialized agents in sequence:

| Step | Agent | What It Does |
|------|-------|--------------|
| 1 | **alignment-validator** | Checks if the feature fits your PROJECT.md goals and scope. Blocks if it doesn't. |
| 2 | **researcher** | Searches for best practices, patterns, and existing solutions |
| 3 | **planner** | Designs the architecture and creates an implementation plan |
| 4 | **test-master** | Writes tests FIRST (TDD) - the tests define what "done" means |
| 5 | **implementer** | Writes code to make the tests pass |
| 6 | **reviewer** | Reviews code quality, checks it follows your patterns |
| 7 | **security-auditor** | Scans for vulnerabilities (OWASP top 10) |
| 8 | **doc-master** | Updates documentation to match the new code |

After all agents complete:
- Code is committed with a descriptive message
- Changes are pushed to your branch
- A pull request is created
- The GitHub issue is closed with a summary

**One command. Full software development lifecycle. Aligned to your project.**

---

## Why Use This?

**Without autonomous-dev**:
- You ask Claude to build a feature
- Claude makes assumptions about your architecture
- You review the code, find issues, ask for fixes
- Repeat until it's acceptable
- Manually write tests (or skip them)
- Manually update docs (or skip them)
- Hope you didn't introduce security issues

**With autonomous-dev**:
- You define your project once (PROJECT.md)
- You create a GitHub issue for each feature
- You run `/auto-implement "issue #X"`
- Claude follows your rules, writes tests first, reviews its own work, scans for security, updates docs
- You review a complete, tested, documented pull request

**The difference**: Claude stops guessing and starts following your project's rules.

---

## What's PROJECT.md?

A simple markdown file that defines your project. Example:

```markdown
# PROJECT.md

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
- All endpoints must have rate limiting

## ARCHITECTURE
- src/api/ - FastAPI route handlers
- src/models/ - SQLAlchemy models
- src/services/ - Business logic
- tests/ - Pytest test suite
```

When you run `/auto-implement "Add user registration"`:
- ✅ Allowed - user registration is IN scope
- Claude follows your FastAPI + PostgreSQL + JWT constraints
- Tests go in `tests/`, code follows your architecture

When you run `/auto-implement "Add analytics dashboard"`:
- ❌ Blocked - analytics is OUT of scope
- No code written, no time wasted
- You're asked to either change the request or update PROJECT.md

**This is how Claude stays aligned** - it reads PROJECT.md before every feature.

---

## Install

### Prerequisites

| Requirement | Install Command |
|-------------|-----------------|
| **Claude Code 2.0+** | [Download](https://claude.ai/download) |
| **Python 3.9+** | `python3 --version` to verify |
| **gh CLI** (GitHub) | `brew install gh && gh auth login` |

### New Project (Greenfield)

Copy and paste into Claude Code:

```
I want to set up autonomous-dev for a new project. Please help me:

1. Install the plugin:
   - Run: /plugin marketplace add akaszubski/autonomous-dev
   - Run: /plugin install autonomous-dev

2. Tell me to restart Claude Code (Cmd+Q on Mac, Ctrl+Q on Windows/Linux)

3. After I restart, set up hooks and scripts:
   - Run: python3 ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/hooks/setup.py
   - Walk me through the setup wizard options

4. Help me create PROJECT.md:
   - Create .claude/PROJECT.md with GOALS, SCOPE, CONSTRAINTS, ARCHITECTURE
   - Ask me about my project goals, what's in/out of scope, technical constraints

5. Set up GitHub integration:
   - Verify gh CLI: gh --version
   - Help me create initial GitHub issues

6. Run /health-check to verify everything works

7. Show me my first feature with /auto-implement "issue #1"

My project is: [DESCRIBE YOUR PROJECT HERE]
```

### Existing Project (Brownfield)

Copy and paste into Claude Code:

```
I want to add autonomous-dev to my existing project. Please help me:

1. Install the plugin:
   - Run: /plugin marketplace add akaszubski/autonomous-dev
   - Run: /plugin install autonomous-dev

2. Tell me to restart Claude Code (Cmd+Q on Mac, Ctrl+Q on Windows/Linux)

3. After I restart, set up hooks and scripts:
   - Run: python3 ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/hooks/setup.py
   - Walk me through the setup wizard options

4. Analyze my existing project:
   - Run /align-project-retrofit --dry-run
   - Show me what changes would be made

5. Help me create PROJECT.md based on my existing code:
   - Infer GOALS, SCOPE, CONSTRAINTS, ARCHITECTURE from what exists

6. Run the retrofit:
   - Run /align-project-retrofit (step-by-step mode)

7. Run /health-check to verify everything works
```

---

## Usage

### Single Feature (from GitHub Issue)

```bash
/auto-implement "issue #72"
```

### Multiple Features (Batch)

```bash
# From GitHub issues
/batch-implement --issues 72 73 74 75

# From a file (one feature per line)
/batch-implement sprint-backlog.txt

# Resume after context reset
/batch-implement --resume batch-20251209-143022
```

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
/status              # View PROJECT.md alignment and progress
/align-project       # Fix alignment issues
/create-issue "..."  # Create GitHub issue with research
/health-check        # Verify plugin installation
```

---

## How It Works

### The Agent Pipeline

Every `/auto-implement` runs this 7-agent sequence:

| Agent | Purpose | Output |
|-------|---------|--------|
| **researcher** | Find patterns, best practices | Research summary |
| **planner** | Design architecture, integration | Implementation plan |
| **test-master** | Write tests FIRST (TDD) | Failing test suite |
| **implementer** | Write code to pass tests | Working implementation |
| **reviewer** | Check code quality, patterns | Review feedback |
| **security-auditor** | OWASP vulnerability scan | Security report |
| **doc-master** | Update documentation | Synced docs |

### PROJECT.md Alignment

Features validate against your PROJECT.md before work starts:

```markdown
# .claude/PROJECT.md

## GOALS
- Build a REST API for user management
- Achieve 80% test coverage

## SCOPE
IN: User CRUD, authentication, authorization
OUT: Admin dashboard, analytics, reporting

## CONSTRAINTS
- Python 3.11+ with FastAPI
- PostgreSQL database
- JWT authentication only

## ARCHITECTURE
- src/api/ - FastAPI routes
- src/models/ - SQLAlchemy models
- src/services/ - Business logic
- tests/ - Pytest test suite
```

**If you request something OUT of scope, it's blocked - not implemented wrong.**

### GitHub-First Workflow

```
1. Create GitHub Issue → "Add password reset flow"
2. Run /auto-implement "issue #42"
3. Pipeline executes (research → plan → TDD → implement → review → security → docs)
4. Code committed, pushed, PR created
5. Issue #42 auto-closed with summary
```

---

## Context Management

Each feature uses ~25-35K tokens. After 4-5 features (~150K tokens):

1. System pauses automatically
2. Run `/clear` to reset context
3. Run `/batch-implement --resume <batch-id>` to continue

**This is by design** - forces review checkpoints and prevents degraded performance.

---

## Documentation

### Core Concepts
- [Architecture](docs/ARCHITECTURE.md) - Two-layer system (hooks + agents)
- [Agents](docs/AGENTS.md) - 20 specialized AI agents
- [PROJECT.md Philosophy](docs/MAINTAINING-PHILOSOPHY.md) - Why alignment-first works

### Workflows
- [Batch Processing](docs/BATCH-PROCESSING.md) - Multi-feature workflows
- [Git Automation](docs/GIT-AUTOMATION.md) - Auto-commit, push, PR, issue close
- [Brownfield Adoption](docs/BROWNFIELD-ADOPTION.md) - Retrofit existing projects

### Reference
- [Commands](plugins/autonomous-dev/commands/) - All 21 commands
- [Hooks](docs/HOOKS.md) - 44 automation hooks
- [Skills](docs/SKILLS-AGENTS-INTEGRATION.md) - 28 knowledge packages
- [Libraries](docs/LIBRARIES.md) - 29 Python utilities

### Troubleshooting
- [Troubleshooting Guide](plugins/autonomous-dev/docs/TROUBLESHOOTING.md) - Common issues
- [Development Guide](docs/DEVELOPMENT.md) - Contributing

**[Full Documentation Index](docs/DOCUMENTATION_INDEX.md)**

---

## What You Get

| Component | Count | Purpose |
|-----------|-------|---------|
| Commands | 21 | Slash commands for workflows |
| Agents | 20 | Specialized AI for each SDLC stage |
| Skills | 28 | Domain knowledge (progressive disclosure) |
| Hooks | 44 | Automatic validation on commits |
| Libraries | 29 | Reusable Python utilities |

---

## Quick Reference

```bash
# Install
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
# Restart Claude Code (Cmd+Q / Ctrl+Q)

# Daily workflow
/auto-implement "issue #72"    # Single feature
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
