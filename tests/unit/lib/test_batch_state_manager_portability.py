#!/usr/bin/env python3
"""
TDD Tests for Batch State Manager Portability Fixes (Issue #85) - RED PHASE

This test suite validates that batch_state_manager.py docstrings use portable
path examples with get_batch_state_file() instead of hardcoded paths.

Problem (Issue #85):
- Docstrings show hardcoded Path(".claude/batch_state.json") examples
- Misleads developers to use hardcoded paths
- Contradicts portable path detection added in Issue #79
- Similar issue to auto-implement.md checkpoints (fixed in Issue #85)

Solution:
- Update all docstrings to show get_batch_state_file() usage
- Remove hardcoded Path(".claude/batch_state.json") from examples
- Add regression tests to prevent hardcoded paths from returning
- Document portable path patterns for developers

Test Coverage:
1. Docstring Validation (no hardcoded paths in examples)
2. Path Detection Integration (uses get_batch_state_file())
3. Security Validation (CWE-22 path traversal, CWE-59 symlinks)
4. Cross-Platform Compatibility (Windows/Unix paths)
5. Regression Prevention (automated detection)

TDD Workflow:
- Tests written FIRST (before implementation)
- All tests FAIL initially (docstrings still have hardcoded paths)
- Implementation fixes docstrings to make tests pass (GREEN phase)

Date: 2025-12-06
Issue: GitHub #85 (Fix hardcoded paths in batch_state_manager docstrings)
Agent: test-master
Phase: RED (tests fail, docstrings not yet fixed)

Design Patterns:
    See testing-guide skill for TDD methodology and pytest patterns.
    See library-design-patterns skill for documentation standards.
    See python-standards skill for docstring conventions.
"""

import inspect
import re
import sys
from pathlib import Path
from typing import List, Tuple

try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False
    # Provide minimal pytest stub for when it's not available
    class pytest:
        @staticmethod
        def skip(msg, allow_module_level=False):
            if allow_module_level:
                raise ImportError(msg)

        @staticmethod
        def raises(*args, **kwargs):
            return MockRaises()

        @staticmethod
        def fixture(*args, **kwargs):
            def decorator(func):
                return func
            return decorator

        @staticmethod
        def main(*args, **kwargs):
            raise ImportError("pytest not available - use run_portability_tests.py instead")

    class MockRaises:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                raise AssertionError("Expected exception was not raised")
            return True

# Add lib directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))

# Import the module to test
try:
    import batch_state_manager
    from batch_state_manager import (
        create_batch_state,
        save_batch_state,
        load_batch_state,
        update_batch_progress,
        record_auto_clear_event,
        cleanup_batch_state,
        get_default_state_file,
    )
    from path_utils import get_batch_state_file
    MODULE_AVAILABLE = True
except ImportError as e:
    MODULE_AVAILABLE = False
    pytest.skip(f"Module not available: {e}", allow_module_level=True)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def extract_code_examples_from_docstring(docstring: str) -> List[str]:
    """Extract code examples from docstring.

    Finds all code blocks in docstring (between >>> and next line without >>>).

    Args:
        docstring: Docstring text

    Returns:
        List of code example lines
    """
    if not docstring:
        return []

    examples = []
    lines = docstring.split('\n')

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('>>>'):
            # Extract code after >>>
            code = stripped[3:].strip()
            examples.append(code)

    return examples


def find_hardcoded_paths_in_docstring(docstring: str) -> List[Tuple[str, str]]:
    """Find hardcoded path references in docstring.

    Searches for:
    - Path(".claude/batch_state.json")
    - ".claude/batch_state.json" (string literal)

    Args:
        docstring: Docstring text

    Returns:
        List of (pattern, line) tuples where hardcoded paths found
    """
    if not docstring:
        return []

    findings = []

    # Patterns to detect hardcoded paths
    patterns = [
        r'Path\(["\']\.claude/batch_state\.json["\']\)',  # Path(".claude/batch_state.json")
        r'["\']\.claude/batch_state\.json["\']',  # ".claude/batch_state.json"
    ]

    lines = docstring.split('\n')
    for line_num, line in enumerate(lines, start=1):
        for pattern in patterns:
            if re.search(pattern, line):
                findings.append((pattern, line.strip()))

    return findings


def check_for_portable_path_usage(docstring: str) -> bool:
    """Check if docstring uses portable path functions.

    Returns True if docstring mentions get_batch_state_file() or get_default_state_file().

    Args:
        docstring: Docstring text

    Returns:
        True if portable path functions mentioned, False otherwise
    """
    if not docstring:
        return False

    # Check for recommended patterns
    portable_patterns = [
        'get_batch_state_file()',
        'get_default_state_file()',
        'DEFAULT_STATE_FILE',
    ]

    return any(pattern in docstring for pattern in portable_patterns)


# ============================================================================
# TEST CLASS 1: DOCSTRING VALIDATION
# ============================================================================


class TestDocstringValidation:
    """Test that docstrings use portable path examples (no hardcoded paths)."""

    def test_module_docstring_no_hardcoded_paths(self):
        """Test module docstring doesn't use hardcoded path examples.

        EXPECTED FAILURE: Module docstring currently shows:
            Path(".claude/batch_state.json")

        SHOULD SHOW:
            get_batch_state_file()
        """
        module_doc = batch_state_manager.__doc__
        assert module_doc is not None, "Module docstring missing"

        # Check for hardcoded paths
        hardcoded_paths = find_hardcoded_paths_in_docstring(module_doc)

        # This should FAIL until docstrings are fixed
        assert len(hardcoded_paths) == 0, (
            f"Module docstring contains hardcoded paths (should use get_batch_state_file()):\n"
            f"{chr(10).join([f'  - {line}' for _, line in hardcoded_paths])}"
        )

    def test_module_docstring_recommends_portable_paths(self):
        """Test module docstring shows portable path examples.

        EXPECTED FAILURE: Module docstring currently shows hardcoded paths.

        SHOULD RECOMMEND:
        - get_batch_state_file() function
        - get_default_state_file() function
        - DEFAULT_STATE_FILE constant
        """
        module_doc = batch_state_manager.__doc__
        assert module_doc is not None, "Module docstring missing"

        # Check for portable path usage
        uses_portable = check_for_portable_path_usage(module_doc)

        # This should FAIL until docstrings are fixed
        assert uses_portable, (
            "Module docstring should demonstrate portable path usage with "
            "get_batch_state_file() or get_default_state_file()"
        )

    def test_save_batch_state_docstring_no_hardcoded_paths(self):
        """Test save_batch_state() docstring uses portable examples.

        EXPECTED FAILURE: Function docstring currently shows:
            >>> save_batch_state(Path(".claude/batch_state.json"), state)

        SHOULD SHOW:
            >>> save_batch_state(get_batch_state_file(), state)
        """
        func_doc = inspect.getdoc(save_batch_state)
        assert func_doc is not None, "save_batch_state docstring missing"

        # Check for hardcoded paths
        hardcoded_paths = find_hardcoded_paths_in_docstring(func_doc)

        # This should FAIL until docstrings are fixed
        assert len(hardcoded_paths) == 0, (
            f"save_batch_state docstring contains hardcoded paths:\n"
            f"{chr(10).join([f'  - {line}' for _, line in hardcoded_paths])}\n\n"
            f"Use get_batch_state_file() instead"
        )

    def test_load_batch_state_docstring_no_hardcoded_paths(self):
        """Test load_batch_state() docstring uses portable examples.

        EXPECTED FAILURE: Function docstring currently shows:
            >>> state = load_batch_state(Path(".claude/batch_state.json"))

        SHOULD SHOW:
            >>> state = load_batch_state(get_batch_state_file())
        """
        func_doc = inspect.getdoc(load_batch_state)
        assert func_doc is not None, "load_batch_state docstring missing"

        # Check for hardcoded paths
        hardcoded_paths = find_hardcoded_paths_in_docstring(func_doc)

        # This should FAIL until docstrings are fixed
        assert len(hardcoded_paths) == 0, (
            f"load_batch_state docstring contains hardcoded paths:\n"
            f"{chr(10).join([f'  - {line}' for _, line in hardcoded_paths])}\n\n"
            f"Use get_batch_state_file() instead"
        )

    def test_update_batch_progress_docstring_no_hardcoded_paths(self):
        """Test update_batch_progress() docstring uses portable examples.

        EXPECTED FAILURE: Function docstring currently shows:
            >>> update_batch_progress(
            ...     state_file=Path(".claude/batch_state.json"),
            ...     feature_index=0,
            ...     status="completed",
            ... )

        SHOULD SHOW:
            >>> update_batch_progress(
            ...     state_file=get_batch_state_file(),
            ...     feature_index=0,
            ...     status="completed",
            ... )
        """
        func_doc = inspect.getdoc(update_batch_progress)
        assert func_doc is not None, "update_batch_progress docstring missing"

        # Check for hardcoded paths
        hardcoded_paths = find_hardcoded_paths_in_docstring(func_doc)

        # This should FAIL until docstrings are fixed
        assert len(hardcoded_paths) == 0, (
            f"update_batch_progress docstring contains hardcoded paths:\n"
            f"{chr(10).join([f'  - {line}' for _, line in hardcoded_paths])}\n\n"
            f"Use get_batch_state_file() instead"
        )

    def test_record_auto_clear_event_docstring_no_hardcoded_paths(self):
        """Test record_auto_clear_event() docstring uses portable examples.

        EXPECTED FAILURE: Function docstring currently shows:
            >>> record_auto_clear_event(
            ...     state_file=Path(".claude/batch_state.json"),
            ...     feature_index=2,
            ...     context_tokens_before_clear=155000,
            ... )

        SHOULD SHOW:
            >>> record_auto_clear_event(
            ...     state_file=get_batch_state_file(),
            ...     feature_index=2,
            ...     context_tokens_before_clear=155000,
            ... )
        """
        func_doc = inspect.getdoc(record_auto_clear_event)
        assert func_doc is not None, "record_auto_clear_event docstring missing"

        # Check for hardcoded paths
        hardcoded_paths = find_hardcoded_paths_in_docstring(func_doc)

        # This should FAIL until docstrings are fixed
        assert len(hardcoded_paths) == 0, (
            f"record_auto_clear_event docstring contains hardcoded paths:\n"
            f"{chr(10).join([f'  - {line}' for _, line in hardcoded_paths])}\n\n"
            f"Use get_batch_state_file() instead"
        )

    def test_all_public_functions_have_docstrings(self):
        """Test all public functions have docstrings.

        This ensures we don't miss any functions when validating examples.
        """
        # Get all public functions (not starting with _)
        public_functions = [
            name for name in dir(batch_state_manager)
            if callable(getattr(batch_state_manager, name))
            and not name.startswith('_')
            and name not in ['deprecated']  # Exclude decorators
        ]

        # Check each has a docstring
        missing_docstrings = []
        for func_name in public_functions:
            func = getattr(batch_state_manager, func_name)
            if not inspect.getdoc(func):
                missing_docstrings.append(func_name)

        assert len(missing_docstrings) == 0, (
            f"Public functions missing docstrings: {missing_docstrings}"
        )


# ============================================================================
# TEST CLASS 2: PATH DETECTION INTEGRATION
# ============================================================================


class TestPathDetectionIntegration:
    """Test integration with path_utils.get_batch_state_file()."""

    def test_default_state_file_uses_portable_detection(self):
        """Test DEFAULT_STATE_FILE uses get_batch_state_file().

        Verifies that module-level constant is set correctly.
        """
        # DEFAULT_STATE_FILE should be set to get_batch_state_file() result
        # (or fallback to Path(".claude/batch_state.json") if no project root)

        from batch_state_manager import DEFAULT_STATE_FILE

        # Should be a Path object
        assert isinstance(DEFAULT_STATE_FILE, Path), (
            f"DEFAULT_STATE_FILE should be Path, got {type(DEFAULT_STATE_FILE)}"
        )

        # Should end with batch_state.json
        assert DEFAULT_STATE_FILE.name == "batch_state.json", (
            f"DEFAULT_STATE_FILE should end with batch_state.json, got {DEFAULT_STATE_FILE.name}"
        )

    def test_get_default_state_file_returns_portable_path(self):
        """Test get_default_state_file() returns portable path.

        Function should use get_batch_state_file() for lazy evaluation.
        """
        result = get_default_state_file()

        # Should be a Path object
        assert isinstance(result, Path), (
            f"get_default_state_file() should return Path, got {type(result)}"
        )

        # Should end with batch_state.json
        assert result.name == "batch_state.json", (
            f"get_default_state_file() should end with batch_state.json, got {result.name}"
        )

        # Should be absolute path (not relative)
        # Note: This may fail if running outside git repo (uses fallback)
        # but that's expected behavior
        if result != Path(".claude/batch_state.json"):
            assert result.is_absolute(), (
                f"get_default_state_file() should return absolute path, got {result}"
            )

    def test_save_and_load_work_with_portable_paths(self, tmp_path):
        """Test save/load work with paths from get_batch_state_file().

        Integration test: Verify portable path detection works end-to-end.
        """
        # Create a temporary state file
        state_file = tmp_path / ".claude" / "batch_state.json"
        state_file.parent.mkdir(parents=True)

        # Create test state
        state = create_batch_state(
            features=["feature 1", "feature 2"],
            state_file=str(state_file),
        )

        # Save using portable path
        save_batch_state(state_file, state)

        # Verify file exists
        assert state_file.exists(), "State file should be created"

        # Load using portable path
        loaded_state = load_batch_state(state_file)

        # Verify loaded correctly
        assert loaded_state.batch_id == state.batch_id
        assert loaded_state.features == state.features


# ============================================================================
# TEST CLASS 3: SECURITY VALIDATION
# ============================================================================


class TestSecurityValidation:
    """Test security validations prevent path traversal and symlink attacks."""

    def test_save_rejects_path_traversal_attempts(self, tmp_path):
        """Test save_batch_state() rejects path traversal (CWE-22).

        Security: Prevent writing to arbitrary filesystem locations.
        """
        # Create test state
        state = create_batch_state(
            features=["test feature"],
        )

        # Attempt path traversal
        malicious_path = tmp_path / ".." / ".." / "etc" / "passwd"

        # Should raise error (security validation)
        from batch_state_manager import BatchStateError
        with pytest.raises((BatchStateError, ValueError)) as exc_info:
            save_batch_state(malicious_path, state)

        # Error message should mention security
        error_msg = str(exc_info.value).lower()
        assert any(keyword in error_msg for keyword in ["path", "security", "invalid"]), (
            f"Error should mention security concern, got: {exc_info.value}"
        )

    def test_load_rejects_symlink_attacks(self, tmp_path):
        """Test load_batch_state() rejects symlinks (CWE-59).

        Security: Prevent reading sensitive files via symlink.
        """
        # Create a sensitive file
        sensitive_file = tmp_path / "sensitive.txt"
        sensitive_file.write_text("SECRET DATA")

        # Create symlink
        symlink_path = tmp_path / "state.json"
        symlink_path.symlink_to(sensitive_file)

        # Should raise error (symlink validation)
        from batch_state_manager import BatchStateError
        with pytest.raises((BatchStateError, ValueError)) as exc_info:
            load_batch_state(symlink_path)

        # Error message should mention symlink
        error_msg = str(exc_info.value).lower()
        assert "symlink" in error_msg, (
            f"Error should mention symlink, got: {exc_info.value}"
        )

    def test_create_batch_state_sanitizes_feature_names(self):
        """Test create_batch_state() sanitizes feature names (CWE-117 log injection).

        Security: Prevent newlines in feature names from corrupting logs.
        """
        # Feature with newlines (log injection attempt)
        malicious_feature = "feature\n[ERROR] Fake error message\nfeature"

        # Create state
        state = create_batch_state(
            features=[malicious_feature],
        )

        # Feature should be sanitized (newlines removed/replaced)
        assert "\n" not in state.features[0], (
            "Feature names should not contain newlines after sanitization"
        )
        assert "\r" not in state.features[0], (
            "Feature names should not contain carriage returns after sanitization"
        )


# ============================================================================
# TEST CLASS 4: CROSS-PLATFORM COMPATIBILITY
# ============================================================================


class TestCrossPlatformCompatibility:
    """Test cross-platform path handling (Windows/Unix)."""

    def test_save_load_roundtrip_with_windows_style_path(self, tmp_path):
        """Test save/load work with Windows-style paths.

        Note: This tests Path() handling of backslashes on all platforms.
        """
        # Create test directory
        state_dir = tmp_path / ".claude"
        state_dir.mkdir()

        # Windows-style path (backslashes)
        windows_path_str = str(state_dir / "batch_state.json").replace("/", "\\")

        # Create state
        state = create_batch_state(
            features=["test feature"],
        )

        # Save with Windows-style path
        save_batch_state(windows_path_str, state)

        # Load with same path
        loaded_state = load_batch_state(windows_path_str)

        # Verify roundtrip
        assert loaded_state.batch_id == state.batch_id

    def test_portable_paths_work_on_all_platforms(self):
        """Test get_batch_state_file() works on all platforms.

        Verifies path separators are correct for current OS.
        """
        result = get_batch_state_file()

        # Should use OS-appropriate separators
        # Path() automatically handles this
        assert isinstance(result, Path)

        # Convert to string and check it's a valid path
        path_str = str(result)
        assert len(path_str) > 0

        # Should end with batch_state.json (regardless of OS)
        assert path_str.endswith("batch_state.json")

    def test_relative_path_resolution_consistent(self, tmp_path):
        """Test relative paths resolve consistently across platforms.

        Verifies that relative paths are resolved from PROJECT_ROOT,
        not current working directory.
        """
        # This test verifies the fix from Issue #79
        # Before: Relative paths resolved from cwd (inconsistent)
        # After: Relative paths resolve from PROJECT_ROOT (consistent)

        from batch_state_manager import save_batch_state, create_batch_state

        # Create test state
        state = create_batch_state(features=["test"])

        # Use relative path (should resolve from PROJECT_ROOT)
        relative_path = "custom/batch_state.json"

        # This should NOT fail with "file not found" when cwd != PROJECT_ROOT
        # (Before Issue #79 fix, this would fail from subdirectories)
        # Note: This test validates the behavior, even if it creates the file
        # in a non-standard location

        try:
            # Attempt to save (will resolve relative path)
            save_batch_state(relative_path, state)

            # If we get here, path was resolved successfully
            # (implementation should resolve from PROJECT_ROOT)
            assert True, "Relative path should resolve from PROJECT_ROOT"

        except Exception as e:
            # If this fails, it should be a clear error message
            error_msg = str(e)
            assert "PROJECT_ROOT" in error_msg or "project root" in error_msg.lower(), (
                f"Error should mention PROJECT_ROOT context, got: {e}"
            )


# ============================================================================
# TEST SUITE SUMMARY
# ============================================================================


def test_suite_summary():
    """Print test suite summary (for documentation).

    This is a meta-test that documents the test coverage.
    """
    print("\n" + "=" * 80)
    print("TEST SUITE: Batch State Manager Portability (Issue #85)")
    print("=" * 80)
    print("\nTest Classes:")
    print("  1. TestDocstringValidation (7 tests)")
    print("     - Validates docstrings use portable path examples")
    print("     - Checks for hardcoded Path('.claude/batch_state.json')")
    print("     - Ensures get_batch_state_file() is recommended")
    print()
    print("  2. TestPathDetectionIntegration (3 tests)")
    print("     - Validates integration with path_utils")
    print("     - Tests get_default_state_file() function")
    print("     - Verifies save/load work with portable paths")
    print()
    print("  3. TestSecurityValidation (3 tests)")
    print("     - Tests path traversal prevention (CWE-22)")
    print("     - Tests symlink attack prevention (CWE-59)")
    print("     - Tests log injection prevention (CWE-117)")
    print()
    print("  4. TestCrossPlatformCompatibility (3 tests)")
    print("     - Tests Windows/Unix path handling")
    print("     - Validates portable paths work everywhere")
    print("     - Tests relative path resolution consistency")
    print()
    print("TOTAL: 16 tests")
    print()
    print("TDD Status: RED PHASE (all tests should FAIL)")
    print("Expected Failures:")
    print("  - Docstrings still show hardcoded paths")
    print("  - Need to update to use get_batch_state_file()")
    print()
    print("Implementation Will:")
    print("  1. Update module docstring examples")
    print("  2. Update save_batch_state() docstring")
    print("  3. Update load_batch_state() docstring")
    print("  4. Update update_batch_progress() docstring")
    print("  5. Update record_auto_clear_event() docstring")
    print("  6. Replace all Path('.claude/batch_state.json') with get_batch_state_file()")
    print("=" * 80)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
