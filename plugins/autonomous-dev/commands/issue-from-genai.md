---
description: Create GitHub Issue from GenAI finding (UX or architecture)
---

# Create Issue from GenAI Finding

**Create GitHub Issue from GenAI validation finding**

---

## Usage

```bash
/issue-from-genai "<finding_description>"
```

**Examples**:
```bash
/issue-from-genai "No progress indicator"
/issue-from-genai "Reviewer agent using Sonnet instead of Haiku"
/issue-from-genai "Form validation happens too late"
```

**Source**: GenAI validation (`/test-uat-genai` or `/test-architecture`)
**Time**: < 5 seconds
**Output**: Single GitHub Issue

---

## What This Does

Creates GitHub Issue from GenAI finding:
1. Search last GenAI validation for finding
2. Extract full context (impact, recommendation)
3. Identify affected files
4. Create descriptive GitHub Issue
5. Tag appropriately (ux, architecture, optimization)

---

## Expected Output

```
Creating issue from GenAI finding: "No progress indicator"...

Found in last validation: /test-uat-genai (2 minutes ago)

Finding details:
  Type: UX Friction
  Priority: Medium
  Impact: Users don't know if export is working
  Recommendation: Add progress bar

Creating GitHub issue...

✅ Issue #45: "UX: Add progress indicator for large exports"
   Priority: Medium
   Type: enhancement
   Labels: ux, automated, genai-finding
   https://github.com/user/repo/issues/45

Issue body:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## UX Friction Point

No progress indicator shown during large CSV exports (> 1000 rows).

## User Impact
- Users don't know if export is working
- May close browser thinking it's frozen
- Causes anxiety on slow connections
- Poor UX for data-heavy workflows

## Current Behavior
Export starts silently, completes without feedback.
No way to know progress or time remaining.

## Recommended Solution
Add progress indicator showing:
1. Current progress (rows exported / total rows)
2. Estimated time remaining
3. Cancel button for long-running exports
4. Success notification on completion

## Technical Details
- Affected file: src/export.py:export_to_csv()
- Related test: tests/uat/test_export.py
- Implementation complexity: Medium (2-4 hours)

## Found By
GenAI UAT Validation (/test-uat-genai)
Date: 2025-10-20
Priority: Medium (user-facing UX issue)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Finding Types

**UX Findings** (from `/test-uat-genai`):
- Progress indicators missing
- Error messages unclear
- Form validation timing
- Accessibility issues
- Performance perception

**Architecture Findings** (from `/test-architecture`):
- Model optimization opportunities
- Agent pipeline deviations
- Context management issues
- Architectural drift
- Principle violations

---

## Issue Labels

**Auto-assigned**:
- `ux` - UX friction points
- `architecture` - Architectural issues
- `optimization` - Performance/cost savings
- `technical-debt` - Drift from standards
- `genai-finding` - All GenAI findings
- `automated` - Auto-created

---

## When to Use

- ✅ After `/test-uat-genai` (UX findings)
- ✅ After `/test-architecture` (architectural findings)
- ✅ When you want single issue (not all via `/issue-auto`)
- ✅ For specific high-priority findings

---

## Priority Override

**Auto-assigned priority** based on finding type:
- Critical: User-blocking UX issues
- High: Major architectural drift
- Medium: UX friction, optimization opportunities
- Low: Minor improvements

**Override if needed**:
```bash
/issue-from-genai "Form validation" --priority=high
```

---

## Requirements

**GitHub CLI** (`gh`) must be installed and authenticated.

---

## Related Commands

- `/issue-auto` - Auto-detect all GenAI findings
- `/issue-from-test` - Create from test failure
- `/issue-create` - Manual creation
- `/test-uat-genai` - Run UX validation first
- `/test-architecture` - Run architecture validation first

---

**Use this to create focused issues for specific GenAI findings. More control than /issue-auto.**
