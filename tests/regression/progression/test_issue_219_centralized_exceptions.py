#!/usr/bin/env python3
"""
Regression Tests for Issue #219: Centralize GitHub API exceptions into exceptions.py

TDD RED PHASE: These tests will FAIL initially (no centralized exceptions.py).
After implementation, tests should PASS.

Goal: Verify that GitHub API exceptions are centralized in a single exceptions.py
module to eliminate duplication and provide consistent exception hierarchy.

High Priority Exceptions (Scope for Issue #219):
- AutonomousDevError (base exception for entire plugin)
- APIError (category for all API-related errors)
- GitHubAPIError (GitHub-specific API errors)
- IssueNotFoundError (specific GitHub issue error)
- IssueAlreadyClosedError (specific GitHub issue error)

Test Categories:
1. Exception Hierarchy Tests (5 tests) - Verify inheritance chain
2. Exception Instantiation Tests (5 tests) - Verify creation and message handling
3. Exception Catching Tests (4 tests) - Verify polymorphic catching
4. Import Consolidation Tests (4 tests) - Verify single source of truth
5. Duplicate Removal Tests (3 tests) - Verify duplicates removed from modules
6. Documentation Tests (2 tests) - Verify CHANGELOG and docstrings

Total: 23 comprehensive tests

Created: 2026-01-09
Issue: #219 (Centralize GitHub API exceptions into exceptions.py)
Agent: test-master
"""

import sys
from pathlib import Path
from typing import Type

import pytest

# Add lib to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
LIB_PATH = PROJECT_ROOT / "plugins/autonomous-dev/lib"
sys.path.insert(0, str(LIB_PATH))


# ============================================================================
# Test Category 1: Exception Hierarchy Tests (5 tests)
# ============================================================================


def test_autonomous_dev_error_inherits_from_exception():
    """Verify AutonomousDevError is base exception that inherits from Exception.

    TDD: This test will PASS after exceptions.py is created.
    AutonomousDevError should be the root exception for all plugin errors.
    """
    # Import from centralized exceptions module
    from exceptions import AutonomousDevError  # type: ignore[import-not-found]

    # Verify inheritance
    assert issubclass(AutonomousDevError, Exception), \
        "AutonomousDevError should inherit from Exception"

    # Verify it's not the same as Exception (custom class)
    assert AutonomousDevError is not Exception, \
        "AutonomousDevError should be a custom exception class"


def test_api_error_inherits_from_autonomous_dev_error():
    """Verify APIError inherits from AutonomousDevError.

    TDD: This test will PASS after exceptions.py is created.
    APIError should be category exception for all API-related errors.
    """
    # Import from centralized exceptions module
    from exceptions import APIError, AutonomousDevError  # type: ignore[import-not-found]

    # Verify inheritance chain
    assert issubclass(APIError, AutonomousDevError), \
        "APIError should inherit from AutonomousDevError"
    assert issubclass(APIError, Exception), \
        "APIError should transitively inherit from Exception"


def test_github_api_error_inherits_from_api_error():
    """Verify GitHubAPIError inherits from APIError.

    TDD: This test will PASS after exceptions.py is created.
    GitHubAPIError should be GitHub-specific API exception.
    """
    # Import from centralized exceptions module
    from exceptions import APIError, AutonomousDevError, GitHubAPIError  # type: ignore[import-not-found]

    # Verify inheritance chain
    assert issubclass(GitHubAPIError, APIError), \
        "GitHubAPIError should inherit from APIError"
    assert issubclass(GitHubAPIError, AutonomousDevError), \
        "GitHubAPIError should transitively inherit from AutonomousDevError"
    assert issubclass(GitHubAPIError, Exception), \
        "GitHubAPIError should transitively inherit from Exception"


def test_issue_not_found_error_inherits_from_github_api_error():
    """Verify IssueNotFoundError inherits from GitHubAPIError.

    TDD: This test will PASS after exceptions.py is created.
    IssueNotFoundError should be specific GitHub issue exception.
    """
    # Import from centralized exceptions module
    from exceptions import (  # type: ignore[import-not-found]
        APIError,
        AutonomousDevError,
        GitHubAPIError,
        IssueNotFoundError,
    )

    # Verify inheritance chain
    assert issubclass(IssueNotFoundError, GitHubAPIError), \
        "IssueNotFoundError should inherit from GitHubAPIError"
    assert issubclass(IssueNotFoundError, APIError), \
        "IssueNotFoundError should transitively inherit from APIError"
    assert issubclass(IssueNotFoundError, AutonomousDevError), \
        "IssueNotFoundError should transitively inherit from AutonomousDevError"
    assert issubclass(IssueNotFoundError, Exception), \
        "IssueNotFoundError should transitively inherit from Exception"


def test_issue_already_closed_error_inherits_from_github_api_error():
    """Verify IssueAlreadyClosedError inherits from GitHubAPIError.

    TDD: This test will PASS after exceptions.py is created.
    IssueAlreadyClosedError should be specific GitHub issue exception.
    """
    # Import from centralized exceptions module
    from exceptions import (  # type: ignore[import-not-found]
        APIError,
        AutonomousDevError,
        GitHubAPIError,
        IssueAlreadyClosedError,
    )

    # Verify inheritance chain
    assert issubclass(IssueAlreadyClosedError, GitHubAPIError), \
        "IssueAlreadyClosedError should inherit from GitHubAPIError"
    assert issubclass(IssueAlreadyClosedError, APIError), \
        "IssueAlreadyClosedError should transitively inherit from APIError"
    assert issubclass(IssueAlreadyClosedError, AutonomousDevError), \
        "IssueAlreadyClosedError should transitively inherit from AutonomousDevError"
    assert issubclass(IssueAlreadyClosedError, Exception), \
        "IssueAlreadyClosedError should transitively inherit from Exception"


# ============================================================================
# Test Category 2: Exception Instantiation Tests (5 tests)
# ============================================================================


def test_autonomous_dev_error_instantiation():
    """Verify AutonomousDevError can be instantiated with message.

    TDD: This test will PASS after exceptions.py is created.
    """
    from exceptions import AutonomousDevError  # type: ignore[import-not-found]

    # Create exception with message
    error = AutonomousDevError("Test error message")

    # Verify message is preserved
    assert str(error) == "Test error message", \
        "Exception message should be preserved in str()"
    assert error.args == ("Test error message",), \
        "Exception args should contain message"


def test_api_error_instantiation():
    """Verify APIError can be instantiated with message.

    TDD: This test will PASS after exceptions.py is created.
    """
    from exceptions import APIError  # type: ignore[import-not-found]

    # Create exception with message
    error = APIError("API request failed")

    # Verify message is preserved
    assert str(error) == "API request failed", \
        "Exception message should be preserved in str()"
    assert error.args == ("API request failed",), \
        "Exception args should contain message"


def test_github_api_error_instantiation():
    """Verify GitHubAPIError can be instantiated with message.

    TDD: This test will PASS after exceptions.py is created.
    """
    from exceptions import GitHubAPIError  # type: ignore[import-not-found]

    # Create exception with message
    error = GitHubAPIError("GitHub API rate limit exceeded")

    # Verify message is preserved
    assert str(error) == "GitHub API rate limit exceeded", \
        "Exception message should be preserved in str()"
    assert error.args == ("GitHub API rate limit exceeded",), \
        "Exception args should contain message"


def test_issue_not_found_error_instantiation():
    """Verify IssueNotFoundError can be instantiated with message.

    TDD: This test will PASS after exceptions.py is created.
    """
    from exceptions import IssueNotFoundError  # type: ignore[import-not-found]

    # Create exception with message
    error = IssueNotFoundError("Issue #42 not found")

    # Verify message is preserved
    assert str(error) == "Issue #42 not found", \
        "Exception message should be preserved in str()"
    assert error.args == ("Issue #42 not found",), \
        "Exception args should contain message"


def test_issue_already_closed_error_instantiation():
    """Verify IssueAlreadyClosedError can be instantiated with message.

    TDD: This test will PASS after exceptions.py is created.
    """
    from exceptions import IssueAlreadyClosedError  # type: ignore[import-not-found]

    # Create exception with message
    error = IssueAlreadyClosedError("Issue #42 is already closed")

    # Verify message is preserved
    assert str(error) == "Issue #42 is already closed", \
        "Exception message should be preserved in str()"
    assert error.args == ("Issue #42 is already closed",), \
        "Exception args should contain message"


# ============================================================================
# Test Category 3: Exception Catching Tests (4 tests)
# ============================================================================


def test_github_api_error_catches_issue_not_found_error():
    """Verify GitHubAPIError catches IssueNotFoundError polymorphically.

    TDD: This test will PASS after exceptions.py is created.
    Demonstrates polymorphic exception handling via inheritance.
    """
    from exceptions import GitHubAPIError, IssueNotFoundError  # type: ignore[import-not-found]

    # Raise IssueNotFoundError, catch as GitHubAPIError
    try:
        raise IssueNotFoundError("Issue #999 not found")
    except GitHubAPIError as e:
        # Should catch IssueNotFoundError as GitHubAPIError
        assert isinstance(e, IssueNotFoundError), \
            "Should catch IssueNotFoundError as GitHubAPIError"
        assert str(e) == "Issue #999 not found", \
            "Exception message should be preserved"
    except Exception:
        pytest.fail("Should catch IssueNotFoundError as GitHubAPIError")


def test_github_api_error_catches_issue_already_closed_error():
    """Verify GitHubAPIError catches IssueAlreadyClosedError polymorphically.

    TDD: This test will PASS after exceptions.py is created.
    Demonstrates polymorphic exception handling via inheritance.
    """
    from exceptions import GitHubAPIError, IssueAlreadyClosedError  # type: ignore[import-not-found]

    # Raise IssueAlreadyClosedError, catch as GitHubAPIError
    try:
        raise IssueAlreadyClosedError("Issue #42 is already closed")
    except GitHubAPIError as e:
        # Should catch IssueAlreadyClosedError as GitHubAPIError
        assert isinstance(e, IssueAlreadyClosedError), \
            "Should catch IssueAlreadyClosedError as GitHubAPIError"
        assert str(e) == "Issue #42 is already closed", \
            "Exception message should be preserved"
    except Exception:
        pytest.fail("Should catch IssueAlreadyClosedError as GitHubAPIError")


def test_api_error_catches_github_api_error():
    """Verify APIError catches GitHubAPIError polymorphically.

    TDD: This test will PASS after exceptions.py is created.
    Demonstrates category exception catching specific exceptions.
    """
    from exceptions import APIError, GitHubAPIError  # type: ignore[import-not-found]

    # Raise GitHubAPIError, catch as APIError
    try:
        raise GitHubAPIError("GitHub API timeout")
    except APIError as e:
        # Should catch GitHubAPIError as APIError
        assert isinstance(e, GitHubAPIError), \
            "Should catch GitHubAPIError as APIError"
        assert str(e) == "GitHub API timeout", \
            "Exception message should be preserved"
    except Exception:
        pytest.fail("Should catch GitHubAPIError as APIError")


def test_autonomous_dev_error_catches_api_error():
    """Verify AutonomousDevError catches APIError polymorphically.

    TDD: This test will PASS after exceptions.py is created.
    Demonstrates base exception catching category exceptions.
    """
    from exceptions import APIError, AutonomousDevError  # type: ignore[import-not-found]

    # Raise APIError, catch as AutonomousDevError
    try:
        raise APIError("API request failed")
    except AutonomousDevError as e:
        # Should catch APIError as AutonomousDevError
        assert isinstance(e, APIError), \
            "Should catch APIError as AutonomousDevError"
        assert str(e) == "API request failed", \
            "Exception message should be preserved"
    except Exception:
        pytest.fail("Should catch APIError as AutonomousDevError")


# ============================================================================
# Test Category 4: Import Consolidation Tests (4 tests)
# ============================================================================


def test_exceptions_module_exists():
    """Verify exceptions.py module exists in lib directory.

    TDD: This test will PASS after exceptions.py is created.
    """
    exceptions_file = LIB_PATH / "exceptions.py"

    assert exceptions_file.exists(), \
        f"exceptions.py should exist at {exceptions_file}"
    assert exceptions_file.is_file(), \
        f"exceptions.py should be a file at {exceptions_file}"


def test_all_exceptions_importable_from_exceptions():
    """Verify all 5 high-priority exceptions are importable from exceptions module.

    TDD: This test will PASS after exceptions.py is created.
    """
    # Import all exceptions from centralized module
    from exceptions import (  # type: ignore[import-not-found]
        APIError,
        AutonomousDevError,
        GitHubAPIError,
        IssueAlreadyClosedError,
        IssueNotFoundError,
    )

    # Verify all exceptions are importable (test passes if no ImportError)
    assert AutonomousDevError is not None
    assert APIError is not None
    assert GitHubAPIError is not None
    assert IssueNotFoundError is not None
    assert IssueAlreadyClosedError is not None


def test_github_issue_closer_imports_from_exceptions():
    """Verify github_issue_closer.py imports exceptions from centralized module.

    TDD: This test will PASS after github_issue_closer.py is updated.
    Should NOT define exceptions locally, should import from exceptions.py.
    """
    github_issue_closer_file = LIB_PATH / "github_issue_closer.py"
    source_code = github_issue_closer_file.read_text()

    # Should import from exceptions module
    assert "from exceptions import" in source_code, \
        "github_issue_closer.py should import from exceptions module"

    # Should NOT define GitHubAPIError locally (duplicate)
    lines = source_code.split("\n")
    local_definitions = [
        line for line in lines
        if "class GitHubAPIError" in line
        and not line.strip().startswith("#")
    ]

    assert len(local_definitions) == 0, \
        "github_issue_closer.py should NOT define GitHubAPIError locally (use centralized exceptions.py)"


def test_github_issue_fetcher_imports_from_exceptions():
    """Verify github_issue_fetcher.py imports exceptions from centralized module.

    TDD: This test will PASS after github_issue_fetcher.py is updated.
    Should NOT define exceptions locally, should import from exceptions.py.
    """
    github_issue_fetcher_file = LIB_PATH / "github_issue_fetcher.py"
    source_code = github_issue_fetcher_file.read_text()

    # Should import from exceptions module
    assert "from exceptions import" in source_code, \
        "github_issue_fetcher.py should import from exceptions module"

    # Should NOT define GitHubAPIError locally (duplicate)
    lines = source_code.split("\n")
    local_definitions = [
        line for line in lines
        if "class GitHubAPIError" in line
        and not line.strip().startswith("#")
    ]

    assert len(local_definitions) == 0, \
        "github_issue_fetcher.py should NOT define GitHubAPIError locally (use centralized exceptions.py)"


# ============================================================================
# Test Category 5: Duplicate Removal Tests (3 tests)
# ============================================================================


def test_no_duplicate_github_api_error_in_github_issue_closer():
    """Verify GitHubAPIError is not duplicated in github_issue_closer.py.

    TDD: This test will PASS after duplicates are removed.
    """
    github_issue_closer_file = LIB_PATH / "github_issue_closer.py"
    source_code = github_issue_closer_file.read_text()

    # Count class definitions (should be 0 after consolidation)
    lines = source_code.split("\n")
    github_api_error_definitions = [
        line for line in lines
        if line.strip().startswith("class GitHubAPIError")
    ]

    assert len(github_api_error_definitions) == 0, \
        f"github_issue_closer.py should NOT define GitHubAPIError (found {len(github_api_error_definitions)} definitions)"


def test_no_duplicate_github_api_error_in_github_issue_fetcher():
    """Verify GitHubAPIError is not duplicated in github_issue_fetcher.py.

    TDD: This test will PASS after duplicates are removed.
    """
    github_issue_fetcher_file = LIB_PATH / "github_issue_fetcher.py"
    source_code = github_issue_fetcher_file.read_text()

    # Count class definitions (should be 0 after consolidation)
    lines = source_code.split("\n")
    github_api_error_definitions = [
        line for line in lines
        if line.strip().startswith("class GitHubAPIError")
    ]

    assert len(github_api_error_definitions) == 0, \
        f"github_issue_fetcher.py should NOT define GitHubAPIError (found {len(github_api_error_definitions)} definitions)"


def test_no_duplicate_issue_not_found_error():
    """Verify IssueNotFoundError is not duplicated across modules.

    TDD: This test will PASS after duplicates are removed.
    Should only exist in exceptions.py.
    """
    github_issue_closer_file = LIB_PATH / "github_issue_closer.py"
    github_issue_fetcher_file = LIB_PATH / "github_issue_fetcher.py"

    # Count definitions in github_issue_closer.py
    closer_source = github_issue_closer_file.read_text()
    closer_definitions = [
        line for line in closer_source.split("\n")
        if line.strip().startswith("class IssueNotFoundError")
    ]

    # Count definitions in github_issue_fetcher.py
    fetcher_source = github_issue_fetcher_file.read_text()
    fetcher_definitions = [
        line for line in fetcher_source.split("\n")
        if line.strip().startswith("class IssueNotFoundError")
    ]

    # Total duplicates (should be 0)
    total_duplicates = len(closer_definitions) + len(fetcher_definitions)

    assert total_duplicates == 0, \
        f"IssueNotFoundError should only exist in exceptions.py (found {total_duplicates} duplicate definitions)"


# ============================================================================
# Test Category 6: Documentation Tests (2 tests)
# ============================================================================


def test_changelog_mentions_issue_219():
    """Verify CHANGELOG.md documents Issue #219 exception centralization.

    TDD: This test will PASS after CHANGELOG is updated.
    """
    changelog = PROJECT_ROOT / "CHANGELOG.md"
    changelog_text = changelog.read_text()

    # Should mention Issue #219
    assert "#219" in changelog_text, \
        "CHANGELOG should document Issue #219"

    # Should mention exception centralization keywords
    exception_keywords = [
        "exception",
        "centralize",
        "exceptions.py",
        "GitHubAPIError",
        "duplicate",
    ]

    found_keywords = [kw for kw in exception_keywords if kw in changelog_text]

    assert len(found_keywords) >= 3, \
        f"CHANGELOG should document exception centralization with relevant keywords (found: {found_keywords})"


def test_exceptions_module_has_docstrings():
    """Verify exceptions.py has comprehensive module and class docstrings.

    TDD: This test will PASS after exceptions.py is created with docstrings.
    """
    exceptions_file = LIB_PATH / "exceptions.py"
    source_code = exceptions_file.read_text()

    # Should have module docstring
    assert '"""' in source_code or "'''" in source_code, \
        "exceptions.py should have module docstring"

    # Should have docstrings for each exception class
    exception_classes = [
        "AutonomousDevError",
        "APIError",
        "GitHubAPIError",
        "IssueNotFoundError",
        "IssueAlreadyClosedError",
    ]

    for exception_class in exception_classes:
        # Find class definition
        lines = source_code.split("\n")
        class_line_index = None

        for i, line in enumerate(lines):
            if f"class {exception_class}" in line:
                class_line_index = i
                break

        assert class_line_index is not None, \
            f"{exception_class} should be defined in exceptions.py"

        # Check for docstring within next 5 lines
        docstring_found = False
        for i in range(class_line_index + 1, min(class_line_index + 6, len(lines))):
            if '"""' in lines[i] or "'''" in lines[i]:
                docstring_found = True
                break

        assert docstring_found, \
            f"{exception_class} should have a docstring"


# ============================================================================
# Test Summary
# ============================================================================


def test_centralization_completeness():
    """Meta-test: Verify test coverage is comprehensive for Issue #219.

    This test validates that we're testing all requirements from Issue #219.
    """
    import inspect

    # Count test functions
    current_module = sys.modules[__name__]
    test_functions = [
        name for name, obj in inspect.getmembers(current_module)
        if inspect.isfunction(obj) and name.startswith("test_")
    ]

    # Should have tests for all categories
    categories = {
        "exception_hierarchy": [
            "test_autonomous_dev_error_inherits_from_exception",
            "test_api_error_inherits_from_autonomous_dev_error",
            "test_github_api_error_inherits_from_api_error",
            "test_issue_not_found_error_inherits_from_github_api_error",
            "test_issue_already_closed_error_inherits_from_github_api_error",
        ],
        "exception_instantiation": [
            "test_autonomous_dev_error_instantiation",
            "test_api_error_instantiation",
            "test_github_api_error_instantiation",
            "test_issue_not_found_error_instantiation",
            "test_issue_already_closed_error_instantiation",
        ],
        "exception_catching": [
            "test_github_api_error_catches_issue_not_found_error",
            "test_github_api_error_catches_issue_already_closed_error",
            "test_api_error_catches_github_api_error",
            "test_autonomous_dev_error_catches_api_error",
        ],
        "import_consolidation": [
            "test_exceptions_module_exists",
            "test_all_exceptions_importable_from_exceptions",
            "test_github_issue_closer_imports_from_exceptions",
            "test_github_issue_fetcher_imports_from_exceptions",
        ],
        "duplicate_removal": [
            "test_no_duplicate_github_api_error_in_github_issue_closer",
            "test_no_duplicate_github_api_error_in_github_issue_fetcher",
            "test_no_duplicate_issue_not_found_error",
        ],
        "documentation": [
            "test_changelog_mentions_issue_219",
            "test_exceptions_module_has_docstrings",
        ],
    }

    # Verify all category tests exist
    for category, expected_tests in categories.items():
        for test_name in expected_tests:
            assert test_name in test_functions, \
                f"Missing test: {test_name} (category: {category})"

    # Should have at least 23 tests (comprehensive coverage)
    assert len(test_functions) >= 23, \
        f"Insufficient test coverage: {len(test_functions)} tests (expected 23+)"


# ============================================================================
# Bonus Test: Exception Hierarchy Visualization
# ============================================================================


def test_exception_hierarchy_visualization():
    """Visualize complete exception hierarchy for documentation.

    TDD: This test will PASS after exceptions.py is created.
    Useful for validating the exception tree structure.
    """
    from exceptions import (  # type: ignore[import-not-found]
        APIError,
        AutonomousDevError,
        GitHubAPIError,
        IssueAlreadyClosedError,
        IssueNotFoundError,
    )

    # Build hierarchy map
    hierarchy = {
        Exception: {
            AutonomousDevError: {
                APIError: {
                    GitHubAPIError: {
                        IssueNotFoundError: {},
                        IssueAlreadyClosedError: {},
                    }
                }
            }
        }
    }

    # Verify hierarchy structure
    def verify_hierarchy(parent: Type[Exception], children: dict) -> None:
        """Recursively verify exception inheritance hierarchy."""
        for child, grandchildren in children.items():
            assert issubclass(child, parent), \
                f"{child.__name__} should inherit from {parent.__name__}"
            if grandchildren:
                verify_hierarchy(child, grandchildren)

    verify_hierarchy(Exception, hierarchy[Exception])
