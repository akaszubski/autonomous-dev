# /issue - GitHub Issue Auto-Creation

**Automatically create GitHub Issues from testing results**

---

## Purpose

Create GitHub Issues from:
- Test failures (pytest)
- GenAI validation findings (UX, architecture)

**Goal**: Zero manual issue tracking - let testing drive continuous improvement

---

## Usage

```bash
# Auto-detect issues from last test run
/issue auto

# Create issue from specific test failure
/issue from-test test_export_speed

# Create issue from GenAI finding
/issue from-genai "No progress indicator"

# Manual issue creation
/issue create --title "Export too slow" --type bug --priority high

# Dry run (preview without creating)
/issue auto --dry-run
```

---

## Commands

### `/issue auto`

**Auto-detect and create issues from last test run**

```bash
/issue auto

# Analyzes:
# - pytest output (failures)
# - GenAI validation results

# Creates issues for:
# ✅ Test failures
# ✅ UX problems (< 8/10 score)
# ✅ Architectural drift
```

**Options**:
```bash
/issue auto --dry-run              # Preview only
/issue auto --priority high        # Override priority
/issue auto --milestone "Sprint 12" # Add to milestone
/issue auto --assign @username     # Assign to user
```

---

### `/issue from-test <test_name>`

**Create issue from specific test failure**

```bash
/issue from-test test_export_speed

# Creates issue with:
# - Title: "test_export_speed fails - performance regression"
# - Body: Stack trace, error, reproduction steps
# - Labels: bug, automated, unit, performance
# - Link: Test file + line number
```

**Example Output**:
```markdown
✅ Created issue #42

**Title**: test_export_speed fails - performance regression

**Labels**: bug, automated, unit, performance

**Link**: https://github.com/user/repo/issues/42

**Body**:
Test: tests/unit/test_export.py::test_export_speed:45
Error: AssertionError: Export took 12s (expected < 10s)

[Stack trace...]

Reproduction:
pytest tests/unit/test_export.py::test_export_speed -v
```

---

### `/issue from-genai "<finding>"`

**Create issue from GenAI validation finding**

```bash
/issue from-genai "No progress indicator during export"

# Creates issue with:
# - Title: "UX: No progress indicator during export"
# - Body: Impact analysis, recommendations, expected improvement
# - Labels: enhancement, ux, genai-detected
# - Priority: Based on UX impact
```

**Example Output**:
```markdown
✅ Created issue #43

**Title**: UX: No progress indicator during export

**Labels**: enhancement, ux, genai-detected, medium-priority

**Body**:
GenAI Validation Finding:

**Issue**: Users don't know how long export will take
**Impact**: Medium - causes user anxiety on large exports
**UX Score**: 6/10 (target: 8/10)

**Recommendation**:
Add progress indicator showing:
- Current step (e.g., "Processing 150/500 records")
- Estimated time remaining
- Cancel option

**Expected Improvement**: UX score → 9/10
```

---

### `/issue create`

**Manual issue creation with custom details**

```bash
/issue create \
  --title "Export performance regression" \
  --body "Export now takes 12s instead of 8s" \
  --type bug \
  --priority high \
  --labels performance,regression \
  --assign @akaszubski \
  --milestone "Sprint 12"

# Creates standard GitHub issue
```

---

## Integration with /test

**All `/test` commands support `--track-issues`**:

```bash
# Auto-create issues during testing
/test all --track-issues
/test uat-genai --track-issues
/test architecture --track-issues
/test system-performance --track-issues

# Combined
/test all uat-genai architecture system-performance --track-issues
```

**Example**:
```bash
/test all --track-issues

# Output:
Running pytest...
✅ 45 tests passed
❌ 2 tests failed
   ✅ Created issue #42: "test_export_speed fails"
   ✅ Created issue #43: "test_validation_error fails"

Running GenAI UX validation...
⚠️ 1 UX issue found
   ✅ Created issue #44: "No progress indicator during export"

Running GenAI architectural validation...
⚠️ 1 drift detected
   ✅ Created issue #45: "Context management drift in orchestrator"

Running system performance analysis...
⚠️ 1 optimization opportunity
   ✅ Created issue #46: "Switch reviewer to Haiku (save 92%)"

---
Summary:
- Created 5 issues
- Bugs: 2
- Enhancements: 2
- Optimizations: 1

View: gh issue list --label automated
```

---

## Issue Templates

### Bug (Test Failure)

```markdown
## Test Failure

**Test**: `tests/unit/test_export.py::test_export_speed:45`
**Status**: FAILED
**Date**: 2025-10-20

## Error

AssertionError: Export took 12s (expected < 10s)

## Stack Trace

[full stack trace]

## Reproduction

```bash
pytest tests/unit/test_export.py::test_export_speed -v
```

## Context

- Python: 3.11.5
- pytest: 7.4.2
- Coverage: 85%
- Platform: darwin

## Suggested Fix

Implement caching to reduce database queries during export.

---
*Auto-created by `/test --track-issues`*
```

---

### Enhancement (GenAI Finding)

```markdown
## GenAI Validation Finding

**Issue**: No progress indicator during export
**Impact**: Medium - causes user anxiety
**Current UX Score**: 6/10
**Target UX Score**: 8/10

## Analysis

Users don't know how long export will take. On large datasets (500+ records),
export can take 10+ seconds with no feedback.

## Recommendation

Add progress indicator:
- Current step: "Processing 150/500 records"
- Estimated time remaining
- Cancel option

## Expected Improvement

UX score → 9/10

## Related Goals

PROJECT.md Goal #2: "Users complete tasks in < 5 steps"

---
*Auto-created by `/test uat-genai --track-issues`*
```

---

### Optimization (Performance Finding)

```markdown
## Optimization Opportunity

**Component**: reviewer agent
**Type**: Model optimization

## Current State

- Model: Sonnet ($3/1M tokens)
- Avg tokens: 1,800/invocation
- Avg cost: $0.054/invocation
- Monthly cost: $1.08 (20 features)

## Proposed Change

- Switch to: Haiku ($0.25/1M tokens)
- New cost: $0.0045/invocation
- Monthly cost: $0.09
- Savings: $0.99/month (92% reduction)

## Cost-Benefit Analysis

**Implementation Time**: 5 minutes
**Monthly Savings**: $0.99
**Annual Savings**: $11.88
**Risk**: Low

## Risk Assessment

**Risk Level**: Low
**Reasoning**: Review is simple task suitable for Haiku. Quality unlikely to degrade.

## Action Items

1. Update `agents/reviewer.md` (change model to haiku)
2. Test with 3 features
3. Monitor quality (should remain 100%)
4. Keep change if quality maintained

---
*Auto-created by `/test system-performance --track-issues`*
```

---

## Configuration

### .env Setup

```bash
# .env (gitignored)
GITHUB_AUTO_ISSUES=true           # Enable auto-issue creation
GITHUB_ISSUE_LABELS=automated     # Default labels (comma-separated)
GITHUB_ISSUE_ASSIGN=true          # Auto-assign to current user
GITHUB_ISSUE_PROJECT=              # Optional: Default project board
GITHUB_ISSUE_DRY_RUN=false        # Preview only (don't create)
```

### Priority Mapping

**Auto-assigned based on severity**:

| Finding Type | Default Priority |
|--------------|-----------------|
| Test failure (critical path) | High |
| Test failure (other) | Medium |
| Architectural violation | High |
| UX issue (score < 6/10) | High |
| UX issue (score 6-7/10) | Medium |
| UX issue (score 7-8/10) | Low |
| Optimization (> 50% savings) | Medium |
| Optimization (10-50% savings) | Low |
| Optimization (< 10% savings) | Low |

---

## Label Conventions

**Type Labels**:
- `bug` - Test failures, broken functionality
- `enhancement` - UX improvements, features
- `optimization` - Performance, cost reduction

**Source Labels**:
- `automated` - All auto-created issues
- `genai-detected` - From GenAI validation
- `layer-1` - From pytest
- `layer-2` - From GenAI validation
- `layer-3` - From system performance

**Category Labels**:
- `unit`, `integration`, `uat` - Test type
- `ux`, `architecture` - GenAI finding type
- `performance`, `cost-reduction` - Optimization type

**Priority Labels**:
- `high-priority` - Fix immediately
- `medium-priority` - Fix this sprint
- `low-priority` - Backlog
- `low-hanging-fruit` - Easy wins

---

## Workflow Examples

### Example 1: Daily Development

```bash
# Morning: Pull latest
git pull

# Develop feature
# ... make changes ...

# Before commit: Run tests with issue tracking
/test all --track-issues

# Fix critical issues
gh issue list --label high-priority
# Fix issues #42, #43

# Re-test
/test all

# Commit when passing
/commit
```

---

### Example 2: Weekly Sprint Planning

```bash
# Monday: Review auto-created issues from last week
gh issue list --label automated --created ">=2025-10-14"

# Prioritize
gh issue edit 44 --milestone "Sprint 12" --add-label high-priority
gh issue edit 45 --milestone "Sprint 12"
gh issue edit 46 --add-label low-hanging-fruit

# Add to sprint
gh issue list --milestone "Sprint 12"

# Auto-implement easy wins
/auto-implement --from-issue 46
```

---

### Example 3: Pre-Release Validation

```bash
# Complete validation before release
/test all uat-genai architecture system-performance --track-issues

# Review all findings
gh issue list --label automated

# Fix critical issues
gh issue list --label high-priority
# Address all high-priority

# Re-validate
/test all uat-genai architecture

# Release when clean
✅ All tests passing
✅ No high-priority issues
✅ UX score: 8.5/10
✅ Architecture: 100% aligned
→ Ready for release
```

---

## Advanced Usage

### Batch Issue Creation

```bash
# Create issues for all findings in one command
/issue batch \
  --from-test-failures \
  --from-genai-findings

# Equivalent to:
/issue auto
```

---

### Issue Linking

```bash
# Link related issues
/issue create --title "Optimize export" --links #42,#43

# Link to PR
gh pr create --body "Fixes #42, #43, #44"

# Auto-close when PR merges
gh pr merge 45
# → Issues #42, #43, #44 automatically closed
```

---

### Custom Templates

```bash
# Use custom issue template
/issue create \
  --template .github/ISSUE_TEMPLATE/performance.md \
  --fill-template test_name=test_export_speed,error="12s > 10s"
```

---

## Metrics

### View Created Issues

```bash
# All automated issues
gh issue list --label automated

# By type
gh issue list --label bug
gh issue list --label enhancement
gh issue list --label optimization

# By priority
gh issue list --label high-priority
gh issue list --label low-hanging-fruit

# This week
gh issue list --label automated --created ">=2025-10-14"
```

---

### Issue Analytics

```bash
# Count by type
gh issue list --label automated --json labels | \
  jq '[.[] | .labels[].name] | group_by(.) | map({type: .[0], count: length})'

# Resolution time
gh issue list --state closed --label automated --limit 10 --json closedAt,createdAt | \
  jq '.[] | (.closedAt | fromdateiso8601) - (.createdAt | fromdateiso8601) | . / 86400 | "Days: \(.)"'
```

---

## Prerequisites

### GitHub CLI Required

```bash
# Install
brew install gh          # macOS
sudo apt install gh      # Linux
winget install GitHub.cli # Windows

# Authenticate
gh auth login

# Test
gh auth status

# Required scopes
gh auth refresh --scopes repo,project
```

---

## Troubleshooting

### Issue Not Created

**Check**:
```bash
# Verify authentication
gh auth status

# Check repo permissions
gh repo view

# Dry run to see what would be created
/issue auto --dry-run
```

---

### Wrong Labels

**Fix**:
```bash
# Update default labels in .env
GITHUB_ISSUE_LABELS=automated,bot-created

# Or specify per issue
/issue create --labels custom,labels,here
```

---

### Duplicate Issues

**Prevention**:
```bash
# Check for existing issues before creating
gh issue list --search "test_export_speed in:title"

# Skip duplicates (auto-enabled)
/issue auto --skip-duplicates
```

---

## Future Enhancements

### Auto-Implementation from Issues

```bash
# Coming soon
/auto-implement --from-issue 42

# Workflow:
1. Reads issue #42
2. Analyzes problem
3. Generates plan
4. Implements fix
5. Runs tests
6. Creates PR
7. Links PR to issue
```

---

### Issue Analytics Dashboard

```bash
# Coming soon
/issue analytics

# Shows:
- Issue creation rate
- Resolution time
- Auto-implementation success rate
- Cost savings from optimizations
```

---

## See Also

- `docs/GITHUB-ISSUES-INTEGRATION.md` - Complete integration guide
- `docs/SYSTEM-PERFORMANCE-GUIDE.md` - Layer 3 testing
- `docs/GENAI-TESTING-GUIDE.md` - Layer 2 testing
- `/auto-implement` - Auto-fix issues (future)

---

## Summary

**Purpose**: Zero manual issue tracking - let testing drive continuous improvement

**Three Layers → Three Issue Types**:
1. Layer 1 (pytest) → Bug issues
2. Layer 2 (GenAI) → Enhancement issues
3. Layer 3 (Performance) → Optimization issues

**Commands**:
```bash
/issue auto                           # Auto-create from tests
/test all --track-issues              # Enable during testing
gh issue list --label automated       # View created issues
/auto-implement --from-issue N        # Auto-fix (future)
```

**Workflow**:
```
Test → Find Issues → Create GitHub Issues → Prioritize → Auto-Implement → Merge → Close
```

**The autonomous system tracks and fixes itself!** 🚀
