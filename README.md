# autonomous-dev

[![Claude Code 2.0+](https://img.shields.io/badge/Claude%20Code-2.0+-blueviolet)](https://claude.ai/download)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![macOS](https://img.shields.io/badge/Platform-macOS-lightgrey)](https://apple.com/macos)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)

**Traditional software engineering meets AI.**

Claude is brilliant but drifts. It starts with a plan, then improvises. Documentation falls out of sync. Tests get "added later." Direction shifts mid-feature.

autonomous-dev provides **macro alignment with micro flexibility**:

- **Macro**: PROJECT.md defines goals, scope, constraints — Claude checks alignment before every feature
- **Micro**: Claude can still improve the implementation when it finds better patterns

```
research → plan → test → implement → review → security → docs → commit
```

Every step. Every feature. Documentation, tests, and code stay in sync automatically.

```bash
/auto-implement "issue #72"
```

---

## Quick Start (macOS)

```bash
# 1. Install
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)

# 2. Restart Claude Code (required - commands are cached)
# Press Cmd+Q, then reopen

# 3. Use
/auto-implement "your feature description"
```

**Requirements:**
- Claude Code 2.0+
- macOS (not tested on Windows/Linux)
- Python 3.9+

**System tools (install separately):**
- git: `xcode-select --install` or `brew install git`
- gh CLI: `brew install gh && gh auth login` (required for GitHub automation)

**For contributors:** Development dependencies are in `plugins/autonomous-dev/requirements-dev.txt` (pytest, coverage, etc.)

---

## The Problem We Solve

Claude working alone drifts. Claude working within a framework stays consistent.

| Without autonomous-dev | With autonomous-dev |
|------------------------|---------------------|
| Claude decides workflow per-session | Same 8-step pipeline every time |
| Plan drifts mid-implementation | Macro alignment checked, micro improvements allowed |
| Tests written "if time permits" | Tests written first (TDD enforced) |
| Documentation falls out of sync | Auto-updated every feature |
| "Best practices" from training data | Actual web search with source URLs |
| Scope creep ("while I'm here...") | Out-of-scope requests blocked |
| Manual commit/push/PR | Automated git workflow |

**The insight**: This isn't about limiting Claude. It's about **fusing traditional software engineering discipline with AI capability**. Claude brings intelligence; the framework brings consistency.

---

## What Actually Happens

When you run `/auto-implement "add user authentication"`:

| Step | What Happens | Time |
|------|--------------|------|
| 0. Alignment | Checks feature against PROJECT.md scope | <1 min |
| 1. Research | Searches codebase AND web (parallel) | 2-3 min |
| 1.1 Validation | **Verifies web search actually ran** (not hallucinated) | <1 min |
| 2. Planning | Designs implementation approach | 2-4 min |
| 3. TDD Tests | Writes failing tests first | 3-8 min |
| 4. Implementation | Makes tests pass | 3-8 min |
| 5-7. Validation | Review + Security + Docs (parallel) | 2-4 min |
| 8. Git | Commit, push, PR (automated) | <1 min |

**Total: 15-30 minutes** depending on complexity.

After completion:
- ✅ Code committed with conventional commit message
- ✅ Changes pushed to your branch
- ✅ Pull request created
- ✅ GitHub issue auto-closed

---

## Why Web Research Matters

Most AI coding tools answer from training data. That's fine for "how do I sort a list" but dangerous for "what's the current best practice for JWT authentication."

We force actual web search:

```
└─ Task (Research best practices) · 5 tool uses ✅
   ⎿  Web Search: JWT authentication best practices 2024...
```

If you see `0 tool uses`, the pipeline blocks:

```
❌ Web research failed: 0 WebSearch calls made.
   Results would be hallucinated. Retrying...
```

This validation was added because we caught Claude returning "best practices" that it never actually searched for.

---

## PROJECT.md: Your Scope Boundary

```markdown
# .claude/PROJECT.md

## GOALS
- Build REST API for user management
- Ship MVP by end of Q1

## SCOPE
IN: User CRUD, authentication, password reset
OUT: Admin dashboard, analytics, billing

## CONSTRAINTS
- Python 3.11+ with FastAPI
- PostgreSQL database
- JWT authentication (no sessions)
```

**Request something IN scope**: Claude follows your constraints.

**Request something OUT of scope**: Blocked immediately.

```
❌ BLOCKED: Feature not aligned with PROJECT.md

Feature requested: "Add analytics dashboard"
Why blocked: Explicitly OUT of scope
```

This prevents the "while I'm here, let me also refactor..." drift.

---

## Honest Benchmarks

We document **typical performance**, not marketing claims.

### Time Per Feature

| Complexity | Time | Example |
|------------|------|---------|
| Simple | 5-10 min | Add validation to existing endpoint |
| Medium | 15-20 min | New endpoint with tests |
| Complex | 25-35 min | Security system, major refactor |

### Session & Batch Limits

| Metric | Typical | Notes |
|--------|---------|-------|
| Features per context window | 4-8 | Auto-compaction handles this |
| Features per batch | 50+ | Fully automatic, survives context resets |
| Tokens per feature | 20-40K | Depends on complexity |

**Fully unattended**: `/batch-implement` handles context limits automatically. State persists externally, so when Claude auto-compacts, the next feature bootstraps fresh and continues. No manual intervention needed.

---

## Commands

| Command | Purpose |
|---------|---------|
| `/auto-implement "..."` | Full pipeline for one feature |
| `/batch-implement --issues 1 2 3` | Process multiple features |
| `/setup` | Create PROJECT.md interactively |
| `/sync` | Update plugin from GitHub |
| `/health-check` | Verify installation |
| `/align` | Fix alignment issues |
| `/create-issue "..."` | Create GitHub issue with research (--quick for fast mode) |

---

## What Gets Installed

```
~/.claude/              # Global (shared across projects)
├── hooks/              # Automation hooks
├── lib/                # Shared Python libraries
└── settings.json       # Hook configuration

.claude/                # Per-project
├── commands/           # Slash commands
├── agents/             # AI agents
├── config/             # Policy files
├── scripts/            # Utility scripts
└── PROJECT.md          # Your scope definition
```

**Why global components?** Claude Code's settings.json references hooks by absolute path. Global installation ensures hooks work in any project.

---

## Using in Multiple Repos

After the initial install, adding autonomous-dev to another project is simple:

```bash
# 1. Open the new project in Claude Code
cd /path/to/your/other/project

# 2. Sync commands and agents (global hooks already work)
/sync

# 3. Restart Claude Code to load new commands
# Press Cmd+Q, then reopen

# 4. Create PROJECT.md for this repo (optional but recommended)
/setup
```

**What `/sync` does:**
- Pulls commands to `.claude/commands/`
- Pulls agents to `.claude/agents/`
- Global hooks already work (installed to `~/.claude/hooks/`)

**Important:** Always restart Claude Code after `/sync` — commands are cached in memory.

---

## Known Limitations

### Platform
- **macOS tested** - Primary development platform
- Linux likely works (similar paths) but unverified
- Windows untested

### Technical
- **Restart required after `/sync`** - Commands are cached in memory
- **Python 3.9+ required** - For library code
- **gh CLI required** - For GitHub automation features

### Design
- **Context limits exist** - 4-8 features per window, but batch processing handles this
- **Complex installation** - Can't be marketplace-only due to global hooks requirement

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Commands not found | Restart Claude Code (`Cmd+Q`), not just close |
| Web research returns 0 tool uses | Should auto-retry; if not, the validation catches it |
| "Path outside project root" | Update plugin (`/sync`), we fixed `/tmp/` access |
| Features drift from scope | Create/update PROJECT.md with clear SCOPE section |

---

## What We're Not

- **Not a marketplace plugin** - Requires global installation
- **Not cross-platform** - macOS only (for now)
- **Not magic** - Claude still makes mistakes, just more consistently
- **Not for "vibe coding"** - This is for disciplined, production-quality work

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - How the two-layer system works
- [Agents](docs/AGENTS.md) - Specialized AI agents
- [Hooks](docs/HOOKS.md) - Automation hooks reference
- [Batch Processing](docs/BATCH-PROCESSING.md) - Multi-feature workflows
- [Git Automation](docs/GIT-AUTOMATION.md) - Auto-commit, push, PR
- [Environment Configuration](docs/ENV-CONFIGURATION.md) - All .env variables and settings
- [Troubleshooting](plugins/autonomous-dev/docs/TROUBLESHOOTING.md)

---

## Contributing

Issues and PRs welcome at [github.com/akaszubski/autonomous-dev](https://github.com/akaszubski/autonomous-dev).

This project uses itself for development (dogfooding). Every feature was built using `/auto-implement`.

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Summary

autonomous-dev is **traditional software engineering discipline for AI-assisted development**:

1. **Macro alignment** - PROJECT.md keeps direction consistent
2. **Micro flexibility** - Claude improves implementations when it finds better patterns
3. **Consistent pipeline** - Same 8 steps every time
4. **Real web research** - Validated, not hallucinated from training data
5. **Everything stays in sync** - Docs, tests, code updated together
6. **Batch processing** - 50+ features with crash recovery

**The fusion**: You define the direction. Claude brings the intelligence. The framework keeps everything consistent.

```bash
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)
# Restart Claude Code (Cmd+Q)
/auto-implement "your feature"
```
