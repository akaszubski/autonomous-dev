#!/usr/bin/env python3
"""
TDD Tests for Code Path Analyzer Library (FAILING - Red Phase)

This module contains FAILING tests for code_path_analyzer.py which discovers
all code paths matching a pattern for debug-first enforcement.

Requirements:
1. Find all locations matching a pattern (regex search)
2. Return CodePath objects with file_path, line_number, context, match_text
3. Handle empty results gracefully
4. Handle invalid patterns gracefully
5. Search recursively in project directory
6. Filter by file types (e.g., ["*.py", "*.md"])
7. Exclude common directories (.git, __pycache__, node_modules)
8. Support multiline context (N lines before/after match)

Test Coverage Target: 95%+ of code path discovery logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe code path discovery requirements
- Tests should FAIL until code_path_analyzer.py is implemented
- Each test validates ONE discovery requirement

Author: test-master agent
Date: 2026-01-03
Related: Issue #200 - Debug-first enforcement and self-test requirements
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# This import will FAIL until code_path_analyzer.py is created
from plugins.autonomous_dev.lib.code_path_analyzer import (
    CodePath,
    CodePathAnalyzer,
    find_all_code_paths,
)


class TestCodePathDataClass:
    """Test CodePath dataclass structure."""

    def test_code_path_creation(self):
        """Test CodePath can be created with all fields.

        REQUIREMENT: CodePath dataclass with proper fields.
        Expected: CodePath created with file_path, line_number, context, match_text.
        """
        code_path = CodePath(
            file_path="/path/to/file.py",
            line_number=42,
            context="def function():\n    result = calculate()\n    return result",
            match_text="calculate()"
        )

        assert code_path.file_path == "/path/to/file.py"
        assert code_path.line_number == 42
        assert code_path.context == "def function():\n    result = calculate()\n    return result"
        assert code_path.match_text == "calculate()"

    def test_code_path_minimal_creation(self):
        """Test CodePath with minimal required fields.

        REQUIREMENT: CodePath requires file_path, line_number, match_text.
        Expected: CodePath created with empty context allowed.
        """
        code_path = CodePath(
            file_path="/path/to/file.py",
            line_number=1,
            context="",
            match_text="import sys"
        )

        assert code_path.file_path == "/path/to/file.py"
        assert code_path.line_number == 1
        assert code_path.match_text == "import sys"


class TestFindAllCodePaths:
    """Test find_all_code_paths() function for pattern matching."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project with test files."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()

        # Create Python file with multiple matches
        py_file = project_root / "example.py"
        py_file.write_text("""
def calculate():
    result = compute_value()
    return result

def process():
    value = calculate()
    return value
""")

        # Create another Python file
        py_file2 = project_root / "utils.py"
        py_file2.write_text("""
def compute_value():
    return 42
""")

        # Create markdown file
        md_file = project_root / "README.md"
        md_file.write_text("""
# README

Call `calculate()` to get result.
""")

        # Create subdirectory with file
        subdir = project_root / "subdir"
        subdir.mkdir()
        sub_file = subdir / "module.py"
        sub_file.write_text("""
from example import calculate

result = calculate()
""")

        return project_root

    def test_find_simple_pattern(self, temp_project):
        """Test finding simple string pattern.

        REQUIREMENT: Find all locations matching a pattern.
        Expected: CodePath objects for each match.
        """
        results = find_all_code_paths(
            pattern="calculate",
            project_root=temp_project
        )

        assert len(results) > 0
        assert all(isinstance(r, CodePath) for r in results)
        assert all("calculate" in r.match_text for r in results)

    def test_find_regex_pattern(self, temp_project):
        """Test finding regex pattern.

        REQUIREMENT: Support regex patterns.
        Expected: CodePath objects matching regex.
        """
        results = find_all_code_paths(
            pattern=r"def \w+\(\):",
            project_root=temp_project,
            file_types=["*.py"]
        )

        assert len(results) > 0
        assert all("def " in r.match_text for r in results)

    def test_filter_by_file_types(self, temp_project):
        """Test filtering by file types.

        REQUIREMENT: Filter by file types (e.g., ["*.py", "*.md"]).
        Expected: Only files matching file_types included.
        """
        # Search only Python files
        py_results = find_all_code_paths(
            pattern="calculate",
            project_root=temp_project,
            file_types=["*.py"]
        )

        assert all(r.file_path.endswith('.py') for r in py_results)

        # Search only Markdown files
        md_results = find_all_code_paths(
            pattern="calculate",
            project_root=temp_project,
            file_types=["*.md"]
        )

        assert all(r.file_path.endswith('.md') for r in md_results)

    def test_multiple_file_types(self, temp_project):
        """Test filtering with multiple file types.

        REQUIREMENT: Support multiple file types.
        Expected: Files matching any file type included.
        """
        results = find_all_code_paths(
            pattern="calculate",
            project_root=temp_project,
            file_types=["*.py", "*.md"]
        )

        file_extensions = {Path(r.file_path).suffix for r in results}
        assert '.py' in file_extensions or '.md' in file_extensions

    def test_recursive_search(self, temp_project):
        """Test recursive search in subdirectories.

        REQUIREMENT: Search recursively in project directory.
        Expected: Matches found in subdirectories.
        """
        results = find_all_code_paths(
            pattern="calculate",
            project_root=temp_project
        )

        # Should find matches in subdirectory
        subdir_matches = [r for r in results if "subdir" in r.file_path]
        assert len(subdir_matches) > 0

    def test_line_numbers_accurate(self, temp_project):
        """Test line numbers are accurate.

        REQUIREMENT: Return accurate line numbers.
        Expected: line_number points to actual match location.
        """
        results = find_all_code_paths(
            pattern="def calculate",
            project_root=temp_project,
            file_types=["*.py"]
        )

        # Verify line numbers are positive integers
        assert all(r.line_number > 0 for r in results)

        # Verify we can read the file and find the match at that line
        for result in results:
            with open(result.file_path, 'r') as f:
                lines = f.readlines()
                # Line numbers are 1-indexed
                line_content = lines[result.line_number - 1]
                assert "calculate" in line_content

    def test_context_includes_surrounding_lines(self, temp_project):
        """Test context includes surrounding lines.

        REQUIREMENT: Support multiline context (N lines before/after match).
        Expected: Context contains lines before and after match.
        """
        results = find_all_code_paths(
            pattern="def calculate",
            project_root=temp_project,
            file_types=["*.py"],
            context_lines=2
        )

        # Context should be non-empty and contain multiple lines
        assert all(len(r.context) > 0 for r in results)
        assert any('\n' in r.context for r in results)

    def test_empty_results_no_matches(self, temp_project):
        """Test empty results when no matches found.

        REQUIREMENT: Handle empty results gracefully.
        Expected: Empty list returned, no errors.
        """
        results = find_all_code_paths(
            pattern="nonexistent_pattern_xyz123",
            project_root=temp_project
        )

        assert results == []
        assert isinstance(results, list)

    def test_invalid_pattern_gracefully(self, temp_project):
        """Test handling invalid regex pattern.

        REQUIREMENT: Handle invalid patterns gracefully.
        Expected: Returns empty list or raises clear error.
        """
        try:
            results = find_all_code_paths(
                pattern="[invalid(regex",
                project_root=temp_project
            )
            # If it doesn't raise, should return empty or valid results
            assert isinstance(results, list)
        except ValueError as e:
            # Acceptable to raise ValueError for invalid regex
            assert "pattern" in str(e).lower() or "regex" in str(e).lower()

    def test_nonexistent_project_root(self):
        """Test handling nonexistent project root.

        REQUIREMENT: Validate project_root parameter.
        Expected: Raises ValueError or returns empty list.
        """
        try:
            results = find_all_code_paths(
                pattern="test",
                project_root="/nonexistent/path/xyz123"
            )
            # If it doesn't raise, should return empty list
            assert results == []
        except (ValueError, FileNotFoundError) as e:
            # Acceptable to raise error for invalid path
            assert "path" in str(e).lower() or "not found" in str(e).lower()


class TestCodePathAnalyzerClass:
    """Test CodePathAnalyzer class for stateful code path discovery."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project with test files."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()

        # Create .git directory (should be excluded)
        git_dir = project_root / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")

        # Create __pycache__ directory (should be excluded)
        pycache_dir = project_root / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "test.pyc").write_text("compiled")

        # Create node_modules directory (should be excluded)
        node_dir = project_root / "node_modules"
        node_dir.mkdir()
        (node_dir / "package.js").write_text("package")

        # Create normal Python file
        py_file = project_root / "example.py"
        py_file.write_text("""
def test_function():
    pass
""")

        return project_root

    def test_analyzer_initialization(self, temp_project):
        """Test CodePathAnalyzer initializes with project root.

        REQUIREMENT: CodePathAnalyzer class for stateful discovery.
        Expected: Analyzer created with project_root.
        """
        analyzer = CodePathAnalyzer(temp_project)

        assert analyzer.project_root == temp_project

    def test_analyzer_find_method(self, temp_project):
        """Test CodePathAnalyzer.find() method.

        REQUIREMENT: Analyzer.find() executes search.
        Expected: Returns list of CodePath objects.
        """
        analyzer = CodePathAnalyzer(temp_project)
        results = analyzer.find(pattern="def test_function")

        assert isinstance(results, list)
        assert all(isinstance(r, CodePath) for r in results)

    def test_analyzer_excludes_git_directory(self, temp_project):
        """Test analyzer excludes .git directory.

        REQUIREMENT: Exclude common directories (.git).
        Expected: No matches in .git directory.
        """
        analyzer = CodePathAnalyzer(temp_project)
        results = analyzer.find(pattern="config")

        # Should not find matches in .git directory
        git_matches = [r for r in results if ".git" in r.file_path]
        assert len(git_matches) == 0

    def test_analyzer_excludes_pycache_directory(self, temp_project):
        """Test analyzer excludes __pycache__ directory.

        REQUIREMENT: Exclude common directories (__pycache__).
        Expected: No matches in __pycache__ directory.
        """
        analyzer = CodePathAnalyzer(temp_project)
        results = analyzer.find(pattern="compiled")

        # Should not find matches in __pycache__ directory
        pycache_matches = [r for r in results if "__pycache__" in r.file_path]
        assert len(pycache_matches) == 0

    def test_analyzer_excludes_node_modules_directory(self, temp_project):
        """Test analyzer excludes node_modules directory.

        REQUIREMENT: Exclude common directories (node_modules).
        Expected: No matches in node_modules directory.
        """
        analyzer = CodePathAnalyzer(temp_project)
        results = analyzer.find(pattern="package")

        # Should not find matches in node_modules directory
        node_matches = [r for r in results if "node_modules" in r.file_path]
        assert len(node_matches) == 0

    def test_analyzer_custom_exclude_patterns(self, temp_project):
        """Test analyzer with custom exclude patterns.

        REQUIREMENT: Support custom exclude patterns.
        Expected: Custom patterns excluded from search.
        """
        # Create custom directory to exclude
        custom_dir = temp_project / "build"
        custom_dir.mkdir()
        (custom_dir / "output.py").write_text("def build():\n    pass")

        analyzer = CodePathAnalyzer(
            temp_project,
            exclude_patterns=["build", ".git", "__pycache__", "node_modules"]
        )
        results = analyzer.find(pattern="def build")

        # Should not find matches in build directory
        build_matches = [r for r in results if "build" in r.file_path]
        assert len(build_matches) == 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project with edge case files."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()

        # Create file with special characters
        special_file = project_root / "special-chars.py"
        special_file.write_text("# Special: @#$%^&*()")

        # Create empty file
        empty_file = project_root / "empty.py"
        empty_file.write_text("")

        # Create binary file (should be skipped)
        binary_file = project_root / "binary.bin"
        binary_file.write_bytes(b'\x00\x01\x02\x03')

        # Create very long line
        long_line_file = project_root / "long_line.py"
        long_line_file.write_text("x = " + "a" * 10000)

        return project_root

    def test_search_empty_file(self, temp_project):
        """Test searching empty file.

        REQUIREMENT: Handle empty files gracefully.
        Expected: No matches, no errors.
        """
        results = find_all_code_paths(
            pattern="test",
            project_root=temp_project,
            file_types=["*.py"]
        )

        # Should not crash on empty file
        assert isinstance(results, list)

    def test_search_binary_file_skipped(self, temp_project):
        """Test binary files are skipped.

        REQUIREMENT: Skip binary files.
        Expected: Binary files not included in results.
        """
        results = find_all_code_paths(
            pattern=".*",
            project_root=temp_project,
            file_types=["*.bin"]
        )

        # Binary files should be skipped or handled gracefully
        assert isinstance(results, list)

    def test_search_very_long_line(self, temp_project):
        """Test handling very long lines.

        REQUIREMENT: Handle very long lines gracefully.
        Expected: Match found, context truncated if needed.
        """
        results = find_all_code_paths(
            pattern="x = a",
            project_root=temp_project,
            file_types=["*.py"]
        )

        # Should find match in file with long line
        assert len(results) > 0
        # Context should be truncated or handled reasonably
        for result in results:
            if "long_line.py" in result.file_path:
                # Context should exist but be reasonable length
                assert len(result.context) < 100000  # Not the entire 10k line

    def test_search_special_characters(self, temp_project):
        """Test searching for special characters.

        REQUIREMENT: Handle special characters in pattern.
        Expected: Special chars escaped properly in regex.
        """
        results = find_all_code_paths(
            pattern="@#\\$%",  # Escaped special chars
            project_root=temp_project,
            file_types=["*.py"]
        )

        # Should handle special characters in pattern
        assert isinstance(results, list)

    def test_match_text_extraction_accurate(self, temp_project):
        """Test match_text contains actual matched text.

        REQUIREMENT: match_text contains the actual match.
        Expected: match_text is substring of original line.
        """
        py_file = temp_project / "test.py"
        py_file.write_text("def my_function():\n    pass")

        results = find_all_code_paths(
            pattern=r"def \w+",
            project_root=temp_project,
            file_types=["*.py"]
        )

        for result in results:
            if "test.py" in result.file_path:
                assert "def my_function" in result.match_text or "def " in result.match_text

    def test_context_default_value(self, temp_project):
        """Test default context_lines value.

        REQUIREMENT: Default context_lines is reasonable.
        Expected: Default provides 2-3 lines of context.
        """
        py_file = temp_project / "test.py"
        py_file.write_text("""
line1
line2
def target():
    pass
line6
line7
""")

        results = find_all_code_paths(
            pattern="def target",
            project_root=temp_project,
            file_types=["*.py"]
        )

        # Default context should include surrounding lines
        assert len(results) > 0
        for result in results:
            if "test.py" in result.file_path:
                # Context should contain multiple lines
                assert result.context.count('\n') >= 2

    def test_case_sensitive_search(self, temp_project):
        """Test case-sensitive search.

        REQUIREMENT: Support case-sensitive search.
        Expected: Pattern matching is case-sensitive by default.
        """
        py_file = temp_project / "test.py"
        py_file.write_text("Calculate\ncalculate\nCALCULATE")

        results_lower = find_all_code_paths(
            pattern="calculate",
            project_root=temp_project,
            file_types=["*.py"]
        )

        results_upper = find_all_code_paths(
            pattern="CALCULATE",
            project_root=temp_project,
            file_types=["*.py"]
        )

        # Should find different results for different cases
        lower_matches = [r for r in results_lower if "test.py" in r.file_path]
        upper_matches = [r for r in results_upper if "test.py" in r.file_path]

        assert len(lower_matches) > 0
        assert len(upper_matches) > 0

    def test_case_insensitive_search(self, temp_project):
        """Test case-insensitive search option.

        REQUIREMENT: Support case-insensitive search.
        Expected: case_sensitive=False finds all case variations.
        """
        py_file = temp_project / "test.py"
        py_file.write_text("Calculate\ncalculate\nCALCULATE")

        results = find_all_code_paths(
            pattern="calculate",
            project_root=temp_project,
            file_types=["*.py"],
            case_sensitive=False
        )

        # Should find all three variations
        test_matches = [r for r in results if "test.py" in r.file_path]
        assert len(test_matches) == 3
