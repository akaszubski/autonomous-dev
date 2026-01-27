# Project Context - Autonomous Development Plugin

**Last Updated**: 2026-01-27
**Version**: v3.44.0

---

## GOALS

**Mission**: Traditional software engineering meets AI.

Claude is brilliant but drifts. It starts with a plan, then improvises. Documentation falls out of sync. Tests get "added later." Direction shifts mid-feature.

autonomous-dev provides **macro alignment with micro flexibility**:

- **Macro**: PROJECT.md defines goals, scope, constraints — Claude checks alignment before every feature
- **Micro**: Claude can still improve the implementation when it finds better patterns

**What success looks like**:

```
research → plan → test → implement → review → security → docs → commit
```

Every step. Every feature. Documentation, tests, and code stay in sync automatically.

```bash
/implement "issue #72"
```

**User Intent** (stated 2025-10-26):
> "I speak requirements and Claude Code delivers a first grade software engineering outcome in minutes by following all the necessary steps that would need to be taken in top level software engineering but so much quicker with the use of AI and validation"

**Key Points:**
- All SDLC steps required — Research → Plan → TDD → Implement → Review → Security → Docs (no shortcuts)
- Professional quality enforced via hooks (can't skip or bypass)
- Speed via AI — Each step accelerated, not eliminated
- PROJECT.md is the gatekeeper — Work blocked if not aligned

---

## SCOPE

**IN Scope** (Features we build):

- Feature request detection and auto-orchestration
- 8-step pipeline: research → plan → test → implement → review → security → docs → commit
- PROJECT.md alignment validation before any work begins
- File organization enforcement (src/, tests/, docs/)
- Brownfield project support (`/align --retrofit`)
- Batch processing with crash recovery (`/implement --batch`, `--issues`, `--resume`)
- Automated git operations (commit, push, PR creation)
- MCP security validation and tool auto-approval

**OUT of Scope** (Features we avoid):

- Replacing human developers — AI augments, doesn't replace
- Skipping PROJECT.md alignment — Never proceed without validation
- Optional best practices — All SDLC steps are mandatory
- Language-specific lock-in — Stay generic
- SaaS/Cloud hosting — Local-first
- Paid features — 100% free, MIT license

---

## CONSTRAINTS

### Design Principles

**Philosophy**: "Less is more" — Every element serves the mission.

**Anti-bloat gates** (every feature must pass):
1. **Alignment** — Does it serve the primary mission?
2. **Constraint** — Does it respect boundaries?
3. **Minimalism** — Is this the simplest solution?
4. **Value** — Does benefit outweigh complexity?

**Red flags** (immediate bloat indicators):
- "This will be useful in the future" (hypothetical)
- "We should also handle X, Y, Z" (scope creep)
- "Let's create a framework for..." (over-abstraction)

### Technical Requirements

- **Primary**: Markdown (agent/skill/command definitions)
- **Supporting**: Python 3.11+ (hooks/scripts), Bash (automation), JSON (config)
- **Testing**: pytest, automated test scripts
- **Claude Code**: 2.0+ with plugins, agents, hooks, skills, slash commands

### Performance Requirements

- Context budget: < 8,000 tokens per feature
- Feature time: 15-30 minutes per feature
- Test execution: < 60 seconds
- Validation hooks: < 10 seconds

### Security Requirements

- No hardcoded secrets (enforced by security_scan.py)
- TDD mandatory (tests before implementation)
- Tool restrictions per agent (principle of least privilege)
- 80% minimum test coverage
- MCP security validation (path traversal, injection prevention)

---

## ARCHITECTURE

### Dual-Layer System

**Layer 1: Hook-Based Enforcement** (Automatic, 100% Reliable)
- Git-level pre-commit hooks validate ALL quality gates
- Enforces: PROJECT.md alignment, security, tests, docs, file organization
- Blocks commits if violations detected
- **Guaranteed execution** — hooks run on every commit

**Layer 2: Agent-Based Intelligence** (User-Invoked, AI-Enhanced)
- User invokes `/implement` for AI assistance
- Claude coordinates specialist agents
- Provides intelligent guidance and implementation help
- **Conditional execution** — Claude decides which agents based on complexity

**Key Distinction:**
- **Hooks = enforcement** (quality gates, always active, blocking)
- **Agents = intelligence** (expert assistance, conditionally invoked, advisory)

### Current Components (v3.44.0)

| Component | Count | Purpose |
|-----------|-------|---------|
| Agents | 23 | Specialized AI assistants (8 pipeline + 15 utility) |
| Skills | 29 | Progressive disclosure knowledge packages |
| Commands | 21 | Active slash commands (5 archived: align-claude, align-project, align-project-retrofit, sync-dev, update-plugin) |
| Hooks | 72 | Automation and enforcement |
| Libraries | 154 | Python utilities for security, validation, automation |

### Agent Pipeline

```
/implement "feature"
     ↓
PROJECT.md Alignment Check (blocks if misaligned)
     ↓
┌──────────┬──────────┬────────────┬─────────────┐
│ Research │ Planning │ TDD Tests  │ Implementation│
│ (Haiku)  │ (Sonnet) │ (Sonnet)   │ (Sonnet)     │
└──────────┴──────────┴────────────┴─────────────┘
     ↓
┌──────────┬────────────┬───────────┐
│ Review   │ Security   │ Docs      │  ← Parallel validation
│ (Haiku)  │ (Opus)     │ (Haiku)   │
└──────────┴────────────┴───────────┘
     ↓
Git Operations (commit, push, PR)
```

**Model Tiers:**
- **Haiku** (8 agents): Fast pattern matching — researcher-local, reviewer, doc-master, commit-message-generator, alignment-validator, project-progress-tracker, sync-validator, pr-description-generator
- **Sonnet** (11 agents): Balanced reasoning — researcher, implementer, test-master, planner, issue-creator, setup-wizard, project-bootstrapper, brownfield-analyzer, quality-validator, alignment-analyzer, project-status-analyzer
- **Opus** (2 agents): Deep analysis — security-auditor, advisor

**Agent Categories** (23 total):
- **Pipeline** (8): researcher-local, planner, test-master, implementer, reviewer, security-auditor, doc-master, issue-creator
- **Utility** (15): advisor, alignment-analyzer, alignment-validator, brownfield-analyzer, commit-message-generator, experiment-critic, pr-description-generator, project-bootstrapper, project-progress-tracker, project-status-analyzer, quality-validator, researcher, setup-wizard, sync-validator, test-coverage-auditor

### Repository Structure

```
autonomous-dev/
├── plugins/autonomous-dev/     # Plugin source (what users install)
│   ├── agents/                 # 23 AI agents
│   ├── commands/               # 21 active commands (5 archived)
│   ├── hooks/                  # 72 automation hooks
│   ├── skills/                 # 29 skill packages
│   ├── lib/                    # 154 Python libraries
│   └── docs/                   # User documentation
├── docs/                       # Developer documentation
├── tests/                      # Test suite
├── .claude/                    # Installed plugin (symlink)
├── CLAUDE.md                   # Development instructions
├── PROJECT.md                  # This file (alignment gatekeeper)
└── README.md                   # User-facing overview
```

---

## DISTRIBUTION

**Bootstrap-First Architecture** — install.sh is the primary installation method.

```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

**Why bootstrap-first?** autonomous-dev requires global infrastructure that the marketplace cannot configure:
- Global hooks in `~/.claude/hooks/`
- Python libraries in `~/.claude/lib/`
- Specific `~/.claude/settings.json` format

**What install.sh does:**
- Downloads all plugin components
- Installs global infrastructure (~60 hooks, ~75 libs)
- Installs project components (commands, agents, config)
- Non-blocking: Missing components don't block workflow

**Uninstall:**
```bash
/sync --uninstall --force
```

---

## ENFORCEMENT

**PROJECT.md is the gatekeeper** — All work validates against this file before execution.

**Blocking enforcement:**
- Feature doesn't serve GOALS → BLOCKED
- Feature is OUT of SCOPE → BLOCKED
- Feature violates CONSTRAINTS → BLOCKED

**Options when blocked:**
1. Update PROJECT.md to include the feature
2. Modify the request to align with current scope
3. Don't implement

**This file is the source of truth for strategic direction.**

---

**For development workflow**: See CLAUDE.md
**For user documentation**: See README.md
**For troubleshooting**: See plugins/autonomous-dev/docs/TROUBLESHOOTING.md
