# Github Workflow - Detailed Guide

## CURRENT SPRINT

**Sprint Name**: Sprint 6: Documentation Accuracy
**GitHub Milestone**: https://github.com/user/repo/milestone/6
**Duration**: 2025-10-24 → 2025-10-27
```

**orchestrator reads this**:
```bash
# When you run autonomous pipeline
"Implement feature X"

# orchestrator:
# 1. Reads PROJECT.md current sprint
# 2. Queries GitHub Milestone via gh CLI
# 3. Links work to sprint
# 4. Tracks progress
```

**Manual sprint queries**:
```bash
# List milestones
gh api repos/user/repo/milestones

# View specific milestone
gh api repos/user/repo/milestones/6

# List issues in milestone
gh issue list --milestone "Sprint 6"
```

---

## Issue Lifecycle Management

### Close Issues Automatically

**Via commit message**:
```bash
git commit -m "feat: add user auth

Implements JWT-based authentication with secure token handling.

Closes #42
Fixes #43
Resolves #44"

git push

# Result: Issues #42, #43, #44 auto-closed when PR merges
```

**Keywords that work**:
- `Closes #123`
- `Fixes #123`
- `Resolves #123`
- `Closes: #123`
- `Fixes: #123`

### Close Issues Manually

```bash
gh issue close 42
gh issue close 42 --comment "Fixed in PR #123"
```

### Reopen Issues

```bash
gh issue reopen 42
gh issue reopen 42 --comment "Regression found, reopening"
```

### Clean Up Stale Issues

```bash
# List old open issues
gh issue list --state open --json number,title,updatedAt

# Close stale issues
gh issue close 42 --comment "Closing as stale (no activity in 90 days)"
```

---

## Troubleshooting

### "GitHub CLI not found"

```bash
# Install gh CLI
brew install gh         # Mac
# OR
sudo apt install gh     # Linux
# OR
choco install gh        # Windows

# Verify
gh --version
```

### "Not authenticated"

```bash
# Authenticate
gh auth login

# Follow prompts:
# 1. Choose: GitHub.com
# 2. Choose: HTTPS
# 3. Choose: Login with web browser
# 4. Authorize in browser

# Verify
gh auth status
```

### "Permission denied creating issue"

**Check**:
```bash
# Verify repo access
gh repo view

# Check token scopes
gh auth status
```

**Fix**:
```bash
# Re-authenticate with full scopes
gh auth login --scopes repo,write:discussion,workflow
```

### "Issue creation failed"

**Check**:
```bash
# Test manually
gh issue create --title "Test" --body "Test issue"

# If works: Plugin hook issue
# If fails: GitHub CLI issue
```

**Common causes**:
- Rate limiting (wait 60 seconds)
- Network issues (check connection)
- Repository archived (can't create issues)

### "No test failures found"

**Cause**: `/issue` option 1 requires test failures

**Fix**:
```bash
# Run tests first
/test

# If all pass: No issues to create
# If failures: Now /issue will find them
```

---

## Best Practices

### ✅ DO

1. **Start from issues**
   - Every feature should have a GitHub issue
   - Reference issue in branch name: `feature/42-add-auth`
   - Reference issue in commit: `Closes #42`

2. **Use draft PRs by default**
   - `/pr-create` (draft mode)
   - Review yourself before marking ready
   - Safe guard against premature merges

3. **Enable auto-tracking for high priority**
   - `GITHUB_TRACK_THRESHOLD=high`
   - Auto-create for critical bugs
   - Manual /issue for enhancements

4. **Link to PROJECT.md goals**
   - In issue description: "Supports Goal #1: Solo developer productivity"
   - Maintains strategic alignment
   - Makes prioritization clear

5. **Use conventional commits**
   - `feat:`, `fix:`, `docs:`, `refactor:`
   - Clean commit history
   - Auto-generates better PR descriptions

### ❌ DON'T

1. **Skip GitHub issues**
   - All work should be traceable
   - Even quick fixes: Create issue first

2. **Create ready PRs blindly**
   - Avoid `/pr-create --ready` unless confident
   - Draft mode is safer default

3. **Auto-track everything**
   - Don't set `GITHUB_TRACK_THRESHOLD=low`
   - Creates noise, too many issues
   - Medium or high only

4. **Forget to clean up**
   - Close stale issues regularly
   - Archive completed milestones
   - Keep issue list clean

5. **Break the workflow**
   - Don't commit directly to main
   - Don't skip PRs "because solo developer"
   - Workflow builds good habits

---

## Integration with Other Commands

### With Testing

```bash
# Run tests
/test

# If failures: Auto-create issues
/issue
```

### With Commits

```bash
# Format + test + security
/commit

# Standard commit (full checks)
/commit --check

# Push to GitHub (future)
/commit --push
```

### With Alignment

```bash
# Check PROJECT.md alignment
/align-project

# Fix issues found
/align-project

# Create issue for remaining work
/issue
```

---

## Advanced: Custom Issue Templates

**Create** `.github/ISSUE_TEMPLATE/bug_report.md`:
```markdown
---
name: Bug Report
about: Report a bug
labels: bug
---

## Description
