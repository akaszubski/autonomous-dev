---
name: batch-implement
description: Execute multiple features sequentially with automatic context management
author: implementer agent
version: 1.0.0
date: 2025-11-15
---

# /batch-implement - Batch Feature Implementation

Execute multiple features sequentially with automatic context clearing between features. Prevents context bloat while maintaining autonomous development workflow.

## Purpose

Process a list of features in sequence, invoking `/auto-implement` for each feature and automatically clearing context between features to maintain optimal performance.

## Usage

```bash
/batch-implement features.txt
```

## Input Format

Features file (plain text, UTF-8):
```text
# Authentication features
Add user login
Add user logout

# User management features
Add user profile page
Add password reset
```

**Format Requirements**:
- One feature per line
- Empty lines are skipped
- Comment lines (starting with #) are skipped
- Duplicate features are automatically removed (preserving first occurrence)
- Maximum 1000 features per file
- Maximum 500 characters per feature line
- Maximum file size: 1MB

## Workflow

### CHECKPOINT 1: Validate Input File

**Objective**: Validate features file for security and correctness

**Tasks**:
1. Parse features file path from user input
2. Validate file exists and is readable
3. Check file size limit (1MB) - CWE-400 DoS prevention
4. Validate UTF-8 encoding
5. Prevent path traversal attacks - CWE-22

**Security Checks**:
- ✅ Path traversal prevention (CWE-22)
- ✅ File size limit (CWE-400)
- ✅ Encoding validation

**Output**:
```
✓ Features file validated: features.txt
  - File size: 1.2 KB
  - Encoding: UTF-8
  - Security: Passed
```

**Error Handling**:
- File not found → Clear error with path
- File too large → Show size and limit
- Invalid encoding → Request UTF-8 file
- Path traversal detected → Block and log to security audit

---

### CHECKPOINT 2: Parse Features

**Objective**: Extract and deduplicate features from file

**Tasks**:
1. Read file content (UTF-8)
2. Split into lines
3. Strip whitespace from each line
4. Skip empty lines
5. Skip comment lines (starting with #)
6. Enforce line length limit (500 chars) - CWE-400
7. Deduplicate features (preserve first occurrence)
8. Enforce feature count limit (1000) - CWE-400

**Output**:
```
✓ Parsed 15 features from file:
  1. Add user login
  2. Add user logout
  3. Add user profile page
  ...

  Skipped: 3 empty lines, 2 comments, 1 duplicate
```

**Error Handling**:
- Line too long → Show line number and limit
- Too many features → Show count and limit
- No features found → Warn and exit

---

### CHECKPOINT 3: Execute Batch

**Objective**: Execute features sequentially with context management

**Tasks**:
1. Generate unique batch ID
2. For each feature:
   a. Log progress (current/total)
   b. Invoke /auto-implement via Task tool
   c. Track timing and git statistics
   d. Execute /clear command (context management)
   e. Update session file with progress
   f. Handle errors (continue or abort based on mode)
3. Calculate batch metrics (timing, success rate)

**Context Management**:
- Clear context after EACH feature
- Keeps context under 8K tokens
- Prevents context bloat scaling issues

**Error Handling**:
- Continue-on-failure mode (default): Log error, continue with next feature
- Abort-on-failure mode: Stop batch on first error

**Progress Tracking**:
```
[Batch 1/15] Executing: Add user login
  Status: Success
  Duration: 28.3s
  Files changed: 3

[Batch 2/15] Executing: Add user logout
  Status: Success
  Duration: 22.1s
  Files changed: 2

...
```

**Session File Logging**:
- Location: `docs/sessions/YYYYMMDD-HHMMSS-batch-{batch_id}.json`
- Content: Progress, timing, status per feature
- Format: JSON for machine parsing

---

### CHECKPOINT 4: Generate Summary

**Objective**: Create human-readable summary report

**Tasks**:
1. Calculate aggregate metrics:
   - Total features processed
   - Success/failure counts
   - Success rate percentage
   - Total execution time
   - Average time per feature
2. List failed features (if any) with error messages
3. Aggregate git statistics (files changed, lines added/removed)
4. Format summary report

**Output**:
```
======================================================================
BATCH AUTO-IMPLEMENT SUMMARY
======================================================================

Batch ID: batch-a1b2c3d4
Total features: 15
Successful: 13
Failed: 2
Success rate: 86.7%

Total time: 382.5 seconds
Average time per feature: 25.5 seconds

FAILED FEATURES:
  1. Add invalid feature
     Error: Feature does not align with PROJECT.md goals
  2. Add broken feature
     Error: Tests failed after implementation

GIT STATISTICS:
  Files changed: 42
  Lines added: 1,234
  Lines removed: 567

======================================================================
```

---

## Implementation Details

### BatchAutoImplement Class

**Location**: `plugins/autonomous-dev/lib/batch_auto_implement.py`

**Key Methods**:
- `validate_features_file(path)` - Security validation
- `parse_features(path)` - Feature extraction and deduplication
- `execute_batch(path)` - Sequential execution orchestration
- `generate_summary(result)` - Summary report generation

**Internal Methods**:
- `_execute_single_feature()` - Single feature execution via Task tool
- `_track_progress()` - Session file logging
- `_ensure_directories()` - Directory structure validation

### Data Classes

**FeatureResult**:
```python
@dataclass
class FeatureResult:
    feature_name: str
    status: str  # "success" or "failed"
    duration_seconds: float
    git_stats: Dict[str, Any]
    error: Optional[str]
```

**BatchResult**:
```python
@dataclass
class BatchResult:
    batch_id: str
    total_features: int
    successful_features: int
    failed_features: int
    feature_results: List[FeatureResult]
    failed_feature_names: List[str]
    total_time_seconds: float

    def success_rate() -> float:
        # Returns success rate percentage (0.0 - 100.0)
```

### Exception Hierarchy

- `ValidationError` - Input validation failures
- `BatchExecutionError` - Fatal batch execution errors

---

## Security Features

### CWE-22: Path Traversal Prevention

- Uses `security_utils.validate_path()` for all file paths
- Blocks attempts to access files outside project directory
- Example: `../../etc/passwd` → ValidationError

### CWE-400: DoS Prevention

- File size limit: 1MB
- Feature count limit: 1000
- Line length limit: 500 characters
- Prevents resource exhaustion attacks

### CWE-78: Command Injection Prevention

- No shell command execution
- Uses Task tool API for /auto-implement invocation
- Uses /clear command API (no subprocess calls)

### Audit Logging

All operations logged to `logs/security_audit.log`:
- File validation
- Feature parsing
- Batch execution start/complete
- Individual feature execution
- Progress tracking errors
- Context clearing errors

---

## Performance Characteristics

### Context Management

**Problem**: Without context clearing, context bloats:
- Feature 1: 2K tokens
- Feature 2: 5K tokens
- Feature 3: 8K tokens
- Feature 4: **Context limit exceeded** ❌

**Solution**: Clear context after each feature:
- Feature 1: 2K tokens → /clear → 200 tokens
- Feature 2: 2K tokens → /clear → 200 tokens
- Feature 3: 2K tokens → /clear → 200 tokens
- Feature 100: 2K tokens → /clear → 200 tokens ✅

**Scalability**: Support for 100+ features in single batch

### Timing Estimates

- 10 features: ~4-5 minutes (with context clearing)
- 50 features: ~20-25 minutes
- 100 features: ~40-50 minutes

**Note**: Actual timing depends on feature complexity and /auto-implement performance

---

## Examples

### Basic Usage

```bash
# Create features file
cat > features.txt << EOF
Add user authentication
Add password reset
Add email verification
EOF

# Execute batch
/batch-implement features.txt
```

### With Comments and Grouping

```bash
# Create organized features file
cat > features.txt << EOF
# Phase 1: Authentication
Add user login
Add user logout
Add session management

# Phase 2: User Profile
Add profile page
Add avatar upload
Add profile editing

# Phase 3: Security
Add two-factor authentication
Add password strength validation
EOF

# Execute batch
/batch-implement features.txt
```

### Continue on Failure (Default)

```bash
# If a feature fails, continue with remaining features
/batch-implement features.txt

# Output will show which features failed
# Summary report lists failed features
```

### Check Session Logs

```bash
# View latest batch session
cat docs/sessions/$(ls -t docs/sessions/ | grep batch | head -1)
```

---

## Error Handling

### Validation Errors

**File Not Found**:
```
Error: Features file not found: missing.txt
```

**File Too Large**:
```
Error: File size (2.5MB) exceeds limit (1.0MB): huge.txt
```

**Invalid UTF-8**:
```
Error: File is not valid UTF-8: binary.txt
```

**Path Traversal**:
```
Error: Path traversal detected: ../../etc/passwd
```

### Parsing Errors

**Line Too Long**:
```
Error: Line 15 exceeds maximum length (523 > 500 chars): features.txt
```

**Too Many Features**:
```
Error: Feature count (1,234) exceeds limit (1,000): features.txt
```

**No Features**:
```
Error: No features found in file: empty.txt
```

### Execution Errors

**Feature Fails (Continue Mode)**:
```
[Batch 3/10] Executing: Add invalid feature
  Status: Failed
  Error: Feature does not align with PROJECT.md goals

Continuing with remaining features...
```

**Feature Fails (Abort Mode)**:
```
[Batch 3/10] Executing: Add invalid feature
  Status: Failed
  Error: Feature does not align with PROJECT.md goals

Aborting batch execution (abort-on-failure mode)
```

---

## Integration with /auto-implement

Each feature is executed via the full `/auto-implement` workflow:

1. **Alignment Check** - Validates against PROJECT.md
2. **Research** - Patterns and best practices (researcher agent)
3. **Planning** - Architecture design (planner agent)
4. **TDD Tests** - Test generation (test-master agent)
5. **Implementation** - Code implementation (implementer agent)
6. **Parallel Validation** - Quality, security, docs (3 agents)
7. **Git Automation** - Commit, push, PR (if enabled)

**Context Cleared After Each Feature** to maintain performance

---

## Best Practices

### Feature Descriptions

✅ **Good**: Clear, specific, actionable
```text
Add user login with email and password
Add password reset via email
Add email verification on signup
```

❌ **Bad**: Vague, ambiguous, too broad
```text
Fix authentication
Update user stuff
Make it better
```

### File Organization

**Recommended Structure**:
```text
# Group related features
# Use clear section headers
# One feature per line
# Keep descriptions concise

# Authentication (Phase 1)
Add user login
Add user logout
Add session management

# User Profile (Phase 2)
Add profile page
Add avatar upload
```

### Batch Size

- **Small batches (5-10 features)**: Quick feedback, easy debugging
- **Medium batches (10-50 features)**: Balance speed and oversight
- **Large batches (50+ features)**: Overnight/background processing

**Recommendation**: Start small (5-10 features) to validate workflow, then scale up

---

## Troubleshooting

### Context Still Growing

**Symptom**: Context exceeds 8K tokens during batch

**Cause**: /clear command not executing properly

**Solution**:
1. Check /clear command implementation
2. Verify execute_clear_command() is called
3. Restart Claude Code to reset context

### Features Failing Consistently

**Symptom**: Multiple features fail with same error

**Cause**:
- Features don't align with PROJECT.md
- Prerequisite features missing
- Environment issues

**Solution**:
1. Review PROJECT.md goals and scope
2. Check feature dependencies (order matters!)
3. Run /health-check to validate environment
4. Test single feature with /auto-implement first

### Slow Execution

**Symptom**: Batch takes much longer than expected

**Cause**:
- Complex features requiring extensive research
- Large codebase slowing down agents
- Network latency (research phase)

**Solution**:
1. Break complex features into smaller pieces
2. Use /research first to cache patterns
3. Run smaller batches during off-peak hours

---

## Related Commands

- `/auto-implement` - Single feature autonomous development
- `/research` - Pre-cache research patterns
- `/plan` - Validate feature plan before batch
- `/status` - Check project progress
- `/health-check` - Validate environment before batch

---

## Version History

**v1.0.0** (2025-11-15)
- Initial implementation
- Sequential feature execution
- Automatic context management
- Security hardening (CWE-22, CWE-400, CWE-78)
- Session file logging
- Summary report generation
- Continue-on-failure and abort-on-failure modes

---

**Implementation**: `plugins/autonomous-dev/lib/batch_auto_implement.py`

**Tests**:
- Unit tests: `tests/unit/test_batch_auto_implement.py` (44 tests)
- Integration tests: `tests/integration/test_batch_workflow.py` (16 tests)

**Security**: Hardened against CWE-22, CWE-400, CWE-78
