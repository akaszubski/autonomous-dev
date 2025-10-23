# Claude Code Autonomous Development Plugin

**Last Updated**: 2025-10-20
**Version**: v2.0.0

Production-ready plugin for autonomous development with PROJECT.md-first architecture.

🚀 **One-command install** • 🤖 **8-agent pipeline** • 📚 **Auto-format, auto-test** • 🔒 **Security scanning** • 🌍 **Multi-language**

---

## Quick Start

```bash
# 1. Add marketplace (one time)
/plugin marketplace add akaszubski/autonomous-dev

# 2. Install plugin
/plugin install autonomous-dev

# 3. Exit and restart Claude Code (required!)
# Press Cmd+Q (Mac) or Ctrl+Q (Linux/Windows)
```

**Done!** All 24 commands now work: `/test`, `/format`, `/commit`, etc.

Claude now autonomously handles formatting, testing, documentation, and security.

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

### 24 Slash Commands

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
- `/align-project` - Analyze + fix (interactive menu: report/fix/preview/cancel)

**Issues** (5 commands):
- `/issue-auto` - Auto-create from test results
- `/issue-from-test` - From specific test failure
- `/issue-from-genai` - From GenAI finding
- `/issue-create` - Manual creation
- `/issue-preview` - Preview without creating

**Documentation** (5 commands):
- `/sync-docs` - Sync all documentation
- `/sync-docs-api` - API docs only
- `/sync-docs-changelog` - CHANGELOG only
- `/sync-docs-organize` - File organization
- `/sync-docs-auto` - Auto-detect and sync

**Quality** (3 commands):
- `/format` - Format code
- `/security-scan` - Security scanning
- `/full-check` - Complete quality check

**Workflow** (4 commands):
- `/auto-implement` - Autonomous feature implementation
- `/setup` - Setup wizard
- `/uninstall` - Uninstall plugin

See [plugins/autonomous-dev/docs/COMMANDS.md](plugins/autonomous-dev/docs/COMMANDS.md) for complete command reference.

### 6 Core Skills
- **python-standards** - PEP 8, type hints, docstrings
- **testing-guide** - TDD workflow, pytest patterns
- **security-patterns** - OWASP, secrets management
- **documentation-guide** - Docstring format, README updates
- **research-patterns** - Web search strategies
- **engineering-standards** - Code quality standards

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
- [COMMANDS.md](plugins/autonomous-dev/docs/COMMANDS.md) - Complete command reference (24 commands)
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

# All 24 commands should appear in autocomplete
```

### Still not working after restart?

```bash
# 1. Check if plugin is installed
ls ~/.claude/plugins/autonomous-dev

# 2. Reinstall completely
/plugin uninstall autonomous-dev
# Exit and restart Claude Code
/plugin install autonomous-dev
# Exit and restart Claude Code again
```

---

## FAQ

**Q: Will it overwrite my existing code?**
A: No! The plugin only adds `.claude/` directory. Your code is untouched.

**Q: Can I customize the agents/hooks?**
A: Yes! After installation, edit files in `.claude/` as needed.

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
