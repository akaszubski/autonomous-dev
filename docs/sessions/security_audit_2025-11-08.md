# Security Audit: sync_dispatcher.py
**Date**: 2025-11-08  
**Auditor**: security-auditor agent  
**File**: `/plugins/autonomous-dev/lib/sync_dispatcher.py`  
**Scope**: Integration of version_detector and orphan_file_cleaner (lines 565-960)

---

## Executive Summary

**Overall Status**: FAIL

The security audit identified **1 CRITICAL vulnerability** related to symlink attack vector (CWE-59). The implementation validates paths, but performs validation **AFTER** calling `.exists()` on untrusted data, allowing attackers to bypass security checks through symlink race conditions.

---

## Vulnerabilities Found

### CRITICAL: Symlink Attack via Path.exists() Before Validation (CWE-59)

**Issue**: Path validation occurs AFTER existence check, creating a race condition window where symlinks can escape validation bounds.

**Location**: `/plugins/autonomous-dev/lib/sync_dispatcher.py:692-710`

```python
# Line 692-693: VULNERABLE - .exists() called before validation
plugin_path = Path(plugin_info.get("path", ""))
if not plugin_path.exists():  # <-- SYMLINK CHECK HAPPENS HERE
    return SyncResult(...)

# Line 703-710: Validation happens AFTER
try:
    plugin_path = validate_path(str(plugin_path), "marketplace plugin directory")
except ValueError as e:
    # ... handle error
```

**Attack Vector**: 
1. Attacker controls `installed_plugins.json` marketplace file
2. Sets `"path": "/tmp/attacker_symlink"` where symlink -> `/etc/sensitive_data`
3. `.exists()` check at line 693 resolves symlink and returns True
4. Symlink is then deleted/replaced before `validate_path()` call at line 703
5. `validate_path()` checks the NEW target (which is whitelisted), validation passes
6. Subsequent file operations use original symlink pointing to `/etc/`

**Impact**: Arbitrary file read/write outside project root via symlink substitution attack.

**Recommendation**:
Call `validate_path()` IMMEDIATELY after extracting untrusted path, BEFORE calling any methods that resolve symlinks (`.exists()`, `.is_dir()`, etc.).

```python
# SECURE: Validate FIRST
plugin_path = Path(plugin_info.get("path", ""))
try:
    plugin_path = validate_path(str(plugin_path), "marketplace plugin directory")
except ValueError as e:
    # ... handle error

# THEN check existence (now safe - path is validated)
if not plugin_path.exists():
    return SyncResult(...)
```

---

## Security Checks Completed

### Path Validation
- **Status**: PASS with critical caveat
- **Finding**: `validate_path()` is comprehensive (4-layer defense: string checks, symlink detection, path resolution, whitelist validation)
- **Issue**: Applied too late in execution flow (after path resolution via `.exists()`)

### Secret Handling
- ✅ **PASS**: No hardcoded API keys, passwords, or tokens in source code
- ✅ **PASS**: `.env` file is properly gitignored (line 1 of `.gitignore`)
- ✅ **PASS**: No secrets in git history (git log -S scan found no matches)
- ✅ **PASS**: All file operations use filesystem paths, not credentials

### Input Validation
- ✅ **PASS**: JSON parsing has exception handling (lines 669-678)
- ✅ **PASS**: Plugin path extracted safely via `.get()` with default empty string (line 692)
- ✅ **PASS**: marketplace_plugins_file validated before use (lines 638-650)
- ❌ **FAIL**: Validation order vulnerability (CWE-59) - see Critical issue above

### File Operations Security
- ✅ **PASS**: Uses `shutil.copytree()` with `dirs_exist_ok=True` (safe, atomic operations)
- ✅ **PASS**: Backup/rollback mechanism prevents data loss on failure (lines 851-890)
- ✅ **PASS**: All paths are validated or generated internally (no untrusted path concatenation)
- ⚠️ **CONCERN**: File operations follow unvalidated symlink at line 737+ (due to validation order issue)

### Authentication & Authorization
- ✅ **PASS**: No authentication required (sync is filesystem-local operation)
- ✅ **PASS**: File permissions respected (uses existing file permissions, no privilege escalation)
- ✅ **PASS**: User context tracked in audit logs (lines 232, audit_log includes USER env var)

### Audit Logging
- ✅ **PASS**: All security-critical operations logged (path validation, version detection, orphan cleanup)
- ✅ **PASS**: Audit log includes context (operation, path, error, user)
- ✅ **PASS**: Failures logged explicitly (lines 320-325, 645-648, 704-710)

### OWASP Top 10 Compliance

| Risk | Status | Finding |
|------|--------|---------|
| **A01: Broken Access Control** | PASS | File operations respect OS-level permissions; no privilege escalation |
| **A02: Cryptographic Failures** | PASS | No sensitive data stored; uses standard file operations |
| **A03: Injection** | PASS | All file paths validated; JSON safely parsed with exception handling |
| **A04: Insecure Design** | PASS | Backup/rollback pattern prevents data loss; validation framework in place |
| **A05: Security Misconfiguration** | PASS | Uses whitelisted directories only; denies by default |
| **A06: Vulnerable Components** | N/A | Uses standard library only (shutil, json, pathlib) |
| **A07: Identification & Auth** | PASS | No authentication needed (local filesystem operation) |
| **A08: Software Data Integrity** | FAIL | Symlink TOCTOU (Time-Of-Check-Time-Of-Use) vulnerability exists |
| **A09: Logging & Monitoring** | PASS | Comprehensive audit logging with JSON format and rotation |
| **A10: SSRF** | N/A | No network operations; filesystem-only |

---

## Detailed Analysis

### Path Validation Framework (Positive)

The codebase implements a strong 4-layer validation approach in `security_utils.py`:

1. **String-level checks** (line 233): Reject `..` and excessively long paths
2. **Symlink detection** (line 252): Reject symlinks before resolution
3. **Path resolution** (line 265): Normalize to absolute path
4. **Whitelist validation** (line 282): Ensure path in PROJECT_ROOT or test temp

**However**: This framework is undermined by calling `.exists()` before validation.

### The TOCTOU (Time-Of-Check-Time-Of-Use) Vulnerability

```
Timeline of attack:

T0: Attacker creates symlink: /tmp/link -> /etc/passwd
T1: Code calls plugin_path.exists() ✓ (resolves symlink, returns True)
T2: Attacker quickly replaces symlink: /tmp/link -> /usr/local/bin/malware
T3: Code calls validate_path() ✓ (validates /usr/local/bin/malware if in whitelist)
T4: Code calls shutil.copytree(plugin_path, ...) (copies from /tmp/link)
T5: But T2 occurred between T1 and T4, so symlink now points to /usr/local/bin/

Race window is short but exploitable on systems with task scheduling pressure.
```

### Why `.exists()` Before Validation is Dangerous

From Python docs: `Path.exists()` **resolves symlinks before checking existence**.

```python
# If /tmp/link -> /system/protected
link = Path("/tmp/link")
link.exists()  # Returns True (resolved symlink target)
link.is_symlink()  # Returns True (but after .exists() called)
```

The code checks for symlinks AFTER resolution, which can return False if symlink is quickly replaced.

---

## Recommendations

### Priority 1: Fix Validation Order (IMMEDIATE)

Move `validate_path()` to execute BEFORE any path resolution:

```python
# Line 692-710 CURRENT (VULNERABLE)
plugin_path = Path(plugin_info.get("path", ""))
if not plugin_path.exists():
    return SyncResult(...)

try:
    plugin_path = validate_path(str(plugin_path), "marketplace plugin directory")
except ValueError as e:
    # ...

# LINE 692-710 SECURE (RECOMMENDED)
plugin_path = Path(plugin_info.get("path", ""))

# Validate FIRST (before any path resolution)
try:
    plugin_path = validate_path(str(plugin_path), "marketplace plugin directory")
except ValueError as e:
    audit_log("security_violation", "marketplace_path_invalid", {...})
    return SyncResult(...)

# THEN check existence (now safe - path already validated)
if not plugin_path.exists():
    return SyncResult(...)
```

### Priority 2: Apply Same Fix to _dispatch_marketplace() and _dispatch_plugin_dev()

Same vulnerability exists at:
- Line 376-382 (MARKETPLACE mode)
- Line 468-474 (PLUGIN_DEV mode)

Apply identical fix: validate before calling `.exists()`.

### Priority 3: Document Security Assumptions

Add comment to `sync_dispatcher.py` explaining:
- Assumption: `installed_plugins.json` is controlled by Claude Code (trusted source)
- Rationale: File is in user's `.claude/` directory, not attacker-writable
- If assumption changes, add file integrity checks (HMAC signature verification)

### Priority 4: Consider Atomic Validation

If symlink-free paths are critical, use Python 3.11+ `Path.readlink()` with explicit error handling:

```python
def validate_no_symlinks(path: Path) -> Path:
    """Resolve path while detecting symlinks in any component."""
    current = Path("/")
    for part in path.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Symlink detected: {current}")
    return current.resolve()
```

---

## Risk Assessment

### Current Risk Level: HIGH

**Without fix**: Attacker with write access to `installed_plugins.json` can:
- Read sensitive files from system directories
- Write malicious code to .claude/ directory
- Potentially escape sandbox via file copy operations

**Likelihood**: Medium (requires attacker control of marketplace file)  
**Impact**: High (arbitrary filesystem access)  
**Overall**: HIGH risk

---

## Test Coverage

Recommend adding test case for this vulnerability:

```python
def test_sync_marketplace_rejects_symlink_attack():
    """Test that symlinks are rejected even if initially resolving."""
    
    # Create temp directories
    with tempfile.TemporaryDirectory() as tmpdir:
        project = Path(tmpdir) / "project"
        project.mkdir()
        
        # Create malicious symlink
        symlink = Path(tmpdir) / "plugin_symlink"
        system_path = Path("/etc/passwd")
        symlink.symlink_to(system_path)
        
        # Create marketplace file pointing to symlink
        marketplace_file = Path(tmpdir) / "installed_plugins.json"
        marketplace_file.write_text(json.dumps({
            "autonomous-dev": {"path": str(symlink)}
        }))
        
        # Attempt sync - should FAIL with security error
        dispatcher = SyncDispatcher(str(project))
        result = dispatcher.sync_marketplace(marketplace_file)
        
        assert result.success is False
        assert "security" in result.error.lower() or "symlink" in result.error.lower()
```

---

## Summary

**Vulnerabilities**: 1 CRITICAL (Symlink TOCTOU)  
**Status**: FAIL (requires fix before production use)  
**Fix Complexity**: LOW (reorder validation calls, ~5 lines changed)  
**Timeline to Fix**: 15-30 minutes

The codebase has strong security fundamentals (path validation framework, audit logging, backup/rollback), but is undermined by a simple execution order issue that allows symlink attacks to bypass security checks through a time-of-check-time-of-use race condition.

**Recommendation**: Fix validation order immediately (Priority 1), then re-audit.

