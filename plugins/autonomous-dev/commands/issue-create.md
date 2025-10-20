---
description: Manually create GitHub Issue (custom title, description, labels)
---

# Create GitHub Issue Manually

**Create custom GitHub Issue with full control**

---

## Usage

```bash
/issue-create --title "<title>" --type <type> --priority <priority>
```

**Examples**:
```bash
/issue-create --title "Add dark mode" --type enhancement --priority medium

/issue-create \
  --title "Export crashes on large files" \
  --type bug \
  --priority high \
  --body "Export fails with OOM on files > 10MB"

/issue-create \
  --title "Migrate to Haiku for simple tasks" \
  --type optimization \
  --priority low
```

**Source**: Manual input
**Time**: < 5 seconds
**Output**: Single GitHub Issue

---

## What This Does

Creates GitHub Issue with specified parameters:
- Custom title
- Custom description
- Specified type (bug, enhancement, optimization, technical-debt)
- Specified priority (high, medium, low)
- Optional labels
- Optional assignment

---

## Expected Output

```
Creating GitHub issue...

Title: Add dark mode
Type: enhancement
Priority: medium

✅ Issue #46: "Add dark mode"
   Priority: Medium
   Type: enhancement
   Labels: enhancement, manual
   https://github.com/user/repo/issues/46

Issue created successfully!
```

---

## Parameters

**Required**:
- `--title` - Issue title (short, descriptive)

**Optional**:
- `--type` - Issue type:
  - `bug` - Something is broken
  - `enhancement` - New feature or improvement
  - `optimization` - Performance/cost optimization
  - `technical-debt` - Code quality, refactoring
  - Default: `enhancement`

- `--priority` - Issue priority:
  - `high` - Critical, blocking
  - `medium` - Important, should fix soon
  - `low` - Nice to have
  - Default: `medium`

- `--body` - Issue description (detailed)
  - If omitted, prompts for input

- `--labels` - Additional labels (comma-separated)
  - Example: `--labels "ui,accessibility"`

- `--assign` - Assign to user
  - Example: `--assign @me`

---

## Interactive Mode

**If body not provided**, enters interactive mode:

```bash
/issue-create --title "Add dark mode" --type enhancement

Enter issue description (or press Enter to skip):
> Add dark mode toggle to settings page.
>
> Should support:
> - System preference detection
> - Manual toggle
> - Persistent user choice
>
> [Press Ctrl+D when done]

✅ Issue #46 created
```

---

## Template-Based Creation

**Use templates for common issue types**:

```bash
# Bug report
/issue-create-bug "Export crashes on large files"

# Feature request
/issue-create-feature "Add dark mode support"

# Optimization
/issue-create-optimization "Use Haiku for simple reviews"
```

*(These are shortcuts that call `/issue-create` with preset types)*

---

## Example Issue

**Created issue**:
```markdown
# Add dark mode

**Type**: enhancement
**Priority**: medium

## Description
Add dark mode toggle to settings page.

## Requirements
- System preference detection
- Manual toggle in settings
- Persistent user choice

## Implementation
- Add toggle component
- Update theme context
- Store preference in localStorage

---
*Created manually via /issue-create*
```

---

## When to Use

- ✅ Feature requests
- ✅ Custom bug reports
- ✅ Planning tasks
- ✅ When automated issue creation doesn't fit

---

## Requirements

**GitHub CLI** (`gh`) must be installed and authenticated.

---

## Related Commands

- `/issue-auto` - Auto-create from test results
- `/issue-from-test` - Create from test failure
- `/issue-from-genai` - Create from GenAI finding
- `/issue-preview` - Preview before creating

---

**Use this for manual issue creation when automated tools don't fit your needs.**
