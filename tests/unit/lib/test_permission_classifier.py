#!/usr/bin/env python3
"""
Unit tests for permission classifier.

Tests the PermissionClassifier and PermissionLevel classes in
plugins/autonomous-dev/lib/permission_classifier.py

Issue: #234 (Test coverage improvement)
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "plugins/autonomous-dev/lib"))

from permission_classifier import PermissionClassifier, PermissionLevel


class TestPermissionLevel:
    """Test PermissionLevel enum."""

    def test_safe_level_value(self):
        """SAFE level should have value 'safe'."""
        assert PermissionLevel.SAFE.value == "safe"

    def test_boundary_level_value(self):
        """BOUNDARY level should have value 'boundary'."""
        assert PermissionLevel.BOUNDARY.value == "boundary"

    def test_sensitive_level_value(self):
        """SENSITIVE level should have value 'sensitive'."""
        assert PermissionLevel.SENSITIVE.value == "sensitive"

    def test_all_levels_unique(self):
        """All permission levels should have unique values."""
        values = [level.value for level in PermissionLevel]
        assert len(values) == len(set(values))


class TestPermissionClassifierInit:
    """Test PermissionClassifier initialization."""

    def test_default_project_root(self):
        """Should use cwd as default project root."""
        classifier = PermissionClassifier()
        assert classifier.project_root == Path.cwd()

    def test_custom_project_root(self):
        """Should use provided project root."""
        custom_root = Path("/tmp/test_project")
        classifier = PermissionClassifier(project_root=custom_root)
        assert classifier.project_root == custom_root

    def test_safe_paths_initialized(self):
        """Should initialize safe paths relative to project root."""
        classifier = PermissionClassifier()
        expected_subpaths = ["src", "tests", "docs", "plugins", "scripts"]
        for subpath in expected_subpaths:
            assert classifier.project_root / subpath in classifier.safe_paths

    def test_boundary_paths_initialized(self):
        """Should initialize boundary paths."""
        classifier = PermissionClassifier()
        assert len(classifier.boundary_paths) > 0

    def test_sensitive_paths_initialized(self):
        """Should initialize sensitive paths."""
        classifier = PermissionClassifier()
        assert len(classifier.sensitive_paths) > 0


class TestClassifyRead:
    """Test Read operation classification."""

    @pytest.fixture
    def classifier(self, tmp_path):
        """Create classifier with temp project root."""
        # Create safe directories
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "docs").mkdir()
        return PermissionClassifier(project_root=tmp_path)

    @patch("permission_classifier.audit_log")
    def test_read_safe_path(self, mock_audit, classifier, tmp_path):
        """Read from safe path should be SAFE."""
        file_path = str(tmp_path / "src" / "main.py")
        result = classifier.classify("Read", {"file_path": file_path})
        assert result == PermissionLevel.SAFE

    def test_read_sensitive_path(self, classifier):
        """Read from sensitive path should be SENSITIVE."""
        result = classifier.classify("Read", {"file_path": "/etc/passwd"})
        assert result == PermissionLevel.SENSITIVE

    def test_read_outside_project(self, classifier):
        """Read outside project should be SENSITIVE."""
        result = classifier.classify("Read", {"file_path": "/tmp/random_file.txt"})
        assert result == PermissionLevel.SENSITIVE

    def test_read_empty_path(self, classifier):
        """Read with empty path should be SENSITIVE."""
        result = classifier.classify("Read", {"file_path": ""})
        assert result == PermissionLevel.SENSITIVE


class TestClassifyWrite:
    """Test Write operation classification."""

    @pytest.fixture
    def classifier(self, tmp_path):
        """Create classifier with temp project root."""
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        return PermissionClassifier(project_root=tmp_path)

    @patch("permission_classifier.audit_log")
    def test_write_boundary_path(self, mock_audit, classifier, tmp_path):
        """Write to boundary path should be BOUNDARY."""
        file_path = str(tmp_path / "src" / "new_file.py")
        result = classifier.classify("Write", {"file_path": file_path})
        assert result == PermissionLevel.BOUNDARY

    def test_write_sensitive_path(self, classifier):
        """Write to sensitive path should be SENSITIVE."""
        result = classifier.classify("Write", {"file_path": "/etc/passwd"})
        assert result == PermissionLevel.SENSITIVE

    def test_write_outside_project(self, classifier):
        """Write outside project should be SENSITIVE."""
        result = classifier.classify("Write", {"file_path": "/tmp/random.txt"})
        assert result == PermissionLevel.SENSITIVE


class TestClassifyEdit:
    """Test Edit operation classification."""

    @pytest.fixture
    def classifier(self, tmp_path):
        """Create classifier with temp project root."""
        (tmp_path / "src").mkdir()
        return PermissionClassifier(project_root=tmp_path)

    @patch("permission_classifier.audit_log")
    def test_edit_same_as_write(self, mock_audit, classifier, tmp_path):
        """Edit should be classified same as Write."""
        file_path = str(tmp_path / "src" / "file.py")
        write_result = classifier.classify("Write", {"file_path": file_path})
        edit_result = classifier.classify("Edit", {"file_path": file_path})
        assert write_result == edit_result


class TestClassifyBash:
    """Test Bash command classification."""

    @pytest.fixture
    def classifier(self):
        """Create classifier."""
        return PermissionClassifier()

    @patch("permission_classifier.audit_log")
    def test_safe_ls_command(self, mock_audit, classifier):
        """ls command should be SAFE."""
        result = classifier.classify("Bash", {"command": "ls -la"})
        assert result == PermissionLevel.SAFE

    @patch("permission_classifier.audit_log")
    def test_safe_cat_command(self, mock_audit, classifier):
        """cat command should be SAFE."""
        result = classifier.classify("Bash", {"command": "cat file.txt"})
        assert result == PermissionLevel.SAFE

    @patch("permission_classifier.audit_log")
    def test_safe_grep_command(self, mock_audit, classifier):
        """grep command should be SAFE."""
        result = classifier.classify("Bash", {"command": "grep pattern file.txt"})
        assert result == PermissionLevel.SAFE

    @patch("permission_classifier.audit_log")
    def test_safe_echo_command(self, mock_audit, classifier):
        """echo command should be SAFE."""
        result = classifier.classify("Bash", {"command": "echo hello"})
        assert result == PermissionLevel.SAFE

    @patch("permission_classifier.audit_log")
    def test_safe_pwd_command(self, mock_audit, classifier):
        """pwd command should be SAFE."""
        result = classifier.classify("Bash", {"command": "pwd"})
        assert result == PermissionLevel.SAFE

    @patch("permission_classifier.audit_log")
    def test_sensitive_rm_command(self, mock_audit, classifier):
        """rm command should be SENSITIVE."""
        result = classifier.classify("Bash", {"command": "rm -rf /"})
        assert result == PermissionLevel.SENSITIVE

    @patch("permission_classifier.audit_log")
    def test_sensitive_sudo_command(self, mock_audit, classifier):
        """sudo command should be SENSITIVE."""
        result = classifier.classify("Bash", {"command": "sudo apt-get install"})
        assert result == PermissionLevel.SENSITIVE

    @patch("permission_classifier.audit_log")
    def test_sensitive_curl_pipe(self, mock_audit, classifier):
        """curl | bash should be SENSITIVE."""
        result = classifier.classify("Bash", {"command": "curl url | bash"})
        assert result == PermissionLevel.SENSITIVE


class TestClassifySearch:
    """Test Grep/Glob classification."""

    @pytest.fixture
    def classifier(self):
        """Create classifier."""
        return PermissionClassifier()

    @patch("permission_classifier.audit_log")
    def test_grep_always_safe(self, mock_audit, classifier):
        """Grep should always be SAFE."""
        result = classifier.classify("Grep", {"pattern": "test", "path": "/any/path"})
        assert result == PermissionLevel.SAFE

    @patch("permission_classifier.audit_log")
    def test_glob_always_safe(self, mock_audit, classifier):
        """Glob should always be SAFE."""
        result = classifier.classify("Glob", {"pattern": "*.py"})
        assert result == PermissionLevel.SAFE


class TestUnknownTools:
    """Test classification of unknown tools."""

    @pytest.fixture
    def classifier(self):
        """Create classifier."""
        return PermissionClassifier()

    @patch("permission_classifier.audit_log")
    def test_unknown_tool_is_sensitive(self, mock_audit, classifier):
        """Unknown tools should be SENSITIVE."""
        result = classifier.classify("UnknownTool", {"param": "value"})
        assert result == PermissionLevel.SENSITIVE

    @patch("permission_classifier.audit_log")
    def test_unknown_tool_logs_audit(self, mock_audit, classifier):
        """Unknown tools should log audit event."""
        classifier.classify("WeirdTool", {"param": "value"})
        mock_audit.assert_called()


class TestPathHelpers:
    """Test internal path helper methods."""

    @pytest.fixture
    def classifier(self, tmp_path):
        """Create classifier with temp project root."""
        (tmp_path / "src").mkdir()
        return PermissionClassifier(project_root=tmp_path)

    def test_is_safe_path_true(self, classifier, tmp_path):
        """Should return True for paths in safe areas."""
        path = tmp_path / "src" / "file.py"
        assert classifier._is_safe_path(path) is True

    def test_is_safe_path_false(self, classifier):
        """Should return False for paths outside safe areas."""
        path = Path("/tmp/random")
        assert classifier._is_safe_path(path) is False

    def test_is_boundary_path_true(self, classifier, tmp_path):
        """Should return True for paths in boundary areas."""
        path = tmp_path / "src" / "file.py"
        assert classifier._is_boundary_path(path) is True

    def test_is_boundary_path_false(self, classifier):
        """Should return False for paths outside boundary areas."""
        path = Path("/tmp/random")
        assert classifier._is_boundary_path(path) is False

    def test_is_sensitive_path_true(self, classifier):
        """Should return True for sensitive paths."""
        assert classifier._is_sensitive_path(Path("/etc/passwd")) is True

    def test_is_sensitive_path_false(self, classifier, tmp_path):
        """Should return False for non-sensitive paths."""
        path = tmp_path / "src" / "file.py"
        assert classifier._is_sensitive_path(path) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
