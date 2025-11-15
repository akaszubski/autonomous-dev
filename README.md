# Autonomous Development Plugin for Claude Code

**Speak requirements. Get production-ready code.**

Claude Code plugin that automates the full software development lifecycle: research → plan → test → implement → review → security → documentation.

**Version**: v3.21.0 | **Status**: Production Ready | **Last Updated**: 2025-11-15

---

## What It Does

**You say**: "Add JWT authentication to the API"

**Claude Code**:
1. Researches JWT best practices and security patterns
2. Plans the architecture and integration points
3. Writes tests first (TDD)
4. Implements the code to pass tests
5. Reviews code quality and patterns
6. Scans for security vulnerabilities
7. Updates documentation

**All automated. All in minutes.**

---

## Quick Install

### Prerequisites

**Install Claude Code first** (if you haven't already):
- Download: https://claude.ai/download
- Platforms: macOS, Windows, Linux
- Version: Claude Code 2.0+

Verify: Open Claude Code and type `/version`

### Installation (4 Steps)

**Step 1: Add plugin marketplace**
```bash
# In Claude Code
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
```

**Step 2: Restart Claude Code**
- **macOS**: `Cmd+Q`
- **Windows/Linux**: `Ctrl+Q`
- Wait 5 seconds, then reopen

**Step 3: Bootstrap your project**
```bash
# In your project directory
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

**Step 4: Restart Claude Code again**
- `Cmd+Q` (Mac) or `Ctrl+Q` (Windows/Linux)
- Reopen Claude Code

**Done!** All commands are now available.

---

## Quick Start

### Try Your First Feature

```bash
# In Claude Code
/auto-implement "Add input validation to the login form"
```

Claude Code will:
- ✅ Research validation patterns
- ✅ Plan the implementation
- ✅ Write tests first
- ✅ Implement the code
- ✅ Review quality
- ✅ Scan security
- ✅ Update docs

**Typical time**: 20-30 minutes (fully automated)

### Individual Commands (If You Prefer Step-by-Step)

Instead of the full workflow, run individual agents:

```bash
/research "JWT authentication patterns"  # Research best practices
/plan "Add JWT to API"                   # Plan architecture
/test-feature "JWT authentication"       # Write tests
/implement "Make JWT tests pass"         # Write code
/review                                  # Review code quality
/security-scan                           # Scan for vulnerabilities
/update-docs                             # Sync documentation
```

### Project Management

```bash
/status              # View project health and progress
/align-project       # Fix PROJECT.md alignment issues
/create-issue "..."  # Create GitHub issue with research
```

### Utility

```bash
/setup               # Interactive project configuration
/sync                # Sync plugin updates
/health-check        # Verify all components working
/update-plugin       # Update to latest version
```

---

## Quick Update

**When new version released:**

```bash
# Option 1: One command (easiest)
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)

# Option 2: Built-in command
/update-plugin
```

Both update to latest version automatically.

---

## Learn More

### Documentation

**For Users**:
- **[Architecture Overview](docs/ARCHITECTURE.md)** - How the two-layer system works (hooks + agents)
- **[PROJECT.md Philosophy](docs/PHILOSOPHY.md)** - Why PROJECT.md-first development works
- **[Workflows & Examples](docs/WORKFLOWS.md)** - Real-world usage patterns and examples
- **[Command Reference](docs/REFERENCE.md)** - Complete list of commands and what they do
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

**For Contributors**:
- **[Development Guide](docs/DEVELOPMENT.md)** - How to contribute to the plugin
- **[Maintaining Philosophy](docs/MAINTAINING-PHILOSOPHY.md)** - Keep core principles active
- **[Security](docs/SECURITY.md)** - Security audit and best practices

### Key Concepts

**PROJECT.md-First Development**: Every feature validates against your project's strategic goals before work begins. Zero scope creep.

**Two-Layer Architecture**:
- **Layer 1 (Hooks)**: Automatic enforcement on every commit (alignment, security, tests)
- **Layer 2 (Agents)**: AI assistance via commands (research, plan, implement, review)

**Details**: See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

### Support

- **Issues**: https://github.com/akaszubski/autonomous-dev/issues
- **Discussions**: https://github.com/akaszubski/autonomous-dev/discussions
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)

---

## What You Get

**20 Commands** - Full SDLC automation
**20 AI Agents** - Specialized for each task
**22 Skills** - Deep domain knowledge (progressive disclosure)
**42 Hooks** - Automatic quality enforcement
**18 Libraries** - Reusable Python utilities

**Philosophy**: Automation > Reminders > Hope

Automate quality so you focus on creative work, not manual checks.

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

**Ready to try it?** Start with `/auto-implement "your feature here"`

For detailed documentation, see [docs/](docs/)
