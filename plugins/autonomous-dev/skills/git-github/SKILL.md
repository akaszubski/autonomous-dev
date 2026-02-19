---
name: git-github
version: 1.0.0
type: knowledge
description: Git workflow and GitHub collaboration patterns including conventional commits, branch naming, PR workflow, and gh CLI usage
keywords: git, github, commit, branch, pr, pull request, merge, issue, gh, conventional commits
auto_activate: false
allowed-tools: [Read, Bash]
---

# Git and GitHub Workflow Skill

Comprehensive guide for Git version control and GitHub collaboration patterns.

## When This Activates

- Creating commits or branches
- Opening or reviewing pull requests
- Managing GitHub issues
- Using the gh CLI
- Keywords: "git", "github", "commit", "branch", "pr", "pull request", "merge", "issue"

---

## Conventional Commits

All commit messages follow the conventional commits specification:

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

| Type | When to Use |
|------|-------------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `docs` | Documentation only changes |
| `style` | Formatting, missing semicolons, etc. |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf` | Performance improvement |
| `test` | Adding or correcting tests |
| `chore` | Build process, auxiliary tools, or maintenance |
| `ci` | CI/CD configuration changes |

### Examples

```bash
feat(auth): add JWT token refresh endpoint
fix(api): handle null response from upstream service
docs: update API reference for v2 endpoints
refactor(db): extract query builder into separate module
test(auth): add integration tests for OAuth flow
chore: upgrade dependencies to latest versions
```

### Breaking Changes

Use `!` after type or add `BREAKING CHANGE:` footer:

```bash
feat(api)!: change response format from XML to JSON
```

---

## Branch Naming Conventions

```
<type>/<issue-number>-<short-description>
```

### Patterns

| Pattern | Example |
|---------|---------|
| Feature | `feat/123-add-user-auth` |
| Bug fix | `fix/456-null-pointer-crash` |
| Docs | `docs/789-update-api-reference` |
| Refactor | `refactor/101-extract-helpers` |

### Rules

- Use lowercase with hyphens (no underscores or spaces)
- Include issue number when applicable
- Keep descriptions under 5 words
- Delete branches after merging

---

## PR Workflow with gh CLI

### Creating Pull Requests

```bash
# Create PR with title and body
gh pr create --title "feat: add user authentication" --body "$(cat <<'EOF'
## Summary
- Add JWT-based authentication
- Implement login/logout endpoints

## Test plan
- [ ] Unit tests for token generation
- [ ] Integration tests for auth flow
EOF
)"

# Create draft PR
gh pr create --draft --title "wip: refactor database layer"

# Create PR targeting specific base branch
gh pr create --base develop --title "feat: new feature"
```

### Reviewing Pull Requests

```bash
# List open PRs
gh pr list

# View PR details
gh pr view 123

# Check out PR locally
gh pr checkout 123

# Approve PR
gh pr review 123 --approve

# Request changes
gh pr review 123 --request-changes --body "Please fix the error handling"

# Merge PR
gh pr merge 123 --squash --delete-branch
```

### PR Best Practices

1. **Keep PRs small** - Under 400 lines changed when possible
2. **One concern per PR** - Don't mix features with refactors
3. **Write descriptive titles** - Use conventional commit format
4. **Include test plan** - Checklist of what to verify
5. **Link issues** - Use "Closes #123" in body

---

## Issue Management

### Creating Issues

```bash
# Create issue with title and body
gh issue create --title "Bug: login fails on Safari" --body "Steps to reproduce..."

# Create with labels
gh issue create --title "feat: dark mode" --label "enhancement,ui"

# Create with assignee
gh issue create --title "fix: memory leak" --assignee "@me"
```

### Issue Templates

Use labels to categorize:

| Label | Color | Purpose |
|-------|-------|---------|
| `bug` | red | Something broken |
| `enhancement` | blue | New feature request |
| `documentation` | green | Docs improvement |
| `good first issue` | purple | Beginner friendly |
| `priority: high` | orange | Needs immediate attention |

### Linking Issues to PRs

```bash
# In PR body
Closes #123
Fixes #456
Resolves #789
```

---

## Git Hooks Best Practices

### Pre-commit

```bash
# Format code
black --check src/
isort --check src/

# Lint
flake8 src/

# Check for secrets
detect-secrets scan
```

### Pre-push

```bash
# Run tests
pytest tests/ -x --timeout=60

# Type check
mypy src/
```

### Commit-msg

```bash
# Validate conventional commit format
pattern="^(feat|fix|docs|style|refactor|perf|test|chore|ci)(\(.+\))?!?: .{1,72}"
if ! echo "$1" | grep -qE "$pattern"; then
    echo "Invalid commit message format"
    exit 1
fi
```

---

## Common Git Operations

### Stashing Changes

```bash
git stash push -m "wip: authentication changes"
git stash list
git stash pop
```

### Interactive Rebase (cleanup before PR)

```bash
git rebase -i HEAD~3  # Squash last 3 commits
```

### Cherry-picking

```bash
git cherry-pick abc1234  # Apply specific commit
```

### Resolving Conflicts

```bash
git merge main           # Trigger merge
# Fix conflicts in editor
git add .
git commit               # Complete merge
```

---

## Key Takeaways

1. **Conventional commits** - Always use type(scope): description format
2. **Branch naming** - type/issue-description pattern
3. **Small PRs** - Under 400 lines, one concern each
4. **gh CLI** - Use for all GitHub operations
5. **Link issues** - Always connect PRs to issues
6. **Git hooks** - Automate quality checks
7. **Delete merged branches** - Keep repository clean
