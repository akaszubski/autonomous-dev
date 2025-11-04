# Security Quick Reference - v3.2.3

**For developers working with**: Path validation, plugin directories, issue parsing

---

## Three Security Fixes at a Glance

### 1. Agent Tracker Path Validation (agent_tracker.py)

**What it does**: Prevents directory traversal attacks when creating session files.

**Example attacks blocked**:
```python
# All of these are now BLOCKED:
AgentTracker(session_file="../../etc/passwd")
AgentTracker(session_file="/etc/passwd")
AgentTracker(session_file="/symlink_to_etc")
```

**How it works**:
1. Check for '..' in path
2. Resolve symlinks with resolve()
3. Check for symlinks again
4. Verify path is within PROJECT_ROOT
5. Verify path is a directory

**When you use it**:
- Calling `AgentTracker()` constructor
- Passing `session_file` parameter

**Error behavior**:
- Raises `ValueError` with detailed message
- Error includes expected format and security docs link
- Exception message safe to log (no secrets leaked)

---

### 2. Plugin Path Validation (sync_to_installed.py)

**What it does**: Prevents symlink attacks when accessing plugin directories.

**Example attacks blocked**:
```python
# If installed_plugins.json contains:
# "installPath": "/home/user/.claude/plugins/link_to_etc"
# and link_to_etc -> /etc
#
# This is now BLOCKED:
path = find_installed_plugin_path()  # Returns None
```

**How it works**:
1. Check if installPath exists in JSON
2. Check if it's a symlink (pre-resolve)
3. Resolve path to canonical form
4. Check if it's a symlink (post-resolve)
5. Verify it's within .claude/plugins/
6. Verify it's a directory

**When you use it**:
- Syncing plugin files: `plugins/autonomous-dev/hooks/sync_to_installed.py`
- Called automatically when setting up plugin

**Error behavior**:
- Returns `None` (not ValueError)
- Caller must check for None and handle gracefully
- No exceptions thrown (graceful degradation)

---

### 3. Issue Number Parsing (pr_automation.py)

**What it does**: Safely extracts GitHub issue numbers from commit messages.

**Example attacks blocked**:
```python
# All of these are now handled safely:
extract_issue_numbers(["Fix #abc"])           # Skips invalid number
extract_issue_numbers(["Fix #42.5"])          # Skips float-like
extract_issue_numbers(["Fix #-1"])            # Skips negative
extract_issue_numbers(["Fix #999999999"])     # Skips oversized (> 999999)
extract_issue_numbers(["Fix #"])              # No number to extract
```

**How it works**:
1. Regex matches issue keywords (Closes, Fix, Resolve)
2. For each match, extract the number
3. Try to convert to int
4. Check range: 1-999999
5. On any error, continue processing (don't crash)
6. Return only valid numbers

**When you use it**:
- Creating PRs: `plugins/autonomous-dev/lib/pr_automation.py`
- Called during `/auto-implement` Step 8
- Can be called directly: `from pr_automation import extract_issue_numbers`

**Error behavior**:
- Returns empty list if all numbers are invalid
- Returns subset of valid numbers
- Never crashes or throws exception

---

## Testing These Fixes

### Agent Tracker Security Tests
```bash
# Run security tests
pytest tests/unit/test_agent_tracker_security.py -v

# Run specific test
pytest tests/unit/test_agent_tracker_security.py::test_path_traversal_relative_up -v
```

### Issue Parsing Tests
```bash
# Run issue number parsing tests
pytest tests/test_issue_number_parsing.py -v

# Run specific test
pytest tests/test_issue_number_parsing.py::test_extract_issue_numbers_non_numeric -v
```

---

## Common Questions

### Q: Can I bypass these checks?
**A**: No. These checks are part of the core API and cannot be disabled. If you find a bypass, please report it as a security issue.

### Q: What if I have a legitimate path that fails validation?
**A**: Check:
1. Is the path relative? (Use absolute paths)
2. Does it contain '..'? (Use resolved absolute path)
3. Is it a symlink? (Resolve the symlink target)
4. Is it within the project root? (For agent_tracker) or .claude/plugins/ (for sync_to_installed)
5. Is it a directory? (For sync_to_installed)

### Q: How do I report a security issue?
**A**: Create a private security advisory on GitHub:
1. Go to Security tab
2. Click "Report a vulnerability"
3. Describe the issue

### Q: What's the difference between Layer 1 and Layer 2 symlink checks?
**A**:
- Layer 1 (pre-resolve): Checks if the path itself is a symlink
- Layer 2 (post-resolve): Checks if any parent directory is a symlink
- Both needed for defense in depth

---

## Documentation References

### Detailed Security Documentation
- **Full Fix Details**: `/docs/SECURITY_FIXES_v3.2.3.md`
- **CHANGELOG**: `/CHANGELOG.md` lines 22-83
- **Code Comments**: Each function has inline security comments

### Docstrings
- **agent_tracker.py**: Module and __init__() explain path validation
- **sync_to_installed.py**: find_installed_plugin_path() explains symlink defense
- **pr_automation.py**: extract_issue_numbers() explains error handling

---

## Version Info

| Component | Version | Date |
|-----------|---------|------|
| Security Fixes | v3.2.3 | 2025-11-04 |
| Issue | GitHub #45 | 2025-11-04 |
| Tests Added | 50+ | 2025-11-04 |

---

**Last Updated**: 2025-11-04
**Status**: All fixes implemented and tested
