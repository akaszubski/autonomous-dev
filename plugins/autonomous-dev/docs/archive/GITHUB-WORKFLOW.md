# GitHub-First Workflow Guide

**Last Updated**: 2025-10-25
**Version**: v2.1.0

Complete guide to the GitHub-first development workflow: Issues → Branches → PRs → Code Review → CI/CD → Merge

---

## Overview

The autonomous-dev plugin integrates seamlessly with GitHub to provide a complete team collaboration workflow:

```
GitHub Issue
    ↓
Feature Branch
    ↓
/auto-implement (8-agent pipeline)
    ↓
/full-check (quality gates)
    ↓
/commit (conventional commits)
    ↓
Pull Request
    ↓
Code Review (agent + human)
    ↓
CI/CD Checks
    ↓
Merge to Main
```

---

## Prerequisites

- ✅ GitHub repository with issues enabled
- ✅ GitHub Personal Access Token configured (see `docs/GITHUB_AUTH_SETUP.md`)
- ✅ `gh` CLI installed and authenticated
- ✅ Plugin installed: `/plugin install autonomous-dev`

---

## Complete Workflow

### Step 1: Start from GitHub Issue

**Why**: All work should be traceable to a GitHub issue

```bash
# List issues in current sprint
gh issue list --milestone "Sprint 6"

# View specific issue
gh issue view 42

# Assign issue to yourself
gh issue edit 42 --add-assignee @me
```

**Best Practices**:
- Use issue templates (`.github/ISSUE_TEMPLATE/`)
- Add labels for categorization
- Link to PROJECT.md goals in issue description
- Break large features into multiple issues

---

### Step 2: Create Feature Branch

**Branch Naming Convention**:
```bash
# Format: type/issue-number-short-description
git checkout -b feature/42-add-user-auth
git checkout -b fix/43-login-bug
git checkout -b docs/44-update-readme
git checkout -b refactor/45-auth-module
```

**Branch Types**:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation only
- `refactor/` - Code refactoring
- `test/` - Test additions/fixes
- `chore/` - Maintenance tasks

---

### Step 3: Implement with /auto-implement

**The 8-Agent Pipeline**:

```bash
# Describe the feature (reference issue)
"Implement user authentication per issue #42"

# Run autonomous implementation
/auto-implement
```

**What happens**:
1. **orchestrator** - Validates PROJECT.md alignment
2. **researcher** - Finds best practices (5 min)
3. **planner** - Creates implementation plan (5 min)
4. **test-master** - Writes failing tests first (5 min)
5. **implementer** - Makes tests pass (12 min)
6. **reviewer** - Quality gate check (2 min)
7. **security-auditor** - Security scan (2 min)
8. **doc-master** - Updates CHANGELOG (1 min)

**Total**: ~32 minutes, fully autonomous

---

### Step 4: Run Quality Checks

```bash
# Run all quality checks
/full-check

# This runs:
# - /format (black, isort, prettier)
# - /test (pytest, jest with coverage)
# - /security-scan (secrets, vulnerabilities)
```

**Quality Gates**:
- ✅ Code formatted correctly
- ✅ 80%+ test coverage
- ✅ All tests passing
- ✅ No security issues
- ✅ No hardcoded secrets

---

### Step 5: Commit with Conventional Commits

```bash
# Smart commit with conventional message
/commit

# This generates:
# - Conventional commit message (feat:, fix:, docs:)
# - References issue number automatically
# - Includes co-author attribution
```

**Conventional Commit Format**:
```
<type>(<scope>): <description>

<body>

Closes #<issue-number>

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
```

**Commit Types**:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `refactor:` - Code refactoring
- `test:` - Test changes
- `chore:` - Maintenance

---

### Step 6: Push and Create Pull Request

#### Option A: Using /pr-create (Modern - Recommended)

The `/pr-create` command is the recommended way to create PRs in the autonomous-dev workflow:

```bash
# Push with upstream tracking
git push -u origin feature/42-add-user-auth

# Create draft PR (recommended for autonomous workflow)
/pr-create

# Or: Create draft PR with reviewer assignment
/pr-create --reviewer alice

# Or: Create ready PR with custom title and multiple reviewers
/pr-create --ready --title "feat: Add user authentication" --reviewer alice,bob

# Or: Create PR against different base branch
/pr-create --base develop --reviewer @team-name
```

**What `/pr-create` Does**:
- ✅ Creates draft PR by default (requires explicit approval before merge)
- ✅ Auto-fills title and description from commit messages
- ✅ Parses commit messages for issue linking (Closes #42)
- ✅ Assigns reviewers if specified
- ✅ Validates gh CLI is installed and authenticated
- ✅ Checks for commits between base and head branches
- ✅ Returns PR number and URL for quick linking

**When Draft PRs Are Useful**:
- Early feedback from reviewers before final approval
- Multi-step feature development
- Autonomous workflow safety (requires explicit approval)
- Breaking changes needing discussion

See **PR-AUTOMATION.md** for complete `/pr-create` command reference with all flags and examples.

#### Option B: Using `gh` CLI (Alternative)

```bash
# Push with upstream tracking
git push -u origin feature/42-add-user-auth

# Create PR with gh CLI
gh pr create \
  --title "feat: Add user authentication" \
  --body "$(cat <<'EOF'
## Summary
Implements user authentication system per #42.

## Changes
- Added JWT authentication
- Implemented login/logout endpoints
- Added user session management
- Tests: 95% coverage

## Test Plan
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing complete
- [ ] Security scan passed

Closes #42

🤖 Generated with Claude Code
EOF
)"
```

#### Option C: GitHub Web UI

1. Push branch: `git push -u origin feature/42`
2. Go to GitHub repository
3. Click "Compare & pull request"
4. Fill in PR template
5. Link issue: "Closes #42"

---

### Step 7: Code Review Process

**Automatic Reviewer Agent Pre-Review**:

When PR is created, the reviewer agent automatically:
1. ✅ Checks code quality
2. ✅ Validates test coverage
3. ✅ Reviews security patterns
4. ✅ Checks documentation sync
5. ✅ Posts review comments

**Human Review**:

```bash
# Request reviewers
gh pr edit 123 --add-reviewer @teammate1,@teammate2

# View PR locally
gh pr checkout 123
gh pr diff 123

# Add review comment
gh pr comment 123 --body "LGTM! Just one suggestion..."

# Approve PR
gh pr review 123 --approve --body "Approved"
```

**Review Checklist**:
- [ ] Code follows project standards
- [ ] Tests are comprehensive
- [ ] Documentation updated
- [ ] No security concerns
- [ ] Aligns with PROJECT.md goals

---

### Step 8: Address Review Feedback

```bash
# Checkout PR branch
gh pr checkout 123

# Make changes based on feedback
# (describe changes to Claude)

# Re-run quality checks
/full-check

# Commit changes
/commit

# Push updates
git push

# PR updates automatically
```

---

### Step 9: CI/CD Checks

**Automated Checks** (if configured):

```yaml
# .github/workflows/ci.yml
name: CI

on: [pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: /test
      - name: Check coverage
        run: pytest --cov --cov-fail-under=80
      - name: Security scan
        run: /security-scan
```

**Check Status**:
```bash
# View CI status
gh pr checks 123

# View detailed logs
gh pr view 123 --web
```

---

### Step 10: Merge Pull Request

**Merge Strategies**:

```bash
# Squash and merge (recommended)
gh pr merge 123 --squash --delete-branch

# Merge commit
gh pr merge 123 --merge --delete-branch

# Rebase
gh pr merge 123 --rebase --delete-branch
```

**Auto-Merge** (when all checks pass):
```bash
gh pr merge 123 --squash --auto
```

**After Merge**:
```bash
# Sync local main
git checkout main
git pull origin main

# Delete local branch
git branch -d feature/42-add-user-auth

# Clear context for next feature
/clear
```

---

## GitHub Milestone Integration

### Sprint Tracking with Milestones

**Setup**:
```bash
# Create milestone for sprint
gh api repos/OWNER/REPO/milestones \
  -f title="Sprint 6: Team Collaboration" \
  -f description="Focus on PR automation and code review" \
  -f due_on="2025-11-03T00:00:00Z"

# List milestones
gh api repos/OWNER/REPO/milestones | jq '.[] | {title, number}'
```

**Add Issues to Milestone**:
```bash
# Add issue to milestone
gh issue edit 42 --milestone "Sprint 6"

# List sprint issues
gh issue list --milestone "Sprint 6"
```

**Track Sprint Progress**:
```bash
# View milestone progress
gh api repos/OWNER/REPO/milestones/1 | jq '{title, open_issues, closed_issues}'

# Close milestone when sprint complete
gh api repos/OWNER/REPO/milestones/1 -X PATCH -f state=closed
```

**PROJECT.md Integration**:

Update PROJECT.md with current sprint:
```markdown
## CURRENT SPRINT

**Sprint Name**: Sprint 6: Team Collaboration Features
**GitHub Milestone**: https://github.com/owner/repo/milestone/1
**Duration**: 2025-10-20 → 2025-11-03
**Status**: In Progress (40% complete)
```

---

## Advanced Workflows

### Multi-Issue Feature

For features spanning multiple issues:

```bash
# Create epic issue
gh issue create --title "[EPIC] User Management System" \
  --body "Tracking issue for user management feature"

# Create sub-issues
gh issue create --title "Add user login" --body "Part of #100"
gh issue create --title "Add user profile" --body "Part of #100"
gh issue create --title "Add user permissions" --body "Part of #100"

# Each gets its own branch/PR
git checkout -b feature/101-user-login
# ... implement, commit, PR ...

# Link PRs to epic in PR description
# "Part of #100"
```

### Hotfix Workflow

For urgent production fixes:

```bash
# Create hotfix branch from main
git checkout main
git pull origin main
git checkout -b hotfix/critical-security-issue

# Implement fix
/auto-implement

# Quality check
/full-check

# Commit
/commit

# Create PR with priority label
gh pr create --title "fix: Critical security patch" \
  --label "priority:high" \
  --label "type:security"

# Request immediate review
gh pr edit --add-reviewer @lead-dev

# Fast-track merge after approval
gh pr merge --squash
```

### Draft PR for Early Feedback

```bash
# Push work in progress
git push -u origin feature/wip

# Create draft PR
gh pr create --draft \
  --title "[WIP] Add user authentication" \
  --body "Early draft for feedback. Not ready for review."

# Request early feedback
gh pr comment --body "@teammate1 thoughts on approach?"

# Mark ready when complete
gh pr ready
```

---

## Best Practices

### Issue Management

1. **Use templates** - Consistent issue format
2. **Label issues** - Easy filtering and categorization
3. **Link to PROJECT.md** - Validate alignment
4. **Break down epics** - Smaller, manageable issues
5. **Update estimates** - Track time spent

### Branch Management

1. **Branch from main** - Always start fresh
2. **Keep branches short-lived** - Merge within 1-2 days
3. **Delete after merge** - Keep repository clean
4. **Sync frequently** - `git pull origin main` daily

### Pull Request Best Practices

1. **Small PRs** - Max 400 lines changed
2. **Clear descriptions** - Use PR template
3. **Link issues** - "Closes #N"
4. **Request specific reviewers** - Tag domain experts
5. **Respond to feedback promptly** - Within 24 hours

### Code Review Best Practices

1. **Review promptly** - Within 1 business day
2. **Be constructive** - Suggest improvements
3. **Ask questions** - Understand intent
4. **Approve when ready** - Don't block unnecessarily
5. **Learn from reviews** - Improve future PRs

---

## Troubleshooting

### "Branch behind main"

```bash
# Update branch with latest main
git checkout feature/branch
git fetch origin
git rebase origin/main

# Resolve conflicts if any
git add .
git rebase --continue

# Force push (rebased history)
git push --force-with-lease
```

### "Merge conflicts"

```bash
# Update local main
git checkout main
git pull origin main

# Rebase feature branch
git checkout feature/branch
git rebase main

# Resolve conflicts
# Edit conflicted files
git add .
git rebase --continue

# Push
git push --force-with-lease
```

### "CI checks failing"

```bash
# Run checks locally
/full-check

# View CI logs
gh pr checks 123

# Fix issues
# ... make changes ...
git commit --amend
git push --force-with-lease
```

### "PR needs updates"

```bash
# Checkout PR
gh pr checkout 123

# Make changes
# ... changes ...

# Commit
/commit

# Push
git push

# PR updates automatically
```

---

## Integration with Tools

### GitHub CLI (`gh`)

Essential commands:
```bash
gh auth status         # Check authentication
gh issue list          # List issues
gh pr list             # List PRs
gh pr create           # Create PR
gh pr view N           # View PR
gh pr diff N           # View PR diff
gh pr checks N         # View CI status
gh pr merge N          # Merge PR
```

### Git

Common operations:
```bash
git checkout -b X      # Create branch
git add .              # Stage changes
git commit             # Commit
git push               # Push to remote
git pull               # Pull from remote
git rebase             # Rebase branch
git merge              # Merge branch
```

### Claude Code

Autonomous commands:
```bash
/auto-implement        # Full 8-agent pipeline
/full-check            # Quality gates
/commit                # Smart commit
/clear                 # Clear context
```

---

## Summary Cheatsheet

```bash
# Daily Workflow
gh issue list --milestone "Current Sprint"  # Pick issue
git checkout -b feature/N-description       # Create branch
/auto-implement                             # Implement
/full-check                                 # Quality check
/commit                                     # Commit
git push -u origin feature/N                # Push
gh pr create                                # Create PR
/clear                                      # Clear context

# Review Workflow
gh pr list                                  # List PRs
gh pr checkout N                            # Checkout PR
gh pr diff N                                # View changes
gh pr review N --approve                    # Approve
gh pr merge N --squash --delete-branch      # Merge

# Sync Workflow
git checkout main                           # Switch to main
git pull origin main                        # Pull latest
git branch -d feature/N                     # Delete merged branch
```

---

**For more details**:
- Authentication: `docs/GITHUB_AUTH_SETUP.md`
- Issue tracking: `docs/GITHUB-ISSUES-INTEGRATION.md`
- PR automation: `docs/PR-AUTOMATION.md`
- Code review: `docs/CODE-REVIEW-WORKFLOW.md`
