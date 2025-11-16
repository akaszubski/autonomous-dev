#!/usr/bin/env python3
"""Progressive enhancement example from security_utils.py.

This example demonstrates the progressive enhancement pattern used in
autonomous-dev's path validation functionality. The pattern allows
starting with simple validation and progressively adding stronger
security without breaking existing code.

See:
    - plugins/autonomous-dev/lib/security_utils.py (actual implementation)
    - skills/library-design-patterns/docs/progressive-enhancement.md
"""

from pathlib import Path
from typing import Union, List, Optional


class SecurityError(Exception):
    """Raised when security validation fails."""
    pass


# ============================================================================
# PROGRESSIVE ENHANCEMENT: Three Levels
# ============================================================================

def validate_path_level1(path_input: Union[str, Path]) -> Path:
    """Level 1: Basic string → Path conversion.

    Minimal validation, maximum compatibility.

    Args:
        path_input: Path to validate (string or Path)

    Returns:
        Path object

    Example:
        >>> path = validate_path_level1("/tmp/file.txt")
        >>> isinstance(path, Path)
        True
    """
    # Level 1: Just convert to Path
    return Path(path_input) if isinstance(path_input, str) else path_input


def validate_path_level2(
    path_input: Union[str, Path],
    *,
    must_exist: bool = False
) -> Path:
    """Level 2: Add existence validation.

    Adds type safety and existence checking.

    Args:
        path_input: Path to validate (string or Path)
        must_exist: Whether path must exist (default: False)

    Returns:
        Path object

    Raises:
        FileNotFoundError: If must_exist=True and path doesn't exist
        ValueError: If path is not a file

    Example:
        >>> path = validate_path_level2("/tmp/file.txt", must_exist=True)
        >>> path.exists()
        True
    """
    # Level 1: String → Path conversion
    path = Path(path_input) if isinstance(path_input, str) else path_input

    # Level 2: Existence validation (opt-in)
    if must_exist and not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    if must_exist and not path.is_file():
        raise ValueError(f"Not a file: {path}")

    return path


def validate_path_level3(
    path_input: Union[str, Path],
    *,
    must_exist: bool = False,
    allowed_dirs: Optional[List[Path]] = None
) -> Path:
    """Level 3: Add whitelist security validation.

    Full security hardening with path traversal prevention.

    Args:
        path_input: Path to validate (string or Path)
        must_exist: Whether path must exist (default: False)
        allowed_dirs: Whitelist of allowed directories (default: None)

    Returns:
        Validated and resolved Path object

    Raises:
        FileNotFoundError: If must_exist=True and path doesn't exist
        SecurityError: If path outside allowed directories (CWE-22)
        ValueError: If path is invalid

    Example:
        >>> path = validate_path_level3(
        ...     "/tmp/file.txt",
        ...     allowed_dirs=[Path("/tmp"), Path("/var/tmp")]
        ... )
        >>> # Path is validated against whitelist

    Security:
        - CWE-22 Prevention: Path traversal via whitelist
        - CWE-59 Prevention: Symlink resolution
        - Boundary Checking: Ensures path within allowed directories
    """
    # Level 1: String → Path conversion
    path = Path(path_input) if isinstance(path_input, str) else path_input

    # Level 3: Whitelist validation (opt-in)
    if allowed_dirs:
        # Resolve symlinks (CWE-59 prevention)
        try:
            resolved_path = path.resolve(strict=must_exist)
        except (OSError, RuntimeError) as e:
            raise SecurityError(f"Cannot resolve path: {e}")

        # Check against whitelist (CWE-22 prevention)
        is_allowed = any(
            resolved_path.is_relative_to(allowed_dir.resolve())
            for allowed_dir in allowed_dirs
        )

        if not is_allowed:
            raise SecurityError(
                f"Path outside allowed directories: {resolved_path}\n"
                f"Allowed: {', '.join(str(d) for d in allowed_dirs)}"
            )

        path = resolved_path

    # Level 2: Existence validation (opt-in)
    if must_exist and not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    return path


# ============================================================================
# UNIFIED INTERFACE: All levels in one function
# ============================================================================

def validate_path(
    path_input: Union[str, Path],
    *,
    must_exist: bool = False,
    allowed_dirs: Optional[List[Path]] = None
) -> Path:
    """Validate path with progressive enhancement (unified interface).

    This function automatically applies the appropriate validation level
    based on which parameters are provided:

    - No optional params → Level 1 (string → Path)
    - must_exist=True → Level 2 (+ existence check)
    - allowed_dirs provided → Level 3 (+ security whitelist)

    Args:
        path_input: Path to validate (string or Path)
        must_exist: Whether path must exist (default: False)
        allowed_dirs: Whitelist of allowed directories (default: None)

    Returns:
        Validated Path object

    Raises:
        FileNotFoundError: If must_exist=True and path doesn't exist
        SecurityError: If path outside allowed directories (CWE-22)
        ValueError: If path is invalid

    Example:
        >>> # Level 1: Basic conversion
        >>> path = validate_path("/tmp/file.txt")
        >>>
        >>> # Level 2: With existence check
        >>> path = validate_path("/tmp/file.txt", must_exist=True)
        >>>
        >>> # Level 3: With security validation
        >>> path = validate_path(
        ...     "/tmp/file.txt",
        ...     must_exist=True,
        ...     allowed_dirs=[Path("/tmp")]
        ... )

    Security:
        - CWE-22 Prevention: Path traversal via whitelist (Level 3)
        - CWE-59 Prevention: Symlink resolution (Level 3)
        - Progressive: Security added without breaking compatibility
    """
    # Level 1: Always applied
    path = Path(path_input) if isinstance(path_input, str) else path_input

    # Level 3: Security validation (if requested)
    if allowed_dirs:
        try:
            resolved_path = path.resolve(strict=must_exist)
        except (OSError, RuntimeError) as e:
            raise SecurityError(f"Cannot resolve path: {e}")

        if not any(resolved_path.is_relative_to(d) for d in allowed_dirs):
            raise SecurityError(
                f"Path outside allowed directories: {resolved_path}\n"
                f"Allowed: {', '.join(str(d) for d in allowed_dirs)}"
            )

        path = resolved_path

    # Level 2: Existence validation (if requested)
    if must_exist and not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    return path


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

def example_usage():
    """Demonstrate progressive enhancement in action."""

    # Example 1: Basic usage (Level 1)
    # Works in any environment, minimal validation
    path = validate_path("data.txt")
    print(f"Level 1: {path}")

    # Example 2: Add existence check (Level 2)
    # Still backward compatible, adds safety
    try:
        path = validate_path("data.txt", must_exist=True)
        print(f"Level 2: {path}")
    except FileNotFoundError as e:
        print(f"Level 2: File doesn't exist - {e}")

    # Example 3: Add security validation (Level 3)
    # Maximum security, opt-in via parameter
    ALLOWED_DIRS = [
        Path("/tmp"),
        Path("/var/tmp"),
        Path.home() / "project"
    ]

    try:
        path = validate_path(
            "data.txt",
            must_exist=True,
            allowed_dirs=ALLOWED_DIRS
        )
        print(f"Level 3: {path}")
    except SecurityError as e:
        print(f"Level 3: Security validation failed - {e}")

    # Example 4: Different security contexts
    # Same function, different validation levels

    # Development: Minimal validation
    dev_config = {"allowed_dirs": None, "must_exist": False}
    path = validate_path("data.txt", **dev_config)

    # Production: Full security
    prod_config = {"allowed_dirs": ALLOWED_DIRS, "must_exist": True}
    try:
        path = validate_path("data.txt", **prod_config)
    except (FileNotFoundError, SecurityError):
        pass  # Handle security failure


def example_migration():
    """Show how existing code continues to work as validation is added."""

    # Version 1.0: Basic string support
    def v1_process_file(filepath: str) -> str:
        path = Path(filepath)  # No validation
        return path.read_text()

    # Version 1.1: Add Path support (BACKWARD COMPATIBLE)
    def v11_process_file(filepath: Union[str, Path]) -> str:
        path = validate_path(filepath)  # Level 1
        return path.read_text()

    # Version 1.2: Add existence check (BACKWARD COMPATIBLE)
    def v12_process_file(filepath: Union[str, Path]) -> str:
        path = validate_path(filepath, must_exist=True)  # Level 2
        return path.read_text()

    # Version 2.0: Add security (BACKWARD COMPATIBLE via optional param)
    def v20_process_file(
        filepath: Union[str, Path],
        *,
        allowed_dirs: Optional[List[Path]] = None
    ) -> str:
        path = validate_path(filepath, must_exist=True, allowed_dirs=allowed_dirs)  # Level 3
        return path.read_text()

    # Old code still works!
    result = v20_process_file("data.txt")  # Uses Level 2 (no whitelist)

    # New code gets security!
    result = v20_process_file("data.txt", allowed_dirs=[Path("/tmp")])  # Uses Level 3


if __name__ == "__main__":
    print("Progressive Enhancement Pattern Example")
    print("=" * 60)
    example_usage()
