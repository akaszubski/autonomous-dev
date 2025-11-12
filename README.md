# Claude Code Autonomous Development Plugin

**Last Updated**: 2025-11-09
**Version**: v3.8.1 (Automatic Hook Activation in /update-plugin + Phase 2.5)
**Status**: Production-ready with Command-Driven SDLC + Unified Sync + Performance Optimization + Security Hardening + Automatic Hook Activation

> **User Intent (v3.0+)**: *"I speak requirements and Claude Code delivers first-grade software engineering in minutes by following all necessary SDLC steps (research, plan, TDD, implement, review, security, docs) — automated and accelerated via AI, not shortcuts."*
>
> **📘 Maintenance**: See `docs/MAINTAINING-PHILOSOPHY.md` for keeping the core philosophy active as you iterate

Production-ready plugin with **dual-layer architecture** (Hook Enforcement + Agent Intelligence), **PROJECT.md-first alignment**, and **command-driven workflow**.

**What it does**:
- **Layer 1 (Hooks)**: Automatically validates PROJECT.md alignment, security, tests, and docs on every commit — **guaranteed enforcement**
- **Layer 2 (Agents)**: Provides AI assistance via explicit commands (`/auto-implement` or individual agents) — researches patterns, plans architecture, reviews code — **intelligent enhancement**

🛡️ **Hook-Based Enforcement** • 🤖 **18 AI Specialists** • 📚 **19 Active Skills** • 🧠 **Command Coordination** • 🔒 **Security Scanning** • 📋 **18 Commands** • 🔧 **27 Libraries**

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

2. Run /auto-implement command
   └─> Example: /auto-implement "Add user authentication"

3. Command validates alignment
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

## 🏗️ How It Works: Two-Layer Architecture

autonomous-dev combines **deterministic enforcement** (hooks) with **intelligent assistance** (agents):

### Layer 1: Hook-Based Enforcement (Automatic, 100% Reliable)

**28 Python hooks** run on every commit to enforce quality gates:

```
Developer commits code
    ↓
Pre-commit hooks execute (AUTOMATIC)
    ├─ validate_project_alignment.py → Checks PROJECT.md alignment
    ├─ security_scan.py → Scans for secrets/vulnerabilities
    ├─ auto_generate_tests.py → Generates missing tests
    ├─ auto_update_docs.py → Updates documentation
    ├─ validate_docs_consistency.py → Validates docs accuracy
    └─ auto_fix_docs.py → Fixes documentation issues
    ↓
If ALL pass → Commit allowed ✅
If ANY fail → Commit blocked ❌ (Claude sees errors and fixes)
```

**What's guaranteed:**
- ✅ PROJECT.md alignment enforced
- ✅ Security validated (no secrets, no vulnerabilities)
- ✅ Tests exist (auto-generated if missing)
- ✅ Documentation synchronized
- ✅ File organization enforced
- ✅ Code quality validated

**Hooks run 100% of the time.** No exceptions.

### Layer 2: Agent-Based Intelligence (Optional, AI-Enhanced)

**18 specialist agents** (orchestrator removed v3.2.2) provide expert assistance when invoked via `/auto-implement`:

```
User: /auto-implement "implement JWT authentication"
    ↓
/auto-implement command
    ├─ Validates PROJECT.md alignment (required)
    ├─ Invokes researcher (finds JWT best practices)
    ├─ Invokes planner (designs auth architecture)
    ├─ Invokes test-master (creates test strategies)
    ├─ Invokes implementer (writes code)
    ├─ Invokes reviewer (reviews quality)
    ├─ Invokes security-auditor (checks vulnerabilities)
    └─ Invokes doc-master (updates documentation)
    ↓
Claude coordinates 7-agent workflow
    ↓
Pre-commit hooks validate (AUTOMATIC, GUARANTEED)
    ↓
Professional-quality code with AI enhancement
```

**What's enhanced:**
- 🤖 AI-researched best practices (when invoked)
- 🤖 AI-designed architectures (when invoked)
- 🤖 AI-generated test strategies (when invoked)
- 🤖 AI-enhanced code quality (when invoked)

**Agents run conditionally** — Claude decides which agents to invoke based on feature complexity.

### Key Distinction

| What | How | Reliability |
|------|-----|-------------|
| **Hooks** | Automatic validation on every commit | 100% guaranteed |
| **Agents** | Optional AI assistance when invoked | Conditional (adaptive) |

**Result**: Professional quality (hooks) + Expert intelligence (agents)

### Layer 3: Skills-Based Knowledge (19 Active Skills)

**Status**: 21 active skill packages using progressive disclosure architecture (Issue #35: All 18 agents now actively reference skills)

**How it works**:
- **Agent Integration**: All 18 agents reference relevant skills in their prompts (3-8 skills each)
- Skills are **first-class citizens** in Claude Code 2.0+ (not anti-pattern)
- **Progressive disclosure**: Metadata stays in context (~200 bytes/skill), full content loaded only when needed
- **Auto-activate**: Based on task keywords and patterns
- **Eliminates context bloat**: Only loads relevant skills, can scale to 100+ skills
- **49 skill references** across all agents (18 unique skills referenced)

**Available Skills by Category**:

**Core Development (6)**:
- 🎯 **api-design** - REST API patterns, versioning, error handling
- 🏗️ **architecture-patterns** - System design, ADRs, trade-offs
- 👀 **code-review** - Quality assessment, feedback guidelines
- 🗄️ **database-design** - Schema, migrations, ORM patterns
- ✅ **testing-guide** - TDD methodology, coverage, regression
- 🔒 **security-patterns** - API keys, validation, OWASP

**Workflow & Automation (4)**:
- 🔀 **git-workflow** - Commit conventions, branching, PRs
- 🐙 **github-workflow** - Issues, milestones, automation
- 📋 **project-management** - PROJECT.md, goals, sprints
- 📖 **documentation-guide** - Docs standards, consistency

**Code & Quality (4)**:
- 🐍 **python-standards** - PEP 8, type hints, formatting
- 📊 **observability** - Logging, debugging, profiling
- ⚖️ **consistency-enforcement** - Documentation drift prevention
- 📁 **file-organization** - Project structure standards

**Validation & Analysis (5)**:
- 🔍 **research-patterns** - Research methodology
- 🧠 **semantic-validation** - GenAI-powered validation
- 🔗 **cross-reference-validation** - Link checking
- ⏰ **documentation-currency** - Stale doc detection
- 💡 **advisor-triggers** - Critical analysis patterns

---

## Quick Start

### Installation (Copy-Paste One Command)

**In your project folder, run:**

```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

**That's it.** The script handles everything:
- ✅ Checks if plugin installed (guides you if not)
- ✅ Copies files to your project
- ✅ Tells you next steps

**First time?** Script will say:
```
❌ Plugin not found
Run these commands in Claude Code:
  /plugin marketplace add akaszubski/autonomous-dev
  /plugin install autonomous-dev
Restart Claude Code, then run this script again.
```

**After following those steps**, run the curl command again and you're done!

---

### Keeping Updated (Easy)

**When new version released:**

```bash
# In your project
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

**Same command!** Always gets latest from GitHub.

Or use the built-in command:
```bash
/update-plugin  # Inside Claude Code
```

Both do the same thing - your choice!

---

### Why This Works

**If you prefer to install the plugin yourself first:**

**Step 1: Install plugin via marketplace**
```bash
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
```

**Step 2: Restart Claude Code**
- Press **Cmd+Q** (Mac) or **Ctrl+Q** (Windows/Linux)
- Wait for application to close completely

**Step 3: Bootstrap your project**
```bash
# In your project root
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

**Step 4: Restart Claude Code again**
- Press **Cmd+Q** (Mac) or **Ctrl+Q** (Windows/Linux)
- Reopen Claude Code

**Done!** All 18 commands now available.

**What the bootstrap does**: Copies plugin commands, hooks, and templates to your project's `.claude/` directory. This is required because Claude Code currently needs these files locally to discover them.

**Optional: Run setup wizard**
```bash
/setup
```
This configures automatic hooks (auto-format on save, auto-test on commit) and creates PROJECT.md from template.

### What You Get (18 Commands)

**Core Commands (9)**:
✅ `/auto-implement` - Full 7-agent SDLC workflow
✅ `/align-project` - Find & fix misalignment between goals and code
✅ `/align-claude` - Check/fix documentation drift
✅ `/status` - Track strategic goal progress with AI recommendations
✅ `/setup` - Interactive project configuration
✅ `/sync` - Unified sync (auto-detects: dev environment, marketplace, or plugin dev) - GitHub #47
✅ `/health-check` - Verify all components loaded and working
✅ `/pipeline-status` - Track /auto-implement workflow progress
✅ `/update-plugin` - Interactive plugin update with automatic hook activation - GitHub #50 Phase 2.5

**Individual Agent Commands (7)** - Per GitHub #44:
✅ `/research` - Research patterns and best practices
✅ `/plan` - Architecture and implementation planning
✅ `/test-feature` - TDD test generation
✅ `/implement` - Code implementation
✅ `/review` - Code quality review
✅ `/security-scan` - Security vulnerability scan
✅ `/update-docs` - Documentation synchronization

**Utility Commands (2)**:
✅ `/test` - Run all automated tests (pytest wrapper)
✅ `/uninstall` - Remove or disable plugin

### Verify Installation

```bash
/health-check
```

Should show all 18 commands loaded and working ✅:
- Core (9): `/auto-implement`, `/align-project`, `/align-claude`, `/setup`, `/sync`, `/status`, `/health-check`, `/pipeline-status`, `/update-plugin`
- Individual Agents (7): `/research`, `/plan`, `/test-feature`, `/implement`, `/review`, `/security-scan`, `/update-docs`
- Utility (2): `/test`, `/uninstall`

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

### Git Automation Configuration (Optional)

**Enable automatic git operations in /auto-implement workflow:**

By default, `/auto-implement` stops after documentation sync (Step 6). You can optionally enable Step 7 to automatically commit, push, and create PRs via SubagentStop hook.

**Setup:**

To enable automatic git operations after `/auto-implement` completes, set environment variables in `.env`:

```bash
# 1. Create or edit .env in your project root
vim .env

# 2. Add these lines
AUTO_GIT_ENABLED=true        # Enable automatic git operations (default: false)
AUTO_GIT_PUSH=true           # Enable automatic push to remote (default: false)
AUTO_GIT_PR=true             # Enable automatic PR creation (default: false)
```

**How it works:**

When quality-validator agent completes (last validation step), the SubagentStop hook automatically:

- ✅ Invokes commit-message-generator agent (creates conventional commit message)
- ✅ Stages all changes and creates commit with agent-generated message
- ✅ Pushes to feature branch (if AUTO_GIT_PUSH=true)
- ✅ Creates PR on GitHub (if AUTO_GIT_PR=true and gh CLI installed)

**Safety features:**
- Consent-based: Disabled by default (no behavior change without opt-in)
- Graceful degradation: Works without git/gh CLI (provides manual fallback instructions)
- Prerequisite checks: Validates git installation, config, merge conflicts, uncommitted changes
- No credential logging: Never logs API keys or passwords
- Security validated: Subprocess calls prevent command injection, JSON parsing is safe

**Prerequisites:**
- git CLI installed and configured (user.name and user.email)
- Optional: gh CLI for PR creation (install from https://github.com/cli/cli)
- Optional: GitHub token in .env if gh CLI not in $PATH (GITHUB_TOKEN)

**Troubleshooting:**
- If push fails: Commit still succeeds (graceful degradation)
- If gh not available: PR creation skipped (manual instructions provided)
- If git config missing: Error message shows how to fix (`git config user.name "Your Name"`)

### Updating

**Option 1: Interactive Update (Recommended - Phase 2.5)**

```bash
/update-plugin
# Interactive prompts guide you through:
# 1. Version check (shows current vs available)
# 2. Automatic backup creation (in /tmp)
# 3. Confirmation prompt
# 4. Update with automatic rollback on failure
# 5. Hook activation (adds recommended hooks to settings.local.json)
# 6. Verification (version + file validation)
# 7. Backup cleanup after success

# Exit and restart Claude Code (REQUIRED!)
# Press Cmd+Q (Mac) or Ctrl+Q (Linux/Windows)
```

**Features**:
- ✅ Automatic backup before update (with rollback on failure)
- ✅ Hook activation - adds recommended hooks to settings.local.json (Phase 2.5)
- ✅ Smart settings merge - preserves your existing customizations
- ✅ Verification - confirms update succeeded
- ✅ Non-interactive mode available (`--yes` flag for scripts)

**CLI Options**:
```bash
/update-plugin --check-only          # Check for updates without updating
/update-plugin --yes                 # Skip confirmation prompts
/update-plugin --no-backup           # Skip backup (not recommended)
/update-plugin --activate-hooks      # Enable hook activation (default)
/update-plugin --no-activate-hooks   # Skip hook activation
```

**Option 2: Manual Update (Traditional)**

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

**IMPORTANT**: You must exit and restart Claude Code after updates!

**Hook Activation (Phase 2.5)**:
The `/update-plugin` command now automatically activates recommended hooks in your `settings.local.json`:
- **UserPromptSubmit**: `display_project_context.py`, `enforce_command_limit.py`
- **SubagentStop**: `log_agent_completion.py`, `auto_update_project_progress.py`
- **PrePush**: `auto_test.py`

Your existing customizations are preserved - the update only adds new hooks, never removes your settings.

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
# Command validates against PROJECT.md, then runs 7-agent pipeline

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

### 18 Specialized Agents (Orchestrator Removed v3.2.2)

**Core Workflow Agents (9)** - Execute the main SDLC pipeline (orchestrator removed v3.2.2, Claude coordinates directly):
- **advisor** `sonnet` - Critical thinking and risk validation before decisions
- **researcher** `sonnet` - Web research for patterns, best practices, and existing solutions
- **planner** `opus` - Architecture & implementation planning (complex analysis)
- **test-master** `sonnet` - TDD specialist (writes failing tests first)
- **implementer** `sonnet` - Code implementation (makes tests pass)
- **reviewer** `sonnet` - Quality gate checks (code review)
- **security-auditor** `haiku` - Security scanning and vulnerability detection
- **doc-master** `haiku` - Documentation sync and CHANGELOG updates
- **quality-validator** `sonnet` - GenAI-powered feature quality and standards validation

> **Model Strategy**: Opus for complex planning (1 step), Sonnet for general work (7 steps), Haiku for simple checks (2 steps) = optimized cost/quality

**Utility Agents (9)** - Support core workflow with validation, setup, and automation:
- **alignment-validator** `sonnet` - PROJECT.md alignment validation (features vs goals/scope/constraints)
- **alignment-analyzer** `sonnet` - Detailed conflict analysis (PROJECT.md vs reality/code/docs)
- **project-progress-tracker** `sonnet` - Track and update PROJECT.md goal completion metrics
- **project-status-analyzer** `sonnet` - Real-time project health monitoring and recommendations
- **commit-message-generator** `sonnet` - Conventional commit message generation
- **pr-description-generator** `sonnet` - Comprehensive PR descriptions from implementation artifacts
- **setup-wizard** `sonnet` - Intelligent setup and tech stack detection/configuration
- **project-bootstrapper** `sonnet` - Analyze existing codebases and generate/update PROJECT.md
- **sync-validator** `sonnet` - Smart development environment sync and conflict detection

### 19 Active Skills (Progressive Disclosure Architecture)

**Status**: 21 active skill packages using Claude Code 2.0+ progressive disclosure

**How it works**: Skills use progressive disclosure - metadata stays in context (minimal overhead), full skill content loads only when needed. This architecture allows scaling to 100+ skills without context bloat.

**Categories**: Core Development (6), Workflow & Automation (4), Code & Quality (4), Validation & Analysis (5)

### 18 Slash Commands

All commands are independently discoverable with autocomplete:

**Core Commands** (8):
- `/auto-implement` - Full 7-agent SDLC workflow
- `/align-project` - Analyze & fix PROJECT.md alignment (menu: report/fix/preview/cancel)
- `/align-claude` - Check and fix CLAUDE.md alignment with codebase
- `/setup` - Interactive project setup wizard
- `/sync` - Unified sync (auto-detects: dev environment, marketplace, or plugin dev) - GitHub #47
- `/status` - Track strategic goal progress with AI recommendations
- `/health-check` - Verify all components loaded and working
- `/pipeline-status` - Track /auto-implement workflow progress

**Individual Agent Commands** (7) - Per GitHub #44:
- `/research` - Research patterns and best practices
- `/plan` - Architecture and implementation planning
- `/test-feature` - TDD test generation
- `/implement` - Code implementation
- `/review` - Code quality review
- `/security-scan` - Security vulnerability scan
- `/update-docs` - Documentation synchronization

**Utility Commands** (2):
- `/test` - Run all automated tests (pytest wrapper)
- `/uninstall` - Remove or disable plugin

### Shared Libraries (8 Core + 19 Utilities = 27 Total)

The plugin includes reusable Python libraries for common operations:

**Core Libraries (8)**:

1. **security_utils.py** (628 lines) - Security validation and audit logging
   - Path validation (CWE-22, CWE-59 protection)
   - Input sanitization and length validation
   - Thread-safe audit logging to `logs/security_audit.log`
   - Used by: All security-critical operations

2. **project_md_updater.py** (247 lines) - Atomic PROJECT.md updates
   - `update_goal_progress()` - Update goal completion percentages
   - Atomic writes with backup and rollback
   - Merge conflict detection
   - Used by: auto_update_project_progress.py hook

3. **version_detector.py** (531 lines) - Semantic version management
   - `Version` class with comparison operators
   - `detect_version_mismatch()` - Compare marketplace vs project versions
   - Pre-release version support
   - Used by: sync_dispatcher.py, validate_marketplace_version.py

4. **orphan_file_cleaner.py** (514 lines) - Orphaned file cleanup
   - `detect_orphans()` - Find orphaned commands/hooks/agents
   - `cleanup_orphans()` - Remove with dry-run/confirm/auto modes
   - Audit logging to `logs/orphan_cleanup_audit.log`
   - Used by: sync_dispatcher.py for marketplace sync

5. **sync_dispatcher.py** (976 lines) - Intelligent sync orchestration
   - Auto-detects sync mode (marketplace/env/plugin-dev)
   - Version detection and orphan cleanup integration
   - Non-blocking enhancement pattern
   - Used by: /sync command

6. **validate_marketplace_version.py** (371 lines) - Marketplace version CLI
   - CLI interface for version comparison
   - JSON and human-readable output formats
   - Security validation and audit logging
   - Used by: /health-check command

7. **plugin_updater.py** (658 lines) - Interactive plugin updates
   - `PluginUpdater` class with backup/rollback support
   - Hook activation integration (Phase 2.5)
   - Verification of updates with version + file checks
   - Used by: /update-plugin command

8. **hook_activator.py** (508 lines) - Automatic hook activation
   - `HookActivator` class for settings.local.json management
   - Smart settings merge (preserves customizations)
   - Atomic writes with validation
   - Used by: plugin_updater.py (Phase 2.5 feature)

**Utility Libraries (19)**: Additional helper modules for git operations, performance profiling, session tracking, and other specialized tasks.

**Design Patterns**:
- Progressive enhancement: String → Path → Whitelist validation
- Non-blocking enhancements: Failures don't block core operations
- Atomic file operations: tempfile.mkstemp() + rename pattern
- Security-first: All paths validated via security_utils
- Audit logging: Thread-safe JSON logging for all critical operations

### Automation Hooks (39 Hook Files: 24 Enforcement + 15 Utilities)

All enforcement hooks are **pre-commit** (run before code is committed). They validate quality automatically.

**Core Blocking Hooks (9)** - Run by default, block commits if failed:
- **validate-project-alignment** - PROJECT.md must exist with GOALS/SCOPE/CONSTRAINTS before committing
- **enforce-pipeline-complete** - Validates 7 agents ran when using /auto-implement (v3.2.2+)
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
- **enforce-command-limit** - Monitors command count growth
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

STEP 8: OPTIONAL GIT AUTOMATION (if enabled):
   │
   ├─> commit-message-generator - Conventional commit message from artifacts
   ├─> pr-description-generator - Comprehensive PR description with architecture/testing/security
   ├─> Automatic commit with agent-generated message (requires git)
   ├─> Automatic push to feature branch (requires AUTO_GIT_PUSH=true)
   └─> Automatic PR creation (requires AUTO_GIT_PR=true + gh CLI)

   └─> Features:
       * Consent-based: Only runs if AUTO_GIT_ENABLED=true in .env
       * Graceful degradation: Commits without pushing, PRs without gh CLI
       * No manual git commands needed
       * Safe: Validates prerequisites (git config, merge conflicts, uncommitted changes)
   ↓

Total Time: ~30 minutes + optional 2-3 minutes for git automation
All SDLC steps completed, code committed and pushed (if enabled)
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
   ✅ Code pushed to feature branch (if AUTO_GIT_PUSH=true)
   ✅ GitHub PR created (if AUTO_GIT_PR=true)
   ❌ If any check fails → Commit blocked (Claude can fix)
```

### Validation Logic & Feature Blocking

The `/auto-implement` command validates every feature request using a **4-check system**:

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

**Understanding the Four Locations:**

```
┌──────────────────────────────────────────────────────────┐
│ 1. GITHUB (Remote - Source of Truth)                    │
│    https://github.com/akaszubski/autonomous-dev         │
│    - Public repo where code lives                       │
│    - Users download from here                           │
└──────────────────────────────────────────────────────────┘
                    ↓ git clone/pull
┌──────────────────────────────────────────────────────────┐
│ 2. DEV FOLDER (Local - Where You Edit)                  │
│    ~/Documents/GitHub/autonomous-dev/                   │
│    - Your local git repo                                │
│    - WHERE YOU EDIT CODE ← START HERE                   │
│    - plugins/autonomous-dev/commands/                   │
│    - plugins/autonomous-dev/hooks/                      │
└──────────────────────────────────────────────────────────┘
                    ↓ sync_to_installed.py
┌──────────────────────────────────────────────────────────┐
│ 3. INSTALLED PLUGIN (Global - Shared Across Projects)   │
│    ~/.claude/plugins/marketplaces/autonomous-dev/       │
│    - Installed once per machine                         │
│    - Updated via sync_to_installed.py (dev)             │
│    - Updated via /plugin update (users)                 │
└──────────────────────────────────────────────────────────┘
                    ↓ install.sh
┌──────────────────────────────────────────────────────────┐
│ 4. PROJECT .claude/ (Local - Per Project)               │
│    /path/to/your-project/.claude/                       │
│    - WHERE CLAUDE CODE READS FROM ← COMMANDS RUN HERE   │
│    - One copy per project                               │
│    - Updated via install.sh or /update-plugin           │
└──────────────────────────────────────────────────────────┘
```

**After You Edit Code:**

```bash
# 1. Edit files in DEV FOLDER
vim ~/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/commands/setup.md

# 2. Commit to git (DEV FOLDER → GITHUB)
git add .
git commit -m "fix: update setup command"
git push

# 3. Sync to INSTALLED PLUGIN (DEV FOLDER → INSTALLED PLUGIN)
python plugins/autonomous-dev/hooks/sync_to_installed.py

# 4. Update test project (INSTALLED PLUGIN → PROJECT .claude/)
cd ~/path/to/test-project
bash ~/Documents/GitHub/autonomous-dev/install.sh

# 5. Restart Claude Code
# Press Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)
# Reopen Claude Code

# 6. Test your changes in the project
/setup  # Or whatever command you changed
```

**Quick Reference:**

| What Changed | What to Run | Where |
|--------------|-------------|-------|
| Edited code | `sync_to_installed.py` | In autonomous-dev repo |
| Synced to installed | `install.sh` | In test project |
| Bootstrapped project | Restart Claude Code | - |

**IMPORTANT**: Nothing syncs automatically!
- ❌ Pushing to GitHub doesn't update your installed plugin
- ❌ Syncing to installed doesn't update project .claude/
- ✅ You must manually run sync → bootstrap → restart

---

### User vs Developer Workflows

**Users (Installing/Updating the Plugin):**
```bash
# First time install
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
# Restart Claude Code
cd /path/to/project
bash <(curl -sSL https://raw.githubusercontent.com/.../install.sh)
# Restart Claude Code

# Updating to new version
/plugin update autonomous-dev
# Restart Claude Code
/update-plugin
# Restart Claude Code
```

**Developers (You, Editing the Code):**
```bash
# After editing code
git add . && git commit -m "fix: ..." && git push
python plugins/autonomous-dev/hooks/sync_to_installed.py
cd /path/to/test-project
bash ~/Documents/GitHub/autonomous-dev/install.sh
# Restart Claude Code
```

**Key Difference:**
- **Users**: Get code from GitHub via `/plugin install/update`
- **Developers**: Sync local changes via `sync_to_installed.py`

---

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
ls plugins/autonomous-dev/commands/*.md | wc -l   # Should be 18

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
| **Feature time** | 17-27 min per feature (vs 7+ hrs manual) | Time feature from request to merged PR (parallel validation saves 3 min) |
| **SDLC compliance** | 100% of features follow all 7 steps | /auto-implement enforces all steps |
| **Scope drift** | 0% (zero features outside SCOPE) | Pre-commit hook blocks misaligned work |
| **Test coverage** | 80%+ (enforced minimum) | Coverage report in test output |
| **Security scans** | 100% pass rate | Security-auditor completes successfully |
| **Documentation** | 100% synchronized | Docs validation hook passes |
| **Commit quality** | 100% follow conventional commits | Commit message generator enforces format |

### For Plugin Development

| Metric | Target | How to Check |
|--------|--------|-------------|
| **Agent count** | 19 (8 core + 6 analysis + 5 automation) | `ls plugins/autonomous-dev/agents/ | wc -l` |
| **Command count** | 18 (9 core + 7 individual + 2 utility) | `ls plugins/autonomous-dev/commands/ | wc -l` |
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
- See command list above - Complete command reference (18 commands: 9 core + 7 individual + 2 utility)
- [commit-workflow.md](plugins/autonomous-dev/docs/commit-workflow.md) - Progressive commit workflow
- [TROUBLESHOOTING.md](plugins/autonomous-dev/docs/TROUBLESHOOTING.md) - Common issues & solutions
- [GITHUB_AUTH_SETUP.md](plugins/autonomous-dev/docs/GITHUB_AUTH_SETUP.md) - GitHub integration setup
- [SECURITY.md](docs/SECURITY.md) - Security utilities, path validation, audit logging

### For Python Developers (Shared Libraries API)

The `plugins/autonomous-dev/lib/` directory contains 5 production-ready shared libraries for building autonomous development tools:

**Core Libraries:**
- `security_utils.py` - Path validation, input sanitization, audit logging (CWE-22, CWE-59 protection)
- `project_md_updater.py` - Atomic PROJECT.md updates with merge conflict detection
- `version_detector.py` - Semantic version parsing and comparison (v3.7.1+)
- `orphan_file_cleaner.py` - Orphaned file detection and cleanup (v3.7.1+)
- `sync_dispatcher.py` - Intelligent sync orchestration with version detection and cleanup (v3.7.1+)

**Example: Using sync_marketplace() API (v3.7.1+)**

```python
from pathlib import Path
from plugins.autonomous_dev.lib.sync_dispatcher import sync_marketplace

# Run marketplace sync with version detection and optional cleanup
result = sync_marketplace(
    project_root="/path/to/project",
    marketplace_plugins_file=Path("~/.claude/plugins/installed_plugins.json"),
    cleanup_orphans=True,  # Optional: detect and cleanup orphaned files
    dry_run=True,          # Optional: preview cleanup without deleting
)

# Access comprehensive results
print(result.summary)  # Human-readable summary with version and cleanup info

# Check version comparison
if result.version_comparison:
    print(f"Status: {result.version_comparison.status}")
    print(f"Versions: {result.version_comparison.project_version} → {result.version_comparison.marketplace_version}")

# Check cleanup results
if result.orphan_cleanup:
    print(f"Orphans detected: {result.orphan_cleanup.orphans_detected}")
    print(f"Orphans deleted: {result.orphan_cleanup.orphans_deleted}")
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed library documentation and usage patterns.

### For Contributors

| Guide | Purpose |
|-------|---------|
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development workflow & file locations |
| [docs/](docs/) | Development documentation (architecture, code review, implementation status) |
| [.claude/PROJECT.md](.claude/PROJECT.md) | Project architecture & goals |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [docs/SECURITY.md](docs/SECURITY.md) | Security architecture, utilities, vulnerability fixes (v3.4.1+) |

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

# All 18 commands should appear in autocomplete
```

### Feature request was BLOCKED

**This is intentional!** The `/auto-implement` command validates alignment with PROJECT.md.

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

### Setup says "Plugin not installed or corrupted"

**NEW in latest version**: Setup now shows exactly what's missing!

**Example error message:**
```
❌ Plugin not installed or corrupted!

Missing directories: templates

To fix:
  1. Reinstall plugin (recommended):
     /plugin uninstall autonomous-dev
     (exit and restart Claude Code)
     /plugin install autonomous-dev
     (exit and restart Claude Code)

  2. Or verify you've restarted Claude Code after install
```

**What this means:**
- The plugin is partially installed or corrupted
- The error shows which directories are missing (hooks, commands, or templates)
- Follow the reinstall instructions to fix

**Common causes:**
1. Didn't restart Claude Code after `/plugin install`
2. Plugin install failed mid-way
3. Accidentally deleted `.claude/` directories

**Solution:** Follow the reinstall steps shown in the error message

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

## 🧪 Testing & Quality Assurance

### Regression Test Suite (v3.5.0+)

The plugin includes a comprehensive, four-tier regression test suite protecting against regressions across all released versions (v3.0+).

**Quick Start**:
```bash
# Run all tests
pytest tests/regression/ -v

# Run only fast tests (smoke + regression, < 30s)
pytest tests/regression/ -m "smoke or regression" -v

# Run in parallel (faster)
pytest tests/regression/ -m "smoke or regression" -n auto -v

# Run with coverage
pytest tests/regression/ --cov=plugins/autonomous-dev --cov-report=html
```

**Four-Tier Architecture**:

| Tier | Speed | Purpose | Count | Run |
|------|-------|---------|-------|-----|
| **Smoke** | < 5s | Critical paths only | 20 | Pre-commit |
| **Regression** | < 30s | Bug/feature protection | 40 | Pre-push |
| **Extended** | 1-5min | Performance, edge cases | 8 | Nightly |
| **Progression** | Variable | Feature evolution tracking | 27 | Optional |

**What's Tested**:
- ✅ Plugin loading & command routing
- ✅ v3.4.1 race condition fix (security)
- ✅ v3.4.0 auto-update PROJECT.md (atomic writes)
- ✅ v3.3.0 parallel validation (3 agents)
- ✅ 35+ security audit findings
- ✅ All public APIs and integrations

**Tools**:
- **pytest-xdist**: Parallel execution across CPU cores (smoke: 25 tests in < 5s)
- **syrupy**: Snapshot testing for output validation
- **pytest-testmon**: Smart test selection (only affected tests run on code changes)

**TDD Workflow**:
```bash
# 1. Write failing test (Red)
pytest tests/regression/regression/test_feature_v3_5_0.py -v
# EXPECTED: FAILED - feature not implemented

# 2. Implement feature (Green)
# ... write code ...

# 3. Run test again (verify pass)
pytest tests/regression/regression/test_feature_v3_5_0.py -v
# EXPECTED: PASSED

# 4. Run full suite (ensure no regressions)
pytest tests/regression/ -m regression -n auto
```

**Coverage Target**: 80%+ across all tiers
- View report: `pytest tests/regression/ --cov-report=html && open htmlcov/index.html`

**More Info**: See [tests/regression/README.md](tests/regression/README.md) for:
- Fixture reference (isolated_project, timing_validator, mocks)
- Writing custom tests
- Troubleshooting & debugging
- Backfill strategy for new features

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
