# GitHub Issues Auto-Tracking Integration

**Automatically create and link GitHub Issues from testing results**

---

## The Vision

**Problem**: Testing finds bugs/improvements but requires manual GitHub Issue creation

**Solution**: Auto-create GitHub Issues from:
- Layer 1: Test failures (pytest)
- Layer 2: GenAI validation findings (UX issues, architectural drift)
- Layer 3: System performance opportunities (model optimization, agent improvements)

**Outcome**: Continuous improvement driven by automated issue tracking

---

## How It Works

### Manual Flow (Current)
```bash
# Run tests
/test all

# Find issue
"test_export_speed FAILED - took 12s (expected < 10s)"

# Manually create GitHub Issue
gh issue create --title "Export too slow" --body "..."

# Manual tracking, easy to forget
```

### Automated Flow (Proposed)
```bash
# Run tests with auto-tracking
/test all --track-issues

# Auto-creates GitHub Issue
✅ Created issue #42: "test_export_speed fails - performance regression"
   Link: https://github.com/user/repo/issues/42
   Labels: bug, performance, automated
   Assigned to: current user

# Links to test output
Issue body contains:
- Test failure details
- Stack trace
- System context
- Suggested fix (from GenAI)
```

---

## Integration Points

### 1. Layer 1: Pytest Failures → GitHub Issues

**When**: Test fails
**Auto-creates issue with**:
- Title: `test_name fails - brief description`
- Body: Stack trace, error message, reproduction steps
- Labels: `bug`, `automated`, test type (`unit`/`integration`/`uat`)
- Link: Test file + line number

**Example**:
```bash
/test unit --track-issues

# Test fails
tests/unit/test_export.py::test_export_speed FAILED

# Auto-creates issue
✅ Issue #42 created
Title: "test_export_speed fails - performance regression"
Body:
  Test: tests/unit/test_export.py::test_export_speed:45
  Error: AssertionError: Export took 12s (expected < 10s)

  Stack trace:
  [full stack trace]

  Reproduction:
  pytest tests/unit/test_export.py::test_export_speed -v

  Context:
  - Python: 3.11.5
  - pytest: 7.4.2
  - Coverage: 85%

Labels: bug, automated, unit, performance
```

---

### 2. Layer 2: GenAI Validation → GitHub Issues

**When**: GenAI finds UX issues or architectural drift
**Auto-creates issue with**:
- Title: GenAI finding summary
- Body: Detailed analysis, recommendations, priority
- Labels: `enhancement`, `ux`, `architecture`, `genai-detected`

**Example**:
```bash
/test uat-genai --track-issues

# GenAI finds issue
⚠️ UX Issue Detected: No progress indicator during export

# Auto-creates issue
✅ Issue #43 created
Title: "UX: No progress indicator during export"
Body:
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

  **Related Goal**: PROJECT.md Goal #2 - "Users complete tasks in < 5 steps"

Labels: enhancement, ux, genai-detected, medium-priority
```

---

### 3. Layer 3: System Performance → GitHub Issues

**When**: Meta-analysis finds optimization opportunities
**Auto-creates issue with**:
- Title: Optimization opportunity
- Body: Cost/benefit analysis, specific action, expected savings
- Labels: `optimization`, `cost-reduction`, `performance`

**Example**:
```bash
/test system-performance --track-issues

# Finds optimization
⚠️ Optimization Opportunity: reviewer agent using Sonnet (could use Haiku)

# Auto-creates issue
✅ Issue #44 created
Title: "Optimize reviewer agent - switch to Haiku"
Body:
  System Performance Analysis:

  **Current State**:
  - Agent: reviewer
  - Model: Sonnet ($3/1M tokens)
  - Avg tokens: 1,800/invocation
  - Avg cost: $0.054/invocation
  - Monthly cost: $1.08 (20 features)

  **Proposed Change**:
  - Switch to: Haiku ($0.25/1M tokens)
  - New cost: $0.0045/invocation
  - Monthly cost: $0.09
  - Savings: $0.99/month (92% reduction)

  **Risk**: Low (simple review task suitable for Haiku)

  **Action Required**:
  1. Update agents/reviewer.md (model: haiku)
  2. Test with 3 features
  3. Monitor quality (should remain 100%)
  4. Keep change if quality maintained

  **Expected ROI**: $12/year savings, 5min implementation

Labels: optimization, cost-reduction, low-hanging-fruit
```

---

## Commands

### `/issue` - Create GitHub Issue from Testing Results

**Basic usage**:
```bash
# Auto-detect issues from last test run
/issue auto

# Create issue from specific test failure
/issue from-test test_export_speed

# Create issue from GenAI finding
/issue from-genai "No progress indicator"

# Create issue with custom details
/issue create --title "Export too slow" --type bug --priority high
```

**Options**:
```bash
--track-issues    # Enable auto-issue creation during /test
--dry-run        # Show what issues would be created (don't create)
--labels         # Add custom labels
--assign         # Assign to user (default: current user)
--milestone      # Link to milestone
--project        # Add to GitHub Project board
```

---

### Enhanced `/test` Commands

**All test commands support `--track-issues`**:

```bash
# Layer 1: Auto-create issues for test failures
/test all --track-issues

# Layer 2: Auto-create issues for GenAI findings
/test uat-genai --track-issues
/test architecture --track-issues

# Layer 3: Auto-create issues for optimization opportunities
/test system-performance --track-issues

# Combined: Complete issue tracking
/test all uat-genai architecture system-performance --track-issues
```

---

## Issue Templates

### Bug Template (Layer 1)
```markdown
---
name: Test Failure (Automated)
about: Automatically created from pytest failure
labels: bug, automated
---

## Test Failure

**Test**: `{{ test_file }}::{{ test_name }}:{{ line_number }}`
**Status**: FAILED
**Date**: {{ date }}

## Error

```
{{ error_message }}
```

## Stack Trace

```
{{ stack_trace }}
```

## Reproduction

```bash
pytest {{ test_file }}::{{ test_name }} -v
```

## Context

- Python: {{ python_version }}
- pytest: {{ pytest_version }}
- Coverage: {{ coverage }}%
- Platform: {{ platform }}

## Suggested Fix

{{ genai_suggestion }}

---
*Auto-created by `/test --track-issues`*
```

---

### Enhancement Template (Layer 2 - GenAI)
```markdown
---
name: GenAI UX Finding (Automated)
about: Automatically created from GenAI validation
labels: enhancement, ux, genai-detected
---

## GenAI Validation Finding

**Issue**: {{ issue_summary }}
**Impact**: {{ impact_level }} - {{ impact_description }}
**Current UX Score**: {{ current_score }}/10
**Target UX Score**: {{ target_score }}/10

## Analysis

{{ detailed_analysis }}

## Recommendation

{{ recommendation }}

## Expected Improvement

{{ expected_improvement }}

## Related Goals

{{ related_project_goals }}

---
*Auto-created by `/test uat-genai --track-issues`*
```

---

### Optimization Template (Layer 3 - Performance)
```markdown
---
name: System Optimization (Automated)
about: Automatically created from system performance analysis
labels: optimization, cost-reduction
---

## Optimization Opportunity

**Component**: {{ component_name }}
**Type**: {{ optimization_type }}

## Current State

- {{ current_state_details }}

## Proposed Change

- {{ proposed_change_details }}

## Cost-Benefit Analysis

**Current Cost**: {{ current_cost }}
**Proposed Cost**: {{ proposed_cost }}
**Savings**: {{ savings }} ({{ savings_percent }}%)
**Implementation Time**: {{ implementation_time }}
**ROI**: {{ roi }}

## Risk Assessment

**Risk Level**: {{ risk_level }}
**Reasoning**: {{ risk_reasoning }}

## Action Items

{{ action_items }}

---
*Auto-created by `/test system-performance --track-issues`*
```

---

## Workflow Integration

### Development Workflow with Auto-Issues

```bash
# 1. Develop feature
# ... make changes ...

# 2. Run complete testing with issue tracking
/test all uat-genai architecture system-performance --track-issues

# Output:
Running pytest...
✅ 45 tests passed
❌ 2 tests failed
   → Created issue #42: "test_export_speed fails"
   → Created issue #43: "test_validation_error fails"

Running GenAI UX validation...
✅ 4 workflows validated
⚠️ 1 UX issue found
   → Created issue #44: "No progress indicator during export"

Running GenAI architectural validation...
✅ 13 principles aligned
⚠️ 1 drift detected
   → Created issue #45: "Context management drift in orchestrator"

Running system performance analysis...
✅ Performance within targets
⚠️ 1 optimization opportunity
   → Created issue #46: "Switch reviewer to Haiku (save 92%)"

# 3. Review created issues
gh issue list --label automated

# 4. Prioritize and assign
gh issue edit 42 --add-label high-priority
gh issue edit 44 --add-label sprint-next

# 5. Auto-implement fixes (future)
/auto-implement --from-issue 42
```

---

### Sprint Planning with Auto-Issues

```bash
# Generate issues for all findings
/test all uat-genai architecture system-performance --track-issues

# Filter by priority
gh issue list --label high-priority
gh issue list --label low-hanging-fruit

# Add to sprint milestone
gh issue edit 42 --milestone "Sprint 12"
gh issue edit 44 --milestone "Sprint 12"

# Add to GitHub Project
gh issue edit 42 --add-project "Q4 Roadmap"

# Auto-assign to /auto-implement
/auto-implement --from-issue 42 --from-issue 44
```

---

## GitHub CLI Setup

**Required**: GitHub CLI (`gh`) installed and authenticated

### Installation

```bash
# macOS
brew install gh

# Linux
sudo apt install gh

# Windows
winget install GitHub.cli
```

### Authentication

```bash
# Login to GitHub
gh auth login

# Test authentication
gh auth status

# Configure permissions
gh auth refresh --scopes repo,project
```

---

## Configuration

### .env Configuration

```bash
# .env (already in .gitignore)
GITHUB_AUTO_ISSUES=true           # Enable auto-issue creation
GITHUB_ISSUE_LABELS=automated     # Default labels
GITHUB_ISSUE_ASSIGN=true          # Auto-assign to current user
GITHUB_ISSUE_PROJECT=              # Optional: Default project board
GITHUB_ISSUE_DRY_RUN=false        # Set true to preview only
```

### PROJECT.md Integration

```markdown
# PROJECT.md

## GitHub Integration

**Auto-Issue Creation**: Enabled
**Issue Labels**:
- `bug` - Test failures (Layer 1)
- `enhancement` - GenAI UX findings (Layer 2)
- `optimization` - Performance opportunities (Layer 3)
- `automated` - All auto-created issues

**Priority Mapping**:
- High: Test failures, architectural violations
- Medium: UX issues, security findings
- Low: Optimizations, documentation

**Workflow**:
1. Run `/test --track-issues` before merge
2. Review auto-created issues
3. Prioritize for sprint
4. Auto-implement with `/auto-implement --from-issue N`
```

---

## Implementation Plan

### Phase 1: Basic Integration (Week 1)
```bash
# Create /issue command
commands/issue.md

# Supports:
- /issue auto (detect from last test run)
- /issue from-test test_name
- /issue create (manual)

# Uses gh CLI:
gh issue create --title "..." --body "..." --label automated
```

### Phase 2: Test Integration (Week 2)
```bash
# Add --track-issues flag to /test
commands/test.md

# Auto-creates issues for:
- ✅ Pytest failures (Layer 1)
- ⚠️ GenAI findings (Layer 2) - basic

# Example:
/test all --track-issues
```

### Phase 3: GenAI Integration (Week 3)
```bash
# Enhanced GenAI issue creation
- UX findings → detailed enhancement issues
- Architectural drift → specific fix issues
- Priority and impact assessment

# Example:
/test uat-genai --track-issues
```

### Phase 4: Performance Integration (Week 4)
```bash
# System performance issue creation
- Model optimization opportunities
- Agent performance issues
- Cost reduction recommendations

# Example:
/test system-performance --track-issues
```

### Phase 5: Auto-Implementation (Month 2)
```bash
# Close the loop: auto-implement from issues
/auto-implement --from-issue 42

# Workflow:
1. Issue created from testing
2. /auto-implement reads issue
3. Generates plan
4. Implements fix
5. Runs tests
6. Creates PR
7. Links PR to issue
8. Auto-closes issue when PR merges
```

---

## Examples

### Example 1: Test Failure → Auto-Issue → Auto-Fix

```bash
# Step 1: Test fails, issue created
/test unit --track-issues

FAILED tests/unit/test_export.py::test_export_speed
✅ Created issue #42: "test_export_speed fails - performance regression"

# Step 2: Auto-implement fix
/auto-implement --from-issue 42

# Workflow:
- Reads issue #42
- Analyzes test failure
- Generates optimization plan
- Implements caching
- Runs tests (now passing)
- Creates PR #43
- Links PR to issue #42

# Step 3: Merge PR, issue auto-closes
gh pr merge 43
✅ Closed issue #42 (fixed by PR #43)
```

---

### Example 2: GenAI Finding → Enhancement → Implementation

```bash
# Step 1: GenAI finds UX issue
/test uat-genai --track-issues

⚠️ UX Issue: No progress indicator during export
✅ Created issue #44: "UX: Add progress indicator to export"

# Step 2: Prioritize for sprint
gh issue edit 44 --milestone "Sprint 12" --add-label high-priority

# Step 3: Auto-implement
/auto-implement --from-issue 44

# Implements:
- Progress bar component
- Updates export workflow
- Adds cancel button
- Tests UX improvement

# Step 4: Validate improvement
/test uat-genai

✅ UX Score improved: 6/10 → 9/10
✅ Issue #44 validated as fixed
```

---

### Example 3: Performance Opportunity → Optimization

```bash
# Step 1: System analysis finds opportunity
/test system-performance --track-issues

⚠️ Optimization: reviewer using Sonnet (could use Haiku)
✅ Created issue #46: "Optimize reviewer - switch to Haiku (save 92%)"

# Step 2: Quick win - add to sprint
gh issue edit 46 --add-label low-hanging-fruit

# Step 3: Auto-implement
/auto-implement --from-issue 46

# Changes:
- Updates agents/reviewer.md (model: haiku)
- Runs 3 test features
- Validates quality maintained
- Creates PR with cost-benefit analysis

# Result:
✅ Quality maintained (100% success rate)
✅ Cost reduced: $0.054 → $0.0045/review (92% savings)
✅ Monthly savings: $0.99
```

---

## Metrics & Reporting

### Issue Creation Metrics

```bash
# View auto-created issues
gh issue list --label automated

# View by type
gh issue list --label bug          # Test failures
gh issue list --label enhancement  # GenAI UX findings
gh issue list --label optimization # Performance opportunities

# View by priority
gh issue list --label high-priority
gh issue list --label low-hanging-fruit

# View resolved
gh issue list --state closed --label automated --limit 10
```

### Monthly Report

```markdown
## GitHub Issues - October 2025

**Auto-Created Issues**: 42 total
- Test failures: 12 (29%)
- UX improvements: 18 (43%)
- Optimizations: 12 (28%)

**Resolution**:
- Auto-implemented: 35 (83%)
- Manual review: 5 (12%)
- Deferred: 2 (5%)

**Time to Resolution**:
- Avg: 2.3 days
- Auto-implemented: 1.2 days
- Manual: 5.1 days

**Value Delivered**:
- Bugs fixed: 12
- UX improvements: 18 (avg score +2.1/10)
- Cost savings: $15.40/month (optimizations)

**Efficiency**:
- Issue creation: 100% automated
- Implementation: 83% automated
- Time saved: ~30 hours (vs manual tracking)
```

---

## Best Practices

### 1. Run with --track-issues Before Merge
```bash
# Always before merging
/test all uat-genai architecture --track-issues

# Review issues, prioritize, then merge
```

### 2. Weekly Issue Review
```bash
# Monday: Review auto-created issues
gh issue list --label automated --created ">=$(date -d '7 days ago' +%Y-%m-%d)"

# Prioritize
gh issue edit N --milestone "Current Sprint"
```

### 3. Label Consistently
```bash
# Use standard labels
- automated (all auto-created)
- bug, enhancement, optimization (by type)
- high-priority, medium-priority, low-priority
- low-hanging-fruit (easy wins)
```

### 4. Close the Loop
```bash
# Auto-implement when possible
/auto-implement --from-issue N

# Link PRs to issues
gh pr create --body "Fixes #42"

# Verify issue closure
gh issue view 42 --comments
```

---

## Future Enhancements

### Sprint Auto-Planning
```bash
# Auto-generate sprint from issues
/sprint plan --from-issues --priority high

# Creates:
- Sprint milestone
- Prioritized backlog
- Estimated effort
- Auto-implementation queue
```

### Predictive Issue Creation
```bash
# GenAI predicts issues before they occur
/test predict-issues

# Analyzes:
- Code complexity trends
- Historical patterns
- Similar codebases
- Creates preventive issues
```

### Issue Analytics Dashboard
```bash
# Visualize issue trends
/issue analytics

# Shows:
- Issue creation rate
- Resolution time
- Auto-implementation success rate
- Cost savings from optimizations
- UX score improvements
```

---

## Summary

**Current State**: Manual issue creation, easy to forget

**Proposed State**: Automated issue tracking integrated with testing

**Three Layers, Three Issue Types**:
1. **Layer 1** (pytest) → Bug issues (test failures)
2. **Layer 2** (GenAI) → Enhancement issues (UX, architecture)
3. **Layer 3** (Performance) → Optimization issues (cost, speed)

**Workflow**:
```bash
/test --track-issues          # Auto-create issues
gh issue list                 # Review and prioritize
/auto-implement --from-issue  # Auto-fix
gh pr merge                   # Deploy and close issue
```

**Benefits**:
- ✅ Zero manual issue tracking
- ✅ Complete testing → issue → fix → deploy loop
- ✅ Measurable improvements (UX scores, cost savings)
- ✅ Sprint planning from real data
- ✅ Continuous improvement automated

**The autonomous system tracks and fixes itself!** 🚀
