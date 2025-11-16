# Git Operations API Specification

**Date**: 2025-11-04
**Source**: Test-driven design from test files
**Status**: Specification derived from TDD tests

This document specifies the expected API for `git_operations.py` based on the test suite.

---

## Module: `plugins/autonomous-dev/lib/git_operations.py`

### Core Validation Functions

#### `validate_git_repo() -> Tuple[bool, str]`

Validates if current directory is a git repository.

**Returns:**
- `(True, '')` - Valid git repository
- `(False, error_message)` - Not a git repository or git not installed

**Implementation Notes:**
- Use `git rev-parse --git-dir`
- Handle `FileNotFoundError` (git not installed)
- Handle `CalledProcessError` (not a git repo)
- Handle `PermissionError`

**Example:**
```python
is_valid, error = validate_git_repo()
if not is_valid:
    print(f"Error: {error}")
    return
```

---

#### `check_git_config() -> Tuple[bool, str]`

Validates that git user.name and user.email are configured.

**Returns:**
- `(True, '')` - Both user.name and user.email are set
- `(False, error_message)` - One or both config values missing

**Implementation Notes:**
- Use `git config user.name` and `git config user.email`
- Return error message indicating which config is missing
- Both must be set for success

**Example:**
```python
is_configured, error = check_git_config()
if not is_configured:
    print(f"Git config error: {error}")
    print("Run: git config --global user.name 'Your Name'")
    print("Run: git config --global user.email 'your@email.com'")
```

---

#### `detect_merge_conflict() -> Tuple[bool, List[str]]`

Detects if there are unmerged paths (merge conflicts).

**Returns:**
- `(False, [])` - No conflicts
- `(True, ['file1.py', 'file2.py'])` - Conflicts in listed files

**Implementation Notes:**
- Use `git status --porcelain`
- Look for "UU" or "AA" or "DD" status codes (unmerged)
- Parse output to extract conflicted file paths
- Return empty list if git error (fail safe)

**Example:**
```python
has_conflict, files = detect_merge_conflict()
if has_conflict:
    print(f"Merge conflicts in: {', '.join(files)}")
    print("Resolve conflicts before committing")
```

---

#### `is_detached_head() -> bool`

Checks if repository is in detached HEAD state.

**Returns:**
- `False` - On a branch
- `True` - In detached HEAD state or error (fail safe)

**Implementation Notes:**
- Use `git symbolic-ref -q HEAD`
- Returns 0 if on branch, 1 if detached
- Default to True on error (safe state)

**Example:**
```python
if is_detached_head():
    print("Warning: You are in detached HEAD state")
    print("Create a branch with: git checkout -b <branch-name>")
```

---

#### `has_uncommitted_changes() -> bool`

Checks if there are uncommitted changes in working tree.

**Returns:**
- `False` - Working tree clean
- `True` - Uncommitted changes exist or error (fail safe)

**Implementation Notes:**
- Use `git status --porcelain`
- Any output means changes exist
- Default to True on error (safe state)

**Example:**
```python
if not has_uncommitted_changes():
    print("Nothing to commit, working tree clean")
```

---

### Git Operations Functions

#### `stage_all_changes() -> Tuple[bool, str]`

Stages all changes in the working tree.

**Returns:**
- `(True, '')` - Staging succeeded
- `(False, error_message)` - Staging failed

**Implementation Notes:**
- Use `git add .`
- Succeeds even if nothing to add
- Handle permission errors
- Handle git errors

**Example:**
```python
success, error = stage_all_changes()
if not success:
    print(f"Failed to stage changes: {error}")
```

---

#### `commit_changes(message: str) -> Tuple[bool, str, str]`

Creates a git commit with the given message.

**Returns:**
- `(True, commit_sha, '')` - Commit succeeded
- `(False, '', error_message)` - Commit failed

**Implementation Notes:**
- Validate message is not empty before calling git
- Use `git commit -m "message"`
- Parse commit SHA from output (e.g., "[main abc1234]")
- Handle "nothing to commit" gracefully
- Handle missing git config
- Support multiline messages

**Example:**
```python
success, sha, error = commit_changes('feat: add new feature')
if success:
    print(f"Committed: {sha}")
else:
    print(f"Commit failed: {error}")
```

---

#### `get_remote_name() -> str`

Gets the name of the first git remote (usually 'origin').

**Returns:**
- `'origin'` - Remote name (or first remote if multiple)
- `''` - No remote configured or error

**Implementation Notes:**
- Use `git remote`
- Return first line of output
- Return empty string on error or no output
- Common remote names: origin, upstream

**Example:**
```python
remote = get_remote_name()
if not remote:
    print("No remote configured")
    print("Add remote: git remote add origin <url>")
```

---

#### `push_to_remote(branch: str, remote: str = 'origin', set_upstream: bool = False, timeout: int = 30) -> Tuple[bool, str]`

Pushes commits to remote repository.

**Parameters:**
- `branch` - Branch name to push
- `remote` - Remote name (default: 'origin')
- `set_upstream` - Use -u flag for new branches (default: False)
- `timeout` - Network timeout in seconds (default: 30)

**Returns:**
- `(True, '')` - Push succeeded
- `(False, error_message)` - Push failed

**Implementation Notes:**
- Use `git push <remote> <branch>` or `git push -u <remote> <branch>`
- Handle `TimeoutExpired` (network timeout)
- Handle `CalledProcessError` (rejected, protected branch, permission denied)
- Parse stderr for specific error messages

**Example:**
```python
success, error = push_to_remote('main', 'origin')
if not success:
    if 'protected' in error.lower():
        print("Cannot push to protected branch")
    elif 'timeout' in error.lower():
        print("Network timeout - try again")
    else:
        print(f"Push failed: {error}")
```

---

#### `create_feature_branch(branch_name: str) -> Tuple[bool, str, str]`

Creates a new feature branch.

**Parameters:**
- `branch_name` - Name for the new branch

**Returns:**
- `(True, branch_name, '')` - Branch created
- `(False, '', error_message)` - Branch creation failed

**Implementation Notes:**
- Use `git checkout -b <branch_name>`
- Handle "already exists" error
- Handle "not a valid branch name" error
- Branch name validation happens in git command

**Example:**
```python
success, branch, error = create_feature_branch('feature/new-feature')
if success:
    print(f"Created and switched to branch: {branch}")
else:
    print(f"Failed to create branch: {error}")
```

---

### High-Level Workflow Function

#### `auto_commit_and_push(commit_message: str, branch: str, push: bool = True) -> Dict[str, Any]`

High-level function that orchestrates the full commit-and-push workflow.

**Parameters:**
- `commit_message` - Commit message
- `branch` - Branch name to push to
- `push` - Whether to push after committing (default: True)

**Returns:**
```python
{
    'success': bool,       # Overall success (True if commit succeeded)
    'commit_sha': str,     # Commit SHA if committed, '' otherwise
    'pushed': bool,        # True if pushed successfully
    'error': str           # Error message if any, '' otherwise
}
```

**Workflow:**
1. Validate git repo
2. Check git config
3. Detect merge conflicts
4. Check for detached HEAD
5. Check for uncommitted changes
6. Stage all changes
7. Commit changes
8. Get remote name (if push requested)
9. Push to remote (if push requested)

**Graceful Degradation:**
- If commit succeeds but push fails, return success=True with pushed=False
- If nothing to commit, return success=True with commit_sha='' and error message
- If prerequisites fail, return success=False with error message

**Implementation Notes:**
- Call validation functions first
- Stop on critical errors (not a repo, merge conflict, detached HEAD)
- Continue on non-critical errors (push failure after commit)
- Populate error message with helpful context

**Example:**
```python
result = auto_commit_and_push(
    commit_message='feat: add new feature\\n\\nDetailed description',
    branch='main',
    push=True
)

if result['success']:
    print(f"Committed: {result['commit_sha']}")
    if result['pushed']:
        print("Pushed to remote")
    else:
        print(f"Push failed: {result['error']}")
else:
    print(f"Workflow failed: {result['error']}")
```

---

## Error Handling Philosophy

### Fail-Safe Defaults
When errors occur, default to the safe state:
- `is_detached_head()` → Returns `True` on error (assume detached)
- `has_uncommitted_changes()` → Returns `True` on error (assume changes)
- `detect_merge_conflict()` → Returns `(False, [])` on error (assume clean)

### Graceful Degradation
- Commit succeeds but push fails → Still report success (commit worked)
- Nothing to commit → Report success with empty SHA and helpful message
- Prerequisites missing → Report failure with actionable error message

### Error Messages
All error messages should:
- Explain what went wrong
- Be lowercase and concise
- Include relevant context (file names, config names, etc.)
- Help user understand how to fix (implicitly)

**Good error messages:**
- `"not a git repository"`
- `"git user.name not set"`
- `"merge conflict detected in: file1.py, file2.py"`
- `"branch 'feature/test' already exists"`
- `"network timeout while pushing to remote"`
- `"protected branch update failed"`

**Bad error messages:**
- `"Error"` (not specific)
- `"Command failed"` (not helpful)
- `"Git error: 128"` (too technical)

---

## Testing

### Mocking Strategy
All tests mock `subprocess.run` to avoid:
- Real git commands executing
- Network calls
- File system modifications

### Coverage Requirements
- **Target**: 90%+ code coverage
- **All functions**: Must have at least one test
- **Error paths**: Must be tested (not just happy paths)
- **Edge cases**: Detached HEAD, merge conflicts, permission errors, timeouts

### Test Files
- **Unit tests**: `/tests/unit/test_git_operations.py` (48 tests)
- **Integration tests**: `/tests/integration/test_auto_implement_git.py` (17 tests)

---

## Import Example

```python
# In auto-implement command or other code
from git_operations import (
    validate_git_repo,
    check_git_config,
    auto_commit_and_push,
)

# Validate prerequisites
is_valid, error = validate_git_repo()
if not is_valid:
    print(f"Git not available: {error}")
    # Continue without git automation

is_configured, error = check_git_config()
if not is_configured:
    print(f"Git config incomplete: {error}")
    # Continue without git automation

# Run full workflow
result = auto_commit_and_push(
    commit_message=commit_msg,
    branch=current_branch,
    push=user_wants_push
)

if result['success'] and result['pushed']:
    print("✅ Changes committed and pushed")
elif result['success']:
    print(f"✅ Changes committed: {result['commit_sha']}")
    if result['error']:
        print(f"⚠️  Push failed: {result['error']}")
else:
    print(f"❌ Workflow failed: {result['error']}")
```

---

## Implementation Checklist

Before implementing, ensure:

- [ ] All functions return correct tuple/dict format
- [ ] All functions handle errors gracefully
- [ ] Error messages are helpful and actionable
- [ ] Subprocess calls have proper error handling
- [ ] Fail-safe defaults are used appropriately
- [ ] Graceful degradation is implemented
- [ ] All 65 tests pass
- [ ] Coverage is 90%+
- [ ] No real git commands executed in tests
- [ ] Documentation is updated

---

**Status**: Ready for implementation. Use this specification and the test files to guide TDD implementation.
