# Security Audit: Issue #50 Phase 2 (/update-plugin Command)

**Date**: 2025-11-09  
**Agent**: security-auditor  
**Files Audited**:
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/lib/plugin_updater.py` (658 lines)
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/lib/update_plugin.py` (378 lines)
- `/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/commands/update-plugin.md`

---

## Security Status

**Overall**: FAIL - Multiple critical syntax and security issues must be fixed before merge

**Critical Issues**: 4  
**High Issues**: 2  
**Medium Issues**: 1  
**Low Issues**: 1

---

## Vulnerabilities Found

### [CRITICAL]: Malformed audit_log() Calls - Syntax Errors

**Issue**: Multiple audit_log() calls have broken syntax with unclosed parentheses and mismatched brackets. This causes the entire module to fail Python parsing.

**Locations**:
1. `plugin_updater.py:228-241` - `check_for_updates` audit log
2. `plugin_updater.py:246-254` - `check_for_updates_error` audit log  
3. `plugin_updater.py:387-393` - `update_success` audit log
4. `plugin_updater.py:419-428` - `rollback_failed` audit log
5. `plugin_updater.py:434-442` - `update_error` audit log
6. `plugin_updater.py:486-493` - `backup_empty` audit log
7. `plugin_updater.py:509-515` - `plugin_backup_created` audit log
8. `plugin_updater.py:553-559` - `plugin_rollback` audit log
9. `plugin_updater.py:584-591` - `backup_cleanup_error` audit log
10. `plugin_updater.py:598-604` - `plugin_backup_cleanup` audit log
11. `plugin_updater.py:642-648` - `verification_success` audit log

**Pattern**: All malformed calls follow the same broken pattern:
```python
security_utils.audit_log(
    "event_type",
    "status",
    {
        "key": "value",
        "path": str(some_path,  # <-- Missing closing paren for str()
    },
),  # <-- Extra closing paren and comma for dict closing brace
    extra_arg=value,  # <-- Arguments AFTER closing dict paren (invalid)
)
```

**Attack Vector**: Cannot exploit - syntax error prevents module from loading. Security measures never execute.

**Recommendation**: 
Fix all audit_log() calls to follow correct syntax:
```python
security_utils.audit_log(
    "event_type",
    "status",
    {
        "key": "value",
        "path": str(some_path),
        "extra_arg": value,
    },
)
```
The third parameter to audit_log() is a dict context. All key-value pairs should be INSIDE the dict, not after it.

---

### [CRITICAL]: Unvalidated marketplace_file Path - CWE-22

**Issue**: The marketplace file path is hardcoded without path validation:
```python
marketplace_file = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
```

While `Path.home()` is safe, the path is passed directly to `sync_marketplace()` without validating it through `security_utils.validate_path()`. This bypasses the security layer.

**Location**: `plugin_updater.py:316-321`

**Attack Vector**: 
- If `Path.home()` is compromised or symlinked
- If sync_dispatcher doesn't validate marketplace_file path internally
- Potential to read/write files outside project scope

**Recommendation**: Validate the marketplace_file path before passing to sync_marketplace():
```python
marketplace_file = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
try:
    # Validate marketplace file exists and is within user's home directory
    validated_file = security_utils.validate_path(
        str(marketplace_file), 
        "marketplace plugins file"
    )
except ValueError as e:
    raise UpdateError(f"Invalid marketplace file path: {e}")

sync_result = sync_marketplace(
    project_root=str(self.project_root),
    marketplace_plugins_file=validated_file,
    ...
)
```

---

### [CRITICAL]: Backup Directory Permissions Not Validated After Creation

**Issue**: Backup directory is created with `mkdtemp()` and permissions set to 0o700:
```python
backup_path = Path(tempfile.mkdtemp(prefix=backup_name + "-"))
backup_path.chmod(0o700)
```

However, there is NO verification that:
1. The permissions were actually set correctly
2. The directory is in a safe temp location (could be symlink)
3. Race condition between mkdtemp() and chmod()

**Location**: `plugin_updater.py:478-481`

**Attack Vector**: TOCTOU vulnerability
- mkdtemp() creates directory in /tmp
- Between creation (mkdtemp) and chmod (line 481), attacker could:
  - Create symlink at that location
  - Hardlink to sensitive file
  - Change parent directory permissions

**Recommendation**: Check that mkdtemp() created directory safely:
```python
# Use explicit secure temp directory creation
import tempfile
import os

# Option 1: Use TemporaryDirectory context manager (handles cleanup)
with tempfile.TemporaryDirectory(prefix=backup_name + "-") as backup_path:
    backup_path = Path(backup_path)
    
    # Verify permissions were set correctly
    stat_info = backup_path.stat()
    if (stat_info.st_mode & 0o777) != 0o700:
        raise BackupError(f"Failed to set backup permissions to 0o700")
    
    # Verify not a symlink (symlink check should happen in path validation)
    if backup_path.is_symlink():
        raise BackupError(f"Backup directory is a symlink (possible attack)")
    
    # Proceed with backup...
```

---

### [CRITICAL]: No Input Validation for Plugin Name - CWE-78

**Issue**: The plugin_name parameter is passed to security_utils.audit_log() and used in user messages without validation:

```python
def __init__(
    self,
    project_root: Path,
    plugin_name: str = "autonomous-dev",  # <-- No validation
):
    ...
    self.plugin_name = plugin_name  # <-- No sanitization
    security_utils.audit_log(
        "plugin_updater",
        "initialized",
        {
            "plugin_name": plugin_name,  # <-- Used in audit log
        },
    )
```

In `update_plugin.py`, plugin_name comes from CLI args:
```python
parser.add_argument(
    "--plugin-name",
    type=str,
    default="autonomous-dev",
    help="Name of plugin to update (default: autonomous-dev)",
)
```

**Attack Vector**: 
- Audit log injection: `--plugin-name="test\" or \"1\"==\"1"`
- Directory traversal in plugin_name: `--plugin-name="../../../etc/passwd"`
- Code injection: `--plugin-name=$(rm -rf /)`

**Recommendation**: Validate plugin_name to alphanumeric + dash/underscore:
```python
import re

def __init__(
    self,
    project_root: Path,
    plugin_name: str = "autonomous-dev",
):
    # Validate plugin_name (alphanumeric + dash/underscore only)
    if not re.match(r'^[a-zA-Z0-9_-]+$', plugin_name):
        raise UpdateError(
            f"Invalid plugin name: {plugin_name}\n"
            f"Expected alphanumeric characters, dashes, and underscores only"
        )
    
    self.plugin_name = plugin_name
```

---

### [HIGH]: Backup Path Not Validated Before Rollback - CWE-22

**Issue**: The `_rollback()` method only checks if backup_path exists, but doesn't validate it's a safe path:

```python
def _rollback(self, backup_path: Path) -> None:
    try:
        # Validate backup path exists
        if not backup_path.exists():
            raise BackupError(f"Backup path does not exist: {backup_path}")
        
        # No validation that backup_path is safe!
        # Could be symlink, could be outside allowed dirs
        
        # Remove current plugin directory if it exists
        if self.plugin_dir.exists():
            shutil.rmtree(self.plugin_dir)
        
        # Restore from backup (could restore to wrong location due to symlink)
        self.plugin_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(backup_path, self.plugin_dir, dirs_exist_ok=True)
```

**Location**: `plugin_updater.py:540-558`

**Attack Vector**: 
- If backup_path is a symlink, shutil.copytree() follows it
- Could copy from arbitrary location on filesystem
- Could overwrite critical files during restore

**Recommendation**: Validate backup_path before restoring:
```python
def _rollback(self, backup_path: Path) -> None:
    try:
        # Validate backup path exists
        if not backup_path.exists():
            raise BackupError(f"Backup path does not exist: {backup_path}")
        
        # Check for symlink attacks
        if backup_path.is_symlink():
            raise BackupError(
                f"Backup path is a symlink (possible attack): {backup_path}"
            )
        
        # Validate it's in temp directory (where we created it)
        if not str(backup_path).startswith(str(Path(tempfile.gettempdir()))):
            raise BackupError(
                f"Backup path is outside temp directory (possible attack): {backup_path}"
            )
        
        # Proceed with rollback...
```

---

### [HIGH]: No Validation that plugin.json Matches Expected Format

**Issue**: The `_verify_update()` method reads and parses plugin.json but doesn't validate it has the required fields:

```python
def _verify_update(self, expected_version: str) -> None:
    try:
        plugin_json = self.plugin_dir / "plugin.json"
        if not plugin_json.exists():
            raise VerificationError(...)
        
        plugin_data = json.loads(plugin_json.read_text())
        
        # Only checks version field exists
        actual_version = plugin_data.get("version")
        if actual_version != expected_version:
            raise VerificationError(...)
```

**Location**: `plugin_updater.py:620-640`

**Issue**:
- plugin.json could be valid JSON but not a plugin manifest
- Missing validation of required fields (name, version, author, etc.)
- Large plugin.json could cause DoS (reads entire file into memory)

**Recommendation**: Validate plugin.json structure:
```python
def _verify_update(self, expected_version: str) -> None:
    try:
        plugin_json = self.plugin_dir / "plugin.json"
        if not plugin_json.exists():
            raise VerificationError(...)
        
        # Check file size reasonable (< 10MB)
        file_size = plugin_json.stat().st_size
        if file_size > 10 * 1024 * 1024:
            raise VerificationError(
                f"plugin.json is too large: {file_size} bytes"
            )
        
        plugin_data = json.loads(plugin_json.read_text())
        
        # Validate required fields
        required_fields = ["version", "name"]
        missing = [f for f in required_fields if f not in plugin_data]
        if missing:
            raise VerificationError(
                f"plugin.json missing required fields: {missing}"
            )
        
        actual_version = plugin_data.get("version")
        if actual_version != expected_version:
            raise VerificationError(...)
```

---

### [MEDIUM]: Missing Error Message Context - CWE-217 (Insufficient Logging)

**Issue**: Some error messages lack sufficient context for security debugging:

**Location**: `plugin_updater.py:186` and others
```python
if not self.project_root.exists():
    raise UpdateError(f"Project path does not exist: {self.project_root}")
```

Better:
```python
if not self.project_root.exists():
    raise UpdateError(
        f"Project path does not exist: {self.project_root}\n"
        f"Expected valid Claude project with .claude directory.\n"
        f"See docs/setup.md for configuration instructions."
    )
```

**Recommendation**: Add more helpful error messages with context and documentation links.

---

### [LOW]: User Input from stdin Not Size-Limited

**Issue**: The `confirm_update()` function accepts user input from stdin without length validation:

**Location**: `update_plugin.py:185`
```python
response = input("\nDo you want to proceed with the update? [y/N]: ").strip().lower()
```

While this is low-risk (only reading user response), best practice is to limit input:

```python
response = input("\nDo you want to proceed with the update? [y/N]: ")[:100].strip().lower()
```

**Recommendation**: Add a reasonable length limit to user input to prevent DoS from huge pastes.

---

## Security Checks Completed

- [x] Hardcoded secrets search - No secrets found in code
- [x] Path validation usage - Found gap in marketplace_file validation
- [x] Symlink protection - Found missing symlink checks in rollback
- [x] Backup permissions (CWE-732) - chmod(0o700) called but not verified
- [x] Audit logging (CWE-778) - Found: syntax errors prevent execution
- [x] Input validation - Found: plugin_name not validated
- [x] TOCTOU vulnerabilities - Found: mkdtemp/chmod race condition
- [x] Error message data leakage - Clean, no sensitive data in errors
- [x] .gitignore secrets - .env properly gitignored
- [x] Git history secrets - No secrets found in history
- [x] File permission validation - Not verified after creation
- [x] Race conditions - Found: backup creation race window

---

## OWASP Top 10 Compliance

| Category | Status | Notes |
|----------|--------|-------|
| A01: Broken Access Control | FAIL | No validation that backed-up plugin files are accessible only to user |
| A02: Cryptographic Failures | PASS | No cryptographic operations |
| A03: Injection | FAIL | plugin_name parameter not validated (CWE-78) |
| A04: Insecure Design | FAIL | TOCTOU vulnerability in mkdtemp/chmod sequence |
| A05: Security Misconfiguration | FAIL | Backup permissions not verified after chmod() |
| A06: Vulnerable/Outdated Components | PASS | Using safe stdlib functions (shutil, tempfile) |
| A07: Authentication/Session Mgmt | PASS | No auth required (local operation) |
| A08: Software/Data Integrity | FAIL | No validation of backup contents |
| A09: Logging/Monitoring Failures | FAIL | Syntax errors break all audit logging |
| A10: SSRF | PASS | No network operations |

---

## Recommendations

### Critical (Must Fix Before Merge)

1. **Fix all audit_log() syntax errors** - 11 malformed calls throughout plugin_updater.py
2. **Validate plugin_name input** - Add regex validation for alphanumeric + dash/underscore
3. **Fix TOCTOU in backup creation** - Use TemporaryDirectory context manager or add verification
4. **Validate marketplace_file path** - Use security_utils.validate_path() before passing to sync_dispatcher
5. **Add symlink checks in rollback** - Reject symlinks and validate backup path in allowed directories

### High Priority (Before First Release)

6. **Validate plugin.json structure** - Check required fields and file size limits
7. **Verify backup permissions** - Check stat() results after chmod() to confirm 0o700

### Medium Priority

8. **Enhance error messages** - Add documentation links and expected format info
9. **Add input size limits** - Limit stdin reads to prevent DoS
10. **Add backup corruption detection** - Verify file counts and checksums after restore

---

## Test Recommendations

Before marking this as secure, add these tests:

```python
# tests/test_plugin_updater_security.py

def test_rejects_directory_traversal_in_plugin_name():
    """Plugin name with ../ should be rejected"""
    with pytest.raises(UpdateError, match="Invalid plugin name"):
        PluginUpdater(project_root, plugin_name="../../../etc/passwd")

def test_rejects_symlink_backup():
    """Rollback should reject symlinked backup directory"""
    # Create symlink to /tmp
    backup_symlink = create_temp_symlink("/tmp")
    with pytest.raises(BackupError, match="symlink"):
        updater._rollback(backup_symlink)

def test_verifies_backup_permissions():
    """Backup directory should have 0o700 permissions"""
    backup_path = updater._create_backup()
    stat_info = backup_path.stat()
    assert (stat_info.st_mode & 0o777) == 0o700

def test_validates_plugin_json_structure():
    """Verification should validate required fields in plugin.json"""
    # Create invalid plugin.json (missing version field)
    with pytest.raises(VerificationError, match="required fields"):
        updater._verify_update("1.0.0")
```

---

## Conclusion

The /update-plugin implementation has **solid architectural design** with good separation of concerns (PluginUpdater, UpdateResult, error handling). However, it has **critical syntax errors** and **5 unresolved security vulnerabilities** that must be fixed before merge.

**Current Status**: FAIL - Blocking issues present

**Next Steps**:
1. Fix all 11 audit_log() syntax errors
2. Add plugin_name input validation  
3. Fix TOCTOU vulnerability in backup creation
4. Add path validation for marketplace_file
5. Add symlink rejection in rollback
6. Re-run security audit after fixes

All issues are fixable with the recommended changes above.

