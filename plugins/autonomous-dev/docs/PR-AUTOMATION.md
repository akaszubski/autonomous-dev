# PR Automation Guide

**Last Updated**: 2025-10-20
**Version**: v2.0.0

Automated Pull Request creation, linking, and management workflow.

---

## Quick Start

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

## Auto-Create PR from Feature

### Method 1: Using `gh` CLI (Recommended)

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

### "No permission to create PR"

Ensure GitHub token has `repo` scope:
```bash
gh auth status
# If needed:
gh auth refresh -s repo
```

### "PR not linking to issue"

Use correct keywords in commit/PR description:
- `Closes #N` (not `close` or `closing`)
- Must be in commit message or PR description
- Issue number must be correct

### "Auto-merge not working"

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
