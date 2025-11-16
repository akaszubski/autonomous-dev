# Progressive Enhancement Pattern

**Pattern Type**: Validation & Security
**Skill**: library-design-patterns
**Version**: 1.0.0

---

## Overview

Progressive enhancement is a pattern where validation and security features are added incrementally, starting with basic functionality and progressively adding stronger validation without breaking existing code.

**Core Principle**: Start simple, add complexity gradually, maintain backward compatibility.

---

## Pattern Levels

### Level 1: String-Based (Basic)

**Characteristics**:
- Accept string paths
- Minimal validation
- Maximum compatibility
- Works in any environment

**Example**:
```python
def process_file(filepath: str) -> Result:
    """Process file at given path.

    Args:
        filepath: Path to file (string)

    Returns:
        Processing result
    """
    # Basic operation, no validation
    with open(filepath, 'r') as f:
        data = f.read()
    return _process(data)
```

**Use Case**: Initial implementation, maximum compatibility

---

### Level 2: Path Objects (Type Safety)

**Characteristics**:
- Accept both strings and Path objects
- Type conversion for flexibility
- Basic existence validation
- Cross-platform path handling

**Example**:
```python
from pathlib import Path
from typing import Union

def process_file(filepath: Union[str, Path]) -> Result:
    """Process file at given path.

    Args:
        filepath: Path to file (string or Path object)

    Returns:
        Processing result

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    # Convert to Path for type safety
    path = Path(filepath) if isinstance(filepath, str) else filepath

    # Add existence validation
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Check if it's a file (not directory)
    if not path.is_file():
        raise ValueError(f"Not a file: {path}")

    with path.open('r') as f:
        data = f.read()
    return _process(data)
```

**Use Case**: Production code with basic safety

---

### Level 3: Whitelist Validation (Security)

**Characteristics**:
- Path whitelist enforcement
- Symlink resolution
- Path traversal prevention (CWE-22)
- Full security hardening

**Example**:
```python
from pathlib import Path
from typing import Union, List, Optional

class SecurityError(Exception):
    """Raised when security validation fails."""
    pass

def process_file(
    filepath: Union[str, Path],
    *,
    allowed_dirs: Optional[List[Path]] = None
) -> Result:
    """Process file at given path with security validation.

    Args:
        filepath: Path to file (string or Path object)
        allowed_dirs: Whitelist of allowed directories (optional)

    Returns:
        Processing result

    Raises:
        FileNotFoundError: If file doesn't exist
        SecurityError: If path outside allowed directories
        ValueError: If path is not a file

    Security:
        - CWE-22 Prevention: Path traversal validation via whitelist
        - Symlink Resolution: Resolves symlinks before validation
        - Boundary Checking: Ensures path within allowed directories
    """
    # Convert to Path for type safety
    path = Path(filepath) if isinstance(filepath, str) else filepath

    # Resolve symlinks (security)
    try:
        path = path.resolve(strict=True)
    except (OSError, RuntimeError) as e:
        raise SecurityError(f"Cannot resolve path: {e}")

    # Whitelist validation (CWE-22 prevention)
    if allowed_dirs:
        if not any(path.is_relative_to(allowed_dir) for allowed_dir in allowed_dirs):
            raise SecurityError(
                f"Path outside allowed directories: {path}\n"
                f"Allowed: {', '.join(str(d) for d in allowed_dirs)}"
            )

    # Existence validation
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Type validation
    if not path.is_file():
        raise ValueError(f"Not a file: {path}")

    # Process with full security
    with path.open('r') as f:
        data = f.read()
    return _process(data)
```

**Use Case**: Security-sensitive production code

---

## Migration Strategy

### Gradual Enhancement

```python
# Version 1.0: Basic string support
def process_file(filepath: str) -> Result:
    with open(filepath, 'r') as f:
        return _process(f.read())

# Version 1.1: Add Path support (backward compatible)
def process_file(filepath: Union[str, Path]) -> Result:
    path = Path(filepath) if isinstance(filepath, str) else filepath
    with path.open('r') as f:
        return _process(f.read())

# Version 1.2: Add validation (backward compatible)
def process_file(filepath: Union[str, Path]) -> Result:
    path = Path(filepath) if isinstance(filepath, str) else filepath
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with path.open('r') as f:
        return _process(f.read())

# Version 2.0: Add security (opt-in via parameter)
def process_file(
    filepath: Union[str, Path],
    *,
    allowed_dirs: Optional[List[Path]] = None
) -> Result:
    path = Path(filepath) if isinstance(filepath, str) else filepath

    # Whitelist validation (opt-in)
    if allowed_dirs:
        path = path.resolve(strict=True)
        if not any(path.is_relative_to(d) for d in allowed_dirs):
            raise SecurityError(f"Path outside allowed directories")

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open('r') as f:
        return _process(f.read())
```

**Key Insight**: Each version is backward compatible. Existing code continues to work as validation is added.

---

## Real-World Example: security_utils.py

The `security_utils.py` library demonstrates progressive enhancement:

```python
# plugins/autonomous-dev/lib/security_utils.py

from pathlib import Path
from typing import Union, List, Optional

def validate_path(
    path_input: Union[str, Path],
    *,
    must_exist: bool = False,
    allowed_dirs: Optional[List[Path]] = None,
    allow_symlinks: bool = False
) -> Path:
    """Validate and sanitize file path with progressive security.

    Progressive Enhancement Levels:
    1. String/Path conversion (always)
    2. Existence validation (if must_exist=True)
    3. Whitelist validation (if allowed_dirs provided)
    4. Symlink validation (if allow_symlinks=False)

    Args:
        path_input: Path to validate (string or Path)
        must_exist: Whether path must exist (default: False)
        allowed_dirs: Whitelist of allowed directories (optional)
        allow_symlinks: Whether to allow symlinks (default: False)

    Returns:
        Validated Path object

    Raises:
        FileNotFoundError: If must_exist=True and path doesn't exist
        SecurityError: If path outside allowed directories
        ValueError: If path is invalid

    Security:
        - CWE-22: Path traversal prevention via whitelist
        - CWE-59: Symlink following protection
    """
    # Level 1: String to Path conversion
    path = Path(path_input) if isinstance(path_input, str) else path_input

    # Level 2: Existence validation (opt-in)
    if must_exist and not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    # Level 3: Symlink validation (opt-in)
    if not allow_symlinks and path.is_symlink():
        raise ValueError(f"Symlinks not allowed: {path}")

    # Level 4: Whitelist validation (opt-in)
    if allowed_dirs:
        try:
            resolved = path.resolve(strict=must_exist)
        except (OSError, RuntimeError) as e:
            raise ValueError(f"Cannot resolve path: {e}")

        if not any(resolved.is_relative_to(d) for d in allowed_dirs):
            raise SecurityError(
                f"Path outside allowed directories: {resolved}\n"
                f"Allowed: {', '.join(str(d) for d in allowed_dirs)}"
            )

        return resolved

    return path
```

**Usage**:
```python
# Basic usage (Level 1)
path = validate_path("/tmp/file.txt")

# With existence check (Level 2)
path = validate_path("/tmp/file.txt", must_exist=True)

# With whitelist (Level 3)
path = validate_path(
    "/tmp/file.txt",
    allowed_dirs=[Path("/tmp"), Path("/var/tmp")]
)

# Full security (Level 4)
path = validate_path(
    "/tmp/file.txt",
    must_exist=True,
    allowed_dirs=[Path("/tmp")],
    allow_symlinks=False
)
```

---

## Benefits

### 1. Graceful Degradation

Code works even when security features unavailable:

```python
# High-security environment
path = validate_path(user_input, allowed_dirs=[SAFE_DIR])

# Low-security environment (development, testing)
path = validate_path(user_input)  # Still works, less validation
```

### 2. Backward Compatibility

Existing code continues to work as new validation is added:

```python
# Old code (still works)
result = process_file("data.txt")

# New code (uses enhanced validation)
result = process_file("data.txt", allowed_dirs=[DATA_DIR])
```

### 3. Opt-In Security

Security features are opt-in via parameters:

```python
def process_file(
    filepath: Union[str, Path],
    *,
    allowed_dirs: Optional[List[Path]] = None,  # Opt-in security
    must_exist: bool = False  # Opt-in validation
) -> Result:
    # Security applied only if allowed_dirs provided
    if allowed_dirs:
        path = validate_path(filepath, allowed_dirs=allowed_dirs)
    else:
        path = Path(filepath)
```

### 4. Flexible Deployment

Same code works in different security contexts:

```python
# Production (high security)
config = {
    "allowed_dirs": [PROJECT_DIR, DATA_DIR],
    "must_exist": True
}

# Development (low security)
config = {
    "allowed_dirs": None,
    "must_exist": False
}

# Use same function with different config
result = process_file(input_path, **config)
```

---

## Anti-Patterns

### ❌ All-or-Nothing Validation

```python
# Bad: Forces all validation always
def process_file(filepath: str, allowed_dirs: List[Path]) -> Result:
    # Can't use without whitelist!
    if not any(Path(filepath).is_relative_to(d) for d in allowed_dirs):
        raise SecurityError("Not allowed")
```

### ✅ Progressive Validation

```python
# Good: Validation is progressive and opt-in
def process_file(
    filepath: Union[str, Path],
    *,
    allowed_dirs: Optional[List[Path]] = None  # Optional!
) -> Result:
    # Works without whitelist, adds security when provided
    if allowed_dirs:
        path = validate_path(filepath, allowed_dirs=allowed_dirs)
    else:
        path = Path(filepath)
```

---

### ❌ Breaking Changes

```python
# Version 1.0
def process_file(filepath: str) -> Result:
    pass

# Version 2.0 (BREAKS EXISTING CODE!)
def process_file(filepath: Path, allowed_dirs: List[Path]) -> Result:
    # Changed required parameter types!
    pass
```

### ✅ Backward Compatible Enhancement

```python
# Version 1.0
def process_file(filepath: str) -> Result:
    pass

# Version 2.0 (BACKWARD COMPATIBLE)
def process_file(
    filepath: Union[str, Path],  # Still accepts strings!
    *,
    allowed_dirs: Optional[List[Path]] = None  # Optional new feature!
) -> Result:
    pass
```

---

## Checklist

When implementing progressive enhancement:

- [ ] Start with simple type (string)
- [ ] Add Union[str, Path] for flexibility
- [ ] Convert string to Path internally
- [ ] Add optional validation parameters (allowed_dirs, must_exist)
- [ ] Make security features opt-in (not required)
- [ ] Maintain backward compatibility at each level
- [ ] Document each enhancement level
- [ ] Test with and without enhancements
- [ ] Provide migration guide for users

---

## References

- **Template**: `templates/library-template.py` (shows progressive enhancement)
- **Example**: `examples/progressive-enhancement-example.py`
- **Real Implementation**: `plugins/autonomous-dev/lib/security_utils.py`
- **Related Patterns**: Two-tier design, security-first design
- **Cross-Reference**: security-patterns skill
