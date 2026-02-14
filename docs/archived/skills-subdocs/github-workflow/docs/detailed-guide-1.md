# Github Workflow - Detailed Guide

## Detailed Documentation

For comprehensive PR and issue description guidance:
- **PR Templates**: See [docs/pr-template-guide.md](docs/pr-template-guide.md) for effective pull request descriptions
- **Issue Templates**: See [docs/issue-template-guide.md](docs/issue-template-guide.md) for clear issue descriptions
- **PR Examples**: See [examples/pr-template.md](examples/pr-template.md) for complete example PR
- **Issue Examples**: See [examples/issue-template.md](examples/issue-template.md) for complete example issue

For automation patterns and security:
- **PR Automation**: See [docs/pr-automation.md](docs/pr-automation.md) for auto-labeling, auto-reviewers, and auto-merge workflows
- **Issue Automation**: See [docs/issue-automation.md](docs/issue-automation.md) for auto-triage, auto-assignment, and stale issue detection
- **GitHub Actions**: See [docs/github-actions-integration.md](docs/github-actions-integration.md) for CI/CD workflow patterns and custom actions
- **API Security**: See [docs/api-security-patterns.md](docs/api-security-patterns.md) for webhook signature verification and token security

---

## Quick Reference

### Commands Available
```bash
/issue           # Create GitHub issues (test failures, GenAI, manual)
/pr-create       # Create pull request with auto-filled content
```

### Hooks Available
- `auto_track_issues.py` - Auto-create issues on push/commit (configurable)

### Configuration
```bash
# .env file
GITHUB_AUTO_TRACK_ISSUES=true      # Enable auto-tracking
GITHUB_TRACK_ON_PUSH=true          # Track before push
GITHUB_TRACK_THRESHOLD=medium      # Minimum priority (low/medium/high)
GITHUB_DRY_RUN=false               # Preview mode (true = no actual creation)
```

---

## Complete Workflow

### End-to-End: Issue → Feature → PR → Merge

```bash
# 1. Start from GitHub issue
gh issue list
gh issue view 42
gh issue edit 42 --add-assignee @me

# 2. Create feature branch
git checkout -b feature/42-add-user-auth

# 3. Implement feature
"Implement user authentication per issue #42"
# orchestrator runs autonomous pipeline

# 4. Quality check
/full-check

# 5. Commit with issue reference
/commit
# Add to commit message: "Closes #42"

# 6. Create pull request
/pr-create
# Auto-links to issue #42
# Creates draft PR by default

# 7. Review and merge
gh pr view
gh pr ready      # Mark draft as ready
gh pr merge --auto --squash
```

---

## Issue Creation Patterns

### Pattern 1: After Test Failures

```bash
# Run tests
/test

# Tests fail - auto-create issues
/issue
# Menu appears:
# 1. Auto-create from test failures (2 issues) ← Choose this
# 2. Create from GenAI findings
# 3. Create manual issue
# 4. Preview (dry run)
# 5. Cancel

Choice [1-5]: 1

# Result: GitHub issues created automatically
# - Full stack traces included
# - Labeled: automated, test-failure, bug
# - Priority: high
```

**When to use**:
- CI/CD pipeline failures
- Local test failures
- Want automatic bug tracking

### Pattern 2: From GenAI Findings

```bash
# Run GenAI validation
/test-uat-genai        # UX validation
# OR
/test-architecture     # Architecture validation

# Found issues - create tracking issues
/issue
Choice [1-5]: 2

# Result: GitHub issues created from AI analysis
# - UX friction points
# - Architecture drift
# - Performance opportunities
# - Labeled: automated, genai-finding, enhancement
```

**When to use**:
- After GenAI validation
- UX improvements needed
- Architecture cleanup
- Code quality tracking

### Pattern 3: Manual Issue Creation

```bash
/issue
Choice [1-5]: 3

# Interactive prompts:
Title: Memory leak in background sync
Priority [high/medium/low]: high
Type [bug/enhancement/technical-debt/documentation]: bug
Description:
Background sync accumulates memory over time.
After 24 hours, reaches 2GB.
(Press Ctrl+D when done)

Additional labels: performance, memory
Assign to: akaszubski

# Result: Custom GitHub issue created
```

**When to use**:
- Manual bug reports
- Feature requests
- Documentation tasks
- Custom tracking needs

---

## Automatic Issue Tracking

### Enable Auto-Tracking

**Setup** (one-time):
```bash
# Add to .env
cat >> .env << 'EOF'
GITHUB_AUTO_TRACK_ISSUES=true
GITHUB_TRACK_ON_PUSH=true
GITHUB_TRACK_THRESHOLD=medium
GITHUB_DRY_RUN=false
EOF

# Install GitHub CLI
brew install gh

# Authenticate
gh auth login
```

**How it works**:
```bash
# You work normally
/test                  # Tests fail
/commit                # Commit changes
git push               # Push to GitHub

# Hook runs automatically:
# - Detects test failures
# - Creates GitHub issues
# - Labels and prioritizes
# - Links to commits

# No manual /issue needed!
```

**Configuration Options**:

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `GITHUB_AUTO_TRACK_ISSUES` | true/false | false | Enable auto-tracking |
| `GITHUB_TRACK_ON_PUSH` | true/false | true | Track before push |
| `GITHUB_TRACK_ON_COMMIT` | true/false | false | Track after commit |
| `GITHUB_TRACK_THRESHOLD` | low/medium/high | medium | Minimum priority to track |
| `GITHUB_DRY_RUN` | true/false | false | Preview only (no creation) |

**Example workflows**:

**Conservative** (manual review):
```bash
GITHUB_AUTO_TRACK_ISSUES=true
GITHUB_TRACK_ON_PUSH=false
GITHUB_DRY_RUN=true

# Result: Shows what would be created, but doesn't create
# You review, then manually run /issue
```

**Aggressive** (full automation):
```bash
GITHUB_AUTO_TRACK_ISSUES=true
GITHUB_TRACK_ON_PUSH=true
GITHUB_DRY_RUN=false

# Result: Issues created automatically on every push
# Fast, automated, but less control
```

**Balanced** (recommended):
```bash
GITHUB_AUTO_TRACK_ISSUES=true
GITHUB_TRACK_ON_PUSH=true
GITHUB_TRACK_THRESHOLD=high
GITHUB_DRY_RUN=false

# Result: Only high-priority issues auto-created
# Manual /issue for medium/low priority
```

---

## Pull Request Patterns

### Pattern 1: Simple Draft PR

```bash
/pr-create

# What happens:
# ✅ Creates draft PR
# ✅ Auto-fills title from commit messages
# ✅ Auto-fills body from commit messages
# ✅ Parses "Closes #42" and links issues
# ✅ Draft mode: Requires manual "Ready for review"

# Result:
# Draft PR created
# URL: https://github.com/user/repo/pull/123
```

**When to use**:
- Default workflow (safe)
- Want manual review before marking ready
- Still working on PR
- Need reviewer feedback before finalizing

### Pattern 2: PR with Reviewer Assignment

```bash
/pr-create --reviewer alice

# Same as Pattern 1, plus:
# ✅ Assigns alice as reviewer
# ✅ Sends notification to alice

# For multiple reviewers:
/pr-create --reviewer alice,bob
```

**When to use**:
- Know who should review
- Team workflow (solo developer: skip this)
- Want immediate review request

### Pattern 3: Ready for Review (Not Draft)

```bash
/pr-create --ready

# What's different:
# ✅ Creates PR as "Ready for review" (not draft)
# ✅ Triggers CI/CD immediately
# ✅ Can be merged immediately if checks pass

# Use with caution - skips draft safety
```

**When to use**:
- Confident PR is ready
- Fast-track workflow
- Small changes
- Solo developer (no team review needed)

---

## Sprint/Milestone Integration
