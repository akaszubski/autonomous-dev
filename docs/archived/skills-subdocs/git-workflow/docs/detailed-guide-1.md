# Git Workflow - Detailed Guide

## When This Activates
- Git operations (commit, branch, merge)
- Pull request creation/review
- Release management
- CI/CD integration
- Keywords: "git", "commit", "branch", "pr", "merge", "github"

## Detailed Documentation

For comprehensive commit message patterns and examples:
- **Commit Patterns**: See [docs/commit-patterns.md](docs/commit-patterns.md) for detailed conventional commit specification
- **Real-World Examples**: See [examples/commit-examples.txt](examples/commit-examples.txt) for 50+ production-ready commit messages

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
