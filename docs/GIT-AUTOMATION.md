# Git Automation Control

**Last Updated**: 2025-11-11
**Related Issue**: [#61 - Enable Zero Manual Git Operations by Default](https://github.com/akaszubski/autonomous-dev/issues/61)

This document describes the automatic git operations feature for seamless end-to-end workflow after `/auto-implement` completes.

## Overview

Automatic git operations (commit, push, PR creation) provide a seamless end-to-end workflow for feature implementation. This feature is **enabled by default** as of v3.12.0 (opt-out model with first-run consent).

## Status

**Default Feature** - Enabled by default with first-run consent prompt (opt-out available)

## Environment Variables

Configure git automation by setting these variables in your `.env` file:

```bash
# Master switch - disables automatic git operations after /auto-implement
AUTO_GIT_ENABLED=false       # Default: true (enabled by default, opt-out)

# Disable automatic push to remote (requires AUTO_GIT_ENABLED=true)
AUTO_GIT_PUSH=false          # Default: true (enabled by default, opt-out)

# Disable automatic PR creation (requires AUTO_GIT_ENABLED=true and gh CLI)
AUTO_GIT_PR=false            # Default: true (enabled by default, opt-out)
```

### Environment Variable Details

| Variable | Default | Description | Dependencies |
|----------|---------|-------------|--------------|
| `AUTO_GIT_ENABLED` | `true` | Master switch for all git automation | None |
| `AUTO_GIT_PUSH` | `true` | Enable automatic push to remote | `AUTO_GIT_ENABLED=true` |
| `AUTO_GIT_PR` | `true` | Enable automatic PR creation | `AUTO_GIT_ENABLED=true`, `gh` CLI installed |

### First-Run Consent (v3.12.0+)

On the **first run** of `/auto-implement`, users see an interactive consent prompt:

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║  🚀 Zero Manual Git Operations (NEW DEFAULT)                ║
║                                                              ║
║  Automatic git operations enabled after /auto-implement:    ║
║                                                              ║
║    ✓ automatic commit with conventional commit message      ║
║    ✓ automatic push to remote                               ║
║    ✓ automatic pull request creation                        ║
║                                                              ║
║  HOW TO OPT OUT:                                            ║
║                                                              ║
║  Add to .env file:                                          ║
║    AUTO_GIT_ENABLED=false                                   ║
║                                                              ║
║  Or disable specific operations:                            ║
║    AUTO_GIT_PUSH=false   # Disable push                     ║
║    AUTO_GIT_PR=false     # Disable PR creation              ║
║                                                              ║
║  See docs/GIT-AUTOMATION.md for details                     ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

Do you want to enable automatic git operations? (Y/n):
```

- **Default**: Yes (pressing Enter accepts)
- **User choice recorded**: Stored in `~/.autonomous-dev/user_state.json`
- **Non-interactive mode**: Skips prompt (CI/CD environments)

### Opt-Out Model

**To disable all git automation**, add to `.env`:

```bash
AUTO_GIT_ENABLED=false
```

**To disable specific operations**, add to `.env`:

```bash
# Enable commit but not push or PR
AUTO_GIT_ENABLED=true
AUTO_GIT_PUSH=false
AUTO_GIT_PR=false
```

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
- On first run: displays interactive consent prompt (v3.12.0+)
- Checks `AUTO_GIT_ENABLED` environment variable (default: true)
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

## Opt-Out Consent Design (v3.12.0+)

The git automation feature follows an **opt-out consent design** with first-run awareness:

### Design Philosophy

1. **Enabled by default** - Seamless zero-manual-git-operations workflow out of the box
2. **First-run consent** - Interactive prompt on first `/auto-implement` run
3. **User state persistence** - Consent choice stored in `~/.autonomous-dev/user_state.json`
4. **Environment override** - `.env` variables override user state preferences
5. **Validates all prerequisites** - Checks git config, remote, credentials before operations
6. **Non-blocking** - Git automation failures don't affect feature completion
7. **Always provides fallback** - Manual instructions if automation fails
8. **Audited operations** - All git operations logged to security audit

### Why Opt-Out Model?

- **Seamless workflow**: Zero manual git operations by default (matches modern expectations)
- **Informed consent**: First-run warning educates users about behavior
- **Easy opt-out**: Simple `.env` file configuration to disable
- **User control**: Can opt-out entirely or disable specific operations (push/PR)
- **Repository safety**: Validates git state before all operations
- **Flexibility**: Can enable commit but not push (staged rollout)
- **Transparency**: Clear environment variables, not hidden settings

### User State Management

**State File**: `~/.autonomous-dev/user_state.json`

**Structure**:
```json
{
  "first_run_complete": true,
  "preferences": {
    "auto_git_enabled": true
  },
  "version": "1.0"
}
```

**Priority**: Environment variables (`.env`) > User state file > Defaults (true)

**Libraries**:
- `plugins/autonomous-dev/lib/user_state_manager.py` - State persistence
- `plugins/autonomous-dev/lib/first_run_warning.py` - Interactive consent prompt

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

### Default Behavior (Full Automation)

By default, git automation is **enabled** (v3.12.0+):

```bash
# No .env configuration needed - full automation enabled by default
```

Run feature implementation:
```bash
/auto-implement "add user authentication with JWT"
```

Result: Feature implemented, committed, pushed, and PR created automatically.

---

### Enable Commit Only (Disable Push/PR)

Create `.env` file in project root:

```bash
# Enable automatic commit (but not push or PR)
AUTO_GIT_ENABLED=true
AUTO_GIT_PUSH=false
AUTO_GIT_PR=false
```

Run feature implementation:
```bash
/auto-implement "add rate limiting to API endpoints"
```

Result: Feature implemented and committed locally (not pushed).

---

### Disable All Automation (Opt-Out)

```bash
# Disable all git automation (opt-out)
AUTO_GIT_ENABLED=false
```

Result: Feature implemented, no git operations performed (manual commit required).

## Troubleshooting

### Git automation not working

**Symptoms**: Feature completes, but no commit created

**Diagnosis**:
```bash
# Check environment variables (if configured)
cat .env | grep AUTO_GIT

# Check user state
cat ~/.autonomous-dev/user_state.json
```

**Solutions**:
- Default is **enabled** (v3.12.0+) - no configuration needed
- If you opted out on first run, edit `~/.autonomous-dev/user_state.json` and set `"auto_git_enabled": true`
- If you set `AUTO_GIT_ENABLED=false` in `.env`, remove it or set to `true`
- Verify `.env` file in project root (same directory as `.claude/`) if configured
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

1. **Maintain opt-out consent design** - Always enabled by default with first-run warning (v3.12.0+)
2. **Add security validation** - Use security_utils for all operations
3. **Audit logging** - Log all git operations to security audit
4. **Graceful degradation** - Provide manual fallback if automation fails
5. **Test coverage** - Add unit tests for new functionality
6. **User state persistence** - Use `user_state_manager.py` for preference storage
