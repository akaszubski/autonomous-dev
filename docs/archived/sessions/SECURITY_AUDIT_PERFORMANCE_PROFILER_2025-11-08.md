# Security Audit Report
## performance_profiler.py, researcher.md, planner.md

**Audit Date**: 2025-11-08
**Auditor**: security-auditor agent
**Files Scanned**: 
- plugins/autonomous-dev/lib/performance_profiler.py (539 lines)
- plugins/autonomous-dev/agents/researcher.md (agent config)
- plugins/autonomous-dev/agents/planner.md (agent config)

---

## SECURITY STATUS: FAIL (Medium Severity Issues Found)

### Vulnerabilities Found: 3

---

## VULNERABILITY DETAILS

### [MEDIUM]: Insufficient Input Validation - Agent Name Parameter
**Issue**: The `agent_name` parameter in `PerformanceTimer.__init__()` accepts arbitrary strings without validation against the allowed agent list. Malformed agent names can be logged, potentially causing log analysis failures or injection attacks when metrics are parsed downstream.

**Location**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/lib/performance_profiler.py:82-95`

**Code**:
```python
def __init__(
    self,
    agent_name: str,
    feature: str,
    log_to_file: bool = False,
    log_path: Optional[Path] = None
):
    """Initialize performance timer."""
    self.agent_name = agent_name
    self.feature = feature
    # ... truncate feature to 500 chars ...
    if len(feature) > 500:
        self.feature = feature[:500]
```

**Attack Vector**: 
- Attacker (or buggy code) passes `agent_name = "researcher\"; } {\n malicious"` to PerformanceTimer
- This string is stored as-is and serialized to JSON
- While JSON encoding prevents code execution, it violates security principle of least privilege
- Log consumers might parse this malformed JSON and extract incorrect metric data
- Attack: `agent_name = "../../../etc/passwd"` could be logged as-is

**Security Pattern Violation**: The codebase provides `validate_agent_name()` in `security_utils.py` but performance_profiler.py does not use it.

**CWE Reference**: CWE-20 (Improper Input Validation)

**Recommendation**:
```python
# FIX: Add input validation using security_utils
from lib.security_utils import validate_agent_name, validate_input_length

def __init__(
    self,
    agent_name: str,
    feature: str,
    log_to_file: bool = False,
    log_path: Optional[Path] = None
):
    """Initialize performance timer."""
    # Validate agent name against whitelist
    self.agent_name = validate_agent_name(agent_name, "performance timer initialization")
    
    # Validate feature length (prevents log bloat)
    self.feature = validate_input_length(feature, 500, "feature", "performance timer feature description")
```

**Severity Justification**: Medium - No code execution risk due to JSON serialization, but violates input validation best practices and could cause downstream log analysis issues.

---

### [MEDIUM]: Unsafe Path Creation Without Whitelist Validation
**Issue**: The `_write_to_log()` method creates the logs directory using `mkdir(parents=True, exist_ok=True)` without validating that `self.log_path` is within the allowed directory whitelist. While `DEFAULT_LOG_PATH` is safe, a custom `log_path` parameter could point anywhere.

**Location**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/lib/performance_profiler.py:175-182`

**Code**:
```python
def _write_to_log(self):
    """Write metrics to JSON log file (newline-delimited JSON format)."""
    # Ensure logs directory exists - NO VALIDATION!
    self.log_path.parent.mkdir(parents=True, exist_ok=True)

    # Thread-safe write
    with _write_lock:
        with open(self.log_path, "a") as f:
            f.write(self.to_json() + "\n")
```

**Attack Vector**:
- Code calls: `PerformanceTimer("researcher", "feature", log_to_file=True, log_path=Path("/etc/secrets.json"))`
- `_write_to_log()` creates `/etc/` if needed and writes metrics to `/etc/secrets.json`
- While `/etc/` probably isn't writable, this violates principle of least privilege
- Better attack: `log_path=Path("/var/log/app/malicious.log")` on vulnerable systems

**Security Pattern Violation**: The codebase provides `validate_path()` in `security_utils.py` with 4-layer defense (CWE-22 protection), but performance_profiler.py doesn't use it.

**CWE Reference**: CWE-22 (Improper Limitation of a Pathname to a Restricted Directory / Path Traversal)

**Recommendation**:
```python
# FIX: Validate log_path using security_utils.validate_path()
from lib.security_utils import validate_path

def __init__(
    self,
    agent_name: str,
    feature: str,
    log_to_file: bool = False,
    log_path: Optional[Path] = None
):
    """Initialize performance timer."""
    self.agent_name = validate_agent_name(agent_name, "performance timer initialization")
    self.feature = validate_input_length(feature, 500, "feature", "performance timer")
    self.log_to_file = log_to_file
    
    # Validate log_path if custom path provided
    if log_path is not None:
        self.log_path = validate_path(log_path, "performance log file", allow_missing=True)
    else:
        # DEFAULT_LOG_PATH is pre-validated, safe to use
        self.log_path = DEFAULT_LOG_PATH

def _write_to_log(self):
    """Write metrics to JSON log file (newline-delimited JSON format)."""
    # Path already validated in __init__, safe to use
    self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    with _write_lock:
        with open(self.log_path, "a") as f:
            f.write(self.to_json() + "\n")
```

**Severity Justification**: Medium - Depends on filesystem permissions, but violates defense-in-depth principle. Could enable log file injection attacks on systems with unusual permissions.

---

### [MEDIUM]: Feature String Not Escaped in JSON Output
**Issue**: The `feature` field in JSON output is truncated to 500 characters but not validated/escaped. While JSON encoding provides some protection, extremely long or specially-crafted strings could cause parsing issues downstream when metrics are aggregated.

**Location**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/lib/performance_profiler.py:92, 145-157`

**Code**:
```python
# Truncate feature description to prevent log bloat
if len(feature) > 500:
    self.feature = feature[:500]  # Naive truncation, no validation

def as_dict(self) -> Dict[str, Any]:
    """Convert timer data to dictionary for JSON serialization."""
    return {
        "agent_name": self.agent_name,
        "feature": self.feature,  # No validation of special characters
        "duration": self.duration,
        "start_time": self.start_timestamp,
        "end_time": self.end_timestamp,
        "success": self.success
    }
```

**Attack Vector**:
- Input: `feature = "feature\u0000null byte poison\ninjected newline"`
- Output JSON: `{"feature": "feature\u0000null byte..."}`
- Log parsing code might stop at null byte and misinterpret subsequent lines
- NDJSON parser might treat newline in feature as record delimiter (parse corruption)
- Downstream JSON parsing tools could fail or produce unexpected output

**Security Pattern Violation**: Missing input validation/sanitization. The codebase validates input lengths (`validate_input_length()`) but doesn't sanitize content.

**CWE Reference**: CWE-117 (Improper Output Neutralization for Logs), CWE-20 (Improper Input Validation)

**Recommendation**:
```python
def __init__(
    self,
    agent_name: str,
    feature: str,
    log_to_file: bool = False,
    log_path: Optional[Path] = None
):
    """Initialize performance timer."""
    self.agent_name = validate_agent_name(agent_name, "performance timer initialization")
    # Use validate_input_length to check length AND sanitize content
    self.feature = validate_input_length(
        feature, 
        500, 
        "feature", 
        "performance timer feature description"
    )
    # ... rest of init ...

# Note: validate_input_length() validates length. For complete security,
# add a sanitize_log_output() function to remove null bytes and control chars:

def sanitize_log_output(value: str) -> str:
    \"\"\"Remove characters that could break log parsing.\"\"\"
    # Remove null bytes and control characters (except tab, newline in JSON)
    sanitized = ''.join(
        c for c in value 
        if ord(c) >= 32 or c in '\t'  # Keep printable chars + tab
    )
    return sanitized
```

**Severity Justification**: Medium - JSON encoding provides defense-in-depth, but null bytes and newlines in NDJSON could cause log parsing issues. Not an RCE risk but violates log integrity principles.

---

## SECURITY CHECKS COMPLETED

### Secrets & Credentials
- ✅ No hardcoded API keys detected
- ✅ No passwords in plaintext
- ✅ No tokens or secrets in code
- ✅ No credentials in agent configs (researcher.md, planner.md)

### Input Validation
- ❌ **FAILED**: agent_name parameter not validated (see Vulnerability #1)
- ❌ **FAILED**: feature parameter uses naive truncation, not validated sanitization (see Vulnerability #3)
- ⚠️ **PARTIAL**: log_path parameter accepts arbitrary paths without whitelist validation (see Vulnerability #2)

### Path Traversal & File Access (CWE-22)
- ❌ **FAILED**: custom log_path not validated against whitelist (see Vulnerability #2)
- ✅ DEFAULT_LOG_PATH is safe (within project directory)
- ⚠️ mkdir() is called without prior path validation

### JSON Injection & Log Parsing (CWE-117)
- ❌ **FAILED**: feature string not sanitized for special characters (see Vulnerability #3)
- ✅ JSON encoding prevents code injection (json.dumps handles escaping)
- ⚠️ NDJSON format (one JSON per line) vulnerable to newlines in feature field

### Thread Safety & Concurrent Access
- ✅ Uses threading.Lock() for concurrent writes to logs
- ✅ Thread lock properly scoped (global _write_lock)
- ✅ Atomic writes pattern (acquire lock, write, release)

### Resource Exhaustion (DoS Prevention)
- ✅ Feature description truncated to 500 characters (prevents unbounded log growth)
- ✅ No infinite loops or unbounded allocations
- ⚠️ Log file size not limited (could grow indefinitely)
- ⚠️ No rotation policy (security_utils has rotating file handler with 10MB limit, performance_profiler doesn't)

### Error Handling
- ✅ Exception handling in __exit__ (logs errors but doesn't suppress exceptions)
- ✅ JSON parsing errors handled gracefully (skip_corrupted parameter)
- ✅ File I/O errors logged but don't crash profiler

### Authorization & Authentication
- ✅ No authentication mechanisms needed (internal profiling tool)
- ✅ Not exposed to external APIs

### Agent Configuration (researcher.md, planner.md)
- ✅ researcher.md model change (haiku) is performance optimization, no security impact
- ✅ planner.md prompt simplification has no security concerns
- ✅ Both agent configs properly restrict tool access

---

## RECOMMENDATIONS (Priority Order)

### CRITICAL (Must Fix Before Merge)
1. **Add input validation to PerformanceTimer.__init__()**
   - Use `validate_agent_name()` from security_utils
   - Use `validate_input_length()` for feature parameter
   - Validates and sanitizes inputs per CWE-20 and CWE-117

2. **Validate custom log_path parameter**
   - Use `validate_path()` from security_utils for custom log_path
   - Prevents CWE-22 path traversal attacks
   - Allow missing=True since log files don't exist until first write

3. **Sanitize special characters in feature field**
   - Remove null bytes and control characters that could break log parsing
   - Prevents log parsing attacks per CWE-117

### HIGH (Should Fix in Next Phase)
4. **Add log rotation like security_utils does**
   - Implement RotatingFileHandler (10MB max, 5 backups)
   - Prevents unbounded log growth and disk exhaustion
   - Consider moving to use audit_log() from security_utils for consistency

5. **Add audit logging for performance metrics**
   - Log when performance falls below baselines
   - Log when profiling overhead exceeds 5%
   - Integrates with security audit trail

### MEDIUM (Nice to Have)
6. **Validate metric values**
   - Ensure duration is non-negative (already handles negative duration with warning)
   - Validate that timestamp strings are valid ISO 8601
   - Validate agent names when aggregating metrics

7. **Document security assumptions**
   - Add SECURITY.md section explaining trust boundaries
   - Document that performance_profiler is internal-only (not exposed to user input)
   - List CWE vulnerabilities addressed

---

## CWE COVERAGE ANALYSIS

| CWE | Vulnerability | Status | Impact |
|-----|---|---|---|
| **CWE-20** | Improper Input Validation | FAIL | agent_name and feature not validated |
| **CWE-22** | Path Traversal | FAIL | custom log_path not validated |
| **CWE-117** | Improper Log Output Neutralization | FAIL | feature string not sanitized |
| **CWE-400** | Uncontrolled Resource Consumption | WARN | No log rotation policy |

---

## COMPARISON WITH security_utils.py

### How performance_profiler SHOULD follow security_utils patterns:

**security_utils provides**:
1. `validate_path()` - 4-layer whitelist validation (CWE-22 defense)
2. `validate_agent_name()` - Alphanumeric + hyphen/underscore only
3. `validate_input_length()` - Prevent unbounded strings
4. `audit_log()` - Thread-safe JSON audit logging with rotation
5. `_get_audit_logger()` - RotatingFileHandler (10MB, 5 backups)

**performance_profiler currently does**:
- Uses default log path (safe) ✓
- Uses threading.Lock for concurrent writes ✓
- Manually truncates feature string (incomplete) ✗
- Doesn't validate agent_name ✗
- Doesn't validate custom log_path ✗
- Doesn't use audit_log pattern ✗
- No log rotation (unbounded growth) ✗

---

## TEST COVERAGE NOTES

Good news: Test suite exists with 22 test methods covering:
- Timer context manager interface
- Duration measurement accuracy
- Metadata capture
- JSON serialization
- Log file writing
- Concurrent writes (thread safety)
- Metric aggregation
- Report generation

Recommended test additions:
1. Test malicious agent_name with special characters (currently passes through)
2. Test custom log_path with path traversal attempts (currently no validation)
3. Test feature string with null bytes and newlines (currently not sanitized)
4. Test aggregate_metrics_by_agent with corrupted metric data

---

## FINAL ASSESSMENT

**Security Status**: FAIL
**Severity**: MEDIUM (3 medium vulnerabilities)
**Risk Level**: Medium
**Recommendation**: Block merge until vulnerabilities #1-3 are fixed

The performance_profiler.py module has 3 medium-severity input validation and path traversal issues that violate the security patterns established in security_utils.py. The module doesn't leverage the existing centralized security functions, creating unnecessary security gaps.

**Timeline**:
- Fix #1-3: 30 minutes (add 3 validate calls)
- Add tests for malicious inputs: 20 minutes
- Code review: 10 minutes
- Total: ~1 hour to full security compliance

The agent config changes (researcher.md, planner.md) have no security implications - they are performance optimizations and documentation updates.

---

**Generated**: 2025-11-08 by security-auditor agent
**Reference**: CWE-20, CWE-22, CWE-117, CWE-400
**Compliance**: OWASP A01:2021 (Broken Access Control), A03:2021 (Injection), A04:2021 (Insecure Design)
