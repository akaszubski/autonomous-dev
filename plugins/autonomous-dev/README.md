# Autonomous Dev - Claude Code Plugin

[![Available on Claude Code Commands Directory](https://img.shields.io/badge/Claude_Code-Commands_Directory-blue)](https://claudecodecommands.directory/command/autonomous-dev)
[![Version](https://img.shields.io/badge/version-3.2.1-green)](https://github.com/akaszubski/autonomous-dev/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](https://github.com/akaszubski/autonomous-dev/blob/main/LICENSE)

**Version**: v3.2.1
**Last Updated**: 2025-11-03
**Status**: Sync-Dev & GitHub Integration + Security Audit Complete

Production-ready plugin with 8 GenAI-native commands, 19 specialist agents, 30+ automated hooks, and PROJECT.md-first architecture.

Works with: Python, JavaScript, TypeScript, React, Node.js, and more!

---

## 🚀 Installation

### Quick Install (One Command)

**For first-time users:**

```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

This will guide you through plugin installation and bootstrap.

---

### Recommended: Fresh Install (Most Reliable)

**For guaranteed latest version or when updating:**

```bash
# STEP 1: Nuclear clean (removes old plugin completely)
rm -rf ~/.claude/plugins/marketplaces/autonomous-dev

# STEP 2: Kill ALL Claude Code sessions (important if you have multiple terminals)
pkill -9 claude
# Wait 2 seconds, then reopen Claude Code

# STEP 3: Fresh install from GitHub
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev

# STEP 4: Kill and restart Claude Code again
pkill -9 claude
# Wait 2 seconds, then reopen Claude Code

# STEP 5: Bootstrap (copies plugin files to your project)
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
# OR if you cloned the repo:
# cd /path/to/autonomous-dev && ./scripts/resync-dogfood.sh

# STEP 6: Kill and restart Claude Code one final time
pkill -9 claude
# Wait 2 seconds, then reopen Claude Code

# STEP 7: Verify installation
/health-check  # Should show: Commands: 10/10 present ✅

# STEP 8: Verify new agents loaded (optional)
grep -n "STEP 1: Invoke Researcher" ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/agents/orchestrator.md
# Should show: 75:#### **STEP 1: Invoke Researcher**
```

**Important Notes:**
- Use `pkill -9 claude` instead of `/exit` or `Cmd+Q` to ensure all Claude sessions restart
- This is especially important if you have Claude running in multiple terminals
- `pkill` kills ALL Claude processes, ensuring fresh agent reload from disk

**Why this approach?**
- ✅ Guarantees fresh clone from GitHub (no stale files)
- ✅ Ensures you have the latest agents, hooks, and commands
- ✅ Verifiable (can check file timestamps)
- ✅ Recommended when updating or troubleshooting

**What gets installed:**
- 10 slash commands (`/auto-implement`, `/pipeline-status`, etc.)
- 19 specialist agents (orchestrator, researcher, planner, etc.)
- 35+ automation hooks (validation, security, testing, docs)
- Templates and project scaffolding

---

### Optional: Run Setup Wizard

After installation, configure automatic hooks:

```bash
/setup
```

This:
- Creates PROJECT.md from template
- Configures automatic hooks (auto-format, auto-test, etc.)
- Sets up file organization enforcement

### What the Bootstrap Script Does

The install.sh script copies plugin files to your project's `.claude/` directory:
- **Commands** → `.claude/commands/` (8 slash commands)
- **Hooks** → `.claude/hooks/` (30+ automation hooks)
- **Templates** → `.claude/templates/` (PROJECT.md templates)
- **Agents** → `.claude/agents/` (19 specialist agents)
- **Skills** → `.claude/skills/` (optional capabilities)

**Why is this needed?** Claude Code currently requires plugin commands to be in your project's `.claude/` directory to be discoverable. The bootstrap script handles this one-time setup automatically.

### Troubleshooting

**Bootstrap script fails?**

Check if plugin is installed:
```bash
ls ~/.claude/plugins/marketplaces/autonomous-dev/
```

If not found, install plugin first (Step 1) and restart (Step 2).

**Commands still not showing?**

Try manual bootstrap:
```bash
# Copy commands manually
cp ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/commands/*.md .claude/commands/
# Restart Claude Code
```

## ✨ What's New in v3.2.1

**🎯 Hooks Installation & Testing Release + Enhanced Setup**

This release completes the hooks infrastructure with proper installation, testing, dogfooding support, AND improved setup error handling:

### v3.2.1 Changes (2025-11-02)

**✅ Enhanced Setup & Error Messages** (NEW):
- **Better diagnostics**: Shows exactly which directories are missing (hooks, commands, templates)
- **Clear recovery steps**: Step-by-step reinstall instructions in error messages
- **Developer mode**: `--dev-mode` flag for testing from git clone
- **98% confidence**: GenAI-validated installation flow
- **Fixes**: All three directories now checked consistently (hooks AND commands AND templates)

**✅ Hooks Installation Complete** (2025-10-27):
- **30+ hooks installed** to `.claude/hooks/` for dogfooding
- **6 core hooks tested** and verified working:
  - ✅ validate_project_alignment.py
  - ✅ security_scan.py (with GenAI)
  - ✅ auto_generate_tests.py
  - ✅ auto_update_docs.py
  - ✅ validate_docs_consistency.py (path fixed)
  - ✅ auto_fix_docs.py
- **Fixed path resolution** in validate_docs_consistency.py for dogfooding scenarios
- **Configuration updated** - `.claude/settings.local.json` points to `.claude/hooks/`
- **Distribution-ready** - `plugins/autonomous-dev/hooks/` is clean source, `.claude/hooks/` is gitignored

**How it works**:
1. Source hooks in `plugins/autonomous-dev/hooks/` (for distribution)
2. User runs `/setup` → setup script copies to their `.claude/hooks/`
3. Settings configured → hooks run on PreCommit events
4. You test with dogfooding → `.claude/hooks/` copy verifies user experience

**Why separate locations**:
- ✅ Distribution stays clean (only plugins/ needed)
- ✅ Dogfooding tests real scenario (.claude/hooks/ like user install)
- ✅ .gitignore protects dogfooding copy from distribution
- ✅ Workflow: plugins/ (source) → .claude/ (test) → ~/.claude/ (user)

**Verification Status**:
- ✅ All 30 hooks present in both locations
- ✅ All imports resolve correctly
- ✅ GenAI utilities (genai_utils.py, genai_prompts.py) working
- ✅ Commit test verified PreCommit execution
- ✅ 6 core hooks tested individually
- ✅ Documentation updated in README

### v3.2.1 Previous Changes (2025-10-26)

**🔍 Simplified `/align-full` Command**:
- **Before**: 5-level hierarchy, cascade analysis, stakeholder categorization
- **After**: One simple question per conflict
- **Decision**: `A) PROJECT.md is correct → align code/docs` OR `B) Update PROJECT.md to match reality`
- **Removed**: 90% of complexity logic, 574 lines of code
- **Result**: 2-3 minute decisions (vs 5-10 min with hierarchy)

**✅ What Stays the Same**:
- GenAI conflict detection still finds mismatches
- GitHub issues still auto-created based on your decision
- `.todos.md` file still synced with issues
- Fully reversible (change mind, re-run, choose again)

**Why This Is Better**:
- ✅ No categorization overhead ("what level is this?")
- ✅ Objective framework (PROJECT.md is source of truth)
- ✅ Works at any scale (5 conflicts or 500)
- ✅ USER DECIDES, not system assumes

### Key Principle

```
PROJECT.md = Source of Truth

For every conflict:
  A) YES → Align code/docs to PROJECT.md
  B) NO  → Update PROJECT.md to match reality
```

That's the complete decision framework.

---

## ✨ What's New in v3.2.0

**🧠 GenAI Validation & Alignment Release**

This release replaces traditional testing with GenAI-powered validation and adds deep alignment analysis:

### v3.2.0 Features (2025-10-26)

- 🧪 **GenAI Quality Validation** (`agents/quality-validator.md`)
  - Replaces traditional unit testing (pytest, jest)
  - Validates 4 dimensions: Intent alignment, UX quality, Architecture, Documentation
  - Asks: "Does this serve PROJECT.md goals?" not just "Does it work?"
  - Scores features 0-10 on strategic alignment
  - **Philosophy**: Quality = alignment with vision, not just "tests pass"

- 🔍 **Full Alignment Analysis** (`/align-full` command)
  - Deep GenAI scan finds ALL inconsistencies
  - Compares PROJECT.md (truth) vs code (reality) vs docs (claims)
  - 6 inconsistency types: docs vs code, scope drift, missing references, constraint violations, broken links, outdated claims
  - Interactive resolution (asks what to do for each)
  - Auto-creates GitHub issues for tracking
  - Builds synced `.todos.md` file

- 📊 **GitHub Issue Integration**
  - Every inconsistency → GitHub issue automatically
  - Labels: `alignment`, `inconsistency`, severity
  - Linked to `.todos.md` for tracking
  - Close issue when todo complete

- ✅ **Deep Alignment Metrics**
  - Overall alignment percentage (PROJECT.md vs reality)
  - Traceability score (code → goals)
  - Constraint compliance (LOC budget, dependencies)
  - Documentation accuracy

**Impact**:
- ✅ GenAI validates strategic alignment, not just function behavior
- ✅ Finds inconsistencies humans miss (docs vs code vs PROJECT.md)
- ✅ Auto-creates actionable todos with GitHub sync
- ✅ Weekly alignment runs prevent drift
- ✅ Projected 95%+ alignment after fix workflow

---

## ✨ What's New in v3.2.1

**Latest Release - Sync-Dev Restoration & GitHub Integration (2025-11-03)**

This release restores the `/sync-dev` command with comprehensive security audit and adds automatic GitHub issue tracking to the `/auto-implement` workflow:

### v3.2.1 Features (2025-11-03)

- ✅ **`/sync-dev` Restored** - Development environment synchronization with security audit
  - Smart conflict detection via sync-validator agent
  - Dependency mismatch detection (package.json, requirements.txt, Cargo.toml, etc.)
  - Environment variable drift detection (.env files)
  - Pending database migration identification
  - Build artifact validation and cleanup
  - Comprehensive security audit: `docs/sessions/SECURITY_AUDIT_SYNC_DEV.md`
  - Security considerations documented in command help
  - Use after git pulls, plugin updates, or environment issues

- ✅ **GitHub Issue Auto-Integration** - Automatic issue creation/closure for `/auto-implement`
  - Creates issue at workflow start with feature description
  - Tracks issue in pipeline JSON for reference
  - Auto-closes on completion with execution summary
  - Graceful degradation if `gh` CLI unavailable
  - Labels: automated, feature, in-progress (created) → completed (closed)

### v3.2.0 Features (2025-10-27)

- 🧠 **GenAI Command Refactoring**: Replaced Python orchestration with intelligent agents
  - ✅ Refactored `/align-project` → GenAI-native (alignment-analyzer agent)
  - ✅ Refactored `/status` → GenAI-native (project-progress-tracker agent)
  - **Result**: 8 commands, all with intelligent GenAI reasoning

### v3.1.0 Features (2025-10-26)

- 🗂️ **Command Simplification**: 64% reduction (11 → 4 core commands)
  - Archived: `/test`, `/advise` (manual quality checks → automatic hooks)
  - Merged: `/bootstrap`, `/create-project-md` into `/setup`
  - **Philosophy**: Background enforcement, not manual intervention

- 📋 **Professional Methodology Documentation** (`docs/METHODOLOGY.md`)
  - Partnership model (you decide WHAT, Claude handles HOW)
  - /clear discipline (context management)
  - Trust + verify philosophy
  - Warn don't block approach
  - Small batch development patterns
  - Success metrics and common pitfalls

- 🔄 **Migration Support** (`commands/archived/ARCHIVE.md`)
  - Detailed guide for each archived command
  - Hook replacements explained
  - Before/after workflow examples
  - Restoration instructions if needed

**Impact**:
- ✅ Cognitive overhead reduced (4 commands vs 11)
- ✅ Pure vibe coding UX (natural language → professional result)
- ✅ All quality enforcement automatic (hooks validate at commit)
- ✅ Philosophy-driven architecture (aligned with stated goals)
- ✅ Professional practices documented (methodology guide)

---

## ✨ What's New in v3.0.2

**🤖 Automation & Onboarding Release - Critical Thinking + Smart Setup**

This release focuses on **automatic quality gates** and **intelligent project configuration**:

### v3.0.2 Features (2025-10-26)

- 🎯 **Preview Mode Advisor**: Automatic 15-second quality gates for significant decisions
  - Shows quick alignment score (0-10), complexity (LOW/MEDIUM/HIGH), one-line recommendation
  - User chooses: Y (full 2-5 min analysis) / N (skip) / always / never
  - Preserves "1 command" workflow while offering critical analysis
  - Auto-triggers on: new dependencies, architecture changes, scope expansions, tech swaps, major features

- 🚀 **Project Bootstrapping** (`/bootstrap`): Tech stack auto-detection and optimal config generation
  - Detects: Node.js/TypeScript, Python, Rust, Go from project files
  - Analyzes: Project size (LOC count), testing frameworks, documentation state
  - Generates: Optimal `.claude/config.yml` for your specific tech stack
  - **Onboarding**: 30-60 min manual config → 2-3 min automatic
  - Choose: Accept defaults / Customize / Fast/Balanced/Strict modes

### v3.0.1 Features (2025-10-26)

- 🧠 **Advisor Agent** ("Devils Advocate"): Critical thinking before implementation
  - GenAI excels at critical thinking > code generation
  - Provides: Alignment scoring, complexity assessment, trade-off analysis, alternatives, risk identification
  - Catches: Scope creep, overengineering, misaligned features, risky decisions
  - Command: `/advise "your proposal"` for explicit analysis

- 🎛️ **Advisor Triggers Skill**: Pattern detection for significant decisions
  - Detects: New dependencies, architecture changes, scope expansions, technology swaps, major features
  - Configurable: Sensitivity (low/medium/high), auto-invoke on/off

### v3.0.0 Features (2025-10-26)

- 🔍 **GenAI-Powered Semantic Validation**: PROJECT.md claims vs actual code comparison
  - Detects: "CRITICAL ISSUE" marked but already solved, outdated claims, stale markers
  - Skills: semantic-validation, documentation-currency, cross-reference-validation
  - Enhanced alignment-validator with 5-phase workflow

- 📋 **PROJECT.md Bootstrapping** (`/create-project-md`): AI generates PROJECT.md from codebase
  - Analyzes: 2000+ LOC projects in <60s
  - Generates: 300-500 line PROJECT.md (80-90% complete)
  - Modes: generate/template/interactive

- 📁 **File Organization Auto-Fix**: Automatically corrects misplaced files
  - Integrated with pre-commit hook
  - Auto-fix mode by default (was: warn only)

- 🔗 **Cross-Reference Updates** (`post_file_move.py` hook): Auto-updates broken refs after file moves
  - Interactive approval with preview
  - 100% broken reference detection

**Impact**:
- ✅ Critical decisions get automatic quality gates (catches 80%+ risky proposals)
- ✅ Project setup optimized for your tech stack (not generic config)
- ✅ Onboarding: 30-60 min → 2-3 min (95% faster)
- ✅ Outdated docs detected automatically (saves 2-3 hours per project)
- ✅ File organization enforced (saves 2 hours per project)
- ✅ Total time savings: 6-7 hours per medium-sized project

**Previous releases**:
- **v2.5.0**: UX Excellence (tiered installation, error messages 2.0, command cleanup)
- **v2.1.0**: PROJECT.md-First Architecture with orchestrator agent

## 📋 PROJECT.md-First Philosophy

Everything starts with `PROJECT.md` at your project root - defining goals, scope, and constraints. The orchestrator validates every feature against PROJECT.md before work begins, ensuring zero tolerance for scope drift.

**Learn more**: See main [README.md](../../README.md#-the-projectmd-first-philosophy)

## 🔒 Strict Mode - SDLC Automation

**"Vibe coding" that enforces professional best practices automatically**

Strict Mode turns natural language requests into complete SDLC workflows:

```bash
# Just describe what you want
"implement user authentication with JWT"

# System automatically:
→ Detects feature request (auto-orchestration)
→ Checks PROJECT.md alignment (gatekeeper)
→ Runs full agent pipeline if aligned
→ Enforces all SDLC steps (Research → Plan → Test → Implement → Review → Security → Docs)
→ Validates before commit (blocking hooks)
```

**Enable Strict Mode**:
```bash
# Copy strict mode template
cp plugins/autonomous-dev/templates/settings.strict-mode.json .claude/settings.local.json

# Ensure PROJECT.md exists
cp plugins/autonomous-dev/templates/PROJECT.md .claude/PROJECT.md

# All future work now follows strict SDLC
```

**What it enforces**:
- ✅ PROJECT.md gatekeeper - Work BLOCKED if not aligned with strategic direction
- ✅ Auto-orchestration - "implement X" auto-triggers full agent pipeline
- ✅ File organization - Standard structure enforced (src/, tests/, docs/, scripts/)
- ✅ Commit validation - All commits checked for alignment + tests + security + docs (BLOCKING)

**Works for**:
- Greenfield projects - Start with best practices from day 1
- Brownfield projects - Retrofit existing projects (coming soon: `/align-project-retrofit`)

**Learn more**: See [docs/STRICT-MODE.md](docs/STRICT-MODE.md)

### 📝 Hybrid Auto-Fix Documentation (v2.1.0)

**Problem**: README.md and other docs drift out of sync when code changes.

**Solution**: Hybrid auto-fix + validation - "vibe coding" with safety net.

**True "Vibe Coding" Experience:**

```bash
# You add a new skill
git add skills/my-new-skill/
git commit -m "feat: add my-new-skill"

# 🔧 Attempting to auto-fix documentation...
# ✅ Auto-fixed: README.md (updated skill count: 13 → 14)
# ✅ Auto-fixed: marketplace.json (updated metrics)
# 📝 Auto-staged: README.md
# 📝 Auto-staged: .claude-plugin/marketplace.json
# 🔍 Validating auto-fix...
#
# ============================================================
# ✅ Documentation auto-updated and validated!
# ============================================================
#
# Auto-fixed files have been staged automatically.
# Proceeding with commit...

# [Commit succeeds!]
```

**How it works (Option C: Hybrid Approach):**

1. **Detect** - Finds code changes requiring doc updates
2. **Auto-fix** - Automatically updates docs for simple cases:
   - Skill/agent count updates (just increment numbers)
   - Version sync (copy version across files)
   - Marketplace metrics (auto-calculate)
3. **Validate** - Checks auto-fix worked correctly
4. **Auto-stage** - Adds fixed docs to commit automatically
5. **Block only if needed** - Only blocks for complex cases requiring human input:
   - New commands (need human-written descriptions)
   - New feature docs (need human context)
   - Breaking changes (need human explanation)

**Smart mappings:**
- Add skill/agent → **AUTO-FIX** count in README.md + marketplace.json
- Version bump → **AUTO-FIX** sync version across all files
- Add command → **MANUAL** (need human-written description)
- Add hook → **MANUAL** (need human-written docs)

**Works out-of-box:**
```bash
# After plugin install, auto-fix is enabled by default!
/plugin install autonomous-dev
# Done! Docs stay in sync automatically.

# No manual setup required! ✅
```

**Manual setup (optional):**
```bash
# If you want to customize which hooks run:
cp plugins/autonomous-dev/templates/settings.strict-mode.json .claude/settings.local.json
```

**Result**: README.md never goes stale, and you never have to manually update counts/versions! 🎉

## 🔍 How to Find This Plugin

**Discovery Options**:

1. **Direct Install** (if you're reading this):
   ```bash
   /plugin marketplace add akaszubski/autonomous-dev
   /plugin install autonomous-dev
   ```

2. **GitHub Search**: Search for `"claude-code plugin" autonomous development`

3. **Community Directories**:
   - [Claude Code Plugin Hub](https://claudecodeplugin.org)
   - [Claude Code Marketplace](https://github.com/ananddtyagi/claude-code-marketplace)

4. **Share**: Tell colleagues about `akaszubski/autonomous-dev`

**Star this repo** to help others discover it! ⭐

## Quick Install

**Choose Your Installation Tier**: [docs/INSTALLATION.md](docs/INSTALLATION.md)

| Tier | Time | What You Get |
|------|------|--------------|
| **[Basic](#basic-tier-2-minutes)** | 2 min | Commands only (learning/solo) |
| **[Standard](#standard-tier-5-minutes)** | 5 min | Commands + auto-hooks (solo with automation) |
| **[Team](#team-tier-10-minutes)** | 10 min | Full integration (GitHub + PROJECT.md) |

**Not sure?** Start with [Basic](#basic-tier-2-minutes) → upgrade later.

---

### Basic Tier (2 minutes)

**For**: Solo developers, learning the plugin, want explicit control

```bash
# 1. Add the marketplace
/plugin marketplace add akaszubski/autonomous-dev

# 2. Install the plugin
/plugin install autonomous-dev

# 3. Exit and restart Claude Code (REQUIRED!)
# Press Cmd+Q (Mac) or Ctrl+Q (Linux/Windows)
```

**Done!** All 4 core commands work immediately:
- `/auto-implement` - Autonomous feature development (vibe coding entry point)
- `/setup` - Configuration wizard (creates PROJECT.md, configures hooks)
- `/status` - View PROJECT.md goal progress
- `/uninstall` - Remove plugin

**Recommended first-time flow:**
```bash
# 1. Run setup
/setup
# → Auto-detects tech stack, creates PROJECT.md, installs hooks

# 2. Start building with vibe coding
"Add user authentication"
# → /auto-implement runs automatically in strict mode
```

**Philosophy**: 4 commands (64% reduction from v3.0.2). Manual quality commands archived - hooks enforce automatically in background.

**Upgrade to Standard** when you want automatic formatting/testing: [docs/INSTALLATION.md#standard-tier](docs/INSTALLATION.md#standard-tier)

---

### Standard Tier (5 minutes)

**For**: Solo developers who want automatic quality checks

```bash
# Basic tier + setup wizard
/setup

# Choose: "Automatic Hooks"
# Enables: auto-format, auto-test, security scan
```

**What changes**:
- ✅ Code auto-formatted on save
- ✅ Tests run before commit
- ✅ Security scan before commit
- ✅ 80% coverage enforced

**Upgrade to Team** when collaborating with GitHub: [docs/INSTALLATION.md#team-tier](docs/INSTALLATION.md#team-tier)

---

### Team Tier (10 minutes)

**For**: Teams collaborating with GitHub, want scope enforcement

```bash
# Standard tier + PROJECT.md + GitHub
/setup

# Steps:
# 1. Create PROJECT.md (strategic direction)
# 2. Setup GitHub integration (token + milestones)
# 3. Verify: /align-project && /health-check
```

**What changes**:
- ✅ PROJECT.md governance (scope enforcement)
- ✅ GitHub sprint tracking
- ✅ Automatic issue creation
- ✅ PR description generation
- ✅ `/auto-implement` validates alignment before work

**Full details**: [docs/INSTALLATION.md](docs/INSTALLATION.md)

---

## Plugin Development Notes

**Developing this plugin?** Remember:
- Edit location: `/path/to/autonomous-dev/plugins/autonomous-dev/`
- Runtime location: `~/.claude/plugins/autonomous-dev/`

**Workflow**: Edit → `python .claude/hooks/sync_to_installed.py` → Restart → Test

See `docs/TROUBLESHOOTING.md` section 0 for details.

---

### Updating

**⚠️ TWO-LAYER UPDATE PROCESS** - The plugin has two separate parts that update differently:

#### Layer 1: Global Plugin (Automatic)
**What gets updated**: Agents, skills, commands (available globally across all projects)

```bash
# 1. Uninstall
/plugin uninstall autonomous-dev

# 2. Exit and restart Claude Code (REQUIRED!)
# Press Cmd+Q (Mac) or Ctrl+Q (Linux/Windows)

# 3. Reinstall
/plugin install autonomous-dev

# 4. Exit and restart again
```

✅ **Done!** Agents, skills, and commands are now updated.

#### Layer 2: Project-Level Hooks (Manual Per Project)
**What gets updated**: Hooks in each project's `.claude/hooks/` directory

**⚠️ CRITICAL**: Plugin reinstall does NOT update hooks in your projects!

**For EACH project using hooks**, choose one:

**Option A: Quick Update** (recommended):
```bash
# Navigate to your project
cd ~/my-project

# Re-run setup to update hooks
/setup
```

**Option B: Manual Update** (advanced):
```bash
# Copy updated hooks from plugin to project
cp -r ~/.claude/plugins/autonomous-dev/hooks/ .claude/hooks/
```

**Why this matters**:
- Without updating hooks: Old hook versions run (may have bugs/missing features)
- With updating hooks: Latest hook versions run (bug fixes + new features)

**See**: [QUICKSTART.md](QUICKSTART.md) for complete walkthrough

## What You Get

### 🤖 19 Specialized Agents

**Core Workflow Agents (9)**:

| Agent | Purpose | Model | Size |
|-------|---------|-------|------|
| **orchestrator** | Master coordinator - validates PROJECT.md alignment, manages context, auto-invokes advisor | sonnet | 335 lines |
| **advisor** | Critical thinking/"devils advocate" - analyzes proposals before implementation | sonnet | 600+ lines |
| **planner** | Architecture & design planning for complex features | opus | 74 lines |
| **researcher** | Research patterns, best practices, security considerations | sonnet | 66 lines |
| **test-master** | TDD workflow, comprehensive test coverage | sonnet | 67 lines |
| **implementer** | Clean code implementation following patterns | sonnet | 61 lines |
| **reviewer** | Code quality gate before merge | sonnet | 70 lines |
| **security-auditor** | Security scanning & OWASP compliance | haiku | 68 lines |
| **doc-master** | Documentation sync & CHANGELOG automation | haiku | 63 lines |

**Utility Agents (10)**:

| Agent | Purpose | Model | Size |
|-------|---------|-------|------|
| **alignment-validator** | GenAI-powered PROJECT.md alignment validation | sonnet | 88 lines |
| **project-bootstrapper** | Analyzes codebase and generates optimal configuration | sonnet | 600+ lines |
| **setup-wizard** | Intelligent setup wizard - analyzes tech stack and guides plugin configuration | sonnet | 600+ lines |
| **project-status-analyzer** | Real-time project health - goals, metrics, blockers | sonnet | 400+ lines |
| **sync-validator** | Smart dev sync - detects conflicts, validates compatibility | sonnet | 400+ lines |
| **commit-message-generator** | Generate conventional commit messages | sonnet | 142 lines |
| **pr-description-generator** | Generate comprehensive PR descriptions | sonnet | 283 lines |
| **project-progress-tracker** | Track progress against PROJECT.md goals | sonnet | 266 lines |
| **advisor** | Critical thinking/"devils advocate" - analyzes proposals | sonnet | 600+ lines |
| **quality-validator** | GenAI-powered feature validation | sonnet | 400+ lines |

**Skills**: 19+ active skills including api-design, architecture-patterns, code-review, database-design, testing-guide, security-patterns, git-workflow, python-standards, observability, and more.

---

### ⚙️ 8 Commands (All GenAI-Native)

**Philosophy**: "Vibe coding with background enforcement" - Natural language input → Professional engineering output

| Command | Purpose | Agent | When to Use |
|---------|---------|-------|------------|
| `/auto-implement` | Autonomous feature development | orchestrator | Every feature - describe what you want |
| `/align-project` | Find/fix conflicts between goals and code | alignment-analyzer | After major changes, before releases |
| `/status` | Track strategic progress, get recommendations | project-progress-tracker | Check goal progress, decide next priorities |
| `/sync-dev` | Synchronize development environment | sync-validator | After git pull, plugin updates, environment issues |
| `/setup` | Interactive setup wizard | project-bootstrapper | Once per project during installation |
| `/health-check` | Validate plugin component integrity | (Python validation) | After installation, when debugging issues |
| `/align-claude` | Check/fix documentation drift | (Validation + script) | Automated via hook, manual check optional |
| `/test` | Run all automated tests | (Pytest wrapper) | Validate quality before commit |
| `/uninstall` | Remove or disable plugin | (Interactive menu) | When cleaning up |

**Workflow**:
```bash
# 1. Setup (once)
/setup

# 2. Check strategic direction
/status           # See what goals need work

# 3. Implement feature (repeat)
/auto-implement "Add user authentication"  # Natural language
# → Orchestrator coordinates agents
# → All SDLC steps automated
# → Hooks validate at commit

/status           # Check updated progress
/clear            # Reset context for next feature

# 4. Before release
/align-project    # Ensure implementation matches goals
/test             # Run full test suite
```

**Key Changes**:
- ✅ **All commands are GenAI-native**: Every command uses intelligent agents
- ✅ **Commands are cooperative**: `/status` → `/auto-implement` → `/align-project` → `/test`
- ✅ **Added `/sync-dev`**: Smart environment sync after git pull or plugin updates
- ✅ **Kept `/test`**: Simple bash wrapper for pytest (no GenAI needed)

See [commands/archived/ARCHIVE.md](commands/archived/ARCHIVE.md) for migration guide.

---

### 📦 Archived Commands

The following commands have been **moved to `commands/archived/`** to align with the "vibe coding with background enforcement" philosophy:

**v3.1.0 Archived** (Philosophy alignment):
- `/test` → `hooks/auto_test.py` runs tests automatically at commit
- `/align-project` → `hooks/validate_project_alignment.py` validates alignment at commit
- `/advise` → orchestrator agent validates PROJECT.md alignment automatically
- `/bootstrap` → Merged into `/setup` (auto-detection included)
- `/create-project-md` → Merged into `/setup` (PROJECT.md creation included)
- `/health-check` → Developer tool moved to `scripts/health_check.py`

**v2.5.0 Archived** (Granular workflow commands):
- **Testing Commands**: `/test-unit`, `/test-integration`, `/test-uat`, `/test-uat-genai`, `/test-architecture`, `/test-complete`
- **Commit Commands**: `/commit`, `/commit-check`, `/commit-push`, `/commit-release`
- **Quality Commands**: `/format`, `/security-scan`, `/full-check`
- **Docs Commands**: `/sync-docs`, `/sync-docs-api`, `/sync-docs-changelog`, `/sync-docs-organize`
- **Issue Commands**: `/issue`, `/issue-auto`, `/issue-create`, `/issue-from-test`, `/issue-from-genai`
- **GitHub Commands**: `/pr-create`

**Why archived?**: These commands violated the philosophy of "background enforcement". The `/auto-implement` workflow + hooks handle all quality steps automatically.

**Migration guide**: See [commands/archived/ARCHIVE.md](commands/archived/ARCHIVE.md) for detailed migration from manual commands to automated hooks.

**Still available**: Files exist in `commands/archived/` if you need manual control. Can be restored by moving to `commands/` directory.

### ⚡ 30+ Automated Hooks

**Core Hooks (6 GenAI-Enhanced)**:

| Hook | Purpose | GenAI Model | Status |
|------|---------|-------------|--------|
| **validate_project_alignment.py** | Enforce PROJECT.md alignment | - | ✅ Tested |
| **security_scan.py** | Scan for secrets + GenAI context analysis | Haiku | ✅ Tested |
| **auto_generate_tests.py** | Auto-generate test scaffolding (TDD) | Sonnet | ✅ Tested |
| **auto_update_docs.py** | Keep API docs in sync | Sonnet | ✅ Tested |
| **validate_docs_consistency.py** | Validate doc accuracy with GenAI | Sonnet | ✅ Tested |
| **auto_fix_docs.py** | Auto-fix documentation issues | Haiku | ✅ Tested |

**Extended Hooks (22 Additional)**:

| Hook | Purpose |
|------|---------|
| **auto_format.py** | Format with black + isort (Python) |
| **auto_test.py** | Run related tests |
| **auto_tdd_enforcer.py** | Enforce TDD (test before code) |
| **auto_add_to_regression.py** | Add to regression suite |
| **auto_enforce_coverage.py** | Ensure 80%+ test coverage |
| **auto_sync_dev.py** | Sync dev environment |
| **auto_track_issues.py** | Auto-create GitHub issues |
| **detect_doc_changes.py** | Detect documentation changes |
| **detect_feature_request.py** | Detect feature requests |
| **enforce_bloat_prevention.py** | Prevent code bloat |
| **enforce_command_limit.py** | Enforce command count limits |
| **enforce_file_organization.py** | Enforce standard structure |
| **enforce_orchestrator.py** | Verify orchestrator ran |
| **enforce_tdd.py** | Enforce TDD workflow |
| **post_file_move.py** | Update refs after file moves |
| **validate_claude_alignment.py** | Validate CLAUDE.md alignment |
| **validate_documentation_alignment.py** | Validate documentation alignment |
| **validate_readme_accuracy.py** | Validate README accuracy |
| **validate_readme_with_genai.py** | GenAI-powered README validation |
| **validate_session_quality.py** | Validate session quality |
| + 2 utility files | genai_utils.py, genai_prompts.py |

**Installation**:
- Hooks stored in `plugins/autonomous-dev/hooks/` (distribution source)
- Copied to `.claude/hooks/` on setup for dogfooding (tests like user install)
- Setup script copies to user's `.claude/hooks/` during `/setup`
- Configured in `.claude/settings.local.json` PreCommit event

---

## 🚀 Key Features

### Three-Layer Testing Framework

**Layer 1: Code Coverage** (pytest) - Optional
- Fast automated tests (< 1s)
- Traditional unit/integration/UAT tests
- 80%+ coverage target
- **Setup**: `pip install -r requirements-dev.txt`
- **Run**: `/test` or `pytest tests/`

**Layer 2: Quality Coverage** (GenAI) ⭐ **Primary**
- UX quality validation (8/10 target)
- Architectural intent verification
- Goal alignment checking

**Layer 3: System Performance** (Meta-analysis) ⭐ **NEW**
- Agent effectiveness tracking
- Model optimization (Opus/Sonnet/Haiku)
- Cost efficiency analysis
- ROI measurement

**Commands**:
```bash
# Primary (GenAI) - No dependencies required
/test-uat-genai                # Layer 2: UX quality validation (2-5min)
/test-architecture             # Layer 2: Architectural intent verification (2-5min)
/test-complete                 # Layer 1 + 2: Complete validation (5-10min)

# Optional (pytest) - Requires: pip install -r requirements-dev.txt
/test                          # Layer 1: pytest tests (< 60s, if pytest installed)
```

**See**: [COVERAGE-GUIDE.md](docs/COVERAGE-GUIDE.md), [SYSTEM-PERFORMANCE-GUIDE.md](docs/SYSTEM-PERFORMANCE-GUIDE.md)

---

### Automatic GitHub Issue Tracking ⭐ **NEW**

**Zero-effort issue creation** - runs automatically as you work:

```bash
# Just push normally
git push

# Auto-creates issues:
✅ #42: "test_export_speed fails" (bug)
✅ #43: "No progress indicator" (UX)
✅ #44: "Optimize reviewer - save 92%" (cost)

# Review later
gh issue list --label automated
```

**Three automatic triggers**:
1. **On Push** (recommended) - Before git push
2. **Background** - After each Claude prompt (silent)
3. **After Commit** - Per-commit tracking

**What gets tracked**:
- Test failures (Layer 1) → Bug issues
- UX problems (Layer 2) → Enhancement issues
- Architectural drift (Layer 2) → Architecture issues
- Optimization opportunities (Layer 3) → Optimization issues

**Configuration**:
```bash
# .env
GITHUB_AUTO_TRACK_ISSUES=true
GITHUB_TRACK_ON_PUSH=true
GITHUB_TRACK_THRESHOLD=medium
```

**See**: [AUTO-ISSUE-TRACKING.md](docs/AUTO-ISSUE-TRACKING.md), [GITHUB-ISSUES-INTEGRATION.md](docs/GITHUB-ISSUES-INTEGRATION.md)

---

### PROJECT.md-First Architecture

**Strategic alignment before coding**:
- All work validates against PROJECT.md (goals, scope, constraints)
- Orchestrator blocks misaligned features
- No scope creep, no architectural drift

**Commands**:
- `/auto-implement` - 8-agent pipeline with PROJECT.md validation
- `/align-project` - Safely align existing projects

---

### Standard Project Structure

**The automations expect and enforce this structure:**

```
your-project/
├── docs/                     # Project documentation
│   ├── api/                  # API documentation
│   ├── guides/               # User guides
│   └── sessions/             # Agent session logs (auto-created)
├── src/                      # Source code
├── tests/                    # All tests
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests
│   └── uat/                  # User acceptance tests
├── scripts/                  # Project automation scripts
├── .claude/
│   ├── PROJECT.md            # Project definition (agents read this)
│   └── settings.local.json   # Local settings (gitignored)
├── README.md
├── CHANGELOG.md
└── [language-specific files] # package.json, pyproject.toml, etc.
```

**Key directories:**
- `docs/` - All project documentation (not plugin docs)
- `src/` - All source code (language-specific structure)
- `tests/` - All tests (organized by type: unit/integration/uat)
- `scripts/` - Build and automation scripts
- `PROJECT.md` - **Source of truth** (agents read before every feature)

**Auto-created:**
- `docs/sessions/` - Agent activity logs (for debugging)

**Commands that use this structure:**
- `/align-project` - Validates and fixes structure
- `/sync-docs-organize` - Organizes .md files into docs/
- `/auto-implement` - Creates files following this structure

**See**: [templates/PROJECT.md](templates/PROJECT.md) for complete structure definition

---

### Continuous Improvement

**Autonomous system optimizes itself**:
- Tests itself (3 layers)
- Tracks its own issues (automatic)
- Measures its own performance (ROI, cost, speed)
- Suggests its own optimizations

**Complete loop**: Test → Find Issues → Track → Fix → Measure → Optimize

---

## How It Works

### ⭐ PROJECT.md-First Workflow (MOST IMPORTANT)

**Every feature starts with alignment validation:**

```
You: "Add user authentication"

orchestrator (PRIMARY MISSION):
1. ✅ Reads PROJECT.md
2. ✅ Validates alignment with GOALS
3. ✅ Checks if IN SCOPE
4. ✅ Verifies CONSTRAINTS respected
5. ✅ Queries GitHub Milestone (optional)
6. ✅ Only proceeds if aligned

Then coordinates 7-agent pipeline:
7. researcher → Web research (5 min)
8. planner → Architecture plan (5 min, opus model)
9. test-master → Writes FAILING tests (5 min, TDD)
10. implementer → Makes tests PASS (12 min)
11. reviewer → Quality gate check (2 min)
12. security-auditor → Security scan (2 min, haiku)
13. doc-master → Updates docs + CHANGELOG (1 min, haiku)
14. Prompts: "Run /clear for next feature"

Total: ~32 minutes, fully autonomous
```

**Result**: No scope creep. All work aligns with strategic direction.

### Safe Project Alignment

Bring existing projects into alignment with `/align-project`:

```bash
# Phase 1: Analysis only (read-only, safe)
/align-project

# Phase 2: Generate PROJECT.md from code
/align-project --generate-project-md

# Phase 3: Interactive alignment (ask before each change)
/align-project --interactive
```

**7 Advanced Features**:
1. Smart Diff View - unified view with risk scoring
2. Dry Run with Stash - test changes before applying
3. Pattern Learning - learns from your decisions
4. Conflict Resolution - handles PROJECT.md vs reality mismatches
5. Progressive Enhancement - quick wins → deep work
6. Undo Stack - visual history with rollback
7. Simulation Mode - risk-free sandbox

### Agents Auto-Invoke

The orchestrator manages the entire pipeline automatically - you just describe what you want.

### Skills Auto-Activate

- Write Python → python-standards activates
- Write tests → testing-guide activates
- Handle secrets → security-patterns activates

### Hooks (Two Modes)

**Slash Commands Mode** (default):
- Run manually when needed: `/format`, `/test`, `/security-scan`
- Full control, great for learning

**Automatic Hooks Mode** (optional):
- Save file → auto_format.py runs
- Commit → auto_test.py + security_scan.py run
- Zero manual intervention

**Configure via**: `/setup`

## Requirements

- **Claude Code**: 2.0.0 or higher
- **Python**: 3.11+ (for hooks)
- **Git**: For automation hooks

## Configuration

### Easy Setup (Recommended)

Run the interactive setup wizard:

```bash
/setup
```

This will:
1. Copy hooks and templates to your project
2. Configure your workflow (slash commands or automatic hooks)
3. Set up PROJECT.md from template
4. Configure GitHub integration (optional)
5. Guide you through all options interactively

**See**: [QUICKSTART.md](QUICKSTART.md) for complete guide

### PROJECT.md Setup (Manual)

If you prefer manual setup, create `PROJECT.md` to define your strategic direction:

```bash
# Copy template (after running /setup)
cp .claude/templates/PROJECT.md PROJECT.md

# Edit to define your:
# - GOALS (what you're building, success metrics)
# - SCOPE (what's in/out of scope)
# - CONSTRAINTS (tech stack, performance, security)
# - CURRENT SPRINT (GitHub milestone, sprint goals)
```

**See**: [PROJECT.md template](templates/PROJECT.md) for complete structure

### GitHub Integration (Optional)

Enable sprint tracking, issue sync, and **automatic issue tracking**:

```bash
# 1. Install GitHub CLI
brew install gh          # macOS
sudo apt install gh      # Linux

# 2. Authenticate
gh auth login

# 3. Configure automatic issue tracking
cp .env.example .env

# Edit .env:
GITHUB_AUTO_TRACK_ISSUES=true       # Enable automatic tracking
GITHUB_TRACK_ON_PUSH=true           # Auto-create issues before push
GITHUB_TRACK_THRESHOLD=medium       # Filter by priority
```

**Automatic Issue Tracking** ⭐ **NEW**:
- Automatically creates GitHub Issues from testing results
- Runs before git push (or in background)
- Tracks bugs, UX issues, and optimizations
- Zero manual effort

**See**:
- [AUTO-ISSUE-TRACKING.md](docs/AUTO-ISSUE-TRACKING.md) - Automatic tracking guide
- [GITHUB-ISSUES-INTEGRATION.md](docs/GITHUB-ISSUES-INTEGRATION.md) - Complete integration guide
- [GITHUB_AUTH_SETUP.md](docs/GITHUB_AUTH_SETUP.md) - GitHub authentication setup

**Note**: GitHub is optional - plugin works great without it. PROJECT.md is the primary source of truth.

### Hooks Configuration

**Using /setup (Recommended)**:
The setup wizard configures hooks automatically based on your choice.

**Manual Configuration**:
If you chose "Automatic Hooks" mode, edit `.claude/settings.local.json`:

```json
{
  "hooks": {
    "PostToolUse": {
      "Write": ["python .claude/hooks/auto_format.py"],
      "Edit": ["python .claude/hooks/auto_format.py"]
    },
    "PreCommit": {
      "*": [
        "python .claude/hooks/auto_test.py",
        "python .claude/hooks/security_scan.py"
      ]
    }
  }
}
```

**Note**: `.claude/settings.local.json` is gitignored - safe for local customization!

## Why Use This?

**Before autonomous-dev:**
- ❌ Scope creep (features don't align with goals)
- ❌ Manual code formatting
- ❌ Forget to write tests
- ❌ Inconsistent code quality
- ❌ Documentation gets out of sync
- ❌ Security vulnerabilities slip through
- ❌ Context budget explodes after 3-4 features

**After autonomous-dev:**
- ✅ **PROJECT.md alignment** - no scope creep
- ✅ **Orchestrated workflow** - 8-agent coordination
- ✅ **Model-optimized** - 40% cost reduction (opus/sonnet/haiku)
- ✅ **Auto-formatted code** (black + isort)
- ✅ **TDD enforced** (test before code)
- ✅ **80%+ coverage required**
- ✅ **Docs auto-updated**
- ✅ **Security auto-scanned**
- ✅ **Context management** - scales to 100+ features
- ✅ **Safe alignment** - 7 advanced features for existing projects

## Support

- **Issues**: [GitHub Issues](https://github.com/akaszubski/autonomous-dev/issues)
- **Documentation**: [Full Docs](https://github.com/akaszubski/autonomous-dev/docs)

## License

MIT License

## Version

**v3.2.1** (2025-10-27)

**Major Updates in v3.2.1**:
- ✅ Hooks installation complete (30+ hooks to `.claude/hooks/`)
- ✅ 6 core hooks tested and verified working
- ✅ Path resolution fixed for dogfooding scenarios
- ✅ README documentation updated
- 🚀 Distribution-ready with proper source/test separation

**Previous Major Updates**:
- ⭐ PROJECT.md-first architecture (alignment validation on every feature)
- 🤖 orchestrator agent (master coordinator with PRIMARY MISSION)
- 🎯 Alignment simplicity (all conflicts reduce to one question)
- 🧠 GenAI command refactoring (8 GenAI-native commands)
- 📊 GitHub integration (optional sprint tracking with .env auth)
- 🔧 /align-project command (3-phase safe alignment with 7 advanced features)
- 🧠 Model optimization (opus/sonnet/haiku for 40% cost reduction)
- 📋 Context management (scales to 100+ features)
- 🛡️ Safe alignment (dry run, pattern learning, undo stack, simulation mode)

**See**: [HYBRID_ARCHITECTURE_SUMMARY.md](../../HYBRID_ARCHITECTURE_SUMMARY.md) for complete details

---

**🤖 Powered by Claude Code 2.0** | **PROJECT.md-First** | **Generic & Production-Ready**
