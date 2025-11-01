# Claude Code Autonomous Development Plugin

**Last Updated**: 2025-10-27
**Version**: v3.1.0 (Agent-Skill Integration Architecture)
**Status**: Production-ready with Vibe Coding + Agent-Skill Integration

> **User Intent (v3.0+)**: *"I speak requirements and Claude Code delivers first-grade software engineering in minutes by following all necessary SDLC steps (research, plan, TDD, implement, review, security, docs) — automated and accelerated via AI, not shortcuts."*

Production-ready plugin for **autonomous development teams** with **dual-layer architecture** (Vibe Coding + Background Enforcement), **PROJECT.md-first enforcement**, and **automatic agent orchestration**.

**What it does**: You describe a feature in natural language → plugin automatically researches, plans, writes tests, implements, reviews, audits security, updates docs, and commits — all while validating alignment with your PROJECT.md goals.

🧠 **Vibe Coding** • 🛑 **PROJECT.md Gatekeeper** • 🤖 **19 Specialist Agents** • ✅ **Auto-Orchestration** • 🔒 **Security Enforcement** • 📋 **8 Core Commands**

---

## ⭐ The PROJECT.md-First Philosophy

**Everything starts with PROJECT.md** - your project's strategic direction documented once, enforced automatically across all work.

### What is PROJECT.md?

A single markdown file at your project root that defines your project's strategic direction with **four required sections**:

```markdown
# PROJECT.md

## GOALS
What success looks like. Examples:
- "Build a scalable REST API"
- "Create user-friendly dashboard"
- "Achieve 99.9% uptime"

## SCOPE
What's IN and OUT of scope. Examples:
- IN: User authentication, payments processing
- OUT: Mobile apps, marketing site, analytics

## CONSTRAINTS
Technical and business limits. Examples:
- "Must support Python 3.11+"
- "PostgreSQL for data persistence"
- "Must pass OWASP Top 10 security scan"

## ARCHITECTURE
How the system works. Examples:
- "FastAPI backend + React frontend + PostgreSQL"
- "Microservices with Kubernetes"
- "Monolithic Django application"
```

### Why PROJECT.md-First?

✅ **Single source of truth** - One file defines strategic direction
✅ **Automatic enforcement** - Every feature validates against PROJECT.md BEFORE work begins
✅ **Zero scope creep** - Features outside SCOPE are automatically blocked
✅ **Team alignment** - Humans and AI work toward same goals
✅ **Survives tools** - PROJECT.md is markdown at root, survives plugin updates
✅ **Prevents drift** - Strategic goals don't change accidentally

### How It Works

```
1. Create PROJECT.md (at project root)
   └─> Define GOALS, SCOPE, CONSTRAINTS, ARCHITECTURE

2. Use /auto-implement for features
   └─> Example: "Add user authentication"

3. orchestrator validates alignment
   ├─> Does feature serve GOALS? ✓
   ├─> Is feature IN SCOPE? ✓
   ├─> Respects CONSTRAINTS? ✓
   ├─> Aligns with ARCHITECTURE? ✓
   └─> If ANY check fails → BLOCK work

4. If blocked, you have two options
   ├─> Option A: Update PROJECT.md (if direction changed)
   └─> Option B: Modify feature request (to align with current scope)

5. Feature proceeds ONLY if fully aligned
   └─> Research → Plan → TDD → Implement → Review → Security → Docs
```

**Result**: Zero tolerance for scope drift. Strategic alignment guaranteed.

---

## 🧠 Vibe Coding: Natural Language Feature Development

**Vibe Coding** is the core innovation: describe what you want in natural language, and the plugin automatically orchestrates the entire development pipeline.

### How Vibe Coding Works

After installation, the plugin configures `customInstructions` in Claude Code to monitor for feature requests. When you write something like:

```
"Add user authentication with JWT tokens"
"Implement Redis caching for API responses"
"Create admin dashboard for user management"
```

The system automatically:
1. **Detects** the feature request (via `detect-feature-request` hook)
2. **Auto-invokes** `/auto-implement` (you don't need to type the command)
3. **Validates** alignment with PROJECT.md (orchestrator gatekeeper)
4. **Executes** the 7-agent pipeline automatically
5. **Commits** the feature automatically

**Result**: You speak requirements, the plugin delivers production-ready code in ~30 minutes.

### Without Vibe Coding (Manual Mode)

If you prefer not to use vibe coding:
```bash
# You manually type this after installation
/auto-implement "Add user authentication"
```

Both work! Vibe coding is an **optional convenience** (enabled via `customInstructions` in `.claude/settings.local.json`).

---

## Quick Start

### Installation (3 Simple Steps)

**Step 1: Add marketplace and install**
```bash
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
```

**Step 2: Exit Claude Code completely**
- Press **Cmd+Q** (Mac) or **Ctrl+Q** (Windows/Linux)
- Wait for it to close

**Step 3: Reopen Claude Code**
- Launch Claude Code

**Done!** All 8 commands now available.

**Optional: Run setup wizard**
```bash
/setup
```
This configures automatic hooks (auto-format on save, auto-test on commit) and creates PROJECT.md from template.

### What You Get (8 Commands)

**Core Commands**:
✅ `/auto-implement` - Describe a feature, Claude handles everything autonomously
✅ `/align-project` - Find & fix misalignment between goals and code
✅ `/status` - Track strategic goal progress with AI recommendations
✅ `/setup` - Interactive project configuration
✅ `/test` - Run all automated tests (unit + integration + UAT)

**Utility Commands**:
✅ `/health-check` - Verify all components loaded and working
✅ `/sync-dev` - Intelligent development sync with conflict detection
✅ `/uninstall` - Remove or disable plugin

### Verify Installation

```bash
/health-check
```

Should show all 8 commands loaded and working ✅:
- `/auto-implement`, `/align-project`, `/setup`, `/test`, `/status`
- `/health-check`, `/sync-dev`, `/uninstall`

### Optional Setup (Advanced)

**Only needed if you want automatic hooks** (auto-format on save, auto-test on commit):

```bash
/setup
```

This wizard helps you:
- Enable automatic formatting on file save
- Create PROJECT.md from template
- Configure GitHub integration (.env file)
- Choose between slash commands or automatic hooks

**Note**: Most users don't need this! You can use slash commands manually or let hooks run automatically at commit.

### Updating

```bash
# 1. Uninstall current version
/plugin uninstall autonomous-dev

# 2. Exit and restart Claude Code (REQUIRED!)
# Press Cmd+Q (Mac) or Ctrl+Q (Linux/Windows)

# 3. Reopen Claude Code and reinstall
/plugin install autonomous-dev

# 4. Exit and restart again
# Press Cmd+Q (Mac) or Ctrl+Q (Linux/Windows)

# 5. Reopen Claude Code
# Done!
```

**IMPORTANT**: You must exit and restart Claude Code after both uninstall AND install!

**Note**: If you're using automatic hooks, you may want to re-run `/setup` after updating to get the latest hook versions.

---

## Getting Started: New Project vs Existing Project

### 🆕 Starting a New Project

**Perfect workflow for greenfield projects:**

```bash
# 1. Install plugin (see Quick Start above)

# 2. Create PROJECT.md
/setup
# Creates PROJECT.md from template at project root
# Edit PROJECT.md to define your goals, scope, constraints

# 3. Set up project structure
/align-project
# Choose option 2 (Fix interactively)
# Creates tests/, docs/, .gitignore, etc.

# 4. Start developing
/auto-implement "implement user authentication"
# Orchestrator validates against PROJECT.md, then runs 8-agent pipeline

# Done! You now have:
# ✅ PROJECT.md defining strategic direction
# ✅ Aligned project structure
# ✅ Autonomous development ready
```

**Result**: Strategic direction → enforced automatically from day 1.

### 🔄 Retrofitting an Existing Project

**Safe workflow for adding to existing codebases:**

```bash
# 1. Install plugin (see Quick Start above)

# 2. Create PROJECT.md from your existing project
/setup
# Creates PROJECT.md template
# Edit to match your CURRENT goals, scope, constraints
# Tip: Document what you have, not what you wish you had

# 3. Analyze current alignment
/align-project
# Choose option 1 (View report only)
# See what needs to change to align with PROJECT.md

# 4. Fix issues gradually (or not at all)
/align-project
# Choose option 2 (Fix interactively)
# Say YES to changes you want, NO to skip
# Press 'q' to quit anytime

# 5. Update PROJECT.md as you refactor
vim PROJECT.md  # Update SCOPE, GOALS as project evolves
/align-project  # Re-check alignment

# Done! You now have:
# ✅ PROJECT.md documenting current strategic direction
# ✅ Gradual alignment with best practices
# ✅ Autonomous development on new features
```

**Result**: Strategic direction documented → gradual alignment → enforced going forward.

### Key Differences

| Aspect | New Project | Existing Project |
|--------|-------------|------------------|
| PROJECT.md | Define ideal state | Document current state |
| Alignment | Full alignment immediately | Gradual alignment over time |
| Risk | Low (greenfield) | Medium (refactoring) |
| Approach | Prescriptive | Descriptive then prescriptive |

**Both workflows result in**: PROJECT.md-first development where future work validates against strategic direction automatically.

---

## What You Get

### 19 Specialized Agents

**Core Workflow Agents (8)** - Execute the main SDLC pipeline in sequence:
- **orchestrator** `sonnet` - PROJECT.md gatekeeper, validates alignment before any work begins
- **researcher** `sonnet` - Web research for patterns, best practices, and existing solutions
- **planner** `opus` - Architecture & implementation planning (complex analysis)
- **test-master** `sonnet` - TDD specialist (writes failing tests first)
- **implementer** `sonnet` - Code implementation (makes tests pass)
- **reviewer** `sonnet` - Quality gate checks (code review)
- **security-auditor** `haiku` - Security scanning and vulnerability detection
- **doc-master** `haiku` - Documentation sync and CHANGELOG updates

> **Model Strategy**: Opus for complex planning (1 step), Sonnet for general work (6 steps), Haiku for simple checks (2 steps) = optimized cost/quality

**Analysis & Validation Agents (6)** - Validate quality and PROJECT.md alignment:
- **advisor** `sonnet` - Critical thinking and risk validation before decisions
- **quality-validator** `sonnet` - GenAI-powered feature quality and standards validation
- **alignment-validator** `sonnet` - PROJECT.md alignment validation (features vs goals/scope/constraints)
- **alignment-analyzer** `sonnet` - Detailed conflict analysis (PROJECT.md vs reality/code/docs)
- **project-progress-tracker** `sonnet` - Track and update PROJECT.md goal completion metrics
- **project-status-analyzer** `sonnet` - Real-time project health monitoring and recommendations

**Automation & Setup Agents (5)** - Configure workflows and automate routine tasks:
- **commit-message-generator** `sonnet` - Conventional commit message generation
- **pr-description-generator** `sonnet` - Comprehensive PR descriptions from implementation artifacts
- **setup-wizard** `sonnet` - Intelligent setup and tech stack detection/configuration
- **project-bootstrapper** `sonnet` - Analyze existing codebases and generate/update PROJECT.md
- **sync-validator** `sonnet` - Smart development environment sync and conflict detection

### 19 Specialist Skills (Progressive Disclosure Architecture)

Agents leverage 19 specialized skill packages using **progressive disclosure** - metadata stays in context (minimal overhead), full skill content loads only when needed.

**Organized by Category**:

**Core Development Skills**:
- **api-design** - REST API design, versioning, error handling, pagination, OpenAPI documentation
- **architecture-patterns** - System architecture, ADRs, design patterns, tradeoff analysis
- **code-review** - Code quality assessment, style checking, pattern detection
- **database-design** - Schema design, migrations, query optimization, ORM patterns
- **testing-guide** - TDD methodology, test patterns, coverage strategies, regression prevention
- **security-patterns** - API key management, input validation, encryption, OWASP compliance

**Workflow & Automation Skills**:
- **git-workflow** - Commit conventions, branching strategies, PR workflows
- **github-workflow** - Issues, PRs, milestones, auto-tracking
- **project-management** - PROJECT.md creation, goal setting, sprint planning, scope definition
- **documentation-guide** - Documentation standards, API docs, README patterns, consistency

**Code & Quality Skills**:
- **python-standards** - PEP 8, type hints, docstrings, black/isort formatting
- **observability** - Logging, debugging, profiling, performance monitoring
- **consistency-enforcement** - Documentation consistency, drift prevention
- **file-organization** - Project structure enforcement, auto-fix mode

**Validation & Analysis Skills**:
- **research-patterns** - Research methodology, pattern discovery, best practices
- **semantic-validation** - GenAI-powered semantic validation, drift detection
- **cross-reference-validation** - Documentation reference validation, link checking
- **documentation-currency** - Stale documentation detection, version lag detection
- **advisor-triggers** - Critical analysis patterns, decision trade-offs

**How Skills Work**: Each agent includes relevant skill metadata in its system prompt. When an agent recognizes a task needs specialized expertise, it loads the full skill content (SKILL.md) and supporting files on-demand. This "progressive disclosure" approach eliminates context bloat - you can scale to 50+ skills without exceeding token budgets.

### 9 Slash Commands

All commands are independently discoverable with autocomplete:

**Core Commands** (6):
- `/auto-implement` - Describe feature, Claude handles everything autonomously
- `/align-project` - Analyze & fix PROJECT.md alignment (menu: report/fix/preview/cancel)
- `/align-claude` - Check and fix CLAUDE.md alignment with codebase
- `/setup` - Interactive project setup wizard
- `/test` - Run all automated tests (unit + integration + UAT)
- `/status` - Track strategic goal progress with AI recommendations

**Utility Commands** (3):
- `/health-check` - Verify all components loaded and working
- `/sync-dev` - Intelligent development sync with conflict detection
- `/uninstall` - Remove or disable plugin

See [plugins/autonomous-dev/docs/COMMANDS.md](plugins/autonomous-dev/docs/COMMANDS.md) for complete command reference.

### Automation Hooks (24 total)

All hooks are **pre-commit** (run before code is committed). They validate quality automatically.

**Core Blocking Hooks (9)** - Run by default, block commits if failed:
- **detect-feature-request** - Auto-invokes `/auto-implement` when feature requests detected (vibe coding)
- **validate-project-alignment** - PROJECT.md must exist with GOALS/SCOPE/CONSTRAINTS before committing
- **enforce-orchestrator** - Validates orchestrator ran and made alignment decision (v3.0+)
- **enforce-tdd** - Validates tests written BEFORE code (test-first development required)
- **auto-test** - pytest (Python), jest (JS/TS) - tests must pass
- **security-scan** - Secrets detection, vulnerability scanning - must pass security checks
- **auto-format** - black + isort (Python), prettier (JS/TS) - auto-fixes and validates formatting
- **validate-docs-consistency** - Documentation must match code changes
- **enforce-file-organization** - Project structure must follow standard organization

**Extended Optional Hooks (15)** - Provide additional enforcement and automation:
- **auto-enforce-coverage** - Enforces 80% minimum test coverage
- **auto-add-to-regression** - Automatically adds tests to regression suite
- **auto-generate-tests** - Generates test skeletons for new code
- **auto-update-docs** - Updates documentation when code changes
- **auto-fix-docs** - Auto-corrects common documentation patterns
- **auto-sync-dev** - Smart synchronization of development branches
- **auto-tdd-enforcer** - Reinforces TDD workflow compliance
- **auto-track-issues** - Tracks issues and updates status
- **detect-doc-changes** - Detects undocumented code changes
- **post-file-move** - Updates imports/references after file moves
- **enforce-bloat-prevention** - Prevents documentation/code sprawl
- **enforce-command-limit** - Ensures command count stays ≤ 8
- **validate-claude-alignment** - CLAUDE.md alignment checking
- **validate-documentation-alignment** - Detects docs drift vs code
- **validate-session-quality** - Quality checks for session logs

---

## How It Works

### The Autonomous Development Loop

This is a **dual-layer architecture**: Vibe Coding (natural language triggers) + Background Enforcement (automatic validation).

```
LAYER 1: VIBE CODING (User Experience)
   ↓
You: "implement user authentication"
   ↓
[Auto-Orchestration Hook]
   └─> Detects feature request automatically
   └─> Auto-invokes /auto-implement (no manual command typing)
   ↓

LAYER 2: BACKGROUND ENFORCEMENT (Quality Assurance)
   ↓
orchestrator (PROJECT.md GATEKEEPER)
   ├─> 1. Reads PROJECT.md (GOALS, SCOPE, CONSTRAINTS)
   ├─> 2. Validates: Does feature serve GOALS?
   ├─> 3. Validates: Is feature IN SCOPE?
   ├─> 4. Validates: Respects CONSTRAINTS?
   └─> 5. Decision:
        ✅ Aligned → Proceed with 7-agent pipeline
        ❌ NOT Aligned → BLOCK work (user updates PROJECT.md or modifies request)
   ↓

7-AGENT PIPELINE (only if PROJECT.md aligned):
   │
   ├─> researcher (5 min)     Finds patterns & best practices
   ├─> planner (5 min)        Creates architecture plan
   ├─> test-master (5 min)    Writes tests first (TDD)
   ├─> implementer (10 min)   Writes code to pass tests
   ├─> reviewer (2 min)       Quality gate checks
   ├─> security-auditor (2 min) Security scanning
   └─> doc-master (1 min)     Documentation sync
   ↓

Total Time: ~30 minutes (vs 7+ hours manual)
All SDLC steps completed, no shortcuts taken
   ↓

PRE-COMMIT VALIDATION (Automatic & Blocking):
   ├─> ✅ PROJECT.md alignment
   ├─> ✅ Tests pass (80%+ coverage)
   ├─> ✅ Security scan passes
   ├─> ✅ Docs synchronized
   ├─> ✅ Code formatted
   └─> ✅ TDD workflow validated
   ↓

RESULT:
   ✅ Code committed (professional quality guaranteed)
   ❌ If any check fails → Commit blocked (Claude can fix)
```

### Validation Logic & Feature Blocking

The orchestrator validates every feature request using a **4-check system**:

```python
def validate_feature(feature_request, project_md):
    # Check 1: Does it serve project GOALS?
    if not serves_any_goal(feature_request, project_md.goals):
        return BLOCK("Feature doesn't advance project goals")

    # Check 2: Is it explicitly IN SCOPE?
    if feature_request not in project_md.scope.in_scope:
        return BLOCK("Feature is outside defined SCOPE")

    # Check 3: Does it respect CONSTRAINTS?
    if violates_constraints(feature_request, project_md.constraints):
        return BLOCK("Feature violates technical/business constraints")

    # Check 4: Does it align with ARCHITECTURE?
    if not aligns_with_architecture(feature_request, project_md.architecture):
        return BLOCK("Feature doesn't fit system architecture")

    # All checks pass → proceed with pipeline
    return APPROVE(feature_request)
```

**When Features Are BLOCKED:**

```
❌ BLOCKED: Feature not aligned with PROJECT.md

**Your PROJECT.md SCOPE**: [Lists IN/OUT]
**Your Feature Request**: "implement mobile app"
**Issue**: Mobile app is explicitly OUT of scope

**Resolution Options**:
1. Update PROJECT.md SCOPE to include mobile (if direction changed)
2. Modify request to align with current SCOPE
3. Don't implement (feature is out of scope)

Strict mode: Work CANNOT proceed without alignment.
```

**Why Blocking?**

✅ **Prevents scope creep** - Features stay aligned with goals
✅ **Saves time** - You explicitly chose what's in/out
✅ **Forces alignment** - All work must serve strategic goals
✅ **Team clarity** - No ambiguity about what gets built

---

## 📁 Standard Project Structure (Enforced)

The plugin enforces a standard project structure that works across all languages:

```
project/
├── src/                          # ✅ ALL source code here
│   ├── module1.py / index.js
│   ├── module2.py / component.tsx
│   └── ...
├── tests/                        # ✅ ALL tests here
│   ├── unit/                    # Unit tests (fast)
│   │   ├── test_module1.py
│   │   └── ...
│   ├── integration/             # Integration tests (medium)
│   │   ├── test_api.py
│   │   └── ...
│   └── uat/                     # User acceptance tests (slow)
│       ├── test_workflows.py
│       └── ...
├── docs/                        # ✅ ALL documentation here
│   ├── api/                    # API documentation
│   ├── guides/                 # User guides
│   ├── sessions/               # Agent session logs
│   └── ...
├── scripts/                     # ✅ Utility scripts
│   ├── setup.py
│   └── ...
├── .claude/                     # Claude Code configuration
│   ├── PROJECT.md             # Strategic direction (GATEKEEPER)
│   ├── settings.local.json    # Hook configuration
│   └── hooks/                 # Project-specific hook overrides
├── README.md                    # User documentation (required)
├── LICENSE                      # MIT or other (required)
├── .gitignore                   # Git ignore patterns
└── pyproject.toml / package.json # Dependencies (required)
```

**Enforcement Rules** (pre-commit hook validates):
- ✅ `src/` exists and contains source code
- ✅ `tests/` exists with unit/ integration/ uat/ subdirectories
- ✅ `docs/` exists with guides and session logs
- ✅ `scripts/` exists for utilities
- ✅ `.claude/` has PROJECT.md (enforced by validate-project-alignment hook)
- ✅ Root directory clean (only README.md, LICENSE, config files)
- ❌ No loose source files in root
- ❌ No tests in src/ directory
- ❌ No src files scattered in root

If your project doesn't match, run:
```bash
/align-project
# Choose "Fix interactively" to migrate your code automatically
```

---

## 🎯 Design Principles (Production Standards)

These principles are derived from official Anthropic Claude Code patterns and guide all design decisions:

### Philosophy

1. **Trust the Model** - Claude Sonnet/Opus are extremely capable; don't over-prescribe implementation
2. **Simple > Complex** - 50-line agent beats 800-line agent (both work, simple scales better)
3. **Warn > Auto-fix** - Let Claude see and fix issues (builds pattern understanding)
4. **Minimal > Complete** - Focused guidance beats exhaustive documentation
5. **Parallel > Sequential** - Launch multiple agents for diverse perspectives

### Agent Design

**Requirements**:
- **Target**: 50-100 lines total (frontmatter + content)
- **Maximum**: 150 lines strictly enforced
- **Structure**: Clear mission, core responsibilities, process, output format
- **Tools**: Only essential tools, principle of least privilege

**Anti-patterns to avoid**:
- ❌ Bash scripts embedded in markdown
- ❌ Python code examples in prompts
- ❌ Complex artifact protocols
- ❌ Detailed JSON schemas (100+ line examples)
- ❌ Step-by-step prescriptions (trust the model)
- ❌ Over-specification of techniques

### Hook Design

**Requirements**:
- **Single concern** - One hook, one purpose
- **Declarative** - Rules at top, easy to maintain
- **Exit codes**: 0 (silent), 1 (warn user), 2 (block + alert Claude)
- **Fast** - Must complete in < 1 second

**Anti-patterns**:
- ❌ Auto-fixing (hide issues from Claude)
- ❌ Complex multi-stage logic
- ❌ Heavy I/O operations
- ❌ Silent failures

### Context Management

**Critical Constraints**:
- **Per-feature budget**: < 8,000 tokens
- **Agent prompts**: 500-1,000 tokens (50-100 lines)
- **Codebase exploration**: 2,000-3,000 tokens
- **Working memory**: 2,000-3,000 tokens

**Best Practices**:
- ✅ Keep agents short (minimal context usage)
- ✅ No artifact protocols (avoid `.claude/artifacts/` complexity)
- ✅ Session logging (reference file paths, not content)
- ✅ Clear after features (use `/clear` between features)
- ✅ Minimal prompts (trust model > detailed instructions)

---

## 👨‍💻 Development Workflow (For Contributors)

If you're developing the plugin (not just using it), follow this critical workflow:

### ⚠️ CRITICAL RULE: Edit Location Matters

```
❌ WRONG: Edit in .claude/agents/, .claude/commands/, .claude/hooks/
         (these are installed copies - changes will be lost)

✅ RIGHT: Edit in plugins/autonomous-dev/agents/, commands/, hooks/
         (these are the source - plugin reads from here)
```

### Development Workflow

```
1. EDIT SOURCE
   └─> Make changes in: plugins/autonomous-dev/agents/, commands/, hooks/

2. REINSTALL PLUGIN
   └─> /plugin uninstall autonomous-dev
   └─> Exit Claude Code (Cmd+Q or Ctrl+Q)
   └─> Restart Claude Code
   └─> /plugin install autonomous-dev
   └─> Exit Claude Code again
   └─> Restart Claude Code

3. TEST LIKE USERS
   └─> Test features in .claude/ environment
   └─> This mirrors what users see after installation

4. FIX & ITERATE
   └─> Edit plugins/autonomous-dev/ again
   └─> Repeat steps 2-3
```

### File Organization for Plugin Development

```
SOURCE OF TRUTH (Edit here):
plugins/autonomous-dev/
├── agents/         (19 AI agents)
├── commands/       (8 slash commands)
├── hooks/          (24 automation hooks)
├── scripts/        (setup wizard, infrastructure)
├── templates/      (PROJECT.md, settings templates)
├── docs/          (user guides)
└── tests/         (plugin tests)

TESTING ENVIRONMENT (Don't edit here):
.claude/           (installed plugin copy)
├── agents/        (mirrors plugins/autonomous-dev/agents/)
├── commands/      (mirrors plugins/autonomous-dev/commands/)
├── hooks/         (mirrors plugins/autonomous-dev/hooks/)
└── PROJECT.md     (your repo-specific goals)
```

### When to Edit What

| File | Where | Why | When |
|------|-------|-----|------|
| Agent logic | `plugins/autonomous-dev/agents/` | Source of truth | Bug fixes, feature improvements |
| Command workflow | `plugins/autonomous-dev/commands/` | Source of truth | New commands, command flow changes |
| Automation hooks | `plugins/autonomous-dev/hooks/` | Source of truth | New enforcement rules, bug fixes |
| PROJECT.md | `.claude/PROJECT.md` | Repo-specific | Update project goals, scope, architecture |
| settings.local.json | `.claude/settings.local.json` | Personal/local | Enable/disable hooks per project |

### Quality Standards

Before committing changes:

```bash
# 1. Verify agent/command lengths
wc -l plugins/autonomous-dev/agents/*.md  # Should be 50-100 lines each
wc -l plugins/autonomous-dev/commands/*.md # Should be reasonable

# 2. Verify counts
ls plugins/autonomous-dev/agents/*.md | wc -l     # Should be 19
ls plugins/autonomous-dev/commands/*.md | wc -l   # Should be 8

# 3. Run tests
/test  # All tests must pass

# 4. Verify structure
/health-check  # All components should load
```

---

## 📊 Success Metrics (How to Measure)

The plugin's success is measured by these concrete metrics:

### For Users

| Metric | Target | How to Check |
|--------|--------|-------------|
| **Feature time** | 20-30 min per feature (vs 7+ hrs manual) | Time feature from request to merged PR |
| **SDLC compliance** | 100% of features follow all 7 steps | orchestrator validates before proceeding |
| **Scope drift** | 0% (zero features outside SCOPE) | Pre-commit hook blocks misaligned work |
| **Test coverage** | 80%+ (enforced minimum) | Coverage report in test output |
| **Security scans** | 100% pass rate | Security-auditor completes successfully |
| **Documentation** | 100% synchronized | Docs validation hook passes |
| **Commit quality** | 100% follow conventional commits | Commit message generator enforces format |

### For Plugin Development

| Metric | Target | How to Check |
|--------|--------|-------------|
| **Agent count** | 19 (8 core + 6 analysis + 5 automation) | `ls plugins/autonomous-dev/agents/ | wc -l` |
| **Command count** | 8 (5 core + 3 utility) | `ls plugins/autonomous-dev/commands/ | wc -l` |
| **Agent length** | 50-100 lines (max 150) | `wc -l plugins/autonomous-dev/agents/*.md` |
| **Hook count** | 24 (9 core + 15 extended) | `ls plugins/autonomous-dev/hooks/ | wc -l` |
| **Context per feature** | < 8,000 tokens | Monitor during development |
| **Test execution** | < 60 seconds | Measure in CI/local |
| **Hook execution** | < 10 seconds total | Sum of all pre-commit hooks |

### Example Success Session

```
User: "Add JWT authentication to API"
             ↓
orchestrator: ✓ Serves GOALS (security requirement)
             ✓ IN SCOPE (authentication is included)
             ✓ Respects CONSTRAINTS (JWT standard)
             ✓ Aligns with ARCHITECTURE (FastAPI + auth)
             ↓
researcher   ✓ Finds JWT best practices (5 min)
planner      ✓ Plans auth flow (5 min)
test-master  ✓ Writes auth tests (5 min)
implementer  ✓ Implements endpoints (10 min)
reviewer     ✓ Code review passes (2 min)
security     ✓ Security scan passes (2 min)
doc-master   ✓ Docs updated (1 min)
             ↓
Pre-commit validation:
  ✓ PROJECT.md aligned
  ✓ Tests pass (89% coverage)
  ✓ Security scan OK
  ✓ Code formatted
  ✓ Docs synchronized
             ↓
Result: Feature merged in 30 minutes
        All SDLC steps completed
        Professional quality guaranteed
```

---

## ⚠️ Out of Scope (What We DON'T Do)

To maintain focus and quality, these features are **explicitly out of scope**:

- ❌ **Replacing human developers** - AI augments, doesn't replace
- ❌ **Skipping SDLC steps** - All steps required, no shortcuts
- ❌ **Optional best practices** - TDD, security, docs are mandatory in strict mode
- ❌ **Manual step management** - System handles steps automatically (user shouldn't manage)
- ❌ **Language lock-in** - Stay generic, support Python/JS/TypeScript/Go/Rust
- ❌ **Breaking existing workflows** - Enhance gradually, don't disrupt
- ❌ **SaaS/cloud hosting** - Local-first, you own your infrastructure
- ❌ **Paid features** - 100% free, MIT license, community-driven
- ❌ **Auto-fixing without visibility** - Claude must see and approve fixes
- ❌ **Hidden enforcement** - All rules explicit, transparent
- ❌ **Removing human judgment** - Claude assists, you decide final direction

---

## Supported Languages

- ✅ **Python** - black, isort, pytest, type hints
- ✅ **JavaScript** - prettier, jest, eslint
- ✅ **TypeScript** - prettier, jest, eslint
- ✅ **React** - prettier, jest, component testing
- ✅ **Node.js** - prettier, jest, API testing
- ✅ **Go** - gofmt, go test (basic support)
- ✅ **Rust** - rustfmt, cargo test (basic support)

---

## Examples

### Example 1: React Web App
```bash
cd my-react-app
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev

# Claude now handles:
# ✓ Auto-format with prettier
# ✓ Auto-test with jest
# ✓ 80% coverage enforcement
# ✓ Security scanning
```

### Example 2: Python API
```bash
cd my-fastapi-project
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev

# Claude now handles:
# ✓ Auto-format with black + isort
# ✓ Auto-test with pytest
# ✓ Type hints enforcement
# ✓ Security scanning
```

---

## Documentation

### For Plugin Users

| Guide | Purpose |
|-------|---------|
| [QUICKSTART.md](plugins/autonomous-dev/QUICKSTART.md) | Get running in 2 minutes |
| [plugins/autonomous-dev/README.md](plugins/autonomous-dev/README.md) | Complete plugin documentation |
| [plugins/autonomous-dev/docs/](plugins/autonomous-dev/docs/) | All user guides (commands, GitHub, testing, troubleshooting, etc.) |

**Key docs:**
- [COMMANDS.md](plugins/autonomous-dev/docs/COMMANDS.md) - Complete command reference (21 commands)
- [commit-workflow.md](plugins/autonomous-dev/docs/commit-workflow.md) - Progressive commit workflow
- [TROUBLESHOOTING.md](plugins/autonomous-dev/docs/TROUBLESHOOTING.md) - Common issues & solutions
- [GITHUB_AUTH_SETUP.md](plugins/autonomous-dev/docs/GITHUB_AUTH_SETUP.md) - GitHub integration setup

### For Contributors

| Guide | Purpose |
|-------|---------|
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development workflow & file locations |
| [docs/](docs/) | Development documentation (architecture, code review, implementation status) |
| [.claude/PROJECT.md](.claude/PROJECT.md) | Project architecture & goals |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

---

## 🔧 Troubleshooting

### Commands not available after `/plugin install`

**Solution:** Exit and restart Claude Code (Cmd+Q or Ctrl+Q)

Claude Code needs a restart to load the plugin commands. After restarting:

```bash
# Test by typing:
/test
/auto-implement
/align-project

# All 8 commands should appear in autocomplete
```

### Feature request was BLOCKED

**This is intentional!** The orchestrator validates alignment with PROJECT.md.

**Example block:**
```
❌ BLOCKED: Feature not aligned with PROJECT.md

PROJECT.md SCOPE: [Lists IN/OUT of scope items]
Your Request: "implement mobile app"
Issue: Mobile app is OUT of scope

Resolution:
1. Update PROJECT.md SCOPE to include mobile apps
2. Modify request to align with current SCOPE
3. Don't implement (feature is out of scope)
```

**Why blocks happen:**
- ✅ Feature doesn't serve project GOALS
- ✅ Feature is explicitly OUT of SCOPE
- ✅ Feature violates CONSTRAINTS (tech limits)
- ✅ Feature doesn't fit ARCHITECTURE

**What to do:**
1. Read the block message carefully
2. Choose option: Update PROJECT.md OR modify feature
3. Try again with aligned request

**This is a feature, not a bug!** Blocking prevents scope creep and ensures work aligns with strategic goals.

### Still not working after restart?

**Verify installation:**

```bash
# In Claude Code, check installed plugins
/plugin list
# Should show: autonomous-dev

# If not listed, reinstall:
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
# Exit and restart Claude Code (Cmd+Q or Ctrl+Q)
```

**If commands still don't appear:**

1. **Check Claude Code version**: Must be 2.0.0 or higher
   ```bash
   /help
   ```

2. **Completely reinstall**:
   ```bash
   /plugin uninstall autonomous-dev
   # Exit Claude Code (Cmd+Q or Ctrl+Q)
   # Reopen Claude Code
   /plugin install autonomous-dev
   # Exit Claude Code again
   # Reopen Claude Code
   # Commands should now appear
   ```

3. **GitHub Installation Issues**: If marketplace install fails, report at [GitHub Issues](https://github.com/akaszubski/autonomous-dev/issues)

### My PROJECT.md alignment is failing

**Cause:** PROJECT.md is missing required sections or malformed.

**Fix:**
```bash
# 1. Check PROJECT.md structure
cat PROJECT.md | grep -E "^## (GOALS|SCOPE|CONSTRAINTS|ARCHITECTURE)"
# Should show all 4 sections

# 2. If missing sections, use template
cp .claude/settings.local.json PROJECT.md  # Copy template
# Edit PROJECT.md to add all 4 required sections

# 3. Re-run work
/auto-implement "your feature"
```

**Required sections in PROJECT.md:**
- `## GOALS` - What success looks like
- `## SCOPE` - What's in/out of scope
- `## CONSTRAINTS` - Technical/business limits
- `## ARCHITECTURE` - How system works

### Pre-commit hooks are blocking my commits

**This is intentional!** Hooks enforce quality standards.

**Common blocks:**
- ❌ Tests failing → Run `/test` to see failures, fix code
- ❌ Security scan failing → `security-auditor` found issues, fix code
- ❌ Coverage < 80% → Write more tests
- ❌ Code not formatted → Run `/format` or let hook auto-fix
- ❌ PROJECT.md alignment → Run `/align-project`

**To fix:**
1. Read the hook error message
2. Run `/test` to debug
3. Fix the issue
4. Run `git add .` and try committing again

**Hooks cannot be bypassed** (unless you edit `.claude/settings.local.json` to disable)

---

## FAQ

**Q: Will it overwrite my existing code?**
A: No! The plugin only creates `PROJECT.md` at your project root (via `/setup`). Your code is untouched.

**Q: Where does the plugin install?**
A: Plugin files install to Claude Code's plugin directory (managed automatically). You don't need to manage these files. The only file in your project is `PROJECT.md` (at root).

**Q: What about the `.claude/` directory?**
A: **You don't need it!** All commands work without `.claude/`. Advanced users can create `.claude/` for project-specific customizations (agent overrides, hooks), but 99% of users never need this.

**Q: Does this send my code anywhere?**
A: No. Everything runs locally. Hooks are Python scripts on your machine.

**Q: Do I need to run setup after installing?**
A: **No!** All commands work immediately after install + restart. Setup is only for advanced users who want automatic hooks (auto-format on save).

**Q: How do I uninstall?**
A: `/plugin uninstall autonomous-dev` then **exit and restart Claude Code**

**Q: How do I update?**
A:
1. `/plugin uninstall autonomous-dev`
2. **Exit and restart Claude Code (required!)**
3. `/plugin install autonomous-dev`
4. **Exit and restart again**

**Q: Why do I need to restart Claude Code after installing/uninstalling?**
A: Claude Code caches plugin files. Restarting ensures changes take effect and prevents conflicts between versions.

**Q: Is this beginner-friendly?**
A: Yes! Just install and start coding. Claude handles the rest.

---

## Requirements

- **Claude Code**: 2.0.0 or higher
- **Python**: 3.11+ (for hooks)
- **Git**: For version control features

---

## Support

- **Issues**: [GitHub Issues](https://github.com/akaszubski/autonomous-dev/issues)
- **Discussions**: [GitHub Discussions](https://github.com/akaszubski/autonomous-dev/discussions)

---

## License

MIT License - See [LICENSE](LICENSE)

---

## Credits

Created by [@akaszubski](https://github.com/akaszubski)

Powered by [Claude Code 2.0](https://claude.com/claude-code)
