# PR Automation Guide

**Last Updated**: 2025-10-23
**Version**: v2.1.0

Automated Pull Request creation, linking, and management workflow with `/pr-create` command.

---

## Quick Start

### The Modern Way: Using `/pr-create` Command

```bash
# After implementing feature
/commit

# Create a draft PR (recommended for autonomous workflow)
/pr-create

# Or: Create a ready PR with reviewer assignment
/pr-create --ready --reviewer alice

# PR automatically:
# ✅ Links to issues (if mentioned in commits)
# ✅ Creates as draft by default (requires human approval)
# ✅ Parses commit messages for issue linking
# ✅ Supports reviewer assignment
# ✅ Triggers reviewer agent via GitHub Actions
```

### The Traditional Way: Using `gh` CLI

```bash
# After implementing feature
/commit

# Push and auto-create PR
git push -u origin feature/branch-name
gh pr create --fill

# PR automatically:
# ✅ Links to issue (if mentioned in commits)
# ✅ Requests reviews
# ✅ Runs CI checks
# ✅ Triggers reviewer agent
```

---

## `/pr-create` Command Reference

The `/pr-create` slash command is the recommended way to create PRs in the autonomous-dev workflow.

### Usage

```bash
/pr-create [FLAGS]
```

### Flags

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--title` | string | auto-fill | Custom PR title (uses commit messages if not provided) |
| `--body` | string | auto-fill | Custom PR description (uses commit messages if not provided) |
| `--ready` | boolean | false | Create as ready PR (skip draft mode, requires approval) |
| `--reviewer` | string | none | Assign reviewer(s) (comma-separated for multiple) |
| `--base` | string | main | Target branch (usually main or develop) |

### Examples

#### Example 1: Simple Draft PR (Default)

```bash
/pr-create
```

**Result:**
- Creates draft PR from current branch to main
- Uses commit messages for title/body
- No reviewer assigned
- Ready for feedback before marking as ready

#### Example 2: Draft PR with Reviewer

```bash
/pr-create --reviewer alice
```

**Result:**
- Creates draft PR
- Assigns alice as reviewer
- Alice gets notified immediately
- Can request changes before approval

#### Example 3: Ready PR with Custom Title

```bash
/pr-create --ready --title "feat: Add user authentication" --reviewer alice,bob
```

**Result:**
- Creates ready PR (not draft)
- Requires explicit approval flag to skip draft mode
- Alice and Bob assigned as reviewers
- Custom title used instead of commit messages

#### Example 4: PR to Different Base Branch

```bash
/pr-create --base develop --reviewer @frontend-team
```

**Result:**
- Merges to develop branch (not main)
- Assigns frontend-team for review
- Uses commit messages for title/body

### How It Works Internally

1. **Validates Prerequisites**
   - Checks `gh` CLI is installed and authenticated
   - Verifies you're in a git repository

2. **Gets Current Branch**
   - Determines your feature branch name
   - Fails if you're on main/master (can't create PR from default branch)

3. **Checks for Commits**
   - Verifies commits exist between base and head branches
   - Fails if no commits found (nothing to create PR for)

4. **Parses Issues**
   - Searches commit messages for issue keywords: Closes, Fixes, Resolves
   - Example: `feat: Add auth (closes #42)` → links PR to issue #42
   - Supports: `Closes #N`, `Fixes #N`, `Resolves #N` (case-insensitive)

5. **Creates PR**
   - Runs: `gh pr create --draft --base main ...flags`
   - Default: Draft mode (requires explicit approval before merge)
   - Optional: Assigns reviewers if specified

6. **Returns Result**
   ```json
   {
     "success": true,
     "pr_number": 42,
     "pr_url": "https://github.com/owner/repo/pull/42",
     "draft": true,
     "linked_issues": [42, 123],
     "error": null
   }
   ```

---

## Auto-Create PR from Feature (Traditional Methods)

### Method 1: Using `gh` CLI (Alternative)

```bash
# Create PR with auto-filled details
gh pr create --fill

# Create PR with template
gh pr create

# Create draft PR
gh pr create --draft
```

### Method 2: Git Push + GitHub Web

```bash
# Push creates "Create PR" button on GitHub
git push -u origin feature/42-description
# Click "Compare & pull request" on GitHub
```

---

## Auto-Link Issues

### In Commits

```bash
# Commit messages automatically parsed
git commit -m "feat: Add auth (closes #42)"
git commit -m "fix: Login bug

Fixes #43"
```

### In PR Description

```markdown
## Summary
Implements user authentication.

Closes #42
Fixes #43
Related to #44
```

**Keywords** that auto-close issues:
- `Closes #N`, `Fixes #N`, `Resolves #N`
- Works in commits and PR descriptions

---

## Auto-Request Reviews

### Method 1: CODEOWNERS File

Create `.github/CODEOWNERS`:
```
# Auto-request reviews based on files changed
*.py @python-team
*.js @frontend-team
docs/* @docs-team
```

### Method 2: gh CLI

```bash
# Request specific reviewers
gh pr create --reviewer @user1,@user2

# Request team review
gh pr create --reviewer @org/team-name
```

### Method 3: GitHub Settings

Repository Settings → Branches → Branch protection rules:
- Require pull request reviews before merging
- Require review from Code Owners

---

## Auto-Update PRs

### When New Commits Pushed

```bash
# Make changes based on feedback
# ... edit files ...

/commit
git push

# PR updates automatically:
# ✅ New commits appear
# ✅ CI re-runs
# ✅ Review dismissed (if configured)
```

### Auto-Rebase on Main Updates

Enable in GitHub Settings → General → "Automatically update pull request branches"

Or manually:
```bash
gh pr checkout 123
git fetch origin
git rebase origin/main
git push --force-with-lease
```

---

## Reviewer Agent Integration

The reviewer agent automatically:

1. **Runs on PR creation**
2. **Checks**:
   - Code quality standards
   - Test coverage (80%+ minimum)
   - Security patterns
   - Documentation sync
3. **Posts review comments**
4. **Suggests improvements**

View agent review:
```bash
gh pr view 123 --comments
```

---

## CI/CD Integration

### Auto-Run Checks

Create `.github/workflows/pr-checks.yml`:

```yaml
name: PR Checks

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Format check
        run: black --check .
      - name: Run tests
        run: pytest --cov --cov-fail-under=80
      - name: Security scan
        run: bandit -r .
```

---

## Auto-Merge When Ready

### Enable Auto-Merge

```bash
# Auto-merge when all checks pass
gh pr merge 123 --auto --squash
```

### Requirements for Auto-Merge

Configure in GitHub Settings → Branches:
- ✅ All CI checks must pass
- ✅ Required reviews approved
- ✅ No merge conflicts
- ✅ Branch up to date with main

---

## PR Templates

### Create Template

`.github/PULL_REQUEST_TEMPLATE.md`:
```markdown
## Summary
<!-- Brief description of changes -->

## Changes
- [ ] Feature implementation
- [ ] Tests added/updated
- [ ] Documentation updated

## Test Plan
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing complete

## Closes
<!-- Link issues: Closes #N -->

🤖 Generated with Claude Code
```

Auto-fills when creating PR via web UI or `gh pr create`.

---

## Advanced Automation

### Auto-Label PRs

`.github/workflows/auto-label.yml`:
```yaml
name: Auto Label

on: [pull_request]

jobs:
  label:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/labeler@v4
        with:
          repo-token: "${{ secrets.GITHUB_TOKEN }}"
```

`.github/labeler.yml`:
```yaml
'type:docs':
  - docs/**/*
'type:tests':
  - tests/**/*
'type:frontend':
  - '**/*.js'
  - '**/*.ts'
```

### Auto-Assign Reviewers

`.github/auto_assign.yml`:
```yaml
addReviewers: true
addAssignees: false

reviewers:
  - reviewer1
  - reviewer2

numberOfReviewers: 2
```

---

## Troubleshooting

### `/pr-create` Command Issues

#### "GitHub CLI not installed"

Error: `GitHub CLI not installed. Install from https://cli.github.com/`

**Solution:**
```bash
# Install GitHub CLI
brew install gh              # macOS
choco install gh             # Windows
apt install gh               # Ubuntu/Debian

# Verify installation
gh --version
```

#### "GitHub CLI not authenticated"

Error: `GitHub CLI not authenticated. Run: gh auth login`

**Solution:**
```bash
# Authenticate with GitHub
gh auth login

# Select options:
# - GitHub.com or GitHub Enterprise? → GitHub.com
# - Preferred protocol? → HTTPS (or SSH)
# - Authenticate Git with your GitHub credentials? → Yes
# - How would you like to authenticate? → Paste an authentication token

# Verify authentication
gh auth status
```

**Get a Personal Access Token:**
1. Visit: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: `repo` (full repository control)
4. Copy token and paste when prompted by `gh auth login`

#### "Cannot create PR from main branch"

Error: `Cannot create PR from main branch. Switch to a feature branch first.`

**Solution:**
```bash
# Create and switch to feature branch
git checkout -b feature/your-feature-name

# Or: Switch to existing feature branch
git checkout feature/your-feature-name

# Then retry
/pr-create
```

#### "No commits found between base and head"

Error: `No commits found between main and feature/branch. Nothing to create PR for.`

**Solution:**
```bash
# Check if you have commits
git log main..HEAD --oneline

# If no commits:
# 1. Make sure you're on the right branch
git branch

# 2. Make changes and commit
/commit

# 3. Try again
/pr-create
```

#### "GitHub API rate limit exceeded"

Error: `GitHub API rate limit exceeded. Try again later.`

**Solution:**
```bash
# Check current rate limit
gh api rate_limit

# Wait a few minutes and retry
# or use authenticated token with higher limits
gh auth logout
gh auth login  # Re-authenticate
```

#### "Permission denied - insufficient GITHUB_TOKEN scope"

Error: `Permission denied. Check repository permissions and SAML authorization`

**Solution:**
```bash
# Check current token scopes
gh auth status

# Refresh token with repo scope
gh auth refresh -s repo

# If that doesn't work, create new token with full 'repo' scope:
# https://github.com/settings/tokens
```

### Traditional `gh` CLI Issues

#### "No permission to create PR"

Ensure GitHub token has `repo` scope:
```bash
gh auth status
# If needed:
gh auth refresh -s repo
```

#### "PR not linking to issue"

Use correct keywords in commit/PR description:
- `Closes #N` (not `close` or `closing`)
- Must be in commit message or PR description
- Issue number must be correct

#### "Auto-merge not working"

Check:
1. All required checks passing
2. Required reviews approved
3. No merge conflicts
4. Branch protection rules met

```bash
gh pr checks 123
gh pr view 123
```

---

## Best Practices

1. **Always link issues** - Use "Closes #N"
2. **Request reviews early** - Use draft PRs for feedback
3. **Keep PRs small** - Max 400 lines changed
4. **Use templates** - Consistent PR format
5. **Auto-merge carefully** - Only for well-tested features

---

**See also**:
- GitHub Workflow: `docs/GITHUB-WORKFLOW.md`
- Code Review: `docs/CODE-REVIEW-WORKFLOW.md`
- GitHub Auth: `docs/GITHUB_AUTH_SETUP.md`
