# Git Workflow - Detailed Guide

## Troubleshooting

### Undoing Changes

```bash
# Undo last commit (keep changes)
git reset --soft HEAD~1

# Undo last commit (discard changes)
git reset --hard HEAD~1

# Undo changes to specific file
git checkout -- file.py

# Revert a merged PR
git revert -m 1 <merge-commit-hash>
```

### Fixing Commit Messages

```bash
# Fix last commit message
git commit --amend -m "fix: correct commit message"

# Fix older commits
git rebase -i HEAD~3
# Change "pick" to "reword" for commits to fix
```

### Resolving Merge Conflicts

```bash
# 1. Update main
git checkout main
git pull origin main

# 2. Merge main into feature branch
git checkout feat/my-feature
git merge main

# 3. Resolve conflicts
# (edit files, remove conflict markers)

# 4. Mark as resolved
git add .
git commit -m "chore: resolve merge conflicts with main"

# 5. Push
git push origin feat/my-feature
```

---

## Integration with [PROJECT_NAME]

[PROJECT_NAME] uses the following git workflow:

- **Branch naming**: `<type>/<description>` (e.g., `feat/pdf-support`)
- **Commit messages**: Conventional commits (`feat:`, `fix:`, etc.)
- **PR reviews**: Required for all changes to main
- **CI checks**: Tests, formatters, linters must pass
- **Release**: Semantic versioning with GitHub Releases

---

**Version**: 1.0.0
**Type**: Knowledge skill (no scripts)
**See Also**: engineering-standards, documentation-guide, code-review
