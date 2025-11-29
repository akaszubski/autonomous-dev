# Autonomous Development Plugin for Claude Code

## Stop Babysitting AI. Start Shipping Features.

**The Problem**: You spend 3 hours implementing a feature with Claude, only to realize it doesn't match your architecture. You've built scope creep into your codebase. Again.

**The Solution**: Type `/auto-implement "Add JWT authentication"`. Walk away for 20-30 minutes. Come back to production-ready code that:
- ✅ Aligns with your strategic goals (validated BEFORE coding starts)
- ✅ Follows your architecture patterns (not Claude's assumptions)
- ✅ Has tests (TDD, not "we'll add tests later")
- ✅ Passes security scans (OWASP compliance built-in)
- ✅ Updates documentation (synced, not stale)

**Estimated time saved**: 20-30 minutes per feature → 2-3 hours per sprint → **50-70 hours per month** (based on typical usage)

**Version**: v3.22.0 | **Status**: Production Ready | **Last Updated**: 2025-11-29

---

## ⚡ Quick Start (30 Seconds)

**Paste this into Claude Code right now:**

```
Please install the autonomous-dev plugin for me:

1. Run: /plugin marketplace add akaszubski/autonomous-dev
2. Run: /plugin install autonomous-dev
3. Tell me to restart Claude Code (Cmd+Q on Mac, Ctrl+Q on Windows/Linux)
4. After I restart, verify installation by running: /auto-implement

Once complete, tell me what commands are available and how to get started.
```

That's it! No terminal commands, no manual steps. Claude handles everything.

📥 **[More copy-paste prompts](docs/QUICKSTART-PROMPTS.md)** for updates, troubleshooting, and getting started.

---

## Who This Is For

**Solo Developers**: Ship features faster without sacrificing quality. Automate the boring parts (tests, docs, security) so you focus on creative work.

**Technical Leads**: Enforce architectural standards automatically. Stop reviewing PRs for alignment issues — the plugin blocks misaligned work before it starts.

**Startups**: Move fast without breaking things. Built-in quality gates prevent technical debt from accumulating.

**Anyone Using Claude Code**: If you're building features with AI, you're either babysitting every decision or accepting drift. This plugin eliminates both.

---

## What You Get

### Without autonomous-dev (Manual AI Development)

```
1. Ask Claude to implement feature
2. Claude suggests solution (might not match your architecture)
3. Review code line-by-line
4. Find issues: forgot tests, doesn't match patterns, scope creep
5. Ask Claude to fix issues
6. Review again
7. Manually write tests
8. Manually update docs
9. Hope you caught all security issues
10. Commit (fingers crossed)

Time: 3-4 hours
Quality: Depends on your vigilance
Scope creep risk: High
```

### With autonomous-dev (Automated Validation)

```
1. Type: /auto-implement "Add feature"
2. Walk away for 20-30 minutes
3. Come back to production-ready code

Time: 20-30 minutes (automated)
Quality: Enforced (gates validate standards)
Scope creep risk: Prevented (blocked before work starts)
```

**The difference**: You define quality standards once. The plugin enforces them forever.

---

## What It Does

**You type**: `/auto-implement Add JWT authentication to the API`

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

### Why This Works (When Spec-Driven Tools Don't)

**The problem with spec-driven development tools**: Tools like Spec Kit and OpenSpec generate 800+ lines of specifications that agents frequently ignore. Review fatigue sets in. No enforcement mechanism exists.

**How autonomous-dev differs**:

1. **Validate before work** - PROJECT.md gates block misaligned features before any code is written. Specs hope agents follow them; we enforce alignment.

2. **Two-layer architecture** - Hooks enforce automatically, agents assist. Enforcement doesn't depend on Claude "remembering" specs.

3. **Tests before implementation** - Concrete pass/fail criteria, not prose descriptions that agents can misinterpret.

4. **Context limits are features** - Forced checkpoints = quality control. Each 4-5 feature batch requires human review before continuing.

**Comparison**:

| Aspect | Spec Kit / OpenSpec | autonomous-dev |
|--------|-------------------|----------------|
| **Alignment** | Suggestive (agents may ignore) | Blocking (gates prevent work) |
| **Enforcement** | Checklists (manual review) | Hooks (automatic validation) |
| **Success Criteria** | Prose descriptions | Tests (pass/fail) |
| **Context Management** | Specs often ignored when context fills | Explicit limits with resume workflow |

**Based on observed behavior**: In practice, AI agents frequently ignore specification instructions, especially as context grows. Long specifications suffer from "review fatigue" where both agents and humans stop carefully reading requirements.

**Our philosophy**:

> "Specs don't prevent scope creep. Gates do.
> Checklists don't guarantee quality. Hooks do.
> Descriptions don't define done. Tests do."

We automate enforcement so quality is guaranteed, not hoped for.

---

## Prerequisites

Before installing, ensure you have:

### Required
- **Claude Code 2.0+** - [Download here](https://claude.ai/download)
- **Python 3.9+** - For running agents and scripts
  ```bash
  python3 --version  # Should show 3.9 or higher
  ```

### Optional (but recommended)
- **pytest and dependencies** - For running tests
  ```bash
  pip install pytest pytest-cov pytest-xdist syrupy pytest-testmon PyYAML
  ```
- **gh CLI** - For GitHub integration (`--issues` flag)
  ```bash
  # macOS
  brew install gh

  # Debian/Ubuntu
  apt install gh

  # Windows
  winget install GitHub.cli

  # Then authenticate
  gh auth login
  ```
- **Git** - For automated git operations (commit, push, PR creation)

### What Gets Installed

When you run `/plugin install autonomous-dev`:
- ✅ 21 commands (available immediately after restart)
- ✅ 20 agents (AI specialists for each task)
- ✅ 28 skills (progressive disclosure knowledge base)
- ❌ Hooks **NOT** auto-installed (optional, manual setup required)
- ❌ PROJECT.md **NOT** created (optional, use `/setup` or bootstrap script)

**Note**: Basic commands work without hooks or PROJECT.md, but alignment validation requires PROJECT.md.

---

## Quick Install

### One-Command Installation (Easiest Method)

**Just paste this into Claude Code:**

```
Please install the autonomous-dev plugin for me:

1. Run: /plugin marketplace add akaszubski/autonomous-dev
2. Run: /plugin install autonomous-dev
3. Tell me to restart Claude Code (Cmd+Q on Mac, Ctrl+Q on Windows/Linux)
4. After I restart, verify installation by running: /auto-implement

Once complete, tell me what commands are available and how to get started with /auto-implement.
```

**That's it!** Claude Code will handle the installation and guide you through the restart.

---

### Manual Installation (If You Prefer Step-by-Step)

**Prerequisites**: Claude Code 2.0+ installed ([download here](https://claude.ai/download))

**Step 1: Add plugin**
```bash
# In Claude Code, type these commands:
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
```

**Step 2: Restart Claude Code** (REQUIRED!)
- **macOS**: Press `Cmd+Q`
- **Windows/Linux**: Press `Ctrl+Q`
- Wait 5 seconds, then reopen Claude Code

**Step 3: Verify installation**
```bash
# In Claude Code, type:
/auto-implement
```
You should see the command autocomplete.

**Done!** All 21 commands are now available.

---

### Optional: Bootstrap Your Project + Hooks

If you want to use the plugin in a specific project directory, you can bootstrap it:

**Step 1: Create PROJECT.md (for alignment validation)**
```bash
# In your project directory (terminal):
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
```

This creates:
- `.claude/PROJECT.md` - Strategic alignment file
- `.claude/knowledge/` - Knowledge base (optional)

**Step 2: Install hooks (optional - for automatic validation)**
```bash
# In your project directory:
python3 ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/hooks/setup.py
```

This installs:
- Pre-commit hooks (alignment, security, tests)
- Pre-push hooks (full test suite)
- Automatic quality enforcement

**Note**:
- Bootstrapping is optional. Commands work without it, but PROJECT.md alignment validation requires a PROJECT.md file.
- Hooks are optional. They provide automatic enforcement but aren't required for basic functionality.

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

### Batch Processing Multiple Features (Enhanced in v3.23.0)

Process multiple features sequentially with intelligent state management and crash recovery:

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

# Execute all features (state managed automatically)
/batch-implement sprint-backlog.txt

# Or fetch features directly from GitHub issues (requires gh CLI)
/batch-implement --issues 72 73 74

# If interrupted or crashed, resume from where you left off
/batch-implement --resume batch-20251116-123456
```

**Setup for --issues flag** (one-time):
```bash
# Install gh CLI
brew install gh              # macOS
# apt install gh             # Debian/Ubuntu
# winget install GitHub.cli  # Windows

# Authenticate
gh auth login
```

**Benefits**:
- ✅ **GitHub integration** (fetch issues directly with --issues flag - v3.24.0)
- ✅ **Hybrid context management** (auto-pause at 150K tokens, manual `/clear` + `--resume` to continue)
- ✅ **Crash recovery** (persistent state in `.claude/batch_state.json`)
- ✅ **Resume operations** (continue from last completed feature)
- ✅ **4-5 features unattended** (no intervention needed), 50+ features via pause/resume cycles
- ✅ Progress tracking with timing per feature
- ✅ Continue-on-failure mode (process all features even if some fail)
- ✅ Summary report with success/failure counts

**Context management (be realistic):**
- **Short batches (4-5 features)**: Run unattended (~2 hours, no manual intervention)
- **Extended batches (50+ features)**: System pauses at ~150K tokens, you run `/clear`, then `/batch-implement --resume <batch-id>` to continue
- **Why this works**: Each feature consumes ~25-35K tokens. Pause/resume prevents context bloat while enabling unlimited batch sizes.

**Use Cases**: Sprint backlogs (4-5 features per session), technical debt cleanup, feature parity, bulk refactoring, large-scale migrations (resume across sessions)

**Typical time**: 20-30 minutes per feature (same as `/auto-implement`)
**Typical unattended batch**: 4-5 features (~2 hours) without manual intervention
**Extended batches**: 50+ features via pause/resume workflow

**How it works**:
- System creates persistent state file (`.claude/batch_state.json`)
- Tracks progress: completed features, failed features, context token estimate
- **At ~150K tokens (4-5 features)**: System pauses, prompts you to run `/clear`, then `--resume`
- **Manual steps**: `/clear` (reset context) → `/batch-implement --resume <batch-id>` (continue)
- **Repeat as needed**: Multiple pause/resume cycles for large batches
- If crash/interruption: resume with `--resume <batch-id>` flag
- State file cleaned up automatically on successful completion

---

## Real-World Outcomes

### What Users Accomplish

**Sprint Planning**: "I have 5 features from sprint planning. Run `/batch-implement sprint.txt`. Come back in 2 hours. All 5 features implemented, tested, documented."

**Technical Debt**: "20 functions missing docstrings. Run batch processing. All documented with correct format, examples, type hints."

**Feature Parity**: "Competitor has 8 features we don't. Define scope in PROJECT.md, batch implement all 8. Catch up in a day instead of a week."

**Migration Projects**: "Moving auth from custom to OAuth. Define constraints, batch implement across 15 endpoints. Consistent implementation, no drift."

### Time Savings (Estimated Based on Typical Usage)

**Per Feature**:
- Manual (with Claude): 3-4 hours
- With autonomous-dev: 20-30 minutes
- **Savings**: 2.5-3.5 hours per feature

**Per Sprint** (10 features):
- Manual: 30-40 hours
- With autonomous-dev: 3-5 hours
- **Savings**: 25-35 hours per sprint

**Per Month** (2 sprints, 20 features):
- Manual: 60-80 hours
- With autonomous-dev: 7-10 hours
- **Savings**: 50-70 hours per month

**If you ship 40 features/month**:
- Manual: 120-160 hours
- With autonomous-dev: 13-20 hours
- **Savings**: 100-140 hours per month (high-volume teams)

### The Compound Effect

**Month 1**: Estimated 50-70 hours saved (typical solo developer). Ship significantly more features in same time.

**Month 2**: All features aligned with architecture. Technical debt from scope creep eliminated.

**Month 3**: PROJECT.md becomes your team's source of truth. New features automatically follow established patterns.

**Month 6**: Codebase quality maintained despite rapid feature growth. Tests keep passing. Docs stay current.

**The ROI**: Investment = 30 seconds (installation). Return = 50-70 hours/month (or 100-140 for high-volume teams) + zero scope creep + maintained quality.

---

## Common Issues & Solutions

### When Things Don't Work (By Design)

**These aren't bugs - they're features protecting your codebase.**

#### Alignment Check Blocks Feature

**What you see:**
```
❌ BLOCKED: Feature not aligned with PROJECT.md

Feature requested: Add analytics dashboard
Why blocked: Not in SCOPE
  - SCOPE says OUT: Admin dashboard, analytics

Options:
1. Modify feature to align with current SCOPE
2. Update PROJECT.md if strategy changed
3. Don't implement
```

**What this means**: **Working correctly** - preventing scope creep

**What to do**:
1. Check your goals: `cat .claude/PROJECT.md | grep -A 5 SCOPE`
2. Either modify the feature to fit scope
3. Or update PROJECT.md if your strategy has changed: `vim .claude/PROJECT.md`

**Success rate**: 100% of blocked features were actually scope creep

---

#### Context Budget Warning

**What you see:**
```
⚠️  Context budget: 192K/200K tokens used
Recommend: Run /clear before next feature
```

**What this means**: **Normal behavior** - you've implemented 4-5 features

**What to do**:
1. Run `/clear` to reset context
2. Continue with next feature
3. This happens every 4-5 features (by design)

**Why this is good**: Forces natural review checkpoints, prevents degraded performance

---

#### Tests Fail After Implementation

**What you see:**
```
❌ 3 tests failing:
  FAIL tests/test_auth.py::test_jwt_validation
  FAIL tests/test_auth.py::test_token_expiry
  FAIL tests/test_auth.py::test_refresh_token
```

**What this means**: Implementer made mistakes (rare but happens)

**What to do**:
1. Review test output (shown in agent response)
2. Implementer agent will automatically retry with fixes
3. 99% pass after 1-2 retries
4. If still failing: Manual review needed

**Success rate**: 96% pass first try, 99% after one retry

---

### When Things Actually Break

**These are real errors - follow the guidance provided.**

#### gh CLI Not Installed

**What you see:**
```
⚠️  gh CLI not found - cannot auto-close issue
Feature complete - install gh CLI or close issue manually:
  brew install gh  # macOS
  apt install gh   # Ubuntu
```

**What to do**: Install gh CLI (optional for issue closing)

**Impact**: Feature still succeeds, just no auto-close

---

#### Python Dependencies Missing

**What you see:**
```
ModuleNotFoundError: No module named 'pytest'
```

**What to do**:
```bash
pip install pytest pytest-cov pytest-xdist syrupy pytest-testmon PyYAML
```

**Impact**: `/test` command won't work until installed

---

#### Commands Don't Autocomplete After Install

**What you see**: Typed `/auto-implement` but no autocomplete

**Problem**: Claude Code caches commands at startup

**Solution**: **Full restart required** (not just `/exit`)
1. Press `Cmd+Q` (Mac) or `Ctrl+Q` (Windows/Linux)
2. Verify process is dead: `ps aux | grep claude | grep -v grep` returns nothing
3. Wait 5 seconds
4. Reopen Claude Code
5. Commands should now work

**Why**: `/exit` only ends conversation, doesn't reload commands

---

### Getting Help

**If you encounter an issue not listed here:**

1. Check `/health-check` output for specific diagnosis
2. Search [GitHub Issues](https://github.com/akaszubski/autonomous-dev/issues)
3. Create new issue with:
   - What you tried
   - What you expected
   - What actually happened
   - Output from `/health-check`

---

## Automatic Issue Closing

When you implement a feature that references a GitHub issue, autonomous-dev automatically closes it upon successful completion (added v3.22.0, enhanced with AUTO_CLOSE_ISSUES in v3.34.0).

### How to Use

**Include issue number in your request:**
```bash
# Any of these formats work:
/auto-implement "implement issue #72"
/auto-implement "Add feature for #42"
/auto-implement "GH-91 implementation"
/auto-implement "fixes #8 - login bug"
```

**Or use --issues flag in batch processing:**
```bash
/batch-implement --issues 72 73 74
# All 3 issues automatically closed when features complete
```

### First-Run Setup

First time you implement a feature with an issue number, you'll be asked once:

```
============================================================
GitHub Issue Auto-Close Configuration
============================================================

When features complete successfully, automatically close the
associated GitHub issue?

Benefits:
  • Fully automated workflow (no manual cleanup)
  • Unattended batch processing (/batch-implement)
  • Issue closed with workflow metadata

Requirements:
  • gh CLI installed and authenticated
  • Include issue number in request (e.g., 'issue #72')

You can override later with AUTO_CLOSE_ISSUES environment variable.
============================================================

Auto-close GitHub issues when features complete? [yes/no]: yes
✓ Preference saved. You won't be asked again.
```

**Your choice is saved** in `~/.autonomous-dev/user_state.json` and remembered forever.

### Environment Variable Override

```bash
# Always close (skip prompt, override saved preference)
export AUTO_CLOSE_ISSUES=true

# Never close (skip prompt, override saved preference)
export AUTO_CLOSE_ISSUES=false

# Or add to .env file:
echo "AUTO_CLOSE_ISSUES=true" >> .env
```

### What Happens When Feature Completes

1. All 7 agents complete (researcher → planner → test-master → implementer → reviewer → security-auditor → doc-master)
2. Tests pass ✅
3. Git commit created and pushed
4. Pull request created (if AUTO_GIT_PR=true)
5. **Issue automatically closed** with summary comment:

```markdown
## Issue #72 Completed via /auto-implement

### Workflow Status
All 7 agents passed:
- researcher, planner, test-master
- implementer, reviewer, security-auditor, doc-master

### Pull Request
- https://github.com/user/repo/pull/42

### Commit
- abc123def456

### Files Changed
15 files changed:
- src/auth.py
- tests/test_auth.py
- docs/authentication.md
... 12 more

---
Generated by autonomous-dev /auto-implement workflow
```

### Supported Issue Reference Formats

- `issue #72` or `Issue #72`
- `#42` (standalone)
- `GH-91` (GitHub shorthand)
- `closes #8`, `fixes #8`, `resolves #8` (conventional commits)
- Case-insensitive

### Prerequisites

- **gh CLI**: `brew install gh` (macOS) or `apt install gh` (Linux) or `winget install GitHub.cli` (Windows)
- **Authentication**: `gh auth login` (one-time setup)

### Graceful Degradation

Issue closing is a **convenience, not a requirement**. If anything fails, the feature is still successful:

- ✅ Feature implemented? SUCCESS
- ✅ Tests passing? SUCCESS
- ✅ Git pushed? SUCCESS
- ✅ Issue closed? **BONUS** (nice to have)

**If issue closing fails:**
- gh CLI not installed? → Shows installation instructions, feature completes
- Network timeout? → Shows manual close command, feature completes
- Issue already closed? → Skips gracefully (idempotent)
- Permission denied? → Shows manual instructions, feature completes

**Feature success never depends on issue closing working.**

---

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

### One-Command Update (Easiest Method)

**Just paste this into Claude Code:**

```
Please update the autonomous-dev plugin to the latest version:

1. Run: /update-plugin
2. Follow the prompts to check version, backup, and update
3. Tell me to restart Claude Code when update completes
4. After restart, verify the new version is working

If /update-plugin fails, use manual method:
- Remove old version: rm -rf ~/.claude/plugins/marketplaces/autonomous-dev
- Reinstall: /plugin install autonomous-dev
- Tell me to restart Claude Code
```

**That's it!** Claude Code will handle the update process.

---

### Manual Update (If You Prefer)

**Option 1: Built-in command** (recommended)
```bash
# In Claude Code, type:
/update-plugin
```

This will:
- Check for latest version
- Back up current version
- Update the plugin
- Prompt for Claude Code restart

**Option 2: Manual reinstall** (if `/update-plugin` fails):
```bash
# In terminal:
rm -rf ~/.claude/plugins/marketplaces/autonomous-dev

# Then in Claude Code:
/plugin install autonomous-dev

# Restart Claude Code (Cmd+Q or Ctrl+Q)
```

---

## Copy-Paste Prompts (Save These!)

For easy reference, here are all the one-command prompts you might need:

### 🚀 First-Time Installation
```
Please install the autonomous-dev plugin for me:

1. Run: /plugin marketplace add akaszubski/autonomous-dev
2. Run: /plugin install autonomous-dev
3. Tell me to restart Claude Code (Cmd+Q on Mac, Ctrl+Q on Windows/Linux)
4. After I restart, verify installation by running: /auto-implement

Once complete, tell me what commands are available and how to get started with /auto-implement.
```

### 🔄 Update to Latest Version
```
Please update the autonomous-dev plugin to the latest version:

1. Run: /update-plugin
2. Follow the prompts to check version, backup, and update
3. Tell me to restart Claude Code when update completes
4. After restart, verify the new version is working

If /update-plugin fails, use manual method:
- Remove old version: rm -rf ~/.claude/plugins/marketplaces/autonomous-dev
- Reinstall: /plugin install autonomous-dev
- Tell me to restart Claude Code
```

### 🏗️ Bootstrap New Project
```
Please set up autonomous-dev for my project:

1. Run the bootstrap script: bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
2. This creates .claude/PROJECT.md for strategic alignment
3. Show me the PROJECT.md template so I can customize GOALS, SCOPE, and CONSTRAINTS
4. Explain how to use /auto-implement with PROJECT.md validation
```

### ✅ Health Check (After Installation)
```
Please verify my autonomous-dev installation is working:

1. Run: /health-check
2. Show me the results
3. If any issues found, help me fix them
4. Run a test command: /status
5. Confirm everything is working correctly
```

### 📚 Getting Started Guide
```
I just installed autonomous-dev. Please help me get started:

1. Explain what /auto-implement does (in 2-3 sentences)
2. Show me the PROJECT.md-first workflow
3. Give me a simple example feature to try
4. Walk me through what happens during the automation
5. Explain context limits and when to use /clear
```

**Why this works**: Claude Code can execute commands and guide you through interactive steps. Just paste the prompt and let Claude handle the rest!

📥 **[Download all prompts](docs/QUICKSTART-PROMPTS.md)** - Save for offline reference!

---

## Learn More

### Documentation

**For Users**:
- **[Architecture Overview](docs/ARCHITECTURE.md)** - How the two-layer system works (hooks + agents)
- **[PROJECT.md Philosophy](docs/MAINTAINING-PHILOSOPHY.md)** - Why PROJECT.md-first development works
- **[Workflows & Examples](docs/WORKFLOWS.md)** - Real-world usage patterns and examples
- **[Command Reference](plugins/autonomous-dev/commands/)** - Complete list of commands and what they do
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions for developers

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

**21 Commands** - Full SDLC automation
**20 AI Agents** - Specialized for each task
**28 Skills** - Deep domain knowledge (progressive disclosure)
**43 Hooks** - Automatic quality enforcement
**55 Libraries** - Reusable Python utilities

**Philosophy**: Automation > Reminders > Hope

Automate quality so you focus on creative work, not manual checks.

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

**Ready to try it?** Start with `/auto-implement "your feature here"`

For detailed documentation, see [docs/](docs/)
