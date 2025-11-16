# Issue #77: Implementer Quick Start Guide

**TDD Status**: RED → awaiting GREEN phase
**Your Mission**: Make 44 failing tests pass by implementing the --issues flag feature

---

## Quick Start

### Run Tests to See Current State
```bash
# Activate virtual environment
source .venv/bin/activate

# Run unit tests (27 tests - ALL should be RED)
pytest tests/unit/lib/test_github_issue_fetcher.py -v

# Run integration tests (17 tests - ALL should be RED)
pytest tests/integration/test_batch_implement_issues_flag.py -v
```

**Expected**: All tests fail with `ModuleNotFoundError` or `NameError`

---

## Implementation Checklist

### Phase 1: Create `github_issue_fetcher.py` (Priority 1)

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/lib/github_issue_fetcher.py`

#### Function 1: `validate_issue_numbers()`
```python
def validate_issue_numbers(issue_numbers: List[int]) -> None:
    """Validate GitHub issue numbers.

    Security (CWE-20): Input validation
    - Accept only positive integers (>0)
    - Reject zero, negatives
    - Max 100 issues per batch
    - Raise ValueError with helpful messages
    """
    # TODO: Implement validation logic
    pass
```

**Tests to Pass** (7 tests):
- `test_valid_single_issue`
- `test_valid_multiple_issues`
- `test_invalid_negative_issue`
- `test_invalid_zero_issue`
- `test_invalid_too_many_issues`
- `test_invalid_mixed_valid_invalid`
- `test_invalid_empty_list`

---

#### Function 2: `fetch_issue_title()`
```python
def fetch_issue_title(issue_number: int) -> Optional[str]:
    """Fetch single issue title via gh CLI.

    Security (CWE-78): Command injection prevention
    - Use subprocess.run() with LIST args
    - shell=False (CRITICAL)
    - 10-second timeout
    - Audit log all operations

    Returns:
        Issue title if exists, None if 404
    """
    # TODO: Implement subprocess call
    # Example: subprocess.run(['gh', 'issue', 'view', str(issue_number), '--json', 'title'], ...)
    pass
```

**Tests to Pass** (7 tests):
- `test_fetch_existing_issue`
- `test_fetch_missing_issue`
- `test_gh_cli_not_installed`
- `test_gh_cli_timeout`
- `test_command_injection_prevention` (SECURITY CRITICAL)
- `test_json_parse_error`

**Security Requirements**:
```python
# ✅ CORRECT (list args, shell=False)
result = subprocess.run(
    ['gh', 'issue', 'view', str(issue_number), '--json', 'title'],
    capture_output=True,
    text=True,
    timeout=10,
    shell=False  # CRITICAL!
)

# ❌ WRONG (security violation CWE-78)
result = subprocess.run(
    f"gh issue view {issue_number} --json title",
    shell=True,  # SECURITY VIOLATION!
    ...
)
```

---

#### Function 3: `fetch_issue_titles()`
```python
def fetch_issue_titles(issue_numbers: List[int]) -> Dict[int, str]:
    """Batch fetch multiple issue titles.

    Features:
    - Call fetch_issue_title() for each issue
    - Graceful degradation: skip missing issues (return None)
    - Audit log batch operations
    - Raise ValueError if ALL issues missing

    Returns:
        Dict mapping issue_number → title (only successful fetches)
    """
    # TODO: Implement batch fetching with graceful degradation
    pass
```

**Tests to Pass** (4 tests):
- `test_all_issues_exist`
- `test_mixed_valid_invalid` (graceful degradation)
- `test_all_issues_missing`
- `test_audit_logging`

---

#### Function 4: `format_feature_description()`
```python
def format_feature_description(issue_number: int, title: str) -> str:
    """Format issue as feature description.

    Security (CWE-117): Log injection prevention
    - Sanitize newlines (\n, \r)
    - Remove control characters (\t, \x00, \x1b)
    - Truncate long titles (>200 chars → "...")
    - Handle empty/whitespace-only titles

    Returns:
        "Issue #72: Add logging feature"
    """
    # TODO: Implement sanitization and formatting
    pass
```

**Tests to Pass** (6 tests):
- `test_format_normal_title`
- `test_sanitize_newlines` (SECURITY CRITICAL)
- `test_sanitize_control_characters`
- `test_truncate_long_titles`
- `test_empty_title_handling`
- `test_whitespace_only_title`

**Sanitization Example**:
```python
# Remove newlines (CWE-117 prevention)
title = title.replace('\n', ' ').replace('\r', ' ')

# Remove control characters
title = ''.join(char for char in title if ord(char) >= 32 or char == ' ')

# Truncate if needed
if len(title) > 200:
    title = title[:200] + "..."
```

---

### Phase 2: Enhance `batch_state_manager.py` (Priority 2)

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/lib/batch_state_manager.py`

**Changes Required**:

1. **Add fields to BatchState dataclass**:
```python
@dataclass
class BatchState:
    # ... existing fields ...
    issue_numbers: Optional[List[int]] = None  # NEW
    source_type: str = "file"  # NEW: "file" or "issues"
```

2. **Update create_batch_state() signature**:
```python
def create_batch_state(
    features: List[str],
    state_file: Path,
    issue_numbers: Optional[List[int]] = None,  # NEW
    source_type: str = "file"  # NEW
) -> BatchState:
    """Create new batch state."""
    # ... existing logic ...
    return BatchState(
        # ... existing fields ...
        issue_numbers=issue_numbers,
        source_type=source_type
    )
```

3. **Ensure backward compatibility in load_batch_state()**:
```python
def load_batch_state(state_file: Path) -> BatchState:
    """Load batch state from JSON."""
    with open(state_file) as f:
        data = json.load(f)

    # Backward compatibility: old state files lack these fields
    if 'issue_numbers' not in data:
        data['issue_numbers'] = None
    if 'source_type' not in data:
        data['source_type'] = 'file'

    return BatchState(**data)
```

**Tests to Pass** (3 tests):
- `test_state_includes_issue_numbers`
- `test_state_includes_source_type`
- `test_resume_preserves_issue_numbers`
- `test_backward_compatibility`

---

### Phase 3: Update `batch-implement.md` (Priority 3)

**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/commands/batch-implement.md`

**Changes Required**:

1. **Add --issues argument parsing**:
```markdown
## Usage

```bash
# Option 1: File-based (existing)
/batch-implement <features-file>

# Option 2: Issue-based (NEW)
/batch-implement --issues <issue-numbers>

# Resume either type
/batch-implement --resume <batch-id>
```

2. **Add mutual exclusivity validation**:
```python
if has_file_arg and has_issues_arg:
    raise ValueError(
        "Cannot use --issues and <features-file> together. "
        "Choose one: file-based or issue-based batch processing."
    )
```

3. **Integrate github_issue_fetcher**:
```python
from github_issue_fetcher import (
    validate_issue_numbers,
    fetch_issue_titles,
    format_feature_description
)

# If --issues flag provided
if issues_arg:
    # Parse: "72,73,74" → [72, 73, 74]
    issue_numbers = [int(x.strip()) for x in issues_arg.split(',')]

    # Validate
    validate_issue_numbers(issue_numbers)

    # Fetch titles
    issue_titles = fetch_issue_titles(issue_numbers)

    # Format as features
    features = [
        format_feature_description(num, title)
        for num, title in issue_titles.items()
    ]

    # Create state
    state = create_batch_state(
        features=features,
        state_file=state_file,
        issue_numbers=list(issue_titles.keys()),
        source_type="issues"
    )
```

**Tests to Pass** (8 tests from integration):
- `test_issues_flag_basic_workflow`
- `test_mutually_exclusive_file_and_issues`
- `test_gh_cli_not_installed`
- And 5 more integration tests

---

## Test-Driven Development Workflow

### Recommended Order:

1. **Start with validation** (easiest, no dependencies):
   ```bash
   # Implement validate_issue_numbers()
   pytest tests/unit/lib/test_github_issue_fetcher.py::TestValidateIssueNumbers -v
   ```

2. **Then formatting** (no subprocess, just string manipulation):
   ```bash
   # Implement format_feature_description()
   pytest tests/unit/lib/test_github_issue_fetcher.py::TestFormatFeatureDescription -v
   ```

3. **Then single fetch** (subprocess complexity):
   ```bash
   # Implement fetch_issue_title()
   pytest tests/unit/lib/test_github_issue_fetcher.py::TestFetchIssueTitle -v
   ```

4. **Then batch fetch** (builds on single fetch):
   ```bash
   # Implement fetch_issue_titles()
   pytest tests/unit/lib/test_github_issue_fetcher.py::TestFetchIssueTitles -v
   ```

5. **Then state management** (enhance existing module):
   ```bash
   # Enhance batch_state_manager.py
   pytest tests/integration/test_batch_implement_issues_flag.py::TestIssueBasedStateManagement -v
   ```

6. **Finally integration** (command updates):
   ```bash
   # Update batch-implement.md
   pytest tests/integration/test_batch_implement_issues_flag.py -v
   ```

---

## Security Checklist (CRITICAL)

Before marking complete, verify:

### ✅ CWE-20: Input Validation
- [ ] Positive integers only (reject zero, negatives)
- [ ] Max 100 issues enforced
- [ ] Validation happens BEFORE subprocess calls
- [ ] Helpful error messages for invalid inputs

### ✅ CWE-78: Command Injection Prevention
- [ ] subprocess.run() uses LIST arguments (not string)
- [ ] shell=False in ALL subprocess calls
- [ ] No string concatenation in commands
- [ ] Test `test_command_injection_prevention` passes

### ✅ CWE-117: Log Injection Prevention
- [ ] Newlines (\n, \r) stripped from titles
- [ ] Control characters removed (\t, \x00, \x1b, etc.)
- [ ] Long titles truncated (>200 chars)
- [ ] Test `test_sanitize_newlines` passes

### ✅ Audit Logging
- [ ] All gh CLI operations logged
- [ ] Validation results logged
- [ ] Errors and warnings logged
- [ ] Test `test_audit_logging` passes

---

## Coverage Verification

### Unit Tests (90%+ target)
```bash
pytest tests/unit/lib/test_github_issue_fetcher.py \
  --cov=plugins.autonomous_dev.lib.github_issue_fetcher \
  --cov-report=term-missing \
  --cov-fail-under=90
```

### Integration Tests (85%+ combined)
```bash
pytest tests/integration/test_batch_implement_issues_flag.py \
  --cov=plugins.autonomous_dev.lib \
  --cov=plugins.autonomous_dev.commands \
  --cov-report=term-missing \
  --cov-fail-under=85
```

---

## Common Pitfalls to Avoid

### ❌ WRONG: String concatenation in subprocess
```python
# SECURITY VIOLATION (CWE-78)
cmd = f"gh issue view {issue_number} --json title"
subprocess.run(cmd, shell=True)  # Allows command injection!
```

### ✅ CORRECT: List arguments
```python
subprocess.run(
    ['gh', 'issue', 'view', str(issue_number), '--json', 'title'],
    shell=False,
    timeout=10
)
```

### ❌ WRONG: No sanitization
```python
# LOG INJECTION VULNERABILITY (CWE-117)
return f"Issue #{num}: {title}"  # title may contain \n
```

### ✅ CORRECT: Sanitize first
```python
sanitized = title.replace('\n', ' ').replace('\r', ' ')
return f"Issue #{num}: {sanitized}"
```

---

## Success Criteria

**Phase 1 Complete**: All 27 unit tests pass
**Phase 2 Complete**: All 17 integration tests pass
**Phase 3 Complete**: Coverage ≥90% unit, ≥85% combined
**Feature Complete**: All 44 tests GREEN, security verified

---

## Need Help?

### Check Test Output
```bash
# Verbose output shows exact assertion failures
pytest tests/unit/lib/test_github_issue_fetcher.py -vv

# Show local variables on failure
pytest tests/unit/lib/test_github_issue_fetcher.py -vv -l
```

### Review Test File
Each test has comprehensive docstrings explaining:
- What is being tested (Given)
- How to implement it (When)
- What the expected result is (Then)

### Security Requirements
See `tests/ISSUE77_TDD_RED_PHASE_SUMMARY.md` for complete security checklist

---

**Good luck with the GREEN phase!** 🟢

**Remember**: Tests are your specification. Make them pass one by one, and the feature will emerge.
