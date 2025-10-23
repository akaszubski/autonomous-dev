# Automatic Issue Tracking

**Zero-effort GitHub Issues creation - runs automatically as you work**

---

## The Vision

**Problem**: Manual issue tracking is tedious and gets forgotten

**Solution**: Automatic issue creation that runs in the background:
- After each test run
- Before each git push
- Continuously while you work

**Outcome**: Complete issue tracking with zero manual effort

---

## How It Works

### Automatic Triggers

**Three modes** (choose one or combine):

#### 1. On Push (Recommended) ⭐
```bash
# When you push to GitHub
git push

# Automatically:
# 1. Scans for test failures
# 2. Checks GenAI validation results
# 3. Analyzes performance opportunities
# 4. Creates GitHub Issues
# 5. Continues with push
```

**Best for**: Catching issues before they reach CI/CD

---

#### 2. After Prompt (Background)
```bash
# As you work with Claude Code
# ... make changes ...
# ... run tests ...

# Automatically in background:
# - Scans test results
# - Creates issues silently
# - No interruption to workflow
```

**Best for**: Real-time issue tracking without thinking about it

---

#### 3. After Commit (Optional)
```bash
# After each commit
git commit -m "Add feature"

# Automatically:
# - Quick scan
# - Create issues
# - Continue workflow
```

**Best for**: Per-commit tracking (can be noisy)

---

## Setup

### 1. Install Prerequisites

```bash
# Install GitHub CLI
brew install gh          # macOS
sudo apt install gh      # Linux
winget install GitHub.cli # Windows

# Authenticate
gh auth login

# Verify
gh auth status
```

---

### 2. Configure .env

Create or update `.env`:

```bash
# .env (gitignored)

# === Automatic Issue Tracking ===

# Enable automatic tracking
GITHUB_AUTO_TRACK_ISSUES=true

# === Trigger Points ===

# Run before git push (recommended)
GITHUB_TRACK_ON_PUSH=true

# Run after each Claude Code prompt (background)
GITHUB_TRACK_ON_PROMPT=false

# Run after each commit (optional, can be noisy)
GITHUB_TRACK_ON_COMMIT=false

# === Filtering ===

# Minimum priority to create issues
# Options: low, medium, high
GITHUB_TRACK_THRESHOLD=medium

# Dry run (preview only, don't create)
GITHUB_DRY_RUN=false

# === Background Execution ===

# Run in background (non-blocking)
GITHUB_TRACK_BACKGROUND=true
```

---

### 3. Run /setup (If Not Already Done)

```bash
# Copy hooks to project
/setup

# Hooks are copied to .git/hooks/:
# - pre-push → auto_track_issues
# - post-commit → auto_track_issues (optional)
# - UserPromptSubmit → auto_track_issues (optional)
```

---

### 4. Test It

```bash
# Test dry run
GITHUB_DRY_RUN=true python3 plugins/autonomous-dev/hooks/auto_track_issues.py

# Output:
[14:30:45] [INFO] Starting automatic issue tracking...
[14:30:46] [INFO] Found 2 test failures
[14:30:47] [DRY RUN] Would create issue: test_export_speed fails
[14:30:47] [DRY RUN] Would create issue: test_validation fails
```

---

## What Gets Tracked Automatically

### Layer 1: Test Failures (pytest)

**Detects**:
- Failed pytest tests
- Performance regressions
- Broken functionality

**Creates**:
- Bug issues with full stack traces
- Reproduction steps
- System context

**Labels**: `bug`, `automated`, `layer-1`

---

### Layer 2: GenAI Validation Findings

**Detects**:
- UX issues (score < 8/10)
- Architectural drift
- Design violations

**Creates**:
- Enhancement issues (UX)
- Architecture issues (drift)
- Recommendations and impact analysis

**Labels**: `enhancement`, `ux`, `genai-detected`, `layer-2` OR `architecture`, `genai-detected`, `layer-2`

---

### Layer 3: System Performance Opportunities

**Detects**:
- Model optimization opportunities
- Agent inefficiencies
- Cost reduction potential

**Creates**:
- Optimization issues with ROI
- Cost-benefit analysis
- Action items

**Labels**: `optimization`, `cost-reduction`, `layer-3`

---

## Workflows

### Workflow 1: Pre-Push (Recommended) ⭐

```bash
# Your normal workflow
git add .
git commit -m "Add export feature"

# Push triggers auto-tracking
git push

# Output:
🔍 Checking for issues to track...
[14:30:45] [INFO] Starting automatic issue tracking...
[14:30:46] [INFO] Found 2 test failures
[14:30:47] [INFO] ✅ Created issue: https://github.com/user/repo/issues/42
[14:30:48] [INFO] ✅ Created issue: https://github.com/user/repo/issues/43
✅ Issue tracking complete

# Push continues normally
```

**Benefits**:
- Catches issues before CI/CD
- Creates issues automatically
- Non-blocking (push continues)
- No extra commands needed

---

### Workflow 2: Background (Silent)

```bash
# Enable background tracking
# .env: GITHUB_TRACK_ON_PROMPT=true

# Work normally
# ... run /test all ...
# ... continue coding ...

# In background (you don't see this):
# - Scans test results
# - Creates GitHub Issues
# - No interruption

# Later, check what was created
gh issue list --label automated

# Output:
#42  test_export_speed fails     bug, automated     30 minutes ago
#43  No progress indicator        ux, genai-detected 30 minutes ago
```

**Benefits**:
- Zero interruption
- Real-time tracking
- Discover issues later
- Completely automatic

---

### Workflow 3: Manual Trigger

```bash
# Run manually anytime
python3 plugins/autonomous-dev/hooks/auto_track_issues.py

# Or via /issue-auto command
/issue-auto
```

---

## Configuration Options

### Priority Filtering

```bash
# Only create high-priority issues
GITHUB_TRACK_THRESHOLD=high

# Create all issues (including low priority)
GITHUB_TRACK_THRESHOLD=low

# Medium and high only (recommended)
GITHUB_TRACK_THRESHOLD=medium
```

**Priority Assignment**:
- **High**: Test failures in critical path, architectural violations
- **Medium**: UX issues (score 6-7/10), moderate optimizations
- **Low**: UX issues (score 7-8/10), small optimizations

---

### Dry Run Mode

```bash
# Preview what would be created
GITHUB_DRY_RUN=true

# Actually create issues
GITHUB_DRY_RUN=false
```

---

### Background vs Foreground

```bash
# Background (non-blocking, silent)
GITHUB_TRACK_BACKGROUND=true

# Foreground (blocking, shows output)
GITHUB_TRACK_BACKGROUND=false
```

---

## What You See

### Pre-Push Output

```bash
$ git push

🔍 Checking for issues to track...
[14:30:45] [INFO] Starting automatic issue tracking...
[14:30:46] [INFO] Found 2 test failures
[14:30:46] [INFO] Found 1 GenAI findings
[14:30:47] [INFO] ✅ Created issue: https://github.com/user/repo/issues/42
[14:30:48] [INFO] ✅ Created issue: https://github.com/user/repo/issues/43
[14:30:49] [INFO] ✅ Created issue: https://github.com/user/repo/issues/44
[14:30:49] [INFO] View: gh issue list --label automated
✅ Issue tracking complete

Enumerating objects: 5, done.
Counting objects: 100% (5/5), done.
...
```

---

### Background Mode Output

```bash
# You see nothing!

# Issues are created silently in background

# Check later
$ gh issue list --label automated

#42  test_export_speed fails        bug, automated       5 minutes ago
#43  No progress indicator           ux, genai-detected   5 minutes ago
#44  Switch reviewer to Haiku        optimization         5 minutes ago
```

---

## Duplicate Prevention

**Smart deduplication**:
- Checks for existing issues with similar titles
- Skips duplicates automatically
- Only creates new issues for new findings

```bash
# First run
✅ Created issue #42: "test_export_speed fails"

# Second run (same failure)
⏭️  Skipping duplicate issue: #42 - test_export_speed fails
```

---

## Integration with Testing

### Automatic Flow

```bash
# 1. You run tests
/test all uat-genai architecture

# 2. Tests complete (some fail, some warn)

# 3. On next push, issues auto-created
git push
# → Creates issues for failures/warnings

# 4. Review issues
gh issue list --label automated

# 5. Auto-implement fixes (future)
/auto-implement --from-issue 42
```

---

## Advanced Usage

### Custom Labels

Modify `hooks/auto_track_issues.py`:

```python
# Add custom labels
issues.append({
    "labels": ["bug", "automated", "layer-1", "critical", "production"],
    # ...
})
```

---

### Custom Priority Logic

```python
# Custom priority calculation
def calculate_priority(issue: Dict) -> str:
    if "test_export" in issue["test_name"]:
        return "high"  # Critical path
    if issue["type"] == "architecture":
        return "high"  # Architecture issues always high
    return "medium"
```

---

### Notifications

```bash
# Get notified when issues are created
# Configure GitHub notifications:
gh auth refresh --scopes notifications

# Or use webhook
# See: https://docs.github.com/webhooks
```

---

## Troubleshooting

### Hook Not Running

**Check 1: Is it enabled?**
```bash
# .env
GITHUB_AUTO_TRACK_ISSUES=true
GITHUB_TRACK_ON_PUSH=true
```

**Check 2: Is hook installed?**
```bash
ls -la .git/hooks/pre-push
# Should exist and be executable
```

**Check 3: Is gh authenticated?**
```bash
gh auth status
# Should show "Logged in"
```

---

### No Issues Created

**Reason 1: No failures found**
```bash
# Check pytest cache
ls -la .pytest_cache/v/cache/lastfailed
# Should contain failed tests
```

**Reason 2: Below threshold**
```bash
# Lower threshold
GITHUB_TRACK_THRESHOLD=low
```

**Reason 3: Duplicates skipped**
```bash
# Check existing issues
gh issue list --search "test_export_speed in:title"
```

---

### Issues Created But Not Visible

**Check labels**:
```bash
# View all automated issues
gh issue list --label automated

# View by layer
gh issue list --label layer-1  # pytest
gh issue list --label layer-2  # GenAI
gh issue list --label layer-3  # performance
```

---

## Disable Temporarily

### Quick Disable

```bash
# Disable in .env
GITHUB_AUTO_TRACK_ISSUES=false

# Or remove hook
rm .git/hooks/pre-push
```

---

### Selective Disable

```bash
# Disable only pre-push
GITHUB_TRACK_ON_PUSH=false

# Disable only background
GITHUB_TRACK_ON_PROMPT=false
```

---

## Examples

### Example 1: Work, Push, Auto-Track

```bash
# Day 1: Add feature
git add .
git commit -m "Add export feature"

# Tests run, some fail (you don't notice)

# Push to GitHub
git push

# Output:
🔍 Checking for issues to track...
✅ Created issue #42: "test_export_speed fails"
✅ Created issue #43: "No progress indicator"

# Continue working...
```

**Later**:
```bash
# Check what was auto-created
gh issue list --label automated

# Fix issues
/auto-implement --from-issue 42
```

---

### Example 2: Background Tracking (Silent)

```bash
# Enable background
# .env: GITHUB_TRACK_ON_PROMPT=true
# .env: GITHUB_TRACK_BACKGROUND=true

# Work normally
/test all
# ... continue coding ...

# (Issues created silently in background)

# End of day: Review
gh issue list --label automated --created today

#42  test_export_speed fails    bug         2 hours ago
#43  UX: No progress bar        ux          2 hours ago
#44  Optimize reviewer          optimization 1 hour ago

# Plan next day from real data
```

---

### Example 3: Pre-Release Check

```bash
# Before release, full validation
/test all uat-genai architecture system-performance

# Push to trigger issue creation
git push

# Review all findings
gh issue list --label automated

# Fix high-priority issues
gh issue list --label high-priority
/auto-implement --from-issue 42
/auto-implement --from-issue 43

# Re-validate
/test all uat-genai architecture

# Release when clean
✅ No high-priority issues
→ Safe to release
```

---

## Metrics

### View Auto-Created Issues

```bash
# This week
gh issue list --label automated --created ">=$(date -d '7 days ago' +%Y-%m-%d)"

# By type
gh issue list --label bug
gh issue list --label enhancement
gh issue list --label optimization

# By priority
gh issue list --label high-priority
```

---

### Count Issues

```bash
# Total automated issues
gh issue list --label automated --json number --jq '. | length'

# By layer
gh issue list --label layer-1 --json number --jq '. | length'  # pytest
gh issue list --label layer-2 --json number --jq '. | length'  # GenAI
gh issue list --label layer-3 --json number --jq '. | length'  # performance
```

---

## Best Practices

### 1. Start with Pre-Push Only

```bash
# .env (recommended starting point)
GITHUB_AUTO_TRACK_ISSUES=true
GITHUB_TRACK_ON_PUSH=true
GITHUB_TRACK_ON_PROMPT=false
GITHUB_TRACK_THRESHOLD=medium
```

**Why**: Predictable, visible, non-intrusive

---

### 2. Weekly Issue Review

```bash
# Monday: Review last week
gh issue list --label automated --created ">=2025-10-14"

# Prioritize
gh issue edit N --milestone "Sprint 12"

# Auto-implement easy wins
/auto-implement --from-issue N
```

---

### 3. Use Priority Filtering

```bash
# Only high-priority issues
GITHUB_TRACK_THRESHOLD=high

# Review medium/low manually
gh issue list --label medium-priority
```

---

### 4. Close the Loop

```bash
# Issues created → Auto-implement → Merge → Close
/auto-implement --from-issue 42
gh pr merge 43
# → Issue #42 auto-closes
```

---

## Summary

**Question**: Is there a way to do this automatically as we work?

**Answer**: ✅ **Yes! Multiple ways!**

**Three Automatic Triggers**:
1. **Pre-Push** (recommended) - Before git push
2. **Background** - After each Claude Code prompt
3. **Post-Commit** - After each commit

**Configuration**:
```bash
# .env
GITHUB_AUTO_TRACK_ISSUES=true       # Enable
GITHUB_TRACK_ON_PUSH=true           # Trigger on push
GITHUB_TRACK_THRESHOLD=medium       # Filter by priority
```

**Workflow**:
```bash
# Work normally
git push

# Auto-creates issues:
✅ #42: "test_export_speed fails"
✅ #43: "No progress indicator"
✅ #44: "Optimize reviewer"

# Review later
gh issue list --label automated
```

**Benefits**:
- ✅ Zero manual effort
- ✅ Never forget to track issues
- ✅ Real testing data drives backlog
- ✅ Continuous improvement automated

**The autonomous system tracks itself while you work!** 🚀
