# Implementation Checklist for Issue #83: Symlink Documentation

**Issue**: Document symlink requirement for plugin imports
**Test Suite**: TDD Red Phase Complete
**Date**: 2025-11-19
**Implementer**: doc-master agent (or manual implementation)

---

## Test Results Summary

### Unit Tests: `tests/unit/test_issue83_symlink_documentation.py`

**Status**: 17 / 36 tests FAILING (expected - documentation incomplete)

**Failing Tests**:
- DEVELOPMENT.md missing Step 4.5 symlink section
- DEVELOPMENT.md missing macOS/Linux commands
- DEVELOPMENT.md missing Windows commands
- DEVELOPMENT.md missing correct command syntax
- TROUBLESHOOTING.md file doesn't exist (5 tests failing)
- Plugin README missing Development Setup section
- tests/README.md missing DEVELOPMENT.md link
- Cross-references incomplete (3 tests failing)
- Unix/Windows command syntax tests failing
- Documentation completeness checks failing

### Integration Tests: `tests/integration/test_issue83_symlink_workflow.py`

**Status**: 8 / 21 tests FAILING (expected - workflows incomplete)

**Failing Tests**:
- Step numbering in DEVELOPMENT.md
- TROUBLESHOOTING.md missing (4 tests)
- Unix/Windows command validation
- Security messaging consistency

---

## Implementation Tasks

### 1. Create `docs/TROUBLESHOOTING.md` (HIGH PRIORITY)

**Status**: File doesn't exist - 9 tests failing

**Required Content**:
```markdown
# Troubleshooting Guide

## ModuleNotFoundError: No module named 'autonomous_dev'

**Symptom**: When running tests or importing from the plugin, you see:
```
ModuleNotFoundError: No module named 'autonomous_dev'
```

**Root Cause**: Python package names cannot contain hyphens (`-`), only underscores (`_`).
The plugin directory is named `autonomous-dev` (with hyphen) but Python expects
`autonomous_dev` (with underscore) for imports.

**Solution**: Create a development symlink:

**macOS/Linux**:
```bash
cd plugins
ln -s autonomous-dev autonomous_dev
```

**Windows (Command Prompt - Run as Administrator)**:
```cmd
cd plugins
mklink /D autonomous_dev autonomous-dev
```

**Windows (PowerShell - Run as Administrator)**:
```powershell
cd plugins
New-Item -ItemType SymbolicLink -Path "autonomous_dev" -Target "autonomous-dev"
```

**Verification**:
```bash
# macOS/Linux
ls -la plugins/ | grep autonomous_dev
# Should show: autonomous_dev -> autonomous-dev

# Windows
dir plugins\ | findstr autonomous_dev
```

**See Also**: [DEVELOPMENT.md](DEVELOPMENT.md) for complete setup instructions
```

**Tests This Fixes**:
- `test_troubleshooting_md_exists`
- `test_troubleshooting_md_has_modulenotfound_section`
- `test_troubleshooting_md_mentions_symlink_solution`
- `test_troubleshooting_md_links_to_development_md`
- `test_troubleshooting_md_has_error_example`
- `test_developer_can_find_troubleshooting_from_error_message`
- `test_troubleshooting_provides_root_cause_explanation`
- `test_troubleshooting_links_to_solution_in_development_md`
- `test_troubleshooting_provides_quick_fix_command`

---

### 2. Update `docs/DEVELOPMENT.md` (HIGH PRIORITY)

**Status**: Partially exists - 10 tests failing

**Add Section After Step 4** (before "Test Hooks Work"):

```markdown
### Step 4.5: Create Development Symlink

**Why This Is Needed**: Python package names cannot contain hyphens. The plugin
directory is `autonomous-dev` (with hyphen for clarity), but Python imports require
`autonomous_dev` (with underscore). A symlink bridges this gap.

**Security Note**: This symlink is safe - it uses a relative path within the repository
and is automatically gitignored.

**macOS/Linux**:
```bash
cd plugins
ln -s autonomous-dev autonomous_dev
```

**Windows (Command Prompt - Run as Administrator)**:
```cmd
cd plugins
mklink /D autonomous_dev autonomous-dev
```

**Windows (PowerShell - Run as Administrator)**:
```powershell
cd plugins
New-Item -ItemType SymbolicLink -Path "autonomous_dev" -Target "autonomous-dev"
```

**Verify Symlink Creation**:

**macOS/Linux**:
```bash
ls -la plugins/ | grep autonomous_dev
# Expected output: autonomous_dev -> autonomous-dev
```

**Windows**:
```cmd
dir plugins\ | findstr autonomous_dev
# Expected output: <SYMLINKD> autonomous_dev [autonomous-dev]
```

**Test Import**:
```bash
python -c "from autonomous_dev.lib import security_utils; print('✓ Import works')"
# Should print: ✓ Import works
```

**Troubleshooting**: If you encounter `ModuleNotFoundError`, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

**Note**: The symlink is gitignored automatically (see `.gitignore`). Do not commit it to the repository.
```

**Tests This Fixes**:
- `test_development_md_has_symlink_step`
- `test_development_md_has_macos_linux_commands`
- `test_development_md_has_windows_commands`
- `test_development_md_commands_are_correct`
- `test_unix_symlink_command_syntax`
- `test_windows_symlink_command_syntax`
- `test_documentation_provides_complete_workflow`
- `test_developer_can_follow_development_md_step_by_step`

---

### 3. Update `plugins/autonomous-dev/README.md` (MEDIUM PRIORITY)

**Status**: Exists but missing Development Setup section - 2 tests failing

**Add Section** (in "For Contributors" or similar area):

```markdown
## Development Setup

**For plugin development**, you'll need to create a symlink for Python imports:

**Quick Setup**:
```bash
cd plugins
ln -s autonomous-dev autonomous_dev  # macOS/Linux
```

**Why**: Python imports require `autonomous_dev` (underscore) but the directory
is `autonomous-dev` (hyphen). The symlink bridges this.

**Full Instructions**: See [DEVELOPMENT.md](../../docs/DEVELOPMENT.md) for complete
setup instructions including Windows commands and troubleshooting.
```

**Tests This Fixes**:
- `test_plugin_readme_has_development_setup_section`
- `test_plugin_readme_links_to_development_md`

---

### 4. Update `tests/README.md` (LOW PRIORITY)

**Status**: Exists but missing DEVELOPMENT.md link - 1 test failing

**Add to "Running Tests" or "Setup" section**:

```markdown
## Setup

**Development Environment**: Before running tests, ensure you've completed the
development setup in [DEVELOPMENT.md](../docs/DEVELOPMENT.md), including creating
the `autonomous_dev` symlink.

If you encounter `ModuleNotFoundError`, see [TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md).
```

**Tests This Fixes**:
- `test_tests_readme_links_to_development_md`

---

### 5. Update `.gitignore` (ALREADY DONE)

**Status**: COMPLETE - `plugins/autonomous_dev` already in .gitignore

**Verify Entry** (no changes needed):
```bash
grep "plugins/autonomous_dev" .gitignore
# Output: plugins/autonomous_dev
```

**Optional Enhancement** (add comment):
```gitignore
# Development symlink (autonomous-dev → autonomous_dev for Python imports)
plugins/autonomous_dev
```

**Tests Already Passing**:
- `test_gitignore_exists`
- `test_gitignore_includes_autonomous_dev_directory`
- `test_gitignore_entry_is_correctly_formatted`

---

### 6. Optional: Update `CONTRIBUTING.md` (BONUS)

**Status**: Exists and already mentions setup - tests passing

**Optional Enhancement** (add quick reference):

```markdown
## Development Environment

**Quick Start**:
1. Fork and clone the repository
2. Follow [DEVELOPMENT.md](docs/DEVELOPMENT.md) setup instructions
3. Create symlink: `cd plugins && ln -s autonomous-dev autonomous_dev`
4. Run tests: `pytest tests/`

See [DEVELOPMENT.md](docs/DEVELOPMENT.md) for complete setup details.
```

---

## Verification Steps

### After Implementation, Run Tests:

```bash
# 1. Run unit tests
.venv/bin/pytest tests/unit/test_issue83_symlink_documentation.py -v

# Expected: 36/36 tests PASSING

# 2. Run integration tests
.venv/bin/pytest tests/integration/test_issue83_symlink_workflow.py -v

# Expected: 21/21 tests PASSING

# 3. Full test suite
.venv/bin/pytest tests/unit/test_issue83_symlink_documentation.py \
                  tests/integration/test_issue83_symlink_workflow.py -v

# Expected: 57/57 tests PASSING
```

---

## Priority Order

1. **Create `docs/TROUBLESHOOTING.md`** (9 tests failing)
   - Most critical - file doesn't exist
   - Fixes developer experience for common error

2. **Update `docs/DEVELOPMENT.md`** (10 tests failing)
   - Add Step 4.5 with complete instructions
   - Include OS-specific commands
   - Add verification steps

3. **Update `plugins/autonomous-dev/README.md`** (2 tests failing)
   - Add Development Setup section
   - Link to main DEVELOPMENT.md

4. **Update `tests/README.md`** (1 test failing)
   - Add reference to DEVELOPMENT.md

5. **Verify `.gitignore`** (already complete)
   - Optionally add explanatory comment

---

## Command Syntax Reference

### Unix (macOS/Linux)
```bash
# Create symlink (target → link)
ln -s autonomous-dev autonomous_dev

# Verify
ls -la | grep autonomous_dev
# Output: autonomous_dev -> autonomous-dev

# Test
test -L autonomous_dev && echo "Symlink exists"
```

### Windows (Command Prompt)
```cmd
REM Run as Administrator
mklink /D autonomous_dev autonomous-dev

REM Verify
dir | findstr autonomous_dev
REM Output: <SYMLINKD> autonomous_dev [autonomous-dev]
```

### Windows (PowerShell)
```powershell
# Run as Administrator
New-Item -ItemType SymbolicLink -Path "autonomous_dev" -Target "autonomous-dev"

# Verify
Get-Item autonomous_dev | Select-Object LinkType, Target
```

---

## Common Mistakes to Avoid

1. **Don't use absolute paths** - Always use relative paths for portability
2. **Don't swap target/link** - Target is `autonomous-dev`, link is `autonomous_dev`
3. **Don't commit symlink** - Verify `.gitignore` includes `plugins/autonomous_dev`
4. **Don't forget Windows** - Include both mklink and New-Item commands
5. **Don't skip verification** - Always show developers how to verify symlink creation

---

## Example Error Message (For TROUBLESHOOTING.md)

```python
Traceback (most recent call last):
  File "tests/unit/test_something.py", line 10, in <module>
    from autonomous_dev.lib import security_utils
ModuleNotFoundError: No module named 'autonomous_dev'
```

This exact error should appear in TROUBLESHOOTING.md for searchability.

---

## Success Criteria

- [ ] All 36 unit tests pass
- [ ] All 21 integration tests pass
- [ ] Developer can find symlink instructions from multiple entry points
- [ ] Developer encountering error can find solution via TROUBLESHOOTING.md
- [ ] Documentation is consistent across all files
- [ ] Commands work on macOS, Linux, and Windows
- [ ] Security concerns are addressed (relative path, gitignored)
- [ ] Cross-references between docs are correct

---

## Related Files

- **Test Coverage**: `tests/TEST_COVERAGE_ISSUE_83.md`
- **Unit Tests**: `tests/unit/test_issue83_symlink_documentation.py`
- **Integration Tests**: `tests/integration/test_issue83_symlink_workflow.py`
- **GitHub Issue**: #83
