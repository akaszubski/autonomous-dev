# Autonomous Development Plugin for Claude Code

**Speak requirements. Get production-ready code. Guaranteed alignment with your strategic goals.**

Claude Code plugin that automates the full software development lifecycle with PROJECT.md-first validation: alignment → research → plan → test → implement → review → security → documentation.

**Version**: v3.21.0 | **Status**: Production Ready | **Last Updated**: 2025-11-15

---

## What It Does

**You say**: "Add JWT authentication to the API"

**Claude Code**:
1. **Validates against PROJECT.md** - Checks feature aligns with GOALS, SCOPE, CONSTRAINTS (blocks if misaligned)
2. Researches JWT best practices and security patterns
3. Plans the architecture and integration points
4. Writes tests first (TDD)
5. Implements the code to pass tests
6. Reviews code quality and patterns
7. Scans for security vulnerabilities
8. Updates documentation

**All automated. All aligned with your strategic goals.**

### The Key Differentiator: PROJECT.md-First

**Every feature validates against your strategic direction BEFORE work begins.**

Define once in `.claude/PROJECT.md`:
- **GOALS**: What success looks like
- **SCOPE**: What's IN and OUT
- **CONSTRAINTS**: Technical and business limits
- **ARCHITECTURE**: How the system works

Features outside your SCOPE are automatically **blocked**. Zero scope creep. Zero wasted effort.

**Example**:
```
Your PROJECT.md says:
  SCOPE:
    IN: User authentication, API endpoints
    OUT: Admin dashboard, analytics

You request: "/auto-implement Add analytics dashboard"

Result: ❌ BLOCKED
  "Analytics is OUT OF SCOPE per PROJECT.md.
   Either remove analytics from OUT scope, or modify request."
```

No work happens until alignment is fixed. This saves hours of wasted implementation.

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
- ✅ Validate against PROJECT.md (alignment check)
- ✅ Research validation patterns
- ✅ Plan the implementation
- ✅ Write tests first
- ✅ Implement the code
- ✅ Review quality
- ✅ Scan security
- ✅ Update docs

**Typical time**: 20-30 minutes (fully automated)

### Batch Processing Multiple Features (NEW in v3.22.0)

Process multiple features sequentially with automatic context management:

```bash
# Create features file
cat > sprint-backlog.txt <<EOF
# Authentication
Add user login with JWT
Add password reset flow

# API improvements
Add rate limiting to API
Add API versioning
EOF

# Execute all features
/batch-implement sprint-backlog.txt
```

**Benefits**:
- ✅ Automatic context clearing between features (prevents context bloat)
- ✅ Progress tracking with timing per feature
- ✅ Continue-on-failure mode (process all features even if some fail)
- ✅ Summary report with success/failure counts

**Use Cases**: Sprint backlogs, technical debt cleanup, feature parity, bulk refactoring

**Typical time**: 20-30 minutes per feature (same as `/auto-implement`)

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
- **[PROJECT.md Philosophy](docs/MAINTAINING-PHILOSOPHY.md)** - Why PROJECT.md-first development works
- **[Workflows & Examples](docs/WORKFLOWS.md)** - Real-world usage patterns and examples
- **[Command Reference](plugins/autonomous-dev/commands/)** - Complete list of commands and what they do
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions (coming soon)

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
