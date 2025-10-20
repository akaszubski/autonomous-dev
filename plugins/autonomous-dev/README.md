# Autonomous Dev - Generic Claude Code Plugin

**Production-ready autonomous development setup for ANY project**

Works with: Python, JavaScript, TypeScript, React, Node.js, and more!

## Quick Install

```bash
# 1. Add the marketplace
/plugin marketplace add akaszubski/claude-code-bootstrap

# 2. Install the plugin
/plugin install autonomous-dev

# 3. Run setup (copies hooks and templates, configures workflow)
/setup
```

**What gets installed:**
- ✅ Agents & Skills: Auto-active immediately
- ✅ Commands: Available immediately (`/align-project`, `/auto-implement`, etc.)
- ⚠️ Hooks: Copied but require setup (opt-in for safety)

**See**: [QUICKSTART.md](QUICKSTART.md) for complete walkthrough

## What You Get

### 🤖 8 Specialized Agents

| Agent | Purpose | Model |
|-------|---------|-------|
| **orchestrator** | Master coordinator - validates PROJECT.md alignment, manages context, coordinates all agents | sonnet |
| **planner** | Architecture & design planning for complex features | opus |
| **researcher** | Web research & best practices discovery | sonnet |
| **test-master** | TDD workflow, progression tracking, regression prevention | sonnet |
| **implementer** | Clean code implementation following patterns | sonnet |
| **reviewer** | Code quality gate before merge | sonnet |
| **security-auditor** | Security scanning & OWASP compliance | haiku |
| **doc-master** | Documentation sync & CHANGELOG automation | haiku |

### 📚 6 Core Skills

| Skill | Domain |
|-------|--------|
| **python-standards** | PEP 8, type hints, docstrings (Google style) |
| **testing-guide** | Complete testing methodology (TDD, progression, regression) |
| **security-patterns** | API key management, input validation, secure coding |
| **documentation-guide** | CHANGELOG updates, API docs, filesystem alignment |
| **research-patterns** | Research methodology, pattern discovery |
| **engineering-standards** | Code review, git workflow, best practices |

### ⚙️ Key Commands

| Command | Purpose | Speed |
|---------|---------|-------|
| `/setup` | Configure workflow (hooks, PROJECT.md, presets) | One-time |
| `/auto-implement` | Autonomous feature implementation (8-agent pipeline) | 20-30min |
| `/align-project` | Safely align project with PROJECT.md standards | 10-15min |
| `/test [target]` | Run tests (pytest) or GenAI validation | Varies |
| &nbsp;&nbsp;`/test unit` | Fast unit tests (pytest) | < 1s |
| &nbsp;&nbsp;`/test integration` | Integration tests (pytest) | < 10s |
| &nbsp;&nbsp;`/test uat` | User acceptance tests (pytest) | < 60s |
| &nbsp;&nbsp;`/test uat-genai` | GenAI: UX quality & goal alignment | 2-5min |
| &nbsp;&nbsp;`/test architecture` | GenAI: Architectural intent validation | 2-5min |
| &nbsp;&nbsp;`/test system-performance` | Layer 3: Agent/model/cost optimization | Future |
| `/issue [action]` | Auto-create GitHub Issues from test results | < 5s |
| &nbsp;&nbsp;`/issue auto` | Create issues from last test run | < 5s |
| &nbsp;&nbsp;`/issue from-test` | Issue from specific test failure | < 5s |
| &nbsp;&nbsp;`/test --track-issues` | Auto-create issues during testing | Varies |
| `/format` | Format code (black, isort, prettier) | < 5s |
| `/security-scan` | Scan for secrets & vulnerabilities | < 30s |
| `/full-check` | Complete check (format + test + security) | < 60s |
| `/commit` | Quick commit - format + unit tests + security → commit locally | < 5s |
| `/commit-check` | Standard commit - all tests + coverage → commit locally | < 60s |
| `/commit-push` | Push commit - full integrity + doc sync → push to GitHub | 2-5min |
| `/commit-release` | Release - complete validation + version bump + GitHub Release | 5-10min |
| `/uninstall` | Remove plugin files from project | < 5s |

**See**: `commands/test.md` for complete testing guide

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

**Layer 1: Code Coverage** (pytest)
- Fast automated tests (< 1s)
- Traditional unit/integration/UAT
- 80%+ coverage target

**Layer 2: Quality Coverage** (GenAI) ⭐
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
/test all                      # Layer 1: pytest
/test uat-genai                # Layer 2: UX quality
/test architecture             # Layer 2: Architectural intent
/test system-performance       # Layer 3: Meta-optimization (future)
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
1. ✅ Reads .claude/PROJECT.md
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

**Configure via**: `/setup` or `python .claude/scripts/setup.py`

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

Or use the automated script:

```bash
# Solo developer (slash commands)
python .claude/scripts/setup.py --preset=solo

# Team (automatic hooks + GitHub)
python .claude/scripts/setup.py --preset=team
```

This will:
1. Copy hooks and templates to your project
2. Configure your workflow (slash commands or automatic hooks)
3. Set up PROJECT.md from template
4. Configure GitHub integration (optional)

**See**: [QUICKSTART.md](QUICKSTART.md) for complete guide

### PROJECT.md Setup (Manual)

If you prefer manual setup, create `.claude/PROJECT.md` to define your strategic direction:

```bash
# Copy template (after running /setup or setup.py)
cp .claude/templates/PROJECT.md .claude/PROJECT.md

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

- **Issues**: [GitHub Issues](https://github.com/akaszubski/claude-code-bootstrap/issues)
- **Documentation**: [Full Docs](https://github.com/akaszubski/claude-code-bootstrap/docs)

## License

MIT License

## Version

**v2.0.0** (2025-10-20)

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
