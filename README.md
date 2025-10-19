# Claude Code 2.0 Autonomous Development Plugins

**Production-ready plugins for autonomous development**

🚀 **One-command install** • 🤖 **Generic autonomous development** • 📚 **Auto-format, auto-test** • 🔒 **Security scanning** • 🌍 **Multi-language**

---

## Quick Start

```bash
# Add this marketplace
/plugin marketplace add akaszubski/claude-code-bootstrap

# Install autonomous development setup
/plugin install autonomous-dev
```

**Done!** Claude now autonomously handles formatting, testing, documentation, and security.

---

## How It Works: The Autonomous Loop

Every time you write code, the plugin automatically:

```
1. CODE WRITTEN
   └─> You: "Add user authentication"
   └─> implementer agent writes code

2. AUTO-FORMAT (instant)
   └─> black + isort format Python
   └─> prettier formats JS/TS
   └─> No manual linting needed

3. AUTO-TEST (2-5 seconds)
   └─> Runs related tests automatically
   └─> Shows failures immediately
   └─> Blocks commit if tests fail

4. AUTO-COVERAGE (during tests)
   └─> Measures coverage on changed files
   └─> Enforces 80% minimum
   └─> Prevents untested code from shipping

5. AUTO-SECURITY (5 seconds)
   └─> Scans for hardcoded secrets (.env violations)
   └─> Checks for SQL injection patterns
   └─> Validates input sanitization

6. AUTO-DOCUMENT (when APIs change)
   └─> Updates docstrings
   └─> Syncs README if needed
   └─> Generates CHANGELOG entries

7. COMMIT ✅
   └─> All checks passed
   └─> Code is formatted, tested, documented, secure
```

**Key principle**: You write code. Everything else is automatic.

---

## What You Get: autonomous-dev Plugin

**Works with**: Python, JavaScript, TypeScript, React, Node.js, and more!

**Includes**:
- ✅ 7 specialized agents (planner, researcher, test-master, implementer, reviewer, security-auditor, doc-master)
- ✅ 6 core skills (python-standards, testing-guide, security-patterns, documentation-guide, research-patterns, engineering-standards)
- ✅ 8 automation hooks (auto-format, auto-test, TDD enforcement, coverage enforcement, security scan)

**Perfect for**:
- Web applications (React, Next.js, Express)
- APIs (FastAPI, Django, Node.js)
- CLI tools
- Libraries
- Any Python/JavaScript/TypeScript project

[📖 Full docs](plugins/autonomous-dev/README.md)

---

## What You Get

### Autonomous Development Workflow

```
You: "Add user authentication"

Claude automatically:
1. planner → Creates architecture plan
2. test-master → Writes FAILING tests (TDD enforced)
3. implementer → Makes tests PASS
4. reviewer → Quality gate check
5. security-auditor → Security scan
6. doc-master → Updates docs + CHANGELOG

All automatic. No manual steps.
```

### Auto-Everything

- **Auto-format**: Code formatted on every write (black, prettier, gofmt)
- **Auto-test**: Related tests run automatically
- **Auto-coverage**: 80%+ coverage enforced
- **Auto-security**: Secrets and vulnerabilities detected
- **Auto-docs**: Documentation synced with code

### Skills Auto-Activate

- Write Python → python-standards activates
- Write tests → testing-guide activates
- Handle API keys → security-patterns activates
- Write documentation → documentation-guide activates

---

## Installation

```bash
# Add marketplace
/plugin marketplace add akaszubski/claude-code-bootstrap

# Install plugin
/plugin install autonomous-dev

# Updates are automatic
/plugin update autonomous-dev
```

**Benefits**:
- ✅ One-command installation
- ✅ Automatic updates
- ✅ Version management
- ✅ Easy to uninstall (`/plugin uninstall autonomous-dev`)

---

## What Gets Installed

The plugin installs these components to your project:

```
your-project/
├── .claude/
│   ├── agents/              # Specialized subagents
│   │   ├── planner.md       # Architecture & design
│   │   ├── researcher.md    # Web research
│   │   ├── test-master.md   # TDD + regression
│   │   ├── implementer.md   # Code implementation
│   │   ├── reviewer.md      # Quality gate
│   │   ├── security-auditor.md # Security scanning
│   │   └── doc-master.md    # Doc sync
│   ├── skills/              # Domain knowledge
│   │   ├── python-standards/
│   │   ├── testing-guide/
│   │   ├── security-patterns/
│   │   └── documentation-guide/
│   └── settings.json        # Hook configuration
└── scripts/hooks/
    ├── auto_format.py       # Auto-formatting
    ├── auto_test.py         # Auto-testing
    ├── auto_enforce_coverage.py # Coverage check
    └── security_scan.py     # Security scanning
```

---

## Examples

### Example 1: React Web App

```bash
cd my-react-app
/plugin install autonomous-dev

# Claude now handles:
# ✓ Auto-format with prettier
# ✓ Auto-test with jest
# ✓ 80% coverage enforcement
# ✓ Security scanning
# ✓ TDD workflow
```

### Example 2: Python API

```bash
cd my-fastapi-project
/plugin install autonomous-dev

# Claude now handles:
# ✓ Auto-format with black + isort
# ✓ Auto-test with pytest
# ✓ Type hints enforcement
# ✓ Docstring validation
# ✓ Security scanning
```

### Example 3: Node.js Backend

```bash
cd my-express-api
/plugin install autonomous-dev

# Claude now handles:
# ✓ Auto-format with prettier
# ✓ Auto-test with jest/mocha
# ✓ Code quality enforcement
# ✓ Security vulnerability scanning
# ✓ Auto-documentation
```

---

## Documentation

| Guide | Purpose |
|-------|---------|
| **README.md** (this file) | Quick start & overview |
| **[plugins/autonomous-dev/README.md](plugins/autonomous-dev/README.md)** | Complete plugin documentation |

---

## FAQ

**Q: Will it overwrite my existing code?**
A: No! The plugin only adds `.claude/` and `scripts/hooks/`. Your code is untouched.

**Q: Can I customize the agents/hooks?**
A: Absolutely! After installation, edit `.claude/agents/*.md`, `scripts/hooks/*.py`, `.claude/settings.json` as needed.

**Q: Does this send my code anywhere?**
A: No. Everything runs locally. Hooks are just Python scripts on your machine.

**Q: How do I uninstall?**
A: `/plugin uninstall autonomous-dev` or manually delete `.claude/` and `scripts/hooks/`.

**Q: Can I customize the installed files?**
A: Yes! After installation, all files in `.claude/` and `scripts/hooks/` are yours to modify.

**Q: Is this beginner-friendly?**
A: Yes! Just run `/plugin install autonomous-dev` and start coding. Claude handles everything else.

**Q: What languages does this support?**
A: Python, JavaScript, TypeScript, Go, Rust, and more. The plugin is language-agnostic with specific optimizations for Python/JS/TS.

---

## Requirements

- **Claude Code**: 2.0.0 or higher
- **Python**: 3.11+ (for hooks)
- **Git**: For automation hooks

---

## Support

- **Issues**: [GitHub Issues](https://github.com/akaszubski/claude-code-bootstrap/issues)
- **Discussions**: [GitHub Discussions](https://github.com/akaszubski/claude-code-bootstrap/discussions)
- **Main Project**: [ReAlign Repository](https://github.com/akaszubski/realign)

---

## License

MIT License - See [LICENSE](LICENSE) file

---

## Credits

Created by [@akaszubski](https://github.com/akaszubski)

Powered by [Claude Code 2.0](https://claude.com/claude-code)

---

---

## New Features (2025-10-19)

### 🎯 PROJECT.md - Goal Alignment System

Prevent scope creep with automatic feature alignment:

```bash
# Every feature is validated against project goals
# Located: .claude/PROJECT.md
# Defines: GOALS, SCOPE, CONSTRAINTS, ARCHITECTURE
```

### 🧹 Context Management

Scale to 100+ features without performance degradation:

```bash
# After each feature:
/clear

# Context stays under 8K tokens (vs 50K+ without management)
```

**Session Tracker**: Logs agent actions to files instead of context
- Located: `scripts/session_tracker.py`
- Logs: `docs/sessions/`
- Result: 10x more efficient context usage

### 🔌 MCP Server Integration

Optional Claude Desktop enhancement:

```bash
# Configuration: .mcp/config.json
# Provides:
- Filesystem access (read/write repository)
- Shell commands (git, gh, python, npm)
- Git operations (status, diff, commit)
- Python interpreter (with virtualenv)

# Setup guide: .mcp/README.md
# Test script: .mcp/test-mcp.sh
```

### 📚 Documentation

- **CLAUDE.md** - Project-specific instructions (streamlined to 215 lines)
- **docs/UPDATES.md** - Complete update changelog
- **.mcp/TESTING.md** - MCP server testing guide

---

**🚀 Transform your development workflow in one command**

```bash
/plugin marketplace add akaszubski/claude-code-bootstrap
/plugin install autonomous-dev
```

**Happy autonomous coding! 🤖✨**
