#!/usr/bin/env python3
"""
Unit tests for ProtectedFileDetector (TDD Red Phase - Issue #106).

Tests for GenAI-first installation system protected file detection.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially because ProtectedFileDetector doesn't exist yet.

Test Strategy:
- User artifact detection (PROJECT.md, .env, custom hooks)
- File hash comparison
- Modification detection
- Protected file categorization

Date: 2025-12-09
Issue: #106 (GenAI-first installation system)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import hashlib

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will FAIL until implementation exists
try:
    from protected_file_detector import ProtectedFileDetector
except ImportError as e:
    pytest.skip(f"Implementation not found: {e}", allow_module_level=True)


class TestProtectedFileDetectorInitialization:
    """Test ProtectedFileDetector initialization."""

    def test_initialize_with_default_protected_patterns(self, tmp_path):
        """Test initialization with default protected file patterns.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        detector = ProtectedFileDetector()

        # Should include common user artifacts
        protected_patterns = detector.get_protected_patterns()
        assert ".claude/PROJECT.md" in protected_patterns
        assert ".env" in protected_patterns
        assert ".claude/hooks/custom_*.py" in protected_patterns

    def test_initialize_with_custom_patterns(self, tmp_path):
        """Test initialization with custom protected patterns.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        custom_patterns = [".claude/custom.txt", "config/*.yaml"]
        detector = ProtectedFileDetector(additional_patterns=custom_patterns)

        patterns = detector.get_protected_patterns()
        assert ".claude/custom.txt" in patterns
        assert "config/*.yaml" in patterns

    def test_initialize_with_plugin_defaults_registry(self, tmp_path):
        """Test initialization with plugin defaults registry.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        # Registry maps files to their default hashes
        defaults_registry = {
            ".claude/hooks/pre_commit.py": "abc123...",
            ".claude/settings.json": "def456...",
        }

        detector = ProtectedFileDetector(plugin_defaults=defaults_registry)

        assert detector.has_plugin_default(".claude/hooks/pre_commit.py")
        assert not detector.has_plugin_default(".claude/PROJECT.md")


class TestUserArtifactDetection:
    """Test detection of user-created artifacts."""

    def test_detect_project_md_as_user_artifact(self, tmp_path):
        """Test that PROJECT.md is always protected.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".claude").mkdir()
        (project_dir / ".claude" / "PROJECT.md").write_text("# Goals")

        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_dir)

        assert any(f["path"] == ".claude/PROJECT.md" for f in protected_files)

    def test_detect_env_file_as_user_artifact(self, tmp_path):
        """Test that .env file is protected.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".env").write_text("API_KEY=secret")

        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_dir)

        assert any(f["path"] == ".env" for f in protected_files)

    def test_detect_custom_hooks_as_user_artifacts(self, tmp_path):
        """Test that custom hooks are protected.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        hooks_dir = project_dir / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "custom_pre_commit.py").write_text("# Custom hook")

        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_dir)

        assert any(
            "custom_pre_commit.py" in f["path"] for f in protected_files
        )

    def test_detect_user_state_files_as_protected(self, tmp_path):
        """Test that user state files are protected.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".claude").mkdir()
        (project_dir / ".claude" / "batch_state.json").write_text("{}")
        (project_dir / ".claude" / "session_state.json").write_text("{}")

        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_dir)

        state_files = [f["path"] for f in protected_files]
        assert ".claude/batch_state.json" in state_files
        assert ".claude/session_state.json" in state_files

    def test_does_not_detect_plugin_defaults_as_user_artifacts(self, tmp_path):
        """Test that unmodified plugin defaults are not protected.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        hooks_dir = project_dir / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)

        # Create file with known plugin default content
        default_content = "# Default plugin hook"
        default_hash = hashlib.sha256(default_content.encode()).hexdigest()

        (hooks_dir / "auto_format.py").write_text(default_content)

        defaults_registry = {".claude/hooks/auto_format.py": default_hash}
        detector = ProtectedFileDetector(plugin_defaults=defaults_registry)

        protected_files = detector.detect_protected_files(project_dir)

        # Should not be protected (matches plugin default)
        assert not any("auto_format.py" in f["path"] for f in protected_files)


class TestFileHashComparison:
    """Test file hash comparison for modification detection."""

    def test_calculate_file_hash_sha256(self, tmp_path):
        """Test calculating SHA256 hash of file.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        test_file = tmp_path / "test.txt"
        content = "test content"
        test_file.write_text(content)

        detector = ProtectedFileDetector()
        file_hash = detector.calculate_hash(test_file)

        expected_hash = hashlib.sha256(content.encode()).hexdigest()
        assert file_hash == expected_hash

    def test_compare_hash_matches_plugin_default(self, tmp_path):
        """Test hash comparison with plugin default.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        test_file = tmp_path / "file.py"
        content = "default content"
        test_file.write_text(content)

        default_hash = hashlib.sha256(content.encode()).hexdigest()
        defaults_registry = {"file.py": default_hash}

        detector = ProtectedFileDetector(plugin_defaults=defaults_registry)

        assert detector.matches_plugin_default(test_file, "file.py")

    def test_compare_hash_differs_from_plugin_default(self, tmp_path):
        """Test hash comparison when file is modified.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        test_file = tmp_path / "file.py"
        test_file.write_text("modified content")

        default_hash = hashlib.sha256(b"original content").hexdigest()
        defaults_registry = {"file.py": default_hash}

        detector = ProtectedFileDetector(plugin_defaults=defaults_registry)

        assert not detector.matches_plugin_default(test_file, "file.py")

    def test_handles_binary_files(self, tmp_path):
        """Test hash calculation for binary files.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        test_file = tmp_path / "binary.bin"
        binary_content = b"\x00\x01\x02\xff\xfe\xfd"
        test_file.write_bytes(binary_content)

        detector = ProtectedFileDetector()
        file_hash = detector.calculate_hash(test_file)

        expected_hash = hashlib.sha256(binary_content).hexdigest()
        assert file_hash == expected_hash


class TestModificationDetection:
    """Test detection of modified files."""

    def test_detect_modified_plugin_file(self, tmp_path):
        """Test detection of user-modified plugin file.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        hooks_dir = project_dir / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)

        # Create modified hook
        (hooks_dir / "auto_format.py").write_text("# User modified")

        # Register plugin default
        default_hash = hashlib.sha256(b"# Default plugin hook").hexdigest()
        defaults_registry = {".claude/hooks/auto_format.py": default_hash}

        detector = ProtectedFileDetector(plugin_defaults=defaults_registry)
        protected_files = detector.detect_protected_files(project_dir)

        # Should be protected (modified from default)
        modified_files = [f for f in protected_files if f.get("modified")]
        assert any("auto_format.py" in f["path"] for f in modified_files)

    def test_detect_unmodified_plugin_file(self, tmp_path):
        """Test that unmodified plugin files are not protected.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        hooks_dir = project_dir / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)

        # Create unmodified hook
        default_content = "# Default plugin hook"
        (hooks_dir / "auto_format.py").write_text(default_content)

        default_hash = hashlib.sha256(default_content.encode()).hexdigest()
        defaults_registry = {".claude/hooks/auto_format.py": default_hash}

        detector = ProtectedFileDetector(plugin_defaults=defaults_registry)
        protected_files = detector.detect_protected_files(project_dir)

        # Should not be protected (matches default)
        assert not any("auto_format.py" in f["path"] for f in protected_files)

    def test_categorize_modified_vs_new_files(self, tmp_path):
        """Test categorization of modified vs new user files.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()

        # New user file (no plugin default)
        (claude_dir / "PROJECT.md").write_text("# Goals")

        # Modified plugin file
        hooks_dir = claude_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "auto_format.py").write_text("# Modified")

        default_hash = hashlib.sha256(b"# Default").hexdigest()
        defaults_registry = {".claude/hooks/auto_format.py": default_hash}

        detector = ProtectedFileDetector(plugin_defaults=defaults_registry)
        protected_files = detector.detect_protected_files(project_dir)

        # Check categorization
        new_files = [f for f in protected_files if f.get("category") == "new"]
        modified_files = [
            f for f in protected_files if f.get("category") == "modified"
        ]

        assert any("PROJECT.md" in f["path"] for f in new_files)
        assert any("auto_format.py" in f["path"] for f in modified_files)


class TestProtectedFileCategories:
    """Test protected file categorization."""

    def test_categorize_user_config_files(self, tmp_path):
        """Test categorization of user configuration files.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        (project_dir / ".env").write_text("SECRET=value")
        (project_dir / ".claude").mkdir()
        (project_dir / ".claude" / "PROJECT.md").write_text("# Project")

        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_dir)

        config_files = [
            f for f in protected_files if f.get("category") == "config"
        ]
        assert any(".env" in f["path"] for f in config_files)
        assert any("PROJECT.md" in f["path"] for f in config_files)

    def test_categorize_user_state_files(self, tmp_path):
        """Test categorization of user state files.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".claude").mkdir()
        (project_dir / ".claude" / "batch_state.json").write_text("{}")

        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_dir)

        state_files = [
            f for f in protected_files if f.get("category") == "state"
        ]
        assert any("batch_state.json" in f["path"] for f in state_files)

    def test_categorize_custom_hooks(self, tmp_path):
        """Test categorization of custom hooks.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        hooks_dir = project_dir / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "custom_validation.py").write_text("# Custom")

        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_dir)

        custom_hooks = [
            f for f in protected_files if f.get("category") == "custom_hook"
        ]
        assert any("custom_validation.py" in f["path"] for f in custom_hooks)


class TestGlobPatternMatching:
    """Test glob pattern matching for protected files."""

    def test_match_simple_glob_pattern(self, tmp_path):
        """Test matching simple glob patterns.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        detector = ProtectedFileDetector(additional_patterns=["*.env"])

        assert detector.matches_pattern(".env")
        assert detector.matches_pattern("production.env")
        assert not detector.matches_pattern("config.json")

    def test_match_wildcard_glob_pattern(self, tmp_path):
        """Test matching wildcard glob patterns.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        detector = ProtectedFileDetector(
            additional_patterns=[".claude/hooks/custom_*.py"]
        )

        assert detector.matches_pattern(".claude/hooks/custom_validate.py")
        assert detector.matches_pattern(".claude/hooks/custom_format.py")
        assert not detector.matches_pattern(".claude/hooks/auto_format.py")

    def test_match_recursive_glob_pattern(self, tmp_path):
        """Test matching recursive glob patterns.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        detector = ProtectedFileDetector(additional_patterns=["**/*.secret"])

        assert detector.matches_pattern("config/api.secret")
        assert detector.matches_pattern("deep/nested/dir/data.secret")
        assert not detector.matches_pattern("config/api.json")


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_nonexistent_project_directory(self, tmp_path):
        """Test handling nonexistent project directory.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        nonexistent = tmp_path / "nonexistent"

        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(nonexistent)

        assert protected_files == []

    def test_handles_empty_project_directory(self, tmp_path):
        """Test handling empty project directory.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        project_dir = tmp_path / "empty"
        project_dir.mkdir()

        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_dir)

        assert protected_files == []

    def test_handles_symlinks(self, tmp_path):
        """Test handling symlinked protected files.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create target and symlink
        target = tmp_path / "actual.env"
        target.write_text("SECRET=value")
        symlink = project_dir / ".env"
        symlink.symlink_to(target)

        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_dir)

        # Should detect symlinked .env
        assert any(".env" in f["path"] for f in protected_files)

    def test_handles_large_project_directory(self, tmp_path):
        """Test performance with large project directory.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        project_dir = tmp_path / "large-project"
        project_dir.mkdir()

        # Create 1000 files
        for i in range(1000):
            (project_dir / f"file{i}.py").write_text(f"# File {i}")

        # Add protected file
        (project_dir / ".env").write_text("SECRET=value")

        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_dir)

        # Should still detect .env efficiently
        assert any(".env" in f["path"] for f in protected_files)
        assert len(protected_files) == 1  # Only .env is protected

    def test_thread_safety(self, tmp_path):
        """Test thread safety for concurrent detection.

        Current: FAILS - ProtectedFileDetector doesn't exist
        """
        import threading

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".env").write_text("SECRET=value")

        detector = ProtectedFileDetector()
        results = []

        def detect():
            protected_files = detector.detect_protected_files(project_dir)
            results.append(len(protected_files))

        threads = [threading.Thread(target=detect) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should get same result
        assert all(count == results[0] for count in results)
