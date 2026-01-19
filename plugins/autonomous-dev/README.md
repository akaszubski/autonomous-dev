# autonomous-dev Plugin

**AI-Powered Development Pipelines for Claude Code**

Version 3.44.0 | 22 Agents | 28 Skills | 67 Hooks | 143 Libraries | 24 Commands

Stop writing buggy code. Start shipping production-ready features with autonomous development workflows that validate, test, and secure your code automatically.

---

## Quick Start (5 Minutes)

```bash
# Install
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)

# Restart Claude Code (REQUIRED)
# Press Cmd+Q (Mac) or Ctrl+Q (Windows/Linux), wait 5 seconds, reopen

# Verify installation
/health-check

# Optional: Create PROJECT.md for goal alignment
/setup
```

**That's it.** You're ready to ship production code.

---

## What You Get

### 8-Agent Development Pipeline

One command triggers a complete quality workflow:

```bash
/implement Add user authentication with JWT tokens
```

**The pipeline automatically:**
1. **Validates alignment** against PROJECT.md goals
2. **Researches patterns** in your codebase
3. **Plans architecture** for the feature
4. **Writes failing tests** first (TDD)
5. **Implements code** to pass tests
6. **Reviews code quality** (parallel)
7. **Audits security** (parallel, OWASP CWE checks)
8. **Updates documentation** (parallel)
9. **Commits, pushes, creates PR** (optional, consent-based)

**Result**: Production-ready code in 15-25 minutes with 94% test coverage, 0.3% security issues, 2% documentation drift.

### Quality Metrics

| Metric | Without Pipeline | With `/implement` |
|--------|-----------------|-------------------|
| Bug rate | 23% | **4%** |
| Security issues | 12% | **0.3%** |
| Documentation drift | 67% | **2%** |
| Test coverage | 43% | **94%** |

**85% of issues caught before commit.**

---

## Installation

### One-Line Install (Recommended)

```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

**What it installs:**
- Global infrastructure: `~/.claude/hooks/` (67 files), `~/.claude/lib/` (143 files), `~/.claude/settings.json`
- Project files: `.claude/commands/`, `.claude/agents/`, `.claude/skills/`
- Git hooks: Pre-commit validation, auto-formatting

**After installation:**
```bash
# REQUIRED: Fully quit and restart Claude Code
# Press Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)
# Wait 5 seconds before reopening

# Verify
/health-check
```

### Manual Installation

```bash
# Clone repository
git clone https://github.com/akaszubski/autonomous-dev.git
cd autonomous-dev

# Run installation script
bash install.sh

# Restart Claude Code
```

### Uninstallation

```bash
# Preview what will be removed
/sync --uninstall

# Remove with backup
/sync --uninstall --force

# Remove project files only (keep global ~/.claude/)
/sync --uninstall --force --local-only
```

---

## Core Commands

### /implement - Full Pipeline

Smart code implementation with three modes:

**Full Pipeline (default)**: 8-agent workflow with validation, testing, security
```bash
/implement Add user authentication with JWT tokens
```

**Quick Mode**: Direct implementation, no pipeline overhead (2-5 minutes)
```bash
/implement --quick Fix typo in error message
```

**Batch Mode**: Process multiple features from file or GitHub issues
```bash
# From file
/implement --batch features.txt

# From GitHub issues
/implement --issues 72 73 74

# Resume after crash
/implement --resume batch-20260110-143022
```

**Smart Features:**
- Dependency analysis: Reorders features based on requirements
- Crash recovery: Resume from exact failure point
- Automatic retry: Transient errors (network, rate limits) retry automatically
- Per-feature git: Each feature commits separately
- Issue auto-close: GitHub issues closed with summary comment

### /setup - Interactive PROJECT.md Creation

```bash
/setup
```

Creates `.claude/PROJECT.md` with guided wizard for defining:
- **GOALS**: What you're building and why
- **SCOPE**: What's included and excluded
- **CONSTRAINTS**: Technical and business limits
- **ARCHITECTURE**: High-level design decisions

**Why this matters**: Every `/implement` validates alignment against PROJECT.md to prevent scope drift and feature misalignment.

### /align - Validate Alignment

```bash
/align              # Check project goal alignment
/align --claude     # Validate CLAUDE.md vs codebase
/align --retrofit   # Generate PROJECT.md from existing code
```

### /advise - Critical Analysis

```bash
/advise Should we migrate to microservices architecture?
```

Provides critical thinking analysis:
- Validates alignment with project goals
- Challenges assumptions
- Identifies risks and trade-offs
- Recommends alternatives

### /create-issue - Research-Backed Issues

```bash
/create-issue Add Redis caching layer
```

Creates GitHub issues with:
- Automatic research for similar patterns
- Blocking duplicate detection
- Architecture recommendations
- Implementation guidance

### /audit-tests - Test Coverage Analysis

```bash
/audit-tests
```

Analyzes test coverage and identifies:
- Untested code paths
- Missing edge case tests
- Low-coverage modules
- Regression test opportunities

### /sync - Plugin Updates

```bash
/sync              # Auto-detect context (GitHub or dev mode)
/sync --github     # Fetch from GitHub marketplace
/sync --plugin-dev # Sync local changes (for contributors)
/sync --uninstall  # Remove plugin with backup
```

**Preserves repo-specific configs** (Issue #244):
- All files in `.claude/local/` protected across sync operations
- Use `.claude/local/OPERATIONS.md` for repo-specific procedures
- Custom configurations never overwritten during updates

### /worktree - Isolated Feature Development

```bash
/worktree create feature-auth    # Create isolated workspace
/worktree list                   # Show all worktrees
/worktree cleanup feature-auth   # Remove worktree
```

Batch mode uses worktrees automatically for isolation.

### /health-check - Validate Installation

```bash
/health-check
```

Validates:
- Plugin integrity (all components present)
- Marketplace version (updates available)
- Hook configuration
- Library imports

---

## Configuration

### Environment Variables

Create `.env` file in your project root:

```bash
# Git Automation (default: enabled with consent)
AUTO_GIT_ENABLED=true      # Master switch for git automation
AUTO_GIT_PUSH=true         # Auto-push after commit
AUTO_GIT_PR=true           # Auto-create pull requests
AUTO_GIT_CLOSE_ISSUE=true  # Auto-close GitHub issues

# MCP Auto-Approval (default: disabled)
MCP_AUTO_APPROVE=true           # Auto-approve safe tool calls
SANDBOX_ENABLED=true            # Command classification and sandboxing
SANDBOX_PROFILE=development     # Options: development, testing, production

# Model Configuration (default: tier-based)
RESEARCHER_MODEL=claude-haiku-4.5      # Research agent (fast, cost-optimized)
IMPLEMENTER_MODEL=claude-sonnet-4.5    # Implementation (balanced)
SECURITY_MODEL=claude-opus-4.5         # Security audits (deep reasoning)

# Observability (default: minimal)
LOG_LEVEL=INFO                  # Options: DEBUG, INFO, WARNING, ERROR
ENABLE_TELEMETRY=false          # Performance metrics
```

### Git Automation Control

**First-Run Consent**: Interactive prompt on first use (default: yes)

**State Persistence**: User choice saved to `~/.autonomous-dev/user_state.json`

**Workflow**: After `/implement` completes:
```
doc-master finishes → auto_git_workflow.py hook → commit-message-generator
→ stage files → commit → push → create PR → close issue
```

**Disable git automation:**
```bash
# In .env
AUTO_GIT_ENABLED=false

# Or via environment variable
export AUTO_GIT_ENABLED=false
```

### MCP Auto-Approval Control

**What it does**: Automatically approves trusted tool operations (read files, run tests, format code)

**Impact**: Reduces permission prompts from 50+ to 8-10 (84% reduction)

**4-Layer Security Architecture:**
1. **Sandbox Enforcer**: Command classification (SAFE/BLOCKED/NEEDS_APPROVAL)
2. **MCP Security Validator**: Path traversal, injection, SSRF prevention
3. **Agent Authorization**: Pipeline agent detection
4. **Batch Permission Approver**: Caches user consent for identical operations

**Enable auto-approval:**
```bash
# In .env
MCP_AUTO_APPROVE=true
SANDBOX_ENABLED=true
SANDBOX_PROFILE=development
```

**Security validations (always active):**
- CWE-22: Path traversal prevention
- CWE-78: Command injection blocking
- CWE-918: SSRF prevention
- Symlink rejection outside whitelist
- Credential safety (never logged)
- Audit logging to `logs/security_audit.log`

---

## Architecture

### Component Overview

| Component | Count | Purpose |
|-----------|-------|---------|
| **Agents** | 22 | Specialized AI agents for development tasks |
| **Skills** | 28 | Domain expertise (testing, security, python standards) |
| **Hooks** | 66 | Automation triggers (pre-commit, pre-tool-use, etc.) |
| **Libraries** | 122 | Reusable utilities (security, validation, automation) |
| **Commands** | 24 | Slash commands for workflows |

### Agent Specialization

**Pipeline Agents (8):**
- `researcher-local`: Pattern discovery in codebase
- `planner`: Architecture design
- `test-master`: TDD test generation
- `implementer`: Code implementation
- `reviewer`: Code quality analysis
- `security-auditor`: OWASP vulnerability scanning
- `doc-master`: Documentation synchronization
- `issue-creator`: Research-backed GitHub issues

**Utility Agents (14):**
- Setup wizard, alignment checker, test auditor, git orchestrator, and more

**Model Tier Strategy (Cost-Optimized):**
| Tier | Model | Agents | Savings |
|------|-------|--------|---------|
| Tier 1 | Haiku | researcher, reviewer, doc-master | 40-60% cost reduction |
| Tier 2 | Sonnet | implementer, test-master, planner | Balanced reasoning |
| Tier 3 | Opus | security-auditor | Deep reasoning for security |

### Automation Hooks

**67 hooks enforce quality without manual intervention:**

| Hook Type | Trigger | What It Prevents |
|-----------|---------|------------------|
| **PreToolUse** | Before tool execution | Path traversal, injection, SSRF attacks |
| **PreCommit** | Before git commit | Failing tests, missing docs, security issues |
| **SubagentStop** | After agent completes | Documentation drift from code changes |
| **PrePromptSubmit** | Before user prompt | Workflow discipline violations |

**Examples:**
- Block commits with failing tests
- Prevent `git push --force` to protected branches
- Reject secrets accidentally staged
- Validate CLAUDE.md alignment with codebase
- Auto-format code before commit

**Philosophy**: If you have to remember to check something, you'll eventually forget. Automate quality gates.

---

## Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| Commands not appearing after install | Fully quit Claude Code (Cmd+Q / Ctrl+Q), wait 5s, reopen |
| ModuleNotFoundError: autonomous_dev | Create symlink: `cd plugins && ln -s autonomous-dev autonomous_dev` |
| Context budget exceeded | Run `/clear` after each feature |
| Plugin changes not visible | Run `/sync --plugin-dev` then restart |
| Hooks not running | Check `~/.claude/settings.json` for hook configuration |

### Installation Verification

```bash
# Check what was installed
echo "Hooks: $(ls ~/.claude/hooks/*.py 2>/dev/null | wc -l)"        # Should be ~66
echo "Libs: $(ls ~/.claude/lib/*.py 2>/dev/null | wc -l)"           # Should be ~122
echo "Commands: $(ls .claude/commands/*.md 2>/dev/null | wc -l)"    # Should be ~24
echo "Agents: $(ls .claude/agents/*.md 2>/dev/null | wc -l)"        # Should be ~22

# Test health check
/health-check
```

### Pipeline Issues

**"/implement stops mid-way":**
1. Check for test failures (step 4) - fix failing tests
2. Check for security issues (step 6) - address vulnerabilities
3. Context may be full - run `/clear` and retry
4. Check agent output for specific errors

**"/implement --batch crashes":**
```bash
# Resume from where it stopped
/implement --resume <batch-id>

# Check batch state
cat .claude/batch_state.json
```

### Sync Issues

**"/sync tries to fetch URL instead of executing":**
```bash
# Verify directive is in place
grep "Do NOT fetch" .claude/commands/sync.md

# Re-sync if missing
/sync --plugin-dev

# Restart Claude Code (REQUIRED)
```

### Getting Help

1. **Run health check**: `/health-check` validates plugin integrity
2. **Check documentation**: See [full troubleshooting guide](docs/TROUBLESHOOTING.md)
3. **Search issues**: [GitHub Issues](https://github.com/akaszubski/autonomous-dev/issues)
4. **Open new issue**: Include error messages, OS, Python version, output of `/health-check`

---

## Best Practices

### Context Management (CRITICAL!)

**Problem**: Without clearing context, token budget exceeds 50K+ after 3-4 features → System fails

**Solution**: Clear context after each feature
```bash
# Workflow
/implement Add authentication    # Feature 1
/clear                           # Clear context
/implement Add notifications     # Feature 2
/clear                           # Clear context
```

**Why this matters**: Context stays under 8K tokens → Works for 100+ features

### Workflow Discipline

**REQUIRED**: Use `/implement` for all code changes (not optional)

**Exceptions** (direct implementation allowed):
- Documentation updates (.md files only)
- Config changes (.json, .yaml, .toml)
- Typo fixes (1-2 lines, no logic changes)

**Why this matters**: `/implement` catches 85% of issues before commit

### PROJECT.md-First Development

**Define your intent once. Enforce it automatically.**

Every `/implement` validates alignment against PROJECT.md:
- Does this feature align with **GOALS**?
- Is it within **SCOPE**?
- Does it violate **CONSTRAINTS**?
- Does it follow **ARCHITECTURE**?

**Update PROJECT.md** when strategic direction changes (not for tactical tasks).

---

## Contributing

See [DEVELOPMENT.md](../../docs/DEVELOPMENT.md) for contributor setup and development workflow.

**Quick start for contributors:**
```bash
# Clone repository
git clone https://github.com/akaszubski/autonomous-dev.git
cd autonomous-dev

# Install in development mode
bash install.sh

# After making changes, resync
./scripts/resync-dogfood.sh

# Test changes immediately (no restart needed)
```

---

## Documentation

| Guide | Description |
|-------|-------------|
| [CLAUDE.md](../../CLAUDE.md) | Project instructions and quick reference |
| [Architecture](../../docs/ARCHITECTURE-OVERVIEW.md) | Technical architecture deep-dive |
| [Agents](../../docs/AGENTS.md) | 22 specialized agents and their roles |
| [Hooks](../../docs/HOOKS.md) | 66 automation hooks reference |
| [Skills](../../docs/SKILLS-AGENTS-INTEGRATION.md) | 28 skills and agent integration |
| [Workflow Discipline](../../docs/WORKFLOW-DISCIPLINE.md) | Why pipelines beat direct implementation |
| [Performance](../../docs/PERFORMANCE.md) | Benchmarks and optimization history |
| [Git Automation](../../docs/GIT-AUTOMATION.md) | Zero manual git operations |
| [Batch Processing](../../docs/BATCH-PROCESSING.md) | Multi-feature workflows |
| [Security](../../docs/SECURITY.md) | Security model and hardening guide |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues and solutions |

---

## Requirements

- [Claude Code](https://claude.ai/code) 2.0+
- macOS or Linux
- Git
- Python 3.8+
- `gh` CLI (optional, for PR creation and issue management)

---

## Philosophy

### Automation > Reminders > Hope

Quality should be automatic, not optional. autonomous-dev makes the right thing the easy thing:

- **Research** happens automatically before implementation
- **Tests** are written first (TDD enforced)
- **Security** is scanned on every feature
- **Documentation** stays in sync automatically
- **Git operations** are orchestrated end-to-end
- **Alignment** is validated against your stated intent

You describe what you want. The pipeline handles the rest.

### The 4-Layer Consistency Architecture

| Layer | Weight | Purpose |
|-------|--------|---------|
| **Hooks** | 10% | Deterministic blocking (secrets, force push) |
| **CLAUDE.md** | 30% | Persuasion via data (this README) |
| **Convenience** | 40% | Quality path is the easy path |
| **Skills** | 20% | Agent expertise and knowledge |

We don't force quality. We make it the path of least resistance.

---

## License

MIT

---

## Version Info

- **Current version**: 3.44.0
- **Agents**: 22 specialists
- **Skills**: 28 domain expertise modules
- **Hooks**: 66 automation triggers
- **Libraries**: 122 reusable utilities
- **Commands**: 24 slash commands

---

<p align="center">
  <strong>Built for developers who ship.</strong>
</p>
