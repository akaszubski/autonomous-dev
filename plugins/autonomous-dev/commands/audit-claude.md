---
name: audit-claude
description: Validate CLAUDE.md structure against best practices spec (Issue #245)
argument-hint: ""
allowed-tools: [Read, Bash]
---

# CLAUDE.md Structure Auditor

Validate CLAUDE.md against best practices: stays lean (<100 lines), has required pointers, avoids forbidden content.

## Implementation

Run the structure validation script:

```bash
python plugins/autonomous-dev/hooks/audit_claude_structure.py
```

## What This Does

Validates CLAUDE.md against this spec:

### Required Items (7 checks)
- Project name/purpose (first 10 lines)
- Pointer to `.claude/local/OPERATIONS.md`
- Pointer to `.claude/PROJECT.md`
- `/implement` command reference
- `/sync` command reference
- `/clear` context reminder
- Workflow discipline note

### Forbidden Content (5 checks)
- Architecture sections (should be in docs/)
- Workflow step-by-step guides (should be in docs/)
- Troubleshooting sections (should be in docs/)
- Code blocks > 5 lines
- Sections > 20 lines

### Size Limits (2 checks)
- Total file > 100 lines (error)
- Total file > 90 lines (warning)

## Expected Output

**PASS Example:**
```
CLAUDE.md Audit Report
======================
Status: PASS

Required Items:
  [x] Project name/purpose
  [x] Pointer to .claude/local/OPERATIONS.md
  [x] Pointer to .claude/PROJECT.md
  [x] /implement command reference
  [x] /sync command reference
  [x] /clear context reminder
  [x] Workflow discipline note

Forbidden Content: None detected

Stats:
  Total lines: 66 (limit: 100)
  Sections over 20 lines: 0
```

**FAIL Example:**
```
CLAUDE.md Audit Report
======================
Status: FAIL

Required Items:
  [x] Project name/purpose
  [x] Pointer to .claude/local/OPERATIONS.md
  [ ] Pointer to .claude/PROJECT.md  <-- MISSING
  ...

Forbidden Content:
  Line 45-89: Architecture details (move to docs/ARCHITECTURE.md)
  Line 102-108: Code block > 5 lines (shorten or move to docs/)

Stats:
  Total lines: 142 (limit: 100)
  Sections over 20 lines: 2

Suggested Actions:
  1. Add pointer to .claude/PROJECT.md
  2. move to docs/ARCHITECTURE.md
  3. reduce from 142 to <100 lines
```

## When to Use

- Before committing CLAUDE.md changes
- After refactoring CLAUDE.md
- During code review of CLAUDE.md updates
- When onboarding new developers (verify docs are clean)

## Related Commands

- `/align-claude`: Validates component counts and version consistency
- `/health-check`: Full plugin health validation

## Distinction from /align-claude

| Aspect | `/audit-claude` | `/align-claude` |
|--------|-----------------|-----------------|
| Focus | Structure & size | Component counts |
| Checks | Required items, forbidden patterns, line limits | Agent/command/hook counts, version numbers |
| Goal | Keep CLAUDE.md lean | Keep CLAUDE.md accurate |

Both commands complement each other - use both for complete validation.
