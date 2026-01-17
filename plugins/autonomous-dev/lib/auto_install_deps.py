#!/usr/bin/env python3
"""
Auto Install Dependencies - Automatic dependency installation for missing packages

This library provides automatic dependency installation during test execution
when ImportError or ModuleNotFoundError is detected in pytest output.

Features:
- Parse pytest output for ImportError/ModuleNotFoundError
- Extract package names from error messages
- Validate package against project's requirements files (pyproject.toml, requirements.txt)
- Only install if package is in project's requirements (security)
- Use subprocess with shell=False (no command injection)
- Add timeout for pip install (30 seconds default)
- Environment variable: AUTO_INSTALL_DEPS=true to enable (default: false)

Security Features:
- NEVER install packages not in project's requirements
- NEVER use shell=True with pip
- Always validate package names against whitelist
- Log all install attempts for audit
- CWE-78 prevention: No shell=True, no command injection
- CWE-494 prevention: Only install from project requirements

Usage:
    from auto_install_deps import auto_install_missing_deps, extract_missing_packages

    # Parse pytest output and auto-install missing packages
    pytest_output = "ImportError: No module named 'requests'"
    installed = auto_install_missing_deps(pytest_output)
    print(f"Installed: {installed}")

    # Extract missing packages only (no installation)
    packages = extract_missing_packages(pytest_output)
    print(f"Missing: {packages}")

Environment Variables:
    AUTO_INSTALL_DEPS: Enable automatic dependency installation (default: false)
                      Values: "true", "yes", "1" enable
                      Example: AUTO_INSTALL_DEPS=true pytest tests/

Author: implementer agent
Date: 2026-01-18
Related: Auto-install deps feature request

Design Patterns:
    See library-design-patterns skill for standardized design patterns.
    See error-handling-patterns skill for exception hierarchy.
    See python-standards skill for code style and type hints.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Set, Dict, Any

# Import security utilities for audit logging
try:
    from security_utils import audit_log
except ImportError:
    # Graceful degradation if security_utils not available
    def audit_log(event: str, status: str, context: Dict[str, Any]) -> None:
        """Fallback audit logging."""
        pass


class AutoInstallError(Exception):
    """Base exception for auto-install errors."""
    pass


class PackageNotAllowedError(AutoInstallError):
    """Exception raised when package is not in project's requirements."""
    pass


class InstallTimeoutError(AutoInstallError):
    """Exception raised when pip install times out."""
    pass


class InstallFailedError(AutoInstallError):
    """Exception raised when pip install fails."""
    pass


# Import error patterns for pytest output
# Format: (pattern, group_index_for_package_name)
IMPORT_ERROR_PATTERNS = [
    # ImportError: No module named 'package'
    (re.compile(r"ImportError: No module named ['\"]([^'\"]+)['\"]"), 1),
    # ModuleNotFoundError: No module named 'package'
    (re.compile(r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]"), 1),
    # from package import ... (ImportError)
    (re.compile(r"from ([a-zA-Z0-9_]+) import.*ImportError"), 1),
    # import package (ModuleNotFoundError)
    (re.compile(r"import ([a-zA-Z0-9_]+).*ModuleNotFoundError"), 1),
]

# Package name mapping (PyPI name -> import name)
# For packages where the PyPI name differs from the import name
PACKAGE_NAME_MAPPING = {
    # Common mismatches
    "pillow": "PIL",
    "pyyaml": "yaml",
    "python-dateutil": "dateutil",
    "beautifulsoup4": "bs4",
    "opencv-python": "cv2",
    "scikit-learn": "sklearn",
    "opencv-contrib-python": "cv2",
    "python-dotenv": "dotenv",
    "msgpack-python": "msgpack",
    "pycryptodome": "Crypto",
    # Add more as needed
}

# Reverse mapping (import name -> PyPI name)
IMPORT_TO_PYPI = {v: k for k, v in PACKAGE_NAME_MAPPING.items()}


def _is_enabled() -> bool:
    """Check if auto-install is enabled via environment variable.

    Returns:
        True if AUTO_INSTALL_DEPS is set to true/yes/1 (case-insensitive)
    """
    env_value = os.getenv("AUTO_INSTALL_DEPS", "").strip().lower()
    return env_value in ("true", "yes", "1")


def extract_missing_packages(pytest_output: str) -> List[str]:
    """Extract missing package names from pytest output.

    Parses pytest output for ImportError and ModuleNotFoundError messages
    and extracts the package names.

    Args:
        pytest_output: Raw pytest output (stdout + stderr)

    Returns:
        List of unique package names that are missing (empty list if none)

    Examples:
        >>> output = "ImportError: No module named 'requests'"
        >>> extract_missing_packages(output)
        ['requests']

        >>> output = "ModuleNotFoundError: No module named 'numpy'"
        >>> extract_missing_packages(output)
        ['numpy']

        >>> output = "All tests passed"
        >>> extract_missing_packages(output)
        []
    """
    missing_packages: Set[str] = set()

    # Try each pattern
    for pattern, group_idx in IMPORT_ERROR_PATTERNS:
        matches = pattern.findall(pytest_output)
        for match in matches:
            # Get package name from regex group
            if isinstance(match, tuple):
                package = match[group_idx - 1] if len(match) >= group_idx else None
            else:
                package = match

            if package:
                # Extract base package name (remove submodules)
                # e.g., "requests.auth" -> "requests"
                base_package = package.split('.')[0]
                missing_packages.add(base_package)

    return sorted(list(missing_packages))


def _get_requirements_files(project_root: Optional[Path] = None) -> List[Path]:
    """Get list of requirements files to check.

    Args:
        project_root: Project root directory (default: auto-detect)

    Returns:
        List of Path objects for requirements files that exist

    Examples:
        >>> files = _get_requirements_files()
        >>> [f.name for f in files]
        ['requirements.txt', 'requirements-dev.txt', 'pyproject.toml']
    """
    if project_root is None:
        # Auto-detect project root (search for .git or .claude)
        current = Path.cwd()
        for _ in range(10):
            if (current / ".git").exists() or (current / ".claude").exists():
                project_root = current
                break
            if current.parent == current:
                break  # Reached filesystem root
            current = current.parent
        else:
            # Fallback to CWD
            project_root = Path.cwd()

    # Common requirements file locations
    candidates = [
        project_root / "requirements.txt",
        project_root / "requirements-dev.txt",
        project_root / "requirements-test.txt",
        project_root / "pyproject.toml",
        project_root / "setup.py",
        # Plugin-specific paths
        project_root / "plugins" / "autonomous-dev" / "requirements-dev.txt",
    ]

    # Return only files that exist
    return [f for f in candidates if f.exists()]


def _parse_requirements_file(file_path: Path) -> Set[str]:
    """Parse requirements file and extract package names.

    Supports:
    - requirements.txt format (package==version, package>=version, etc.)
    - pyproject.toml format (dependencies list)
    - setup.py format (install_requires list)

    Args:
        file_path: Path to requirements file

    Returns:
        Set of package names (normalized to lowercase)

    Examples:
        >>> # requirements.txt content: "requests==2.28.0\\nnumpy>=1.20.0"
        >>> _parse_requirements_file(Path("requirements.txt"))
        {'requests', 'numpy'}

        >>> # pyproject.toml content: dependencies = ["pytest>=7.0.0"]
        >>> _parse_requirements_file(Path("pyproject.toml"))
        {'pytest'}
    """
    packages: Set[str] = set()

    if not file_path.exists():
        return packages

    try:
        content = file_path.read_text(encoding="utf-8")
    except (IOError, OSError):
        return packages

    # Parse based on file type
    if file_path.name == "pyproject.toml":
        # Parse TOML format (simple regex, not full TOML parser)
        # Look for dependencies = ["package>=version", ...]
        matches = re.findall(r'["\']([a-zA-Z0-9_-]+)(?:[><=!]=|~=|@)', content)
        packages.update(pkg.lower() for pkg in matches)

    elif file_path.name == "setup.py":
        # Parse setup.py format (simple regex)
        # Look for install_requires = ["package>=version", ...]
        matches = re.findall(r'["\']([a-zA-Z0-9_-]+)(?:[><=!]=|~=|@)', content)
        packages.update(pkg.lower() for pkg in matches)

    else:
        # Parse requirements.txt format
        for line in content.splitlines():
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Skip URLs and git references
            if line.startswith(('http://', 'https://', 'git+', '-e')):
                continue

            # Extract package name (before ==, >=, <=, etc.)
            match = re.match(r'^([a-zA-Z0-9_-]+)', line)
            if match:
                packages.add(match.group(1).lower())

    return packages


def is_package_allowed(package: str, requirements_files: Optional[List[Path]] = None) -> bool:
    """Check if package is in project's requirements files.

    This is a security check to prevent installing arbitrary packages.
    Only packages explicitly listed in project requirements are allowed.

    Args:
        package: Package name to check (e.g., "requests", "numpy")
        requirements_files: List of requirements files to check (default: auto-detect)

    Returns:
        True if package is found in any requirements file, False otherwise

    Examples:
        >>> is_package_allowed("pytest")  # In requirements-dev.txt
        True

        >>> is_package_allowed("malicious-package")  # Not in any requirements
        False

    Security:
        - CWE-494 prevention: Only install from known-safe requirements
        - Checks both PyPI name and import name (using PACKAGE_NAME_MAPPING)
    """
    if requirements_files is None:
        requirements_files = _get_requirements_files()

    # Normalize package name to lowercase
    package_lower = package.lower()

    # Check if package is a known import name (e.g., "PIL" -> "pillow")
    pypi_name = IMPORT_TO_PYPI.get(package, package_lower)

    # Parse all requirements files
    allowed_packages: Set[str] = set()
    for req_file in requirements_files:
        allowed_packages.update(_parse_requirements_file(req_file))

    # Check both PyPI name and import name
    return package_lower in allowed_packages or pypi_name in allowed_packages


def install_package(package: str, timeout: int = 30) -> bool:
    """Install package using pip.

    Args:
        package: Package name to install (e.g., "requests", "numpy")
        timeout: Timeout in seconds (default: 30)

    Returns:
        True if installation succeeded, False otherwise

    Raises:
        PackageNotAllowedError: If package is not in project's requirements
        InstallTimeoutError: If installation times out
        InstallFailedError: If installation fails

    Security:
        - CWE-78 prevention: Uses shell=False (no command injection)
        - CWE-494 prevention: Only installs from project requirements
        - Audit logging for all install attempts

    Examples:
        >>> install_package("pytest")  # If in requirements-dev.txt
        True

        >>> install_package("malicious-package")  # Not in requirements
        Traceback (most recent call last):
        ...
        PackageNotAllowedError: Package 'malicious-package' not in project requirements
    """
    # Security check: Only install packages from project requirements
    if not is_package_allowed(package):
        error_msg = (
            f"Package '{package}' not in project requirements. "
            f"Refusing to install for security (CWE-494 prevention)."
        )
        audit_log("package_install", "denied", {
            "package": package,
            "reason": "not_in_requirements",
            "security_risk": True,
        })
        raise PackageNotAllowedError(error_msg)

    # Convert import name to PyPI name if needed
    pypi_package = IMPORT_TO_PYPI.get(package, package)

    # Build pip install command (shell=False for security)
    cmd = [
        sys.executable,  # Use same Python interpreter
        "-m",
        "pip",
        "install",
        pypi_package,
        "--quiet",  # Reduce output noise
    ]

    # Log install attempt
    audit_log("package_install", "started", {
        "package": pypi_package,
        "import_name": package,
        "timeout": timeout,
    })

    try:
        # Run pip install with timeout
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,  # CWE-78 prevention: Never use shell=True
        )

        if result.returncode == 0:
            # Installation succeeded
            audit_log("package_install", "success", {
                "package": pypi_package,
                "import_name": package,
            })
            return True
        else:
            # Installation failed
            error_msg = (
                f"Failed to install '{pypi_package}': {result.stderr.strip()}"
            )
            audit_log("package_install", "failed", {
                "package": pypi_package,
                "import_name": package,
                "returncode": result.returncode,
                "stderr": result.stderr[:500],  # Truncate for audit log
            })
            raise InstallFailedError(error_msg)

    except subprocess.TimeoutExpired:
        # Installation timed out
        error_msg = (
            f"Installation of '{pypi_package}' timed out after {timeout} seconds"
        )
        audit_log("package_install", "timeout", {
            "package": pypi_package,
            "import_name": package,
            "timeout": timeout,
        })
        raise InstallTimeoutError(error_msg)


def auto_install_missing_deps(pytest_output: str, timeout: int = 30) -> List[str]:
    """Automatically install missing dependencies from pytest output.

    This is the main entry point for auto-install functionality.

    Args:
        pytest_output: Raw pytest output (stdout + stderr)
        timeout: Timeout per package in seconds (default: 30)

    Returns:
        List of packages that were successfully installed (empty list if none)

    Raises:
        PackageNotAllowedError: If package is not in project's requirements
        InstallTimeoutError: If installation times out
        InstallFailedError: If installation fails

    Examples:
        >>> output = "ImportError: No module named 'requests'"
        >>> os.environ['AUTO_INSTALL_DEPS'] = 'true'
        >>> installed = auto_install_missing_deps(output)
        >>> print(installed)
        ['requests']

        >>> os.environ['AUTO_INSTALL_DEPS'] = 'false'
        >>> installed = auto_install_missing_deps(output)
        >>> print(installed)
        []

    Security:
        - Only runs if AUTO_INSTALL_DEPS=true
        - Only installs packages from project requirements
        - Audit logs all attempts
    """
    # Check if auto-install is enabled
    if not _is_enabled():
        return []

    # Extract missing packages from pytest output
    missing_packages = extract_missing_packages(pytest_output)

    if not missing_packages:
        return []

    # Install each missing package
    installed: List[str] = []
    for package in missing_packages:
        try:
            if install_package(package, timeout=timeout):
                installed.append(package)
        except (PackageNotAllowedError, InstallTimeoutError, InstallFailedError):
            # Skip packages that fail to install (logged by install_package)
            continue

    return installed


# Convenience functions for direct usage

def get_allowed_packages(requirements_files: Optional[List[Path]] = None) -> Set[str]:
    """Get set of all allowed packages from requirements files.

    Args:
        requirements_files: List of requirements files to check (default: auto-detect)

    Returns:
        Set of allowed package names (lowercase)

    Examples:
        >>> packages = get_allowed_packages()
        >>> 'pytest' in packages
        True
    """
    if requirements_files is None:
        requirements_files = _get_requirements_files()

    allowed: Set[str] = set()
    for req_file in requirements_files:
        allowed.update(_parse_requirements_file(req_file))

    return allowed
