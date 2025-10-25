# Claude Code Autonomous Development Plugin

**Last Updated**: 2025-10-25
**Version**: v2.4.0

Production-ready plugin for autonomous development with **PROJECT.md-first architecture**.

🚀 **One-command install** • 📋 **PROJECT.md-first** • 🤖 **8-agent pipeline** • 📚 **Auto-format, auto-test** • 🔒 **Security scanning** • 🌍 **Multi-language**

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

### Installation

```bash
# 1. Add marketplace (one time)
/plugin marketplace add akaszubski/autonomous-dev

# 2. Install plugin
/plugin install autonomous-dev

# 3. Exit and restart Claude Code (required!)
# Press Cmd+Q (Mac) or Ctrl+Q (Linux/Windows)
```

**Done!** All 21 commands now work: `/test`, `/format`, `/commit`, etc.

Claude now autonomously handles formatting, testing, documentation, and security using **GenAI semantic validation** (95% accuracy).

### Optional Setup (Advanced)

**Only needed if you want automatic hooks** (auto-format on save, auto-test on commit):

```bash
# Run the setup wizard
python plugins/autonomous-dev/scripts/setup.py

# This wizard helps you:
# - Enable automatic formatting on file save
# - Create PROJECT.md from template
# - Configure GitHub integration (.env file)
# - Asks before overwriting any existing files
```

**Note**: Most users don't need this! Use slash commands like `/format`, `/test` instead.

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

### 8 Specialized Agents
- **orchestrator** - Validates PROJECT.md alignment (master coordinator)
- **researcher** - Web research for best practices
- **planner** - Architecture & implementation planning (opus model)
- **test-master** - TDD specialist (writes tests first)
- **implementer** - Code implementation
- **reviewer** - Quality gate checks (sonnet model)
- **security-auditor** - Security scanning (haiku model)
- **doc-master** - Documentation sync (haiku model)

### 21 Slash Commands

All commands are independently discoverable with autocomplete:

**Testing** (7 commands):
- `/test` - All automated tests
- `/test-unit` - Unit tests only (< 1s)
- `/test-integration` - Integration tests (< 10s)
- `/test-uat` - UAT tests (< 60s)
- `/test-uat-genai` - GenAI UX validation (2-5min)
- `/test-architecture` - GenAI architecture validation (2-5min)
- `/test-complete` - Complete pre-release validation (5-10min)

**Commit** (4 commands):
- `/commit` - Quick commit (< 5s)
- `/commit-check` - Standard commit with full tests (< 60s)
- `/commit-push` - Push commit with integrity checks (2-5min)
- `/commit-release` - Production release (5-10min)

**Alignment** (1 command):
- `/align-project` - Analyze + fix (menu: report/fix/preview/cancel)

**Documentation** (1 command):
- `/sync-docs` - Sync docs (menu: smart/full/filesystem/API/CHANGELOG/cancel)

**Issues** (1 command):
- `/issue` - Create issues (menu: tests/GenAI/manual/preview/cancel)

**Quality** (3 commands):
- `/format` - Format code
- `/security-scan` - Security scanning
- `/full-check` - Complete quality check

**Workflow** (4 commands):
- `/auto-implement` - Autonomous feature implementation
- `/setup` - Setup wizard
- `/uninstall` - Uninstall plugin

See [plugins/autonomous-dev/docs/COMMANDS.md](plugins/autonomous-dev/docs/COMMANDS.md) for complete command reference.

### 13 Skills
- **python-standards** - PEP 8, type hints, docstrings
- **testing-guide** - TDD workflow, pytest patterns
- **security-patterns** - OWASP, secrets management
- **documentation-guide** - Docstring format, README updates
- **research-patterns** - Web search strategies
- **architecture-patterns** - System design patterns
- **api-design** - REST API best practices
- **code-review** - Review guidelines
- **consistency-enforcement** - Documentation drift prevention
- **database-design** - Schema design, migrations
- **git-workflow** - Commit conventions, branching
- **observability** - Logging, debugging, profiling
- **project-management** - PROJECT.md templates

### Automation Hooks
- **Auto-format** - black, isort (Python), prettier (JS/TS)
- **Auto-test** - pytest (Python), jest (JS/TS)
- **Auto-coverage** - 80% minimum enforcement
- **Auto-security** - Secrets detection, vulnerability scanning

---

## How It Works

### The Autonomous Loop

Every time you write code, the plugin automatically:

```
1. CODE WRITTEN
   └─> You: "Add user authentication"
   └─> implementer agent writes code

2. AUTO-FORMAT (instant)
   └─> black + isort format Python
   └─> prettier formats JS/TS

3. AUTO-TEST (2-5 seconds)
   └─> Runs related tests automatically
   └─> Shows failures immediately

4. AUTO-COVERAGE
   └─> Measures coverage on changed files
   └─> Enforces 80% minimum

5. AUTO-SECURITY
   └─> Scans for hardcoded secrets
   └─> Checks for SQL injection patterns

6. AUTO-DOCUMENT
   └─> Updates docstrings
   └─> Syncs README if needed
   └─> Use /sync-docs for manual sync

7. COMMIT ✅
   └─> All checks passed
   └─> Code is formatted, tested, documented, secure
```

### PROJECT.md-First Architecture

All work validates against `.claude/PROJECT.md`:

```bash
You: "/auto-implement user authentication"

orchestrator:
1. ✅ Reads PROJECT.md
2. ✅ Checks: Does this align with GOALS?
3. ✅ Checks: Is this IN SCOPE?
4. ✅ Checks: Does this respect CONSTRAINTS?
5. ✅ Coordinates 7-agent pipeline
6. ✅ Reports progress

Result: Only aligned work proceeds. No scope creep.
```

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
