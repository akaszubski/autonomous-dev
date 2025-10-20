---
description: Safe alignment + GitHub sync (interactive + push + issues)
---

# Align Project - Safe + GitHub Sync

**Interactive alignment with GitHub integration (push + issues)**

---

## Usage

```bash
/align-project-sync
```

**Mode**: Interactive + GitHub sync
**Time**: 20-30 minutes (includes user input + GitHub)
**Changes**: With approval, then pushes to GitHub

---

## What This Does

Combines `/align-project-safe` with GitHub integration:

**Phases 1-3**: Same as `/align-project-safe`
- Interactive 3-phase alignment
- User confirms each phase

**Phase 4**: GitHub Sync
- Push commits to GitHub
- Create GitHub Issues for findings
- Create milestones (optional)
- Sync project metadata

---

## Expected Output

```
Running Safe Mode + GitHub Sync...

[Phases 1-3: Same as /align-project-safe]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 4: GitHub Sync
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Proposed GitHub actions:
  - Push commits to origin/main
  - Create issue: "Improve test coverage" (medium)
  - Create issue: "Add API documentation" (low)
  - Update project description

Proceed with GitHub sync? [Y/n]: Y

Pushing to GitHub...
✅ Pushed 3 commits

Creating GitHub issues...
✅ Issue #42: "Improve test coverage"
   https://github.com/user/repo/issues/42
✅ Issue #43: "Add API documentation"
   https://github.com/user/repo/issues/43

Updating project metadata...
✅ Project description updated

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Local Changes:
  Directories created: 5
  Files moved: 3
  Documentation updated: 2
  Hooks installed: 2

GitHub Sync:
  Commits pushed: 3
  Issues created: 2
  Project metadata: Updated

✅ Project aligned and synced with GitHub ✅
```

---

## Requirements

**GitHub CLI** (`gh`) must be installed and authenticated:
```bash
# Install gh
brew install gh  # macOS
# or: https://cli.github.com/

# Authenticate
gh auth login
```

**Permissions needed**:
- Push access to repository
- Issue creation permissions

---

## When to Use

- ✅ **Team environments** (share changes immediately)
- ✅ When you want issue tracking
- ✅ For sprint planning (creates milestones)
- ✅ After major alignment fixes

---

## GitHub Issue Creation

**Auto-creates issues for**:
- Missing test coverage
- Documentation gaps
- Code quality improvements
- Architectural drift
- UX friction points

**Each issue includes**:
- Priority (high/medium/low)
- Detailed description
- Recommended actions
- File locations

---

## Configuration (.env)

```bash
# GitHub sync settings
GITHUB_AUTO_ISSUE=true          # Create issues
GITHUB_ISSUE_LABEL=automated    # Label for issues
GITHUB_CREATE_MILESTONES=false  # Create milestones
```

---

## Related Commands

- `/align-project` - Analysis only
- `/align-project-safe` - Interactive (no GitHub)
- `/align-project-fix` - Auto-fix only
- `/commit-push` - Push changes without alignment

---

**Use this for team environments when you want to share alignment changes and track issues.**
