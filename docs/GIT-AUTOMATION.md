# Git Automation Control

**Last Updated**: 2025-12-06
**Related Issues**: [#61 - Enable Zero Manual Git Operations by Default](https://github.com/akaszubski/autonomous-dev/issues/61), [#91 - Auto-close GitHub issues after /auto-implement](https://github.com/akaszubski/autonomous-dev/issues/91), [#96 - Fix consent blocking in batch processing](https://github.com/akaszubski/autonomous-dev/issues/96), [#93 - Add auto-commit to batch workflow](https://github.com/akaszubski/autonomous-dev/issues/93)

This document describes the automatic git operations feature for seamless end-to-end workflow after `/auto-implement` completes.

## Overview

Automatic git operations (commit, push, PR creation, issue closing) provide a seamless end-to-end workflow for feature implementation. This feature is **enabled by default** as of v3.12.0 (opt-out model with first-run consent). Issue closing was added in v3.22.0 (Issue #91).

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
   ↓ (if git push succeeded)
8.5. Auto-close GitHub issue (if issue number found in feature request)
     - Extract issue number from command args
     - Prompt user for consent (interactive)
     - Close issue via gh CLI with workflow summary
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

**Step 8.5: Auto-Close GitHub Issue (Optional - v3.22.0, Issue #91)**
- Runs after git push succeeds (Step 7)
- Only if issue number found in feature request
- Features:
  - **Issue Number Extraction**: Flexible pattern matching
    - Patterns: `"issue #8"`, `"#8"`, `"Issue 8"` (case-insensitive)
    - First occurrence if multiple mentions
  - **User Consent Prompt**: Interactive - `"Close issue #8 (title)? [yes/no]:`
    - User says "yes"/"y": Proceed with closing
    - User says "no"/"n": Skip closing (feature still successful)
    - User presses Ctrl+C: Cancel entire workflow
  - **Issue State Validation**: Validates via `gh` CLI
    - Issue exists (not 404)
    - Issue is currently open (can close)
    - User has permission to close
  - **Close Summary**: Markdown summary with workflow metadata
    - All agents passed (researcher, planner, test-master, etc.)
    - Pull request URL
    - Commit hash
    - Files changed count and names
  - **gh CLI Operation**: Safe subprocess call
    - Security: CWE-20 (validates issue number 1-999999)
    - Security: CWE-78 (subprocess list args, shell=False)
    - Security: CWE-117 (sanitizes file names in summary)
    - Audit logs to security_audit.log
  - **Error Handling**: Graceful degradation
    - Issue already closed: Skip (idempotent)
    - Issue not found: Skip with warning
    - gh CLI unavailable: Skip with manual instructions
    - Network error: Skip with retry instructions
    - All failures non-blocking (feature still successful)

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

## Batch Workflow Integration (NEW in v3.36.0 - Issue #93)

Per-feature git automation is now integrated into `/batch-implement` workflow. Each feature automatically commits with conventional commit messages when batch processing completes.

### Overview

When running `/batch-implement`:

1. **Feature processing**: Standard workflow runs for each feature
2. **Quality checks pass**: All validation agents complete
3. **Git automation triggers**: `execute_git_workflow()` invoked with `in_batch_mode=True`
4. **Git operations recorded**: Results saved in batch_state.json for audit trail
5. **Batch continues**: Next feature begins processing

### How It Works

The batch mode integration differs from `/auto-implement` in key ways:

**Similarities**:
- Same git operations: commit, push, PR creation
- Same environment variables: `AUTO_GIT_ENABLED`, `AUTO_GIT_PUSH`, `AUTO_GIT_PR`
- Same commit message format: Conventional commits with co-authorship
- Same error handling: Non-blocking failures with detailed logging

**Differences**:
- **No interactive prompts**: Batch mode skips first-run consent prompt
- **Environment variables only**: All decisions via `.env` file (no stdin)
- **Audit trail**: Git operations tracked in batch_state.json for each feature
- **Per-feature commits**: One commit per completed feature (not per-step)

### Batch State Structure

The `batch_state.json` now includes a `git_operations` field tracking per-feature git results:

```json
{
  "batch_id": "batch-20251206-001",
  "current_index": 2,
  "completed": ["feature1", "feature2", "feature3"],
  "failed": [],
  "git_operations": {
    "0": {
      "commit": {
        "success": true,
        "timestamp": "2025-12-06T10:00:00Z",
        "sha": "abc123def456",
        "branch": "feature/auth"
      },
      "push": {
        "success": true,
        "timestamp": "2025-12-06T10:00:15Z",
        "branch": "feature/auth",
        "remote": "origin"
      },
      "pr": {
        "success": true,
        "timestamp": "2025-12-06T10:00:30Z",
        "number": 42,
        "url": "https://github.com/user/repo/pull/42"
      }
    },
    "1": {
      "commit": {
        "success": true,
        "timestamp": "2025-12-06T10:15:00Z",
        "sha": "def456abc123",
        "branch": "feature/jwt"
      },
      "push": {
        "success": false,
        "timestamp": "2025-12-06T10:15:15Z",
        "error": "Network timeout"
      }
    },
    "2": {
      "commit": {
        "success": false,
        "timestamp": "2025-12-06T10:30:00Z",
        "error": "Merge conflict in auth.py"
      }
    }
  }
}
```

**Structure**:
- `git_operations[feature_index][operation_type]` contains operation results
- Operation types: `commit`, `push`, `pr`
- Each operation includes: `success`, `timestamp`, operation-specific metadata

### Git Operation Recording API

To record git operations during batch processing, use:

```python
from batch_state_manager import record_git_operation

# Record successful commit
state = record_git_operation(
    state=batch_state,
    feature_index=0,
    operation='commit',
    success=True,
    commit_sha='abc123def456',
    branch='feature/auth'
)

# Record failed push (with error message)
state = record_git_operation(
    state=batch_state,
    feature_index=1,
    operation='push',
    success=False,
    branch='feature/jwt',
    error_message='Network timeout'
)

# Record successful PR
state = record_git_operation(
    state=batch_state,
    feature_index=0,
    operation='pr',
    success=True,
    pr_number=42,
    pr_url='https://github.com/user/repo/pull/42'
)
```

### Query Git Status

Retrieve git operation status for debugging:

```python
from batch_state_manager import get_feature_git_status

# Get status of all git operations for a feature
status = get_feature_git_status(batch_state, feature_index=0)
# Returns: {
#   'commits': {'success': True, 'sha': 'abc123...'},
#   'pushes': {'success': True},
#   'prs': {'success': True, 'number': 42, 'url': '...'}
# }
```

### Configuration for Batch Mode

Configure git automation for batch processing via `.env`:

```bash
# Enable automatic git operations for all features
AUTO_GIT_ENABLED=true

# Disable push (commits only)
AUTO_GIT_PUSH=false

# Disable PR creation (commits and push only)
AUTO_GIT_PR=false
```

### Behavior in Batch Mode

**With default configuration** (`AUTO_GIT_ENABLED=true`):
- Each feature commits after completion
- Each feature pushes (if `AUTO_GIT_PUSH=true`)
- Each feature creates PR (if `AUTO_GIT_PR=true`)

**With conservative configuration** (`AUTO_GIT_ENABLED=true, AUTO_GIT_PUSH=false`):
- Each feature commits locally
- No push to remote
- Manual push after batch completes: `git push origin <branch>`

**With disabled git** (`AUTO_GIT_ENABLED=false`):
- No git operations
- Manual commit/push required after batch
- Feature implementation still succeeds

### Error Recovery

If a git operation fails during batch:

1. **Commit failure**: Feature marked complete, batch continues
2. **Push failure**: Error recorded, batch continues (manual push later)
3. **PR failure**: Error recorded, batch continues (manual PR later)

All failures are **non-blocking** - batch processing never stops due to git errors.

To check what failed:

```bash
# View failed git operations
cat .claude/batch_state.json | jq '.git_operations[] | select(.commit.success == false)'

# Example: Find all failed pushes
cat .claude/batch_state.json | jq '.git_operations[] | select(.push.success == false)'
```

### See Also

- [docs/BATCH-PROCESSING.md](BATCH-PROCESSING.md) - Batch processing documentation (includes git automation section)
- [GitHub Issue #93](https://github.com/akaszubski/autonomous-dev/issues/93) - Implementation issue
- `plugins/autonomous-dev/lib/batch_state_manager.py` - BatchState.git_operations field
- `plugins/autonomous-dev/lib/auto_implement_git_integration.py` - `execute_git_workflow()` function

---

## Batch Mode Consent Bypass (NEW in v3.35.0 - Issue #96)

For unattended batch processing, consent is automatically resolved via environment variables, preventing interactive prompts from blocking the batch workflow.

### Problem

In `/batch-implement` workflows, if `/auto-implement` shows an interactive consent prompt during the first feature, the entire batch blocks waiting for user input. This defeats the purpose of unattended batch processing.

**Before Issue #96**: Batch processing would hang on first feature's consent prompt, requiring manual intervention to continue.

### Solution

**STEP 5 (Consent Check)** now checks `AUTO_GIT_ENABLED` environment variable BEFORE showing interactive prompt:

```python
# Check consent via environment variables (Issue #96)
consent = check_consent_via_env()

if not consent['enabled']:
    # Skip git operations entirely (no prompt)
    pass
elif consent['enabled']:
    # Auto-proceed with git operations (no prompt)
    pass
else:
    # Show interactive prompt (first-run or env var not set)
    pass
```

### Usage in Batch Processing

Configure `.env` before running batch:

```bash
# Enable automatic git operations for unattended batch
export AUTO_GIT_ENABLED=true

# Or in .env file
echo "AUTO_GIT_ENABLED=true" >> .env

# Then run batch - no prompts, fully unattended
/batch-implement features.txt
```

**Result**: Each feature in the batch:
1. Checks `AUTO_GIT_ENABLED` environment variable
2. Auto-proceeds without prompt (if true)
3. Skips without prompt (if false)
4. No blocking on interactive consent

### Backward Compatibility

- **First run without env var**: Shows interactive consent prompt (stored for future runs)
- **Subsequent runs**: Uses stored preference OR environment variable (env var takes precedence)
- **Explicit override**: Set `AUTO_GIT_ENABLED=false` to disable despite stored preference

### See Also

- [docs/BATCH-PROCESSING.md](BATCH-PROCESSING.md) - Prerequisites for unattended batches
- [GitHub Issue #96](https://github.com/akaszubski/autonomous-dev/issues/96) - Consent blocking fix

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

---

### Issue not auto-closed (v3.22.0+, Issue #91)

**Symptoms**: Feature completes with git automation, but GitHub issue not closed

**Diagnosis**:
```bash
# Check if issue number was detected
# (Should appear in workflow output or in auto_git_workflow.py debug logs)

# Check if gh CLI is installed
gh --version

# Check if you have permission to close the issue
gh issue view <issue-number> --json state
```

**Solutions**:
- **No issue number found**: Ensure feature request includes issue pattern
  - Examples: `"issue #8"`, `"#8"`, `"Issue 8"`
  - Check: `/auto-implement implement issue #8` (must have issue number)
- **User declined consent**: Step 8.5 prompts for consent
  - If you said "no", issue closing is skipped (expected behavior)
  - Re-run /auto-implement with same issue to get prompt again
- **gh CLI not installed**: Issue closing requires gh CLI
  - Install: `brew install gh` (Mac) or [GitHub CLI](https://cli.github.com/)
  - Authenticate: `gh auth login`
- **Issue already closed**: Gracefully skipped (idempotent)
  - Re-opening issue will allow closing again on next /auto-implement
- **Permission error**: You may not have permission to close issue
  - Check: `gh issue view <issue-number>`
  - Solution: Only repo maintainers can close issues (not collaborators)
- **Network error**: Temporary gh API failure
  - Solution: Manual close: `gh issue close <issue-number>`

---

## Performance Impact

Git automation adds **minimal overhead** to `/auto-implement` workflow:

| Operation | Time (seconds) |
|-----------|----------------|
| Consent check | < 0.1 |
| Agent invocation (commit-message-generator) | 5-15 |
| Git commit | < 1 |
| Git push | 1-5 (network dependent) |
| PR creation (pr-description-generator) | 10-20 |
| Issue closing (v3.22.0, Issue #91) | 1-3 (user prompt + gh CLI) |

**Total overhead**: 15-50 seconds (with full automation including issue closing)

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Main project documentation
- [LIBRARIES.md](LIBRARIES.md) - Library API reference (includes auto_implement_git_integration.py and github_issue_closer.py)
- [GitHub Issue #58](https://github.com/akaszubski/autonomous-dev/issues/58) - Git automation implementation
- [GitHub Issue #91](https://github.com/akaszubski/autonomous-dev/issues/91) - Auto-close GitHub issues after /auto-implement
- [plugins/autonomous-dev/README.md](../plugins/autonomous-dev/README.md) - User guide

## Contributing

Improvements to git automation are welcome! When contributing:

1. **Maintain opt-out consent design** - Always enabled by default with first-run warning (v3.12.0+)
2. **Add security validation** - Use security_utils for all operations
3. **Audit logging** - Log all git operations to security audit
4. **Graceful degradation** - Provide manual fallback if automation fails
5. **Test coverage** - Add unit tests for new functionality
6. **User state persistence** - Use `user_state_manager.py` for preference storage
