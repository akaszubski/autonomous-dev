---
name: align-project-retrofit
description: "[DEPRECATED] Use /align --retrofit instead. Brownfield project retrofit."
argument-hint: "[--dry-run] [--auto]"
allowed-tools: [Bash, Read, Write, Grep, Edit]
deprecated: true
redirect-to: align
---

# /align-project-retrofit - DEPRECATED

**This command is deprecated.** Use `/align --retrofit` instead.

## Deprecation Notice

```
⚠️  DEPRECATED: /align-project-retrofit is deprecated and will be removed in v4.0.0

Migration:
  Old: /align-project-retrofit
  New: /align --retrofit

  Old: /align-project-retrofit --dry-run
  New: /align --retrofit --dry-run

  Old: /align-project-retrofit --auto
  New: /align --retrofit --auto

The new /align command with --retrofit flag provides brownfield project retrofit.
```

## Implementation

This command automatically redirects to `/align --retrofit` with the same functionality.

**ACTION REQUIRED**: Display the deprecation notice above, then invoke the new `/align --retrofit` command.

Parse arguments for --dry-run and --auto flags and pass them through:

Use the Skill tool to invoke the `align` skill with retrofit flag:

```
skill: "align"
args: "--retrofit [additional flags from original command]"
```

---

## Migration Guide

| Old Command | New Command |
|-------------|-------------|
| `/align-project-retrofit` | `/align --retrofit` |
| `/align-project-retrofit --dry-run` | `/align --retrofit --dry-run` |
| `/align-project-retrofit --auto` | `/align --retrofit --auto` |

The behavior is identical - 5-phase brownfield retrofit workflow.

---

**Deprecated in**: v3.48.0 (Issue #268)
**Removal planned**: v4.0.0
**Replacement**: `/align --retrofit`
