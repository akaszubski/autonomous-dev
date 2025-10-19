"""Unit tests for auto_enforce_coverage.py hook"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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

from auto_enforce_coverage import (
    get_coverage_summary,
    find_uncovered_code,
    extract_uncovered_code,
    create_coverage_test_prompt,
)


class TestGetCoverageSummary:
    """Test coverage summary extraction."""

    def test_extracts_percent_covered(self):
        """Test extraction of coverage percentage."""
        coverage_data = {
            "totals": {
                "percent_covered": 85.5,
                "num_statements": 100,
                "covered_lines": 85,
                "missing_lines": 15,
                "excluded_lines": 0,
            }
        }

        summary = get_coverage_summary(coverage_data)

        assert summary["percent_covered"] == 85.5
        assert summary["num_statements"] == 100
        assert summary["covered_lines"] == 85
        assert summary["missing_lines"] == 15

    def test_handles_missing_totals(self):
        """Test handling of missing totals in coverage data."""
        coverage_data = {}

        summary = get_coverage_summary(coverage_data)

        assert summary["percent_covered"] == 0.0
        assert summary["num_statements"] == 0


class TestFindUncoveredCode:
    """Test uncovered code detection."""

    def test_finds_uncovered_files(self):
        """Test finding files with missing coverage."""
        coverage_data = {
            "files": {
                "src/module1.py": {
                    "missing_lines": [10, 15, 20],
                    "summary": {"percent_covered": 75.0},
                },
                "src/module2.py": {
                    "missing_lines": [5, 8],
                    "summary": {"percent_covered": 90.0},
                },
            }
        }

        uncovered = find_uncovered_code(coverage_data)

        assert len(uncovered) == 2
        # Should be sorted by priority (more missing + lower % = higher priority)
        assert uncovered[0]["file"] == "src/module1.py"
        assert uncovered[0]["num_missing"] == 3

    def test_ignores_fully_covered_files(self):
        """Test that fully covered files are not included."""
        coverage_data = {
            "files": {
                "src/module1.py": {
                    "missing_lines": [],
                    "summary": {"percent_covered": 100.0},
                },
                "src/module2.py": {
                    "missing_lines": [10],
                    "summary": {"percent_covered": 95.0},
                },
            }
        }

        uncovered = find_uncovered_code(coverage_data)

        assert len(uncovered) == 1
        assert uncovered[0]["file"] == "src/module2.py"

    def test_ignores_test_files(self):
        """Test that test files are ignored."""
        coverage_data = {
            "files": {
                "tests/test_module.py": {
                    "missing_lines": [10, 20],
                    "summary": {"percent_covered": 50.0},
                },
                "src/module.py": {
                    "missing_lines": [5],
                    "summary": {"percent_covered": 95.0},
                },
            }
        }

        uncovered = find_uncovered_code(coverage_data)

        # Should only include src files
        assert len(uncovered) == 1
        assert uncovered[0]["file"] == "src/module.py"

    def test_sorts_by_priority(self):
        """Test that results are sorted by priority."""
        coverage_data = {
            "files": {
                "src/low_priority.py": {
                    "missing_lines": [1],
                    "summary": {"percent_covered": 99.0},
                },
                "src/high_priority.py": {
                    "missing_lines": [1, 2, 3, 4, 5],
                    "summary": {"percent_covered": 50.0},
                },
            }
        }

        uncovered = find_uncovered_code(coverage_data)

        # high_priority should be first (more missing + lower %)
        assert uncovered[0]["file"] == "src/high_priority.py"
        assert uncovered[0]["priority"] > uncovered[1]["priority"]


class TestExtractUncoveredCode:
    """Test uncovered code extraction."""

    def test_extracts_code_with_context(self, tmp_path):
        """Test extraction of uncovered code with surrounding context."""
        test_file = tmp_path / "module.py"
        test_file.write_text(
            "line 1\n"
            "line 2\n"
            "line 3 - uncovered\n"
            "line 4\n"
            "line 5\n"
        )

        code = extract_uncovered_code(str(test_file), [3])

        # Should include line 3 and context (lines 1-5)
        assert "line 3" in code
        assert "→" in code  # Marker for uncovered line

    def test_extracts_multiple_uncovered_lines(self, tmp_path):
        """Test extraction of multiple uncovered lines."""
        test_file = tmp_path / "module.py"
        test_file.write_text("\n".join([f"line {i}" for i in range(1, 11)]))

        code = extract_uncovered_code(str(test_file), [3, 7])

        # Should include both uncovered lines with context
        assert "line 3" in code
        assert "line 7" in code

    def test_handles_file_read_error(self):
        """Test handling of file read errors."""
        code = extract_uncovered_code("nonexistent.py", [1, 2, 3])

        assert "Error reading file" in code


class TestCreateCoverageTestPrompt:
    """Test coverage test prompt generation."""

    def test_creates_prompt_with_file_info(self):
        """Test that prompt includes file information."""
        uncovered_item = {
            "file": "src/module.py",
            "missing_lines": [10, 15, 20],
            "coverage_pct": 75.0,
            "num_missing": 3,
        }

        # Mock extract_uncovered_code to avoid file I/O
        with patch("auto_enforce_coverage.extract_uncovered_code") as mock_extract:
            mock_extract.return_value = "def function():\n    pass"

            prompt = create_coverage_test_prompt(uncovered_item)

        assert "src/module.py" in prompt
        assert "75.0%" in prompt
        assert "[10, 15, 20]" in prompt

    def test_prompt_includes_instructions(self):
        """Test that prompt includes testing instructions."""
        uncovered_item = {
            "file": "src/module.py",
            "missing_lines": [5],
            "coverage_pct": 90.0,
            "num_missing": 1,
        }

        with patch("auto_enforce_coverage.extract_uncovered_code") as mock_extract:
            mock_extract.return_value = "code"

            prompt = create_coverage_test_prompt(uncovered_item)

        assert "test-master" in prompt
        assert "pytest" in prompt
        assert "coverage" in prompt.lower()
