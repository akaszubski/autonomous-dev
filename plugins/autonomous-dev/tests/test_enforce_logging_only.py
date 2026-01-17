#!/usr/bin/env python3
"""
Tests for enforce_logging_only hook.

Tests the pre-commit hook that blocks print statements in production code.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Add hooks to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from enforce_logging_only import (
    _is_enabled,
    _allow_print_in_cli,
    _allow_print_in_tests,
    _is_excluded_path,
    _is_test_file,
    _is_cli_file,
    _is_allowed_print,
    check_file,
    scan_directory,
    main,
)


class TestIsEnabled:
    """Tests for _is_enabled function."""

    def test_disabled_by_default(self):
        """Environment variable not set should return False."""
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ENFORCE_LOGGING_ONLY", None)
            assert _is_enabled() is False

    def test_enabled_with_true(self):
        """ENFORCE_LOGGING_ONLY=true should return True."""
        with mock.patch.dict(os.environ, {"ENFORCE_LOGGING_ONLY": "true"}):
            assert _is_enabled() is True

    def test_enabled_with_yes(self):
        """ENFORCE_LOGGING_ONLY=yes should return True."""
        with mock.patch.dict(os.environ, {"ENFORCE_LOGGING_ONLY": "yes"}):
            assert _is_enabled() is True

    def test_enabled_with_1(self):
        """ENFORCE_LOGGING_ONLY=1 should return True."""
        with mock.patch.dict(os.environ, {"ENFORCE_LOGGING_ONLY": "1"}):
            assert _is_enabled() is True

    def test_disabled_with_false(self):
        """ENFORCE_LOGGING_ONLY=false should return False."""
        with mock.patch.dict(os.environ, {"ENFORCE_LOGGING_ONLY": "false"}):
            assert _is_enabled() is False

    def test_case_insensitive(self):
        """Environment variable should be case-insensitive."""
        with mock.patch.dict(os.environ, {"ENFORCE_LOGGING_ONLY": "TRUE"}):
            assert _is_enabled() is True

        with mock.patch.dict(os.environ, {"ENFORCE_LOGGING_ONLY": "True"}):
            assert _is_enabled() is True


class TestAllowPrintInCli:
    """Tests for _allow_print_in_cli function."""

    def test_allowed_by_default(self):
        """Print in CLI should be allowed by default."""
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ALLOW_PRINT_IN_CLI", None)
            assert _allow_print_in_cli() is True

    def test_can_be_disabled(self):
        """ALLOW_PRINT_IN_CLI=false should disable."""
        with mock.patch.dict(os.environ, {"ALLOW_PRINT_IN_CLI": "false"}):
            assert _allow_print_in_cli() is False


class TestAllowPrintInTests:
    """Tests for _allow_print_in_tests function."""

    def test_allowed_by_default(self):
        """Print in tests should be allowed by default."""
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ALLOW_PRINT_IN_TESTS", None)
            assert _allow_print_in_tests() is True

    def test_can_be_disabled(self):
        """ALLOW_PRINT_IN_TESTS=false should disable."""
        with mock.patch.dict(os.environ, {"ALLOW_PRINT_IN_TESTS": "false"}):
            assert _allow_print_in_tests() is False


class TestIsExcludedPath:
    """Tests for _is_excluded_path function."""

    def test_venv_excluded(self):
        """Files in .venv should be excluded."""
        assert _is_excluded_path(Path(".venv/lib/site-packages/pkg.py")) is True

    def test_pycache_excluded(self):
        """Files in __pycache__ should be excluded."""
        assert _is_excluded_path(Path("lib/__pycache__/module.cpython-310.pyc")) is True

    def test_git_excluded(self):
        """Files in .git should be excluded."""
        assert _is_excluded_path(Path(".git/hooks/pre-commit")) is True

    def test_normal_path_not_excluded(self):
        """Normal paths should not be excluded."""
        assert _is_excluded_path(Path("lib/module.py")) is False
        assert _is_excluded_path(Path("plugins/autonomous-dev/lib/auto_install_deps.py")) is False


class TestIsTestFile:
    """Tests for _is_test_file function."""

    def test_file_in_tests_dir(self):
        """Files in tests/ directory should be test files."""
        assert _is_test_file(Path("tests/test_module.py")) is True
        assert _is_test_file(Path("plugins/autonomous-dev/tests/test_hook.py")) is True

    def test_test_prefixed_file(self):
        """Files named test_*.py should be test files."""
        assert _is_test_file(Path("test_something.py")) is True

    def test_non_test_file(self):
        """Non-test files should return False."""
        assert _is_test_file(Path("lib/module.py")) is False
        assert _is_test_file(Path("hooks/enforce_logging_only.py")) is False


class TestIsCliFile:
    """Tests for _is_cli_file function."""

    def test_argparse_cli(self):
        """Files using argparse are CLI tools."""
        content = """
import argparse
parser = argparse.ArgumentParser()
"""
        assert _is_cli_file(content) is True

    def test_click_cli(self):
        """Files using click are CLI tools."""
        content = """
import click

@click.command()
def main():
    pass
"""
        assert _is_cli_file(content) is True

    def test_typer_cli(self):
        """Files using typer are CLI tools."""
        content = """
import typer
app = typer.Typer()
"""
        assert _is_cli_file(content) is True

    def test_main_guard(self):
        """Files with if __name__ == '__main__' are CLI tools."""
        content = '''
def main():
    pass

if __name__ == "__main__":
    main()
'''
        assert _is_cli_file(content) is True

    def test_library_file(self):
        """Library files without CLI indicators are not CLI tools."""
        content = """
def helper():
    return 42
"""
        assert _is_cli_file(content) is False


class TestIsAllowedPrint:
    """Tests for _is_allowed_print function."""

    def test_commented_print_allowed(self):
        """Commented print statements should be allowed."""
        assert _is_allowed_print("    # print('debug')") is True

    def test_normal_print_not_allowed(self):
        """Normal print statements should not be allowed."""
        assert _is_allowed_print("    print('hello')") is False
        assert _is_allowed_print("print(value)") is False


class TestCheckFile:
    """Tests for check_file function."""

    def test_file_with_print(self):
        """File with print statement should return issues."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def foo():\n    print('hello')\n")
            f.flush()
            filepath = Path(f.name)

        try:
            issues = check_file(filepath)
            assert len(issues) == 1
            assert issues[0][1] == 2  # Line number
            assert "print" in issues[0][2]  # Line content
        finally:
            filepath.unlink()

    def test_file_without_print(self):
        """File without print should return no issues."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def foo():\n    return 42\n")
            f.flush()
            filepath = Path(f.name)

        try:
            issues = check_file(filepath)
            assert len(issues) == 0
        finally:
            filepath.unlink()

    def test_cli_file_allowed(self):
        """CLI file with print should be allowed."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write('import argparse\nprint("hello")\n')
            f.flush()
            filepath = Path(f.name)

        try:
            with mock.patch.dict(os.environ, {"ALLOW_PRINT_IN_CLI": "true"}):
                issues = check_file(filepath)
                assert len(issues) == 0
        finally:
            filepath.unlink()

    def test_non_existent_file(self):
        """Non-existent file should return no issues."""
        issues = check_file(Path("/nonexistent/file.py"))
        assert len(issues) == 0


class TestScanDirectory:
    """Tests for scan_directory function."""

    def test_scan_finds_prints(self):
        """Scanning should find print statements in Python files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lib_dir = Path(tmpdir) / "lib"
            lib_dir.mkdir()

            # Create file with print
            (lib_dir / "module.py").write_text("def foo():\n    print('hello')\n")

            issues = scan_directory(lib_dir)
            assert len(issues) == 1

    def test_scan_excludes_venv(self):
        """Scanning should skip .venv directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            venv_dir = Path(tmpdir) / ".venv" / "lib"
            venv_dir.mkdir(parents=True)

            # Create file with print in venv
            (venv_dir / "module.py").write_text("print('hello')\n")

            issues = scan_directory(Path(tmpdir))
            assert len(issues) == 0

    def test_scan_excludes_tests(self):
        """Scanning should skip tests directory when allowed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir) / "tests"
            tests_dir.mkdir()

            # Create test file with print
            (tests_dir / "test_module.py").write_text("print('test output')\n")

            with mock.patch.dict(os.environ, {"ALLOW_PRINT_IN_TESTS": "true"}):
                issues = scan_directory(Path(tmpdir))
                assert len(issues) == 0

    def test_scan_nonexistent_directory(self):
        """Scanning non-existent directory should return empty list."""
        issues = scan_directory(Path("/nonexistent/directory"))
        assert len(issues) == 0


class TestMain:
    """Tests for main function."""

    def test_disabled_returns_0(self):
        """Main should return 0 when enforcement is disabled."""
        with mock.patch.dict(os.environ, {"ENFORCE_LOGGING_ONLY": "false"}):
            result = main()
            assert result == 0

    def test_no_issues_returns_0(self):
        """Main should return 0 when no print statements found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal project structure
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()
            lib_dir = Path(tmpdir) / "plugins" / "autonomous-dev" / "lib"
            lib_dir.mkdir(parents=True)

            # Create clean file
            (lib_dir / "clean.py").write_text("def foo():\n    return 42\n")

            with mock.patch.dict(os.environ, {"ENFORCE_LOGGING_ONLY": "true"}):
                original_cwd = os.getcwd()
                try:
                    os.chdir(tmpdir)
                    result = main()
                    assert result == 0
                finally:
                    os.chdir(original_cwd)

    def test_issues_returns_2(self):
        """Main should return 2 when print statements found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal project structure
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()
            lib_dir = Path(tmpdir) / "plugins" / "autonomous-dev" / "lib"
            lib_dir.mkdir(parents=True)

            # Create file with print
            (lib_dir / "bad.py").write_text("def foo():\n    print('bad')\n")

            with mock.patch.dict(os.environ, {"ENFORCE_LOGGING_ONLY": "true"}):
                original_cwd = os.getcwd()
                try:
                    os.chdir(tmpdir)
                    result = main()
                    assert result == 2
                finally:
                    os.chdir(original_cwd)


class TestIntegration:
    """Integration tests for logging enforcement."""

    def test_full_workflow(self):
        """Test complete workflow with mixed files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Create project structure
            (project / ".git").mkdir()
            lib_dir = project / "plugins" / "autonomous-dev" / "lib"
            lib_dir.mkdir(parents=True)
            hooks_dir = project / "plugins" / "autonomous-dev" / "hooks"
            hooks_dir.mkdir(parents=True)
            tests_dir = project / "plugins" / "autonomous-dev" / "tests"
            tests_dir.mkdir(parents=True)

            # Create production file with print (should fail)
            (lib_dir / "module.py").write_text("def foo():\n    print('bad')\n")

            # Create CLI file with print (should pass)
            (hooks_dir / "cli.py").write_text('import argparse\nprint("ok")\n')

            # Create test file with print (should pass)
            (tests_dir / "test_module.py").write_text("print('test')\n")

            env = {
                "ENFORCE_LOGGING_ONLY": "true",
                "ALLOW_PRINT_IN_CLI": "true",
                "ALLOW_PRINT_IN_TESTS": "true",
            }

            with mock.patch.dict(os.environ, env):
                original_cwd = os.getcwd()
                try:
                    os.chdir(tmpdir)
                    result = main()
                    # Should find 1 issue in lib/module.py
                    assert result == 2
                finally:
                    os.chdir(original_cwd)

    def test_all_clean_passes(self):
        """Test clean project passes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Create project structure
            (project / ".git").mkdir()
            lib_dir = project / "plugins" / "autonomous-dev" / "lib"
            lib_dir.mkdir(parents=True)

            # Create clean production file (no print)
            (lib_dir / "module.py").write_text("""
import logging

logger = logging.getLogger(__name__)

def foo():
    logger.info("Using logger correctly")
    return 42
""")

            with mock.patch.dict(os.environ, {"ENFORCE_LOGGING_ONLY": "true"}):
                original_cwd = os.getcwd()
                try:
                    os.chdir(tmpdir)
                    result = main()
                    assert result == 0
                finally:
                    os.chdir(original_cwd)
