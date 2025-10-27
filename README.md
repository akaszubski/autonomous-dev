# Claude Code Autonomous Development Plugin

**Last Updated**: 2025-10-27
**Version**: v3.2.0
**Status**: Production-ready with Vibe Coding + Auto-Orchestration

Production-ready plugin for autonomous development with **dual-layer architecture** (Vibe Coding + Background Enforcement), **PROJECT.md-first enforcement**, and **automatic agent orchestration**.

🧠 **Vibe Coding** • 🛑 **PROJECT.md Gatekeeper** • 🤖 **19 Specialist Agents** • ✅ **Auto-Orchestration** • 🔒 **Security Enforcement** • 📋 **8 Core Commands**

---

## ⭐ The PROJECT.md-First Philosophy

**Everything starts with PROJECT.md** - your project's strategic direction documented once, enforced automatically.

### What is PROJECT.md?

A single file at your project root that defines:
- **GOALS**: What success looks like
- **SCOPE**: What's in/out of scope
- **CONSTRAINTS**: Technical and business limits
- **ARCHITECTURE**: How the system works

### Why PROJECT.md-First?

✅ **Alignment**: Every feature (human or AI-written) validates against PROJECT.md before work begins
✅ **Prevents drift**: Automatic scope creep detection
✅ **Team clarity**: Shared strategic direction for humans + AI
✅ **Survives tools**: PROJECT.md is markdown at root - survives plugin changes

### How It Works

```
1. You create PROJECT.md (or use /setup to generate from template)
2. Run /align-project to ensure project structure matches
3. Use /auto-implement for features → orchestrator validates against PROJECT.md first
4. If feature doesn't align → orchestrator stops and suggests either:
   - Modify feature to align
   - Update PROJECT.md if direction changed
```

**Result**: Zero tolerance for scope drift. Strategic alignment automated.

---

## Quick Start

### Installation (4 Steps)

**Step 1: Uninstall current version** (if you have it)
```bash
/plugin uninstall autonomous-dev
```

**Step 2: Exit Claude Code completely**
- Press **Cmd+Q** (Mac) or **Ctrl+Q** (Windows/Linux)
- Wait for it to close

**Step 3: Reopen Claude Code**
- Launch Claude Code

**Step 4: Install from marketplace**
```bash
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
```

**Step 5: Exit and restart again** (required!)
- Press **Cmd+Q** or **Ctrl+Q**

**Step 6: Reopen Claude Code**
- Launch Claude Code

**Done!** All 8 commands now available.

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
# Done!
```

**IMPORTANT**: You must exit and restart Claude Code after both uninstall AND install!

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

**Core Workflow Agents (8)** - Execute the main SDLC pipeline:
- **orchestrator** - PROJECT.md gatekeeper, validates alignment before any work begins
- **researcher** - Web research for patterns and best practices
- **planner** - Architecture & implementation planning
- **test-master** - TDD specialist (writes tests first)
- **implementer** - Code implementation
- **reviewer** - Quality gate checks
- **security-auditor** - Security scanning and vulnerability detection
- **doc-master** - Documentation sync

**Analysis & Validation Agents (6)** - Validate quality and alignment:
- **advisor** - Critical thinking and risk validation
- **quality-validator** - GenAI-powered feature quality validation
- **alignment-validator** - PROJECT.md alignment validation
- **alignment-analyzer** - Detailed conflict analysis (PROJECT.md vs reality)
- **project-progress-tracker** - Track and update goal completion
- **project-status-analyzer** - Real-time project health monitoring

**Automation & Setup Agents (5)** - Configure and automate workflows:
- **commit-message-generator** - Conventional commit generation
- **pr-description-generator** - Comprehensive PR descriptions
- **setup-wizard** - Intelligent setup and tech stack configuration
- **project-bootstrapper** - Analyze codebases and generate PROJECT.md
- **sync-validator** - Smart dev sync and conflict detection

### 8 Slash Commands

All commands are independently discoverable with autocomplete:

**Core Commands** (5):
- `/auto-implement` - Describe feature, Claude handles everything autonomously
- `/align-project` - Analyze & fix PROJECT.md alignment (menu: report/fix/preview/cancel)
- `/setup` - Interactive project setup wizard
- `/test` - Run all automated tests (unit + integration + UAT)
- `/status` - Track strategic goal progress with AI recommendations

**Utility Commands** (3):
- `/health-check` - Verify all components loaded and working
- `/sync-dev` - Intelligent development sync with conflict detection
- `/uninstall` - Remove or disable plugin

See [plugins/autonomous-dev/docs/COMMANDS.md](plugins/autonomous-dev/docs/COMMANDS.md) for complete command reference.

### Automation Hooks (24 total)

**Core Enforcement Hooks (9)**:
- **auto-format** - black + isort (Python), prettier (JS/TS)
- **auto-test** - pytest (Python), jest (JS/TS)
- **security-scan** - Secrets detection, vulnerability scanning
- **validate-project-alignment** - PROJECT.md validation before commits
- **validate-docs-consistency** - Documentation consistency enforcement
- **enforce-file-organization** - Standard structure enforcement
- **enforce-orchestrator** - Validates orchestrator ran (v3.0+)
- **enforce-tdd** - Validates tests written before code (v3.0+)
- **detect-feature-request** - Auto-invokes /auto-implement (vibe coding)

**Extended Enforcement Hooks (15)**:
- auto-add-to-regression, auto-enforce-coverage, auto-fix-docs, auto-generate-tests, auto-sync-dev, auto-tdd-enforcer, auto-track-issues, auto-update-docs, detect-doc-changes, enforce-bloat-prevention, enforce-command-limit, post-file-move, validate-claude-alignment, validate-documentation-alignment, validate-session-quality

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

### PROJECT.md-First Philosophy

Everything starts with **PROJECT.md** - a single file that defines your project's strategic direction:

```markdown
# PROJECT.md (at your project root)

## GOALS
What success looks like (e.g., "Build a scalable API")

## SCOPE
What's in/out (e.g., "Include auth, exclude payments")

## CONSTRAINTS
Technical limits (e.g., "Must support Python 3.11+")

## ARCHITECTURE
How it works (e.g., "FastAPI + PostgreSQL + Redis")
```

**Why PROJECT.md-First?**

✅ **Single source of truth** - One file defines strategic direction
✅ **Automatic enforcement** - All work validates against PROJECT.md before proceeding
✅ **Zero scope creep** - Feature requests outside SCOPE are automatically blocked
✅ **Team alignment** - Humans and AI work toward same goals
✅ **Survives tool changes** - PROJECT.md is markdown at root, survives plugin updates

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

## Troubleshooting Installation

### Commands not available after `/plugin install`

**Solution:** Exit and restart Claude Code (Cmd+Q or Ctrl+Q)

Claude Code needs a restart to load the plugin commands. After restarting:

```bash
# Test by typing:
/test
/format
/commit

# All 21 commands should appear in autocomplete
```

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
   # Check version in Claude Code
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
