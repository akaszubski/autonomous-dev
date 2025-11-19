# Implementation Checklist - Issue #91

**Feature**: Auto-close GitHub issues after /auto-implement completes successfully
**TDD Phase**: RED (tests written, ready for implementation)
**Tests Created**: 54 tests (52 failing, 2 passing - as expected)

---

## Components to Implement

### 1. Library: `github_issue_closer.py`

**Location**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/lib/github_issue_closer.py`

**Functions to Implement**: 5

#### Function 1: `extract_issue_number(command_args: str) -> Optional[int]`
**Tests**: 8
**Purpose**: Extract issue number from command arguments

**Patterns to Support**:
- `"issue #8"` → 8
- `"#8"` → 8
- `"Issue 8"` → 8
- Case insensitive (ISSUE, issue, Issue)
- Multiple mentions → use first
- No issue number → return None
- Empty string → return None

**Implementation Hints**:
- Use regex: `r'(?:issue\s*#?|#)(\d+)'` with `re.IGNORECASE`
- Return first match only
- Handle None/empty gracefully

---

#### Function 2: `validate_issue_state(issue_number: int) -> bool`
**Tests**: 5
**Purpose**: Validate issue exists and is open via gh CLI

**Requirements**:
- Call: `gh issue view {issue_number} --json state,title,number`
- Timeout: 10 seconds
- Raise `IssueAlreadyClosedError` if state == "closed"
- Raise `IssueNotFoundError` if issue doesn't exist
- Raise `GitHubAPIError` on timeout or network failure
- Return True if issue is open

**Implementation Hints**:
```python
subprocess.run(
    ['gh', 'issue', 'view', str(issue_number), '--json', 'state,title,number'],
    capture_output=True,
    text=True,
    timeout=10,
    check=True,
)
```

---

#### Function 3: `generate_close_summary(issue_number: int, metadata: dict) -> str`
**Tests**: 5
**Purpose**: Generate formatted close summary for issue comment

**Required Sections**:
1. Completion message: "Completed via /auto-implement"
2. All 7 agents passed (list each: researcher, planner, test-master, implementer, reviewer, security-auditor, doc-master)
3. PR URL (if available in metadata)
4. Commit hash (if available)
5. Files changed count
6. File list (truncate at 10 files, show "... N more")

**Security**: CWE-117 - Sanitize newlines and control characters

**Implementation Hints**:
```python
summary = f"""Completed via /auto-implement

All 7 agents passed:
- researcher
- planner
- test-master
- implementer
- reviewer
- security-auditor
- doc-master

{f"PR: {metadata['pr_url']}" if 'pr_url' in metadata else ''}
Commit: {metadata['commit_hash']}
Files changed: {len(metadata['files_changed'])}
{format_file_list(metadata['files_changed'])}
"""
# Sanitize: replace newlines, remove control chars
```

---

#### Function 4: `close_github_issue(issue_number: int, summary: str) -> bool`
**Tests**: 5
**Purpose**: Close issue via gh CLI with summary comment

**Requirements**:
- Call: `gh issue close {issue_number} --comment {summary}`
- Timeout: 10 seconds
- Idempotent: Return True if already closed
- Raise `IssueNotFoundError` if issue doesn't exist
- Raise `GitHubAPIError` on timeout
- Log audit event before closing

**Implementation Hints**:
```python
log_audit_event({
    'action': 'close_github_issue',
    'issue_number': issue_number,
    'timestamp': datetime.now().isoformat(),
})

subprocess.run(
    ['gh', 'issue', 'close', str(issue_number), '--comment', summary],
    capture_output=True,
    text=True,
    timeout=10,
    check=True,
)
```

---

#### Function 5: `prompt_user_consent(issue_number: int) -> bool`
**Tests**: 4
**Purpose**: Prompt user for consent to close issue

**Requirements**:
- Prompt: f"Close issue #{issue_number}? (yes/no): "
- Accept: "yes", "YES", "Yes", "y" → True
- Decline: "no", "NO", "No", "n" → False
- Invalid input → re-prompt (max 3 tries)
- Case insensitive

**Implementation Hints**:
```python
for _ in range(3):
    response = input(f"Close issue #{issue_number}? (yes/no): ").strip().lower()
    if response in ['yes', 'y']:
        return True
    elif response in ['no', 'n']:
        return False
    print("Invalid input. Please enter 'yes' or 'no'.")
return False  # Default to no after 3 tries
```

---

### Custom Exceptions to Define

```python
class IssueAlreadyClosedError(Exception):
    """Raised when trying to close an already-closed issue."""
    pass

class IssueNotFoundError(Exception):
    """Raised when issue doesn't exist."""
    pass

class GitHubAPIError(Exception):
    """Raised when gh CLI fails (timeout, network error)."""
    pass
```

---

## 2. Hook Modification: `auto_git_workflow.py`

**Location**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/hooks/auto_git_workflow.py`

**Function to Add**: 1

#### Function: `handle_issue_close(command_args: str, metadata: dict) -> bool`
**Tests**: 6
**Purpose**: Orchestrate issue close workflow after git push succeeds

**Workflow**:
```python
def handle_issue_close(command_args: str, metadata: dict) -> bool:
    """Close GitHub issue if present in command args.

    Args:
        command_args: User command arguments (e.g., "implement issue #8")
        metadata: Workflow metadata (pr_url, commit_hash, files_changed)

    Returns:
        True if issue closed successfully or already closed (idempotent)
        False if skipped (no issue, user declined) or failed (gh CLI error)
    """
    try:
        # Step 1: Extract issue number
        issue_number = extract_issue_number(command_args)
        if not issue_number:
            return False  # No issue number, skip gracefully

        # Step 2: Prompt user consent
        if not prompt_user_consent(issue_number):
            return False  # User declined, skip gracefully

        # Step 3: Validate issue state
        try:
            validate_issue_state(issue_number)
        except IssueAlreadyClosedError:
            return True  # Already closed, idempotent success

        # Step 4: Generate summary
        summary = generate_close_summary(issue_number, metadata)

        # Step 5: Close issue
        return close_github_issue(issue_number, summary)

    except (IssueNotFoundError, GitHubAPIError) as e:
        # Log error but don't fail workflow (graceful degradation)
        log_audit_event({
            'action': 'issue_close_failed',
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
        })
        return False
```

**Integration Point**: Call after git push succeeds in `run_hook()`

---

## 3. Command Update: `auto-implement.md`

**Location**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/commands/auto-implement.md`

**Change**: Add STEP 5.1 after git push

```markdown
### STEP 5: Git Operations (if consent given)

[existing content...]

5.1. **Issue Closing** (if issue number in args):
   - Extract issue number from command args (e.g., "issue #8")
   - Prompt user: "Close issue #8? (yes/no)"
   - If yes: Close issue via gh CLI with summary
   - Summary includes: PR link, commit hash, files changed, all 7 agents passed
   - If no: Skip gracefully
   - If already closed: Skip gracefully (idempotent)
```

---

## Security Requirements

All implementations MUST comply with:

### CWE-20: Input Validation
- Validate issue numbers are positive integers
- Reject negative, zero, non-integer inputs
- Raise ValueError for invalid inputs

### CWE-78: Command Injection Prevention
- Use subprocess list args: `['gh', 'issue', 'close', str(issue_number)]`
- NEVER use `shell=True`
- NEVER concatenate strings for commands

### CWE-117: Log Injection Prevention
- Sanitize all output before logging or displaying
- Replace newlines with spaces: `text.replace('\n', ' ')`
- Remove control characters: `re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)`

### Audit Logging
- Log all gh CLI operations
- Log user consent decisions
- Log errors and failures
- Include timestamp, action, metadata

---

## Test Execution

### Run Tests During Implementation

```bash
# After implementing each function, run its tests
.venv/bin/python -m pytest \
  tests/unit/lib/test_github_issue_closer.py::TestIssueNumberExtraction \
  -v

# Run all unit tests
.venv/bin/python -m pytest \
  tests/unit/lib/test_github_issue_closer.py \
  tests/unit/hooks/test_auto_git_workflow_issue_close.py \
  -v

# Run all tests (unit + integration)
.venv/bin/python -m pytest \
  tests/unit/lib/test_github_issue_closer.py \
  tests/unit/hooks/test_auto_git_workflow_issue_close.py \
  tests/integration/test_issue_close_end_to_end.py \
  -v

# Run with coverage
.venv/bin/python -m pytest \
  tests/unit/lib/test_github_issue_closer.py \
  --cov=plugins/autonomous-dev/lib/github_issue_closer \
  --cov-report=term-missing
```

---

## Implementation Order

1. **Phase 1**: Core library functions (5 functions, 3 exceptions)
   - Define custom exceptions
   - Implement `extract_issue_number()`
   - Implement `validate_issue_state()`
   - Implement `generate_close_summary()`
   - Implement `close_github_issue()`
   - Implement `prompt_user_consent()`

2. **Phase 2**: Hook integration
   - Implement `handle_issue_close()` in `auto_git_workflow.py`
   - Add import: `from github_issue_closer import ...`
   - Call `handle_issue_close()` after git push in `run_hook()`

3. **Phase 3**: Command update
   - Add STEP 5.1 to `auto-implement.md`

4. **Phase 4**: Verification
   - Run all 54 tests
   - Verify 100% pass rate
   - Check coverage (target: 95%+)

---

## Expected Test Results

### Current (TDD Red Phase)
```
52 failed, 2 passed
```

### After Implementation (TDD Green Phase)
```
54 passed
```

### Coverage Target
```
github_issue_closer.py: 95%+ coverage
auto_git_workflow.py (new function): 95%+ coverage
```

---

## Files Summary

**Test Files** (already created):
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/lib/test_github_issue_closer.py` (31 tests)
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/hooks/test_auto_git_workflow_issue_close.py` (10 tests)
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/integration/test_issue_close_end_to_end.py` (13 tests)

**Implementation Files** (to be created/modified):
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/lib/github_issue_closer.py` (NEW)
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/hooks/auto_git_workflow.py` (MODIFY - add handle_issue_close)
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/commands/auto-implement.md` (MODIFY - add STEP 5.1)

---

## Notes for Implementer

1. **Follow TDD**: Implement one function at a time, watch tests pass
2. **Security First**: CWE-20, CWE-78, CWE-117 compliance from the start
3. **Graceful Degradation**: All failures return False, log error, workflow continues
4. **Idempotent**: Closing already-closed issues succeeds silently
5. **User Consent**: Always prompt before closing (no automatic closing)
6. **Audit Logging**: Log all security-relevant operations

---

**Status**: Ready for implementation (TDD red phase complete)
**Next Agent**: implementer
**Expected Outcome**: All 54 tests pass (TDD green phase)
