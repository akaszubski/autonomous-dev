---
description: Preview GitHub Issues without creating (dry run for issue commands)
---

# Preview Issues (Dry Run)

**Preview what issues would be created without actually creating them**

---

## Usage

```bash
/issue-preview
```

**Also works with other issue commands**:
```bash
/issue-auto --dry-run
/issue-from-test test_export_speed --dry-run
/issue-from-genai "No progress indicator" --dry-run
```

**Source**: Last test run or specified source
**Time**: < 5 seconds
**Output**: Preview only (no issues created)

---

## What This Does

Shows what issues would be created WITHOUT creating them:
- ✅ Issue titles
- ✅ Issue types (bug, enhancement, etc.)
- ✅ Priorities (high, medium, low)
- ✅ Labels
- ✅ Full body text
- ❌ **Does NOT create issues**

Perfect for testing before actual creation.

---

## Expected Output

```
PREVIEW: Issues that would be created (dry run)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Issue #1 (would be created)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Title: UX: Add progress indicator for large exports
Type: enhancement
Priority: medium
Labels: ux, automated, genai-finding

Body:
## UX Friction Point

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
- Test: tests/uat/test_export.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Issue #2 (would be created)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Title: UX: Real-time form validation
Type: enhancement
Priority: low
Labels: ux, automated, genai-finding

Body:
## UX Friction Point

Form validation only happens on submit.
Users don't get feedback until they try to submit.

## Recommendation
Add real-time validation hints as user types.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUMMARY (DRY RUN)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Would create: 2 issues
  - 0 high priority
  - 1 medium priority
  - 1 low priority

NO ISSUES CREATED - This was a preview only

To create these issues:
  /issue-auto             Create all
  /issue-from-genai "..." Create specific
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## When to Use

- ✅ **Before first issue creation** (see what will be created)
- ✅ Testing issue creation logic
- ✅ Reviewing issue quality
- ✅ For documentation/demos
- ✅ When unsure about automated issues

---

## Dry Run Mode

**Add `--dry-run` to any issue command**:

```bash
# Preview auto-detected issues
/issue-auto --dry-run

# Preview specific test issue
/issue-from-test test_export_speed --dry-run

# Preview GenAI finding issue
/issue-from-genai "No progress indicator" --dry-run

# Preview manual issue
/issue-create --title "Add dark mode" --dry-run
```

---

## Output Format

**Each preview shows**:
1. Issue number (simulated)
2. Title
3. Type and priority
4. Labels
5. Full body text
6. Summary stats

**Color-coded priorities**:
- 🔴 High - Critical issues
- 🟡 Medium - Important issues
- 🟢 Low - Nice-to-have issues

---

## Next Steps

**After preview, choose**:
- `/issue-auto` - Create all issues
- `/issue-from-test <name>` - Create specific test issue
- `/issue-from-genai "<finding>"` - Create specific GenAI issue
- `/issue-create` - Create manual issue
- Nothing - Don't create any issues

---

## Comparison

| Command | Creates Issues | Shows Preview |
|---------|----------------|---------------|
| `/issue-preview` | No | Yes (all) |
| `/issue-auto` | Yes | No |
| `/issue-auto --dry-run` | No | Yes (all) |
| `/issue-from-test ... --dry-run` | No | Yes (one) |

---

## Related Commands

- `/issue-auto` - Auto-create all issues
- `/issue-from-test` - Create from test
- `/issue-from-genai` - Create from GenAI
- `/issue-create` - Manual creation

---

**Use this to preview issues before creating. Completely safe - creates nothing.**
