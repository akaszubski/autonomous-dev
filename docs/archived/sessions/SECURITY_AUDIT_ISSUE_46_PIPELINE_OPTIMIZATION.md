# Security Audit Report: Issue #46 (Pipeline Optimization)

**Audit Date**: November 7, 2025
**Auditor**: security-auditor agent
**Severity Level**: CRITICAL
**Overall Status**: FAIL

---

## Executive Summary

The test mode implementation in `scripts/agent_tracker.py` introduces a **CRITICAL** security vulnerability that allows attackers to write arbitrary files to sensitive system directories. The vulnerability exists because the test mode path validation uses an incomplete blocklist that fails to protect critical system paths like `/var/log/`, `/var/lib/`, `/root/`, and `/opt/`.

**Key Finding**: An attacker can bypass all path validation by:
1. Setting the `PYTEST_CURRENT_TEST` environment variable
2. Providing paths to sensitive system directories (e.g., `/var/log/session.json`)
3. The code accepts these paths because they don't contain `..`, don't start with `/etc/`, and don't start with `/usr/`

**Impact**: 
- Arbitrary file write to system directories
- Potential system compromise via log poisoning or config file modification
- Information disclosure through reading permissions on world-writable directories

---

## Vulnerabilities Found

### CRITICAL: Incomplete System Directory Blocklist in Test Mode

**Severity**: CRITICAL (CVSS 9.8)

**Issue**: Path validation in test mode uses a string-based blocklist that is fundamentally incomplete.

**Location**: `/Users/akaszubski/Documents/GitHub/autonomous-dev/scripts/agent_tracker.py`
- Lines 196-220: Test mode detection and path validation
- Specifically line 215: `if ".." in path_str or path_str.startswith("/etc/") or path_str.startswith("/usr/"):`

**Vulnerable Code**:
```python
else:
    # Test mode: Allow temp directories but block obvious attacks
    path_str = str(resolved_path)
    if ".." in path_str or path_str.startswith("/etc/") or path_str.startswith("/usr/"):
        raise ValueError(...)
```

**Attack Vector**: 
1. Attacker controls environment variable `PYTEST_CURRENT_TEST` (set to any non-empty value)
2. Attacker provides path like `/var/log/session.json` or `/root/.bash_history`
3. Path validation passes because:
   - Does NOT contain `..` sequences
   - Does NOT start with `/etc/`
   - Does NOT start with `/usr/`
4. File is written to sensitive system directory
5. Potential system compromise

**Unblocked Dangerous Paths** (all writable in test mode):
- `/var/log/` - System logs (potential DoS, log injection)
- `/var/lib/` - Package data and persistent storage
- `/var/run/` - Runtime data (PIDs, sockets)
- `/var/tmp/` - System temporary files
- `/root/` - Root home directory
- `/opt/` - Optional software installations
- `/srv/` - Service data
- `/home/` - User home directories
- `/tmp/` - Only blocked if contains `../` which is rare

**Production Impact**:
- ZERO if `PYTEST_CURRENT_TEST` is ONLY set by pytest (no production exposure)
- CRITICAL if environment variable can be injected in production
- CRITICAL if developers accidentally run production code with pytest environment

---

### HIGH: Insufficient Environment Variable Protection

**Severity**: HIGH

**Issue**: The code relies on a single environment variable (`PYTEST_CURRENT_TEST`) to disable critical security checks. This is insufficient because:

1. **Environment Variable Can Be Spoofed**: Any process can set `PYTEST_CURRENT_TEST`
   - Malicious subprocess: `os.environ["PYTEST_CURRENT_TEST"] = "test"`
   - Docker escape: Injected via container environment
   - CI/CD misconfiguration: Leftover from test runs
   - Supply chain attack: Compromised dependency sets this variable

2. **No Verification It's Actually Pytest**: 
   - Code only checks if variable EXISTS, not if it matches pytest's specific value
   - pytest sets `PYTEST_CURRENT_TEST` to format: `path/to/test.py::TestClass::test_method (call)`
   - Code could verify the format, but doesn't

3. **No Audit Trail**: 
   - No logging when test mode is activated
   - No way to detect malicious test mode activation in production

**Code Location**: Lines 196, 422, 475, 550 (all instances):
```python
is_test_mode = os.getenv("PYTEST_CURRENT_TEST") is not None
```

**Attack Scenario**:
```python
# Attacker-controlled code
import os
os.environ["PYTEST_CURRENT_TEST"] = "anything"  # Bypass security

# Now create tracker with restricted path
from scripts.agent_tracker import AgentTracker
tracker = AgentTracker(session_file="/var/log/injection.json")
# SUCCESS - File written to /var/log/
```

---

### HIGH: Blacklist-Based Path Validation

**Severity**: HIGH

**Issue**: The test mode uses a blacklist approach (reject known bad paths) instead of a whitelist approach (only allow known good paths). Blacklist approaches are inherently incomplete:

**Blacklist Gaps**:
```
Current blocklist:
  - Explicitly blocks: /etc/, /usr/
  - String check: Rejects paths containing ".."
  
Gaps that allow exploitation:
  - /var/log/          [NOT BLOCKED]
  - /var/lib/          [NOT BLOCKED]
  - /var/cache/        [NOT BLOCKED]
  - /var/spool/        [NOT BLOCKED]
  - /var/run/          [NOT BLOCKED]
  - /opt/              [NOT BLOCKED]
  - /root/             [NOT BLOCKED]
  - /home/             [NOT BLOCKED]
  - /srv/              [NOT BLOCKED]
  - /lib/              [NOT BLOCKED] - symlink to /usr/lib but separate entry
  - /bin/              [NOT BLOCKED] - symlink to /usr/bin but separate entry
  - /sbin/             [NOT BLOCKED] - symlink to /usr/sbin but separate entry
```

**Production Code Does Better**: 
In production mode (non-test), code uses whitelist approach:
```python
resolved_path.relative_to(PROJECT_ROOT)  # Only allows paths within project
```

This is secure. Test mode should use the same approach but with a different whitelist (temp directory).

---

### MEDIUM: Race Condition in Test Mode Activation

**Severity**: MEDIUM

**Issue**: No synchronization between reading `PYTEST_CURRENT_TEST` and using its value for validation decisions. Between checking:

```python
is_test_mode = os.getenv("PYTEST_CURRENT_TEST") is not None
# ... code ...
if not is_test_mode:
    # Production validation
else:
    # Test validation
```

Another thread could modify `os.environ["PYTEST_CURRENT_TEST"]`, but this is unlikely in practice since pytest sets it once at startup.

---

## Security Checks Completed

### Authentication & Authorization
- Status: NOT APPLICABLE - Code doesn't implement auth
- Note: No user credentials or access control present

### Input Validation
- Status: CRITICAL FAILURE
  - Path validation: INCOMPLETE BLOCKLIST
  - Agent name validation: Weakly bypassed in test mode (allows any string)
  - Message length: PASS (10KB limit enforced)
  - GitHub issue number: PASS (range validation present)

### Secrets Management
- Status: PASS
  - No hardcoded API keys, tokens, or credentials found
  - No secret patterns detected in code
  - Uses environment variables appropriately (when not bypassed)

### Path Traversal Protection
- Status: CRITICAL FAILURE in test mode
  - Production mode: PASS (whitelist to PROJECT_ROOT)
  - Test mode: FAIL (incomplete blacklist)
  - Symlink protection: PASS (is_symlink() check present)
  - .. sequence blocking: PASS (string check present, but test mode bypasses spirit)

### Atomic File Operations
- Status: PASS
  - Uses tempfile.mkstemp() and atomic rename pattern
  - Temp file cleanup on error: PASS
  - No partial writes possible: PASS

### Race Condition Prevention
- Status: PASS (for file operations)
  - Atomic rename prevents partial writes
  - mkstemp ensures unique temp files
  - Note: No file locking, but atomic rename sufficient

### Error Handling
- Status: PASS
  - Detailed error messages with context
  - Temp file cleanup in exception handlers
  - No secrets leaked in error messages

### OWASP Top 10 Alignment
- A01: Broken Access Control - PASS (no auth/authz vulnerabilities, but test mode is a form of broken access)
- A02: Cryptographic Failures - N/A (no encryption)
- A03: Injection - CRITICAL FAILURE (path injection via test mode bypass)
- A04: Insecure Design - CRITICAL (test mode security model is fundamentally flawed)
- A05: Security Misconfiguration - CRITICAL (environment variable used for security decision)
- A06: Vulnerable Components - N/A (no external dependencies with known vulns)
- A07: Authentication Failures - N/A (no auth implemented)
- A08: Data Integrity Failures - PASS (atomic writes prevent corruption)
- A09: Logging & Monitoring Failures - FAIL (no audit log when test mode activated)
- A10: SSRF - N/A (no HTTP calls)

---

## Root Cause Analysis

The test mode implementation attempts to solve a legitimate problem (tests need temp directories outside PROJECT_ROOT) with an insufficient security model.

**The Problem Being Solved**:
- Integration tests need to write session files to temp directories (`/tmp/`, pytest's `tmp_path`)
- These temp directories are outside `PROJECT_ROOT` and fail validation
- Without test mode, 51 tests fail (as noted in session log)

**The Flawed Solution**:
1. Check if `PYTEST_CURRENT_TEST` environment variable exists
2. If test mode: Disable PROJECT_ROOT whitelist validation
3. Instead: Use incomplete string-based blacklist to block "obvious" attacks
4. Result: Incomplete protection of sensitive system directories

**What Should Have Been Done**:
1. In test mode: Validate path is within pytest's temp directory (e.g., `/tmp/pytest-*`)
2. OR: Add a parameter to AgentTracker to specify allowed base directories
3. OR: Create a separate `AgentTrackerForTests` class with appropriate validation
4. OR: Mock the file operations in tests instead of using real paths

---

## Proof of Concept

This vulnerability allows:

```python
import os
from pathlib import Path
from scripts.agent_tracker import AgentTracker

# Step 1: Enable test mode (attacker controls this)
os.environ["PYTEST_CURRENT_TEST"] = "test.py::test_func (setup)"

# Step 2: Attempt to write to /var/log
try:
    tracker = AgentTracker(session_file="/var/log/malicious.json")
    print("SUCCESS: Created tracker with /var/log path!")
    print(f"Session file: {tracker.session_file}")
    # File could now be written to
except ValueError as e:
    print(f"BLOCKED: {e}")

# Step 3: Attempt to write to /var/lib
try:
    tracker = AgentTracker(session_file="/var/lib/apt/malicious.json")
    print("SUCCESS: Created tracker with /var/lib path!")
except ValueError as e:
    print(f"BLOCKED: {e}")

# Step 4: Attempt to write to /root
try:
    tracker = AgentTracker(session_file="/root/.bashrc-injected.json")
    print("SUCCESS: Created tracker with /root path!")
except ValueError as e:
    print(f"BLOCKED: {e}")

# Step 5: Confirm write would work
try:
    tracker = AgentTracker(session_file="/var/log/session.json")
    tracker.start_agent("attacker", "Injected data")
    print("File written to /var/log/session.json")
except Exception as e:
    print(f"Write blocked: {e}")
```

---

## Recommendations

### CRITICAL - Must Fix Before Deployment

1. **Replace Blacklist With Whitelist in Test Mode**
   - Instead of rejecting known-bad paths, only allow known-good paths
   - Whitelist test mode paths to pytest's temp directory or explicit allow-list
   
   **Fix**:
   ```python
   if is_test_mode:
       # Whitelist approach: only allow temp directories
       temp_dirs = [
           Path(tempfile.gettempdir()),  # /tmp on Unix
           Path(os.getenv("TMPDIR", "/tmp")),  # TMPDIR env var
           Path(os.getenv("TEMP", "/tmp")),    # TEMP env var
           Path("/var/folders"),  # macOS temp (if needed)
       ]
       
       resolved_path = Path(session_file).resolve()
       
       # Check if path is within any temp directory
       is_in_temp = any(
           resolved_path.is_relative_to(temp_dir)
           for temp_dir in temp_dirs
           if temp_dir.exists()
       )
       
       if not is_in_temp:
           raise ValueError(
               f"Test mode path must be in temp directory\n"
               f"Allowed: {[str(d) for d in temp_dirs]}\n"
               f"Got: {resolved_path}"
           )
   ```

2. **Validate PYTEST_CURRENT_TEST Format**
   - Check that the environment variable matches pytest's format
   - Harder to spoof if checking actual format
   
   **Fix**:
   ```python
   def is_pytest_running():
       """Verify pytest is actually running, not just env var set."""
       pytest_var = os.getenv("PYTEST_CURRENT_TEST", "")
       # pytest format: "path/to/test.py::ClassName::test_name (STAGE)"
       # Stages: (setup), (call), (teardown)
       return " (" in pytest_var and ")" in pytest_var
   ```

3. **Add Audit Logging**
   - Log when test mode is activated
   - Helps detect malicious test mode activation
   
   **Fix**:
   ```python
   if is_test_mode:
       import logging
       logging.warning(f"Test mode activated. PYTEST_CURRENT_TEST={os.getenv('PYTEST_CURRENT_TEST')}")
   ```

4. **Create Separate Test Helper Class**
   - Instead of modifying production code with test mode, create a test-specific variant
   
   **Fix**:
   ```python
   class AgentTrackerForTests(AgentTracker):
       """Test variant with relaxed path validation."""
       
       def __init__(self, session_file: Optional[str] = None):
           # Allow temp directories but still validate paths
           if session_file:
               self.session_file = Path(session_file)
               # Check within temp directory
               temp_dir = Path(tempfile.gettempdir())
               if not self.session_file.resolve().is_relative_to(temp_dir):
                   raise ValueError(f"Must be in temp dir: {temp_dir}")
           super().__init__(session_file)
   ```

### HIGH - Should Fix

5. **Add Parameter to Control Allowed Paths**
   - Let callers specify allowed base directories instead of relying on env vars
   
   **Fix**:
   ```python
   def __init__(
       self,
       session_file: Optional[str] = None,
       allowed_base_dirs: Optional[List[Path]] = None
   ):
       """Initialize with explicit control over allowed directories."""
       if allowed_base_dirs is None:
           allowed_base_dirs = [PROJECT_ROOT]
       # Validate path is within one of allowed_base_dirs
   ```

6. **Document Test Mode Limitations**
   - Add warning to docstring about test mode security model
   - Explain why tests use AgentTrackerForTests instead
   
   **Fix**:
   ```python
   """
   WARNING: Test mode (PYTEST_CURRENT_TEST env var) disables some security checks.
   
   MUST ONLY BE USED IN TEST ENVIRONMENT.
   
   If running production code, this class will enforce strict path validation.
   For tests, use AgentTrackerForTests instead.
   
   See: docs/SECURITY.md#test-mode for detailed explanation.
   """
   ```

### MEDIUM - Nice To Have

7. **Add Path Normalization Checks**
   - Detect and reject encoded traversal attempts (%, URL encoding, etc.)
   
8. **Add Symlink Loop Detection**
   - Detect and prevent symlink loops that could cause DoS
   
9. **Add File Descriptor Limits**
   - Prevent FD exhaustion if temp files not cleaned up

---

## Test Coverage Analysis

**Current Security Tests**: 38 tests in `test_agent_tracker_security.py`

**Coverage Status**: 
- Path traversal prevention: GOOD (relative paths, absolute paths, symlinks)
- Test mode path validation: **MISSING** - No tests verify the incomplete blocklist
- System directory blocking: WEAK - Only tests `/etc/` and `/usr/`

**Missing Test Cases**:
```python
def test_var_log_path_writable_in_test_mode(tracker):
    """Test that /var/log paths CAN be written in test mode (VULNERABILITY!)"""
    os.environ["PYTEST_CURRENT_TEST"] = "test"
    tracker = AgentTracker(session_file="/var/log/malicious.json")
    # This should fail but currently passes

def test_var_lib_path_writable_in_test_mode(tracker):
    """Test that /var/lib paths CAN be written in test mode (VULNERABILITY!)"""
    os.environ["PYTEST_CURRENT_TEST"] = "test"
    tracker = AgentTracker(session_file="/var/lib/malicious.json")
    # This should fail but currently passes

def test_root_path_writable_in_test_mode(tracker):
    """Test that /root paths CAN be written in test mode (VULNERABILITY!)"""
    os.environ["PYTEST_CURRENT_TEST"] = "test"
    tracker = AgentTracker(session_file="/root/.bashrc-injected")
    # This should fail but currently passes
```

---

## Impact Assessment

**Severity**: CRITICAL
**Exploitability**: HIGH (environment variable is commonly set in CI/CD)
**Discoverability**: MEDIUM (requires understanding of path validation)
**Impact**: HIGH (arbitrary file write to system directories)

**CVSS v3.1 Score**: 9.8 CRITICAL
- Attack Vector: Network (if running in networked service)
- Attack Complexity: Low (just set env var and pass path)
- Privileges Required: Low (any process can set env var)
- User Interaction: None
- Scope: Unchanged
- Confidentiality: High (can read files if overwriting changes permissions)
- Integrity: High (can write/modify files)
- Availability: High (can delete critical files or cause DoS)

---

## Compliance

**OWASP A04: Insecure Design** - VIOLATED
- Security model relies on incomplete blocklist approach
- No proper separation between test and production code paths

**OWASP A05: Security Misconfiguration** - VIOLATED
- Uses environment variable for critical security decision
- Configuration is implicit, not explicit

---

## Conclusion

The Issue #46 (Pipeline Optimization) implementation introduces a CRITICAL path traversal vulnerability through an incomplete test mode. While the underlying problem (tests needing temp directories) is legitimate, the solution is fundamentally flawed because:

1. It uses a blacklist approach instead of whitelist
2. The blocklist is incomplete and misses many sensitive system paths
3. It relies on environment variable that can be spoofed
4. It provides no audit trail when activated

**Recommendation**: REJECT this implementation and use whitelist approach or separate test class instead.

---

**Auditor**: security-auditor agent
**Date**: 2025-11-07
**Status**: CRITICAL - DO NOT MERGE
