# Claude Code 2.0 Autonomous Development Plugins

> **📦 This is the plugin source repository**
> Users install with `/plugin install autonomous-dev` (see Quick Start below)
> For post-installation docs, see the `INSTALL_TEMPLATE.md` created in your project

**Last Updated**: 2025-10-20
**Version**: v2.0.0

**Production-ready plugins for autonomous development**

🚀 **One-command install** • 🤖 **Orchestrator-driven** • 📚 **Auto-format, auto-test** • 🔒 **Security scanning** • 🌍 **Multi-language**

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
   └─> Use /sync-docs for manual sync

7. COMMIT ✅
   └─> All checks passed
   └─> Code is formatted, tested, documented, secure
```

**Key principle**: You write code. Everything else is automatic.

---

## What You Get: autonomous-dev Plugin

**Works with**: Python, JavaScript, TypeScript, React, Node.js, and more!

**Includes**:
- ✅ **8 specialized agents** - orchestrator (master coordinator), planner, researcher, test-master, implementer, reviewer, security-auditor, doc-master
- ✅ **6 core skills** - python-standards, testing-guide, security-patterns, documentation-guide, research-patterns, engineering-standards
- ✅ **8 automation hooks** - auto-format, auto-test, TDD enforcement, coverage enforcement, security scan
- ✅ **Essential commands** - `/auto-implement`, `/align-project`, `/sync-docs`, `/commit`, `/full-check`

**Perfect for**:
- Web applications (React, Next.js, Express)
- APIs (FastAPI, Django, Node.js)
- CLI tools
- Libraries
- Any Python/JavaScript/TypeScript project

[📖 Full docs](plugins/autonomous-dev/README.md)

---

## What You Get

### Orchestrator-Driven Workflow

```
You: "/auto-implement user authentication"

orchestrator coordinates everything:
1. Validates against .claude/PROJECT.md goals ✅
2. researcher → Finds JWT best practices (5 min)
3. planner → Creates implementation plan (5 min)
4. test-master → Writes FAILING tests first (5 min)
5. implementer → Makes tests PASS (12 min)
6. reviewer → Quality gate check (2 min)
7. security-auditor → Security scan (2 min)
8. doc-master → Updates CHANGELOG (1 min)
9. Prompts: "Run /clear for next feature"

Total: ~32 minutes, fully autonomous
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
| **[QUICKSTART.md](QUICKSTART.md)** | Get running in 2 minutes |
| **README.md** (this file) | Project overview |
| **[plugins/autonomous-dev/README.md](plugins/autonomous-dev/README.md)** | Complete plugin documentation |
| **[docs/README.md](docs/README.md)** | Documentation index |
| **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** | Common issues & solutions |
| **[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)** | How to contribute |

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

### 🔥 Hybrid Architecture Update

**Model-Optimized Agents** (40% cost reduction on fast tasks):
- 🧠 **Opus** for planner (complex architecture planning)
- ⚡ **Sonnet** for researcher, implementer, test-master, reviewer
- 🚀 **Haiku** for security-auditor, doc-master (fast scanning/docs)

**Explicit Workflow Documentation**:
- 📋 `autonomous-feature.md` - Complete TDD workflow (research → plan → test → implement → review)
- 🐛 `autonomous-bugfix.md` - Bug fix with regression prevention
- ♻️ `autonomous-refactor.md` - Safe refactoring with test protection

**Optional Quality Commands** (user control > automatic hooks):
```bash
/format          # Code formatting (black, isort, prettier)
/test            # Run tests with coverage
/security-scan   # Security vulnerability scan
/full-check      # All checks (format + test + security)
/commit          # Smart commit with conventional message
```

**See**: [HYBRID_ARCHITECTURE_SUMMARY.md](docs/architecture/HYBRID_ARCHITECTURE_SUMMARY.md) for complete details

### ⭐ PROJECT.md-First Architecture (MOST IMPORTANT)

**Single Source of Truth**: All work aligns with strategic direction defined in PROJECT.md

**Priority Hierarchy**:
1. **PRIMARY**: PROJECT.md alignment - defines GOALS, SCOPE, CONSTRAINTS
2. **SECONDARY**: GitHub integration - tracks sprint execution (optional)
3. **SUPPORTING**: Safe project alignment - brings codebase into alignment

**What PROJECT.md Defines**:
```markdown
## GOALS ⭐
1. Primary Objective: What you're building
2. Success Metric: How you measure success
3. Quality Standard: Your quality bar

## SCOPE
- IN Scope ✅: Core features, technical capabilities
- OUT of Scope ❌: Explicit boundaries

## CONSTRAINTS
- Technical Stack: Languages, frameworks, tools
- Performance: Response times, scalability
- Security: Secrets management, coverage minimums
- Development: Context budget, feature time limits

## CURRENT SPRINT
- Sprint Name, GitHub Milestone, Duration, Status
- Sprint Goals (1-3 key objectives)
- Key Issues (GitHub issue links)
```

**How It Works**:

```bash
You: "implement user authentication"

orchestrator:
1. ✅ Reads PROJECT.md (PRIMARY validation)
2. ✅ Checks: Does this align with GOALS?
3. ✅ Checks: Is this IN SCOPE?
4. ✅ Checks: Does this respect CONSTRAINTS?
5. ✅ Queries GitHub Milestone (SECONDARY - optional)
6. ✅ Coordinates 7-agent dev team
7. ✅ Reports progress

Result: Only aligned work proceeds. No scope creep.
```

**Safe Project Alignment**:

```bash
# Phase 1: Analysis only (read-only, safe)
/align-project

# Phase 2: Generate PROJECT.md from code (draft only)
/align-project --generate-project-md

# Phase 3: Interactive alignment (ask before each change)
/align-project --interactive
```

**Advanced Features**:
- Smart Diff View - unified view with risk scoring
- Dry Run with Stash - test changes before applying
- Pattern Learning - learns from your decisions
- Conflict Resolution - handles PROJECT.md vs reality mismatches
- Progressive Enhancement - quick wins → deep work in stages
- Undo Stack - visual history with granular rollback
- Simulation Mode - risk-free sandbox testing

**GitHub Integration (Optional)**:

```bash
# Setup authentication
cp .env.example .env
# Edit .env with GITHUB_TOKEN from https://github.com/settings/tokens

# Create GitHub Milestone matching sprint in PROJECT.md
gh api repos/owner/repo/milestones -f title="Sprint 4"

# Auto-sync enabled
# - orchestrator queries milestone for sprint progress
# - Updates issue status as work completes
# - Closes issues when features done
```

**See**: [GITHUB_AUTH_SETUP.md](plugins/autonomous-dev/docs/GITHUB_AUTH_SETUP.md) for complete setup guide

**Templates**:
- [PROJECT.md template](plugins/autonomous-dev/templates/PROJECT.md) - Generic, works for any project type
- [.env.example](.env.example) - GitHub authentication template

**Philosophy**: PROJECT.md defines strategic "what" and "why". GitHub Milestones handle tactical "how". orchestrator ensures alignment before work begins.

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

- **CLAUDE.md** - Project-specific instructions (streamlined)
- **[docs/architecture/HYBRID_ARCHITECTURE_SUMMARY.md](docs/architecture/HYBRID_ARCHITECTURE_SUMMARY.md)** - Complete hybrid architecture reference
- **docs/UPDATES.md** - Complete update changelog
- **.mcp/TESTING.md** - MCP server testing guide

---

**🚀 Transform your development workflow in one command**

```bash
/plugin marketplace add akaszubski/claude-code-bootstrap
/plugin install autonomous-dev
```

**Happy autonomous coding! 🤖✨**
