# Claude Code Bootstrap - Project Instructions

**Last Updated**: 2025-10-19
**Project**: Autonomous Development Plugin for Claude Code 2.0

---

## Project Overview

**autonomous-dev** - Plugin repository for autonomous development in Claude Code.

**Core Plugin**: `autonomous-dev` - Agents, skills, and hooks for 10x faster development

**Install**:
```bash
/plugin marketplace add akaszubski/autonomous-dev
/plugin install autonomous-dev
# Exit and restart Claude Code (Cmd+Q or Ctrl+Q)
# Done! All commands work: /test, /format, /commit, etc.
```

---

## Context Management (CRITICAL!)

### Why This Matters

- ❌ Without clearing: Context bloats to 50K+ tokens after 3-4 features → System fails
- ✅ With clearing: Context stays under 8K tokens → Works for 100+ features

### After Each Feature: Clear Context

```bash
/clear
```

**What this does**: Clears conversation (not files!), resets context budget, maintains performance

**When to clear**:
- ✅ After each feature completes (mandatory)
- ✅ Before starting unrelated feature
- ✅ If responses feel slow

### Session Files Strategy

Agents log to `docs/sessions/` instead of context:

```bash
# Log action
python scripts/session_tracker.py agent_name "message"

# View latest session
cat docs/sessions/$(ls -t docs/sessions/ | head -1)
```

**Result**: Context stays small (200 tokens vs 5,000+ tokens)

---

## PROJECT.MD - Goal Alignment

[`.claude/PROJECT.md`](.claude/PROJECT.md) defines GOALS, SCOPE, CONSTRAINTS, ARCHITECTURE

**Before starting work**:

```bash
# Check alignment
cat .claude/PROJECT.md | grep -A 5 "## GOALS"

# Verify:
# - Does feature serve GOALS?
# - Is feature IN SCOPE?
# - Does feature respect CONSTRAINTS?
```

**Update when strategic direction changes**:
```bash
vim .claude/PROJECT.md
git add .claude/PROJECT.md
git commit -m "docs: Update project goals"
```

---

## Autonomous Development Workflow

1. **Alignment Check**: Verify feature aligns with PROJECT.md
2. **Research**: researcher agent finds patterns
3. **Planning**: planner agent creates plan
4. **TDD Tests**: test-master writes failing tests FIRST
5. **Implementation**: implementer makes tests pass
6. **Review**: reviewer checks quality
7. **Security**: security-auditor scans
8. **Documentation**: doc-master updates docs
9. **Context Clear**: `/clear` for next feature

---

## Architecture

### Agents (7 specialists)

Located: `plugins/autonomous-dev/agents/`

- **researcher**: Web research (WebSearch, WebFetch, Grep, Glob, Read)
- **planner**: Architecture planning (Read, Grep, Glob, Bash)
- **test-master**: TDD specialist (Read, Write, Edit, Bash, Grep, Glob)
- **implementer**: Code implementation (Read, Write, Edit, Bash, Grep, Glob)
- **reviewer**: Quality gate (Read, Bash, Grep, Glob)
- **security-auditor**: Security scanning (Read, Bash, Grep, Glob)
- **doc-master**: Documentation sync (Read, Write, Edit, Bash, Grep, Glob)

### Skills (6 core competencies)

Located: `plugins/autonomous-dev/skills/`

- **python-standards**: PEP 8, type hints, docstrings
- **testing-guide**: TDD workflow, pytest patterns
- **security-patterns**: OWASP, secrets management
- **documentation-guide**: Docstring format, README updates
- **research-patterns**: Web search strategies
- **engineering-standards**: Code quality standards

### Hooks (Automation)

Located: `plugins/autonomous-dev/hooks/`

- `auto_format.py`: black + isort (Python), prettier (JS/TS)
- `auto_test.py`: pytest on related tests
- `auto_enforce_coverage.py`: 80% minimum coverage
- `security_scan.py`: Secrets detection, vulnerability scanning

**Lifecycle hooks**:
- `UserPromptSubmit`: Display project context
- `SubagentStop`: Log agent completion to session

---

## Troubleshooting

### "Context budget exceeded"

```bash
/clear  # Then retry
```

### "Feature doesn't align with PROJECT.md"

1. Check goals: `cat .claude/PROJECT.md | grep GOALS`
2. Either: Modify feature to align
3. Or: Update PROJECT.md if direction changed

### "Agent can't use tool X"

Tool restrictions are intentional (security). If genuinely needed:
```bash
vim plugins/autonomous-dev/agents/[agent].md
# Add to tools: [...] list in frontmatter
```

---

## MCP Server (Optional)

For enhanced Claude Desktop integration, configure the MCP server:

**Location**: `.mcp/config.json`

**Provides**:
- Filesystem access (read/write repository files)
- Shell commands (git, python, npm, etc.)
- Git operations (status, diff, commit)
- Python interpreter (with virtualenv)

**Setup**:
```bash
# See .mcp/README.md for full setup instructions
```

---

## Quick Reference

### Installation
```bash
# 1. Add marketplace
/plugin marketplace add akaszubski/autonomous-dev

# 2. Install plugin
/plugin install autonomous-dev

# 3. Exit and restart Claude Code (REQUIRED!)
# Press Cmd+Q (Mac) or Ctrl+Q (Linux/Windows)
```

**Done!** All commands immediately work.

### Optional Setup
```bash
# Only if you want automatic hooks (auto-format on save, etc.)
python plugins/autonomous-dev/scripts/setup.py
```

### Updating
```bash
# 1. Uninstall
/plugin uninstall autonomous-dev

# 2. Exit and restart Claude Code (REQUIRED!)

# 3. Reinstall
/plugin install autonomous-dev

# 4. Exit and restart again
```

### Daily Workflow
```bash
# Start feature
# (describe feature to Claude)

# After feature completes
/clear
```

### Check Session Logs
```bash
cat docs/sessions/$(ls -t docs/sessions/ | head -1)
```

### Update Goals
```bash
vim .claude/PROJECT.md
```

---

## Philosophy

**Automation > Reminders > Hope**

- Automate repetitive tasks (formatting, testing, security, docs)
- Use agents, skills, hooks to enforce quality automatically
- Focus on creative work, not manual checks

**Research First, Test Coverage Required**

- Always research before implementing
- Always write tests first (TDD)
- Always document changes
- Make quality automatic, not optional

**Context is Precious**

- Clear context after features (`/clear`)
- Use session files for communication
- Stay under 8K tokens per feature
- Scale to 100+ features

---

**For detailed guides**: See `docs/UPDATES.md` and `plugins/autonomous-dev/README.md`

**For code standards**: See skills in `plugins/autonomous-dev/skills/`

**Last Updated**: 2025-10-19
