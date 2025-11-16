# Docstring Standards

**Pattern Type**: Documentation
**Skill**: library-design-patterns
**Version**: 1.0.0

---

## Overview

Google-style docstrings provide comprehensive API documentation for all public functions, classes, and modules in the autonomous-dev plugin ecosystem.

**Core Principle**: Every public API deserves clear, comprehensive documentation.

---

## Function Docstring Template

```python
def function_name(
    positional_arg: Type1,
    another_arg: Type2,
    *,
    keyword_arg: Type3 = default_value,
    optional_arg: Optional[Type4] = None
) -> ReturnType:
    """One-line summary in imperative mood.

    Optional detailed description explaining behavior, edge cases,
    and important implementation details. Can span multiple paragraphs
    if needed to fully explain the function's purpose and usage.

    Args:
        positional_arg: Description of this argument including what
            values are expected and any constraints
        another_arg: Description of second argument
        keyword_arg: Description of keyword argument
            (default: default_value)
        optional_arg: Description of optional argument
            (default: None)

    Returns:
        Description of return value including type and structure.
        For complex returns, describe each field or component.

    Raises:
        ValueError: When input validation fails or value is invalid
        FileNotFoundError: When specified file doesn't exist
        SecurityError: When security validation fails (CWE-XX)

    Example:
        >>> result = function_name("value1", "value2", keyword_arg="custom")
        >>> print(result.status)
        'success'
        >>> print(result.data)
        {'key': 'value'}

    Security:
        - CWE-22: Path traversal prevention via whitelist validation
        - CWE-78: Command injection prevention via argument arrays
        - Audit: Security-relevant operations logged to audit trail

    Note:
        Additional notes about behavior, performance, or caveats.
        Use sparingly for truly important information.

    See:
        - Related function_name or documentation
        - External reference or skill reference
        - Issue #XX for historical context
    """
```

---

## Class Docstring Template

```python
class ClassName:
    """One-line summary of class purpose.

    Detailed description of what this class represents and how it
    should be used. Explain the primary use cases and any important
    design decisions.

    Attributes:
        attribute_name: Description of public attribute including
            expected type and purpose
        another_attr: Description of another attribute

    Example:
        >>> instance = ClassName(param1="value", param2=42)
        >>> instance.method()
        'result'
        >>> print(instance.attribute_name)
        'value'

    Security:
        - Security considerations for the class (if applicable)
        - CWE references for prevented vulnerabilities

    See:
        - Related classes or documentation
        - Skills that provide additional context
    """

    def __init__(
        self,
        param1: Type1,
        *,
        param2: Type2 = default
    ) -> None:
        """Initialize ClassName with given parameters.

        Args:
            param1: Description of initialization parameter
            param2: Description of optional parameter (default: value)

        Raises:
            ValueError: If parameters are invalid
        """
        self.attribute_name = param1
        self.another_attr = param2

    def method_name(self, arg: Type) -> ReturnType:
        """One-line summary of method purpose.

        Args:
            arg: Description of argument

        Returns:
            Description of return value

        Raises:
            ExceptionType: When and why this exception is raised
        """
```

---

## Module Docstring Template

```python
"""Module name and one-line summary.

Detailed description of module purpose, responsibilities, and how it
fits into the larger system. Explain what problems this module solves
and when it should be used.

This module provides:
    - Feature 1: Brief description
    - Feature 2: Brief description
    - Feature 3: Brief description

Typical usage example:
    >>> from module_name import function_name
    >>> result = function_name(arg="value")
    >>> print(result)
    'success'

Design Patterns:
    - Two-tier design: Core logic in this module, CLI in separate script
    - Progressive enhancement: String → Path → Whitelist validation
    - Security-first: Input validation, audit logging (CWE-22, CWE-78)

Security:
    - CWE references for prevented vulnerabilities
    - Security properties and guarantees

See:
    - skills/library-design-patterns: Library design guidance
    - Related modules or documentation
    - Issue #XX for context

Author: agent-name
Date: YYYY-MM-DD
Version: X.Y.Z
"""
```

---

## Docstring Sections

### Required Sections

#### 1. Summary Line

- **One line** describing purpose (imperative mood)
- **No period** at end
- **Imperative mood**: "Calculate result" not "Calculates result"

**Examples**:
```python
"""Calculate Fibonacci number using iterative algorithm"""  # ✅ Good

"""This function calculates the Fibonacci number"""  # ❌ Too verbose

"""Calculates Fibonacci number"""  # ❌ Wrong mood (use imperative)
```

#### 2. Args Section

Document all parameters:

```python
Args:
    param_name: Description of parameter including type expectations
        and any constraints. Can span multiple lines if indented.
    keyword_only_param: Description (default: value) - Include default
    optional_param: Description (default: None) - Note when optional
```

**Best Practices**:
- Describe expected type (even if type-hinted)
- Document constraints (ranges, formats, allowed values)
- Note default values explicitly
- Explain None vs empty string vs missing

#### 3. Returns Section

Document return value:

```python
Returns:
    Description of return value including structure and fields.
    For complex objects, describe each component.

    Example for dict:
    Dict with keys:
        - 'status': Success/failure status (str)
        - 'data': Result data (list)
        - 'errors': Error messages if any (list)
```

**Best Practices**:
- Describe type and structure
- For complex returns, enumerate fields
- Explain None vs empty collection
- Note when exceptions used instead of error returns

#### 4. Raises Section

Document all exceptions:

```python
Raises:
    ValueError: When input validation fails or value is out of range.
        Include specific conditions that trigger this exception.
    FileNotFoundError: When specified file doesn't exist at given path
    SecurityError: When security validation fails (CWE-22: path traversal)
```

**Best Practices**:
- List all exceptions the function raises
- Explain when each exception is raised
- Include CWE references for security exceptions
- Document both direct and propagated exceptions

### Optional Sections

#### 5. Example Section

Provide usage examples:

```python
Example:
    >>> result = function_name(arg="value", kwarg=True)
    >>> print(result.status)
    'success'
    >>> print(result.data)
    ['item1', 'item2']
```

**When to Include**:
- Complex functions with non-obvious usage
- Functions with multiple calling patterns
- Public APIs that other developers will use

#### 6. Security Section

Document security properties:

```python
Security:
    - CWE-22 Prevention: Path traversal via whitelist validation
    - CWE-78 Prevention: Command injection via argument arrays
    - CWE-117 Prevention: Log injection via sanitization
    - Audit: All operations logged to logs/security_audit.log
```

**When to Include**:
- Functions that handle user input
- File system operations
- Command execution
- Authentication/authorization
- Cryptographic operations

#### 7. Note Section

Important behavioral notes:

```python
Note:
    This function modifies the input list in-place. If you need
    the original list preserved, pass a copy.

    Performance: O(n log n) time complexity, O(1) space.
```

**When to Include**:
- Performance characteristics worth noting
- Side effects (mutation, I/O)
- Thread safety considerations
- Deprecation warnings

#### 8. See Section

Cross-references:

```python
See:
    - related_function(): Related functionality
    - skills/library-design-patterns: Design pattern guidance
    - https://example.com/docs: External documentation
    - Issue #123: Historical context
```

**When to Include**:
- Related functions in same module
- Relevant skills for additional context
- External documentation
- GitHub issues with background

---

## Real-World Examples

### Example 1: Simple Function

```python
def fibonacci(n: int) -> int:
    """Calculate nth Fibonacci number using iterative algorithm.

    Args:
        n: Position in Fibonacci sequence (0-indexed, n >= 0)

    Returns:
        Fibonacci number at position n

    Raises:
        ValueError: If n is negative

    Example:
        >>> fibonacci(0)
        0
        >>> fibonacci(5)
        5
        >>> fibonacci(10)
        55
    """
```

### Example 2: Security-Sensitive Function

```python
def validate_path(
    path_input: Union[str, Path],
    *,
    must_exist: bool = False,
    allowed_dirs: Optional[List[Path]] = None
) -> Path:
    """Validate and sanitize file path with security checks.

    Progressive enhancement pattern:
    1. String/Path conversion (always)
    2. Existence validation (if must_exist=True)
    3. Whitelist validation (if allowed_dirs provided)

    Args:
        path_input: Path to validate (string or Path object)
        must_exist: Whether path must exist (default: False)
        allowed_dirs: Whitelist of allowed directories for
            path traversal prevention (default: None)

    Returns:
        Validated Path object, resolved if whitelist provided

    Raises:
        FileNotFoundError: If must_exist=True and path doesn't exist
        SecurityError: If path outside allowed directories (CWE-22)
        ValueError: If path is invalid or malformed

    Example:
        >>> # Basic usage
        >>> path = validate_path("/tmp/file.txt")
        >>>
        >>> # With whitelist (security hardening)
        >>> path = validate_path(
        ...     "/tmp/file.txt",
        ...     allowed_dirs=[Path("/tmp"), Path("/var/tmp")]
        ... )

    Security:
        - CWE-22 Prevention: Path traversal via whitelist validation
        - CWE-59 Prevention: Symlink resolution before validation
        - Boundary Checking: Ensures path within allowed directories

    See:
        - skills/library-design-patterns: Progressive enhancement pattern
        - skills/security-patterns: Comprehensive security guidance
    """
```

### Example 3: Complex Class

```python
class BatchStateManager:
    """Manage persistent state for batch feature processing.

    Provides crash recovery, progress tracking, and automatic context
    clearing for /batch-implement command. State persists across Claude
    restarts via JSON file storage with atomic writes.

    Features:
        - Persistent state across crashes
        - Automatic context clearing at 150K tokens
        - Progress tracking (completed/failed features)
        - Resume capability with --resume flag

    Attributes:
        batch_id: Unique identifier for this batch operation
        state_file: Path to persistent state JSON file
        features: List of all features to process
        current_index: Index of currently processing feature

    Example:
        >>> manager = BatchStateManager.create(["feat1", "feat2"])
        >>> manager.batch_id
        'batch-20251116-123456'
        >>> manager.mark_completed("feat1")
        >>> manager.save()
        >>>
        >>> # Later, after crash
        >>> manager = BatchStateManager.load("batch-20251116-123456")
        >>> manager.get_next_feature()
        'feat2'

    Security:
        - CWE-22 Prevention: State file path validated
        - Atomic Writes: Prevents corruption on crash
        - File Locking: Prevents concurrent access issues

    See:
        - skills/state-management-patterns: State persistence patterns
        - /batch-implement command: Primary consumer
        - Issue #75: Initial implementation
    """
```

---

## Style Guidelines

### Formatting

- **Line length**: 80 characters for docstring text (not code examples)
- **Indentation**: 4 spaces (match Python code)
- **Blank lines**: One blank line between sections
- **Lists**: Use - or * for bullet lists

### Language

- **Tense**: Present tense ("Returns result" not "Will return result")
- **Mood**: Imperative for summary ("Calculate value" not "Calculates value")
- **Voice**: Active voice preferred ("Function processes" not "Is processed")
- **Clarity**: Simple, direct language; avoid jargon when possible

### Common Phrases

- ✅ "Validate input" (imperative)
- ❌ "Validates input" (present tense)

- ✅ "If arg is None" (clear)
- ❌ "When arg isn't specified" (wordy)

- ✅ "Path to file" (concise)
- ❌ "The path to the file" (verbose)

---

## Checklist

When writing docstrings:

- [ ] One-line summary in imperative mood
- [ ] All parameters documented in Args section
- [ ] Return value documented in Returns section
- [ ] All exceptions documented in Raises section
- [ ] Example provided for non-trivial usage
- [ ] Security section for security-sensitive functions
- [ ] Cross-references to related functions/skills
- [ ] Type hints match docstring descriptions
- [ ] Default values explicitly noted
- [ ] No spelling or grammar errors

---

## Tools

### Validation

```python
# Validate docstring format
python -m pydocstyle path/to/file.py

# Generate documentation
python -m pdoc --html path/to/module.py
```

### IDE Support

- **VS Code**: Python extension provides docstring templates
- **PyCharm**: Auto-generates docstring skeleton on typing """
- **vim**: python-mode plugin provides docstring snippets

---

## References

- **Google Style Guide**: https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings
- **PEP 257**: Docstring Conventions
- **Template**: `templates/docstring-template.py`
- **Cross-Reference**: documentation-guide skill (comprehensive docs standards)
