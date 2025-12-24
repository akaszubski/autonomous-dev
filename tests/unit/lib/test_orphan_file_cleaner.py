#!/usr/bin/env python3
"""
TDD Tests for Orphan File Cleaner (FAILING - Red Phase)

This module contains FAILING tests for orphan_file_cleaner.py which will detect
and remove orphaned files after marketplace plugin updates.

Requirements:
1. Detect orphaned commands/hooks/agents in .claude/ subdirectories
2. Dry-run mode: Report orphans without deleting
3. Confirm mode: Delete only with explicit user approval
4. Security: Only operate within .claude/ subdirectories
5. Audit logging: Log all deletions for tracking

Test Coverage Target: 100% of orphan detection and cleanup logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe orphan cleanup requirements
- Tests should FAIL until orphan_file_cleaner.py is implemented
- Each test validates ONE cleanup requirement

Author: test-master agent
Date: 2025-11-08
Issue: GitHub #50 - Fix Marketplace Update UX
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, call

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# This import will FAIL until orphan_file_cleaner.py is created
from plugins.autonomous_dev.lib.orphan_file_cleaner import (
    OrphanFileCleaner,
    OrphanFile,
    CleanupResult,
    OrphanDetectionError,
    detect_orphans,
    cleanup_orphans,
)


class TestOrphanDetectionCommands:
    """Test detecting orphaned command files in .claude/commands/."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project with .claude directory structure."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "commands").mkdir()
        (project_root / ".claude" / "hooks").mkdir()
        (project_root / ".claude" / "agents").mkdir()
        return project_root

    def test_detect_orphaned_command_file(self, temp_project):
        """Test detecting command file not in plugin.json.

        REQUIREMENT: Orphan detection must identify unused command files.
        Expected: Command file not listed in plugin.json flagged as orphan.
        """
        # Create plugin.json with limited commands
        plugin_json = temp_project / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.parent.mkdir(parents=True)
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0",
            "commands": [
                "auto-implement.md",
                "status.md"
            ]
        }))

        # Create command files (one orphan)
        commands_dir = temp_project / ".claude" / "commands"
        (commands_dir / "auto-implement.md").write_text("# Auto Implement")
        (commands_dir / "status.md").write_text("# Status")
        (commands_dir / "old-command.md").write_text("# Orphaned Command")

        cleaner = OrphanFileCleaner(project_root=temp_project)
        orphans = cleaner.detect_orphans()

        # Should find one orphan
        assert len(orphans) == 1
        assert orphans[0].path == commands_dir / "old-command.md"
        assert orphans[0].category == "command"
        assert orphans[0].is_orphan is True

    def test_no_orphans_when_all_commands_listed(self, temp_project):
        """Test that no orphans detected when all commands in plugin.json.

        REQUIREMENT: Accurate detection - no false positives.
        Expected: Empty orphan list when all files are referenced.
        """
        # Create plugin.json with all commands
        plugin_json = temp_project / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.parent.mkdir(parents=True)
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0",
            "commands": [
                "auto-implement.md",
                "status.md"
            ]
        }))

        # Create exactly matching command files
        commands_dir = temp_project / ".claude" / "commands"
        (commands_dir / "auto-implement.md").write_text("# Auto Implement")
        (commands_dir / "status.md").write_text("# Status")

        cleaner = OrphanFileCleaner(project_root=temp_project)
        orphans = cleaner.detect_orphans()

        assert len(orphans) == 0

    def test_detect_multiple_orphaned_commands(self, temp_project):
        """Test detecting multiple orphaned command files.

        REQUIREMENT: Detect all orphans in a single scan.
        Expected: All orphaned commands identified.
        """
        # Create plugin.json with one command
        plugin_json = temp_project / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.parent.mkdir(parents=True)
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0",
            "commands": ["status.md"]
        }))

        # Create multiple command files (2 orphans)
        commands_dir = temp_project / ".claude" / "commands"
        (commands_dir / "status.md").write_text("# Status")
        (commands_dir / "old-command-1.md").write_text("# Orphan 1")
        (commands_dir / "old-command-2.md").write_text("# Orphan 2")

        cleaner = OrphanFileCleaner(project_root=temp_project)
        orphans = cleaner.detect_orphans()

        assert len(orphans) == 2
        orphan_names = [o.path.name for o in orphans]
        assert "old-command-1.md" in orphan_names
        assert "old-command-2.md" in orphan_names


class TestOrphanDetectionHooks:
    """Test detecting orphaned hook files in .claude/hooks/."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "hooks").mkdir()
        return project_root

    def test_detect_orphaned_hook_file(self, temp_project):
        """Test detecting hook file not in plugin.json.

        REQUIREMENT: Orphan detection covers hooks.
        Expected: Hook file not listed in plugin.json flagged as orphan.
        """
        # Create plugin.json with limited hooks
        plugin_json = temp_project / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.parent.mkdir(parents=True)
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0",
            "hooks": [
                "auto_format.py",
                "security_scan.py"
            ]
        }))

        # Create hook files (one orphan)
        hooks_dir = temp_project / ".claude" / "hooks"
        (hooks_dir / "auto_format.py").write_text("# Auto Format")
        (hooks_dir / "security_scan.py").write_text("# Security Scan")
        (hooks_dir / "old_hook.py").write_text("# Orphaned Hook")

        cleaner = OrphanFileCleaner(project_root=temp_project)
        orphans = cleaner.detect_orphans()

        assert len(orphans) == 1
        assert orphans[0].path == hooks_dir / "old_hook.py"
        assert orphans[0].category == "hook"

    def test_ignore_pycache_and_init_files(self, temp_project):
        """Test that __pycache__ and __init__.py are not flagged as orphans.

        REQUIREMENT: Ignore Python infrastructure files.
        Expected: __pycache__, __init__.py, *.pyc not reported as orphans.
        """
        # Create plugin.json with no hooks
        plugin_json = temp_project / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.parent.mkdir(parents=True)
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0",
            "hooks": []
        }))

        # Create Python infrastructure files
        hooks_dir = temp_project / ".claude" / "hooks"
        (hooks_dir / "__init__.py").write_text("")
        (hooks_dir / "__pycache__").mkdir()
        (hooks_dir / "__pycache__" / "module.pyc").write_text("bytecode")

        cleaner = OrphanFileCleaner(project_root=temp_project)
        orphans = cleaner.detect_orphans()

        # Should not flag __init__.py or __pycache__
        assert len(orphans) == 0


class TestOrphanDetectionAgents:
    """Test detecting orphaned agent files in plugins/autonomous-dev/agents/."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project with agents directory."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "plugins").mkdir()
        (project_root / ".claude" / "plugins" / "autonomous-dev").mkdir()
        (project_root / ".claude" / "plugins" / "autonomous-dev" / "agents").mkdir()
        return project_root

    def test_detect_orphaned_agent_file(self, temp_project):
        """Test detecting agent file not in plugin.json.

        REQUIREMENT: Orphan detection covers agents.
        Expected: Agent file not listed in plugin.json flagged as orphan.
        """
        # Create plugin.json with limited agents
        plugin_json = temp_project / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0",
            "agents": [
                "researcher.md",
                "planner.md"
            ]
        }))

        # Create agent files (one orphan)
        agents_dir = temp_project / ".claude" / "plugins" / "autonomous-dev" / "agents"
        (agents_dir / "researcher.md").write_text("# Researcher")
        (agents_dir / "planner.md").write_text("# Planner")
        (agents_dir / "old-agent.md").write_text("# Orphaned Agent")

        cleaner = OrphanFileCleaner(project_root=temp_project)
        orphans = cleaner.detect_orphans()

        assert len(orphans) == 1
        assert orphans[0].path.name == "old-agent.md"
        assert orphans[0].category == "agent"


class TestDryRunMode:
    """Test dry-run mode reports orphans without deleting."""

    @pytest.fixture
    def temp_project_with_orphans(self, tmp_path):
        """Create project with orphaned files."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "commands").mkdir()

        # Create plugin.json with no commands
        plugin_json = project_root / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.parent.mkdir(parents=True)
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0",
            "commands": []
        }))

        # Create orphaned command
        orphan = project_root / ".claude" / "commands" / "orphan.md"
        orphan.write_text("# Orphan")

        return project_root, orphan

    def test_dry_run_reports_orphans_without_deleting(self, temp_project_with_orphans):
        """Test dry-run mode detects orphans but doesn't delete them.

        REQUIREMENT: Dry-run mode for safe inspection.
        Expected: Orphans reported, files still exist after dry-run.
        """
        project_root, orphan_file = temp_project_with_orphans

        cleaner = OrphanFileCleaner(project_root=project_root)
        result = cleaner.cleanup_orphans(dry_run=True)

        # Should report orphan
        assert result.orphans_detected == 1
        assert result.orphans_deleted == 0
        assert result.dry_run is True

        # File should still exist
        assert orphan_file.exists()

    def test_dry_run_result_contains_orphan_details(self, temp_project_with_orphans):
        """Test dry-run result includes details about orphans.

        REQUIREMENT: Provide detailed report for user review.
        Expected: Result includes list of orphan files and metadata.
        """
        project_root, orphan_file = temp_project_with_orphans

        cleaner = OrphanFileCleaner(project_root=project_root)
        result = cleaner.cleanup_orphans(dry_run=True)

        # Should include orphan details
        assert len(result.orphans) == 1
        assert result.orphans[0].path == orphan_file
        assert result.orphans[0].category == "command"


class TestConfirmMode:
    """Test confirm mode deletes orphans only with approval."""

    @pytest.fixture
    def temp_project_with_orphans(self, tmp_path):
        """Create project with orphaned files."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "commands").mkdir()

        # Create plugin.json with no commands
        plugin_json = project_root / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.parent.mkdir(parents=True)
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0",
            "commands": []
        }))

        # Create orphaned commands
        orphan1 = project_root / ".claude" / "commands" / "orphan1.md"
        orphan2 = project_root / ".claude" / "commands" / "orphan2.md"
        orphan1.write_text("# Orphan 1")
        orphan2.write_text("# Orphan 2")

        return project_root, [orphan1, orphan2]

    @patch('builtins.input', return_value='y')
    def test_confirm_mode_deletes_with_user_approval(self, mock_input, temp_project_with_orphans):
        """Test confirm mode deletes orphans when user approves.

        REQUIREMENT: Require explicit user approval for deletions.
        Expected: Files deleted only after user confirms.
        """
        project_root, orphan_files = temp_project_with_orphans

        cleaner = OrphanFileCleaner(project_root=project_root)
        result = cleaner.cleanup_orphans(confirm=True)

        # Should delete orphans
        assert result.orphans_deleted == 2
        assert result.orphans_detected == 2

        # Files should be deleted
        for orphan in orphan_files:
            assert not orphan.exists()

    @patch('builtins.input', return_value='n')
    def test_confirm_mode_preserves_files_when_user_declines(self, mock_input, temp_project_with_orphans):
        """Test confirm mode preserves files when user declines.

        REQUIREMENT: Respect user decision to preserve files.
        Expected: Files preserved when user says 'n'.
        """
        project_root, orphan_files = temp_project_with_orphans

        cleaner = OrphanFileCleaner(project_root=project_root)
        result = cleaner.cleanup_orphans(confirm=True)

        # Should not delete orphans
        assert result.orphans_deleted == 0
        assert result.orphans_detected == 2

        # Files should still exist
        for orphan in orphan_files:
            assert orphan.exists()

    def test_auto_mode_deletes_without_confirmation(self, temp_project_with_orphans):
        """Test auto mode deletes orphans without prompting.

        REQUIREMENT: Auto mode for automated cleanup.
        Expected: Files deleted immediately without user input.
        """
        project_root, orphan_files = temp_project_with_orphans

        cleaner = OrphanFileCleaner(project_root=project_root)
        result = cleaner.cleanup_orphans(confirm=False, dry_run=False)

        # Should delete orphans
        assert result.orphans_deleted == 2

        # Files should be deleted
        for orphan in orphan_files:
            assert not orphan.exists()


class TestSecurityValidation:
    """Test security controls restrict operations to .claude/ subdirectories."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        return project_root

    def test_only_claude_subdirectories_allowed(self, temp_project):
        """Test that only .claude/ subdirectories are scanned for orphans.

        SECURITY: Prevent accidental deletion of user files.
        Expected: Only .claude/commands/, .claude/hooks/, plugins/*/agents/ scanned.
        """
        # Create files outside .claude/
        (temp_project / "user_file.md").write_text("User content")
        (temp_project / "docs").mkdir()
        (temp_project / "docs" / "important.md").write_text("Important doc")

        # Create plugin.json with no entries
        plugin_json = temp_project / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.parent.mkdir(parents=True)
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0",
            "commands": [],
            "hooks": [],
            "agents": []
        }))

        cleaner = OrphanFileCleaner(project_root=temp_project)
        orphans = cleaner.detect_orphans()

        # Should not flag user files as orphans
        orphan_paths = [o.path for o in orphans]
        assert temp_project / "user_file.md" not in orphan_paths
        assert temp_project / "docs" / "important.md" not in orphan_paths

    def test_path_traversal_attack_blocked(self, temp_project):
        """Test that path traversal via project_root is blocked.

        SECURITY: Prevent attackers from deleting system files.
        Expected: ValueError or SecurityError for malicious paths.
        """
        malicious_root = temp_project / ".." / ".." / "etc"

        with pytest.raises((ValueError, PermissionError, FileNotFoundError)):
            cleaner = OrphanFileCleaner(project_root=malicious_root)
            cleaner.detect_orphans()

    def test_symlink_attack_blocked(self, temp_project):
        """Test that symlinks pointing outside project are rejected.

        SECURITY: Prevent symlink-based deletion attacks.
        Expected: Symlinks to outside directories not followed.
        """
        # Create target outside project
        outside_target = temp_project.parent / "important_file.md"
        outside_target.write_text("Critical data")

        # Create symlink inside .claude/commands/
        commands_dir = temp_project / ".claude" / "commands"
        commands_dir.mkdir(parents=True)
        symlink_path = commands_dir / "malicious_link.md"

        if hasattr(os, 'symlink'):
            try:
                symlink_path.symlink_to(outside_target)

                # Create plugin.json with no commands
                plugin_json = temp_project / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
                plugin_json.parent.mkdir(parents=True)
                plugin_json.write_text(json.dumps({
                    "name": "autonomous-dev",
                    "version": "3.8.0",
                    "commands": []
                }))

                cleaner = OrphanFileCleaner(project_root=temp_project)
                # Should either reject symlink or not delete outside file
                cleaner.cleanup_orphans(confirm=False, dry_run=False)

                # Critical: outside file must still exist
                assert outside_target.exists()
            except OSError:
                pytest.skip("Symlinks not supported on this system")
        else:
            pytest.skip("Symlinks not available on Windows")


class TestAuditLogging:
    """Test audit logging for all deletion operations."""

    @pytest.fixture
    def temp_project_with_orphans(self, tmp_path):
        """Create project with orphaned files."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "commands").mkdir()
        (project_root / "logs").mkdir()

        # Create plugin.json with no commands
        plugin_json = project_root / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.parent.mkdir(parents=True)
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0",
            "commands": []
        }))

        # Create orphaned command
        orphan = project_root / ".claude" / "commands" / "orphan.md"
        orphan.write_text("# Orphan")

        return project_root, orphan

    def test_audit_log_created_for_deletions(self, temp_project_with_orphans):
        """Test that deletions are logged to audit file.

        REQUIREMENT: Audit trail for all file deletions.
        Expected: logs/orphan_cleanup_audit.log contains deletion records.
        """
        project_root, orphan_file = temp_project_with_orphans

        cleaner = OrphanFileCleaner(project_root=project_root)
        cleaner.cleanup_orphans(confirm=False, dry_run=False)

        # Check audit log exists
        audit_log = project_root / "logs" / "orphan_cleanup_audit.log"
        assert audit_log.exists()

        # Check log contains deletion record
        log_content = audit_log.read_text()
        assert str(orphan_file.name) in log_content
        assert "deleted" in log_content.lower()

    def test_audit_log_includes_metadata(self, temp_project_with_orphans):
        """Test audit log includes timestamp, user, file path.

        REQUIREMENT: Complete audit trail for security review.
        Expected: JSON log entries with timestamp, operation, path, user.
        """
        project_root, orphan_file = temp_project_with_orphans

        cleaner = OrphanFileCleaner(project_root=project_root)
        cleaner.cleanup_orphans(confirm=False, dry_run=False)

        # Parse audit log
        audit_log = project_root / "logs" / "orphan_cleanup_audit.log"
        log_entries = [json.loads(line) for line in audit_log.read_text().strip().split('\n')]

        # Check first entry
        entry = log_entries[0]
        assert "timestamp" in entry
        assert "operation" in entry
        assert "path" in entry
        assert entry["operation"] == "delete_orphan"


class TestErrorHandling:
    """Test error handling for permission denied and other failures."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "commands").mkdir()
        return project_root

    def test_permission_denied_handled_gracefully(self, temp_project, monkeypatch):
        """Test that permission denied errors are caught and reported.

        REQUIREMENT: Graceful error handling for read-only files.
        Expected: CleanupResult includes error details, doesn't crash.
        """
        # Create plugin.json with no commands
        plugin_json = temp_project / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.parent.mkdir(parents=True)
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0",
            "commands": []
        }))

        # Create orphan file
        orphan = temp_project / ".claude" / "commands" / "readonly.md"
        orphan.write_text("# Read-only")

        # Mock os.unlink to raise PermissionError (reliable across platforms)
        import os
        original_unlink = os.unlink
        def mock_unlink(path):
            if str(path).endswith("readonly.md"):
                raise PermissionError(f"Permission denied: {path}")
            return original_unlink(path)

        monkeypatch.setattr("os.unlink", mock_unlink)

        cleaner = OrphanFileCleaner(project_root=temp_project)
        result = cleaner.cleanup_orphans(confirm=False, dry_run=False)

        # Should report error but not crash
        assert result.errors == 1
        assert result.orphans_deleted == 0

    def test_missing_plugin_json_raises_error(self, temp_project):
        """Test that missing plugin.json raises clear error.

        REQUIREMENT: Fail fast if plugin.json not found.
        Expected: OrphanDetectionError indicating missing plugin.json.
        """
        # No plugin.json created

        cleaner = OrphanFileCleaner(project_root=temp_project)

        with pytest.raises(OrphanDetectionError) as exc_info:
            cleaner.detect_orphans()

        assert "plugin.json" in str(exc_info.value).lower()


class TestCleanupResultDataClass:
    """Test CleanupResult data class for reporting outcomes."""

    def test_cleanup_result_attributes(self):
        """Test CleanupResult has expected attributes.

        REQUIREMENT: Result object must capture cleanup outcome.
        Expected: Has orphans_detected, orphans_deleted, dry_run, errors.
        """
        result = CleanupResult(
            orphans_detected=5,
            orphans_deleted=3,
            dry_run=False,
            errors=0,
            orphans=[]
        )

        assert result.orphans_detected == 5
        assert result.orphans_deleted == 3
        assert result.dry_run is False
        assert result.errors == 0

    def test_cleanup_result_summary_message(self):
        """Test CleanupResult can generate summary message.

        REQUIREMENT: Provide clear user feedback.
        Expected: summary property returns descriptive text.
        """
        result = CleanupResult(
            orphans_detected=5,
            orphans_deleted=3,
            dry_run=False,
            errors=2,
            orphans=[]
        )

        summary = result.summary

        assert "5" in summary  # Detected count
        assert "3" in summary  # Deleted count
        assert "2" in summary or "error" in summary.lower()  # Error count


class TestHighLevelFunctions:
    """Test high-level convenience functions."""

    @pytest.fixture
    def temp_project_with_orphans(self, tmp_path):
        """Create project with orphaned files."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "commands").mkdir()

        # Create plugin.json
        plugin_json = project_root / ".claude" / "plugins" / "autonomous-dev" / "plugin.json"
        plugin_json.parent.mkdir(parents=True)
        plugin_json.write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "3.8.0",
            "commands": []
        }))

        # Create orphan
        orphan = project_root / ".claude" / "commands" / "orphan.md"
        orphan.write_text("# Orphan")

        return project_root

    def test_detect_orphans_function(self, temp_project_with_orphans):
        """Test detect_orphans() convenience function.

        REQUIREMENT: High-level API for orphan detection.
        Expected: Returns list of OrphanFile objects.
        """
        orphans = detect_orphans(project_root=temp_project_with_orphans)

        assert len(orphans) == 1
        assert isinstance(orphans[0], OrphanFile)
        assert orphans[0].category == "command"

    def test_cleanup_orphans_function(self, temp_project_with_orphans):
        """Test cleanup_orphans() convenience function.

        REQUIREMENT: High-level API for cleanup.
        Expected: Returns CleanupResult object.
        """
        result = cleanup_orphans(
            project_root=temp_project_with_orphans,
            dry_run=True
        )

        assert isinstance(result, CleanupResult)
        assert result.orphans_detected == 1
        assert result.dry_run is True
