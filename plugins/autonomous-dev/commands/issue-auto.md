---
description: Auto-create GitHub Issues from last test run (detects failures & findings)
---

# Issue Auto-Creation

**Automatically create GitHub Issues from test results**

---

## Usage

```bash
/issue-auto
```

**Source**: Last test run (pytest or GenAI)
**Time**: < 5 seconds
**Output**: GitHub Issues created

---

## What This Does

Auto-detects issues from last test execution:
- ❌ **Test failures** (pytest) → Bug issues
- ⚠️ **UX friction** (`/test-uat-genai`) → UX improvement issues
- ⚠️ **Architectural drift** (`/test-architecture`) → Technical debt issues
- 💡 **Optimization opportunities** → Enhancement issues

**Creates GitHub Issue for each finding** with full context.

---

## Expected Output

```
Auto-detecting issues from last test run...

Found test run: /test-uat-genai (completed 2 minutes ago)

Findings detected:
1. UX Friction: No progress indicator (medium priority)
2. UX Friction: Form validation timing (low priority)

Creating GitHub issues...

✅ Issue #42: "UX: Add progress indicator for exports"
   Priority: Medium
   Type: enhancement
   Labels: ux, automated
   https://github.com/user/repo/issues/42

✅ Issue #43: "UX: Real-time form validation"
   Priority: Low
   Type: enhancement
   Labels: ux, automated
   https://github.com/user/repo/issues/43

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Created 2 issues from last test run
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Requirements

**GitHub CLI** (`gh`) must be installed:
```bash
# Install
brew install gh  # macOS
# or: https://cli.github.com/

# Authenticate
gh auth login
```

---

## Issue Details

**Each issue includes**:
- **Title**: Clear, actionable description
- **Priority**: High, Medium, or Low
- **Type**: bug, enhancement, technical-debt
- **Labels**: automated, ux, architecture, performance
- **Body**:
  - Problem description
  - User impact
  - Recommended solution
  - File locations
  - Related test output

**Example issue body**:
```markdown
## Problem
No progress indicator shown during large CSV exports (> 1000 rows).

## User Impact
- Users don't know if export is working
- May close browser thinking it's frozen
- Poor UX for data-heavy workflows

## Recommendation
Add progress bar showing:
- Current row / total rows
- Estimated time remaining
- Cancel button

## Location
- File: src/export.py:export_to_csv()
- Test: tests/uat/test_export.py:test_export_large_dataset

## Found By
GenAI UAT Validation (/test-uat-genai)
Priority: Medium
```

---

## When to Use

- ✅ After `/test-uat-genai` (UX findings)
- ✅ After `/test-architecture` (drift findings)
- ✅ After `/test-complete` (all findings)
- ✅ After pytest failures (bug tracking)

---

## Configuration (.env)

```bash
# Issue auto-creation settings
GITHUB_AUTO_ISSUE=true          # Enable auto-creation
GITHUB_ISSUE_LABEL=automated    # Label for auto-issues
GITHUB_ASSIGN_TO_ME=false       # Auto-assign to current user
```

---

## Related Commands

- `/issue-from-test` - Create issue from specific test
- `/issue-from-genai` - Create issue from GenAI finding
- `/issue-create` - Manual issue creation
- `/issue-preview` - Preview without creating

---

**Use this after test runs to automatically track all findings. Zero manual issue creation.**
