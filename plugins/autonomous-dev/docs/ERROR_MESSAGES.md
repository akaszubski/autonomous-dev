# Error Message Guidelines

**Version**: 1.0.0 (Issue #16)
**Last Updated**: 2025-10-26
**Status**: Standard for all autonomous-dev error messages

---

## Purpose

This document defines the standard error message format for the autonomous-dev plugin. All errors should follow the **WHERE + WHAT + HOW + LEARN MORE** pattern.

**Problem (Before Issue #16)**:
```
❌ black or isort not installed. Run: pip install black isort
```

**Solution (After Issue #16)**:
```
======================================================================
ERROR: black not found [ERR-101]
======================================================================

Where you are:
  • Python: /opt/homebrew/bin/python3.14 (v3.14.0)
  • Working directory: /Users/you/project
  • Hook: auto_format.py (post-tool-use)

What's wrong:
  • black formatter not installed in current Python environment

How to fix:
  1. Install in current environment:
     /opt/homebrew/bin/python3.14 -m pip install black

  2. OR use project virtualenv:
     source venv/bin/activate
     pip install black

  3. OR skip formatting for this commit:
     git commit --no-verify

Learn more: docs/TROUBLESHOOTING.md#issue-1-hooks-not-running

======================================================================
```

---

## Error Message Framework

All scripts should use `lib/error_messages.py` for consistent error formatting.

### Basic Usage

```python
from error_messages import formatter_not_found_error

# Pre-built error templates
error = formatter_not_found_error("black", sys.executable)
error.print()
sys.exit(1)
```

### Custom Errors

```python
from error_messages import ErrorMessage, ErrorCode

error = ErrorMessage(
    code=ErrorCode.YOUR_ERROR_CODE,
    title="Short error title",
    what_wrong="Detailed explanation of what went wrong",
    how_to_fix=[
        "Step 1 with command:\ncommand here",
        "Step 2 alternative:\nother command"
    ],
    learn_more="docs/TROUBLESHOOTING.md#your-section"
)

error.print()
sys.exit(1)
```

---

## Error Code Registry

Error codes follow pattern: `ERR-XXX`

### Installation & Setup (ERR-100s)
- **ERR-101**: Formatter not found (black, isort, prettier, gofmt)
- **ERR-102**: PROJECT.md missing
- **ERR-103**: GitHub token invalid
- **ERR-104**: Python version mismatch
- **ERR-105**: Dependency missing

### Hook Errors (ERR-200s)
- **ERR-201**: Hook execution failed
- **ERR-202**: Hook not executable
- **ERR-203**: Hook timeout

### Validation Errors (ERR-300s)
- **ERR-301**: Validation failed (general)
- **ERR-302**: Test coverage below minimum
- **ERR-303**: Security issue found
- **ERR-304**: Command/component invalid

### File/Directory Errors (ERR-400s)
- **ERR-401**: File not found
- **ERR-402**: Directory not found
- **ERR-403**: Permission denied
- **ERR-404**: File parse error

### Configuration Errors (ERR-500s)
- **ERR-501**: Config file missing
- **ERR-502**: Config file invalid
- **ERR-503**: Environment mismatch

---

## Error Message Anatomy

### 1. WHERE (Context)

**Purpose**: Help user understand their current environment

**Include**:
- Python interpreter path and version
- Current working directory
- Script/hook name
- Hook type (if applicable)

**Auto-captured** by `ErrorContext` class:
```python
from error_messages import ErrorContext

context = ErrorContext()
# Automatically captures:
#  - Python: /path/to/python (vX.Y.Z)
#  - Working directory: /current/dir
#  - Script: script_name.py
#  - Hook: pre-commit (if HOOK_TYPE env var set)
```

### 2. WHAT (Problem)

**Purpose**: Clearly explain what went wrong

**Guidelines**:
- Be specific: "black formatter not installed" not "formatter missing"
- Include relevant details: file paths, expected values, actual values
- Use bullet points for multiple issues
- Avoid jargon when possible

**Examples**:
- Good: "PROJECT.md file not found at: /path/to/PROJECT.md"
- Bad: "File missing"

### 3. HOW (Fix Steps)

**Purpose**: Provide actionable recovery steps

**Guidelines**:
- Number the steps (1, 2, 3...)
- Include actual commands to run
- Provide alternatives (OR clauses)
- Multi-line commands use proper formatting
- Least destructive options first

**Format**:
```python
how_to_fix=[
    "Primary fix (recommended):\ncommand to run",
    "Alternative fix:\nother command",
    "Emergency bypass (not recommended):\nskip command"
]
```

**Examples**:
```
1. Install in current environment:
   /path/to/python -m pip install package

2. OR use project virtualenv:
   source venv/bin/activate
   pip install package

3. OR skip validation (not recommended):
   git commit --no-verify
```

### 4. LEARN MORE (Documentation)

**Purpose**: Link to detailed troubleshooting

**Format**: `docs/TROUBLESHOOTING.md#section-anchor`

**Guidelines**:
- Every error should link to TROUBLESHOOTING.md
- Use descriptive anchor names
- Keep anchors stable (don't rename frequently)

---

## Pre-Built Error Templates

Use these for common error scenarios:

### Formatter Not Found
```python
from error_messages import formatter_not_found_error

error = formatter_not_found_error("black", sys.executable)
error.print()
```

### PROJECT.md Missing
```python
from error_messages import project_md_missing_error

error = project_md_missing_error(Path("PROJECT.md"))
error.print()
```

### Dependency Missing
```python
from error_messages import dependency_missing_error

error = dependency_missing_error(
    package_name="pytest",
    required_for="running tests",
    python_path=sys.executable
)
error.print()
```

### Validation Failed
```python
from error_messages import validation_failed_error

error = validation_failed_error(
    what_failed="Test coverage below minimum",
    failures=[
        "src/module_a.py: 65% (needs 80%)",
        "src/module_b.py: 45% (needs 80%)"
    ],
    fix_command="pytest --cov=src --cov-report=term-missing"
)
error.print()
```

### File Not Found
```python
from error_messages import file_not_found_error

error = file_not_found_error(
    file_path=Path("config.json"),
    expected_purpose="plugin configuration"
)
error.print()
```

### Config Invalid
```python
from error_messages import config_invalid_error

error = config_invalid_error(
    config_file=Path("settings.json"),
    errors=["Invalid JSON syntax at line 5", "Missing required field: 'name'"],
    example_config="templates/settings.json"
)
error.print()
```

---

## Adding New Error Codes

1. **Choose code range** based on error category (100s, 200s, etc.)

2. **Add to ErrorCode class** in `lib/error_messages.py`:
   ```python
   class ErrorCode:
       YOUR_NEW_ERROR = "ERR-XXX"
   ```

3. **Update this document** with error code description

4. **Add to TROUBLESHOOTING.md** with recovery steps

5. **(Optional) Create template function** if error is common:
   ```python
   def your_error_template(...) -> ErrorMessage:
       return ErrorMessage(
           code=ErrorCode.YOUR_NEW_ERROR,
           ...
       )
   ```

---

## Migration Checklist

When updating existing error messages:

- [ ] Import error_messages module
- [ ] Replace print statements with ErrorMessage
- [ ] Add error code (new or existing)
- [ ] Include WHERE context (auto-captured)
- [ ] Explain WHAT went wrong (specific)
- [ ] Provide HOW to fix (actionable steps)
- [ ] Link to LEARN MORE (TROUBLESHOOTING.md)
- [ ] Test error message output
- [ ] Update TROUBLESHOOTING.md if needed

---

## Examples

### Example 1: Hook Failure (hooks/auto_format.py)

**Before**:
```python
except FileNotFoundError:
    return False, "black or isort not installed. Run: pip install black isort"
```

**After**:
```python
except FileNotFoundError as e:
    formatter = "black" if "black" in str(e) else "isort"
    error = formatter_not_found_error(formatter, sys.executable)
    error.print()
    sys.exit(1)
```

### Example 2: Missing Directory (scripts/health_check.py)

**Before**:
```python
print("❌ Plugin directory not found!", file=sys.stderr)
print(f"Checked: {home_plugin}", file=sys.stderr)
print(f"Checked: {cwd_plugin}", file=sys.stderr)
sys.exit(1)
```

**After**:
```python
error = ErrorMessage(
    code=ErrorCode.DIRECTORY_NOT_FOUND,
    title="Plugin directory not found",
    what_wrong=f"autonomous-dev plugin not found in expected locations:\n  • {home_plugin}\n  • {cwd_plugin}",
    how_to_fix=[
        "Install the plugin:\n/plugin marketplace add akaszubski/autonomous-dev\n/plugin install autonomous-dev",
        "Exit and restart Claude Code (REQUIRED):\nPress Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)",
        "Verify installation:\n/plugin list",
    ],
    learn_more="docs/TROUBLESHOOTING.md#plugin-not-found"
)
error.print()
sys.exit(1)
```

---

## Testing Error Messages

Test error output with:

```bash
# Demo all pre-built templates
python lib/error_messages.py

# Test specific error in your script
python your_script.py  # Trigger error condition
```

Verify output includes:
- ✓ Error code [ERR-XXX]
- ✓ WHERE section (context)
- ✓ WHAT section (problem)
- ✓ HOW section (numbered steps)
- ✓ LEARN MORE link

---

## References

- **Issue #16**: Error Messages Lack Context and Recovery Guidance
- **Implementation**: `lib/error_messages.py`
- **Updated scripts**: `hooks/auto_format.py`, `scripts/health_check.py`
- **Troubleshooting**: `docs/TROUBLESHOOTING.md`

---

**Status**: ✅ Standard adopted (Issue #16 resolved)
**Next**: Migrate all remaining scripts to use error framework
