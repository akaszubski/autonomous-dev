---
name: batch-implement
description: "[DEPRECATED] Use /implement --batch or --issues instead."
argument-hint: "<file> or --issues <nums> or --resume <id>"
allowed-tools: [Task, Read, Write, Bash, Grep, Glob]
deprecated: true
redirect-to: implement
---

# /batch-implement - DEPRECATED

**This command is deprecated.** Use `/implement --batch`, `/implement --issues`, or `/implement --resume` instead.

## Deprecation Notice

```
⚠️  DEPRECATED: /batch-implement is deprecated and will be removed in v4.0.0

Migration:
  Old: /batch-implement features.txt
  New: /implement --batch features.txt

  Old: /batch-implement --issues 72 73 74
  New: /implement --issues 72 73 74

  Old: /batch-implement --resume batch-123
  New: /implement --resume batch-123

The new /implement command consolidates all implementation modes.
```

## Implementation

This command automatically redirects to `/implement` with the appropriate flags.

ARGUMENTS: {{ARGUMENTS}}

**ACTION REQUIRED**: Display the deprecation notice above, then invoke the new `/implement` command.

Parse ARGUMENTS to determine the redirect:

```python
args = "{{ARGUMENTS}}"

if "--issues" in args:
    # /batch-implement --issues 72 73 → /implement --issues 72 73
    redirect_args = args  # Already has --issues flag
elif "--resume" in args:
    # /batch-implement --resume id → /implement --resume id
    redirect_args = args  # Already has --resume flag
else:
    # /batch-implement file.txt → /implement --batch file.txt
    redirect_args = f"--batch {args}"
```

Use the Skill tool to invoke the `implement` skill:

```
skill: "implement"
args: "[redirect_args computed above]"
```

Or execute the batch workflow from `/implement` directly.

---

## Migration Guide

| Old Command | New Command |
|-------------|-------------|
| `/batch-implement file.txt` | `/implement --batch file.txt` |
| `/batch-implement --issues 1 2 3` | `/implement --issues 1 2 3` |
| `/batch-implement --resume id` | `/implement --resume id` |

The behavior is identical - batch processing with auto-worktree isolation.

---

**Deprecated in**: v3.47.0 (Issue #203)
**Removal planned**: v4.0.0
**Replacement**: `/implement --batch`, `/implement --issues`, `/implement --resume`
