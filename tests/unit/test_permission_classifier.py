#!/usr/bin/env python3
"""
Unit tests for permission_classifier.py

Tests permission classification logic for intelligent batching.

Date: 2025-11-11
Issue: GitHub #60 (Permission Batching System)
"""

import pytest
from pathlib import Path

from plugins.autonomous_dev.lib.permission_classifier import (
    PermissionClassifier,
    PermissionLevel
)


@pytest.fixture
def classifier():
    """Create permission classifier with test project root"""
    test_root = Path("/tmp/test_project")
    return PermissionClassifier(project_root=test_root)


class TestReadOperations:
    """Test Read operation classification"""

    def test_read_src_file_is_safe(self, classifier):
        """Read from src/ should be SAFE"""
        level = classifier.classify("Read", {
            "file_path": "/tmp/test_project/src/main.py"
        })
        assert level == PermissionLevel.SAFE

    def test_read_tests_file_is_safe(self, classifier):
        """Read from tests/ should be SAFE"""
        level = classifier.classify("Read", {
            "file_path": "/tmp/test_project/tests/test_main.py"
        })
        assert level == PermissionLevel.SAFE

    def test_read_docs_file_is_safe(self, classifier):
        """Read from docs/ should be SAFE"""
        level = classifier.classify("Read", {
            "file_path": "/tmp/test_project/docs/README.md"
        })
        assert level == PermissionLevel.SAFE

    def test_read_config_file_is_sensitive(self, classifier):
        """Read from .env should be SENSITIVE"""
        level = classifier.classify("Read", {
            "file_path": "/tmp/test_project/.env"
        })
        assert level == PermissionLevel.SENSITIVE

    def test_read_outside_project_is_sensitive(self, classifier):
        """Read outside project should be SENSITIVE"""
        level = classifier.classify("Read", {
            "file_path": "/etc/passwd"
        })
        assert level == PermissionLevel.SENSITIVE


class TestWriteOperations:
    """Test Write operation classification"""

    def test_write_src_file_is_boundary(self, classifier):
        """Write to src/ should be BOUNDARY"""
        level = classifier.classify("Write", {
            "file_path": "/tmp/test_project/src/new.py"
        })
        assert level == PermissionLevel.BOUNDARY

    def test_write_tests_file_is_boundary(self, classifier):
        """Write to tests/ should be BOUNDARY"""
        level = classifier.classify("Write", {
            "file_path": "/tmp/test_project/tests/test_new.py"
        })
        assert level == PermissionLevel.BOUNDARY

    def test_write_docs_file_is_boundary(self, classifier):
        """Write to docs/ should be BOUNDARY"""
        level = classifier.classify("Write", {
            "file_path": "/tmp/test_project/docs/guide.md"
        })
        assert level == PermissionLevel.BOUNDARY

    def test_write_config_file_is_sensitive(self, classifier):
        """Write to .env should be SENSITIVE"""
        level = classifier.classify("Write", {
            "file_path": "/tmp/test_project/.env"
        })
        assert level == PermissionLevel.SENSITIVE

    def test_write_outside_project_is_sensitive(self, classifier):
        """Write outside project should be SENSITIVE"""
        level = classifier.classify("Write", {
            "file_path": "/etc/config"
        })
        assert level == PermissionLevel.SENSITIVE


class TestEditOperations:
    """Test Edit operation classification"""

    def test_edit_src_file_is_boundary(self, classifier):
        """Edit in src/ should be BOUNDARY (same as Write)"""
        level = classifier.classify("Edit", {
            "file_path": "/tmp/test_project/src/main.py"
        })
        assert level == PermissionLevel.BOUNDARY


class TestBashOperations:
    """Test Bash operation classification"""

    def test_bash_ls_is_safe(self, classifier):
        """Bash 'ls' command should be SAFE"""
        level = classifier.classify("Bash", {
            "command": "ls -la"
        })
        assert level == PermissionLevel.SAFE

    def test_bash_cat_is_safe(self, classifier):
        """Bash 'cat' command should be SAFE"""
        level = classifier.classify("Bash", {
            "command": "cat file.txt"
        })
        assert level == PermissionLevel.SAFE

    def test_bash_echo_is_safe(self, classifier):
        """Bash 'echo' command should be SAFE"""
        level = classifier.classify("Bash", {
            "command": "echo 'hello'"
        })
        assert level == PermissionLevel.SAFE

    def test_bash_rm_is_sensitive(self, classifier):
        """Bash 'rm' command should be SENSITIVE"""
        level = classifier.classify("Bash", {
            "command": "rm -rf /"
        })
        assert level == PermissionLevel.SENSITIVE

    def test_bash_git_is_sensitive(self, classifier):
        """Bash 'git' command should be SENSITIVE"""
        level = classifier.classify("Bash", {
            "command": "git commit -m 'test'"
        })
        assert level == PermissionLevel.SENSITIVE


class TestSearchOperations:
    """Test Grep/Glob operation classification"""

    def test_grep_is_always_safe(self, classifier):
        """Grep operations should always be SAFE"""
        level = classifier.classify("Grep", {
            "pattern": "test",
            "path": "/tmp/test_project"
        })
        assert level == PermissionLevel.SAFE

    def test_glob_is_always_safe(self, classifier):
        """Glob operations should always be SAFE"""
        level = classifier.classify("Glob", {
            "pattern": "**/*.py"
        })
        assert level == PermissionLevel.SAFE


class TestUnknownOperations:
    """Test unknown tool classification"""

    def test_unknown_tool_is_sensitive(self, classifier):
        """Unknown tools should be SENSITIVE (conservative)"""
        level = classifier.classify("UnknownTool", {
            "param": "value"
        })
        assert level == PermissionLevel.SENSITIVE


class TestSensitivePathDetection:
    """Test sensitive path detection"""

    def test_dotenv_file_is_sensitive(self, classifier):
        """/.env file should be SENSITIVE"""
        level = classifier.classify("Read", {
            "file_path": "/tmp/test_project/.env"
        })
        assert level == PermissionLevel.SENSITIVE

    def test_settings_file_is_sensitive(self, classifier):
        """/.claude/settings.local.json should be SENSITIVE"""
        level = classifier.classify("Read", {
            "file_path": "/tmp/test_project/.claude/settings.local.json"
        })
        assert level == PermissionLevel.SENSITIVE

    def test_git_directory_is_sensitive(self, classifier):
        """/.git/ directory should be SENSITIVE"""
        level = classifier.classify("Write", {
            "file_path": "/tmp/test_project/.git/config"
        })
        assert level == PermissionLevel.SENSITIVE

    def test_system_etc_is_sensitive(self, classifier):
        """/etc/ directory should be SENSITIVE"""
        level = classifier.classify("Read", {
            "file_path": "/etc/passwd"
        })
        assert level == PermissionLevel.SENSITIVE

    def test_system_bin_is_sensitive(self, classifier):
        """/bin/ directory should be SENSITIVE"""
        level = classifier.classify("Write", {
            "file_path": "/bin/sh"
        })
        assert level == PermissionLevel.SENSITIVE
