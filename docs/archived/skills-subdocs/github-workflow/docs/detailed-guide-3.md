# Github Workflow - Detailed Guide

## Steps to Reproduce
1. Step 1
2. Step 2
3. See error

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS:
- Version:

## Additional Context
Any other context
```

**Use**:
```bash
gh issue create --template bug_report.md
```

---

## Quick Command Reference

```bash
# ISSUES
/issue                        # Interactive issue creation
gh issue list                 # List all issues
gh issue view 42              # View specific issue
gh issue create               # Manual issue creation
gh issue close 42             # Close issue

# PULL REQUESTS
/pr-create                    # Draft PR (default)
/pr-create --ready            # Ready PR
/pr-create --reviewer alice   # PR with reviewer
gh pr list                    # List PRs
gh pr view                    # View current PR
gh pr merge                   # Merge PR

# MILESTONES
gh api repos/user/repo/milestones    # List milestones
gh issue list --milestone "Sprint 6" # Issues in milestone

# WORKFLOW
git checkout -b feature/42-description   # Create branch
/commit                                  # Commit with checks
git push                                 # Push changes
/pr-create                               # Create PR
```

---

## See Also

- `docs/GITHUB-WORKFLOW.md` - Complete workflow guide
- `docs/GITHUB_AUTH_SETUP.md` - Authentication setup
- `commands/issue.md` - `/issue` command reference
- `commands/pr-create.md` - `/pr-create` command reference
- `hooks/auto_track_issues.py` - Auto-tracking hook code

---

**Use this skill to master GitHub-first autonomous development workflow**
