# Command Frontmatter Schema

**Purpose**: Standardize YAML frontmatter for slash commands in Claude Code.

**Last Updated**: 2026-01-09
**Issue**: #213 - Standardize command YAML frontmatter

---

## Overview

All slash commands (`.claude/commands/*.md`) use YAML frontmatter to define metadata, permissions, and usage information. This schema defines the standard structure and naming conventions.

---

## Field Definitions

### Required Fields

#### `name:`
**Type**: string
**Description**: Command name (without `/` prefix)
**Example**: `name: auto-implement`
**Rules**:
- Use kebab-case (lowercase with hyphens)
- No spaces or underscores
- Must match filename (e.g., `auto-implement.md` → `name: auto-implement`)

#### `description:`
**Type**: string
**Description**: Brief description of what the command does
**Example**: `description: "Autonomously implement a feature with full SDLC workflow"`
**Rules**:
- One-line summary
- May include flag hints in parentheses
- Use quotes if contains special characters

### Optional Fields

#### `argument-hint:`
**Type**: string
**Description**: Shows expected arguments/flags in autocomplete
**Example**: `argument-hint: "Feature description (e.g., 'user authentication with JWT tokens')"`
**Rules**:
- Use kebab-case (hyphen, not underscore)
- Document all CLI flags used in command body
- Show optional arguments in brackets: `[--flag]`
- Show required arguments without brackets: `<file>`

#### `allowed-tools:`
**Type**: array of strings
**Description**: MCP tools the command is permitted to use (security whitelist)
**Example**: `allowed-tools: [Task, Read, Write, Edit, Bash, Grep, Glob]`
**Rules**:
- Use array syntax: `[Tool1, Tool2]`
- Title case for tool names
- Common tools: `Task`, `Read`, `Write`, `Edit`, `Bash`, `Grep`, `Glob`, `WebSearch`, `WebFetch`

#### `version:`
**Type**: string
**Description**: Command version (semantic versioning)
**Example**: `version: 1.0.0`
**Rules**:
- Follow semver: `MAJOR.MINOR.PATCH`
- Increment on breaking changes

#### `author:`
**Type**: string
**Description**: Command author
**Example**: `author: autonomous-dev`

#### `category:`
**Type**: string
**Description**: Command category
**Example**: `category: core`
**Values**: `core`, `utility`, `experimental`

#### `model:`
**Type**: string
**Description**: Recommended Claude model
**Example**: `model: sonnet`
**Values**: `haiku`, `sonnet`, `opus`

#### `tags:`
**Type**: array of strings
**Description**: Searchable tags
**Example**: `tags: [plugin, update, marketplace]`

---

## Naming Convention: Kebab-Case

**All frontmatter field names use kebab-case** (lowercase words separated by hyphens).

### Correct (Kebab-Case)
```yaml
name: my-command
description: "Does something"
argument-hint: "[--flag]"
allowed-tools: [Bash]
```

### Incorrect (Snake_Case)
```yaml
name: my-command
description: "Does something"
argument_hint: "[--flag]"    # ❌ WRONG - uses underscore
allowed_tools: [Bash]
```

**Why kebab-case?**
- Standard YAML convention
- Matches command naming (e.g., `auto-implement.md`)
- Consistent with flag naming (e.g., `--dry-run`)
- Avoids confusion with Python variable names

---

## Complete Example

### Basic Command

```yaml
---
name: health-check
description: Validate all plugin components are working correctly
argument-hint: "[--verbose]"
allowed-tools: [Read, Bash, Grep, Glob]
---
```

### Full Example with All Fields

```yaml
---
name: auto-implement
description: Autonomously implement a feature with full SDLC workflow
argument-hint: "Feature description (e.g., 'user authentication with JWT tokens')"
allowed-tools: [Task, Read, Write, Edit, Bash, Grep, Glob, WebSearch, WebFetch]
version: 3.45.0
author: autonomous-dev
category: core
model: sonnet
tags: [implementation, pipeline, autonomous]
---
```

### Command with Mode Flags

```yaml
---
name: sync
description: "Sync plugin files (--github default, --env, --marketplace, --plugin-dev, --all, --uninstall)"
argument-hint: "--github | --env | --marketplace | --plugin-dev | --all | --uninstall [--force]"
allowed-tools: [Bash]
version: 1.0.0
category: core
---
```

---

## Deprecated Fields

### `tools:` (deprecated)

**Status**: DEPRECATED - Use `allowed-tools:` instead
**Reason**: `tools:` is documentation-only and not enforced. `allowed-tools:` is the security-validated field.

#### Migration

```yaml
# ❌ OLD (deprecated)
---
name: my-command
tools: [Bash, Read]
allowed-tools: [Bash, Read]  # Duplicate!
---

# ✅ NEW (correct)
---
name: my-command
allowed-tools: [Bash, Read]  # Single source of truth
---
```

**If you see both fields**: Remove `tools:`, keep `allowed-tools:`

---

## Validation

### Automated Checks

Commands are validated by:
- **Pre-commit hook**: `.claude/hooks/validate_command_frontmatter_flags.py`
- **Test suite**: `tests/regression/progression/test_issue_213_command_frontmatter_standardization.py`

### Manual Validation

Check frontmatter syntax:
```bash
# Check for underscore fields (should be kebab-case)
grep -r "argument_hint:" .claude/commands/

# Check for duplicate tools fields
grep -r "^tools:" .claude/commands/ | grep -l "allowed-tools:"

# Run validation hook
python3 .claude/hooks/validate_command_frontmatter_flags.py
```

### Common Issues

**Issue**: `argument_hint:` (underscore)
**Fix**: Change to `argument-hint:` (hyphen)

**Issue**: Both `tools:` and `allowed-tools:` present
**Fix**: Remove `tools:`, keep `allowed-tools:`

**Issue**: Flags in body not documented in frontmatter
**Fix**: Add flags to `description:` or `argument-hint:` field

---

## Best Practices

### Document All Flags

If your command uses `--flag` syntax, document it in frontmatter:

```yaml
# ✅ GOOD
---
name: sync
description: "Sync plugin files (--github default, --env, --marketplace)"
argument-hint: "--github | --env | --marketplace [--force]"
---

# ❌ BAD (flags in body but not documented)
---
name: sync
description: "Sync plugin files"
# Missing argument-hint field
---
```

### Use Quotes for Special Characters

```yaml
# ✅ GOOD
description: "Command with (parentheses) and --flags"
argument-hint: "--flag1 | --flag2 [--flag3]"

# ⚠️ RISKY (may parse incorrectly)
description: Command with (parentheses) and --flags
```

### Minimal is Fine

Not every command needs all fields:

```yaml
# ✅ GOOD - minimal but complete
---
name: clear
description: Clear conversation context
allowed-tools: []
---
```

### Security: Least Privilege

Only include tools actually needed:

```yaml
# ✅ GOOD - only what's needed
---
name: health-check
allowed-tools: [Read, Bash]
---

# ❌ BAD - over-permissioned
---
name: health-check
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Task, WebSearch]
---
```

---

## Related Documentation

- **Validation Hook**: `.claude/hooks/validate_command_frontmatter_flags.py`
- **Test Suite**: `tests/regression/progression/test_issue_213_command_frontmatter_standardization.py`
- **Security**: `docs/MCP-SECURITY.md` (tool whitelisting)
- **Commands**: `.claude/commands/*.md` (live examples)

---

## Change History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-09 | Initial schema documentation (Issue #213) |
| | | Standardized kebab-case naming |
| | | Deprecated `tools:` field |
| | | Documented all standard fields |

---

**Questions?** See Issue #213 or run `/health-check` to validate command frontmatter.
