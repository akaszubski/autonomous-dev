# Project Context - Autonomous Development Plugin

**Last Updated**: 2026-02-17
**Version**: v3.51.0

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
                                                                    ↓
                                              session logs → analysis → issues
```

Every step. Every feature. Documentation, tests, and code stay in sync automatically. The system learns from its own sessions and files issues for what it finds.

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
- Continuous improvement — System learns from sessions, detects drift, auto-files issues

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
- Continuous improvement (session activity logging → drift detection → auto-filed issues)
- GenAI intent testing (LLM-as-judge validation of architecture, congruence, and alignment)
- Hook-settings bidirectional sync enforcement (hooks ↔ settings templates ↔ manifest)
- HARD GATE enforcement patterns for pipeline quality (test gate, anti-stubbing, hook registration)
- Training pipeline utilities (data curation, quality validation, distributed training coordination)

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

### Enforcement Patterns

**HARD GATE pattern** — Proven through #206 (test gate), #310 (anti-stubbing), #348 (hook registration):

Advisory text ("please ensure...") gets ignored under context pressure. What works:
1. **Explicit FORBIDDEN list** — Name the specific bad behaviors
2. **Required actions** — Name the specific resolution options (fix, skip with reason, adjust)
3. **Gate position** — Place between work step and validation step (can't proceed until gate passes)

**Operational wiring rule** — Every infrastructure component (hook, agent, command) must have:
1. **Registration** — Listed in all relevant settings templates and manifests
2. **Wiring test** — Regression test verifying registration, syntax, and no archived references
3. **Documentation** — Entry in the appropriate registry doc

**Archived code rule** — Active code must never import or reference archived components. Archived code lives in `*/archived/` directories and is dead code. If active code needs archived functionality, it must be restored to active status first.

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

### Three-Layer System

**Layer 1: Hook-Based Enforcement** (Automatic, 100% Reliable)
- Hooks run on every tool call, commit, and prompt submission
- Enforces: PROJECT.md alignment, security, tests, docs, file organization
- Blocks operations if violations detected
- **Guaranteed execution** — hooks fire on every event, no opt-out

**Layer 2: Agent-Based Intelligence** (User-Invoked, AI-Enhanced)
- User invokes `/implement` for AI assistance
- Claude coordinates specialist agents through the 8-step pipeline
- Provides intelligent guidance and implementation help
- **Conditional execution** — Claude decides which agents based on complexity

**Layer 3: Continuous Improvement Loop** (Post-Session, Self-Correcting)
- `session_activity_logger.py` (PostToolUse hook) logs every tool call as structured JSONL
- `continuous-improvement-analyst` agent reads logs and detects: workflow bypasses, test drift, doc staleness, hook false positives, congruence violations
- `/improve` command triggers analysis and optionally auto-files GitHub issues
- **Asynchronous** — runs post-session, never blocks active work

**Key Distinctions:**
- **Hooks = enforcement** (quality gates, always active, blocking)
- **Agents = intelligence** (expert assistance, conditionally invoked, advisory)
- **Continuous improvement = learning** (post-hoc analysis, drift detection, issue filing)

### Hook Lifecycle Events

Four event types drive Layer 1 enforcement:

| Event | When | Purpose |
|-------|------|---------|
| **PreToolUse** | Before any tool executes | MCP security, workflow enforcement, tool auto-approval |
| **PostToolUse** | After any tool executes | Activity logging, quality gate checks |
| **UserPromptSubmit** | When user sends a message | Session state, prompt validation |
| **SubagentStop** | When a subagent completes | Pipeline orchestration |

Each hook in settings templates binds to one event via the `matcher` field (tool name or `*` for all).

### Agent Pipeline

```
/implement "feature"
     ↓
PROJECT.md Alignment Check (blocks if misaligned)
     ↓
┌───────────────┬───────────────┐
│ Research-Local │ Research-Web  │  ← Parallel research
│ (Haiku)        │ (Haiku)       │
└───────────────┴───────────────┘
     ↓
Planning (Opus)
     ↓
TDD Tests (Opus)
     ↓
Implementation (Opus) → HARD GATE: 0 test failures
     ↓                → HARD GATE: No stubs/placeholders
     ↓                → HARD GATE: Hook registration verified
     ↓
┌──────────┬────────────┬───────────┐
│ Review   │ Security   │ Docs      │  ← Parallel validation
│ (Sonnet) │ (Opus)     │ (Haiku)   │
└──────────┴────────────┴───────────┘
     ↓
Git Operations (commit, push, PR)
```

**Model Tiers:**
- **Opus**: Complex reasoning — planner, test-master, implementer, security-auditor
- **Sonnet**: Balanced — reviewer, researcher (web)
- **Haiku**: Fast/cheap — researcher-local, doc-master

### Diamond Testing Model

Six-layer testing strategy — deterministic hard floor (bottom), semantic acceptance criteria (top), generated/probabilistic middle:

```
     /  Acceptance Criteria  \     Human-defined, LLM-as-judge evaluated
    / LLM-as-Judge Eval Layer \    Probabilistic, ~85% human agreement
   / Integration & Contract    \   Generated from acceptance criteria
   \ Property-Based Invariants /   "Hook must always exit", manifest sync
    \ Deterministic Unit Tests/    Regression locks (smoke, unit, progression)
     \  Type System / Lints  /     Hard floor, zero tolerance
```

**Key layers**:
- **Bottom (deterministic)**: Lints, type checks, unit tests, smoke tests — CI gate, every commit
- **Middle (generated)**: Integration tests, property invariants — generated from acceptance criteria
- **Top (semantic)**: `tests/genai/` LLM-as-judge + acceptance criteria — validate intent, not implementation

**Principle**: Traditional tests lock in *behavior* (regression prevention). GenAI tests validate *intent and alignment* (drift detection). Acceptance criteria define *done* (specification). Each layer serves a different purpose — unit tests are regression locks, not specifications.

See [docs/TESTING-STRATEGY.md](docs/TESTING-STRATEGY.md) for full model with data citations.

### Repository Structure

```
autonomous-dev/
├── plugins/autonomous-dev/     # Plugin source (what users install)
│   ├── agents/                 # Pipeline + utility agents
│   ├── commands/               # Slash commands
│   ├── hooks/                  # Automation hooks (17 active, 62 archived)
│   ├── skills/                 # Skill packages
│   ├── lib/                    # Python libraries
│   ├── templates/              # Settings templates (7 project, 1 global)
│   └── docs/                   # User documentation
├── docs/                       # Developer documentation
├── tests/                      # Test suite (~9,700 tests)
│   ├── unit/                   # Unit tests
│   ├── regression/             # Smoke + progression regression tests
│   └── genai/                  # GenAI intent tests (LLM-as-judge)
├── .claude/                    # Installed plugin (symlink)
├── CLAUDE.md                   # Development instructions (component counts live here)
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
- Installs global infrastructure (hooks, libs)
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
