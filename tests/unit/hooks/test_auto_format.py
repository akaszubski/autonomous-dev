"""Unit tests for auto_format.py hook"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

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

from auto_format import (
    detect_language,
    format_python,
    format_javascript,
    format_go,
    get_source_files,
)


class TestDetectLanguage:
    """Test language detection."""

    def test_detects_python_from_pyproject_toml(self, tmp_path, monkeypatch):
        """Test detection of Python project from pyproject.toml."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").touch()
        assert detect_language() == "python"

    def test_detects_python_from_setup_py(self, tmp_path, monkeypatch):
        """Test detection of Python project from setup.py."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "setup.py").touch()
        assert detect_language() == "python"

    def test_detects_python_from_requirements_txt(self, tmp_path, monkeypatch):
        """Test detection of Python project from requirements.txt."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "requirements.txt").touch()
        assert detect_language() == "python"

    def test_detects_javascript_from_package_json(self, tmp_path, monkeypatch):
        """Test detection of JavaScript project from package.json."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "package.json").touch()
        assert detect_language() == "javascript"

    def test_detects_go_from_go_mod(self, tmp_path, monkeypatch):
        """Test detection of Go project from go.mod."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "go.mod").touch()
        assert detect_language() == "go"

    def test_returns_unknown_for_undetected_language(self, tmp_path, monkeypatch):
        """Test returns 'unknown' when no language files found."""
        monkeypatch.chdir(tmp_path)
        assert detect_language() == "unknown"


class TestFormatPython:
    """Test Python formatting."""

    @patch("subprocess.run")
    def test_format_python_runs_black_and_isort(self, mock_run):
        """Test that format_python runs both black and isort."""
        mock_run.return_value = MagicMock(returncode=0)

        test_files = [Path("test.py")]
        success, message = format_python(test_files)

        assert success is True
        assert "black + isort" in message
        assert mock_run.call_count == 2

        # Check that black was called
        black_call = mock_run.call_args_list[0]
        assert "black" in black_call[0][0]

        # Check that isort was called
        isort_call = mock_run.call_args_list[1]
        assert "isort" in isort_call[0][0]

    @patch("subprocess.run")
    def test_format_python_handles_missing_tools(self, mock_run):
        """Test that format_python handles missing black/isort gracefully."""
        mock_run.side_effect = FileNotFoundError()

        test_files = [Path("test.py")]
        success, message = format_python(test_files)

        assert success is False
        assert "not installed" in message


class TestFormatJavaScript:
    """Test JavaScript/TypeScript formatting."""

    @patch("subprocess.run")
    def test_format_javascript_runs_prettier(self, mock_run):
        """Test that format_javascript runs prettier."""
        mock_run.return_value = MagicMock(returncode=0)

        test_files = [Path("test.js")]
        success, message = format_javascript(test_files)

        assert success is True
        assert "prettier" in message

        # Check that npx prettier was called
        call_args = mock_run.call_args[0][0]
        assert "npx" in call_args
        assert "prettier" in call_args

    @patch("subprocess.run")
    def test_format_javascript_handles_missing_prettier(self, mock_run):
        """Test that format_javascript handles missing prettier gracefully."""
        mock_run.side_effect = FileNotFoundError()

        test_files = [Path("test.js")]
        success, message = format_javascript(test_files)

        assert success is False
        assert "not installed" in message


class TestFormatGo:
    """Test Go formatting."""

    @patch("subprocess.run")
    def test_format_go_runs_gofmt(self, mock_run):
        """Test that format_go runs gofmt."""
        mock_run.return_value = MagicMock(returncode=0)

        test_files = [Path("test.go")]
        success, message = format_go(test_files)

        assert success is True
        assert "gofmt" in message

        # Check that gofmt was called
        call_args = mock_run.call_args[0][0]
        assert "gofmt" in call_args

    @patch("subprocess.run")
    def test_format_go_handles_missing_gofmt(self, mock_run):
        """Test that format_go handles missing gofmt gracefully."""
        mock_run.side_effect = FileNotFoundError()

        test_files = [Path("test.go")]
        success, message = format_go(test_files)

        assert success is False
        assert "not installed" in message


class TestGetSourceFiles:
    """Test source file discovery."""

    def test_get_python_source_files(self, tmp_path, monkeypatch):
        """Test getting Python source files."""
        monkeypatch.chdir(tmp_path)

        # Create source directory with Python files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "test.py").touch()
        (src_dir / "another.py").touch()

        files = get_source_files("python")

        assert len(files) >= 2
        assert all(f.suffix == ".py" for f in files)

    def test_get_javascript_source_files(self, tmp_path, monkeypatch):
        """Test getting JavaScript source files."""
        monkeypatch.chdir(tmp_path)

        # Create source directory with JS files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "test.js").touch()
        (src_dir / "component.tsx").touch()

        files = get_source_files("javascript")

        assert len(files) >= 2

    def test_returns_empty_list_for_unknown_language(self, tmp_path, monkeypatch):
        """Test returns empty list for unknown language."""
        monkeypatch.chdir(tmp_path)
        files = get_source_files("unknown")
        assert files == []

    def test_returns_empty_list_when_no_src_dir(self, tmp_path, monkeypatch):
        """Test returns empty list when source directory doesn't exist."""
        monkeypatch.chdir(tmp_path)
        files = get_source_files("python")
        assert files == []
