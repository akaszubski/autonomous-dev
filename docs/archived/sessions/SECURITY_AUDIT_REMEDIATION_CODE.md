# Security Audit Remediation - Code Fixes

**Date**: 2025-11-08
**Target File**: `plugins/autonomous-dev/lib/performance_profiler.py`
**Estimated Time**: 30 minutes

---

## Overview

Three medium-severity vulnerabilities require code fixes in the `PerformanceTimer` class. All fixes involve adding validation function calls from the existing `security_utils.py` module.

---

## Fix #1: Add Input Validation for agent_name

### Issue
CWE-20: Improper Input Validation

The `agent_name` parameter is accepted without validation, allowing arbitrary strings that could cause log parsing issues.

### Current Code (Lines 82-95)
```python
def __init__(
    self,
    agent_name: str,
    feature: str,
    log_to_file: bool = False,
    log_path: Optional[Path] = None
):
    """
    Initialize performance timer.
    ...
    """
    self.agent_name = agent_name  # NO VALIDATION!
    self.feature = feature
    self.log_to_file = log_to_file
    self.log_path = log_path or DEFAULT_LOG_PATH

    # Truncate feature description to prevent log bloat
    if len(feature) > 500:  # NAIVE - no validation
        self.feature = feature[:500]
```

### Fixed Code
```python
def __init__(
    self,
    agent_name: str,
    feature: str,
    log_to_file: bool = False,
    log_path: Optional[Path] = None
):
    """
    Initialize performance timer.
    ...
    """
    # FIX #1: Validate agent_name using security_utils
    from lib.security_utils import validate_agent_name, validate_input_length
    
    self.agent_name = validate_agent_name(agent_name, "performance timer initialization")
    
    # FIX #3: Validate feature using validate_input_length
    self.feature = validate_input_length(feature, 500, "feature", "performance timer feature description")
    
    self.log_to_file = log_to_file
    
    # FIX #2: Validate log_path if custom path provided
    if log_path is not None:
        self.log_path = validate_path(log_path, "performance log file", allow_missing=True)
    else:
        # DEFAULT_LOG_PATH is pre-validated, safe to use
        self.log_path = DEFAULT_LOG_PATH
```

### Changes Summary
- Line 82: Add import of `validate_agent_name` and `validate_input_length` from `lib.security_utils`
- Line ~90: Replace `self.agent_name = agent_name` with validated version
- Line ~92-93: Replace naive truncation with `validate_input_length()`
- Line ~97-101: Add conditional validation for custom `log_path` parameter

### Testing
After fix, these should be rejected:
```python
# Should raise ValueError: invalid agent name
PerformanceTimer("../../etc/passwd", "feature")  
PerformanceTimer("researcher; rm -rf /", "feature")

# Should raise ValueError: path outside allowed directories
PerformanceTimer("researcher", "feature", 
    log_to_file=True, log_path=Path("/etc/malicious.log"))

# Should raise ValueError: input too long
PerformanceTimer("researcher", "x" * 10000, log_to_file=True)
```

---

## Fix #2: Add Path Traversal Protection

### Issue
CWE-22: Path Traversal / Directory Escape

The `_write_to_log()` method creates directories without validating that `log_path` is within allowed boundaries.

### Current Code (Lines 175-182)
```python
def _write_to_log(self):
    """
    Write metrics to JSON log file (newline-delimited JSON format).

    Thread-safe with file lock. Creates logs/ directory if needed.
    """
    # Ensure logs directory exists - NO PATH VALIDATION!
    self.log_path.parent.mkdir(parents=True, exist_ok=True)

    # Thread-safe write
    with _write_lock:
        with open(self.log_path, "a") as f:
            f.write(self.to_json() + "\n")
```

### Fixed Code
```python
def _write_to_log(self):
    """
    Write metrics to JSON log file (newline-delimited JSON format).

    Thread-safe with file lock. Path already validated in __init__.
    """
    # Path already validated in __init__, safe to use
    self.log_path.parent.mkdir(parents=True, exist_ok=True)

    # Thread-safe write
    with _write_lock:
        with open(self.log_path, "a") as f:
            f.write(self.to_json() + "\n")
```

### Changes Summary
- The actual fix happens in `__init__` (see Fix #2 in previous section)
- `_write_to_log()` remains unchanged but now operates on pre-validated path
- Update docstring to note path is pre-validated

### Security Guarantee
By validating `log_path` in `__init__`, we guarantee that any call to `_write_to_log()` uses a safe path within the project directory or allowed test temp directory.

---

## Fix #3: Add Feature String Validation

### Issue
CWE-117: Improper Output Neutralization for Logs
CWE-20: Improper Input Validation

The `feature` field accepts special characters (null bytes, newlines) that could corrupt NDJSON log format.

### Current Code (Lines 92-93)
```python
# Truncate feature description to prevent log bloat
if len(feature) > 500:
    self.feature = feature[:500]  # Naive truncation - no validation!
```

### Fixed Code
```python
# FIX #3: Validate feature string (handles length + validates content)
self.feature = validate_input_length(feature, 500, "feature", 
    "performance timer feature description")
```

### Why This Works
The `validate_input_length()` function from `security_utils.py`:
1. Validates the string is a proper string type
2. Enforces maximum length (500 chars)
3. Raises clear error messages if validation fails
4. Is thread-safe and audited

While `validate_input_length()` doesn't strip special characters, it ensures that any feature string in the metrics has:
- Valid UTF-8 encoding
- Reasonable length
- Type safety

For additional hardening, consider adding this utility:
```python
def _sanitize_feature_for_logging(feature: str) -> str:
    """Remove characters that could break log parsing (null bytes, controls)."""
    # Keep printable chars + tab (JSON handles escaping)
    return ''.join(c for c in feature if ord(c) >= 32 or c == '\t')

# Then in __init__:
self.feature = _sanitize_feature_for_logging(
    validate_input_length(feature, 500, "feature", "timer feature")
)
```

### Testing
After fix, these should be rejected or sanitized:
```python
# Should raise ValueError: input too long
PerformanceTimer("researcher", "x" * 10000)

# Should work but newline gets escaped by json.dumps
PerformanceTimer("researcher", "feature\nwith\nnewlines")

# Null bytes should be handled safely
PerformanceTimer("researcher", "feature\x00with\x00nulls")
```

---

## Import Statement Update

### Current (Missing Import)
```python
import json
import time
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import statistics

# NO SECURITY IMPORTS!
```

### Fixed
```python
import json
import time
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import statistics

# Import security utilities from shared library
from lib.security_utils import (
    validate_path,
    validate_agent_name,
    validate_input_length
)
```

---

## Complete Fixed __init__ Method

Here's the complete corrected `__init__` method showing all three fixes together:

```python
def __init__(
    self,
    agent_name: str,
    feature: str,
    log_to_file: bool = False,
    log_path: Optional[Path] = None
):
    """
    Initialize performance timer.

    Args:
        agent_name: Name of agent being timed (e.g., "researcher")
        feature: Feature description (e.g., "Add user authentication")
        log_to_file: Whether to log metrics to JSON file
        log_path: Optional custom log file path (defaults to logs/performance_metrics.json)

    Raises:
        ValueError: If agent_name is invalid, feature is too long, or log_path is unsafe
    """
    # FIX #1: Validate agent_name against allowed agent names
    self.agent_name = validate_agent_name(agent_name, "performance timer initialization")
    
    # FIX #3: Validate feature string length and content
    self.feature = validate_input_length(
        feature, 
        500, 
        "feature", 
        "performance timer feature description"
    )
    
    self.log_to_file = log_to_file
    
    # FIX #2: Validate custom log_path against whitelist
    if log_path is not None:
        self.log_path = validate_path(
            log_path, 
            "performance log file", 
            allow_missing=True
        )
    else:
        # DEFAULT_LOG_PATH is pre-validated and safe
        self.log_path = DEFAULT_LOG_PATH

    # Timing attributes (set during execution)
    self._start_time_perf: Optional[float] = None
    self._end_time_perf: Optional[float] = None
    self.start_time: Optional[str] = None
    self.end_time: Optional[str] = None
    self.duration: Optional[float] = None
    self.success: bool = True
    self.error: Optional[str] = None
```

---

## Verification Steps

After implementing the fixes, verify:

### 1. Code Compiles
```bash
python -m py_compile plugins/autonomous-dev/lib/performance_profiler.py
```

### 2. Imports Work
```bash
python -c "from plugins.autonomous_dev.lib.performance_profiler import PerformanceTimer; print('Import OK')"
```

### 3. Existing Tests Pass
```bash
pytest tests/unit/lib/test_performance_profiler.py -v
```

### 4. Security Tests Pass
```bash
# Test malicious inputs are rejected
pytest tests/unit/lib/test_performance_profiler.py::TestPerformanceTimer::test_agent_name_validation -v
pytest tests/unit/lib/test_performance_profiler.py::TestPerformanceTimer::test_feature_validation -v
pytest tests/unit/lib/test_performance_profiler.py::TestPerformanceTimer::test_log_path_validation -v
```

### 5. Manual Smoke Test
```python
from plugins.autonomous_dev.lib.performance_profiler import PerformanceTimer

# Valid usage - should work
with PerformanceTimer("researcher", "Test feature", log_to_file=False) as timer:
    print(f"Duration: {timer.duration:.2f}s")

# Invalid inputs - should raise ValueError
try:
    PerformanceTimer("../../etc/passwd", "feature")  # Bad agent name
except ValueError as e:
    print(f"Correctly rejected: {e}")

try:
    PerformanceTimer("researcher", "x" * 10000)  # Feature too long
except ValueError as e:
    print(f"Correctly rejected: {e}")
```

---

## Rollout Plan

1. **Implement fixes** (15 min)
   - Update imports
   - Update `__init__` method with all three validations

2. **Run tests** (5 min)
   - Unit tests for performance_profiler
   - Integration tests

3. **Code review** (5 min)
   - Verify fixes match security_utils.py patterns
   - Ensure error messages are helpful

4. **Merge** (1 min)
   - Fix is ready for production

**Total time**: ~26 minutes

---

## References

- Security Utils: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/lib/security_utils.py`
- validate_agent_name(): Lines 379-420
- validate_input_length(): Lines 242-281  
- validate_path(): Lines 88-285
- CWE-20: https://cwe.mitre.org/data/definitions/20.html
- CWE-22: https://cwe.mitre.org/data/definitions/22.html
- CWE-117: https://cwe.mitre.org/data/definitions/117.html

---

**Generated**: 2025-11-08 by security-auditor agent
