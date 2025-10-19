# Autonomous Dev - Generic Claude Code Plugin

**Production-ready autonomous development setup for ANY project**

Works with: Python, JavaScript, TypeScript, React, Node.js, and more!

## Quick Install

```bash
# Add the marketplace
/plugin marketplace add akaszubski/claude-code-bootstrap

# Install the plugin
/plugin install autonomous-dev
```

Done! Your Claude Code environment now has autonomous agents, skills, and hooks.

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

### Hooks Auto-Run

- Save file → auto_format.py + auto_test.py run
- Commit → auto_enforce_coverage.py checks coverage
- All automatic, no manual steps!

## Requirements

- **Claude Code**: 2.0.0 or higher
- **Python**: 3.11+ (for hooks)
- **Git**: For automation hooks

## Configuration

### PROJECT.md Setup

After installation, create `.claude/PROJECT.md` to define your strategic direction:

```bash
# Use the generic template (works for any project type)
cp .claude/templates/PROJECT.md .claude/PROJECT.md

# Edit to define your:
# - GOALS (what you're building, success metrics)
# - SCOPE (what's in/out of scope)
# - CONSTRAINTS (tech stack, performance, security)
# - CURRENT SPRINT (GitHub milestone, sprint goals)
```

**See**: [PROJECT.md template](templates/PROJECT.md) for complete structure

### GitHub Integration (Optional)

Enable sprint tracking and issue sync:

```bash
# 1. Create .env file
cp .env.example .env

# 2. Add GitHub token (https://github.com/settings/tokens)
#    Required scopes: repo, read:org
echo "GITHUB_TOKEN=ghp_your_token_here" > .env

# 3. Add .env to .gitignore (already done by plugin)
echo ".env" >> .gitignore

# 4. Create GitHub Milestone matching your sprint
gh api repos/owner/repo/milestones -f title="Sprint 4"
```

**See**: [GITHUB_AUTH_SETUP.md](docs/GITHUB_AUTH_SETUP.md) for complete guide

**Note**: GitHub is optional - plugin works great without it. PROJECT.md is the primary source of truth.

### Hooks Configuration

After install, hooks are configured in `.claude/settings.json`:

```json
{
  "hooks": {
    "on_file_write": ["auto_format.py", "auto_test.py"],
    "pre_commit": ["auto_enforce_coverage.py"],
    "pre_push": ["security_scan.py"]
  }
}
```

Customize as needed for your project!

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
