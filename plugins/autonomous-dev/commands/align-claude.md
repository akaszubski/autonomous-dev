---
name: align-claude
description: "[DEPRECATED] Use /align --docs instead. Check CLAUDE.md alignment."
argument-hint: "(no arguments needed)"
allowed-tools: [Bash, Read, Write, Edit, Grep, Glob]
deprecated: true
redirect-to: align
---

# /align-claude - DEPRECATED

**This command is deprecated.** Use `/align --docs` instead.

## Deprecation Notice

```
⚠️  DEPRECATED: /align-claude is deprecated and will be removed in v4.0.0

Migration:
  Old: /align-claude
  New: /align --docs

The new /align command with --docs flag provides documentation alignment.
```

## Implementation

This command automatically redirects to `/align --docs` with the same functionality.

**ACTION REQUIRED**: Display the deprecation notice above, then invoke the new `/align --docs` command.

Use the Skill tool to invoke the `align` skill with docs flag:

```
skill: "align"
args: "--docs"
```

Or run the validation script directly:

```bash
python .claude/hooks/validate_claude_alignment.py
```

---

## Migration Guide

| Old Command | New Command |
|-------------|-------------|
| `/align-claude` | `/align --docs` |

The behavior is identical - CLAUDE.md alignment checking.

---

**Deprecated in**: v3.48.0 (Issue #268)
**Removal planned**: v4.0.0
**Replacement**: `/align --docs`
