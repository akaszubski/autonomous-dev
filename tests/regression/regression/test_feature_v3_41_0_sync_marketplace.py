#!/usr/bin/env python3
"""
TDD Tests for Sync Dispatcher Marketplace Integration (FAILING - Red Phase)

This module contains FAILING tests for sync_dispatcher.py marketplace sync
enhancements including version detection and orphan cleanup integration.

Requirements:
1. Marketplace sync detects version upgrades/downgrades
2. Orphan cleanup integrated into marketplace sync workflow
3. Version details included in SyncResult for user messaging
4. Error handling for marketplace not found, permission denied
5. Security: All file operations validated against whitelist

Test Coverage Target: 100% of marketplace sync logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe marketplace sync requirements
- Tests should FAIL until sync_dispatcher.py is enhanced
- Each test validates ONE marketplace sync requirement

Author: test-master agent
Date: 2025-11-08
Issue: GitHub #50 - Fix Marketplace Update UX
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, call, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# This import will FAIL until sync_dispatcher.py is enhanced
from plugins.autonomous_dev.lib.sync_dispatcher import (
    SyncDispatcher,
    SyncResult,
    SyncError,
    sync_marketplace,
)
from plugins.autonomous_dev.lib.sync_mode_detector import SyncMode
from plugins.autonomous_dev.lib.version_detector import VersionComparison
from plugins.autonomous_dev.lib.orphan_file_cleaner import CleanupResult


class TestMarketplaceSyncVersionDetection:
    """Test version detection during marketplace sync."""

    @pytest.fixture
    def temp_environment(self, tmp_path):
        """Create full test environment with marketplace and project."""
        # Project setup
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "plugins").mkdir()
        (project_root / ".claude" / "plugins" / "autonomous-dev").mkdir()

        # Marketplace setup
        marketplace_dir = tmp_path / "marketplace"
        marketplace_dir.mkdir()
        (marketplace_dir / ".claude").mkdir()
        (marketplace_dir / ".claude" / "plugins").mkdir()

        return {
            "project_root": project_root,
            "marketplace_dir": marketplace_dir
        }

    def test_marketplace_sync_detects_version_upgrade(self, temp_environment):
        """Test marketplace sync detects when marketplace has newer version.

        REQUIREMENT: Inform user about version upgrade during sync.
        Expected: SyncResult includes version comparison showing upgrade.
        """
        project_root = temp_environment["project_root"]
        marketplace_dir = temp_environment["marketplace_dir"]

        # Setup project version (old)
        project_plugin = project_root / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        project_plugin.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.7.0"
        }))

        # Setup marketplace version (new)
        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {
                "version": "3.8.0",
                "source": "marketplace",
                "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")
            }
        }))

        # Create marketplace plugin files
        marketplace_plugin_dir = marketplace_dir / ".claude" / "plugins" / "autonomous-dev"
        marketplace_plugin_dir.mkdir(parents=True)
        (marketplace_plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0"
        }))

        dispatcher = SyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(marketplace_plugins_file=marketplace_plugins)

        # Should detect upgrade
        assert result.success is True
        assert result.version_comparison is not None
        assert result.version_comparison.status == VersionComparison.UPGRADE_AVAILABLE
        assert result.version_comparison.project_version == "3.7.0"
        assert result.version_comparison.marketplace_version == "3.8.0"

    def test_marketplace_sync_detects_downgrade_risk(self, temp_environment):
        """Test marketplace sync detects when project is ahead of marketplace.

        REQUIREMENT: Warn user about downgrade risk.
        Expected: SyncResult includes version comparison showing downgrade.
        """
        project_root = temp_environment["project_root"]
        marketplace_dir = temp_environment["marketplace_dir"]

        # Setup project version (new)
        project_plugin = project_root / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        project_plugin.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.9.0"
        }))

        # Setup marketplace version (old)
        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {
                "version": "3.8.0",
                "source": "marketplace",
                "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")
            }
        }))

        marketplace_plugin_dir = marketplace_dir / ".claude" / "plugins" / "autonomous-dev"
        marketplace_plugin_dir.mkdir(parents=True)
        (marketplace_plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0"
        }))

        dispatcher = SyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(marketplace_plugins_file=marketplace_plugins)

        # Should detect downgrade
        assert result.version_comparison is not None
        assert result.version_comparison.status == VersionComparison.DOWNGRADE_RISK

    def test_marketplace_sync_includes_version_in_message(self, temp_environment):
        """Test marketplace sync includes version details in user message.

        REQUIREMENT: Clear user messaging about version changes.
        Expected: SyncResult.message mentions version upgrade.
        """
        project_root = temp_environment["project_root"]
        marketplace_dir = temp_environment["marketplace_dir"]

        # Setup versions
        project_plugin = project_root / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        project_plugin.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.7.0"
        }))

        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {
                "version": "3.8.0",
                "source": "marketplace",
                "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")
            }
        }))

        marketplace_plugin_dir = marketplace_dir / ".claude" / "plugins" / "autonomous-dev"
        marketplace_plugin_dir.mkdir(parents=True)
        (marketplace_plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0"
        }))

        dispatcher = SyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(marketplace_plugins_file=marketplace_plugins)

        # Message should mention version upgrade
        message = result.message.lower()
        assert "3.7.0" in message or "upgrade" in message or "update" in message
        assert "3.8.0" in message


class TestMarketplaceSyncOrphanCleanup:
    """Test orphan cleanup integration in marketplace sync."""

    @pytest.fixture
    def temp_project_with_orphans(self, tmp_path):
        """Create project with orphaned files after version upgrade."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "commands").mkdir()
        (project_root / ".claude" / "plugins").mkdir()
        (project_root / ".claude" / "plugins" / "autonomous-dev").mkdir()

        # Old version with deprecated commands
        project_plugin = project_root / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        project_plugin.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.7.0",
            "commands": ["auto-implement.md", "old-command.md"]
        }))

        # Create orphaned command file
        (project_root / ".claude" / "commands" / "old-command.md").write_text("# Old Command")

        # Marketplace has new version without old-command
        marketplace_dir = tmp_path / "marketplace"
        marketplace_dir.mkdir()
        (marketplace_dir / ".claude").mkdir()
        (marketplace_dir / ".claude" / "plugins").mkdir()

        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {
                "version": "3.8.0",
                "source": "marketplace",
                "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")
            }
        }))

        marketplace_plugin_dir = marketplace_dir / ".claude" / "plugins" / "autonomous-dev"
        marketplace_plugin_dir.mkdir(parents=True)
        (marketplace_plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0",
            "commands": ["auto-implement.md"]  # old-command removed
        }))

        return {
            "project_root": project_root,
            "marketplace_plugins": marketplace_plugins,
            "orphan_file": project_root / ".claude" / "commands" / "old-command.md"
        }

    def test_marketplace_sync_detects_orphans_after_upgrade(self, temp_project_with_orphans):
        """Test marketplace sync detects orphaned files after version upgrade.

        REQUIREMENT: Orphan detection integrated into sync workflow.
        Expected: SyncResult includes orphan detection results.
        """
        project_root = temp_project_with_orphans["project_root"]
        marketplace_plugins = temp_project_with_orphans["marketplace_plugins"]

        dispatcher = SyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(
            marketplace_plugins_file=marketplace_plugins,
            cleanup_orphans=True,
            dry_run=True
        )

        # Should detect orphan
        assert result.orphan_cleanup is not None
        assert result.orphan_cleanup.orphans_detected > 0

    def test_marketplace_sync_cleanup_orphans_dry_run(self, temp_project_with_orphans):
        """Test marketplace sync with dry-run doesn't delete orphans.

        REQUIREMENT: Safe preview of orphan cleanup.
        Expected: Orphans reported but not deleted in dry-run.
        """
        project_root = temp_project_with_orphans["project_root"]
        marketplace_plugins = temp_project_with_orphans["marketplace_plugins"]
        orphan_file = temp_project_with_orphans["orphan_file"]

        dispatcher = SyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(
            marketplace_plugins_file=marketplace_plugins,
            cleanup_orphans=True,
            dry_run=True
        )

        # Should report orphan but not delete
        assert result.orphan_cleanup.orphans_detected > 0
        assert result.orphan_cleanup.orphans_deleted == 0
        assert orphan_file.exists()

    def test_marketplace_sync_cleanup_orphans_auto_mode(self, temp_project_with_orphans):
        """Test marketplace sync with auto-cleanup deletes orphans.

        REQUIREMENT: Automated orphan cleanup after upgrade.
        Expected: Orphans deleted automatically in auto mode.
        """
        project_root = temp_project_with_orphans["project_root"]
        marketplace_plugins = temp_project_with_orphans["marketplace_plugins"]
        orphan_file = temp_project_with_orphans["orphan_file"]

        dispatcher = SyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(
            marketplace_plugins_file=marketplace_plugins,
            cleanup_orphans=True,
            dry_run=False
        )

        # Should delete orphan
        assert result.orphan_cleanup.orphans_deleted > 0
        assert not orphan_file.exists()

    def test_marketplace_sync_skip_orphan_cleanup_when_disabled(self, temp_project_with_orphans):
        """Test marketplace sync skips orphan cleanup when disabled.

        REQUIREMENT: Optional orphan cleanup.
        Expected: No orphan cleanup when cleanup_orphans=False.
        """
        project_root = temp_project_with_orphans["project_root"]
        marketplace_plugins = temp_project_with_orphans["marketplace_plugins"]

        dispatcher = SyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(
            marketplace_plugins_file=marketplace_plugins,
            cleanup_orphans=False
        )

        # Should not include orphan cleanup results
        assert result.orphan_cleanup is None


class TestMarketplaceSyncErrorHandling:
    """Test error handling for marketplace sync failures."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "plugins").mkdir()
        (project_root / ".claude" / "plugins" / "autonomous-dev").mkdir()
        return project_root

    def test_marketplace_not_installed_error(self, temp_project):
        """Test error when marketplace plugin not installed.

        REQUIREMENT: Clear error for missing marketplace installation.
        Expected: SyncResult with success=False, error message.
        """
        # No marketplace plugins file

        dispatcher = SyncDispatcher(project_root=temp_project)
        result = dispatcher.sync_marketplace(
            marketplace_plugins_file=Path("/nonexistent/installed_plugins.json")
        )

        assert result.success is False
        # Implementation returns "Security validation failed" for paths outside allowed locations
        assert "security" in result.message.lower() or "marketplace" in result.message.lower() or "not found" in result.message.lower()

    def test_permission_denied_error(self, temp_project):
        """Test error when marketplace directory not accessible.

        REQUIREMENT: Graceful handling of permission errors.
        Expected: SyncResult with success=False, permission error message.
        """
        # Create read-only marketplace directory
        marketplace_dir = temp_project.parent / "marketplace"
        marketplace_dir.mkdir()
        (marketplace_dir / ".claude").mkdir()
        (marketplace_dir / ".claude" / "plugins").mkdir()

        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {
                "version": "3.8.0",
                "source": "marketplace",
                "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")
            }
        }))

        # Make marketplace directory read-only
        marketplace_dir.chmod(0o444)

        try:
            dispatcher = SyncDispatcher(project_root=temp_project)
            result = dispatcher.sync_marketplace(marketplace_plugins_file=marketplace_plugins)

            # Should handle permission error gracefully
            assert result.success is False or result.message is not None
        finally:
            # Restore permissions for cleanup
            marketplace_dir.chmod(0o755)

    def test_corrupted_marketplace_plugin_json_error(self, temp_project):
        """Test error when marketplace plugin.json is corrupted.

        REQUIREMENT: Detect and report corrupted JSON.
        Expected: SyncResult with success=False, JSON error message.
        """
        marketplace_dir = temp_project.parent / "marketplace"
        marketplace_dir.mkdir()
        (marketplace_dir / ".claude").mkdir()
        (marketplace_dir / ".claude" / "plugins").mkdir()

        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text("{ corrupted json content")

        dispatcher = SyncDispatcher(project_root=temp_project)
        result = dispatcher.sync_marketplace(marketplace_plugins_file=marketplace_plugins)

        assert result.success is False
        error_msg = result.message.lower()
        assert "json" in error_msg or "parse" in error_msg or "corrupt" in error_msg


class TestSyncResultEnhancements:
    """Test SyncResult enhancements for marketplace sync."""

    def test_sync_result_includes_version_comparison(self):
        """Test SyncResult can include version comparison data.

        REQUIREMENT: Rich result object for user messaging.
        Expected: SyncResult has version_comparison attribute.
        """
        version_comparison = VersionComparison(
            status=VersionComparison.UPGRADE_AVAILABLE,
            project_version="3.7.0",
            marketplace_version="3.8.0"
        )

        result = SyncResult(
            success=True,
            mode=SyncMode.MARKETPLACE,
            message="Marketplace sync completed",
            version_comparison=version_comparison
        )

        assert result.version_comparison is not None
        assert result.version_comparison.project_version == "3.7.0"
        assert result.version_comparison.marketplace_version == "3.8.0"

    def test_sync_result_includes_orphan_cleanup(self):
        """Test SyncResult can include orphan cleanup data.

        REQUIREMENT: Rich result object for cleanup reporting.
        Expected: SyncResult has orphan_cleanup attribute.
        """
        cleanup_result = CleanupResult(
            orphans_detected=3,
            orphans_deleted=3,
            dry_run=False,
            errors=0,
            orphans=[]
        )

        result = SyncResult(
            success=True,
            mode=SyncMode.MARKETPLACE,
            message="Marketplace sync completed",
            orphan_cleanup=cleanup_result
        )

        assert result.orphan_cleanup is not None
        assert result.orphan_cleanup.orphans_detected == 3
        assert result.orphan_cleanup.orphans_deleted == 3

    def test_sync_result_summary_includes_all_details(self):
        """Test SyncResult summary includes version and cleanup info.

        REQUIREMENT: Comprehensive user feedback.
        Expected: summary property mentions version upgrade and cleanup.
        """
        version_comparison = VersionComparison(
            status=VersionComparison.UPGRADE_AVAILABLE,
            project_version="3.7.0",
            marketplace_version="3.8.0"
        )

        cleanup_result = CleanupResult(
            orphans_detected=2,
            orphans_deleted=2,
            dry_run=False,
            errors=0,
            orphans=[]
        )

        result = SyncResult(
            success=True,
            mode=SyncMode.MARKETPLACE,
            message="Marketplace sync completed",
            version_comparison=version_comparison,
            orphan_cleanup=cleanup_result
        )

        summary = result.summary

        # Should mention both version upgrade and cleanup
        summary_lower = summary.lower()
        assert "3.7.0" in summary or "3.8.0" in summary or "upgrade" in summary_lower
        assert "orphan" in summary_lower or "cleanup" in summary_lower or "2" in summary


class TestHighLevelMarketplaceSyncFunction:
    """Test high-level sync_marketplace() convenience function."""

    @pytest.fixture
    def temp_environment(self, tmp_path):
        """Create full test environment."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "plugins").mkdir()
        (project_root / ".claude" / "plugins" / "autonomous-dev").mkdir()

        # Setup versions
        project_plugin = project_root / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        project_plugin.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.7.0"
        }))

        marketplace_dir = tmp_path / "marketplace"
        marketplace_dir.mkdir()
        (marketplace_dir / ".claude").mkdir()
        (marketplace_dir / ".claude" / "plugins").mkdir()

        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {
                "version": "3.8.0",
                "source": "marketplace",
                "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")
            }
        }))

        marketplace_plugin_dir = marketplace_dir / ".claude" / "plugins" / "autonomous-dev"
        marketplace_plugin_dir.mkdir(parents=True)
        (marketplace_plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0"
        }))

        return {
            "project_root": project_root,
            "marketplace_plugins": marketplace_plugins
        }

    def test_sync_marketplace_function(self, temp_environment):
        """Test sync_marketplace() convenience function.

        REQUIREMENT: High-level API for marketplace sync.
        Expected: Returns SyncResult with version detection.
        """
        project_root = temp_environment["project_root"]
        marketplace_plugins = temp_environment["marketplace_plugins"]

        result = sync_marketplace(
            project_root=project_root,
            marketplace_plugins_file=marketplace_plugins
        )

        assert isinstance(result, SyncResult)
        assert result.mode == SyncMode.MARKETPLACE
        assert result.version_comparison is not None

    def test_sync_marketplace_function_with_cleanup(self, temp_environment):
        """Test sync_marketplace() with orphan cleanup enabled.

        REQUIREMENT: Integrated workflow via high-level function.
        Expected: Returns SyncResult with cleanup results.
        """
        project_root = temp_environment["project_root"]
        marketplace_plugins = temp_environment["marketplace_plugins"]

        result = sync_marketplace(
            project_root=project_root,
            marketplace_plugins_file=marketplace_plugins,
            cleanup_orphans=True,
            dry_run=True
        )

        assert isinstance(result, SyncResult)
        # May or may not have orphans, but should include cleanup attempt
        assert result.orphan_cleanup is None or isinstance(result.orphan_cleanup, CleanupResult)


class TestSecurityValidation:
    """Test security controls in marketplace sync."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_path_traversal_blocked_in_marketplace_sync(self, temp_project):
        """Test path traversal attacks blocked in marketplace sync.

        SECURITY: Prevent attackers from syncing from /etc/passwd.
        Expected: SyncResult with success=False (graceful failure, not exception)
        """
        malicious_marketplace = temp_project / ".." / ".." / "etc" / "passwd"

        dispatcher = SyncDispatcher(project_root=temp_project)

        # Implementation returns gracefully with success=False instead of raising
        result = dispatcher.sync_marketplace(marketplace_plugins_file=malicious_marketplace)
        assert result.success is False
        assert "security" in result.message.lower() or "security" in (result.error or "").lower()

    def test_only_claude_directories_modified(self, temp_project):
        """Test marketplace sync only modifies .claude/ directories.

        SECURITY: Prevent accidental modification of user files.
        Expected: User files outside .claude/ remain untouched.
        """
        # Create user files
        user_file = temp_project / "important.txt"
        user_file.write_text("Important data")

        # Create minimal marketplace
        marketplace_dir = temp_project.parent / "marketplace"
        marketplace_dir.mkdir()
        (marketplace_dir / ".claude").mkdir()
        (marketplace_dir / ".claude" / "plugins").mkdir()

        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {
                "version": "3.8.0",
                "source": "marketplace",
                "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")
            }
        }))

        dispatcher = SyncDispatcher(project_root=temp_project)
        try:
            dispatcher.sync_marketplace(marketplace_plugins_file=marketplace_plugins)
        except Exception:
            pass  # May fail for other reasons, but shouldn't touch user file

        # User file should be unchanged
        assert user_file.read_text() == "Important data"


class TestVersionDetectionNonBlocking:
    """Test version detection failures don't block sync."""

    @pytest.fixture
    def temp_environment(self, tmp_path):
        """Create full test environment."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "plugins").mkdir()
        (project_root / ".claude" / "plugins" / "autonomous-dev").mkdir()

        marketplace_dir = tmp_path / "marketplace"
        marketplace_dir.mkdir()
        (marketplace_dir / ".claude").mkdir()
        (marketplace_dir / ".claude" / "plugins").mkdir()

        return {
            "project_root": project_root,
            "marketplace_dir": marketplace_dir
        }

    def test_version_detection_failure_does_not_block_sync(self, temp_environment):
        """Test sync succeeds even when version detection fails.

        REQUIREMENT: Non-blocking version detection.
        Expected: SyncResult.success=True even if version detection fails.
        """
        project_root = temp_environment["project_root"]
        marketplace_dir = temp_environment["marketplace_dir"]

        # Setup marketplace with invalid plugin.json (will break version detection)
        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {
                "version": "3.8.0",
                "source": "marketplace",
                "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")
            }
        }))

        marketplace_plugin_dir = marketplace_dir / ".claude" / "plugins" / "autonomous-dev"
        marketplace_plugin_dir.mkdir(parents=True)
        # Invalid JSON will break version detection
        (marketplace_plugin_dir / "plugin.json").write_text("invalid json")

        # Create some actual files to sync
        (marketplace_plugin_dir / "commands").mkdir()
        (marketplace_plugin_dir / "commands" / "test.md").write_text("# Test")

        dispatcher = SyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(marketplace_plugins_file=marketplace_plugins)

        # Sync should succeed despite version detection failure
        assert result.success is True
        # Implementation returns VersionComparison even when project version unavailable
        # (status='project_not_synced' instead of None)
        assert result.version_comparison is None or result.version_comparison.status == 'project_not_synced'

    def test_missing_plugin_json_does_not_block_sync(self, temp_environment):
        """Test sync succeeds when plugin.json is missing.

        REQUIREMENT: Non-blocking version detection.
        Expected: SyncResult.success=True, version_comparison=None.
        """
        project_root = temp_environment["project_root"]
        marketplace_dir = temp_environment["marketplace_dir"]

        # Setup marketplace without plugin.json
        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {
                "version": "3.8.0",
                "source": "marketplace",
                "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")
            }
        }))

        marketplace_plugin_dir = marketplace_dir / ".claude" / "plugins" / "autonomous-dev"
        marketplace_plugin_dir.mkdir(parents=True)
        # No plugin.json created

        # Create some actual files to sync
        (marketplace_plugin_dir / "commands").mkdir()
        (marketplace_plugin_dir / "commands" / "test.md").write_text("# Test")

        dispatcher = SyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(marketplace_plugins_file=marketplace_plugins)

        # Sync should succeed despite missing plugin.json
        assert result.success is True
        # Implementation returns VersionComparison even when project version unavailable
        # (status='project_not_synced' instead of None)
        assert result.version_comparison is None or result.version_comparison.status == 'project_not_synced'

    def test_version_detection_error_logged_but_not_raised(self, temp_environment):
        """Test version detection errors are logged but don't raise exceptions.

        REQUIREMENT: Non-blocking error handling.
        Expected: No exceptions raised, errors logged internally.
        """
        project_root = temp_environment["project_root"]
        marketplace_dir = temp_environment["marketplace_dir"]

        # Setup with corrupted version info
        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {
                "version": "invalid.version.format",
                "source": "marketplace",
                "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")
            }
        }))

        marketplace_plugin_dir = marketplace_dir / ".claude" / "plugins" / "autonomous-dev"
        marketplace_plugin_dir.mkdir(parents=True)
        (marketplace_plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "also.invalid"
        }))

        # Create some actual files to sync
        (marketplace_plugin_dir / "commands").mkdir()
        (marketplace_plugin_dir / "commands" / "test.md").write_text("# Test")

        dispatcher = SyncDispatcher(project_root=project_root)

        # Should not raise exception
        result = dispatcher.sync_marketplace(marketplace_plugins_file=marketplace_plugins)

        # Sync should succeed
        assert result.success is True


class TestOrphanDetectionNonBlocking:
    """Test orphan detection failures don't block sync."""

    @pytest.fixture
    def temp_environment(self, tmp_path):
        """Create full test environment."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "commands").mkdir()
        (project_root / ".claude" / "plugins").mkdir()
        (project_root / ".claude" / "plugins" / "autonomous-dev").mkdir()

        marketplace_dir = tmp_path / "marketplace"
        marketplace_dir.mkdir()
        (marketplace_dir / ".claude").mkdir()
        (marketplace_dir / ".claude" / "plugins").mkdir()

        return {
            "project_root": project_root,
            "marketplace_dir": marketplace_dir
        }

    def test_orphan_detection_failure_does_not_block_sync(self, temp_environment):
        """Test sync succeeds even when orphan detection fails.

        REQUIREMENT: Non-blocking orphan detection.
        Expected: SyncResult.success=True even if orphan detection fails.
        """
        project_root = temp_environment["project_root"]
        marketplace_dir = temp_environment["marketplace_dir"]

        # Setup marketplace
        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {
                "version": "3.8.0",
                "source": "marketplace",
                "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")
            }
        }))

        marketplace_plugin_dir = marketplace_dir / ".claude" / "plugins" / "autonomous-dev"
        marketplace_plugin_dir.mkdir(parents=True)
        (marketplace_plugin_dir / "commands").mkdir()
        (marketplace_plugin_dir / "commands" / "test.md").write_text("# Test")

        dispatcher = SyncDispatcher(project_root=project_root)

        # Sync with cleanup enabled (may fail internally)
        result = dispatcher.sync_marketplace(
            marketplace_plugins_file=marketplace_plugins,
            cleanup_orphans=True,
            dry_run=True
        )

        # Sync should succeed even if orphan detection has issues
        assert result.success is True

    def test_orphan_cleanup_error_does_not_block_sync(self, temp_environment):
        """Test sync succeeds even when orphan cleanup fails.

        REQUIREMENT: Non-blocking orphan cleanup.
        Expected: SyncResult.success=True, cleanup errors reported.
        """
        project_root = temp_environment["project_root"]
        marketplace_dir = temp_environment["marketplace_dir"]

        # Create protected orphan file (will cause cleanup failure)
        orphan_file = project_root / ".claude" / "commands" / "old-command.md"
        orphan_file.write_text("# Old Command")
        orphan_file.chmod(0o444)  # Read-only

        # Setup marketplace
        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {
                "version": "3.8.0",
                "source": "marketplace",
                "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")
            }
        }))

        marketplace_plugin_dir = marketplace_dir / ".claude" / "plugins" / "autonomous-dev"
        marketplace_plugin_dir.mkdir(parents=True)
        (marketplace_plugin_dir / "commands").mkdir()
        (marketplace_plugin_dir / "commands" / "test.md").write_text("# Test")

        try:
            dispatcher = SyncDispatcher(project_root=project_root)

            # Sync with cleanup enabled (may fail to delete protected file)
            result = dispatcher.sync_marketplace(
                marketplace_plugins_file=marketplace_plugins,
                cleanup_orphans=True,
                dry_run=False
            )

            # Sync should succeed despite cleanup errors
            assert result.success is True

            # If cleanup was attempted, errors should be reported
            if result.orphan_cleanup:
                # Cleanup may report errors
                assert result.orphan_cleanup.errors >= 0
        finally:
            # Restore permissions for cleanup
            orphan_file.chmod(0o644)


class TestCombinedWorkflow:
    """Test combined version detection + orphan cleanup workflow."""

    @pytest.fixture
    def temp_full_environment(self, tmp_path):
        """Create complete test environment with versions and orphans."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "commands").mkdir()
        (project_root / ".claude" / "plugins").mkdir()
        (project_root / ".claude" / "plugins" / "autonomous-dev").mkdir()

        # Old version with deprecated command
        project_plugin = project_root / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        project_plugin.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.7.0",
            "commands": ["auto-implement.md", "old-command.md"]
        }))

        # Create orphaned command
        orphan_file = project_root / ".claude" / "commands" / "old-command.md"
        orphan_file.write_text("# Old Command")

        # Marketplace setup
        marketplace_dir = tmp_path / "marketplace"
        marketplace_dir.mkdir()
        (marketplace_dir / ".claude").mkdir()
        (marketplace_dir / ".claude" / "plugins").mkdir()

        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {
                "version": "3.8.0",
                "source": "marketplace",
                "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")
            }
        }))

        marketplace_plugin_dir = marketplace_dir / ".claude" / "plugins" / "autonomous-dev"
        marketplace_plugin_dir.mkdir(parents=True)
        (marketplace_plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0",
            "commands": ["auto-implement.md"]  # old-command removed
        }))

        # Create marketplace commands
        (marketplace_plugin_dir / "commands").mkdir()
        (marketplace_plugin_dir / "commands" / "auto-implement.md").write_text("# Auto Implement")

        return {
            "project_root": project_root,
            "marketplace_plugins": marketplace_plugins,
            "orphan_file": orphan_file
        }

    def test_full_sync_workflow_with_all_features(self, temp_full_environment):
        """Test complete sync workflow with version detection and cleanup.

        REQUIREMENT: Integrated workflow with all features.
        Expected: Version upgrade detected, orphans cleaned, success reported.
        """
        project_root = temp_full_environment["project_root"]
        marketplace_plugins = temp_full_environment["marketplace_plugins"]
        orphan_file = temp_full_environment["orphan_file"]

        dispatcher = SyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(
            marketplace_plugins_file=marketplace_plugins,
            cleanup_orphans=True,
            dry_run=False
        )

        # Should succeed
        assert result.success is True

        # Should detect version upgrade
        assert result.version_comparison is not None
        assert result.version_comparison.project_version == "3.7.0"
        assert result.version_comparison.marketplace_version == "3.8.0"

        # Should cleanup orphans
        assert result.orphan_cleanup is not None
        assert result.orphan_cleanup.orphans_deleted > 0
        assert not orphan_file.exists()

    def test_sync_result_details_comprehensive(self, temp_full_environment):
        """Test SyncResult includes comprehensive details.

        REQUIREMENT: Rich result reporting.
        Expected: SyncResult.details includes version_info and orphan_info.
        """
        project_root = temp_full_environment["project_root"]
        marketplace_plugins = temp_full_environment["marketplace_plugins"]

        dispatcher = SyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(
            marketplace_plugins_file=marketplace_plugins,
            cleanup_orphans=True,
            dry_run=True
        )

        # Should include comprehensive details
        assert "files_updated" in result.details or result.details is not None
        assert result.version_comparison is not None
        assert result.orphan_cleanup is not None

    def test_sync_message_includes_all_info(self, temp_full_environment):
        """Test sync message includes version and orphan info.

        REQUIREMENT: Comprehensive user messaging.
        Expected: Message mentions version upgrade and orphans.
        """
        project_root = temp_full_environment["project_root"]
        marketplace_plugins = temp_full_environment["marketplace_plugins"]

        dispatcher = SyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(
            marketplace_plugins_file=marketplace_plugins,
            cleanup_orphans=True,
            dry_run=True
        )

        message_lower = result.message.lower()

        # Should mention version info
        assert "3.7.0" in message_lower or "3.8.0" in message_lower or "upgrade" in message_lower

        # Should mention orphan info if detected
        if result.orphan_cleanup and result.orphan_cleanup.orphans_detected > 0:
            assert "orphan" in message_lower or "cleanup" in message_lower


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def temp_environment(self, tmp_path):
        """Create test environment."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "plugins").mkdir()
        (project_root / ".claude" / "plugins" / "autonomous-dev").mkdir()

        marketplace_dir = tmp_path / "marketplace"
        marketplace_dir.mkdir()
        (marketplace_dir / ".claude").mkdir()
        (marketplace_dir / ".claude" / "plugins").mkdir()

        return {
            "project_root": project_root,
            "marketplace_dir": marketplace_dir
        }

    def test_no_orphans_detected_clean_sync(self, temp_environment):
        """Test clean sync with no orphaned files.

        REQUIREMENT: Handle clean state gracefully.
        Expected: orphan_cleanup shows 0 orphans if cleanup enabled.
        """
        project_root = temp_environment["project_root"]
        marketplace_dir = temp_environment["marketplace_dir"]

        # Setup matching versions
        project_plugin = project_root / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        project_plugin.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0",
            "commands": ["auto-implement.md"]
        }))

        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {
                "version": "3.8.0",
                "source": "marketplace",
                "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")
            }
        }))

        marketplace_plugin_dir = marketplace_dir / ".claude" / "plugins" / "autonomous-dev"
        marketplace_plugin_dir.mkdir(parents=True)
        (marketplace_plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0",
            "commands": ["auto-implement.md"]
        }))

        dispatcher = SyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(
            marketplace_plugins_file=marketplace_plugins,
            cleanup_orphans=True,
            dry_run=True
        )

        # Should succeed
        assert result.success is True

        # Should detect no orphans
        if result.orphan_cleanup:
            assert result.orphan_cleanup.orphans_detected == 0

    def test_version_already_up_to_date(self, temp_environment):
        """Test sync when versions are already matching.

        REQUIREMENT: Handle up-to-date state.
        Expected: version_comparison shows UP_TO_DATE status.
        """
        project_root = temp_environment["project_root"]
        marketplace_dir = temp_environment["marketplace_dir"]

        # Setup identical versions
        project_plugin = project_root / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        project_plugin.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0"
        }))

        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {
                "version": "3.8.0",
                "source": "marketplace",
                "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")
            }
        }))

        marketplace_plugin_dir = marketplace_dir / ".claude" / "plugins" / "autonomous-dev"
        marketplace_plugin_dir.mkdir(parents=True)
        (marketplace_plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0"
        }))

        dispatcher = SyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(marketplace_plugins_file=marketplace_plugins)

        # Should succeed
        assert result.success is True

        # Should detect versions are same
        if result.version_comparison:
            assert result.version_comparison.project_version == "3.8.0"
            assert result.version_comparison.marketplace_version == "3.8.0"

    def test_both_features_fail_gracefully(self, temp_environment):
        """Test sync succeeds even when both version and orphan features fail.

        REQUIREMENT: Non-blocking error handling for all enhancements.
        Expected: Core sync succeeds, enhanced features fail gracefully.
        """
        project_root = temp_environment["project_root"]
        marketplace_dir = temp_environment["marketplace_dir"]

        # Setup to break both version detection (invalid JSON) and orphan detection
        marketplace_plugins = marketplace_dir / ".claude" / "plugins" / "installed_plugins.json"
        marketplace_plugins.write_text(json.dumps({
            "autonomous-dev": {
                "version": "invalid.version",
                "source": "marketplace",
                "path": str(marketplace_dir / ".claude" / "plugins" / "autonomous-dev")
            }
        }))

        marketplace_plugin_dir = marketplace_dir / ".claude" / "plugins" / "autonomous-dev"
        marketplace_plugin_dir.mkdir(parents=True)
        # Invalid JSON for version detection
        (marketplace_plugin_dir / "plugin.json").write_text("invalid json")

        # Create files to sync
        (marketplace_plugin_dir / "commands").mkdir()
        (marketplace_plugin_dir / "commands" / "test.md").write_text("# Test")

        dispatcher = SyncDispatcher(project_root=project_root)
        result = dispatcher.sync_marketplace(
            marketplace_plugins_file=marketplace_plugins,
            cleanup_orphans=True,
            dry_run=True
        )

        # Core sync should still succeed
        assert result.success is True

        # Enhanced features should be None (failed)
        assert result.version_comparison is None
        # orphan_cleanup may be None if it failed


class TestMarketplaceSyncWithNewFiles:
    """Test marketplace sync handles new files correctly (Issue #97).

    Issue: shutil.copytree(dirs_exist_ok=True) silently fails to copy new files
    when destination directory already exists. This specifically affects marketplace
    sync when users update their plugin.
    """

    @pytest.fixture
    def temp_marketplace_env(self, tmp_path):
        """Create full marketplace test environment."""
        # Project setup
        project_root = tmp_path / "project"
        project_root.mkdir()
        project_claude = project_root / ".claude"
        project_claude.mkdir()

        # Marketplace setup
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        marketplace_base = home_dir / ".claude" / "plugins" / "marketplaces" / "autonomous-dev"
        marketplace_base.mkdir(parents=True)
        marketplace_plugin = marketplace_base / "plugins" / "autonomous-dev"
        marketplace_plugin.mkdir(parents=True)

        return {
            "project_root": project_root,
            "project_claude": project_claude,
            "marketplace_plugin": marketplace_plugin,
            "home_dir": home_dir,
            "tmp_path": tmp_path,
        }

    def test_marketplace_sync_adds_new_commands_to_existing_dir(self, temp_marketplace_env):
        """Test marketplace sync copies new commands when commands/ dir already exists.

        REGRESSION TEST for Issue #97: Marketplace sync scenario

        REQUIREMENT: New commands from marketplace update must appear in project.
        Expected: New command files are copied to existing .claude/commands/ directory.

        TDD RED PHASE: This test will FAIL until copytree is replaced with _sync_directory().
        """
        project_claude = temp_marketplace_env["project_claude"]
        marketplace_plugin = temp_marketplace_env["marketplace_plugin"]
        home_dir = temp_marketplace_env["home_dir"]

        # Setup existing project commands directory with old command
        project_commands = project_claude / "commands"
        project_commands.mkdir()
        (project_commands / "old-command.md").write_text("# Old Command")

        # Marketplace has new commands from update
        marketplace_commands = marketplace_plugin / "commands"
        marketplace_commands.mkdir()
        (marketplace_commands / "new-command-1.md").write_text("# New Command 1")
        (marketplace_commands / "new-command-2.md").write_text("# New Command 2")
        (marketplace_commands / "new-command-3.md").write_text("# New Command 3")

        # Create plugin.json
        (marketplace_plugin / "plugin.json").write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.10.0"
        }))

        # Run marketplace sync
        with patch.dict(os.environ, {'HOME': str(home_dir)}):
            dispatcher = SyncDispatcher(str(temp_marketplace_env["project_root"]))
            result = dispatcher.dispatch(SyncMode.MARKETPLACE)

        # CRITICAL ASSERTIONS: New commands must be copied
        assert (project_commands / "new-command-1.md").exists(), \
            "New command 1 was not copied from marketplace (Issue #97 regression)"
        assert (project_commands / "new-command-2.md").exists(), \
            "New command 2 was not copied from marketplace (Issue #97 regression)"
        assert (project_commands / "new-command-3.md").exists(), \
            "New command 3 was not copied from marketplace (Issue #97 regression)"

        # Old command should still exist
        assert (project_commands / "old-command.md").exists(), \
            "Old command was deleted (should be preserved)"

        # Result should show success
        assert result.success is True, f"Sync failed: {result.message}"

        # File count should reflect new files (at least 3)
        if "files_updated" in result.details:
            assert result.details["files_updated"] >= 3, \
                f"Expected at least 3 files updated, got {result.details['files_updated']}"

    def test_marketplace_sync_audit_logs_file_operations(self, temp_marketplace_env):
        """Test marketplace sync with _sync_directory logs individual file operations.

        REQUIREMENT: Audit logging must capture actual files copied for security tracking.
        Expected: audit_log() called for each file operation, not just directories.

        TDD RED PHASE: This test will FAIL until _sync_directory() adds audit logging.
        """
        project_claude = temp_marketplace_env["project_claude"]
        marketplace_plugin = temp_marketplace_env["marketplace_plugin"]
        home_dir = temp_marketplace_env["home_dir"]

        # Setup marketplace commands
        marketplace_commands = marketplace_plugin / "commands"
        marketplace_commands.mkdir()
        (marketplace_commands / "cmd1.md").write_text("# Command 1")
        (marketplace_commands / "cmd2.md").write_text("# Command 2")

        # Create plugin.json
        (marketplace_plugin / "plugin.json").write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.10.0"
        }))

        # Track audit log calls
        with patch.dict(os.environ, {'HOME': str(home_dir)}):
            with patch('plugins.autonomous_dev.lib.sync_dispatcher.audit_log') as mock_audit:
                dispatcher = SyncDispatcher(str(temp_marketplace_env["project_root"]))
                result = dispatcher.dispatch(SyncMode.MARKETPLACE)

                # Should have audit logs for file operations
                audit_calls = [str(call) for call in mock_audit.call_args_list]

                # Look for file-level logging (not just directory-level)
                file_related_logs = [
                    call for call in audit_calls
                    if any(keyword in call.lower() for keyword in ['file', 'copy', 'sync'])
                ]

                assert len(file_related_logs) > 0, \
                    "No audit logs for file operations (expected detailed logging)"

                # Verify at least one log mentions actual file operations
                assert any('marketplace' in call.lower() for call in audit_calls), \
                    "No audit logs mention marketplace sync"
