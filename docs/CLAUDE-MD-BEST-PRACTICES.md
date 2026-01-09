# CLAUDE.md Best Practices Guide

**Created**: 2026-01-03
**Source**: Web research + community best practices (2024-2025)
**Purpose**: Reference for optimizing CLAUDE.md file size and structure

---

## Executive Summary

| Metric | Best Practice | Current | Target |
|--------|---------------|---------|--------|
| Line count | < 300 lines | 832 lines | 250-300 |
| Token count | ~500-800 | ~6,000 | < 1,000 |
| Instruction count | ~150-200 max | 100+ | < 100 |

**Key Insight**: CLAUDE.md should be a "table of contents" with pointers, not a comprehensive manual.

---

## What to Include (Essential)

1. **WHY** - Project goals and philosophy (2-3 sentences)
2. **WHAT** - High-level project description (1 paragraph)
3. **HOW** - Common commands, setup instructions (bullet list)
4. **Repository etiquette** - Branch naming, commit conventions
5. **Code style** - Formatting rules, design patterns
6. **Testing** - How to run tests (1-2 lines)
7. **Warnings** - Gotchas, edge cases, unexpected behaviors

---

## What to Exclude (Anti-Patterns)

1. **Duplicated info** - Link to docs, don't repeat content
2. **Historical notes** - Version history belongs in CHANGELOG
3. **Detailed troubleshooting** - Link to TROUBLESHOOTING.md
4. **Verbose explanations** - Keep instructions concise
5. **Issue numbers everywhere** - Reference sparingly
6. **Aspirational claims** - Document reality only

---

## Progressive Disclosure Pattern

### Instead of This (Inline Detail):
```markdown
## Workflow Discipline
[100+ lines of explanation, data tables, philosophy, metrics...]
```

### Do This (Link to Detail):
```markdown
## Workflow Discipline
Use `/auto-implement` for features, bugs, API changes. Direct implementation for docs, configs, typos.

**Why:** Catches 85% of issues before commit. See [docs/WORKFLOW.md](docs/WORKFLOW.md) for metrics.
```

---

## Recommended Structure (Target: ~250 lines)

```markdown
# Project Name - CLAUDE.md

## Overview
[2-3 sentences about the project]

## Quick Start
- Setup: `command`
- Test: `command`
- Build: `command`

## Key Principles
1. [Principle 1 - one line]
2. [Principle 2 - one line]
3. [Principle 3 - one line]

## Code Style
- [Convention 1]
- [Convention 2]

## Commands
| Command | Purpose |
|---------|---------|
| /auto-implement | Feature development |
| /create-issue | Issue creation |

## Architecture
[2-3 sentences + link to detailed docs]

## Troubleshooting
See [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

## More Info
- [DEVELOPMENT.md](docs/DEVELOPMENT.md) - Development workflow
- [ARCHITECTURE-OVERVIEW.md](docs/ARCHITECTURE-OVERVIEW.md) - System design
- [SECURITY.md](docs/SECURITY.md) - Security guidelines
```

---

## Validation Enforcement (Issue #197)

CLAUDE.md now has automated validation checks enforced at commit time via `validate_claude_alignment.py` hook:

### Line Count Limits
- **Hard limit**: 300 lines
- **Warning threshold**: 280 lines (93% of limit)
- **Current state**: 288 lines (safe, but approaching warning)

### Section Count Limits
- **Hard limit**: 20 sections
- **Warning threshold**: 18 sections (90% of limit)
- **Target**: 15-20 sections

### Character Limits (Phased Enforcement)

Strictness controlled by `CLAUDE_VALIDATION_PHASE` environment variable:

| Phase | Limit | Behavior | Target |
|-------|-------|----------|--------|
| 1 (default) | 35,000 chars | Warning only | Current state |
| 2 | 25,000 chars | Error (blocks commit) | Near future |
| 3 | 15,000 chars | Error (blocks commit) | Final goal |

**Usage**:
```bash
# Check current phase (default phase 1)
echo $CLAUDE_VALIDATION_PHASE

# Enforce stricter validation during refactoring
CLAUDE_VALIDATION_PHASE=2 git commit  # Blocks if >25k chars
```

### Error Messages

All validation errors and warnings reference this guide for remediation:

```
CLAUDE.md exceeds 300-line limit (301 lines).
See docs/CLAUDE-MD-BEST-PRACTICES.md for guidance.
```

---

## Measurement Metrics

After optimization, validate:

1. **Line count**: < 300 lines
2. **Token count**: < 1,000 tokens
3. **Read time**: < 5 minutes for new developer
4. **AI recall**: Claude can list core principles from memory
5. **Discovery**: Claude knows where to find detailed docs

---

## Sources

- [Anthropic: Claude Code Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices)
- [Claude Blog: Using CLAUDE.md Files](https://claude.com/blog/using-claude-md-files)
- [HumanLayer: Writing a Good CLAUDE.md](https://www.humanlayer.dev/blog/writing-a-good-claude-md)
- [Arize: CLAUDE.md Best Practices](https://arize.com/blog/claude-md-best-practices-learned-from-optimizing-claude-code-with-prompt-learning/)
- [Apidog: 5 Best Practices for Claude.md](https://apidog.com/blog/claude-md/)

---

## Action Items for Issue #195

1. **Move to separate docs**:
   - Workflow Discipline details → docs/WORKFLOW.md
   - Architecture details → docs/ARCHITECTURE-OVERVIEW.md (expand existing)
   - Batch Processing → docs/BATCH-PROCESSING.md (already exists)
   - Git Automation → docs/GIT-AUTOMATION.md (already exists)
   - Troubleshooting → docs/TROUBLESHOOTING.md (consolidate)

2. **Remove from CLAUDE.md**:
   - Historical version notes (v3.24.0, Issue #79, etc.)
   - Detailed data tables (move to relevant docs)
   - Verbose explanations (replace with links)
   - Component version table (move to docs/COMPONENTS.md)

3. **Keep in CLAUDE.md**:
   - Project overview (2-3 sentences)
   - Quick start commands
   - Key principles (bullet list)
   - Command reference table
   - Links to detailed docs
