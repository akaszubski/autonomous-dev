# Project Context - Autonomous Development Plugin

**Last Updated**: 2026-03-28
**Version**: v3.51.0

---

## GOALS

**Mission**: Make Claude Code CLI follow the full software development lifecycle — requirements, architecture, coding, testing, review, security, documentation, deployment — with the discipline of a senior engineering team.

**Why this exists**: Claude is trained as a generalist to get things done. It executes brilliantly but lacks judgment about *what* to do, *when*, and *why*. It will skip tests, bypass process, and drift from intent — not out of malice, but because its training optimizes for immediate completion, not sustainable engineering.

CLAUDE.md instructions drift under context pressure. Prompts get ignored. The context window is finite and the world is bigger than the window. You cannot teach judgment through rules — rules say "always do X" while judgment says "it depends."

autonomous-dev compensates by enforcing process through hooks (deterministic, can't be argued with) and injecting the right context at the right time (PROJECT.md, GitHub issues, research). The system doesn't replace human judgment — it ensures Claude follows the SDLC steps where human judgment has already determined what "good" looks like.

**The core tension**: Enforcement works but is expensive in tokens. Every session re-teaches fundamentals through context that should be native. This is a known cost, not a design flaw — it's the price of working with a generalist model that doesn't yet carry domain judgment in its weights.

autonomous-dev provides **macro alignment with micro flexibility**:

- **Macro**: PROJECT.md defines goals, scope, constraints — Claude checks alignment before every feature
- **Micro**: Claude can still improve the implementation when it finds better patterns

**What success looks like**:

```
research → plan → test → implement → review → security → docs → commit
                                                                    ↓
                                              session logs → analysis → issues
                                                                    ↓
                                         measure → diagnose → fix → verify
                                            ↑                         ↓
                                            └─────────────────────────┘
```

Every step. Every feature. Documentation, tests, and code stay in sync automatically. The system learns from its own sessions, measures its own effectiveness, diagnoses its own weaknesses, and improves its own prompts — verified by benchmarks before deployment.

```bash
/implement "issue #72"    # build features with full SDLC
/self-improve             # system improves itself from runtime data
```

**User Intent** (stated 2025-10-26):
> "I speak requirements and Claude Code delivers a first grade software engineering outcome in minutes by following all the necessary steps that would need to be taken in top level software engineering but so much quicker with the use of AI and validation"

**Current Direction** (stated 2026-03-28):
> Building complete autonomous improvements using real-time runtime data as it's used. The system should get better every week without anyone thinking about it.

**Key Points:**
- All SDLC steps required — Research → Plan → Acceptance Tests → Implement → Review → Security → Docs (no shortcuts, diamond testing model)
- Professional quality enforced via hooks (can't skip or bypass)
- Speed via AI — Each step accelerated, not eliminated
- PROJECT.md is the gatekeeper — Work blocked if not aligned
- Continuous improvement — System learns from sessions, detects drift, auto-files issues
- **Self-improvement** — System measures its own effectiveness via benchmarks, diagnoses weaknesses from runtime data, improves its own agent prompts, and verifies improvements before deploying them

---

## SCOPE

**IN Scope** (Features we build):

- Feature request detection and auto-orchestration
- 8-step pipeline: alignment → research → plan → test → implement → validate → verify → git
- PROJECT.md alignment validation before any work begins
- File organization enforcement (src/, tests/, docs/)
- Brownfield project support (`/align --retrofit`)
- Batch processing with crash recovery (`/implement --batch`, `--issues`, `--resume`)
- Automated git operations (commit, push, PR creation)
- MCP security validation and tool auto-approval
- Continuous improvement (session activity logging → drift detection → auto-filed issues)
- GenAI intent testing (LLM-as-judge validation of architecture, congruence, and alignment)
- Hook-settings bidirectional sync enforcement (hooks ↔ settings templates ↔ manifest)
- HARD GATE enforcement patterns for pipeline quality (test gate, anti-stubbing, hook registration, documentation congruence)
- Alignment validation enforcement (strengthening PROJECT.md scope checks beyond advisory text)
- Training pipeline utilities (data curation, quality validation, distributed training coordination)
- Effectiveness benchmarking (labeled datasets of real diffs, balanced accuracy scoring, per-category and per-difficulty measurement of reviewer/agent quality)
- Skill-based standards enforcement (engineering skills as explicit evaluation criteria for pipeline agents, not just documentation)
- Autonomous self-improvement (runtime data aggregation → weakness diagnosis → prompt/skill fixes → benchmark verification → deploy — closed loop, no human in the loop for safe targets)

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
- Acceptance-first testing mandatory (acceptance tests before implementation, unit tests alongside code; use `--tdd-first` for traditional TDD)
- Tool restrictions per agent (principle of least privilege)
- 80% minimum test coverage
- MCP security validation (path traversal, injection prevention)

---

## ARCHITECTURE

### Harness Engineering

autonomous-dev is a **harness** — the software layer that wraps an AI model to keep it on deterministic rails. The core insight: reliability in multi-step AI workflows compounds multiplicatively. A 10-step process with 90% accuracy per step fails over 60% of the time. Prompt-level instructions ("please run tests") produce unreliable compliance (confirmed by research: "LLM Agents Are Hypersensitive to Nudges", 2025).

The harness implements all 12 elements of the harness engineering framework:
1. **State machine** — `pipeline_state.py` tracks 13 phases with advance/complete API
2. **Validation loops** — STEP 8 HARD GATE loops until 0 test failures
3. **Isolated sub-agents** — 14 specialists with fresh context, constrained tools
4. **Virtual file system** — Worktree isolation, `.claude/artifacts/` persistence
5. **Human-in-the-loop** — Plan approval gate before implementation
6. **Hook enforcement** — 25 hooks with JSON `{"decision": "block"}` hard gates
7. **State persistence** — Checkpoint/resume across failures and context resets
8. **Context management** — Progressive skill injection, `/clear` between features
9. **Deterministic ordering** — `agent_ordering_gate.py` enforces step sequence
10. **Output validation** — Parallel reviewer + security-auditor + LLM-as-judge
11. **Observability** — Structured JSONL logging, timing analysis, token tracking
12. **Error recovery** — Failure analysis, automatic retry with consent, stuck detection

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
- All 4 hook layers log structured JSONL to `.claude/logs/activity/`: UserPromptSubmit (command routing), PreToolUse (security), PostToolUse (activity), Stop (output capture)
- `continuous-improvement-analyst` agent evaluates logs against PROJECT.md + CLAUDE.md to test automation quality: hook execution, pipeline completeness, HARD GATE enforcement, command routing, error handling, known/novel bypass detection
- `/improve` command triggers analysis; `--auto-file` creates issues in `akaszubski/autonomous-dev` with label `auto-improvement`
- **Asynchronous** — runs post-session, never blocks active work

**Layer 4: Autonomous Self-Improvement** (Closed-Loop, Evidence-Driven)
- **Measurement**: Effectiveness benchmarks with 146+ labeled samples measure reviewer/agent accuracy per defect category and difficulty tier. Balanced accuracy, FPR, FNR, per-category breakdown tracked over time.
- **Aggregation**: Runtime signals (session logs, benchmark scores, CI findings, auto-improvement issues) consolidated into ranked weakness reports
- **Diagnosis**: Each weakness traced to root cause — specific file, section, missing instruction — with confidence scoring
- **Action**: HIGH confidence diagnoses applied autonomously to agent prompts, skill definitions, and benchmark data. MEDIUM filed as issues. Hooks and core code require human approval.
- **Verification**: Benchmark run before and after every change. Commit if improved, revert if regressed. Baseline updated on success.
- **Scheduling**: Weekly automated cycles via `/self-improve`. Post-change hooks verify agent prompt edits don't regress quality.
- See issues #579-#584 for implementation roadmap.

**Periodic-Aggregation Passes** (Per-Event Automation ↔ Periodic-Aggregation Duality, Issue #1075)

Per-event automations (doc-master in /implement, CIA in /implement, baseline capture at STEP 1) work well in isolation but each has an unfilled counterpart need: a periodic full-state pass that aggregates across many events. The shape is consistent:

| Per-event automation | Periodic-aggregation pass |
|---|---|
| doc-master per commit (changed-files scope only) | `/refactor --docs` — narrative-doc sweep |
| Test-baseline per session (per-pipeline only) | Machine-readable baseline snapshot across sessions |
| CIA per session (one issue at a time) | Triage pass — root-cause grouping of accumulated `auto-improvement` queue |

A periodic-aggregation pass:
- Runs at maintainer cadence (weekly/monthly), not per-commit.
- Reads accumulated state from prior events.
- Identifies gaps, duplicates, dependencies, drift that per-event scope cannot see.
- Outputs either **updates** (docs reconciled in place) or a **ranked work queue** (triaged issues, baseline snapshot).

This is the architectural layer that catches drift no per-event hook can see — by design, per-event automations have a single-commit blast radius. Periodic passes are additive: they do not replace or modify per-event hooks. Implementations land incrementally — pick one, generalize the pattern, then port to the other variants.

**Key Distinctions:**
- **Hooks = enforcement** (quality gates, always active, blocking)
- **Agents = intelligence** (expert assistance, conditionally invoked, advisory)
- **Continuous improvement = learning** (post-hoc analysis, drift detection, issue filing)
- **Self-improvement = evolution** (autonomous measurement, diagnosis, fix, verification — closed loop)
- **Periodic-aggregation = visibility** (cross-event sweeps that catch what per-event scope misses)

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
Acceptance Tests (Coordinator)  ← Default mode (--tdd-first: TDD Tests via Opus)
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

**Model Tiers** (from implement.md, the source of truth):
- **Opus**: Complex reasoning — planner, test-master, implementer, security-auditor
- **Sonnet**: Balanced — reviewer, researcher (web), continuous-improvement-analyst
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
│   ├── templates/              # Settings templates (6 variants)
│   └── docs/                   # User documentation
├── docs/                       # Developer documentation
├── tests/                      # Test suite (~8,200 runnable, ~10,500 defined)
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   ├── regression/             # Smoke + progression regression tests
│   ├── security/               # Security-focused tests
│   ├── hooks/                  # Hook-specific tests
│   └── genai/                  # GenAI prompt quality tests (LLM-as-judge)
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
