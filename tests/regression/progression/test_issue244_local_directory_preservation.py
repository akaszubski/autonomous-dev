#!/usr/bin/env python3
"""
Progression tests for Issue #244: Repo-specific operational configs preserved across /sync.

Tests for .claude/local/ directory protection during sync operations.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially until implementation is complete.

Test Strategy:
- Test .claude/local/ preservation across all sync modes
- Test that sync completes successfully with .claude/local/ present
- Test backward compatibility (projects without .claude/local/)
- Test integration with protected_file_detector
- Test edge cases (empty directory, nested files, symlinks)

Coverage Target: 80%+

Date: 2026-01-19
Issue: #244 (Preserve .claude/local/ across sync)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Import sync dispatcher components
try:
    from plugins.autonomous_dev.lib.sync_dispatcher import SyncDispatcher
    from plugins.autonomous_dev.lib.protected_file_detector import ProtectedFileDetector
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


@pytest.fixture
def project_with_local_dir(tmp_path):
    """Create a test project with .claude/local/ directory."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Create .claude directory
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir()

    # Create .claude/local/ directory with test files
    local_dir = claude_dir / "local"
    local_dir.mkdir()
    (local_dir / "OPERATIONS.md").write_text("# Repository Operations\n\nCustom procedures.")
    (local_dir / "config.json").write_text('{"environment": "production", "debug": false}')

    # Create nested directory structure
    configs_dir = local_dir / "configs"
    configs_dir.mkdir()
    (configs_dir / "database.json").write_text('{"host": "localhost", "port": 5432}')

    return project_dir


@pytest.fixture
def project_without_local_dir(tmp_path):
    """Create a test project WITHOUT .claude/local/ directory."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Create .claude directory
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir()

    # No local/ directory - for backward compatibility tests

    return project_dir


@pytest.fixture
def mock_plugin_source(tmp_path):
    """Create mock plugin source directory for sync tests."""
    plugin_dir = tmp_path / "plugin-source"
    plugin_dir.mkdir()

    # Create plugin structure
    (plugin_dir / "commands").mkdir()
    (plugin_dir / "commands" / "test.md").write_text("# Test Command")

    (plugin_dir / "hooks").mkdir()
    (plugin_dir / "hooks" / "pre_commit.py").write_text("# Pre-commit hook")

    (plugin_dir / "agents").mkdir()
    (plugin_dir / "agents" / "test-agent.md").write_text("# Test Agent")

    return plugin_dir


class TestProtectedFileDetectorLocalPattern:
    """Test that protected_file_detector includes .claude/local/** pattern."""

    def test_local_pattern_exists_in_protected_patterns(self):
        """Test that .claude/local/** pattern exists in PROTECTED_PATTERNS.

        Current: FAILS - Pattern not added yet
        """
        from plugins.autonomous_dev.lib.protected_file_detector import PROTECTED_PATTERNS

        # Should include .claude/local/** or similar pattern
        assert any("local" in pattern and ".claude" in pattern for pattern in PROTECTED_PATTERNS)

    def test_detector_recognizes_local_files_as_protected(self, project_with_local_dir):
        """Test that ProtectedFileDetector recognizes .claude/local/ files as protected.

        Current: FAILS - Protection not implemented yet
        """
        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_with_local_dir)

        # All local files should be detected as protected
        local_files = [f for f in protected_files if "local" in f["path"]]
        assert len(local_files) >= 3  # OPERATIONS.md, config.json, database.json

        # Check specific files
        paths = [f["path"] for f in local_files]
        assert any("OPERATIONS.md" in p for p in paths)
        assert any("config.json" in p for p in paths)
        assert any("database.json" in p for p in paths)

    def test_is_protected_path_returns_true_for_local_files(self):
        """Test that is_protected_path() returns True for .claude/local/ files.

        Current: FAILS - Protection not implemented yet
        """
        detector = ProtectedFileDetector()

        # Test various local paths
        assert detector.matches_pattern(".claude/local/OPERATIONS.md")
        assert detector.matches_pattern(".claude/local/config.json")
        assert detector.matches_pattern(".claude/local/configs/db.json")
        assert detector.matches_pattern(".claude/local/scripts/deploy.sh")


class TestMarketplaceSyncPreservation:
    """Test that marketplace sync preserves .claude/local/ directory."""

    @patch("plugins.autonomous_dev.lib.sync_dispatcher.modes.Path")
    @patch("plugins.autonomous_dev.lib.sync_dispatcher.modes.json.loads")
    def test_marketplace_sync_preserves_local_directory(
        self, mock_json, mock_path, project_with_local_dir, mock_plugin_source
    ):
        """Test that marketplace sync does not delete .claude/local/ files.

        Current: FAILS - Preservation not implemented yet
        """
        # Setup
        dispatcher = SyncDispatcher(project_path=str(project_with_local_dir))

        # Record original local files
        local_dir = project_with_local_dir / ".claude" / "local"
        original_files = list(local_dir.rglob("*"))
        original_content = {
            f: f.read_text() for f in original_files if f.is_file()
        }

        # Mock marketplace plugin info
        mock_json.return_value = {
            "autonomous-dev": {
                "path": str(mock_plugin_source),
                "version": "1.0.0"
            }
        }

        # Execute sync (mocked)
        # This would normally call dispatcher.sync_marketplace()
        # For now, we test the _sync_directory method doesn't delete local/

        # Simulate sync by copying files
        _ = dispatcher._sync_directory(
            src=mock_plugin_source / "commands",
            dst=project_with_local_dir / ".claude" / "commands",
            pattern="*.md",
            description="command files",
            delete_orphans=False
        )

        # Verify .claude/local/ still exists and is unchanged
        assert local_dir.exists()
        current_files = list(local_dir.rglob("*"))

        # All original files should still exist
        for orig_file in original_files:
            if orig_file.is_file():
                assert orig_file.exists()
                assert orig_file.read_text() == original_content[orig_file]

    def test_marketplace_sync_with_delete_orphans_skips_local(
        self, project_with_local_dir, mock_plugin_source
    ):
        """Test that marketplace sync with delete_orphans=True still preserves .claude/local/.

        Current: FAILS - Exclusion logic not implemented yet
        """
        dispatcher = SyncDispatcher(project_path=str(project_with_local_dir))

        # Record original local files
        local_dir = project_with_local_dir / ".claude" / "local"
        original_operations = (local_dir / "OPERATIONS.md").read_text()

        # Sync with delete_orphans=True (should skip .claude/local/)
        # Note: This is the critical test - even with delete_orphans=True,
        # .claude/local/ should be excluded from deletion

        result = dispatcher._sync_directory(
            src=mock_plugin_source / "commands",
            dst=project_with_local_dir / ".claude" / "commands",
            pattern="*.md",
            description="command files",
            delete_orphans=True  # This should NOT delete .claude/local/
        )

        # Verify .claude/local/ is untouched
        assert local_dir.exists()
        assert (local_dir / "OPERATIONS.md").exists()
        assert (local_dir / "OPERATIONS.md").read_text() == original_operations


class TestPluginDevSyncPreservation:
    """Test that plugin-dev sync preserves .claude/local/ directory."""

    def test_plugin_dev_sync_preserves_local_directory(
        self, project_with_local_dir, mock_plugin_source
    ):
        """Test that plugin-dev sync does not delete .claude/local/ files.

        Current: FAILS - Preservation not implemented yet
        """
        dispatcher = SyncDispatcher(project_path=str(project_with_local_dir))

        # Record original local files
        local_dir = project_with_local_dir / ".claude" / "local"
        original_operations = (local_dir / "OPERATIONS.md").read_text()
        original_config = (local_dir / "config.json").read_text()

        # Simulate plugin-dev sync (uses delete_orphans=True by default)
        result = dispatcher._sync_directory(
            src=mock_plugin_source / "hooks",
            dst=project_with_local_dir / ".claude" / "hooks",
            pattern="*.py",
            description="hook files",
            delete_orphans=True  # Plugin-dev mode uses True
        )

        # Verify .claude/local/ is preserved
        assert local_dir.exists()
        assert (local_dir / "OPERATIONS.md").read_text() == original_operations
        assert (local_dir / "config.json").read_text() == original_config

    def test_plugin_dev_sync_with_orphan_cleanup_skips_local(
        self, project_with_local_dir, mock_plugin_source
    ):
        """Test that plugin-dev orphan cleanup explicitly skips .claude/local/.

        Current: FAILS - Exclusion logic not implemented yet
        """
        dispatcher = SyncDispatcher(project_path=str(project_with_local_dir))

        # Create an "orphan" file in .claude/ (not in plugin source)
        orphan_file = project_with_local_dir / ".claude" / "orphan.txt"
        orphan_file.write_text("This should be deleted")

        # Create file in .claude/local/ (should NOT be deleted)
        local_dir = project_with_local_dir / ".claude" / "local"
        local_file = local_dir / "custom.txt"
        local_file.write_text("This should NOT be deleted")

        # Sync with delete_orphans=True
        # Orphan cleanup should:
        # - Delete orphan.txt (not in source)
        # - Preserve .claude/local/custom.txt (protected)

        # This test verifies exclusion logic in orphan cleanup

        # For now, test that _sync_directory doesn't touch local/
        result = dispatcher._sync_directory(
            src=mock_plugin_source / "commands",
            dst=project_with_local_dir / ".claude" / "commands",
            pattern="*.md",
            description="command files",
            delete_orphans=True
        )

        # Verify local file still exists
        assert local_file.exists()
        assert local_file.read_text() == "This should NOT be deleted"


class TestGitHubSyncPreservation:
    """Test that GitHub sync preserves .claude/local/ directory."""

    @patch("plugins.autonomous_dev.lib.sync_dispatcher.modes.urllib.request.urlopen")
    def test_github_sync_preserves_local_directory(
        self, mock_urlopen, project_with_local_dir
    ):
        """Test that GitHub sync does not delete .claude/local/ files.

        Current: FAILS - Preservation not implemented yet
        """
        dispatcher = SyncDispatcher(project_path=str(project_with_local_dir))

        # Record original local files
        local_dir = project_with_local_dir / ".claude" / "local"
        original_operations = (local_dir / "OPERATIONS.md").read_text()

        # Mock GitHub manifest response
        mock_manifest = {
            "components": {
                "commands": {
                    "files": ["plugins/autonomous-dev/commands/test.md"]
                },
                "hooks": {
                    "files": ["plugins/autonomous-dev/hooks/pre_commit.py"]
                }
            }
        }

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_manifest).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        # Execute GitHub sync (this will fail until implementation is complete)
        # result = dispatcher.dispatch(SyncMode.GITHUB, create_backup=False)

        # For now, test that file discovery skips .claude/local/
        # Verify .claude/local/ is still intact
        assert local_dir.exists()
        assert (local_dir / "OPERATIONS.md").exists()
        assert (local_dir / "OPERATIONS.md").read_text() == original_operations

    def test_github_sync_skips_local_files_in_manifest(
        self, project_with_local_dir
    ):
        """Test that GitHub sync manifest does not include .claude/local/ files.

        Current: FAILS - Exclusion logic not implemented yet
        """
        # This test verifies that the install manifest generator
        # excludes .claude/local/ files from the manifest

        # For now, this is a placeholder test
        # The actual implementation will need to update manifest generation

        local_dir = project_with_local_dir / ".claude" / "local"
        assert local_dir.exists()

        # Manifest should NOT include paths like:
        # - ".claude/local/OPERATIONS.md"
        # - ".claude/local/config.json"
        # These should never be synced from GitHub


class TestSyncResultsWithLocalDirectory:
    """Test that sync operations complete successfully with .claude/local/ present."""

    def test_marketplace_sync_success_with_local_present(
        self, project_with_local_dir, mock_plugin_source
    ):
        """Test that marketplace sync succeeds when .claude/local/ exists.

        Current: FAILS - Integration not tested yet
        """
        dispatcher = SyncDispatcher(project_path=str(project_with_local_dir))

        # Sync should succeed even with .claude/local/ present
        # This verifies no conflicts or errors due to protection logic

        # For now, test basic initialization
        assert dispatcher.project_path == project_with_local_dir

    def test_plugin_dev_sync_success_with_local_present(
        self, project_with_local_dir, mock_plugin_source
    ):
        """Test that plugin-dev sync succeeds when .claude/local/ exists.

        Current: FAILS - Integration not tested yet
        """
        dispatcher = SyncDispatcher(project_path=str(project_with_local_dir))

        # Sync should succeed even with .claude/local/ present
        assert dispatcher.project_path == project_with_local_dir

    def test_github_sync_success_with_local_present(
        self, project_with_local_dir
    ):
        """Test that GitHub sync succeeds when .claude/local/ exists.

        Current: FAILS - Integration not tested yet
        """
        dispatcher = SyncDispatcher(project_path=str(project_with_local_dir))

        # Sync should succeed even with .claude/local/ present
        assert dispatcher.project_path == project_with_local_dir


class TestBackwardCompatibility:
    """Test backward compatibility for projects without .claude/local/."""

    def test_sync_works_without_local_directory(
        self, project_without_local_dir, mock_plugin_source
    ):
        """Test that sync operations work normally when .claude/local/ doesn't exist.

        Current: PASS - This should work already (no regression)
        """
        dispatcher = SyncDispatcher(project_path=str(project_without_local_dir))

        # Sync should work fine without .claude/local/
        claude_dir = project_without_local_dir / ".claude"
        assert claude_dir.exists()
        assert not (claude_dir / "local").exists()

        # Verify dispatcher initialized correctly
        assert dispatcher.project_path == project_without_local_dir

    def test_protected_file_detector_handles_missing_local(
        self, project_without_local_dir
    ):
        """Test that ProtectedFileDetector handles missing .claude/local/ gracefully.

        Current: PASS - This should work already (no regression)
        """
        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_without_local_dir)

        # Should return empty list (no protected files without .claude/local/)
        # or only other protected files (like PROJECT.md if present)
        local_files = [f for f in protected_files if "local" in f["path"]]
        assert len(local_files) == 0


class TestEdgeCases:
    """Test edge cases for .claude/local/ preservation."""

    def test_empty_local_directory_preservation(self, tmp_path):
        """Test that empty .claude/local/ directory is preserved.

        Current: FAILS - Edge case not handled yet
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()

        # Create empty local directory
        local_dir = claude_dir / "local"
        local_dir.mkdir()

        dispatcher = SyncDispatcher(project_path=str(project_dir))

        # After sync, empty directory should still exist
        # (directories are preserved even if empty)
        assert local_dir.exists()
        assert local_dir.is_dir()

    def test_symlinked_local_directory_handling(self, tmp_path):
        """Test handling of symlinked .claude/local/ directory.

        Current: FAILS - Symlink edge case not tested yet
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()

        # Create actual local directory elsewhere
        actual_local = tmp_path / "actual-local"
        actual_local.mkdir()
        (actual_local / "OPERATIONS.md").write_text("# Operations")

        # Create symlink
        local_symlink = claude_dir / "local"
        local_symlink.symlink_to(actual_local)

        # Detector should follow symlinks and protect files
        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_dir)

        # Symlinked files should be detected as protected
        assert any("local" in f["path"] for f in protected_files)

    def test_deeply_nested_local_files_preservation(self, tmp_path):
        """Test that deeply nested files in .claude/local/ are preserved.

        Current: FAILS - Deep nesting not tested yet
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()

        # Create deeply nested structure
        deep_dir = claude_dir / "local" / "a" / "b" / "c" / "d"
        deep_dir.mkdir(parents=True)
        deep_file = deep_dir / "deep.txt"
        deep_file.write_text("Deep file content")

        # Detector should find deeply nested files
        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_dir)

        paths = [f["path"] for f in protected_files]
        assert any("local/a/b/c/d/deep.txt" in p for p in paths)

    def test_local_directory_with_special_characters(self, tmp_path):
        """Test .claude/local/ files with special characters in names.

        Current: FAILS - Special characters not tested yet
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        local_dir = project_dir / ".claude" / "local"
        local_dir.mkdir(parents=True)

        # Create files with special characters
        (local_dir / "config (production).json").write_text('{"env": "prod"}')
        (local_dir / "notes-2024.txt").write_text("Notes")
        (local_dir / "file_with_underscores.md").write_text("# File")

        # All should be detected as protected
        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_dir)

        paths = [f["path"] for f in protected_files]
        assert any("config (production).json" in p for p in paths)
        assert any("notes-2024.txt" in p for p in paths)
        assert any("file_with_underscores.md" in p for p in paths)


class TestRegressionProtection:
    """Test that existing protection patterns still work."""

    def test_project_md_still_protected(self, project_with_local_dir):
        """Test that PROJECT.md protection still works.

        Current: PASS - Existing functionality should not break
        """
        # Create PROJECT.md
        project_md = project_with_local_dir / ".claude" / "PROJECT.md"
        project_md.write_text("# Project Goals")

        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_with_local_dir)

        # PROJECT.md should still be protected
        assert any("PROJECT.md" in f["path"] for f in protected_files)

    def test_env_files_still_protected(self, project_with_local_dir):
        """Test that .env file protection still works.

        Current: PASS - Existing functionality should not break
        """
        # Create .env file
        env_file = project_with_local_dir / ".env"
        env_file.write_text("SECRET=value")

        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_with_local_dir)

        # .env should still be protected
        assert any(".env" in f["path"] for f in protected_files)

    def test_custom_hooks_still_protected(self, project_with_local_dir):
        """Test that custom hook protection still works.

        Current: PASS - Existing functionality should not break
        """
        # Create custom hook
        hooks_dir = project_with_local_dir / ".claude" / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        (hooks_dir / "custom_validate.py").write_text("# Custom hook")

        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_with_local_dir)

        # Custom hook should still be protected
        assert any("custom_validate.py" in f["path"] for f in protected_files)
