---
description: Create GitHub pull request with optional reviewer assignment (default: draft mode)
---

# /pr-create - GitHub PR Creation

**Create pull requests automatically with intelligent defaults and issue linking**

---

## Usage

```bash
/pr-create [FLAGS]
```

**Time**: < 5 seconds
**Requirements**: GitHub CLI (`gh`) installed and authenticated

---

## Flags

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--title` | string | auto-fill | Custom PR title (uses commit messages if not provided) |
| `--body` | string | auto-fill | Custom PR description (uses commit messages if not provided) |
| `--ready` | boolean | false | Create as ready PR (skip draft mode) |
| `--reviewer` | string | none | Assign reviewer(s) (comma-separated for multiple) |
| `--base` | string | main | Target branch (default: main or detected from git) |

---

## Examples

### Example 1: Simple Draft PR (Recommended)

```bash
# Create draft PR (requires human approval before merge)
/pr-create
```

**What happens:**
- ✅ Creates draft PR from current branch to main
- ✅ Auto-fills title/body from commit messages
- ✅ Parses issue keywords (Closes #123, Fixes #456)
- ✅ Links to issues automatically
- ✅ Draft mode: Requires marking as "Ready" before merge

**When to use**: Default workflow - safe, requires review approval

---

### Example 2: Draft PR with Reviewer

```bash
# Create draft PR and assign reviewer
/pr-create --reviewer alice
```

**What happens:**
- ✅ Creates draft PR
- ✅ Assigns alice as reviewer
- ✅ Alice gets notified immediately
- ✅ Alice can provide feedback before you mark as ready

**When to use**: Want early feedback before finalizing PR

---

### Example 3: Ready PR with Multiple Reviewers

```bash
# Create ready-for-review PR with multiple reviewers
/pr-create --ready --reviewer alice,bob
```

**What happens:**
- ✅ Creates ready (not draft) PR
- ✅ Assigns alice and bob as reviewers
- ✅ Both get notified
- ✅ Ready for merge after approvals

**When to use**: Feature complete, tests passing, ready for final review

---

### Example 4: PR to Different Base Branch

```bash
# Create PR targeting develop instead of main
/pr-create --base develop --reviewer team-lead
```

**What happens:**
- ✅ Creates draft PR to develop branch
- ✅ Assigns team-lead as reviewer
- ✅ Useful for feature branches or staging environments

**When to use**: Multi-branch workflows (main/develop/staging)

---

### Example 5: Custom Title and Body

```bash
# Create PR with custom title and description
/pr-create --title "feat: Add user authentication" --body "Implements OAuth 2.0 with Google provider" --ready
```

**What happens:**
- ✅ Uses custom title instead of commit messages
- ✅ Uses custom description
- ✅ Creates as ready PR

**When to use**: Need more descriptive PR title than commit messages provide

---

## How It Works Internally

### Step 1: Prerequisites Validation
- Checks GitHub CLI (`gh`) is installed
- Verifies `gh` is authenticated
- Ensures not on main/master branch

### Step 2: Branch Validation
- Gets current branch name
- Validates branch has commits not in base branch
- Prevents empty PRs

### Step 3: Issue Parsing
- Scans commit messages for issue keywords:
  - `Closes #123`
  - `Fixes #456`
  - `Resolves #789`
- Extracts issue numbers automatically

### Step 4: PR Creation
- Calls `gh pr create` with appropriate flags
- Sets draft mode (unless `--ready` specified)
- Auto-fills title/body from commits (unless custom provided)
- Assigns reviewers if specified

### Step 5: Issue Linking
- GitHub automatically links issues mentioned in commits
- Issues close automatically when PR merges

### Step 6: Returns PR URL
- Outputs PR URL for easy access
- Shows PR number for reference

---

## Configuration

Add to `.env` (optional):

```bash
# PR Creation Defaults
PR_DEFAULT_DRAFT=true          # Create PRs as draft by default (recommended)
PR_DEFAULT_BASE=main           # Default target branch
```

---

## Troubleshooting

### Error: "GitHub CLI not installed"

**Problem**: `gh` command not found

**Solution**:
```bash
# macOS
brew install gh

# Linux
sudo apt install gh    # Debian/Ubuntu
sudo dnf install gh    # Fedora

# Windows
choco install gh       # Chocolatey
winget install gh      # Winget

# Or download from: https://cli.github.com/
```

---

### Error: "GitHub CLI not authenticated"

**Problem**: `gh` not logged in

**Solution**:
```bash
# Authenticate with GitHub
gh auth login

# Follow prompts to:
# 1. Choose GitHub.com
# 2. Choose HTTPS or SSH
# 3. Paste authentication token or login via browser

# Verify authentication
gh auth status
```

**Alternative**: Set GITHUB_TOKEN environment variable
```bash
# Create token at: https://github.com/settings/tokens
# Requires 'repo' scope for PR creation

export GITHUB_TOKEN=ghp_your_token_here
# Or add to .env file
```

---

### Error: "Cannot create PR from main branch"

**Problem**: Currently on main/master branch

**Solution**:
```bash
# Create and switch to feature branch
git checkout -b feature/my-feature

# Make changes, then create PR
/pr-create
```

---

### Error: "No commits found between main and feature-branch"

**Problem**: No commits on feature branch

**Solution**:
```bash
# Make changes first
git add .
git commit -m "feat: Add feature"

# Then create PR
/pr-create
```

---

### Error: "Rate limit exceeded"

**Problem**: GitHub API rate limit hit (60 requests/hour unauthenticated, 5000/hour authenticated)

**Solution**:
```bash
# Check rate limit
gh api rate_limit

# Authenticate to increase limit
gh auth login

# Or wait for rate limit reset
```

---

### Error: "Permission denied / insufficient scope"

**Problem**: GITHUB_TOKEN lacks 'repo' scope

**Solution**:
```bash
# Create new token with 'repo' scope
# Visit: https://github.com/settings/tokens
# Select: repo (Full control of private repositories)

# Update token
gh auth login   # Use new token
```

---

## Best Practices

### 1. Use Draft Mode by Default
```bash
# ✅ Good: Draft allows feedback before final approval
/pr-create

# ❌ Risky: Ready mode skips draft review stage
/pr-create --ready
```

### 2. Assign Reviewers Early
```bash
# ✅ Good: Get feedback during development
/pr-create --reviewer alice

# ❌ Late: Add reviewers after PR is complete
```

### 3. Link Issues in Commits
```bash
# ✅ Good: Issues close automatically
git commit -m "fix: Resolve auth bug (Closes #123)"

# ❌ Manual: Have to close issues manually
git commit -m "fix: Resolve auth bug"
```

### 4. Use Conventional Commits
```bash
# ✅ Good: Clear, semantic commit messages
git commit -m "feat: Add user authentication"
git commit -m "fix: Resolve login error"

# ❌ Unclear: Vague commit messages
git commit -m "Updates"
git commit -m "Fix stuff"
```

---

## Integration with Workflow

### Complete Development Workflow

```bash
# 1. Create feature branch
git checkout -b feature/user-auth

# 2. Implement feature (autonomous or manual)
/auto-implement "user authentication"
# Or: Make changes manually

# 3. Commit changes
/commit

# 4. Create draft PR with reviewer
/pr-create --reviewer alice

# 5. Get feedback, make changes
# ... address review comments ...
/commit

# 6. Mark PR as ready (via GitHub UI or gh CLI)
gh pr ready <PR-number>

# 7. Merge after approval
gh pr merge <PR-number>
```

---

## See Also

- [PR-AUTOMATION.md](../docs/PR-AUTOMATION.md) - Complete guide
- [GITHUB-WORKFLOW.md](../docs/GITHUB-WORKFLOW.md) - Full workflow integration
- `/commit` - Quick commit with formatting
- `/commit-push` - Commit and push to GitHub
- `/auto-implement` - Autonomous feature implementation

---

**Command**: `/pr-create`
**Category**: GitHub Workflow
**Time**: < 5 seconds
**Requirements**: GitHub CLI authenticated
