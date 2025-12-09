# Git Workflow - Detailed Guide

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
