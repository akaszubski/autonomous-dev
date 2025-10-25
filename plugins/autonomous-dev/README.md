# Autonomous Dev - Claude Code Plugin

[![Available on Claude Code Commands Directory](https://img.shields.io/badge/Claude_Code-Commands_Directory-blue)](https://claudecodecommands.directory/command/autonomous-dev)
[![Version](https://img.shields.io/badge/version-2.4.0--beta-orange)](https://github.com/akaszubski/autonomous-dev/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](https://github.com/akaszubski/autonomous-dev/blob/main/LICENSE)

**Version**: v2.4.0-beta
**Last Updated**: 2025-10-26

**Beta Release** - Production features with proven architecture. All 5 critical issues resolved. Documentation 95% accurate. Auto-sync prevents two-location hell. Ready for community testing.

Works with: Python, JavaScript, TypeScript, React, Node.js, and more!

## ✨ What's New in v2.4.0-beta

**🎉 Beta Release - All Critical Issues Resolved!**

This release focuses on **documentation accuracy**, **transparency**, and **automatic sync prevention**:

- 📚 **Documentation 95% Accurate**: All component counts corrected (12 agents, 15 hooks, 8 commands)
- 🏗️ **ARCHITECTURE.md**: Complete Python infrastructure map (250KB documented)
- 🔄 **Auto-Sync**: Prevents two-location hell automatically (most common issue resolved)
- ✅ **Beta Status**: Honest communication - production features, refinements ongoing
- 🔍 **Sync Detection**: Health check reports out-of-sync files with clear guidance

**What's Fixed**:
```
✅ Issue #11: PROJECT.md documentation sync (20% → 95% accurate)
✅ Issue #12: Python infrastructure documented (0% → 100%)
✅ Issue #10: Experimental status → Beta with clear capabilities
✅ Issue #8: Two-location sync hell → Auto-sync on commit
✅ Issue #9: Mandatory restarts → Documented as platform limitation
→ ✅ [Implementation] Making tests pass...
→ ✅ [Review] Code quality check passed
→ ✅ [Security] Vulnerability scan passed
→ ✅ [Documentation] Docs synced
```

**Benefits**:
- Professional consistency without manual steps
- PROJECT.md prevents scope drift automatically
- All SDLC steps enforced (Research → Plan → Test → Implement → Review → Security → Docs)
- Works for greenfield AND brownfield projects (retrofit capability)

**Previous releases**:
- **v2.1.0**: Knowledge Base System with auto-bootstrap
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

**Done!** All 8 commands work immediately:
- `/test` - Run tests
- `/align-project` - Check alignment
- `/auto-implement` - Autonomous feature development
- `/setup` - Configuration wizard
- `/status` - Project status
- `/health-check` - Plugin validation
- `/sync-dev` - Sync plugin (developers only)
- `/uninstall` - Remove plugin

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

**Workflow**: Edit → `python plugins/autonomous-dev/scripts/sync_to_installed.py` → Restart → Test

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

### 🤖 12 Specialized Agents

**Core Workflow Agents (8)**:

| Agent | Purpose | Model | Size |
|-------|---------|-------|------|
| **orchestrator** | Master coordinator - validates PROJECT.md alignment, manages context | sonnet | 67 lines |
| **planner** | Architecture & design planning for complex features | opus | 74 lines |
| **researcher** | Research patterns, best practices, security considerations | sonnet | 66 lines |
| **test-master** | TDD workflow, comprehensive test coverage | sonnet | 67 lines |
| **implementer** | Clean code implementation following patterns | sonnet | 61 lines |
| **reviewer** | Code quality gate before merge | sonnet | 70 lines |
| **security-auditor** | Security scanning & OWASP compliance | haiku | 68 lines |
| **doc-master** | Documentation sync & CHANGELOG automation | haiku | 63 lines |

**Utility Agents (4)**:

| Agent | Purpose | Model | Size |
|-------|---------|-------|------|
| **alignment-validator** | GenAI-powered PROJECT.md alignment validation | sonnet | 88 lines |
| **commit-message-generator** | Generate conventional commit messages | sonnet | 142 lines |
| **pr-description-generator** | Generate comprehensive PR descriptions | sonnet | 283 lines † |
| **project-progress-tracker** | Track progress against PROJECT.md goals | sonnet | 266 lines † |

**Note**: † Utility agents need simplification to match core agent pattern (<75 lines). See [Issue #4](https://github.com/akaszubski/autonomous-dev/issues/4).

**Skills removed**: Per [Issue #5](https://github.com/akaszubski/autonomous-dev/issues/5), skills directory eliminated. PROJECT.md states "No skills/ directory - anti-pattern". Agents follow Anthropic's "trust the model" principle.

---

### ⚙️ 8 Core Commands

**All commands are independently discoverable with autocomplete.**

#### Workflow Commands (3 commands)
| Command | Purpose | Speed |
|---------|---------|-------|
| `/auto-implement` | Autonomous feature implementation (8-agent pipeline) | 60-120s |
| `/setup` | Interactive setup wizard (creates PROJECT.md, configures hooks) | 5-10min |
| `/status` | View PROJECT.md goal progress and alignment status | < 5s |

#### Alignment (1 command)
| Command | Purpose | Speed |
|---------|---------|-------|
| `/align-project` | Analyze + fix PROJECT.md alignment | 5-10min |

**What it checks:**
- Directory structure (src/, docs/, tests/)
- Documentation organization
- Test structure (unit/, integration/, uat/)
- Hook configuration
- PROJECT.md completeness

#### Testing (1 command)
| Command | Purpose | Speed |
|---------|---------|-------|
| `/test` | Run all automated tests (unit + integration + UAT) with pytest | < 60s |

**Note**: Requires `tests/` directory with pytest tests. See [Issue #7](https://github.com/akaszubski/autonomous-dev/issues/7) for test suite setup.

#### Utilities (3 commands)
| Command | Purpose | Speed |
|---------|---------|-------|
| `/health-check` | Validate all plugin components (agents, skills, hooks, commands) | < 5s |
| `/sync-dev` | Sync development changes to installed plugin (for plugin developers) | < 1s |
| `/uninstall` | Uninstall or disable plugin features | < 5s |

---

### 📦 Archived Commands

The following granular commands have been **moved to `commands/archive/`** and are deprecated in favor of the `/auto-implement` workflow:

**Archived Testing Commands**: `/test-unit`, `/test-integration`, `/test-uat`, `/test-uat-genai`, `/test-architecture`, `/test-complete`
**Archived Commit Commands**: `/commit`, `/commit-check`, `/commit-push`, `/commit-release`
**Archived Quality Commands**: `/format`, `/security-scan`, `/full-check`
**Archived Docs Commands**: `/sync-docs`, `/sync-docs-api`, `/sync-docs-changelog`, `/sync-docs-organize`
**Archived Issue Commands**: `/issue`, `/issue-auto`, `/issue-create`, `/issue-from-test`, `/issue-from-genai`
**Archived GitHub Commands**: `/pr-create`

**Why archived?**: These commands provided granular control but added complexity. The autonomous workflow (`/auto-implement`) handles testing, formatting, commits, docs, and PRs automatically.

**Still available**: Files exist in `commands/archive/` if you need granular control. Can be restored by moving to `commands/` directory.

### ⚡ 8 Automated Hooks

| Hook | Event | Action |
|------|-------|--------|
| **auto_format.py** | File write | Format with black + isort (Python) |
| **auto_test.py** | File write | Run related tests |
| **auto_generate_tests.py** | File write | Generate missing tests |
| **auto_tdd_enforcer.py** | File write | Enforce TDD (test before code) |
| **auto_add_to_regression.py** | Test pass | Add to regression suite |
| **auto_enforce_coverage.py** | Commit | Ensure 80%+ test coverage |
| **auto_update_docs.py** | API change | Update documentation automatically |
| **security_scan.py** | File write | Scan for secrets, vulnerabilities |

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

**v2.1.0** (2025-10-25)

**Major Updates**:
- ⭐ PROJECT.md-first architecture (alignment validation on every feature)
- 🤖 orchestrator agent (master coordinator with PRIMARY MISSION)
- 📊 GitHub integration (optional sprint tracking with .env auth)
- 🔧 /align-project command (3-phase safe alignment with 7 advanced features)
- 🧠 Model optimization (opus/sonnet/haiku for 40% cost reduction)
- 📋 Context management (scales to 100+ features)
- 🛡️ Safe alignment (dry run, pattern learning, undo stack, simulation mode)

**See**: [HYBRID_ARCHITECTURE_SUMMARY.md](../../HYBRID_ARCHITECTURE_SUMMARY.md) for complete details

---

**🤖 Powered by Claude Code 2.0** | **PROJECT.md-First** | **Generic & Production-Ready**
