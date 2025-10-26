# Code Review Workflow

**Last Updated**: 2025-10-20
**Version**: v2.0.0

Combining automated reviewer agent with human code review for quality gates.

---

## Two-Layer Review Process

```
Pull Request Created
    ↓
Layer 1: Reviewer Agent (Automated)
    ├─ Code quality check
    ├─ Test coverage validation
    ├─ Security scan
    ├─ Documentation sync
    └─ Posts review comments
    ↓
Layer 2: Human Review (Required)
    ├─ Architecture review
    ├─ Business logic validation
    ├─ Edge case consideration
    └─ Final approval
    ↓
Merge (All approvals + CI passing)
```

---

## Layer 1: Automated Reviewer Agent

### What It Checks

✅ **Code Quality**:
- Follows project standards
- No code smells
- Proper naming conventions
- Comments where needed

✅ **Test Coverage**:
- 80%+ coverage minimum
- All critical paths tested
- Edge cases covered

✅ **Security**:
- No hardcoded secrets
- Input validation present
- No SQL injection risks
- OWASP compliance

✅ **Documentation**:
- Docstrings updated
- README synced
- CHANGELOG entry added

### How to Run

Automatic on PR creation, or manual:
```bash
# Manual reviewer agent run
# (describe PR to Claude)
"Review PR #123 for code quality and security"

# Agent uses reviewer.md configuration
```

---

## Layer 2: Human Review

### Review Checklist

**Architecture** (5 min):
- [ ] Fits existing architecture
- [ ] No unnecessary complexity
- [ ] Proper separation of concerns
- [ ] Scalable approach

**Business Logic** (10 min):
- [ ] Correctly implements requirements
- [ ] Handles edge cases
- [ ] Error handling appropriate
- [ ] Aligns with PROJECT.md goals

**Code Quality** (5 min):
- [ ] Readable and maintainable
- [ ] No duplicated code
- [ ] Proper abstractions
- [ ] Follows team conventions

**Testing** (5 min):
- [ ] Tests are comprehensive
- [ ] Tests are meaningful
- [ ] Test names are clear
- [ ] Mocks used appropriately

**Documentation** (3 min):
- [ ] Code is self-documenting
- [ ] Complex logic explained
- [ ] API changes documented
- [ ] Examples provided

---

## Conducting Reviews

### As Reviewer

```bash
# Checkout PR locally
gh pr checkout 123

# Run tests
/test

# View changes
gh pr diff 123

# Add review comments
gh pr review 123 --comment \
  --body "Consider extracting this logic into a helper function"

# Request changes
gh pr review 123 --request-changes \
  --body "Please add tests for edge case X"

# Approve
gh pr review 123 --approve \
  --body "LGTM! Great work on the tests."
```

### As PR Author

```bash
# View review comments
gh pr view 123

# Address feedback
# ... make changes ...

/commit
git push

# Respond to comments
gh pr comment 123 \
  --body "Updated per your feedback. PTAL"

# Request re-review
gh pr edit 123 --add-reviewer @reviewer
```

---

## Review Standards

### Required for Approval

1. **All automated checks pass**:
   - Reviewer agent approved
   - CI/CD green
   - No merge conflicts

2. **At least 1 human approval**:
   - From team member
   - Or from code owner

3. **All conversations resolved**:
   - No unaddressed comments
   - Questions answered

### Blocking Issues

**Must fix before merge**:
- ❌ Security vulnerabilities
- ❌ Test failures
- ❌ Coverage below 80%
- ❌ Breaking changes without notice
- ❌ Violates PROJECT.md constraints

**Can merge with follow-up issue**:
- ⚠️ Minor refactoring suggestions
- ⚠️ Documentation improvements
- ⚠️ Performance optimizations
- ⚠️ Additional test cases

---

## Review Best Practices

### For Reviewers

1. **Be timely** - Review within 24 hours
2. **Be specific** - Point to exact lines
3. **Be constructive** - Suggest improvements
4. **Ask questions** - Understand intent
5. **Praise good work** - Positive feedback matters

**Good Review Comment**:
```
Consider using a dictionary here instead of multiple if/else blocks:

```python
STATUS_MESSAGES = {
    'active': 'User is active',
    'inactive': 'User is inactive',
    'pending': 'User is pending',
}
return STATUS_MESSAGES.get(status, 'Unknown status')
```

This would be more maintainable and easier to extend.
```

### For PR Authors

1. **Respond promptly** - Address feedback within 24 hours
2. **Don't take personally** - Reviews improve code quality
3. **Ask clarifying questions** - If feedback unclear
4. **Push back respectfully** - If disagree with suggestion
5. **Thank reviewers** - Appreciate their time

---

## CODEOWNERS Integration

Define automatic reviewers by file:

`.github/CODEOWNERS`:
```
# Default reviewers
* @default-reviewer

# Python code
*.py @python-team

# Frontend
src/frontend/** @frontend-team

# Documentation
docs/** @docs-team

# Security-sensitive
.github/workflows/** @security-team
hooks/security_scan.py @security-team

# Infrastructure
.github/** @devops-team
.mcp/** @devops-team
```

Auto-requests reviews when files changed.

---

## Review Metrics

Track review effectiveness:

```bash
# Average time to first review
gh pr list --state closed --json createdAt,reviewedAt

# Review thoroughness (comments per PR)
gh pr view 123 --json comments | jq '.comments | length'

# Approval rate
gh pr list --state merged --json reviews
```

---

## Troubleshooting

### "Review dismissed after new push"

Configure in Branch Protection:
- ✅ "Dismiss stale pull request approvals when new commits are pushed"

Re-request review:
```bash
gh pr edit 123 --add-reviewer @reviewer
```

### "Can't approve own PR"

Best practice: Require review from someone else

Configure in Branch Protection:
- ✅ "Require review from Code Owners"
- ✅ "Require approvals: 1"

### "Conflicting feedback from reviewers"

1. Discuss in PR comments
2. Tag team lead for decision
3. Reach consensus before proceeding

---

## Quick Reference

```bash
# Review Commands
gh pr checkout N         # Checkout PR
gh pr diff N             # View diff
gh pr review N --approve # Approve
gh pr review N --comment # Comment
gh pr review N --request-changes  # Request changes

# Author Commands
gh pr view N             # View PR and comments
gh pr comment N          # Respond to review
git push                 # Update PR with fixes

# Merge Commands
gh pr merge N --squash   # Merge after approval
```

---

**See also**:
- GitHub Workflow: `docs/GITHUB-WORKFLOW.md`
- PR Automation: `docs/PR-AUTOMATION.md`
- Contributing: `docs/CONTRIBUTING.md`
