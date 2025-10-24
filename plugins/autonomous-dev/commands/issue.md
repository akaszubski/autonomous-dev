---
description: Create GitHub Issues with interactive menu (tests/GenAI/manual/preview)
---

# Create GitHub Issue

**Create GitHub Issues from test failures, GenAI findings, or manual input**

---

## Usage

```bash
/issue
```

**Time**: < 5 seconds per issue
**Interactive**: Detects available sources, then presents menu

---

## How It Works

The command runs in two steps:

### Step 1: Source Detection (Always Runs)

Scans for available issue sources:
- ✅ Last test run (pytest failures)
- ✅ Last GenAI validation (`/test-uat-genai`, `/test-architecture`)
- ✅ Manual input (you provide details)

### Step 2: Action Menu (You Choose)

After detection, you see:

```
┌─ Issue Sources Detected ────────────────────┐
│                                              │
│ Available sources:                           │
│                                              │
│ ✅ Last test run: 2 failures (3 min ago)     │
│ ✅ GenAI validation: 3 findings (10 min ago) │
│ ✅ Manual: Always available                  │
│                                              │
└──────────────────────────────────────────────┘

What would you like to do?

1. Auto-create from test failures (2 issues) ← Fast
2. Create from GenAI findings (3 issues)
3. Create manual issue (custom title/description)
4. Preview all (dry run - no issues created)
5. Cancel

Choice [1-5]:
```

**You type your choice (1-5)** - no need to remember which command to use!

---

## Option 1: Auto-Create from Tests

**Automatically create issues from test failures**:

Finds all failures from last test run:

```
Creating issues from test failures...

Source: pytest (3 minutes ago)

Found 2 failures:
  test_export_speed: FAILED (timeout)
  test_oauth_token: FAILED (assertion error)

Creating GitHub issues...

✅ Issue #42: "Bug: Export times out after 30 seconds"
   Type: bug
   Priority: high
   Labels: automated, test-failure, performance
   Body:
     Test: test_export_speed
     File: tests/test_exports.py:145
     Error: Timeout after 30s

     Stack trace:
     ...

✅ Issue #43: "Bug: OAuth token validation fails"
   Type: bug
   Priority: high
   Labels: automated, test-failure, auth
   Body:
     Test: test_oauth_token
     File: tests/test_auth.py:89
     Error: AssertionError: Token invalid

     Stack trace:
     ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Issues created: 2
View: https://github.com/user/repo/issues
```

**When to use**:
- ✅ After test run finds failures
- ✅ CI/CD pipeline failures
- ✅ Want automatic tracking
- ✅ Fast issue creation

**Benefits**:
- Full context (stack trace, file, line)
- Automatic labeling
- High priority for bugs

---

## Option 2: Create from GenAI Findings

**Create issues from GenAI validation findings**:

Finds all findings from last GenAI validation:

```
Creating issues from GenAI findings...

Source: /test-uat-genai (10 minutes ago)

Found 3 findings:
  UX Friction: No progress indicator (medium)
  UX Friction: Form validation timing (low)
  Architecture: Reviewer using wrong model (high)

Creating GitHub issues...

✅ Issue #44: "UX: Add progress indicator for exports"
   Type: enhancement
   Priority: medium
   Labels: automated, ux, genai-finding
   Body:
     Finding: No progress indicator during export
     Impact: User uncertain if app working
     Recommendation: Add spinner/progress bar

     Affected files:
     - src/exports/export.js

     GenAI score: 6/10 (should be 8+)

✅ Issue #45: "UX: Improve form validation timing"
   Type: enhancement
   Priority: low
   Labels: automated, ux, genai-finding
   Body:
     Finding: Validation happens after submit
     Impact: Poor user experience
     Recommendation: Add real-time validation

     Affected files:
     - src/forms/UserForm.js

     GenAI score: 7/10 (should be 8+)

✅ Issue #46: "Architecture: Reviewer agent using Sonnet (should use Haiku)"
   Type: technical-debt
   Priority: high
   Labels: automated, architecture, genai-finding
   Body:
     Finding: Cost optimization opportunity
     Impact: Higher API costs than necessary
     Recommendation: Switch to Haiku for reviewer

     Affected files:
     - plugins/autonomous-dev/agents/reviewer.md

     Cost impact: $0.15 per review (should be $0.03)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Issues created: 3
View: https://github.com/user/repo/issues
```

**When to use**:
- ✅ After GenAI validation (`/test-uat-genai`, `/test-architecture`)
- ✅ UX improvements needed
- ✅ Architecture drift detected
- ✅ Want automatic tracking

**Benefits**:
- Full context from AI analysis
- Impact and recommendations included
- Automatic prioritization

---

## Option 3: Create Manual Issue

**Create custom issue with your own details**:

Interactive prompts:

```
Creating manual GitHub issue...

Title: Memory leak in background sync
Priority [high/medium/low]: high
Type [bug/enhancement/technical-debt/documentation]: bug
Description:
Background sync process accumulates memory over time.
After 24 hours, memory usage reaches 2GB.
(Press Ctrl+D when done)

Additional labels (comma-separated): performance, memory
Assign to (username or leave blank): akaszubski

Creating issue...

✅ Issue #47: "Memory leak in background sync"
   Type: bug
   Priority: high
   Labels: performance, memory
   Assigned: @akaszubski
   URL: https://github.com/user/repo/issues/47
```

**When to use**:
- ✅ Manual bug reports
- ✅ Feature requests
- ✅ Custom issues not from tests/GenAI
- ✅ Need full control

**Benefits**:
- Complete control over content
- Custom labels and assignment
- Can add milestones, projects

---

## Option 4: Preview (Dry Run)

**Show what issues would be created without creating them**:

```
PREVIEW: Issues that would be created (dry run)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Issue #1 (would be created)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Title: Bug: Export times out after 30 seconds
Type: bug
Priority: high
Labels: automated, test-failure, performance

Body:
Test: test_export_speed
File: tests/test_exports.py:145
Error: Timeout after 30s

Stack trace:
...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Issue #2 (would be created)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Title: UX: Add progress indicator for exports
Type: enhancement
Priority: medium
Labels: automated, ux, genai-finding

Body:
Finding: No progress indicator during export
Impact: User uncertain if app working
Recommendation: Add spinner/progress bar

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total issues: 2 (not created - preview only)

To create these issues, run again and choose option 1 or 2.
```

**When to use**:
- ✅ Want to see what would be created first
- ✅ Review before creating
- ✅ Testing issue creation logic

**Benefits**:
- Safe (no actual creation)
- Review full content
- Verify formatting

---

## Option 5: Cancel

**Exit without creating issues**:
- Aborts immediately
- No issues created
- Detection results still shown

---

## Typical Workflows

### After Test Failures

```bash
# Run tests
/test

# Tests fail - create issues automatically
/issue
Choice [1-5]: 1

# Issues created from failures (< 5s)
```

### After GenAI Validation

```bash
# Run GenAI validation
/test-uat-genai

# Found UX issues - create tracking issues
/issue
Choice [1-5]: 2

# Issues created from findings (< 5s)
```

### Manual Bug Report

```bash
# Discovered bug manually
/issue
Choice [1-5]: 3

# Follow prompts to create custom issue
```

### Preview Before Creating

```bash
# Want to see what would be created
/issue
Choice [1-5]: 4

# Review issues, then run again to create
/issue
Choice [1-5]: 1
```

---

## Safety Features

✅ **Detection first**: Always shows available sources
✅ **Interactive choice**: Pick exactly what you need
✅ **Preview mode**: See what would be created (option 4)
✅ **Auto-labeling**: Automatic tags for tracking
✅ **Full context**: Stack traces, GenAI analysis included
✅ **Cancel anytime**: Press Ctrl+C or choose option 5

---

## Comparison to Old Commands

**Before** (3 commands, hard to remember):
```bash
/issue-auto              # From tests
/issue-from-genai        # From GenAI
/issue-preview           # Dry run
# Which one do I need? 🤔
```

**Now** (1 command, self-documenting):
```bash
/issue       # Shows menu, you choose
```

**Benefits**:
- ✅ One command to learn
- ✅ Options shown when needed
- ✅ Can preview before creating
- ✅ Manual creation available

---

## When to Use This Command

**Run /issue when**:
- ❌ Tests fail (option 1)
- ⚠️ GenAI finds issues (option 2)
- 🐛 Manual bug discovered (option 3)
- 👀 Want to preview first (option 4)

**Don't need it if**:
- All tests passing
- No GenAI findings
- Already created issues manually

---

## GitHub Configuration

**Required**:
- GitHub CLI (`gh`) installed
- Authenticated (`gh auth login`)
- Repository access

**Optional**:
Set in `.env`:
```bash
GITHUB_REPO=owner/repo
GITHUB_DEFAULT_LABELS=automated
```

---

## Troubleshooting

### "No test failures found"

- Run tests first (`/test`)
- Check that tests actually failed
- Option 1 requires failed tests

### "No GenAI findings found"

- Run GenAI validation first (`/test-uat-genai` or `/test-architecture`)
- Check validation found issues
- Option 2 requires GenAI findings

### "GitHub authentication failed"

```bash
# Authenticate with GitHub
gh auth login

# Verify authentication
gh auth status
```

### "Permission denied creating issue"

- Verify repository write access
- Check GitHub token permissions
- May need to enable issue creation

---

## Related Commands

- `/test` - Run tests that may create issues
- `/test-uat-genai` - GenAI UX validation
- `/test-architecture` - GenAI architecture validation

---

**Use this to create GitHub Issues from any source. Auto-create for speed, manual for control, preview for safety.**
