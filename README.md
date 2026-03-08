# autonomous-dev

**8-Agent SDLC Pipeline for Claude Code**

Transform feature implementation into an automated, quality-enforced workflow. One command runs research → plan → test → implement → review → security → docs → git automation.

[![Version](https://img.shields.io/badge/version-3.50.0-blue.svg)](plugins/autonomous-dev/VERSION)
[![Pipeline](https://img.shields.io/badge/pipeline-8_agents-green.svg)](docs/AGENTS.md)
[![Skills](https://img.shields.io/badge/skills-active-orange.svg)](docs/ARCHITECTURE-OVERVIEW.md)
[![Hooks](https://img.shields.io/badge/hooks-active-purple.svg)](docs/HOOKS.md)
[![Commands](https://img.shields.io/badge/commands-active-blue.svg)](docs/ARCHITECTURE-OVERVIEW.md)

---

## The Problem

AI coding assistants are powerful, but they drift. They build features you didn't ask for. They ignore your architecture. They forget your constraints.

Without guardrails, you get:
- **Scope creep** — Features that don't align with project goals
- **Untested code** — No TDD enforcement means bugs ship to production
- **Security gaps** — No automated OWASP auditing
- **Documentation drift** — Docs that don't match code

---

## The Solution: Intent-Aligned Development

autonomous-dev keeps AI aligned to YOUR intent. Every feature validates against your project's strategic goals before a single line of code is written.

### PROJECT.md-First Development

Define your intent once. Enforce it automatically.

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

## ARCHITECTURE
- REST API with JWT tokens
- PostgreSQL for persistence
```

Every `/implement` command validates:
- Does this feature align with **GOALS**?
- Is it within **SCOPE**?
- Does it violate **CONSTRAINTS**?
- Does it follow **ARCHITECTURE**?

**Result**: The AI builds what you actually want, not what it thinks you want.

---

## What Changes

| Without Pipeline | With `/implement` |
|-----------------|-------------------|
| Manual scope review | **Automatic PROJECT.md alignment validation** |
| Tests written after (or never) | **Specification-driven tests first, always** |
| Security checked manually | **OWASP scan on every feature** |
| Docs updated "later" | **Doc-master syncs on every feature** |
| Hope-based quality | **Hook-enforced quality gates** |

---

## Quick Start

```bash
# Install via bootstrap script (required — sets up global hooks, libs, config)
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)

# First install: Restart Claude Code (Cmd+Q / Ctrl+Q)
# Subsequent updates: /sync then /reload-plugins (reloads commands, agents, skills)
# Note: /reload-plugins does NOT reload hooks or settings — use full restart for those
/setup  # Guided PROJECT.md creation
```

---

## How It Works

### One Command, Full Pipeline

```bash
/implement Add user authentication with JWT tokens
```

autonomous-dev orchestrates **8 specialized AI agents** in sequence:

```
STEP 1: Alignment     → Validates against PROJECT.md goals
STEP 2: Research      → Finds existing patterns in your codebase
STEP 3: Planning      → Designs the architecture
STEP 4: Acceptance Tests → Writes specification-driven tests (acceptance-first default)
STEP 5: Implementation → Implements code with regression tests
STEP 6: Parallel Validation (3 agents simultaneously):
        ├── Code Review    → Checks quality and patterns
        ├── Security Audit → Scans for OWASP vulnerabilities
        └── Documentation  → Keeps docs in sync
STEP 7: Git Automation → Commit, push, PR, close issue
```

**Result**: Production-ready code in 15-25 minutes.

---

## Key Commands

| Command | Purpose |
|---------|---------|
| `/setup` | Interactive PROJECT.md creation wizard |
| `/implement` | Full pipeline: align, research, plan, test, implement, review, secure, document |
| `/implement --quick` | Fast mode: implementer agent only (2-5 min) |
| `/implement --batch` | Process multiple features from file |
| `/implement --issues 1 2 3` | Process features from GitHub issues |
| `/implement --resume` | Continue interrupted batch |
| `/align` | Validate alignment (project goals, CLAUDE.md, retrofit) |
| `/create-issue` | Research-backed GitHub issues with duplicate detection |
| `/advise` | Critical analysis before major decisions |
| `/audit` | Quality audit (--quick, --security, --docs, --code, --claude, --tests) |
| `/health-check` | Validate all plugin components (agents, hooks, commands) |
| `/sync` | Update plugin (--github, --env, --marketplace, --all, --uninstall) |
| `/worktree` | Manage git worktrees (--list, --status, --merge, --discard) |
| `/improve` | Analyze sessions for pipeline enforcement, bypasses, automation health |
| `/scaffold-genai-uat` | Scaffold LLM-as-judge tests into any repo |
| `/status` | View PROJECT.md goal progress with recommendations |
| `/mem-search` | Search claude-mem persistent memory (optional) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      /implement Pipeline                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   alignment → researcher → planner → test-master → implementer  │
│                                          ↓                       │
│                    ┌─────────────────────┴─────────────────────┐│
│                    │         Parallel Validation               ││
│                    │  reviewer + security-auditor + doc-master ││
│                    │           (60% faster)                    ││
│                    └───────────────────────────────────────────┘│
│                                          ↓                       │
│                              git automation                      │
│                     (commit → push → PR → close issue)           │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  8 Pipeline Agents  │  Skills  │  Hooks  │  Libraries │
└─────────────────────────────────────────────────────────────────┘
```

### Agent Architecture

**8 Pipeline Agents** (invoked via Task tool):
1. **researcher-local** (Haiku) - Searches codebase for existing patterns
2. **researcher** (Sonnet) - Researches best practices and security considerations
3. **planner** (Opus) - Designs implementation architecture
4. **test-master** (Opus) - Writes comprehensive tests (optional `--tdd-first` mode)
5. **implementer** (Opus) - Writes production-quality code with acceptance + regression tests
6. **reviewer** (Sonnet) - Reviews code quality, patterns, and coverage
7. **security-auditor** (Opus) - Scans for OWASP vulnerabilities
8. **doc-master** (Haiku) - Updates documentation to match code changes

**Utility Agents** (6 more):
- commit-message-generator, continuous-improvement-analyst, issue-creator, quality-validator, sync-validator, test-coverage-auditor

**How Agents Work**:
- Agents are markdown prompts (not Python files)
- Invoked via Claude's Task tool with `subagent_type` parameter
- Each agent has specialized knowledge and tools
- Pipeline runs sequentially (except parallel validation in step 6)

### Model Tier Strategy (Cost-Optimized)

| Tier | Model | Agents |
|------|-------|--------|
| **Tier 1** | Haiku | researcher-local, doc-master |
| **Tier 2** | Sonnet | reviewer, researcher (web), continuous-improvement-analyst |
| **Tier 3** | Opus | planner, test-master, implementer, security-auditor |

---

## Active Automation Hooks

Hooks run automatically at key moments to enforce quality without manual intervention:

| Hook Type | What It Does |
|-----------|--------------|
| **PreToolUse** | 4-layer security validation (sandboxing → MCP → agent auth → batch permissions) |
| **PreCommit** | Blocks commits with failing tests, missing docs, or security issues |
| **SubagentStop** | Triggers git automation after pipeline completion |
| **UserPromptSubmit** | Enforces workflow discipline and command validation |
| **SessionStart** | Restores session state after `/clear` for continuity |

**Key Hooks**:
- **unified_pre_tool.py**: 4-layer security (84% reduction in permission prompts)
- **stop_quality_gate.py**: End-of-turn quality checks (pytest, ruff, mypy)
- **enforce_tdd.py**: Test-first workflow enforcement (specification/acceptance tests before implementation)
- **enforce_orchestrator.py**: PROJECT.md alignment validation
- **unified_session_tracker.py**: Session state persistence across `/clear` operations

**Hook Exit Code Semantics**:
- `EXIT_SUCCESS (0)`: Hook passed, continue execution
- `EXIT_WARNING (1)`: Non-blocking warning, log and continue
- `EXIT_BLOCK (2)`: Critical failure, block operation
- Lifecycle hooks (PreToolUse, SubagentStop) must exit 0 (blocking not allowed)

**What hooks catch automatically:**
- Documentation drift from code changes
- Secrets accidentally staged for commit
- `git push --force` to protected branches
- Missing test coverage on new code
- CLAUDE.md out of sync with codebase
- Path traversal and injection attacks
- Agent execution failures (auto-retry with circuit breaker)

**Philosophy**: Quality gates should be automatic. If you have to remember to check something, you'll eventually forget.

---

## Zero Manual Git Operations

After pipeline completion, autonomous-dev handles everything:

```
Feature completes → Generate commit message → Stage & commit
                 → Push to remote → Create PR → Close GitHub issue
```

**Enabled by default** with first-run consent. Configure via `.env`:

```bash
AUTO_GIT_ENABLED=true   # Master switch (default: true)
AUTO_GIT_PUSH=true      # Auto-push (default: true)
AUTO_GIT_PR=true        # Auto-create PRs (default: true)
```

**Features**:
- Conventional commit messages generated by AI
- Co-authorship footer included
- PR descriptions with summary, test plan, related issues
- Automatic GitHub issue closing with workflow summary

---

## Self-Validation Quality Gates

autonomous-dev enforces its own quality standards. When the plugin detects it's running in the autonomous-dev repository, stricter gates activate automatically:

**In autonomous-dev Repository**:
- **Coverage Threshold**: 80% (vs 70% for user projects)
- **No Bypass**: Cannot override quality gates with `--no-verify`
- **Automatic Enforcement**: Enabled without configuration needed

**Quality Gates Enforced**:
| Gate | Standard | autonomous-dev |
|------|----------|-----------------|
| Test Coverage | 70% | **80%** |
| Test-First Requirement | Suggested | **Required** |
| Pre-commit Checks | Optional | **Mandatory** |
| Documentation Sync | Auto-checked | **Strictly enforced** |

**How It Works**:
1. Hooks detect autonomous-dev repository via `plugins/autonomous-dev/manifest.json`
2. Auto-detect based on file structure (survives worktrees, CI/CD)
3. Apply stricter thresholds in enforcement hooks
4. Block commits that don't meet standards (no bypass possible)

**Philosophy**: "We practice what we preach." If autonomous-dev requires 80% coverage from you, it requires it from itself.

---

## Batch Processing

Process 50+ features without manual intervention:

### From File
```bash
# features.txt
Add JWT authentication
Add password reset (requires JWT)
Add email notifications
```

```bash
/implement --batch features.txt
```

### From GitHub Issues
```bash
/implement --issues 72 73 74
```

### Auto-Continuation (Issue #285)

**New**: Batch now automatically continues through all features in a single invocation.
```bash
/implement --batch features.txt
# Processes Features 1/5 → 2/5 → 3/5 → 4/5 → 5/5 automatically
# No manual `/implement --resume` needed between features
# Manual resume only needed if batch is interrupted (not between features)
```

**Why This Matters**: Previously, batch processing stopped after each feature requiring manual intervention. Now features auto-continue without interruption. Failed features are recorded but don't stop the batch.

### Smart Features

**Dependency Analysis**: Automatically reorders features based on dependencies (Issue #157)
```
Original: [tests, auth, email]
Optimized: [auth, email, tests]  # Tests run after implementation
```
- Analyzes feature dependencies via keyword matching
- Topological sort for optimal execution order
- Circular dependency detection with ASCII graph visualization
- Preserves explicit ordering when dependencies are ambiguous

**Checkpoint/Resume**: Automatic session snapshots with safe resume capability (Issues #276, #277)
```bash
# Batch processing automatically creates checkpoints after each feature
# If interrupted, resume from checkpoint:
/implement --resume batch-20260110-143022

# Rollback to previous checkpoint if needed:
/implement --rollback batch-20260110-143022 --previous
```

**Context Management**:
- Claude auto-compact at ~185K tokens (23% increase from 150K baseline)
- Batch checkpoints after every feature (state + progress saved)
- SessionStart hook auto-resumes after `/clear` or auto-compact
- Corrupted checkpoint recovery with `.bak` fallback
- Token tracking: `context_token_delta` per feature for threshold detection

**Automatic Retry**: Transient failures (network, rate limits) retry automatically. Permanent errors (syntax, type) skip immediately.

**Per-Feature Git**: Each feature commits separately with conventional messages.

**Issue Auto-Close**: GitHub issues closed automatically after push with summary comment.

---

## GitHub Actions Integration

Automate PR reviews and issue implementation with Claude directly in your GitHub workflow.

| Workflow | Trigger | What It Does |
|----------|---------|--------------|
| **Claude Code Review** | PR opened/updated, `@claude` comment | Automated code review against project conventions |
| **Claude Issue Implementation** | Issue labeled `claude-implement` | Reads issue, implements solution, opens PR |

See [docs/GITHUB-ACTIONS.md](docs/GITHUB-ACTIONS.md) for setup and configuration.

---

## Advanced Features

### Ralph Loop: Self-Correcting Agent Execution

Agents automatically retry failed operations with intelligent validation:

```
Agent fails → Analyze error → Adjust strategy → Retry (up to 3x)
           ↓
     Circuit breaker prevents infinite loops
```

**5 Validation Strategies**:
1. **pytest**: Test-based validation (tests must pass)
2. **safe_word**: AI confirms completion in response
3. **file_existence**: Required files must exist
4. **regex**: Output must match pattern
5. **json**: Output must be valid JSON

**Features**:
- Token limits prevent runaway costs
- Circuit breaker after 3 failures
- Validation strategy per agent type
- Default: ENABLED for all pipeline agents

### Quality Persistence: Honest Batch Summaries

Batch processing enforces 100% integrity:

**Rules**:
- 100% test pass requirement (not 80%)
- Failed features keep GitHub issues OPEN + 'blocked' label
- Retry escalation: 3 attempts with increasing wait times
- Honest summaries: Never fakes success

**Why This Matters**: Prevents "silent failures" where batch reports success but issues remain broken.

### Worktree Isolation

Per-batch worktree creation for parallel development:

```bash
/implement --batch features.txt
# Creates: .worktrees/batch-20260128-143022/
# Automatic CWD change to worktree
# Main repo remains untouched until merge
```

**Benefits**:
- Concurrent CI jobs without interference
- Per-worktree batch state isolation
- Safe experimentation (discard without affecting main)
- Supports nested worktrees

### Session State Persistence

Session state survives `/clear` operations:

**Stored in** `.claude/local/SESSION_STATE.json`:
- Active tasks and next steps
- Key conventions (repo-specific patterns)
- Recent context (files modified, workflows completed)

**Read at SessionStart**: Automatic continuity across sessions

### UV Script Execution

All hooks use UV for reproducible execution:

**Features**:
- PEP 723 metadata blocks (inline dependencies)
- Zero environment setup overhead
- Graceful fallback to `sys.path`
- Single-file portability

**Example** (from any hook):
```python
#!/usr/bin/env -S uv run --quiet
# /// script
# dependencies = ["pytest", "coverage"]
# ///
```

---

## Security-First Architecture

### 4-Layer Permission Architecture

```
Layer 1: Sandbox Enforcer      → Command classification (SAFE/BLOCKED/NEEDS_APPROVAL)
Layer 2: MCP Security          → Path traversal, injection, SSRF prevention
Layer 3: Agent Authorization   → Pipeline agent detection
Layer 4: Batch Approver        → Caches user consent for identical operations
```

**Result**: 84% reduction in permission prompts (50+ → 8-10).

### Security Validations
- CWE-22: Path traversal prevention
- CWE-78: Command injection blocking
- CWE-918: SSRF prevention
- Symlink rejection outside whitelist
- Credential safety (never logged)
- Audit logging to `logs/security_audit.log`

---

## Performance

### Optimization Results

| Phase | Improvement |
|-------|-------------|
| Model optimization (Haiku for research) | 3-5 min saved |
| Prompt simplification | 2-4 min saved |
| Parallel validation | 60% faster (5 min → 2 min) |
| Smart agent selection | 95% faster for typos/docs |

**Current Performance**:
- Full pipeline: 15-25 minutes per feature
- Quick mode: 2-5 minutes
- Typo fixes: <2 minutes (95% faster than full pipeline)

### Context Management

- Automatic context summarization (Claude Code handles 200K token budget)
- Session files log to `docs/sessions/` (200 tokens vs 5,000+)
- `/clear` recommended after each feature for optimal performance

---

## Documentation

| Guide | Description |
|-------|-------------|
| [CLAUDE.md](CLAUDE.md) | Project instructions and quick reference |
| [Architecture](docs/ARCHITECTURE-OVERVIEW.md) | Technical architecture deep-dive |
| [Agents](docs/AGENTS.md) | 8-agent pipeline + utility agents |
| [Hooks](docs/HOOKS.md) | Active automation hooks reference |
| [Skills](docs/ARCHITECTURE-OVERVIEW.md) | Skills and agent integration |
| [Workflow Discipline](docs/WORKFLOW-DISCIPLINE.md) | Why pipelines beat direct implementation |
| [Performance](docs/PERFORMANCE.md) | Benchmarks and optimization history |
| [Git Automation](docs/GIT-AUTOMATION.md) | Zero manual git operations |
| [Batch Processing](docs/BATCH-PROCESSING.md) | Multi-feature workflows with auto-continuation |
| [Security](docs/SECURITY.md) | Security model and hardening guide |

---

## Requirements

- [Claude Code](https://claude.ai/code) 2.0+
- macOS or Linux
- Git
- `gh` CLI (optional, for PR creation and issue management)

---

## Philosophy

### Automation > Reminders > Hope

Quality should be automatic, not optional. autonomous-dev makes the right thing the easy thing:

- **Research** happens automatically before implementation
- **Tests** are written first (specification-driven, acceptance-first default)
- **Security** is scanned on every feature
- **Documentation** stays in sync automatically
- **Git operations** are orchestrated end-to-end
- **Alignment** is validated against your stated intent

You describe what you want. The pipeline handles the rest.

### The 4-Layer Consistency Architecture

| Layer | Weight | Purpose |
|-------|--------|---------|
| **Hooks** | 10% | Deterministic blocking (secrets, force push) |
| **CLAUDE.md** | 30% | Persuasion via data (this README) |
| **Convenience** | 40% | Quality path is the easy path |
| **Skills** | 20% | Agent expertise and knowledge |

We don't force quality. We make it the path of least resistance.

---

## License

MIT

---

<p align="center">
  <strong>Built for developers who ship.</strong>
</p>
