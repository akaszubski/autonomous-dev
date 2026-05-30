# autonomous-dev — A Development Harness for Claude Code

![Version](https://img.shields.io/badge/version-3.51.0-blue)

**A harness that wraps Claude Code with enforcement, specialist agents, and alignment gates to deliver consistent, production-grade software engineering outcomes.**

A *harness* is the software and structure that wraps an AI model to keep it on track — the prompts, tools, feedback loops, constraints, and validation that turn a capable but undisciplined model into a reliable system. Without a harness, the model is a wild horse with raw power but no direction. With one, that power is controlled, directed, and accountable.

---

## What Is This?

**The problem**: Claude Code is brilliant at execution but unreliable at process. It skips tests, declares "good enough" on failing code, bypasses security reviews, and drifts from your project's intent. Not out of malice — it's trained to complete tasks, not follow engineering discipline. Prompt-level instructions ("please run tests") get ignored under context pressure.

**The solution**: autonomous-dev is a harness that enforces the full software development lifecycle:

1. **You define your project** in a file called PROJECT.md - your goals, what's in/out of scope, constraints, architecture
2. **You track work in GitHub Issues** - each feature or bug is an issue
3. **You run one command** - `/implement "#72"`
4. **Claude executes a full development pipeline** - research, planning, acceptance tests, implementation, code review, security scan, documentation
5. **Claude stays aligned** - if a feature doesn't fit your PROJECT.md scope, it's blocked before any code is written

**In short**: You define the rules once. The harness enforces them for every feature.

---

## What Does It Actually Do?

When you type `/implement "#72"`, Claude coordinates specialist agents through a multi-stage pipeline:

| Step | Agent | What It Does |
|------|-------|--------------|
| 1 | **alignment check** | Checks if the feature fits your PROJECT.md goals and scope. Blocks if it doesn't. |
| 2 | **researcher** (x2) | Searches codebase + web for patterns, best practices, existing solutions |
| 3 | **planner** | Designs the architecture and creates a file-by-file implementation plan |
| 3.5 | **plan-critic** | Adversarial review across 6 axes (assumption audit, scope creep, existing solutions, minimalism, uncertainty, operational integration test). Iterates planner until verdict is PROCEED. |
| 4 | **acceptance tests** | Writes acceptance tests that define what "done" means |
| 5 | **implementer** | Writes code + unit tests to make the acceptance tests pass |
| 5.5 | **plan-implementation alignment gate** | Compares planned files vs implemented files. Blocks on >50% divergence. |
| 6 | **spec-validator** | Spec-blind behavioral validation — writes tests from acceptance criteria *without seeing* the implementation, then validates against it |
| 7 | **reviewer** | Reviews code quality across 6 dimensions (correctness, tests, security, performance, maintainability, observability) |
| 8 | **security-auditor** | Scans for vulnerabilities (OWASP top 10, 29 security-sensitive path patterns) |
| 9 | **doc-master** | Updates documentation to match the new code |

After all agents complete:
- Code is committed with a descriptive message
- Changes are pushed to your branch
- The GitHub issue is closed with a summary
- A continuous improvement analyst examines the session for drift, bypasses, and pipeline health

**One command. Full software development lifecycle. Aligned to your project.**

---

## Why Use This?

**Without a harness**:
- You ask Claude to build a feature
- Claude makes assumptions about your architecture
- It skips tests when context gets long (context anxiety)
- It approves its own work as "good enough" (poor self-evaluation)
- You review the code, find issues, ask for fixes
- Repeat until it's acceptable
- Hope you didn't introduce security issues

**With autonomous-dev**:
- You define your project once (PROJECT.md)
- You create a GitHub issue for each feature
- You run `/implement "#X"`
- The harness enforces every step — research, planning, testing, implementation, adversarial review, security audit, documentation
- You review a complete, tested, documented, security-scanned result

**The difference**: Claude stops guessing. The harness keeps it honest.

### Three-Layer Harness Architecture

autonomous-dev enforces process through three layers, each addressing a different failure mode:

- **Hooks** (deterministic enforcement) — Run on every tool call, commit, and prompt. Hard gates that can't be argued with: tests must pass with 0 failures before code review starts, no stubs or placeholders allowed, security scan is mandatory, documentation must stay in sync. These are the harness equivalent of guardrails — if the model tries to skip a step, it's physically blocked.

- **Agents** (adversarial evaluation) — Each pipeline step is handled by a specialist agent with a specific job and constrained tools. Critically, the implementer never reviews its own work — a separate reviewer agent with a skeptical mandate evaluates it. This follows the generator/evaluator pattern: the tension between agents improves quality, just like a GAN network. No single agent can skip steps or self-approve.

- **Skills** (progressive context injection) — Instead of stuffing the context window with every rule upfront (which causes context anxiety and drift), skills inject domain knowledge only when relevant. Testing standards load during test writing. Security patterns load during security review. This keeps Claude focused within its current step.

**The result**: Every feature goes through every step. Not because Claude remembers to, but because the harness won't let it skip.

### Recent Improvements

Substantial enforcement hardening shipped recently. Current focus areas:

- **Planning workflow** — 7-step `/plan` + adversarial `plan-critic` review (1-5 Likert across 6 axes, composite ≥3.0 → PROCEED)
- **Iterative refinement** — Self-Refine pattern integrated into `/implement`, `/advise`, `/refactor`
- **Pipeline ordering** — Deterministic sequencing; `reviewer → security-auditor` always sequential on security-sensitive changes
- **Session analytics** — Every conversation archived to `~/.claude/archive/` with 17-column SQLite index
- **Prompt quality gate** — Write-time enforcement on `agents/*.md` and `commands/*.md` (PRISM-validated anti-patterns blocked)
- **Closed-loop self-improvement** — Benchmark → modify → re-benchmark → commit-or-revert (see [EVALUATION.md](docs/EVALUATION.md))

See [CHANGELOG.md](CHANGELOG.md) for complete release-over-release details with issue references.

### The 12 Elements of Harness Engineering

The core insight of harness engineering: reliability in multi-step AI workflows is difficult because failures compound. A 10-step process with 90% accuracy per step fails over 60% of the time. "Agent skills" that are just prompts or markdown files — where you *hope* the AI follows instructions — lack the dependability required for production work.

The solution is **deterministic rails**: a software layer that gates and validates every stage. autonomous-dev implements all 12 elements of this framework:

| # | Element | How autonomous-dev implements it |
|---|---------|----------------------------------|
| 1 | **State Machine** | `pipeline_state.py` — 13-phase state machine with `Step` enum, `advance()`/`complete_step()` API, JSON-persisted state |
| 2 | **Validation Loops** | STEP 8 HARD GATE — runs pytest, loops until 0 failures/0 errors. Anti-stubbing gate blocks `raise NotImplementedError()` shortcuts |
| 3 | **Isolated Sub-Agents** | Specialist agents, each spawned with fresh context and constrained tools. Model selection per agent (Haiku/Sonnet/Opus) |
| 4 | **Virtual File System** | Git worktree isolation for batch mode. `checkpoint.py` + `artifacts.py` persist outputs to `.claude/artifacts/` per phase |
| 5 | **Human-in-the-Loop** | Plan mode (STEP 5) requires user approval before implementation. `pause_controller.py` for explicit gates |
| 6 | **Hook Enforcement** | 27 hooks with JSON `{"decision": "block"}` hard gates — not prompt-level nudges. Research-confirmed: nudges produce unreliable compliance. Includes `plan_gate.py` (blocks complex Write/Edit without validated plan) and Layer 6 prompt quality gate (blocks anti-pattern prompts to `agents/*.md` and `commands/*.md`) |
| 7 | **State Persistence** | `CheckpointManager` for resume after failure. `batch_state_manager.py` for multi-feature recovery. `/implement --resume` |
| 8 | **Context Management** | Progressive skill injection loads domain knowledge per-step. `/clear` between features. Agent isolation prevents context rot |
| 9 | **Deterministic Ordering** | `agent_ordering_gate.py` enforces pipeline sequence. "You MUST NOT run STEP 10 before STEP 8 test gate passes" |
| 10 | **Output Validation** | Parallel reviewer + security-auditor in STEP 10. `genai_validate.py` for LLM-as-judge tests. `completion_verifier.py` |
| 11 | **Observability** | `session_activity_logger.py`, `conversation_archiver.py`, `pipeline_timing_analyzer.py`. Structured JSONL + SQLite for long-term analytics |
| 12 | **Error Recovery** | `failure_analyzer.py`, `batch_retry_manager.py`, `stuck_detector.py`, `qa_self_healer.py`. Automatic retry with consent |

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

When you run `/implement "Add user registration"`:
- Allowed - user registration is IN scope
- Claude follows your FastAPI + PostgreSQL + JWT constraints
- Tests go in `tests/`, code follows your architecture

When you run `/implement "Add analytics dashboard"`:
- Blocked - analytics is OUT of scope
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

### One-Line Install

```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

Then **fully quit Claude Code** (Cmd+Q on Mac, Ctrl+Q on Windows/Linux) and reopen it.

### Set Up Your Project

**Open your project folder in terminal**, then start Claude Code:
```bash
cd /path/to/your/project
claude
```

Run the setup wizard:
```
/setup
```

This will walk you through creating PROJECT.md and configuring the plugin for your project.

For existing projects, use:
```
/align --retrofit
```

### Update

```bash
/sync
```

### Uninstall

Two paths — pick the one that matches your situation:

```bash
# Normal uninstall (Claude Code still works)
/sync --uninstall

# Shell-only uninstall (Claude Code is broken, hooks are bricked, or /sync itself fails)
bash install.sh --uninstall            # removes hooks and global registration
bash install.sh --uninstall --dry-run  # preview first
bash install.sh --uninstall --repos "/path/to/repo1,/path/to/repo2"  # also clean per-repo settings
```

See [TROUBLESHOOTING.md](plugins/autonomous-dev/docs/TROUBLESHOOTING.md#uninstalling-autonomous-dev) for the full comparison table and rollback instructions.

---

## Usage

### Single Feature

```bash
/implement "#72"              # From GitHub issue
/implement "Add user auth"    # From description
```

### Pipeline Modes

```bash
/implement "#72"              # Full pipeline (default) - acceptance-first
/implement --light "#72"      # Light pipeline - docs/config/simple changes
/implement --tdd-first "#72"  # TDD-first - unit tests before implementation
/implement --fix "#72"        # Fix mode - root-cause analysis HARD GATE for bug fixes
```

### Planning Workflow

Use `/plan` for changes touching >3 files, >100 lines, or with uncertain approach. The 7-step planning process is enforced by `plan_gate.py` (blocks complex Write/Edit without a validated plan in `.claude/plans/`).

```bash
/plan "Add OAuth login"       # 7-step structured planning + iterative plan-critic
/plan --no-issues "..."       # Skip auto-creation of GitHub issues
/plan-to-issues               # Thorough-mode fallback for batch issue creation
```

The `/plan` flow: problem statement → existing solutions search → minimal path → adversarial critique by plan-critic (1-5 Likert score across 6 axes, iterates planner until composite ≥3.0) → on PROCEED, automatically creates GitHub issues when ≥2 independent work items exist. See [docs/PLANNING-WORKFLOW.md](docs/PLANNING-WORKFLOW.md).

### Plan-exit enforcement is scoped to autonomous-dev projects (since #938)

When deployed user-globally, the plan-exit hooks (`plan_mode_exit_detector.py`,
`unified_pre_tool.py`) fire only inside autonomous-dev projects (detected via
`repo_detector.is_autonomous_dev_repo`). In foreign projects they silently no-op.

Three escape hatches exist (any one bypasses):

- **`/implement --skip-review`** — one-shot, plan-only. Best for ad-hoc cases.
- **`export AUTONOMOUS_DEV_SKIP_PLAN_REVIEW=1`** — persistent across sessions and
  shells. Recommended for users who want plan-critic permanently disabled.
- **`touch .claude/SKIP_PLAN_REVIEW`** — local sentinel file. **Note:** this file
  is gitignored (covered by `.claude/*`) and is therefore not committed; it is
  lost on `git clean -fdx` or fresh clone. Use the env var for cross-session
  persistence.

To re-enable enforcement in foreign projects: `export AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT=1`.
The escape hatches above still win over global enforcement.

**Universal hook bypass** (Issue #969): if any hook is blocking and you cannot run
a slash command to unstick it, set `AUTONOMOUS_DEV_BYPASS=1` or `touch .claude/.bypass`
— every hook honors this and falls through to allow with a logged audit trail.
See [docs/TROUBLESHOOTING.md](plugins/autonomous-dev/docs/TROUBLESHOOTING.md#universal-escape-unstick-any-blocked-hook-issue-969).

### Batch Processing

```bash
/implement --issues 72 73 74 75    # Multiple GitHub issues with worktree isolation
/implement --batch backlog.txt     # From a file (one feature per line)
/implement --resume <batch-id>     # Resume after context reset
```

### Project Management

```bash
/plan "..."              # 7-step planning workflow with adversarial plan-critic
/status                  # View PROJECT.md goal progress
/align                   # Check alignment (--project, --docs, --retrofit, --content)
/create-issue "..."      # Create GitHub issue with automated research
/plan-to-issues          # Thorough-mode batch issue creation from plan output
/health-check            # Verify plugin installation
```

### Quality & Analysis

```bash
/refactor                # Code, docs, and test optimization (--tests, --docs, --docs-redundancy, --code, --fix)
/sweep                   # Quick codebase hygiene (alias for /refactor --quick); --tests for AST-based test pruning analysis
/audit                   # Quality audit (--quick, --security, --docs, --code, --tests)
/skill-eval              # Measure skill effectiveness via behavioral delta scoring (--quick, --skill, --update)
/advise                  # Critical thinking analysis
/improve                 # Automation health analysis (--auto-file to create GitHub issues)
/retrospective           # Session drift detection and alignment updates
/autoresearch            # Autonomous experiment loop — hypothesize, modify, benchmark, commit or revert
```

### Other Commands

```bash
/sync                    # Update plugin (--github, --env, --marketplace, --all)
/worktree                # Git worktrees (--list, --status, --merge, --discard)
/scaffold-genai-uat      # Scaffold LLM-as-judge tests into any repo
/mem-search              # Search claude-mem persistent memory
/triage --auto-improvement  # Cluster open auto-improvement issues by root cause; emit ranked work queue (periodic)
```

---

## How the Harness Works

### Generator / Evaluator Pipeline

Inspired by the adversarial evaluation pattern (generator creates, evaluator judges), every `/implement` runs this pipeline:

```
/implement "feature"
     |
PROJECT.md Alignment Check (blocks if misaligned)
     |
Research Self-Critique (inline FEEDBACK pass, Self-Refine pattern)
     |
+------------------+------------------+
| Research-Local   | Research-Web     |  <- Parallel research
| (Haiku)          | (Sonnet)         |
+------------------+------------------+
     |
Planning (Opus)
     |
Plan Validation Gate (plan-critic, Opus)  <- HARD GATE: adversarial review
     |                                       6 axes, ≥3.0 composite to PROCEED
     |                                       REVISE re-invokes planner
     |
Acceptance Tests (test-master)            <- Acceptance-first (default)
     |                                       or TDD-first (--tdd-first)
Implementation (Opus)            -> HARD GATE: 0 test failures
     |                           -> HARD GATE: No stubs/placeholders
     |                           -> HARD GATE: Root cause analysis (--fix)
     |                           -> HARD GATE: Hook registration verified
     |
Plan-Implementation Alignment Gate -> HARD GATE: planned vs diff files
     |                               (blocks on >50% divergence)
     |
Spec-Blind Validation (spec-validator) <- HARD GATE: behavioral tests
     |                                    from criteria only, no impl
     |
+----------+------------+-----------+
| Review   | Security   | Docs      |  <- Parallel for low-risk,
| (Sonnet) | (Sonnet)   | (Sonnet)  |     sequential for security-sensitive
+----------+------------+-----------+
     |
Remediation Gate (max 2 cycles on findings)
     |
Git Operations (commit, push, close issue)
     |
Agent Completeness Gate (blocks commit if required agents missing)
     |
Continuous Improvement (background analysis)
     |
Session Archive (transcript + SQLite index)
```

### PROJECT.md Alignment

Features validate against your PROJECT.md before work starts. If you request something OUT of scope, it's blocked - not implemented wrong.

### Testing: The Diamond Model

autonomous-dev uses a **diamond testing model** — not the traditional TDD pyramid. The key insight: with agent-speed code generation, acceptance criteria are the cheapest form of meaningful specification. Unit tests generated by agents are useful as regression locks but poor as specifications — agents game them.

```
     /  Acceptance Criteria  \     Human-defined, LLM-as-judge evaluated
    / LLM-as-Judge Eval Layer \    Probabilistic, ~80-90% human agreement
   / Integration & Contract    \   Generated from acceptance criteria
   \ Property-Based Invariants /   "Output must be valid JSON", etc.
    \ Deterministic Unit Tests/    Generated by agent, constrained by above
     \  Type System / Lints  /     Hard floor, zero tolerance
```

**What changed from TDD**:
- **Acceptance criteria drive everything** — defined before implementation, not unit tests
- **Unit tests are regression locks**, not specifications — they prevent drift, they don't define correctness
- **LLM-as-judge evaluation** validates semantic intent (~85% human agreement, `tests/genai/`)
- **Property-based invariants** catch bugs unit tests miss (+23-37% pass@1, `tests/property/`)
- **Spec-blind validation** — a separate agent writes behavioral tests from acceptance criteria *without seeing the implementation*, then validates against it (STEP 8.5 HARD GATE)

The pipeline default is acceptance-first (`/implement "#X"`). Legacy TDD-first is available via `--tdd-first`. See [Testing Strategy](docs/TESTING-STRATEGY.md) for the full 6-layer model with research citations.

### Context Management

As the context window fills up, models exhibit *context anxiety* — they rush through steps, declare things done prematurely, and degrade output quality. autonomous-dev handles this with context resets between features:

1. Each feature uses ~25-35K tokens
2. After 4-5 features, run `/clear` to reset context
3. Run `/implement --resume <batch-id>` to continue from where you left off

Batch processing handles this automatically with worktree isolation and checkpoint/resume.

### Session Analytics & Self-Improvement

autonomous-dev doesn't just run pipelines — it learns from them.

**Long-term session analytics**: Every conversation is archived to `~/.claude/archive/` with full transcripts and a 17-column SQLite index (per-session tokens, cache hit rates, tool calls, model, per-repo attribution). See [docs/SESSION-ANALYTICS.md](docs/SESSION-ANALYTICS.md) for schema + queries.

```sql
sqlite3 ~/.claude/archive/sessions.db \
  "SELECT project, COUNT(*) sessions,
          SUM(total_output_tokens) out_tok, SUM(cache_read_tokens) cache_read
   FROM sessions GROUP BY project ORDER BY out_tok DESC;"
```

**Closed-loop improvement**: The system detects its own weaknesses and fixes them. See [docs/EVALUATION.md](docs/EVALUATION.md) for the full measurement surface (skill-eval, reviewer benchmark, /improve workflow, autoresearch).

```
pipeline runs → session logs → /improve detects drift → files GitHub issues
     ↓                                                        ↓
/autoresearch picks up issues → hypothesize → modify → benchmark → deploy if better
     ↑                                                              ↓
     └──────────────────────────────────────────────────────────────┘
```

- `/improve` analyzes recent sessions for bypasses, test drift, and pipeline degradation — auto-files issues
- `/autoresearch` runs autonomous experiments: modifies agent prompts, benchmarks the change, commits if it improves quality or reverts if it doesn't
- `/retrospective` detects intent evolution and proposes alignment updates
- `/skill-eval` measures whether skill injections actually change agent behavior (behavioral delta scoring)

**The result**: The harness gets better every week without anyone thinking about it.

---

## What You Get

| Component | Count | Purpose |
|-----------|-------|---------|
| Commands | 24 | Slash commands for workflows |
| Agents | 16 | Specialized AI for each SDLC stage (added: plan-critic) |
| Skills | 19 | Domain knowledge (added: planning-workflow, prompt-engineering) |
| Hooks | 30 | Automatic validation and enforcement (added: plan_gate, conversation_archiver, prompt quality gate) |
| Libraries | 210 | Python utilities |

---

## Documentation

### Core Concepts
- [Architecture](docs/ARCHITECTURE-OVERVIEW.md) - Three-layer system (hooks + agents + continuous improvement)
- [Harness Evolution](docs/HARNESS-EVOLUTION.md) - How the harness has evolved across releases
- [Maintaining Philosophy](docs/MAINTAINING-PHILOSOPHY.md) - Why alignment-first works
- [Model Behavior Notes](docs/model-behavior-notes.md) - Production-validated patterns for prompt design

### Workflows
- [Planning Workflow](docs/PLANNING-WORKFLOW.md) - 7-step `/plan` + plan-critic adversarial review
- [Pipeline Modes](docs/PIPELINE-MODES.md) - `/implement` mode matrix (full / light / fix / batch) with per-mode agent sets
- [Batch Processing](docs/BATCH-PROCESSING.md) - Multi-feature workflows with worktree isolation
- [Git Automation](docs/GIT-AUTOMATION.md) - Auto-commit, push, issue close
- [Workflow Discipline](docs/WORKFLOW-DISCIPLINE.md) - Pipeline ordering enforcement (two-tier)

### Observability & Self-Improvement
- [Session Analytics](docs/SESSION-ANALYTICS.md) - sessions.db schema, archive layout, query recipes
- [Evaluation](docs/EVALUATION.md) - Skill-eval, reviewer benchmark, the closed-loop self-improvement cycle

### Prompt & Agent Design
- [Prompt Engineering](docs/PROMPT-ENGINEERING.md) - Constraint budgets (MOSAIC), register shifting, HARD GATE patterns
- [Agents Reference](docs/AGENTS.md) - All 16 specialist agents with model tiers
- [Skills Reference](docs/SKILLS.md) - All 19 progressive skill packages with trigger conditions

### Testing
- [Testing Strategy](docs/TESTING-STRATEGY.md) - Diamond testing model (acceptance-first, 6 layers)
- [GenAI Tests](tests/genai/) - LLM-as-judge semantic validation
- [Property Tests](tests/property/) - Hypothesis-based invariants
- [Spec Validation](tests/spec_validation/) - Spec-blind behavioral tests

### Reference
- [Commands](plugins/autonomous-dev/commands/) - All 24 commands
- [Hooks](docs/HOOKS.md) - 31 active hooks
- [Hook Registry](docs/HOOK-REGISTRY.md) - Sidecar metadata schema
- [Libraries](docs/LIBRARIES.md) - 210 Python utilities
- [Scripts](docs/SCRIPTS.md) - Operational tooling (deploy, validate, benchmark, mine)
- [Label Taxonomy](docs/LABEL-TAXONOMY.md) - GitHub labels + `[BYPASS]`/`[INCOMPLETE]`/`[ORDERING]` finding tags

### Security
- [Sandboxing](docs/SANDBOXING.md) - Command classification and shell injection detection
- [MCP Architecture](docs/MCP-ARCHITECTURE.md) - Per-repo `.mcp.json` default, token-bleed prevention, migration helper
- [MCP Security](docs/MCP-SECURITY.md) - Path traversal, command injection, SSRF prevention
- [Security Audit](docs/SECURITY.md) - Security scanning architecture

### Troubleshooting
- [Troubleshooting Guide](plugins/autonomous-dev/docs/TROUBLESHOOTING.md) - Common issues

---

## Quick Reference

```bash
# Install
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
# Restart Claude Code (Cmd+Q / Ctrl+Q)

# Daily workflow
/implement "#72"                    # Single feature
/implement --issues 1 2 3           # Multiple features
/implement --fix "#99"              # Fix a failing test
/clear                              # Reset context between features

# Check status
/health-check                       # Verify installation
/status                             # View alignment

# Update
/sync                               # Get latest version
```

---

## Support

- **Issues**: [github.com/akaszubski/autonomous-dev/issues](https://github.com/akaszubski/autonomous-dev/issues)
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)

---

## License

MIT License
