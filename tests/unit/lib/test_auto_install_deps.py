#!/usr/bin/env python3
"""
Unit tests for auto_install_deps.py library.

Tests automatic dependency installation with security validation.

Author: implementer agent
Date: 2026-01-18
Related: Auto-install deps feature request
"""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add lib to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib"))

from auto_install_deps import (
    AutoInstallError,
    InstallFailedError,
    InstallTimeoutError,
    PackageNotAllowedError,
    _get_requirements_files,
    _is_enabled,
    _parse_requirements_file,
    auto_install_missing_deps,
    extract_missing_packages,
    get_allowed_packages,
    install_package,
    is_package_allowed,
)


class TestExtractMissingPackages:
    """Test extract_missing_packages() function."""

    def test_extract_importerror_single_quotes(self):
        """Test extraction from ImportError with single quotes."""
        output = "ImportError: No module named 'requests'"
        packages = extract_missing_packages(output)
        assert packages == ["requests"]

    def test_extract_importerror_double_quotes(self):
        """Test extraction from ImportError with double quotes."""
        output = 'ImportError: No module named "numpy"'
        packages = extract_missing_packages(output)
        assert packages == ["numpy"]

    def test_extract_modulenotfounderror(self):
        """Test extraction from ModuleNotFoundError."""
        output = "ModuleNotFoundError: No module named 'pandas'"
        packages = extract_missing_packages(output)
        assert packages == ["pandas"]

    def test_extract_multiple_packages(self):
        """Test extraction of multiple missing packages."""
        output = """
        ImportError: No module named 'requests'
        ModuleNotFoundError: No module named 'numpy'
        ImportError: No module named 'pandas'
        """
        packages = extract_missing_packages(output)
        assert sorted(packages) == ["numpy", "pandas", "requests"]

    def test_extract_submodule(self):
        """Test extraction extracts base package from submodule."""
        output = "ImportError: No module named 'requests.auth'"
        packages = extract_missing_packages(output)
        assert packages == ["requests"]

    def test_extract_no_errors(self):
        """Test extraction returns empty list when no errors."""
        output = "All tests passed successfully"
        packages = extract_missing_packages(output)
        assert packages == []

    def test_extract_duplicates_removed(self):
        """Test extraction removes duplicate package names."""
        output = """
        ImportError: No module named 'requests'
        ImportError: No module named 'requests'
        ModuleNotFoundError: No module named 'requests'
        """
        packages = extract_missing_packages(output)
        assert packages == ["requests"]


class TestParseRequirementsFile:
    """Test _parse_requirements_file() function."""

    def test_parse_requirements_txt(self, tmp_path):
        """Test parsing requirements.txt format."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.28.0\nnumpy>=1.20.0\npandas~=1.5.0")

        packages = _parse_requirements_file(req_file)
        assert packages == {"requests", "numpy", "pandas"}

    def test_parse_requirements_with_comments(self, tmp_path):
        """Test parsing requirements.txt with comments."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("# Comment\nrequests==2.28.0\n# Another comment\nnumpy>=1.20.0")

        packages = _parse_requirements_file(req_file)
        assert packages == {"requests", "numpy"}

    def test_parse_requirements_with_urls(self, tmp_path):
        """Test parsing requirements.txt skips URLs."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text(
            "requests==2.28.0\n"
            "https://example.com/package.whl\n"
            "git+https://github.com/user/repo.git\n"
            "numpy>=1.20.0"
        )

        packages = _parse_requirements_file(req_file)
        assert packages == {"requests", "numpy"}

    def test_parse_pyproject_toml(self, tmp_path):
        """Test parsing pyproject.toml format."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            'dependencies = [\n'
            '    "requests>=2.28.0",\n'
            '    "numpy>=1.20.0",\n'
            ']'
        )

        packages = _parse_requirements_file(pyproject)
        assert packages == {"requests", "numpy"}

    def test_parse_nonexistent_file(self, tmp_path):
        """Test parsing nonexistent file returns empty set."""
        packages = _parse_requirements_file(tmp_path / "nonexistent.txt")
        assert packages == set()


class TestIsPackageAllowed:
    """Test is_package_allowed() function."""

    def test_allowed_package_in_requirements(self, tmp_path):
        """Test allowed package from requirements.txt."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("pytest>=7.0.0\nrequests==2.28.0")

        assert is_package_allowed("pytest", [req_file]) is True
        assert is_package_allowed("requests", [req_file]) is True

    def test_disallowed_package_not_in_requirements(self, tmp_path):
        """Test disallowed package not in requirements."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("pytest>=7.0.0")

        assert is_package_allowed("malicious-package", [req_file]) is False

    def test_allowed_package_case_insensitive(self, tmp_path):
        """Test package name matching is case-insensitive."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("PyYAML>=6.0.0")

        assert is_package_allowed("pyyaml", [req_file]) is True
        assert is_package_allowed("PYYAML", [req_file]) is True
        assert is_package_allowed("PyYAML", [req_file]) is True

    def test_allowed_package_import_name_mapping(self, tmp_path):
        """Test import name to PyPI name mapping."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("pillow>=9.0.0")

        # PIL is the import name, pillow is the PyPI name
        assert is_package_allowed("PIL", [req_file]) is True

    def test_allowed_package_multiple_files(self, tmp_path):
        """Test package allowed from multiple requirements files."""
        req1 = tmp_path / "requirements.txt"
        req1.write_text("pytest>=7.0.0")

        req2 = tmp_path / "requirements-dev.txt"
        req2.write_text("black>=22.0.0")

        assert is_package_allowed("pytest", [req1, req2]) is True
        assert is_package_allowed("black", [req1, req2]) is True


class TestIsEnabled:
    """Test _is_enabled() function."""

    def test_enabled_true(self):
        """Test enabled when AUTO_INSTALL_DEPS=true."""
        with patch.dict(os.environ, {"AUTO_INSTALL_DEPS": "true"}):
            assert _is_enabled() is True

    def test_enabled_yes(self):
        """Test enabled when AUTO_INSTALL_DEPS=yes."""
        with patch.dict(os.environ, {"AUTO_INSTALL_DEPS": "yes"}):
            assert _is_enabled() is True

    def test_enabled_one(self):
        """Test enabled when AUTO_INSTALL_DEPS=1."""
        with patch.dict(os.environ, {"AUTO_INSTALL_DEPS": "1"}):
            assert _is_enabled() is True

    def test_disabled_false(self):
        """Test disabled when AUTO_INSTALL_DEPS=false."""
        with patch.dict(os.environ, {"AUTO_INSTALL_DEPS": "false"}):
            assert _is_enabled() is False

    def test_disabled_empty(self):
        """Test disabled when AUTO_INSTALL_DEPS is empty."""
        with patch.dict(os.environ, {"AUTO_INSTALL_DEPS": ""}):
            assert _is_enabled() is False

    def test_disabled_not_set(self):
        """Test disabled when AUTO_INSTALL_DEPS not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert _is_enabled() is False

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        with patch.dict(os.environ, {"AUTO_INSTALL_DEPS": "TRUE"}):
            assert _is_enabled() is True

        with patch.dict(os.environ, {"AUTO_INSTALL_DEPS": "Yes"}):
            assert _is_enabled() is True


class TestInstallPackage:
    """Test install_package() function."""

    def test_install_not_allowed_package(self, tmp_path):
        """Test installation fails for package not in requirements."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("pytest>=7.0.0")

        with pytest.raises(PackageNotAllowedError) as exc_info:
            install_package("malicious-package")

        assert "not in project requirements" in str(exc_info.value)

    @patch("auto_install_deps.subprocess.run")
    def test_install_success(self, mock_run, tmp_path):
        """Test successful package installation."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.28.0")

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with patch("auto_install_deps._get_requirements_files", return_value=[req_file]):
            result = install_package("requests", timeout=30)

        assert result is True
        mock_run.assert_called_once()

        # Verify subprocess.run was called with correct arguments
        call_args = mock_run.call_args
        assert call_args[0][0][0] == sys.executable
        assert call_args[0][0][1:4] == ["-m", "pip", "install"]
        assert "requests" in call_args[0][0]
        assert call_args[1]["shell"] is False  # Security check
        assert call_args[1]["timeout"] == 30

    @patch("auto_install_deps.subprocess.run")
    def test_install_failure(self, mock_run, tmp_path):
        """Test installation failure."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.28.0")

        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Installation failed")

        with patch("auto_install_deps._get_requirements_files", return_value=[req_file]):
            with pytest.raises(InstallFailedError) as exc_info:
                install_package("requests")

        assert "Failed to install" in str(exc_info.value)

    @patch("auto_install_deps.subprocess.run")
    def test_install_timeout(self, mock_run, tmp_path):
        """Test installation timeout."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.28.0")

        mock_run.side_effect = subprocess.TimeoutExpired("pip", 30)

        with patch("auto_install_deps._get_requirements_files", return_value=[req_file]):
            with pytest.raises(InstallTimeoutError) as exc_info:
                install_package("requests", timeout=30)

        assert "timed out" in str(exc_info.value)

    @patch("auto_install_deps.subprocess.run")
    def test_install_uses_pypi_name_mapping(self, mock_run, tmp_path):
        """Test installation uses PyPI name for import name."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("pillow>=9.0.0")

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with patch("auto_install_deps._get_requirements_files", return_value=[req_file]):
            install_package("PIL")  # Import name

        # Verify pip install was called with PyPI name "pillow"
        call_args = mock_run.call_args[0][0]
        assert "pillow" in call_args


class TestAutoInstallMissingDeps:
    """Test auto_install_missing_deps() function."""

    def test_disabled_returns_empty_list(self):
        """Test returns empty list when AUTO_INSTALL_DEPS is disabled."""
        output = "ImportError: No module named 'requests'"

        with patch.dict(os.environ, {"AUTO_INSTALL_DEPS": "false"}):
            installed = auto_install_missing_deps(output)

        assert installed == []

    def test_no_errors_returns_empty_list(self):
        """Test returns empty list when no import errors."""
        output = "All tests passed successfully"

        with patch.dict(os.environ, {"AUTO_INSTALL_DEPS": "true"}):
            installed = auto_install_missing_deps(output)

        assert installed == []

    @patch("auto_install_deps.install_package")
    def test_install_single_package(self, mock_install):
        """Test installation of single missing package."""
        output = "ImportError: No module named 'requests'"
        mock_install.return_value = True

        with patch.dict(os.environ, {"AUTO_INSTALL_DEPS": "true"}):
            installed = auto_install_missing_deps(output)

        assert installed == ["requests"]
        mock_install.assert_called_once_with("requests", timeout=30)

    @patch("auto_install_deps.install_package")
    def test_install_multiple_packages(self, mock_install):
        """Test installation of multiple missing packages."""
        output = """
        ImportError: No module named 'requests'
        ModuleNotFoundError: No module named 'numpy'
        """
        mock_install.return_value = True

        with patch.dict(os.environ, {"AUTO_INSTALL_DEPS": "true"}):
            installed = auto_install_missing_deps(output)

        assert sorted(installed) == ["numpy", "requests"]
        assert mock_install.call_count == 2

    @patch("auto_install_deps.install_package")
    def test_skip_failed_package(self, mock_install):
        """Test skips package that fails to install."""
        output = """
        ImportError: No module named 'requests'
        ModuleNotFoundError: No module named 'malicious'
        """

        def install_side_effect(package, timeout):
            if package == "malicious":
                raise PackageNotAllowedError("Not allowed")
            return True

        mock_install.side_effect = install_side_effect

        with patch.dict(os.environ, {"AUTO_INSTALL_DEPS": "true"}):
            installed = auto_install_missing_deps(output)

        # Only requests should be installed (malicious failed)
        assert installed == ["requests"]


class TestGetAllowedPackages:
    """Test get_allowed_packages() function."""

    def test_get_allowed_from_single_file(self, tmp_path):
        """Test get allowed packages from single requirements file."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("pytest>=7.0.0\nrequests==2.28.0\nnumpy>=1.20.0")

        packages = get_allowed_packages([req_file])
        assert packages == {"pytest", "requests", "numpy"}

    def test_get_allowed_from_multiple_files(self, tmp_path):
        """Test get allowed packages from multiple requirements files."""
        req1 = tmp_path / "requirements.txt"
        req1.write_text("pytest>=7.0.0\nrequests==2.28.0")

        req2 = tmp_path / "requirements-dev.txt"
        req2.write_text("black>=22.0.0\nmypy>=0.990")

        packages = get_allowed_packages([req1, req2])
        assert packages == {"pytest", "requests", "black", "mypy"}


class TestSecurityFeatures:
    """Test security features of auto_install_deps."""

    def test_never_uses_shell_true(self, tmp_path):
        """Test install_package never uses shell=True."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.28.0")

        with patch("auto_install_deps.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            with patch("auto_install_deps._get_requirements_files", return_value=[req_file]):
                install_package("requests")

            # Verify shell=False was passed
            call_args = mock_run.call_args
            assert call_args[1]["shell"] is False

    def test_whitelist_validation(self, tmp_path):
        """Test whitelist validation prevents arbitrary package installation."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("pytest>=7.0.0")

        # Attempt to install package not in requirements
        with pytest.raises(PackageNotAllowedError):
            with patch("auto_install_deps._get_requirements_files", return_value=[req_file]):
                install_package("malicious-package")

    def test_timeout_protection(self, tmp_path):
        """Test timeout protection prevents hanging installations."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.28.0")

        with patch("auto_install_deps.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("pip", 30)

            with patch("auto_install_deps._get_requirements_files", return_value=[req_file]):
                with pytest.raises(InstallTimeoutError):
                    install_package("requests", timeout=30)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_pytest_output(self):
        """Test empty pytest output."""
        packages = extract_missing_packages("")
        assert packages == []

    def test_malformed_error_message(self):
        """Test malformed error message."""
        output = "ImportError: Something went wrong"
        packages = extract_missing_packages(output)
        assert packages == []

    def test_package_with_hyphen(self, tmp_path):
        """Test package with hyphen in name."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("python-dateutil>=2.8.0")

        packages = _parse_requirements_file(req_file)
        assert "python-dateutil" in packages

    def test_package_with_underscore(self, tmp_path):
        """Test package with underscore in name."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("pytest_cov>=4.0.0")

        packages = _parse_requirements_file(req_file)
        assert "pytest_cov" in packages
