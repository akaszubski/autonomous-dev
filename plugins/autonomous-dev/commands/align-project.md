---
name: align-project
description: "[DEPRECATED] Use /align instead. Analyze and fix project alignment."
argument-hint: "(no arguments needed)"
allowed-tools: [Task, Read, Grep, Glob]
deprecated: true
redirect-to: align
---

# /align-project - DEPRECATED

**This command is deprecated.** Use `/align` instead.

## Deprecation Notice

```
⚠️  DEPRECATED: /align-project is deprecated and will be removed in v4.0.0

Migration:
  Old: /align-project
  New: /align

The new /align command is the default project alignment mode.
```

## Implementation

This command automatically redirects to `/align` with the same functionality.

**ACTION REQUIRED**: Display the deprecation notice above, then invoke the new `/align` command.

Use the Skill tool to invoke the `align` skill:

```
skill: "align"
args: ""
```

Or invoke the alignment-analyzer agent directly as `/align` does.

---

## Migration Guide

| Old Command | New Command |
|-------------|-------------|
| `/align-project` | `/align` |

The behavior is identical - PROJECT.md alignment analysis.

---

**Deprecated in**: v3.48.0 (Issue #268)
**Removal planned**: v4.0.0
**Replacement**: `/align`
