---
name: git-workflow
type: knowledge
description: Git best practices, commit conventions, branching strategies, and pull request workflows. Use when working with git operations, commits, branches, or PRs.
keywords: git, commit, branch, pull request, pr, merge, github, conventional commits, workflow
auto_activate: true
---

# Git Workflow Skill

Git best practices and workflow standards for team collaboration.

## When This Activates
- Git operations (commit, branch, merge)
- Pull request creation/review
- Release management
- CI/CD integration
- Keywords: "git", "commit", "branch", "pr", "merge", "github"

---

## Commit Messages

### Format

**Pattern**: `<type>: <description>`

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `refactor`: Code restructuring (no behavior change)
- `test`: Adding/updating tests
- `chore`: Tooling, dependencies, config

### Examples

```bash
# ❌ BAD
git commit -m "updates"
git commit -m "fixed stuff"
git commit -m "wip"

# ✅ GOOD
git commit -m "feat: add PDF/EPUB content extraction"
git commit -m "fix: correct nested layer access in transformer models"
git commit -m "docs: update QUICKSTART with new training methods"
git commit -m "refactor: extract validation logic to separate module"
git commit -m "test: add integration tests for data curator"
```

### Multi-line Commits

For complex changes, use commit body:

```bash
git commit -m "feat: implement DPO training method

- Add DPOStrategy class with preference pair handling
- Integrate with existing Trainer interface
- Update docs with DPO examples

Closes #15"
```

**Template**:
```
<type>: <short summary>

<body - explain WHY, not WHAT>

<footer - issue references, breaking changes>
```

---

## Branch Naming

### Format

**Pattern**: `<type>/<short-description>`

### Examples

```bash
# ❌ BAD
git checkout -b new-feature
git checkout -b fix
git checkout -b john-branch

# ✅ GOOD
git checkout -b feat/pdf-epub-support
git checkout -b fix/transformer-layer-access
git checkout -b refactor/data-curator-validation
git checkout -b docs/update-training-guide
```

### Types

- `feat/` - New feature development
- `fix/` - Bug fixes
- `refactor/` - Code restructuring
- `docs/` - Documentation updates
- `test/` - Test additions/updates
- `chore/` - Tooling, config, dependencies

---

## Branching Strategies

### Feature Branch Workflow (Recommended)

```bash
# 1. Create feature branch from main
git checkout main
git pull origin main
git checkout -b feat/new-feature

# 2. Work on feature
# ... make changes ...
git add .
git commit -m "feat: implement new feature"

# 3. Keep up to date with main
git checkout main
git pull origin main
git checkout feat/new-feature
git rebase main  # or merge main

# 4. Push and create PR
git push -u origin feat/new-feature
# Create PR via GitHub
```

### Protected Main Branch

**Rules**:
- No direct commits to `main`
- All changes via pull requests
- Require review before merge
- Require CI checks to pass
- Delete branch after merge

---

## Pull Request Guidelines

### PR Title

Same as commit message format:

```
feat: add PDF extraction support
fix: resolve memory leak in data loader
docs: update installation instructions
```

### PR Description Template

```markdown
## Summary
Brief description of changes (1-3 sentences)

## Changes
- Add PDF extraction using PyPDF2
- Update DataCurator class with extract_from_pdf method
- Add tests for PDF extraction

## Testing
- [x] Unit tests added/updated
- [x] Integration tests pass
- [x] Manual testing completed

## Checklist
- [x] Code follows style guide
- [x] Documentation updated
- [x] Tests pass locally
- [x] No new warnings

Closes #42
```

### PR Size Guidelines

**Keep PRs Small**:
- ✅ **Small**: < 300 lines changed (ideal)
- ⚠️ **Medium**: 300-500 lines (acceptable)
- ❌ **Large**: > 500 lines (split if possible)

**Why**: Smaller PRs are:
- Easier to review
- Faster to merge
- Less likely to have conflicts
- Easier to revert if needed

### When to Split PRs

```markdown
# ❌ BAD: One massive PR
feat: complete rewrite of training system
- Refactor trainer (500 lines)
- Add new methods (300 lines)
- Update docs (100 lines)
- Add tests (200 lines)
Total: 1100 lines!

# ✅ GOOD: Multiple focused PRs
PR #1: refactor: extract strategy pattern for training methods (200 lines)
PR #2: feat: add DPO training strategy (150 lines)
PR #3: feat: add full fine-tuning strategy (150 lines)
PR #4: docs: update training guide with new methods (100 lines)
PR #5: test: add integration tests for training strategies (200 lines)
```

---

## Code Review Process

### Creating a PR

1. **Ensure tests pass locally**:
```bash
pytest tests/
black . && isort .
mypy src/
```

2. **Write clear PR description** (use template above)

3. **Request reviewers**: Tag appropriate team members

4. **Link issues**: Use "Closes #N" or "Fixes #N"

### Responding to Review Feedback

**Process**:
1. Read all comments before responding
2. Ask clarifying questions if needed
3. Make requested changes
4. Reply to comments when done
5. Request re-review

**Response Types**:

```markdown
# ✅ Agree and implemented
Done! Changed to use a set for O(1) lookup.

# ❓ Clarifying question
Good point - should this handle empty lists as well, or can we assume non-empty?

# 💭 Alternative approach
I see your concern. What if we use a generator instead? That avoids loading everything into memory.

# ✅ Agree but out of scope
You're right, but I'd prefer to address that in a separate PR since it's unrelated. Created #54 to track it.
```

### Merging

**Options**:
- **Squash and merge**: Combines all commits into one (recommended for feature branches)
- **Rebase and merge**: Replays commits on top of main (for clean history)
- **Merge commit**: Preserves all commits (for long-running branches)

**Recommended**: Squash and merge for most PRs

**After Merge**:
```bash
# Delete remote branch
git push origin --delete feat/my-feature

# Delete local branch
git checkout main
git branch -d feat/my-feature

# Pull latest main
git pull origin main
```

---

## Git Best Practices

### Commit Often, Perfect Later

```bash
# While working
git commit -m "wip: add validation logic"
git commit -m "wip: handle edge cases"
git commit -m "wip: add tests"

# Before pushing, squash/rebase to clean history
git rebase -i HEAD~3
# Squash commits into one clean commit
```

### Write Atomic Commits

**One commit = One logical change**:

```bash
# ❌ BAD: Multiple unrelated changes
git commit -m "fix: add validation, update docs, refactor tests"

# ✅ GOOD: Separate commits
git commit -m "fix: add input validation for user data"
git commit -m "docs: update validation examples in README"
git commit -m "refactor: extract validation tests to separate file"
```

### Use `.gitignore` Properly

**Common patterns**:
```gitignore
# Python
__pycache__/
*.py[cod]
*.so
.Python
env/
venv/
*.egg-info/

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Project-specific
.env
*.log
data/
*.db
```

### Never Commit Secrets

```bash
# ❌ BAD
DATABASE_URL=postgres://user:password@host/db

# ✅ GOOD: Use .env file (gitignored)
# .env
DATABASE_URL=postgres://user:password@host/db

# Load in code
from dotenv import load_dotenv
load_dotenv()
```

**If you accidentally commit secrets**:
1. Rotate the secret immediately
2. Use `git filter-branch` or BFG Repo-Cleaner to remove from history
3. Force push (WARNING: Only on personal branches!)

---

## CI/CD Integration

### GitHub Actions Workflow

Minimum CI checks:

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run formatters (check)
        run: |
          black --check .
          isort --check .

      - name: Run linter
        run: ruff check .

      - name: Run type checker
        run: mypy src/

      - name: Run tests
        run: pytest tests/ --cov=src/ --cov-report=term-missing

      - name: Check coverage
        run: |
          coverage report --fail-under=80
```

### Pre-commit Hooks

Install locally for automatic checks:

```bash
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.11.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: local
    hooks:
      - id: tests
        name: run tests
        entry: pytest tests/
        language: system
        pass_filenames: false
        always_run: true
```

---

## Release Management

### Semantic Versioning

**Format**: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes
- **MINOR**: New features (backwards compatible)
- **PATCH**: Bug fixes (backwards compatible)

**Examples**:
- `1.0.0` → `1.0.1`: Bug fix
- `1.0.1` → `1.1.0`: New feature added
- `1.1.0` → `2.0.0`: Breaking change

### Creating a Release

```bash
# 1. Update version in code
# (setup.py, __version__, etc.)

# 2. Update CHANGELOG.md
## [1.2.0] - 2025-10-25
### Added
- PDF extraction support
- New training strategies

### Fixed
- Memory leak in data loader

### Changed
- Improved error messages

# 3. Commit version bump
git commit -m "chore: bump version to 1.2.0"

# 4. Tag release
git tag -a v1.2.0 -m "Release v1.2.0"

# 5. Push with tags
git push origin main --tags

# 6. Create GitHub Release
# (via GitHub UI or gh CLI)
gh release create v1.2.0 --title "v1.2.0" --notes "See CHANGELOG.md"
```

---

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
**See Also**: python-standards, documentation-guide, code-review
