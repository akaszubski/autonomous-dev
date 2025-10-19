"""Unit tests for auto_generate_tests.py hook"""

import sys
from pathlib import Path

import pytest

# Add hooks directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

from auto_generate_tests import (
    detect_new_feature,
    get_test_file_path,
    tests_already_exist,
    create_test_generation_prompt,
)


class TestDetectNewFeature:
    """Test new feature detection logic."""

    def test_detects_implement_keyword(self):
        """Test detection of 'implement' keyword."""
        assert detect_new_feature("implement user authentication") is True

    def test_detects_add_feature_keyword(self):
        """Test detection of 'add feature' keyword."""
        assert detect_new_feature("add feature for payment processing") is True

    def test_detects_create_new_keyword(self):
        """Test detection of 'create new' keyword."""
        assert detect_new_feature("create new API endpoint") is True

    def test_detects_new_function_keyword(self):
        """Test detection of 'new function' keyword."""
        assert detect_new_feature("new function to calculate totals") is True

    def test_skips_refactor_keyword(self):
        """Test that refactor requests are skipped."""
        assert detect_new_feature("refactor the authentication module") is False

    def test_skips_rename_keyword(self):
        """Test that rename requests are skipped."""
        assert detect_new_feature("rename function to calculateTotal") is False

    def test_skips_format_keyword(self):
        """Test that format requests are skipped."""
        assert detect_new_feature("format the code with black") is False

    def test_skips_typo_keyword(self):
        """Test that typo fixes are skipped."""
        assert detect_new_feature("fix typo in comment") is False

    def test_skips_docstring_update(self):
        """Test that docstring updates are skipped."""
        assert detect_new_feature("update docstring for clarity") is False

    def test_case_insensitive_detection(self):
        """Test that detection is case insensitive."""
        assert detect_new_feature("IMPLEMENT new feature") is True
        assert detect_new_feature("REFACTOR existing code") is False


class TestGetTestFilePath:
    """Test test file path generation."""

    def test_generates_test_file_path(self, tmp_path):
        """Test generation of test file path."""
        source_file = Path("src/[project_name]/authentication.py")

        test_path = get_test_file_path(source_file)

        assert test_path is not None
        assert test_path.name == "test_authentication.py"
        assert "unit" in str(test_path)

    def test_skips_init_files(self):
        """Test that __init__.py files are skipped."""
        source_file = Path("src/__init__.py")

        test_path = get_test_file_path(source_file)

        assert test_path is None

    def test_uses_module_name(self):
        """Test that module name is used for test file."""
        source_file = Path("src/user_manager.py")

        test_path = get_test_file_path(source_file)

        assert "test_user_manager.py" in str(test_path)


class TestTestsAlreadyExist:
    """Test checking for existing tests."""

    def test_returns_true_when_tests_exist(self, tmp_path):
        """Test returns True when test file exists."""
        test_file = tmp_path / "test_module.py"
        test_file.touch()

        assert tests_already_exist(test_file) is True

    def test_returns_false_when_tests_missing(self, tmp_path):
        """Test returns False when test file doesn't exist."""
        test_file = tmp_path / "test_nonexistent.py"

        assert tests_already_exist(test_file) is False

    def test_handles_none_path(self):
        """Test handling of None path (e.g., from __init__.py)."""
        # tests_already_exist returns result of test_file.exists()
        # When test_file is None, it returns False (falsy)
        result = tests_already_exist(None)
        assert result is False or result is None


class TestCreateTestGenerationPrompt:
    """Test test generation prompt creation."""

    def test_includes_feature_description(self):
        """Test that prompt includes feature description."""
        source_file = Path("src/module.py")
        user_prompt = "implement user login with JWT tokens"

        prompt = create_test_generation_prompt(source_file, user_prompt)

        assert "implement user login with JWT tokens" in prompt

    def test_includes_file_paths(self):
        """Test that prompt includes source and test file paths."""
        source_file = Path("src/authentication.py")
        user_prompt = "add feature"

        prompt = create_test_generation_prompt(source_file, user_prompt)

        assert "authentication" in prompt
        assert "test_authentication" in prompt

    def test_includes_pytest_instructions(self):
        """Test that prompt includes pytest testing instructions."""
        source_file = Path("src/module.py")
        user_prompt = "implement feature"

        prompt = create_test_generation_prompt(source_file, user_prompt)

        assert "pytest" in prompt
        assert "test-master" in prompt
        assert "TDD" in prompt
        assert "FAIL" in prompt

    def test_mentions_test_types(self):
        """Test that prompt mentions different test types."""
        source_file = Path("src/module.py")
        user_prompt = "implement feature"

        prompt = create_test_generation_prompt(source_file, user_prompt)

        assert "Happy path" in prompt or "happy" in prompt.lower()
        assert "Edge case" in prompt or "edge" in prompt.lower()
        assert "Error handling" in prompt or "error" in prompt.lower()
