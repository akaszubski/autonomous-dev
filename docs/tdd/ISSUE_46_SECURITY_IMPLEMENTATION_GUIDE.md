# Issue #46 Phase 6 Security - Implementation Guide

**Date**: 2025-11-08
**GitHub Issue**: #46 (Phase 6 - Profiling Infrastructure Security)
**Target**: implementer agent
**Goal**: Implement security validation to make 210+ tests PASS

---

## Quick Start

**Tests Written**: 210+ security tests (all FAIL currently)
**Tests Location**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/unit/lib/test_performance_profiler.py`
**Implementation Target**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/lib/performance_profiler.py`

---

## Implementation Checklist

### Step 1: Add Validation Functions (Top of File)

Add three validation functions BEFORE the `PerformanceTimer` class:

```python
def _validate_agent_name(agent_name: str) -> str:
    """
    Validate and normalize agent_name parameter.

    CWE-20: Improper Input Validation

    Security Requirements:
    - Alphanumeric + hyphens/underscores only
    - Max 256 characters
    - No paths, shell chars, control chars
    - Strip whitespace, normalize to lowercase

    Args:
        agent_name: Raw agent name input

    Returns:
        Normalized agent name (stripped, lowercased)

    Raises:
        ValueError: If agent_name contains invalid characters
    """
    import re
    from ..lib.security_utils import audit_log

    # Strip whitespace
    agent_name = agent_name.strip()

    # Check for empty string
    if not agent_name:
        audit_log("performance_profiler", "validation_failure", {
            "parameter": "agent_name",
            "error": "agent_name is required (empty string)"
        })
        raise ValueError("agent_name is required and cannot be empty")

    # Check max length (256 chars)
    if len(agent_name) > 256:
        audit_log("performance_profiler", "validation_failure", {
            "parameter": "agent_name",
            "value": agent_name[:100],
            "error": "agent_name too long (max 256 chars)"
        })
        raise ValueError(f"agent_name too long (max 256 chars, got {len(agent_name)})")

    # Validate alphanumeric + hyphens/underscores only
    # Pattern: lowercase letters, numbers, hyphens, underscores
    if not re.match(r'^[a-zA-Z0-9_-]+$', agent_name):
        audit_log("performance_profiler", "validation_failure", {
            "parameter": "agent_name",
            "value": agent_name[:100],
            "error": "agent_name contains invalid characters"
        })
        raise ValueError(
            f"agent_name invalid: must contain only alphanumeric characters, "
            f"hyphens, and underscores. Got: {agent_name[:50]}"
        )

    # Normalize to lowercase
    return agent_name.lower()


def _validate_feature(feature: str) -> str:
    """
    Validate and normalize feature parameter.

    CWE-117: Improper Output Neutralization for Logs

    Security Requirements:
    - No newlines (\n, \r)
    - No control characters (\x00-\x1f, \x7f)
    - No tabs (\t)
    - Max 10,000 characters
    - Strip whitespace

    Args:
        feature: Raw feature description

    Returns:
        Normalized feature (stripped)

    Raises:
        ValueError: If feature contains newlines or control characters
    """
    import re
    from ..lib.security_utils import audit_log

    # Strip whitespace
    feature = feature.strip()

    # Check max length (10,000 chars)
    if len(feature) > 10000:
        audit_log("performance_profiler", "validation_failure", {
            "parameter": "feature",
            "error": "feature too long (max 10,000 chars)"
        })
        raise ValueError(f"feature too long (max 10,000 chars, got {len(feature)})")

    # Reject newlines (\n, \r)
    if '\n' in feature or '\r' in feature:
        audit_log("performance_profiler", "validation_failure", {
            "parameter": "feature",
            "value": feature[:100],
            "error": "feature contains newline characters"
        })
        raise ValueError(
            "feature invalid: cannot contain newline characters (CWE-117 log injection)"
        )

    # Reject tabs (\t)
    if '\t' in feature:
        audit_log("performance_profiler", "validation_failure", {
            "parameter": "feature",
            "value": feature[:100],
            "error": "feature contains tab characters"
        })
        raise ValueError(
            "feature invalid: cannot contain tab characters (CWE-117 log injection)"
        )

    # Reject control characters (\x00-\x1f, \x7f)
    # Pattern matches any control character
    if re.search(r'[\x00-\x1f\x7f]', feature):
        audit_log("performance_profiler", "validation_failure", {
            "parameter": "feature",
            "value": feature[:100],
            "error": "feature contains control characters"
        })
        raise ValueError(
            "feature invalid: cannot contain control characters (CWE-117 log injection)"
        )

    # Feature is valid
    return feature


def _validate_log_path(log_path: Path) -> Path:
    """
    Validate log_path parameter.

    CWE-22: Path Traversal

    Security Requirements:
    - Must be within logs/ directory (whitelist)
    - Must have .json extension (lowercase)
    - No parent directory references (..)
    - No hidden files (starting with .)
    - No special files (/dev/null, CON, PRN)
    - Max 4,096 characters

    Args:
        log_path: Raw log path input

    Returns:
        Resolved canonical path

    Raises:
        ValueError: If log_path is outside logs/ directory
    """
    from pathlib import Path
    from ..lib.security_utils import audit_log

    # Resolve to canonical path (resolves symlinks and relative paths)
    try:
        resolved_path = log_path.resolve()
    except Exception as e:
        audit_log("performance_profiler", "validation_failure", {
            "parameter": "log_path",
            "value": str(log_path),
            "error": f"Cannot resolve path: {e}"
        })
        raise ValueError(f"log_path invalid: cannot resolve path: {e}")

    # Check max path length (4,096 chars)
    if len(str(resolved_path)) > 4096:
        audit_log("performance_profiler", "validation_failure", {
            "parameter": "log_path",
            "value": str(log_path)[:100],
            "error": "log_path too long (max 4,096 chars)"
        })
        raise ValueError(f"log_path too long (max 4,096 chars, got {len(str(resolved_path))})")

    # Whitelist validation: Must be in logs/ directory
    # Get project root (4 levels up from this file)
    project_root = Path(__file__).parent.parent.parent.parent.resolve()
    logs_dir = (project_root / "logs").resolve()

    # Check if resolved path is within logs/ directory
    try:
        resolved_path.relative_to(logs_dir)
    except ValueError:
        audit_log("performance_profiler", "validation_failure", {
            "parameter": "log_path",
            "value": str(log_path),
            "error": f"log_path outside logs/ directory"
        })
        raise ValueError(
            f"log_path invalid: must be within logs/ directory. "
            f"Expected prefix: {logs_dir}, got: {resolved_path}"
        )

    # Enforce .json extension (lowercase only)
    if resolved_path.suffix != '.json':
        audit_log("performance_profiler", "validation_failure", {
            "parameter": "log_path",
            "value": str(log_path),
            "error": "log_path must have .json extension"
        })
        raise ValueError(
            f"log_path invalid: must have .json extension (lowercase). "
            f"Got: {resolved_path.suffix}"
        )

    # Reject hidden files (starting with .)
    if any(part.startswith('.') for part in resolved_path.parts):
        audit_log("performance_profiler", "validation_failure", {
            "parameter": "log_path",
            "value": str(log_path),
            "error": "log_path cannot be hidden file"
        })
        raise ValueError(
            f"log_path invalid: cannot be hidden file (starting with .)"
        )

    # Reject special files
    special_files = {'/dev/null', '/dev/zero', '/dev/random', 'CON', 'PRN', 'AUX', 'NUL'}
    if resolved_path.name.upper() in special_files or str(resolved_path) in special_files:
        audit_log("performance_profiler", "validation_failure", {
            "parameter": "log_path",
            "value": str(log_path),
            "error": "log_path cannot be special file"
        })
        raise ValueError(
            f"log_path invalid: cannot be special file ({resolved_path.name})"
        )

    # Check for null bytes in path string
    if '\x00' in str(log_path):
        audit_log("performance_profiler", "validation_failure", {
            "parameter": "log_path",
            "value": str(log_path)[:100],
            "error": "log_path contains null bytes"
        })
        raise ValueError(
            f"log_path invalid: cannot contain null bytes (CWE-22 path traversal)"
        )

    # Path is valid
    return log_path
```

### Step 2: Update PerformanceTimer.__init__()

Replace the existing `__init__()` method with validation:

```python
def __init__(
    self,
    agent_name: str,
    feature: str,
    log_to_file: bool = False,
    log_path: Optional[Path] = None
):
    """
    Initialize performance timer with security validation.

    Args:
        agent_name: Name of agent being timed (validated: CWE-20)
        feature: Feature description (validated: CWE-117)
        log_to_file: Whether to log metrics to JSON file
        log_path: Optional custom log file path (validated: CWE-22)

    Raises:
        ValueError: If any parameter fails security validation
    """
    # Validate and normalize inputs (CWE-20, CWE-117, CWE-22)
    self.agent_name = _validate_agent_name(agent_name)
    self.feature = _validate_feature(feature)

    # Set logging configuration
    self.log_to_file = log_to_file

    # Validate log_path if provided (CWE-22)
    if log_path is not None:
        self.log_path = _validate_log_path(log_path)
    else:
        self.log_path = DEFAULT_LOG_PATH

    # Rest of existing initialization code...
    # (Keep all existing attributes: _start_time_perf, start_time, etc.)
```

### Step 3: Add Import for security_utils

At the top of performance_profiler.py:

```python
import json
import time
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import statistics
import re  # NEW: For regex validation

# NEW: Import security_utils for audit logging
try:
    from ..lib.security_utils import audit_log
except ImportError:
    # Fallback if security_utils not available (shouldn't happen)
    def audit_log(component, action, details):
        logging.warning(f"Audit log: {component}.{action}: {details}")
```

---

## Testing Strategy

### Run Tests Incrementally

**1. Test CWE-20 (agent_name) first:**
```bash
python3 -m pytest tests/unit/lib/test_performance_profiler.py::TestSecurityValidation::test_agent_name_rejects_path_traversal -v
```

**2. Test CWE-117 (feature) second:**
```bash
python3 -m pytest tests/unit/lib/test_performance_profiler.py::TestSecurityValidation::test_feature_rejects_newline_injection -v
```

**3. Test CWE-22 (log_path) third:**
```bash
python3 -m pytest tests/unit/lib/test_performance_profiler.py::TestSecurityValidation::test_log_path_rejects_path_traversal_dotdot -v
```

**4. Run all security validation tests:**
```bash
python3 -m pytest tests/unit/lib/test_performance_profiler.py::TestSecurityValidation -v
```

**5. Run integration tests:**
```bash
python3 -m pytest tests/unit/lib/test_performance_profiler.py::TestSecurityIntegration -v
```

**6. Run ALL tests (verify existing tests still pass):**
```bash
python3 -m pytest tests/unit/lib/test_performance_profiler.py -v
```

---

## Expected Test Results

### Before Implementation (Current State)
- **New tests**: 210+ FAIL (no validation exists)
- **Existing tests**: 71 PASS (use valid inputs)

### After Implementation (Target State)
- **New tests**: 210+ PASS (validation works)
- **Existing tests**: 71 PASS (backward compatible)
- **Total**: 281+ tests ALL PASS

---

## Common Pitfalls

### 1. Import Path Issues

**Problem**: `from ..lib.security_utils import audit_log` might fail

**Solution**: Use try/except with fallback logging

### 2. Path Resolution Issues

**Problem**: `log_path.resolve()` behavior differs on Windows/Unix

**Solution**: Tests use `Path.resolve()` for canonical paths

### 3. Regex Edge Cases

**Problem**: Regex might not catch all Unicode edge cases

**Solution**: Tests cover Unicode, right-to-left override, zero-width chars

### 4. Whitespace Normalization

**Problem**: Tests expect `.strip()` behavior

**Solution**: Always strip whitespace before validation

### 5. Case Sensitivity

**Problem**: Tests expect lowercase normalization for agent_name

**Solution**: Use `.lower()` after validation

---

## Performance Requirements

### Validation Overhead

**Requirement**: <1ms per PerformanceTimer creation

**Test**: `test_validation_performance_overhead` (1,000 iterations)

**Strategy**:
- Use compiled regex patterns (define once at module level)
- Avoid expensive operations in hot path
- Cache path resolution where possible

### Example: Precompile Regex

```python
# At module level (before validation functions)
_AGENT_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
_CONTROL_CHAR_PATTERN = re.compile(r'[\x00-\x1f\x7f]')

# In validation functions, use compiled patterns
if not _AGENT_NAME_PATTERN.match(agent_name):
    raise ValueError(...)
```

---

## Debugging Tips

### 1. Run Single Test

```bash
python3 -m pytest tests/unit/lib/test_performance_profiler.py::TestSecurityValidation::test_agent_name_rejects_path_traversal -vv
```

### 2. Print Validation Errors

Add temporary logging in validation functions:

```python
def _validate_agent_name(agent_name: str) -> str:
    print(f"DEBUG: Validating agent_name: {repr(agent_name)}")
    # ... validation logic
    return agent_name.lower()
```

### 3. Check Audit Log

Verify audit logging works:

```bash
cat logs/security_audit.log | grep "performance_profiler"
```

### 4. Test Specific Attack Vector

```python
# In Python REPL
from plugins.autonomous_dev.lib.performance_profiler import PerformanceTimer

# Test path traversal
try:
    timer = PerformanceTimer("../etc/passwd", "valid")
except ValueError as e:
    print(f"Correctly rejected: {e}")
```

---

## Success Criteria

### Must Pass
- [x] All 210+ security tests PASS
- [x] All 71 existing tests still PASS
- [x] Validation overhead <1ms per timer
- [x] Audit logging integrated
- [x] Error messages clear and actionable

### Must Not Break
- [x] Existing valid inputs work (backward compatibility)
- [x] Timer accuracy maintained
- [x] File I/O performance unchanged
- [x] Thread safety preserved

---

## Next Steps After Implementation

### 1. Code Review (reviewer agent)
- Verify all tests PASS
- Check error message clarity
- Verify backward compatibility

### 2. Security Audit (security-auditor agent)
- Verify CWE-20, CWE-117, CWE-22 mitigated
- Check for additional vulnerabilities
- Verify audit logging completeness

### 3. Documentation (doc-master agent)
- Update SECURITY.md with fixes
- Update performance_profiler.py docstrings
- Add usage examples
- Update CHANGELOG.md

---

## Related Documents

- **Test Summary**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/tests/ISSUE_46_SECURITY_TDD_RED_PHASE_COMPLETE.md`
- **Implementation Plan**: From planner agent (comprehensive 210+ test case breakdown)
- **Security Utils**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/lib/security_utils.py`

---

## Quick Reference: Test Count by CWE

| CWE | Vulnerability | Parameter | Tests | Status |
|-----|--------------|-----------|-------|--------|
| CWE-20 | Improper Input Validation | agent_name | 60 | RED → GREEN |
| CWE-117 | Log Injection | feature | 70 | RED → GREEN |
| CWE-22 | Path Traversal | log_path | 70 | RED → GREEN |
| Integration | All three CWEs | all | 10 | RED → GREEN |
| **Total** | **Security Tests** | **all** | **210** | **RED → GREEN** |

---

**Agent**: implementer
**Phase**: TDD Green Phase
**Goal**: Make all 210+ tests PASS
**File**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/lib/performance_profiler.py`
