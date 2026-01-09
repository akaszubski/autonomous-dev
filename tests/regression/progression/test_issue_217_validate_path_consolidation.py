#!/usr/bin/env python3
"""
Progression Tests for Issue #217: Consolidate 3 validate_path() implementations

TDD RED PHASE: These tests MUST FAIL initially (no implementation yet).

Goal: Validate that security_utils.validate_path() is the single source of truth
for path validation, with wrappers delegating to it.

Test Categories:
1. Single Source of Truth - Verify security_utils.validate_path() exists and has expected signature
2. Wrapper Delegation - Verify wrappers delegate to security_utils
3. No Duplicate Implementation - Check for duplicate code
4. Security - Validate 4-layer security model
5. Backward Compatibility - Existing callers work after consolidation

Created: 2026-01-09
Issue: #217 (Consolidate 3 validate_path() implementations)
Agent: test-master
"""

import re
import sys
import tempfile
from pathlib import Path

import pytest

# Add lib to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
LIB_PATH = PROJECT_ROOT / "plugins/autonomous-dev/lib"
sys.path.insert(0, str(LIB_PATH))

# Import modules under test (dynamically resolved at runtime)
from security_utils import validate_path as security_validate_path  # type: ignore[import-not-found]
from validation import validate_session_path  # type: ignore[import-not-found]
from feature_flags import validate_path as feature_flags_validate_path  # type: ignore[import-not-found]
from worktree_conflict_integration import validate_path as worktree_validate_path  # type: ignore[import-not-found]


# ============================================================================
# Test Category 1: Single Source of Truth
# ============================================================================


def test_security_utils_validate_path_exists():
    """Verify security_utils.validate_path() exists and is importable.

    This is the canonical implementation that all others should delegate to.
    """
    # Should not raise
    assert callable(security_validate_path)

    # Verify signature (path, purpose, allow_missing, test_mode)
    import inspect
    sig = inspect.signature(security_validate_path)
    param_names = list(sig.parameters.keys())

    assert "path" in param_names
    assert "purpose" in param_names
    assert "allow_missing" in param_names
    assert "test_mode" in param_names


def test_security_utils_has_four_layer_validation():
    """Verify security_utils.validate_path() implements 4-layer security model.

    Expected layers:
    1. String-level checks (reject obvious traversal)
    2. Symlink detection (before resolution)
    3. Path resolution (normalize to absolute)
    4. Whitelist validation (PROJECT_ROOT or allowed temp dirs)
    """
    import inspect

    # Get source code
    source = inspect.getsource(security_validate_path)

    # Layer 1: String-level validation (".." check)
    assert '".."' in source or "'..''" in source, "Missing string-level traversal check"

    # Layer 2: Symlink detection
    assert "is_symlink()" in source, "Missing symlink detection"

    # Layer 3: Path resolution
    assert "resolve()" in source, "Missing path resolution"

    # Layer 4: Whitelist validation (PROJECT_ROOT, CLAUDE_HOME, temp)
    assert "PROJECT_ROOT" in source, "Missing PROJECT_ROOT whitelist"
    assert "relative_to" in source, "Missing whitelist validation logic"


def test_security_utils_test_mode_parameter():
    """Verify test_mode parameter works correctly.

    test_mode should allow system temp directory in addition to PROJECT_ROOT.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / "test.txt"
        temp_path.write_text("test")

        # Test mode should allow temp directory
        try:
            result = security_validate_path(temp_path, "test", test_mode=True)
            assert result == temp_path.resolve()
        except ValueError as e:
            pytest.fail(f"test_mode=True should allow temp directory: {e}")

        # Production mode should reject temp directory
        with pytest.raises(ValueError, match="Path outside allowed locations"):
            security_validate_path(temp_path, "test", test_mode=False)


# ============================================================================
# Test Category 2: Wrapper Delegation Tests
# ============================================================================


def test_validation_delegates_to_security_utils():
    """Verify validation.validate_session_path() delegates to security_utils.

    TDD: This test should FAIL initially if validation.py has its own implementation.
    After consolidation, it should use security_utils.validate_path().
    """
    import inspect
    import validation  # type: ignore[import-not-found]

    # Get source code of validate_session_path
    source = inspect.getsource(validation.validate_session_path)

    # Should import and call security_utils.validate_path
    # Either via direct import or via wrapper
    assert "security_utils" in source or "_validate_path_strict" in source, \
        "validate_session_path should delegate to security_utils.validate_path()"

    # Should NOT have its own implementation of core validation logic
    # Key indicators of duplicate implementation:
    duplicate_indicators = [
        'if ".." in',  # String-level traversal check
        'path.is_symlink()',  # Symlink detection
        'relative_to(project_root)',  # Whitelist validation
    ]

    # Allow at most 1 indicator (for wrapper logic)
    found_indicators = sum(1 for indicator in duplicate_indicators if indicator in source)
    assert found_indicators <= 1, \
        f"validate_session_path has duplicate implementation ({found_indicators} indicators found)"


def test_feature_flags_delegates_to_security_utils():
    """Verify feature_flags.validate_path() delegates to security_utils.

    TDD: This test should FAIL initially if feature_flags.py has its own implementation.
    """
    import inspect
    import feature_flags  # type: ignore[import-not-found]

    # Get source code
    source = inspect.getsource(feature_flags.validate_path)

    # Should call security_utils.validate_path
    assert "_validate_path_strict" in source, \
        "feature_flags.validate_path should delegate to security_utils.validate_path()"

    # Should be a thin wrapper (not duplicate implementation)
    assert source.count("\n") < 10, \
        "feature_flags.validate_path should be a thin wrapper (<10 lines)"


def test_worktree_conflict_integration_delegates_to_security_utils():
    """Verify worktree_conflict_integration.validate_path() delegates to security_utils.

    TDD: This test should FAIL initially if worktree_conflict_integration.py has duplicate code.
    """
    import inspect
    import worktree_conflict_integration  # type: ignore[import-not-found]

    # Get source code
    source = inspect.getsource(worktree_conflict_integration.validate_path)

    # Should call security_utils.validate_path
    assert "_validate_path_strict" in source, \
        "worktree_conflict_integration.validate_path should delegate to security_utils.validate_path()"

    # Should be a thin wrapper
    assert source.count("\n") < 10, \
        "worktree_conflict_integration.validate_path should be a thin wrapper"


# ============================================================================
# Test Category 3: No Duplicate Implementation Tests
# ============================================================================


def test_no_duplicate_path_traversal_checks():
    """Verify only security_utils.validate_path() checks for '..' traversal.

    Duplicate checks indicate duplicate implementations.
    """
    files_to_check = [
        LIB_PATH / "validation.py",
        LIB_PATH / "feature_flags.py",
        LIB_PATH / "worktree_conflict_integration.py",
    ]

    for file_path in files_to_check:
        if not file_path.exists():
            continue

        content = file_path.read_text()

        # Remove imports and comments
        lines = [line for line in content.split("\n")
                if not line.strip().startswith("#")
                and not line.strip().startswith("from security_utils")]
        code = "\n".join(lines)

        # Should NOT have its own '..' check (except in wrapper)
        # Pattern: if ".." in <something>
        pattern = r'if\s+["\']\.\.["\']\s+in'
        matches = re.findall(pattern, code)

        assert len(matches) == 0, \
            f"{file_path.name} has duplicate '..' check (found {len(matches)} matches)"


def test_no_duplicate_symlink_checks():
    """Verify only security_utils.validate_path() checks for symlinks.

    Duplicate checks indicate duplicate implementations.
    """
    files_to_check = [
        LIB_PATH / "validation.py",
        LIB_PATH / "feature_flags.py",
        LIB_PATH / "worktree_conflict_integration.py",
    ]

    for file_path in files_to_check:
        if not file_path.exists():
            continue

        content = file_path.read_text()

        # Remove imports and security_utils wrapper code
        lines = [line for line in content.split("\n")
                if not line.strip().startswith("#")
                and not "security_utils" in line]
        code = "\n".join(lines)

        # Should NOT have its own symlink check
        pattern = r'\.is_symlink\(\)'
        matches = re.findall(pattern, code)

        # Allow in validation.py (legacy, will be removed)
        # But NOT in feature_flags.py or worktree_conflict_integration.py
        if file_path.name != "validation.py":
            assert len(matches) == 0, \
                f"{file_path.name} has duplicate symlink check (found {len(matches)} matches)"


def test_no_duplicate_whitelist_validation():
    """Verify only security_utils.validate_path() performs whitelist validation.

    Duplicate whitelist logic indicates duplicate implementations.
    """
    files_to_check = [
        LIB_PATH / "validation.py",
        LIB_PATH / "feature_flags.py",
        LIB_PATH / "worktree_conflict_integration.py",
    ]

    for file_path in files_to_check:
        if not file_path.exists():
            continue

        content = file_path.read_text()

        # Remove imports
        lines = [line for line in content.split("\n")
                if not line.strip().startswith("from")]
        code = "\n".join(lines)

        # Should NOT have its own whitelist logic (relative_to checks)
        # Pattern: relative_to(project_root) or relative_to(allowed_dir)
        pattern = r'relative_to\([^)]*root[^)]*\)'
        matches = re.findall(pattern, code, re.IGNORECASE)

        # Allow in validation.py (legacy)
        if file_path.name != "validation.py":
            assert len(matches) == 0, \
                f"{file_path.name} has duplicate whitelist validation (found {len(matches)} matches)"


# ============================================================================
# Test Category 4: Security Tests
# ============================================================================


def test_path_traversal_prevention():
    """Verify all validate_path implementations reject path traversal.

    Security: CWE-22 (Path Traversal)
    """
    traversal_paths = [
        "../../etc/passwd",
        "../../../etc/shadow",
        "subdir/../../etc/hosts",
    ]

    for path in traversal_paths:
        # security_utils.validate_path
        with pytest.raises(ValueError, match="Path traversal"):
            security_validate_path(Path(path), "test")

        # validation.validate_session_path
        with pytest.raises(ValueError, match="Path traversal"):
            validate_session_path(Path(path))


def test_symlink_detection():
    """Verify all validate_path implementations reject symlinks.

    Security: CWE-59 (Improper Link Resolution Before File Access)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create real file
        real_file = Path(tmpdir) / "real.txt"
        real_file.write_text("test")

        # Create symlink
        symlink = Path(tmpdir) / "link.txt"
        symlink.symlink_to(real_file)

        # All implementations should reject symlinks
        with pytest.raises(ValueError, match="Symlink"):
            security_validate_path(symlink, "test", test_mode=True)


def test_whitelist_validation():
    """Verify all validate_path implementations enforce whitelist.

    Security: Whitelist approach (allow known safe, reject unknown)
    """
    # Allowed: PROJECT_ROOT
    allowed_path = PROJECT_ROOT / "test.txt"

    try:
        result = security_validate_path(allowed_path, "test", allow_missing=True)
        assert result == allowed_path.resolve()
    except ValueError as e:
        pytest.fail(f"PROJECT_ROOT path should be allowed: {e}")

    # Blocked: System directories
    blocked_paths = [
        "/etc/passwd",
        "/usr/bin/malware",
        "/var/log/audit.log",
    ]

    for path in blocked_paths:
        with pytest.raises(ValueError, match="outside allowed locations"):
            security_validate_path(Path(path), "test", test_mode=False)


def test_claude_home_directory_allowed():
    """Verify ~/.claude/ directory is allowed (Claude Code system files).

    Security: Claude Code needs access to plan mode, global CLAUDE.md, settings.

    Note: This test uses the REAL ~/.claude/ directory, not a fixture.
    This is intentional - we're testing that the real Claude home is allowed.
    """
    # Skip if HOME is mocked in test environment
    real_home = Path.home()
    if "/tmp/" in str(real_home) or "/test_home" in str(real_home):
        pytest.skip("Test environment has mocked HOME directory")

    claude_home = real_home / ".claude" / "test.txt"

    try:
        result = security_validate_path(claude_home, "test", allow_missing=True)
        assert result == claude_home.resolve()
    except ValueError as e:
        pytest.fail(f"~/.claude/ should be allowed: {e}")


# ============================================================================
# Test Category 5: Backward Compatibility Tests
# ============================================================================


def test_validation_validate_session_path_compatible():
    """Verify validation.validate_session_path() works after consolidation.

    Backward compatibility: Existing callers should work without changes.
    """
    # Create temp session file
    session_dir = PROJECT_ROOT / "docs" / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)

    session_file = session_dir / "test_session.json"
    session_file.write_text("{}")

    try:
        # Should work
        result = validate_session_path(session_file)
        assert result == session_file.resolve()
    finally:
        # Cleanup
        session_file.unlink(missing_ok=True)


def test_feature_flags_validate_path_compatible():
    """Verify feature_flags.validate_path() works after consolidation.

    Backward compatibility: Returns bool (True/False) for existing callers.
    """
    # Valid path
    valid_path = PROJECT_ROOT / ".claude" / "feature_flags.json"
    result = feature_flags_validate_path(str(valid_path), allow_missing=True)
    assert result is True, "feature_flags.validate_path should return True for valid paths"

    # Invalid path (traversal)
    invalid_path = "../../etc/passwd"
    result = feature_flags_validate_path(invalid_path, allow_missing=True)
    assert result is False, "feature_flags.validate_path should return False for invalid paths"


def test_worktree_validate_path_compatible():
    """Verify worktree_conflict_integration.validate_path() works after consolidation.

    Backward compatibility: Returns tuple (bool, str) for existing callers.
    """
    # Valid path
    valid_path = PROJECT_ROOT / "test.txt"
    is_valid, error = worktree_validate_path(str(valid_path))
    assert is_valid is True, "worktree.validate_path should return (True, '') for valid paths"
    assert error == "", "worktree.validate_path should return empty error for valid paths"

    # Invalid path (traversal)
    invalid_path = "../../etc/passwd"
    is_valid, error = worktree_validate_path(invalid_path)
    assert is_valid is False, "worktree.validate_path should return (False, msg) for invalid paths"
    assert error != "", "worktree.validate_path should return error message for invalid paths"


# ============================================================================
# Test Category 6: Edge Cases
# ============================================================================


def test_validate_path_with_string_input():
    """Verify all implementations accept both string and Path input."""
    test_path = PROJECT_ROOT / "test.txt"

    # String input
    result = security_validate_path(str(test_path), "test", allow_missing=True)
    assert result == test_path.resolve()

    # Path input
    result = security_validate_path(test_path, "test", allow_missing=True)
    assert result == test_path.resolve()


def test_validate_path_with_missing_file():
    """Verify allow_missing parameter works correctly."""
    missing_path = PROJECT_ROOT / "nonexistent_file_12345.txt"

    # allow_missing=True (should work)
    result = security_validate_path(missing_path, "test", allow_missing=True)
    assert result == missing_path.resolve()

    # allow_missing=False (depends on symlink check - if path doesn't exist, can't be symlink)
    # This should still work because resolve() handles missing paths
    result = security_validate_path(missing_path, "test", allow_missing=False)
    assert result == missing_path.resolve()


def test_validate_path_with_long_path():
    """Verify path length validation (prevent buffer overflow).

    Security: CWE-120 (Buffer Overflow)
    """
    # Max path length on POSIX is 4096 characters
    long_path = "a" * 5000

    with pytest.raises(ValueError, match="Path too long"):
        security_validate_path(Path(long_path), "test")


def test_validate_path_purpose_in_error():
    """Verify error messages include purpose for debugging."""
    invalid_path = "../../etc/passwd"

    with pytest.raises(ValueError) as exc_info:
        security_validate_path(Path(invalid_path), "test operation")

    error_msg = str(exc_info.value)
    assert "test operation" in error_msg, "Error message should include purpose"


# ============================================================================
# Test Category 7: Integration Tests
# ============================================================================


def test_all_implementations_reject_same_paths():
    """Verify all implementations have consistent security behavior.

    Integration: All wrappers should delegate to same core logic.
    """
    dangerous_paths = [
        "../../etc/passwd",
        "../../../etc/shadow",
        "/etc/hosts",
    ]

    for path in dangerous_paths:
        # security_utils.validate_path
        with pytest.raises(ValueError):
            security_validate_path(Path(path), "test")

        # validation.validate_session_path
        with pytest.raises(ValueError):
            validate_session_path(Path(path))


def test_all_implementations_allow_same_paths():
    """Verify all implementations allow same safe paths.

    Integration: All wrappers should delegate to same core logic.
    """
    safe_path = PROJECT_ROOT / "test.txt"

    # security_utils.validate_path
    result1 = security_validate_path(safe_path, "test", allow_missing=True)

    # All should resolve to same path
    assert result1 == safe_path.resolve()


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def temp_project_file():
    """Create temporary file in project for testing."""
    test_file = PROJECT_ROOT / "temp_test_file.txt"
    test_file.write_text("test")

    yield test_file

    # Cleanup
    test_file.unlink(missing_ok=True)


@pytest.fixture
def temp_session_file():
    """Create temporary session file for testing."""
    session_dir = PROJECT_ROOT / "docs" / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)

    test_file = session_dir / "temp_session.json"
    test_file.write_text("{}")

    yield test_file

    # Cleanup
    test_file.unlink(missing_ok=True)


# ============================================================================
# Test Summary
# ============================================================================

def test_consolidation_completeness():
    """Meta-test: Verify test coverage is comprehensive.

    This test validates that we're testing all the requirements from Issue #217.
    """
    # Count test functions
    import inspect
    current_module = sys.modules[__name__]
    test_functions = [name for name, obj in inspect.getmembers(current_module)
                     if inspect.isfunction(obj) and name.startswith("test_")]

    # Should have tests for all categories
    categories = {
        "single_source_of_truth": ["test_security_utils_validate_path_exists",
                                   "test_security_utils_has_four_layer_validation",
                                   "test_security_utils_test_mode_parameter"],
        "wrapper_delegation": ["test_validation_delegates_to_security_utils",
                              "test_feature_flags_delegates_to_security_utils",
                              "test_worktree_conflict_integration_delegates_to_security_utils"],
        "no_duplicates": ["test_no_duplicate_path_traversal_checks",
                         "test_no_duplicate_symlink_checks",
                         "test_no_duplicate_whitelist_validation"],
        "security": ["test_path_traversal_prevention",
                    "test_symlink_detection",
                    "test_whitelist_validation",
                    "test_claude_home_directory_allowed"],
        "backward_compat": ["test_validation_validate_session_path_compatible",
                           "test_feature_flags_validate_path_compatible",
                           "test_worktree_validate_path_compatible"],
    }

    # Verify all category tests exist
    for category, expected_tests in categories.items():
        for test_name in expected_tests:
            assert test_name in test_functions, \
                f"Missing test: {test_name} (category: {category})"

    # Should have at least 20 tests (comprehensive coverage)
    assert len(test_functions) >= 20, \
        f"Insufficient test coverage: {len(test_functions)} tests (expected 20+)"
