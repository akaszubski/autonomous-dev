# Git Automation Control

**Last Updated**: 2025-11-09
**Related Issue**: [#58 - Automatic Git Operations](https://github.com/akaszubski/autonomous-dev/issues/58)

This document describes the automatic git operations feature that can be optionally enabled after `/auto-implement` completes.

## Overview

Automatic git operations (commit, push, PR creation) provide a seamless end-to-end workflow for feature implementation. This feature is **disabled by default** for safety and requires explicit opt-in via environment variables.

## Status

**Optional feature** - Disabled by default for safety

## Environment Variables

Configure git automation by setting these variables in your `.env` file:

```bash
# Master switch - enables automatic git operations after /auto-implement
AUTO_GIT_ENABLED=true        # Default: false

# Enable automatic push to remote (requires AUTO_GIT_ENABLED=true)
AUTO_GIT_PUSH=true           # Default: false

# Enable automatic PR creation (requires AUTO_GIT_ENABLED=true and gh CLI)
AUTO_GIT_PR=true             # Default: false
```

### Environment Variable Details

| Variable | Default | Description | Dependencies |
|----------|---------|-------------|--------------|
| `AUTO_GIT_ENABLED` | `false` | Master switch for all git automation | None |
| `AUTO_GIT_PUSH` | `false` | Enable automatic push to remote | `AUTO_GIT_ENABLED=true` |
| `AUTO_GIT_PR` | `false` | Enable automatic PR creation | `AUTO_GIT_ENABLED=true`, `gh` CLI installed |

## How It Works

The git automation workflow integrates seamlessly with `/auto-implement`:

```
1. /auto-implement completes STEP 6 (parallel validation)
   ↓
2. quality-validator agent completes (last validation agent)
   ↓
3. SubagentStop hook triggers auto_git_workflow.py
   ↓
4. Hook checks consent via environment variables
   ↓ (if enabled)
5. Invoke commit-message-generator agent
   ↓
6. Stage changes and create commit with agent-generated message
   ↓ (if AUTO_GIT_PUSH=true)
7. Push commit to remote
   ↓ (if AUTO_GIT_PR=true)
8. Create pull request with pr-description-generator agent
```

### Workflow Steps

**Step 1-2: Feature Completion**
- `/auto-implement` runs through all 7 agents
- Final validation completes with quality-validator agent

**Step 3: Hook Activation**
- SubagentStop lifecycle hook detects quality-validator completion
- Triggers `auto_git_workflow.py` hook

**Step 4: Consent Check**
- Checks `AUTO_GIT_ENABLED` environment variable
- If disabled, workflow exits gracefully (no git operations)
- If enabled, proceeds with validation checks

**Step 5: Commit Message Generation**
- Invokes `commit-message-generator` agent with workflow context
- Agent analyzes changed files and generates conventional commit message
- Format: `type(scope): description` (follows [Conventional Commits](https://www.conventionalcommits.org/))

**Step 6: Git Commit**
- Stages all changes (`git add .`)
- Creates commit with agent-generated message
- Includes co-authorship footer: `Co-Authored-By: Claude <noreply@anthropic.com>`

**Step 7: Git Push (Optional)**
- Only if `AUTO_GIT_PUSH=true`
- Pushes commit to remote repository
- Uses current branch and upstream tracking

**Step 8: Pull Request Creation (Optional)**
- Only if `AUTO_GIT_PR=true` and `gh` CLI available
- Invokes `pr-description-generator` agent
- Creates GitHub PR with comprehensive description
- Includes summary, test plan, and related issues

### Graceful Degradation

If any prerequisite fails, the workflow provides **manual fallback instructions**:

```bash
# Example fallback instructions if git automation fails:
Git automation failed: git not configured

To commit manually:
  git add .
  git commit -m "feat: implement user authentication"
  git push origin feature-branch
  gh pr create --title "Feature: User Authentication"
```

**Key point**: Feature implementation is still successful even if git operations fail.

## Consent-Based Design

The git automation feature follows a **consent-based design philosophy**:

### Safety Principles

1. **Disabled by default** - No behavior change without explicit opt-in
2. **Validates all prerequisites** - Checks git config, remote, credentials before operations
3. **Non-blocking** - Git automation failures don't affect feature completion
4. **Always provides fallback** - Manual instructions if automation fails
5. **Audited operations** - All git operations logged to security audit

### Why Consent-Based?

- **User control**: Users decide when to enable automation
- **Repository safety**: No accidental commits or pushes
- **Flexibility**: Can enable commit but not push (staged rollout)
- **Transparency**: Clear environment variables, not hidden settings

## Security

All git operations follow security best practices:

### Path Validation
- Uses `security_utils.validate_path()` for all file paths
- Prevents path traversal attacks (CWE-22)
- Rejects symlinks outside whitelist (CWE-59)

### Credential Safety
- **Never logs credentials** - API keys, passwords excluded from logs
- **No credential exposure** - Subprocess calls prevent injection attacks
- **Safe JSON parsing** - No arbitrary code execution

### Audit Logging
- All operations logged to `logs/security_audit.log`
- Includes: operation type, timestamp, success/failure, files affected
- Audit log format: JSON (machine-readable)

### Subprocess Safety
- All git commands use subprocess with argument lists (not shell strings)
- Prevents command injection attacks
- Input validation for all user-provided data (branch names, commit messages)

## Implementation Files

### Hook
- **File**: `plugins/autonomous-dev/hooks/auto_git_workflow.py` (588 lines)
- **Lifecycle**: SubagentStop (triggers after quality-validator completes)
- **Responsibility**: Detect feature completion, check consent, invoke git integration

### Core Library
- **File**: `plugins/autonomous-dev/lib/auto_implement_git_integration.py` (1,466 lines)
- **Main Entry Point**: `execute_step8_git_operations()` - Orchestrates entire git workflow

### Key Functions

**Consent and Validation**:
- `check_consent_via_env()` - Check AUTO_GIT_ENABLED environment variable
- `validate_git_state()` - Verify git repository, clean working directory
- `validate_branch_name()` - Ensure valid branch name
- `validate_commit_message()` - Validate conventional commit format
- `check_git_credentials()` - Verify git configured (user.name, user.email)
- `check_git_available()` - Check git command available
- `check_gh_available()` - Check gh CLI installed (for PR creation)

**Git Operations**:
- `create_commit_with_agent_message()` - Generate and create commit
- `push_and_create_pr()` - Push to remote and optionally create PR
- `validate_agent_output()` - Validate commit-message-generator output

### Agent Integration

**commit-message-generator**:
- Invoked with workflow context (feature description, changed files)
- Generates conventional commit message
- Format: `type(scope): description\n\nBody\n\nCo-Authored-By: Claude <noreply@anthropic.com>`

**pr-description-generator**:
- Invoked with commit history and feature context
- Generates comprehensive PR description
- Includes: summary, test plan, breaking changes, related issues

## Usage Examples

### Enable Commit Only

Create `.env` file in project root:

```bash
# Enable automatic commit (but not push or PR)
AUTO_GIT_ENABLED=true
AUTO_GIT_PUSH=false
AUTO_GIT_PR=false
```

Run feature implementation:
```bash
/auto-implement "add user authentication with JWT"
```

Result: Feature implemented and committed locally (not pushed).

---

### Enable Full Automation

```bash
# Enable automatic commit, push, and PR creation
AUTO_GIT_ENABLED=true
AUTO_GIT_PUSH=true
AUTO_GIT_PR=true
```

Run feature implementation:
```bash
/auto-implement "add rate limiting to API endpoints"
```

Result: Feature implemented, committed, pushed, and PR created automatically.

---

### Disable All Automation

```bash
# Disable all git automation (default behavior)
AUTO_GIT_ENABLED=false
```

Or simply don't set any environment variables (same effect).

Result: Feature implemented, no git operations performed (manual commit required).

## Troubleshooting

### Git automation not working

**Symptoms**: Feature completes, but no commit created

**Diagnosis**:
```bash
# Check environment variables
cat .env | grep AUTO_GIT
```

**Solutions**:
- Ensure `AUTO_GIT_ENABLED=true` in `.env` file
- Verify `.env` file in project root (same directory as `.claude/`)
- Check git configured: `git config user.name` and `git config user.email`

---

### Commit created but not pushed

**Symptoms**: Commit appears locally, but not on remote

**Diagnosis**:
```bash
# Check push setting
grep AUTO_GIT_PUSH .env
```

**Solutions**:
- Set `AUTO_GIT_PUSH=true` in `.env` file
- Verify remote configured: `git remote -v`
- Check credentials: `git config credential.helper`

---

### PR not created

**Symptoms**: Commit pushed, but PR not created

**Diagnosis**:
```bash
# Check PR setting
grep AUTO_GIT_PR .env

# Check gh CLI
gh --version
```

**Solutions**:
- Set `AUTO_GIT_PR=true` in `.env` file
- Install gh CLI: `brew install gh` (Mac) or see [GitHub CLI](https://cli.github.com/)
- Authenticate: `gh auth login`

---

### Agent-generated commit message rejected

**Symptoms**: Error: "Commit message doesn't follow conventional commits"

**Diagnosis**: Check audit log for validation errors:
```bash
cat logs/security_audit.log | grep "commit_message_validation"
```

**Solutions**:
- Agent output usually follows convention; check for edge cases
- Manual override: Disable automation and commit manually
- Report issue: If agent consistently generates invalid messages

## Performance Impact

Git automation adds **minimal overhead** to `/auto-implement` workflow:

| Operation | Time (seconds) |
|-----------|----------------|
| Consent check | < 0.1 |
| Agent invocation (commit-message-generator) | 5-15 |
| Git commit | < 1 |
| Git push | 1-5 (network dependent) |
| PR creation (pr-description-generator) | 10-20 |

**Total overhead**: 15-40 seconds (with full automation enabled)

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Main project documentation
- [LIBRARIES.md](LIBRARIES.md) - Library API reference (includes auto_implement_git_integration.py)
- [GitHub Issue #58](https://github.com/akaszubski/autonomous-dev/issues/58) - Git automation implementation
- [plugins/autonomous-dev/README.md](../plugins/autonomous-dev/README.md) - User guide

## Contributing

Improvements to git automation are welcome! When contributing:

1. **Maintain consent-based design** - Always disabled by default
2. **Add security validation** - Use security_utils for all operations
3. **Audit logging** - Log all git operations to security audit
4. **Graceful degradation** - Provide manual fallback if automation fails
5. **Test coverage** - Add unit tests for new functionality
