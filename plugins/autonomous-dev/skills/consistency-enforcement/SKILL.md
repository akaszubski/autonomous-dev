---
name: consistency-enforcement
version: 1.1.0
type: knowledge
description: Documentation consistency enforcement - prevents drift between README.md and actual codebase state. Auto-activates when updating docs, committing changes, or working with skills/agents/commands.
keywords: readme, documentation, commit, sync, update, skill, agent, command, count, marketplace, consistency, drift
auto_activate: true
allowed-tools: [Read]
---

# Consistency Enforcement Skill

**Layer 4 Defense Against Documentation Drift**

Auto-activates to maintain documentation consistency when working on docs, skills, agents, or commands.

**See:** [workflow.md](workflow.md) for step-by-step scenarios
**See:** [templates.md](templates.md) for checklists and commands

## When This Activates

Keywords: "readme", "documentation", "docs", "commit", "sync", "update", "skill", "agent", "command", "count", "marketplace", "consistency", "drift"

---

## Critical Consistency Rules

### Rule 1: README.md is Source of Truth

**All counts must match reality:**

```bash
# Count actual resources
ls -d plugins/autonomous-dev/skills/*/ | wc -l   # Skills
ls plugins/autonomous-dev/agents/*.md | wc -l    # Agents
ls plugins/autonomous-dev/commands/*.md | wc -l  # Commands
```

### Rule 2: All Docs Must Match README.md

These files MUST show the same counts:
- `README.md` (primary source)
- `docs/SYNC-STATUS.md`
- `docs/UPDATES.md`
- `INSTALL_TEMPLATE.md`
- `.claude-plugin/marketplace.json` (metrics)

### Rule 3: Never Reference Non-Existent Skills

```bash
# Verify skill exists before referencing
ls -1 plugins/autonomous-dev/skills/
```

### Rule 4: marketplace.json Matches Reality

```json
{
  "metrics": {
    "agents": 8,
    "skills": 12,
    "commands": 21
  }
}
```

---

## 4-Layer Defense System

| Layer | Location | Purpose |
|-------|----------|---------|
| 1 | `tests/test_documentation_consistency.py` | Automated CI/CD enforcement |
| 2 | `agents/doc-master.md` | Agent memory checklist |
| 3 | `hooks/validate_docs_consistency.py` | Pre-commit hook (optional) |
| 4 | This skill | Auto-reminder during work |

### Run Tests

```bash
pytest tests/test_documentation_consistency.py -v
```

---

## Quick Workflow

**When adding/removing skills, agents, or commands:**

1. Update README.md count
2. Update cross-reference files (SYNC-STATUS.md, UPDATES.md, etc.)
3. Update marketplace.json metrics
4. Run consistency tests
5. Commit

**See:** [workflow.md](workflow.md) for detailed scenarios

---

## Why This Matters

**Documentation drift causes user confusion:**

- README shows "9 Skills" but plugin has 12
- README mentions skill that doesn't exist
- User tries to use non-existent feature

**With 4-layer defense:**

- Layer 1: Tests fail in CI/CD
- Layer 2: doc-master catches before docs.json
- Layer 3: Pre-commit hook blocks commit
- Layer 4: This skill reminds during work

**Result**: Documentation always matches reality

---

## Integration

Works with:
- **documentation-guide**: HOW to write docs
- **git-workflow**: HOW to commit changes
- **project-management**: PROJECT.md consistency

---

## Related Files

- [workflow.md](workflow.md) - Step-by-step scenarios
- [templates.md](templates.md) - Checklists and commands
