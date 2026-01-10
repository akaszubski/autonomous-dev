# Git Automation Control

**Last Updated**: 2026-01-09
**Related Issues**: [#61 - Enable Zero Manual Git Operations by Default](https://github.com/akaszubski/autonomous-dev/issues/61), [#91 - Auto-close GitHub issues after /implement](https://github.com/akaszubski/autonomous-dev/issues/91), [#96 - Fix consent blocking in batch processing](https://github.com/akaszubski/autonomous-dev/issues/96), [#93 - Add auto-commit to batch workflow](https://github.com/akaszubski/autonomous-dev/issues/93), [#144 - Consolidate git hooks](https://github.com/akaszubski/autonomous-dev/issues/144), [#167 - Git automation silently fails in user projects](https://github.com/akaszubski/autonomous-dev/issues/167), [#168 - Auto-close GitHub issues after batch-implement push](https://github.com/akaszubski/autonomous-dev/issues/168), [#212 - Resolve duplicate auto_git_workflow.py](https://github.com/akaszubski/autonomous-dev/issues/212)

This document describes the automatic git operations feature for seamless end-to-end workflow after `/implement` completes.

## Deprecation Notice

**auto_git_workflow.py has been archived** (Issue #144, #212)

The original `auto_git_workflow.py` hook has been consolidated into `unified_git_automation.py` for better maintainability. A backward compatibility shim exists at `.claude/hooks/auto_git_workflow.py` (56 lines) that redirects to the unified implementation.

**What this means for you**:
- Git automation continues to work exactly as before
- No configuration changes required
- Environment variables unchanged (AUTO_GIT_ENABLED, AUTO_GIT_PUSH, AUTO_GIT_PR)
- Shim provides seamless backward compatibility

**For developers**:
- The archived `auto_git_workflow.py` logic is now in `unified_git_automation.py`
- See `plugins/autonomous-dev/hooks/archived/README.md` for archival details
- The shim at `.claude/hooks/auto_git_workflow.py` redirects old references to unified hook

**Related Issues**: [#144 (Consolidation)](https://github.com/akaszubski/autonomous-dev/issues/144), [#212 (Duplicate resolution)](https://github.com/akaszubski/autonomous-dev/issues/212)

## Overview

Automatic git operations (commit, push, PR creation, issue closing) provide a seamless end-to-end workflow for feature implementation. This feature is **enabled by default** as of v3.12.0 (opt-out model with first-run consent). Issue closing was added in v3.22.0 (Issue #91).

## Status

**Default Feature** - Enabled by default with first-run consent prompt (opt-out available)

## Environment Variables

Configure git automation by setting these variables in your `.env` file:

```bash
# Master switch - disables automatic git operations after /implement
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

On the **first run** of `/implement`, users see an interactive consent prompt:

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║  🚀 Zero Manual Git Operations (NEW DEFAULT)                ║
║                                                              ║
║  Automatic git operations enabled after /implement:    ║
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

The git automation workflow integrates seamlessly with `/implement`:

```
1. /implement completes STEP 6 (parallel validation)
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
- `/implement` runs through all 8 agents
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

**Step 8.5: Auto-Close GitHub Issue (Optional - v3.22.0 Issue #91 for /implement, v3.46.0 Issue #168 for batch mode)**
- Runs after git push succeeds (Step 7)
- Only if issue number found in feature request or batch state
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

## User Project Support (NEW in v3.45.0+ - Issue #167)

Git automation now works seamlessly in **user projects** (projects outside the autonomous-dev repository) without requiring the plugin directory structure.

### Problem Fixed (Issue #167)

**Before**: Git automation silently failed in user projects because:
- Required `plugins/autonomous-dev/lib/` for path discovery
- Required `docs/sessions/` for session file tracking
- Required active `path_utils` and security library imports
- Errors were silently swallowed with no user-visible logging

**Result**: Users saw no indication that git automation failed, leaving them confused about why commits/PRs weren't created.

### Solution: Graceful Degradation with Verbose Logging

Git automation now:
1. **Detects library availability** - Gracefully falls back if libraries unavailable
2. **Makes session file optional** - Works without `docs/sessions/` directory
3. **Provides verbose logging** - `GIT_AUTOMATION_VERBOSE=true` shows detailed errors
4. **Validates prerequisites** - Checks git config, remote, credentials before operations
5. **Non-blocking failures** - All errors are informational, never block feature completion

### How It Works in User Projects

When git automation runs in a user project:

```
1. Hook starts → tries to find lib directory
   ├─ Found: Use security_utils and path_utils
   ├─ Not found: Use built-in stubs (graceful degradation)

2. Try to get session file path
   ├─ Found: Use for workflow metadata
   ├─ Not found: Continue anyway (session file optional)

3. Validate git prerequisites
   ├─ Git configured: Continue with operations
   ├─ Git not configured: Show manual instructions

4. Execute git operations (commit/push/PR)
   ├─ Success: Feature complete
   ├─ Failure: Show error + manual fallback instructions
```

### Configuration for User Projects

For verbose debugging in user projects, set:

```bash
# Enable detailed logging for git automation
export GIT_AUTOMATION_VERBOSE=true

# Then run feature implementation
/implement "add feature to my project"
```

**Output** (with verbose mode):

```
[2026-01-01 10:15:32] GIT-AUTOMATION INFO: Git automation starting for feature implementation
[2026-01-01 10:15:32] GIT-AUTOMATION INFO: Checking git prerequisites...
[2026-01-01 10:15:32] GIT-AUTOMATION INFO: Git configured: user.name = John Doe
[2026-01-01 10:15:32] GIT-AUTOMATION INFO: Remote origin available
[2026-01-01 10:15:33] GIT-AUTOMATION INFO: Creating commit...
[2026-01-01 10:15:34] GIT-AUTOMATION INFO: Commit created: abc123def456
[2026-01-01 10:15:35] GIT-AUTOMATION INFO: Pushing to origin...
[2026-01-01 10:15:40] GIT-AUTOMATION INFO: Push successful
[2026-01-01 10:15:41] GIT-AUTOMATION INFO: Creating pull request...
[2026-01-01 10:15:50] GIT-AUTOMATION INFO: PR created: https://github.com/user/repo/pull/42
```

**Without verbose mode**: Silent operation (no output unless error occurs)

### Error Handling in User Projects

Common scenarios and handling:

#### Scenario 1: Git Not Configured

**Symptom**: No commit created, no error shown

**Solution**: Enable verbose logging to see the issue

```bash
export GIT_AUTOMATION_VERBOSE=true
/implement "add feature"

# Output shows:
# [2026-01-01 10:15:32] GIT-AUTOMATION WARNING: Git user not configured
# To fix:
git config user.name "Your Name"
git config user.email "your@email.com"
```

#### Scenario 2: No Remote Repository

**Symptom**: Commit created, but no push/PR

**Solution**: Verbose logging shows the issue

```bash
export GIT_AUTOMATION_VERBOSE=true
/implement "add feature"

# Output shows:
# [2026-01-01 10:15:35] GIT-AUTOMATION WARNING: No remote repository found
# To fix:
git remote add origin https://github.com/user/repo.git
```

#### Scenario 3: Libraries Not Available

**Symptom**: Feature completes normally, but no git operations

**Solution**: This is **expected** in user projects outside the autonomous-dev repo

```bash
export GIT_AUTOMATION_VERBOSE=true
/implement "add feature"

# Output shows:
# [2026-01-01 10:15:32] GIT-AUTOMATION INFO: path_utils not available
# [2026-01-01 10:15:32] GIT-AUTOMATION INFO: Using fallback session discovery
# (continued processing with graceful degradation)
```

**Note**: Lack of libraries does NOT prevent git operations. Session file is optional.

### Technical Implementation

The unified_git_automation.py hook uses **progressive enhancement**:

```python
# 1. Try to find library path
lib_dir = find_lib_dir()  # Looks in 3 locations
if lib_dir:
    # Use real security_utils and path_utils
    from security_utils import validate_path, audit_log
    from path_utils import get_session_dir
    HAS_SECURITY_UTILS = True
else:
    # Use stubs with logging
    HAS_SECURITY_UTILS = False
    def validate_path(...): return True  # Accept all (non-blocking)

# 2. Try to get session file (optional)
session_file = get_session_file_path()  # Returns None if not found
if session_file:
    # Use session metadata
else:
    # Continue anyway (session file is optional)
    pass

# 3. Execute git operations (works with or without session file)
result = execute_git_workflow(
    session_file=session_file,  # Can be None
    consent=consent
)
```

**Key Points**:
- **Library discovery**: Searches in 3 locations (relative, project root, global)
- **Security stubs**: If libraries unavailable, security validation becomes pass-through (no exception)
- **Session file optional**: Hook works with or without session file
- **Clear logging**: `GIT_AUTOMATION_VERBOSE` environment variable enables detailed output
- **Non-blocking**: All errors logged but never abort the workflow

### When to Use Verbose Mode

Enable `GIT_AUTOMATION_VERBOSE=true` when:
- Setting up autonomous-dev in a new user project
- Debugging why git operations aren't happening
- Troubleshooting git configuration issues
- Reporting bugs related to git automation

**Disable verbose mode** (default):
- Normal operation - too verbose for daily use
- CI/CD pipelines - keep logs clean
- Batch processing - one log per feature

### See Also

- [docs/GIT-AUTOMATION.md](GIT-AUTOMATION.md) - This file
- `plugins/autonomous-dev/hooks/unified_git_automation.py` - Implementation (Issue #167)
- `plugins/autonomous-dev/lib/auto_implement_git_integration.py` - Git integration library
- [GitHub Issue #167](https://github.com/akaszubski/autonomous-dev/issues/167) - Silent failures in user projects

## Batch Mode Issue Auto-Close (NEW in v3.46.0 - Issue #168)

**Automatic GitHub issue closing after batch feature completion** - When processing multiple features with `/implement --batch`, each completed feature's associated GitHub issue is automatically closed after push succeeds.

### Overview

Issue auto-close in batch mode provides:
- **Automatic issue extraction**: From feature descriptions or `--issues` list
- **Batch-mode operation**: No interactive prompts (non-blocking)
- **Smart consent**: Reuses `AUTO_GIT_ENABLED` (same as commit/push/PR)
- **Safety features**: Circuit breaker after 5 consecutive failures
- **Idempotent**: Already-closed issues don't cause errors
- **Non-blocking**: Failures don't stop batch processing

### How It Works

For each feature in a batch:

1. **Feature completes** - All tests pass, docs updated, quality checks done
2. **Git commit**: Conventional commit created (Issue #93)
3. **Git push**: Commit pushed to remote (if enabled)
4. **Issue extraction** (NEW): Extract issue number from feature or batch state
5. **Issue close** (NEW): Close GitHub issue with summary comment (if enabled and number found)
6. **State update**: Record result in `batch_state.json` for audit trail

### Configuration

Issue auto-close in batch mode uses the same consent mechanism as commit/push/PR:

```bash
# .env file (project root)
AUTO_GIT_ENABLED=true   # Master switch - enables all git ops including issue close
AUTO_GIT_PUSH=true      # Enable push (required before issue close)
```

**Note**: Issue close only runs after successful push (STEP 7 above). If `AUTO_GIT_PUSH=false`, issue close is skipped.

### Batch State Structure

Issue close results are stored in batch state:

```json
{
  "batch_id": "batch-20251206-001",
  "git_operations": {
    "0": {
      "commit": {"success": true, "sha": "abc123..."},
      "push": {"success": true},
      "issue_close": {
        "success": true,
        "issue_number": 72,
        "message": "Issue #72 closed successfully",
        "timestamp": "2025-12-06T10:00:45Z"
      }
    },
    "1": {
      "commit": {"success": true, "sha": "def456..."},
      "push": {"success": true},
      "issue_close": {
        "success": false,
        "issue_number": 73,
        "error": "Issue already closed",
        "reason": null,
        "timestamp": "2025-12-06T10:15:30Z"
      }
    },
    "2": {
      "commit": {"success": true, "sha": "ghi789..."},
      "push": {"success": true},
      "issue_close": {
        "success": false,
        "skipped": true,
        "issue_number": null,
        "reason": "No issue number found for feature",
        "timestamp": "2025-12-06T10:30:15Z"
      }
    }
  }
}
```

### Issue Number Extraction

The system extracts issue numbers from multiple sources in order:

1. **Issue numbers list** (for `--issues` flag): Direct mapping from command line
   ```bash
   /implement --batch --issues 72 73 74
   # Feature 0 → Issue #72
   # Feature 1 → Issue #73
   # Feature 2 → Issue #74
   ```

2. **Feature text** (for file or fallback): Pattern matching
   ```
   Add JWT validation (fixes #72)      # Extracts: 72
   Implement password reset closes #73 # Extracts: 73
   Related issue #74                   # Extracts: 74
   Create new feature GH-75            # Extracts: 75
   ```

   **Patterns matched** (case-insensitive):
   - `closes #123`, `close #123`
   - `fixes #123`, `fix #123`
   - `resolves #123`, `resolve #123`
   - `GH-123`
   - `issue #123`
   - `issue 123`
   - `#123` (last resort)

### Error Handling

Issue close failures are **non-blocking** - batch continues:

| Error | Behavior | Impact |
|-------|----------|--------|
| Issue not found | Logged warning | Batch continues |
| Issue already closed | Idempotent (success) | Batch continues |
| gh CLI unavailable | Logged warning | Batch continues |
| Network timeout | Logged failure | Circuit breaker +1 |
| No issue number | Logged skip | Batch continues |
| Invalid issue number | Logged error | Batch continues |

**Circuit Breaker**: After 5 consecutive failures across all features, issue close is disabled with warning:

```
[WARNING] Issue close circuit breaker triggered after 5 consecutive failures
[INFO] Skipping issue close for remaining features
[ACTION] Fix the issue and manually close issues: gh issue close 73 74 75
```

### Debugging

Query issue close results in batch state:

```bash
# View successful closures
cat .claude/batch_state.json | jq '.git_operations[] | select(.issue_close.success == true)'

# View failed closures
cat .claude/batch_state.json | jq '.git_operations[] | select(.issue_close.success == false)'

# View skipped closures (no issue number found)
cat .claude/batch_state.json | jq '.git_operations[] | select(.issue_close.skipped == true)'

# View all issue close results
cat .claude/batch_state.json | jq '.git_operations[].issue_close'
```

Check audit log for detailed issue close operations:

```bash
# View issue close audit entries
grep "batch_issue_close" logs/security_audit.log
```

### Examples

**Example 1: Batch with --issues flag**

```bash
/implement --batch --issues 72 73 74
```

Workflow:
```
Feature 0 (Issue #72): "Add JWT token validation"
  ├─ Commit: ✓
  ├─ Push: ✓
  └─ Issue close: ✓ Closed #72

Feature 1 (Issue #73): "Implement password reset"
  ├─ Commit: ✓
  ├─ Push: ✓
  └─ Issue close: ✓ Closed #73

Feature 2 (Issue #74): "Add email notifications"
  ├─ Commit: ✓
  ├─ Push: ✓
  └─ Issue close: ✓ Closed #74
```

**Example 2: Batch with inline references**

```text
# features.txt
Add JWT validation (fixes #72)
Implement password reset (closes #73)
Add rate limiting
```

```bash
/implement --batch features.txt
```

Workflow:
```
Feature 0: "Add JWT validation (fixes #72)"
  ├─ Commit: ✓
  ├─ Push: ✓
  └─ Issue close: ✓ Extracted #72, closed

Feature 1: "Implement password reset (closes #73)"
  ├─ Commit: ✓
  ├─ Push: ✓
  └─ Issue close: ✓ Extracted #73, closed

Feature 2: "Add rate limiting"
  ├─ Commit: ✓
  ├─ Push: ✓
  └─ Issue close: ⊘ No issue number found, skipped
```

**Example 3: Mixed success/failure**

```bash
/implement --batch --issues 72 73 74
```

Workflow:
```
Feature 0: Issue #72
  ├─ Commit: ✓
  ├─ Push: ✓
  └─ Issue close: ✓ Closed successfully

Feature 1: Issue #73
  ├─ Commit: ✓
  ├─ Push: ✓
  └─ Issue close: ✗ Already closed (idempotent → success)

Feature 2: Issue #74
  ├─ Commit: ✓
  ├─ Push: ✓
  └─ Issue close: ✗ gh CLI not found
     [Batch continues - non-blocking]
```

### API Usage

For custom batch workflows using the library:

```python
from batch_issue_closer import (
    should_auto_close_issues,
    get_issue_number_for_feature,
    close_batch_feature_issue,
    handle_close_failure,
)

# Check if auto-close enabled
if should_auto_close_issues():
    # For each completed feature
    for feature_index in completed_features:
        # Extract issue number
        issue_number = get_issue_number_for_feature(state, feature_index)

        if issue_number:
            # Close issue
            result = close_batch_feature_issue(
                state=state,
                feature_index=feature_index,
                commit_sha=commit_sha,
                branch=branch,
                state_file=batch_state_file,
            )

            if result['success']:
                print(f"Issue #{issue_number} closed")
            elif result['skipped']:
                print(f"Skipped: {result['reason']}")
            else:
                # Handle non-blocking failure
                should_stop = handle_close_failure(consecutive_failures)
                if should_stop:
                    print("Circuit breaker triggered")
                    break
```

### See Also

- [docs/BATCH-PROCESSING.md](BATCH-PROCESSING.md) - Batch processing documentation with Issue Auto-Close section
- `plugins/autonomous-dev/lib/batch_issue_closer.py` - Implementation (Issue #168)
- [GitHub Issue #168](https://github.com/akaszubski/autonomous-dev/issues/168) - Auto-close GitHub issues after batch-implement push

---

## Batch Workflow Integration (NEW in v3.36.0 - Issue #93)

Per-feature git automation is now integrated into `/implement --batch` workflow. Each feature automatically commits with conventional commit messages when batch processing completes.

### Overview

When running `/implement --batch`:

1. **Feature processing**: Standard workflow runs for each feature
2. **Quality checks pass**: All validation agents complete
3. **Git automation triggers**: `execute_git_workflow()` invoked with `in_batch_mode=True`
4. **Git operations recorded**: Results saved in batch_state.json for audit trail
5. **Batch continues**: Next feature begins processing

### How It Works

The batch mode integration differs from `/implement` in key ways:

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

In `/implement --batch` workflows, if `/implement` shows an interactive consent prompt during the first feature, the entire batch blocks waiting for user input. This defeats the purpose of unattended batch processing.

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
/implement --batch features.txt
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
2. **First-run consent** - Interactive prompt on first `/implement` run
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
/implement "add user authentication with JWT"
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
/implement "add rate limiting to API endpoints"
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
  - Check: `/implement implement issue #8` (must have issue number)
- **User declined consent**: Step 8.5 prompts for consent
  - If you said "no", issue closing is skipped (expected behavior)
  - Re-run /implement with same issue to get prompt again
- **gh CLI not installed**: Issue closing requires gh CLI
  - Install: `brew install gh` (Mac) or [GitHub CLI](https://cli.github.com/)
  - Authenticate: `gh auth login`
- **Issue already closed**: Gracefully skipped (idempotent)
  - Re-opening issue will allow closing again on next /implement
- **Permission error**: You may not have permission to close issue
  - Check: `gh issue view <issue-number>`
  - Solution: Only repo maintainers can close issues (not collaborators)
- **Network error**: Temporary gh API failure
  - Solution: Manual close: `gh issue close <issue-number>`

---

## Performance Impact

Git automation adds **minimal overhead** to `/implement` workflow:

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
- [GitHub Issue #91](https://github.com/akaszubski/autonomous-dev/issues/91) - Auto-close GitHub issues after /implement
- [README.md](../README.md) - User guide

## Contributing

Improvements to git automation are welcome! When contributing:

1. **Maintain opt-out consent design** - Always enabled by default with first-run warning (v3.12.0+)
2. **Add security validation** - Use security_utils for all operations
3. **Audit logging** - Log all git operations to security audit
4. **Graceful degradation** - Provide manual fallback if automation fails
5. **Test coverage** - Add unit tests for new functionality
6. **User state persistence** - Use `user_state_manager.py` for preference storage
