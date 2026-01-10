---
name: auto-implement
description: "[DEPRECATED] Use /implement instead. Full SDLC workflow."
argument-hint: "Feature description"
allowed-tools: [Task, Read, Write, Edit, Bash, Grep, Glob, WebSearch, WebFetch]
deprecated: true
redirect-to: implement
---

# /auto-implement - DEPRECATED

**This command is deprecated.** Use `/implement` instead.

## Deprecation Notice

```
⚠️  DEPRECATED: /auto-implement is deprecated and will be removed in v4.0.0

Migration:
  Old: /auto-implement "add user authentication"
  New: /implement "add user authentication"

The new /implement command is the default full pipeline mode.
```

## Implementation

This command automatically redirects to `/implement` with the same arguments.

ARGUMENTS: {{ARGUMENTS}}

**ACTION REQUIRED**: Display the deprecation notice above, then invoke the new `/implement` command with the same ARGUMENTS.

Use the Skill tool to invoke the `implement` skill with the same arguments:

```
skill: "implement"
args: "{{ARGUMENTS}}"
```

Or execute the full pipeline workflow from `/implement` directly.

---

## Migration Guide

| Old Command | New Command |
|-------------|-------------|
| `/auto-implement "feature"` | `/implement "feature"` |

The behavior is identical - full 8-agent pipeline.

---

**Deprecated in**: v3.47.0 (Issue #203)
**Removal planned**: v4.0.0
**Replacement**: `/implement`
