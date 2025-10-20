# Team Onboarding Guide

**Last Updated**: 2025-10-20
**Version**: v2.0.0

Complete guide for onboarding new team members to autonomous development workflow.

---

## Overview

This guide helps new developers:
1. Install and configure the autonomous-dev plugin
2. Understand the PROJECT.md-first workflow
3. Set up GitHub integration for team collaboration
4. Learn the team's development workflow
5. Make their first contribution

**Time to complete**: 30-45 minutes

---

## Prerequisites

Before onboarding, ensure you have:
- ✅ Claude Code 2.0+ installed
- ✅ Python 3.11+ installed
- ✅ Git configured
- ✅ GitHub account (for team features)
- ✅ Access to team repository

---

## Step 1: Install Plugin (5 minutes)

### Add Marketplace
```bash
/plugin marketplace add akaszubski/autonomous-dev
```

### Install Plugin
```bash
/plugin install autonomous-dev
```

### Verify Installation
```bash
# Check agents installed
ls -la .claude/agents/

# Should see 8 agents:
# - orchestrator.md
# - planner.md
# - researcher.md
# - test-master.md
# - implementer.md
# - reviewer.md
# - security-auditor.md
# - doc-master.md
```

---

## Step 2: Understand PROJECT.md (10 minutes)

### Read Team's Strategic Direction

```bash
# Open PROJECT.md
cat .claude/PROJECT.md

# Focus on these sections:
# - GOALS: What success looks like
# - SCOPE: What's in/out of scope
# - CONSTRAINTS: Technical limits
# - CURRENT SPRINT: Active work
```

### Key Concepts

**PROJECT.md is the source of truth**:
- All work must align with GOALS
- Features must be IN SCOPE
- Must respect CONSTRAINTS
- orchestrator validates alignment before any work starts

**Example validation**:
```
You: "Add user authentication"

orchestrator:
1. ✅ Reads PROJECT.md
2. ✅ Checks: Does this align with GOALS?
3. ✅ Checks: Is this IN SCOPE?
4. ✅ Checks: Respects CONSTRAINTS?
5. ✅ Only proceeds if aligned
```

### Questions to Ask
- What are the project's primary goals?
- What's explicitly out of scope?
- What are the key constraints?
- What sprint are we in?

---

## Step 3: Configure GitHub Integration (10 minutes)

### Create Personal Access Token

1. **Go to**: https://github.com/settings/tokens
2. **Click**: "Generate new token (classic)"
3. **Name**: "Claude Code Autonomous Dev"
4. **Expiration**: 90 days (renewable)
5. **Scopes**: Check these:
   - ✅ `repo` (Full repository access)
   - ✅ `workflow` (Update GitHub Actions)
6. **Generate token** and copy it

### Configure Environment

```bash
# Create .env file (gitignored)
cat > .env <<EOF
GITHUB_TOKEN=ghp_your_token_here
GITHUB_OWNER=your-org-or-username
GITHUB_REPO=repository-name
EOF

# Verify .gitignore includes .env
grep ".env" .gitignore
```

### Test Connection

```bash
# Test GitHub connection
gh auth status

# If not authenticated:
gh auth login --with-token < .env
```

---

## Step 4: Learn Team Workflow (10 minutes)

### GitHub-First Workflow

```
Issues → Branches → PRs → Code Review → CI/CD → Merge
```

**Step-by-step**:

1. **Pick an issue** from GitHub Milestone
   ```bash
   gh issue list --milestone "Current Sprint"
   ```

2. **Create feature branch**
   ```bash
   git checkout -b feature/issue-123-description
   ```

3. **Implement with /auto-implement**
   ```bash
   # Describe the feature
   "Implement user authentication per issue #123"

   # Run autonomous implementation
   /auto-implement
   ```

4. **Quality checks**
   ```bash
   /full-check
   ```

5. **Commit**
   ```bash
   /commit
   ```

6. **Create PR** (automated or manual)
   ```bash
   # Option 1: Automated (if configured)
   git push -u origin feature/issue-123

   # Option 2: Manual
   gh pr create --title "feat: Add user authentication" \
                --body "Closes #123"
   ```

7. **Code review** - Reviewer agent + human reviewers

8. **Merge** - After approval

### Context Management (CRITICAL)

```bash
# After EACH feature, clear context
/clear

# This keeps context under 8K tokens
# Enables 100+ features per session
```

---

## Step 5: Make First Contribution (5-10 minutes)

### Choose a Good First Issue

```bash
# Find beginner-friendly issues
gh issue list --label "good first issue"
```

### Follow Contribution Guidelines

1. **Read** `docs/CONTRIBUTING.md`
2. **Check** PROJECT.md alignment
3. **Create branch** from main
4. **Implement** with /auto-implement
5. **Test** with /full-check
6. **Commit** with /commit
7. **Push** and create PR
8. **Respond** to review feedback

### Example First Contribution

```bash
# 1. Pick issue
gh issue view 42

# 2. Create branch
git checkout -b fix/issue-42-typo-in-readme

# 3. Make change
# (describe to Claude)

# 4. Auto-implement
/auto-implement

# 5. Quality check
/full-check

# 6. Commit
/commit

# 7. Create PR
git push -u origin fix/issue-42-typo-in-readme
gh pr create

# 8. Clear context
/clear
```

---

## Team Development Workflow

### Daily Workflow

**Morning**:
```bash
# 1. Sync with main
git checkout main
git pull origin main

# 2. Check sprint status
cat .claude/PROJECT.md | grep "CURRENT SPRINT" -A 10

# 3. Pick issue from milestone
gh issue list --milestone "Sprint 6"
```

**During Development**:
```bash
# 1. Create feature branch
git checkout -b feature/issue-N

# 2. Implement
/auto-implement

# 3. Quality check
/full-check

# 4. Commit
/commit

# 5. Clear context
/clear
```

**End of Day**:
```bash
# Push work in progress
git push -u origin feature/issue-N

# Create draft PR (optional)
gh pr create --draft
```

### Team Practices

**Code Review**:
- All PRs require 1+ human approval
- Reviewer agent does pre-review
- Address feedback promptly
- Use GitHub PR review features

**Communication**:
- Use GitHub issues for discussions
- Link PRs to issues
- Update PROJECT.md when direction changes
- Notify team of sprint changes

**Quality Standards**:
- 80%+ test coverage minimum
- All tests must pass
- Security scan must pass
- Format code automatically

---

## Common Team Scenarios

### Scenario 1: Joining Mid-Sprint

```bash
# 1. Read sprint goals
cat .claude/PROJECT.md | grep "Sprint Goals" -A 10

# 2. Check available issues
gh issue list --milestone "Current Sprint" --assignee ""

# 3. Ask team lead for guidance
gh issue comment ISSUE_NUMBER --body "I can work on this"

# 4. Follow normal workflow
```

### Scenario 2: Proposing New Feature

```bash
# 1. Check if in scope
cat .claude/PROJECT.md | grep "SCOPE" -A 20

# 2. Create GitHub issue
gh issue create --title "Feature: X" --body "Description..."

# 3. Discuss with team
# Wait for approval before implementing

# 4. If approved, add to sprint milestone
```

### Scenario 3: Blocked by Dependencies

```bash
# 1. Comment on PR
gh pr comment PR_NUMBER --body "Blocked by #ISSUE_NUMBER"

# 2. Work on different issue
gh issue list --label "ready"

# 3. Come back when unblocked
```

### Scenario 4: Updating PROJECT.md

```bash
# Only update PROJECT.md if:
# - Strategic direction changes
# - New goals added
# - Scope boundaries change
# - Team lead approves

# 1. Create branch
git checkout -b docs/update-project-md

# 2. Edit PROJECT.md
vim .claude/PROJECT.md

# 3. Create PR (requires review)
gh pr create --title "docs: Update PROJECT.md goals"

# 4. Get team approval before merging
```

---

## Troubleshooting

### "Context budget exceeded"
```bash
/clear  # Then retry
```

### "Feature doesn't align with PROJECT.md"
1. Re-read PROJECT.md GOALS and SCOPE
2. Either: Modify feature to align
3. Or: Discuss with team lead about updating PROJECT.md

### "GitHub auth failed"
1. Check `.env` has valid token
2. Token needs `repo` scope
3. See `docs/GITHUB_AUTH_SETUP.md`

### "Pre-commit hooks failed"
1. Hooks auto-format and test your code
2. Read error message
3. Fix issues and retry commit
4. If stuck, ask team for help

### "Tests failing on CI"
1. Run tests locally: `/test`
2. Fix failures
3. Push fix
4. CI will re-run automatically

---

## Team Resources

### Documentation
- **PROJECT.md** - Strategic direction (read daily)
- **docs/CONTRIBUTING.md** - How to contribute
- **docs/GITHUB-WORKFLOW.md** - Complete GitHub workflow
- **docs/CODE-REVIEW-WORKFLOW.md** - Review process
- **docs/TROUBLESHOOTING.md** - Common issues

### Communication Channels
- **GitHub Issues** - Feature discussions, bug reports
- **GitHub Discussions** - Questions, ideas
- **Pull Requests** - Code review, feedback

### Getting Help
1. **Check docs first**: `docs/README.md`
2. **Search existing issues**: `gh issue list`
3. **Ask in GitHub Discussions**
4. **Tag team lead in PR comments**

---

## Checklist: Onboarding Complete

- [ ] Plugin installed and verified
- [ ] Read and understood PROJECT.md
- [ ] GitHub token configured
- [ ] Tested GitHub connection
- [ ] Read CONTRIBUTING.md
- [ ] Understand team workflow
- [ ] Made first contribution
- [ ] Know how to get help
- [ ] Know when to use /clear

**Welcome to the team! 🎉**

---

## Next Steps

1. **Pick a good first issue** - Start small
2. **Join team standup** - If applicable
3. **Review recent PRs** - Learn from others
4. **Ask questions** - We're here to help
5. **Read advanced docs** - docs/CUSTOMIZATION.md

---

## Quick Reference

```bash
# Daily commands
/auto-implement     # Implement feature
/full-check         # Quality checks
/commit             # Smart commit
/clear              # Clear context (IMPORTANT!)

# GitHub commands
gh issue list       # List issues
gh pr create        # Create PR
gh pr list          # List PRs
gh pr view N        # View PR details

# Git workflow
git checkout -b feature/X  # Create branch
git push -u origin X       # Push branch
git checkout main          # Back to main
git pull origin main       # Sync with team
```

---

**Questions? See `docs/TROUBLESHOOTING.md` or ask in GitHub Discussions.**
