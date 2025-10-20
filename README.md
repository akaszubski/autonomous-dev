# Claude Code Autonomous Development Plugin

**Last Updated**: 2025-10-20
**Version**: v2.0.0

Production-ready plugin for autonomous development with PROJECT.md-first architecture.

🚀 **One-command install** • 🤖 **8-agent pipeline** • 📚 **Auto-format, auto-test** • 🔒 **Security scanning** • 🌍 **Multi-language**

---

## Quick Start

```bash
# 1. Add marketplace (one time)
/plugin marketplace add akaszubski/claude-code-bootstrap

# 2. Install plugin
/plugin install autonomous-dev
```

**Done!** Claude now autonomously handles formatting, testing, documentation, and security.

### Updating

```bash
# Get latest version
/plugin uninstall autonomous-dev
/plugin install autonomous-dev
```

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

### Essential Commands
- `/auto-implement` - Autonomous feature implementation
- `/align-project` - Validate alignment with PROJECT.md
- `/sync-docs` - Synchronize documentation with code
- `/commit` - Smart commit with conventional message
- `/full-check` - Complete quality check (format + test + security)

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
/plugin marketplace add akaszubski/claude-code-bootstrap
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
/plugin marketplace add akaszubski/claude-code-bootstrap
/plugin install autonomous-dev

# Claude now handles:
# ✓ Auto-format with black + isort
# ✓ Auto-test with pytest
# ✓ Type hints enforcement
# ✓ Security scanning
```

---

## Documentation

| Guide | Purpose |
|-------|---------|
| [QUICKSTART.md](QUICKSTART.md) | Get running in 2 minutes |
| [plugins/autonomous-dev/README.md](plugins/autonomous-dev/README.md) | Complete plugin documentation |
| [docs/README.md](docs/README.md) | Documentation index |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common issues & solutions |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Plugin development guide |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | How to contribute |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

---

## FAQ

**Q: Will it overwrite my existing code?**
A: No! The plugin only adds `.claude/` directory. Your code is untouched.

**Q: Can I customize the agents/hooks?**
A: Yes! After installation, edit files in `.claude/` as needed.

**Q: Does this send my code anywhere?**
A: No. Everything runs locally. Hooks are Python scripts on your machine.

**Q: How do I uninstall?**
A: `/plugin uninstall autonomous-dev`

**Q: How do I update?**
A: Uninstall then reinstall: `/plugin uninstall autonomous-dev` → `/plugin install autonomous-dev`

**Q: Is this beginner-friendly?**
A: Yes! Just install and start coding. Claude handles the rest.

---

## Requirements

- **Claude Code**: 2.0.0 or higher
- **Python**: 3.11+ (for hooks)
- **Git**: For version control features

---

## Support

- **Issues**: [GitHub Issues](https://github.com/akaszubski/claude-code-bootstrap/issues)
- **Discussions**: [GitHub Discussions](https://github.com/akaszubski/claude-code-bootstrap/discussions)

---

## License

MIT License - See [LICENSE](LICENSE)

---

## Credits

Created by [@akaszubski](https://github.com/akaszubski)

Powered by [Claude Code 2.0](https://claude.com/claude-code)
