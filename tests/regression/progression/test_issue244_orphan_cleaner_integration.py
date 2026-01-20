#!/usr/bin/env python3
"""
Progression tests for Issue #244: OrphanFileCleaner integration with .claude/local/ protection.

Tests that orphan_file_cleaner respects protected_file_detector patterns and
never deletes files in .claude/local/ directory.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially until implementation is complete.

Test Strategy:
- Test that .claude/local/ files are never detected as orphans
- Test that orphan cleanup skips .claude/local/ even when not in plugin.json
- Test integration with ProtectedFileDetector
- Test edge cases (empty .claude/local/, nested files, etc.)

Coverage Target: 80%+

Date: 2026-01-21
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

# Import orphan cleaner and protected file detector
try:
    from plugins.autonomous_dev.lib.orphan_file_cleaner import (
        OrphanFileCleaner,
        OrphanFile,
        CleanupResult,
        detect_orphans,
        cleanup_orphans,
    )
    from plugins.autonomous_dev.lib.protected_file_detector import ProtectedFileDetector
except ImportError as e:
    pytest.skip(f"Implementation not found (TDD red phase): {e}", allow_module_level=True)


@pytest.fixture
def project_with_local_and_orphans(tmp_path):
    """Create test project with .claude/local/ and orphan files."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Create .claude directory structure
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir()

    # Create .claude/local/ with operational configs
    local_dir = claude_dir / "local"
    local_dir.mkdir()
    (local_dir / "OPERATIONS.md").write_text("# Operations\n\nRepo-specific procedures")
    (local_dir / "config.json").write_text('{"environment": "production"}')

    # Create nested structure in local/
    configs_dir = local_dir / "configs"
    configs_dir.mkdir()
    (configs_dir / "database.json").write_text('{"host": "localhost"}')

    # Create command/hook directories
    commands_dir = claude_dir / "commands"
    commands_dir.mkdir()
    (commands_dir / "implement.md").write_text("# Implement")
    (commands_dir / "orphan-command.md").write_text("# Orphan")  # This is orphan

    hooks_dir = claude_dir / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "auto_format.py").write_text("# Format")
    (hooks_dir / "orphan_hook.py").write_text("# Orphan")  # This is orphan

    # Create plugin.json WITHOUT orphaned files
    plugin_dir = claude_dir / "plugins" / "autonomous-dev"
    plugin_dir.mkdir(parents=True)
    plugin_json = plugin_dir / "plugin.json"
    plugin_json.write_text(json.dumps({
        "name": "autonomous-dev",
        "version": "4.0.0",
        "commands": ["implement.md"],  # orphan-command.md NOT listed
        "hooks": ["auto_format.py"],  # orphan_hook.py NOT listed
        "agents": []
    }))

    return project_dir


@pytest.fixture
def project_with_only_local_files(tmp_path):
    """Create test project with ONLY .claude/local/ files (no orphans)."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Create .claude directory structure
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir()

    # Create .claude/local/ with files
    local_dir = claude_dir / "local"
    local_dir.mkdir()
    (local_dir / "OPERATIONS.md").write_text("# Operations")
    (local_dir / "notes.txt").write_text("Notes")

    # Create command/hook directories (empty)
    (claude_dir / "commands").mkdir()
    (claude_dir / "hooks").mkdir()

    # Create plugin.json with empty lists
    plugin_dir = claude_dir / "plugins" / "autonomous-dev"
    plugin_dir.mkdir(parents=True)
    plugin_json = plugin_dir / "plugin.json"
    plugin_json.write_text(json.dumps({
        "name": "autonomous-dev",
        "version": "4.0.0",
        "commands": [],
        "hooks": [],
        "agents": []
    }))

    return project_dir


class TestOrphanCleanerSkipsLocalDirectory:
    """Test that OrphanFileCleaner never detects .claude/local/ files as orphans."""

    def test_local_files_not_detected_as_orphans(self, project_with_local_and_orphans):
        """Test that files in .claude/local/ are never detected as orphans.

        Current: FAILS - Integration not implemented yet
        """
        cleaner = OrphanFileCleaner(project_root=project_with_local_and_orphans)
        orphans = cleaner.detect_orphans()

        # Should detect orphan commands/hooks but NOT local files
        orphan_paths = [str(o.path) for o in orphans]

        # Orphan files should be detected
        assert any("orphan-command.md" in p for p in orphan_paths)
        assert any("orphan_hook.py" in p for p in orphan_paths)

        # Local files should NOT be detected as orphans
        assert not any("OPERATIONS.md" in p for p in orphan_paths)
        assert not any("config.json" in p for p in orphan_paths)
        assert not any("database.json" in p for p in orphan_paths)
        assert not any(".claude/local" in p for p in orphan_paths)

    def test_only_local_files_present_no_orphans_detected(self, project_with_only_local_files):
        """Test that project with ONLY .claude/local/ files has no orphans.

        Current: FAILS - Integration not implemented yet
        """
        cleaner = OrphanFileCleaner(project_root=project_with_only_local_files)
        orphans = cleaner.detect_orphans()

        # Should detect zero orphans (all files are in protected .claude/local/)
        assert len(orphans) == 0

    def test_nested_local_files_not_detected_as_orphans(self, project_with_local_and_orphans):
        """Test that nested files in .claude/local/configs/ are not orphans.

        Current: FAILS - Integration not implemented yet
        """
        cleaner = OrphanFileCleaner(project_root=project_with_local_and_orphans)
        orphans = cleaner.detect_orphans()

        orphan_paths = [str(o.path) for o in orphans]

        # Nested local file should NOT be detected
        assert not any("local/configs/database.json" in p for p in orphan_paths)

    def test_cleanup_orphans_skips_local_directory(self, project_with_local_and_orphans):
        """Test that cleanup_orphans() deletes orphans but preserves .claude/local/.

        Current: FAILS - Integration not implemented yet
        """
        cleaner = OrphanFileCleaner(project_root=project_with_local_and_orphans)

        # Cleanup orphans (not dry-run)
        result = cleaner.cleanup_orphans(dry_run=False, confirm=False)

        # Should have deleted orphans
        assert result.orphans_deleted >= 2  # orphan-command.md, orphan_hook.py

        # Verify .claude/local/ still exists and intact
        local_dir = project_with_local_and_orphans / ".claude" / "local"
        assert local_dir.exists()
        assert (local_dir / "OPERATIONS.md").exists()
        assert (local_dir / "config.json").exists()
        assert (local_dir / "configs" / "database.json").exists()

    def test_get_actual_files_excludes_local_directory(self, project_with_local_and_orphans):
        """Test that _get_actual_files() doesn't return .claude/local/ files.

        Current: FAILS - Integration not implemented yet
        """
        cleaner = OrphanFileCleaner(project_root=project_with_local_and_orphans)

        # Get actual command files
        command_files = cleaner._get_actual_files("commands")
        command_paths = [f.name for f in command_files]

        # Should include commands, but NOT local files
        assert "implement.md" in command_paths
        assert "orphan-command.md" in command_paths
        assert "OPERATIONS.md" not in command_paths
        assert "config.json" not in command_paths


class TestOrphanCleanerIntegrationWithProtectedFileDetector:
    """Test integration between OrphanFileCleaner and ProtectedFileDetector."""

    def test_orphan_cleaner_uses_protected_file_detector(self, project_with_local_and_orphans):
        """Test that OrphanFileCleaner integrates with ProtectedFileDetector.

        Current: FAILS - Integration not implemented yet
        """
        cleaner = OrphanFileCleaner(project_root=project_with_local_and_orphans)

        # OrphanFileCleaner should use ProtectedFileDetector to check files
        # This is an implementation detail, but important for integration

        # Detect orphans
        orphans = cleaner.detect_orphans()

        # Protected files should not be in orphan list
        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_with_local_and_orphans)
        protected_paths = {f["path"] for f in protected_files}

        orphan_paths = {str(o.path.relative_to(project_with_local_and_orphans)) for o in orphans}

        # No overlap between protected files and orphans
        overlap = protected_paths & orphan_paths
        assert len(overlap) == 0, f"Protected files detected as orphans: {overlap}"

    def test_protected_pattern_matching_for_local_files(self, project_with_local_and_orphans):
        """Test that protected pattern .claude/local/** is respected.

        Current: FAILS - Integration not implemented yet
        """
        detector = ProtectedFileDetector()

        # All .claude/local/ paths should match protected pattern
        assert detector.matches_pattern(".claude/local/OPERATIONS.md")
        assert detector.matches_pattern(".claude/local/config.json")
        assert detector.matches_pattern(".claude/local/configs/database.json")
        assert detector.matches_pattern(".claude/local/deeply/nested/file.txt")

    def test_orphan_cleaner_respects_protected_patterns(self, project_with_local_and_orphans):
        """Test that OrphanFileCleaner respects all PROTECTED_PATTERNS.

        Current: FAILS - Integration not implemented yet
        """
        # Create additional protected files
        local_dir = project_with_local_and_orphans / ".claude" / "local"
        (local_dir / "secret.env").write_text("SECRET=value")  # Matches *.env pattern
        (local_dir / "api.secret").write_text("API_KEY=abc")  # Matches **/*.secret pattern

        cleaner = OrphanFileCleaner(project_root=project_with_local_and_orphans)
        orphans = cleaner.detect_orphans()

        orphan_paths = [str(o.path) for o in orphans]

        # Protected files should NOT be orphans
        assert not any("secret.env" in p for p in orphan_paths)
        assert not any("api.secret" in p for p in orphan_paths)


class TestOrphanCleanerEdgeCases:
    """Test edge cases for .claude/local/ protection in orphan cleaner."""

    def test_empty_local_directory_no_errors(self, tmp_path):
        """Test that empty .claude/local/ directory doesn't cause errors.

        Current: FAILS - Edge case not tested yet
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create empty .claude/local/
        local_dir = project_dir / ".claude" / "local"
        local_dir.mkdir(parents=True)

        # Create minimal plugin.json
        plugin_dir = project_dir / ".claude" / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "4.0.0",
            "commands": [],
            "hooks": [],
            "agents": []
        }))

        # Should not error on empty directory
        cleaner = OrphanFileCleaner(project_root=project_dir)
        orphans = cleaner.detect_orphans()

        assert len(orphans) == 0

    def test_local_directory_with_subdirectories(self, tmp_path):
        """Test .claude/local/ with multiple subdirectory levels.

        Current: FAILS - Edge case not tested yet
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create deep directory structure
        deep_dir = project_dir / ".claude" / "local" / "a" / "b" / "c"
        deep_dir.mkdir(parents=True)
        (deep_dir / "deep.txt").write_text("Deep file")

        # Create minimal structure
        (project_dir / ".claude" / "commands").mkdir(parents=True)
        (project_dir / ".claude" / "hooks").mkdir(parents=True)

        plugin_dir = project_dir / ".claude" / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "4.0.0",
            "commands": [],
            "hooks": [],
            "agents": []
        }))

        # Deep local file should not be detected as orphan
        cleaner = OrphanFileCleaner(project_root=project_dir)
        orphans = cleaner.detect_orphans()

        orphan_paths = [str(o.path) for o in orphans]
        assert not any("deep.txt" in p for p in orphan_paths)

    def test_local_directory_symlinks_respected(self, tmp_path):
        """Test that symlinks in .claude/local/ are respected.

        Current: FAILS - Symlink edge case not tested yet
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create actual file elsewhere
        actual_file = tmp_path / "actual-operations.md"
        actual_file.write_text("# Operations")

        # Create .claude/local/ with symlink
        local_dir = project_dir / ".claude" / "local"
        local_dir.mkdir(parents=True)
        symlink = local_dir / "OPERATIONS.md"
        symlink.symlink_to(actual_file)

        # Create minimal structure
        (project_dir / ".claude" / "commands").mkdir(parents=True)
        (project_dir / ".claude" / "hooks").mkdir(parents=True)

        plugin_dir = project_dir / ".claude" / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "4.0.0",
            "commands": [],
            "hooks": [],
            "agents": []
        }))

        # Symlink should not be detected as orphan
        cleaner = OrphanFileCleaner(project_root=project_dir)
        orphans = cleaner.detect_orphans()

        assert len(orphans) == 0

    def test_local_directory_with_special_characters_in_filenames(self, tmp_path):
        """Test .claude/local/ files with special characters.

        Current: FAILS - Edge case not tested yet
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create files with special characters
        local_dir = project_dir / ".claude" / "local"
        local_dir.mkdir(parents=True)
        (local_dir / "config (production).json").write_text('{"env": "prod"}')
        (local_dir / "notes-2024.txt").write_text("Notes")
        (local_dir / "file_with_underscores.md").write_text("# File")

        # Create minimal structure
        (project_dir / ".claude" / "commands").mkdir(parents=True)
        (project_dir / ".claude" / "hooks").mkdir(parents=True)

        plugin_dir = project_dir / ".claude" / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "autonomous-dev",
            "version": "4.0.0",
            "commands": [],
            "hooks": [],
            "agents": []
        }))

        # Files with special characters should not be orphans
        cleaner = OrphanFileCleaner(project_root=project_dir)
        orphans = cleaner.detect_orphans()

        assert len(orphans) == 0


class TestHighLevelConvenienceFunctions:
    """Test high-level convenience functions with .claude/local/ protection."""

    def test_detect_orphans_function_skips_local(self, project_with_local_and_orphans):
        """Test detect_orphans() convenience function skips .claude/local/.

        Current: FAILS - Integration not implemented yet
        """
        orphans = detect_orphans(str(project_with_local_and_orphans))

        orphan_paths = [str(o.path) for o in orphans]

        # Should not include .claude/local/ files
        assert not any(".claude/local" in p for p in orphan_paths)

    def test_cleanup_orphans_function_preserves_local(self, project_with_local_and_orphans):
        """Test cleanup_orphans() convenience function preserves .claude/local/.

        Current: FAILS - Integration not implemented yet
        """
        # Cleanup without dry-run
        result = cleanup_orphans(
            str(project_with_local_and_orphans),
            dry_run=False,
            confirm=False
        )

        # Should have cleaned up orphans
        assert result.orphans_deleted >= 2

        # Verify .claude/local/ still exists
        local_dir = project_with_local_and_orphans / ".claude" / "local"
        assert local_dir.exists()
        assert (local_dir / "OPERATIONS.md").exists()


class TestRegressionProtection:
    """Test that existing orphan detection still works correctly."""

    def test_orphan_commands_still_detected(self, project_with_local_and_orphans):
        """Test that orphan commands are still detected correctly.

        Current: PASS - Existing functionality should not break
        """
        cleaner = OrphanFileCleaner(project_root=project_with_local_and_orphans)
        orphans = cleaner.detect_orphans()

        # Should still detect orphan command
        orphan_commands = [o for o in orphans if o.category == "command"]
        assert len(orphan_commands) >= 1
        assert any("orphan-command.md" in str(o.path) for o in orphan_commands)

    def test_orphan_hooks_still_detected(self, project_with_local_and_orphans):
        """Test that orphan hooks are still detected correctly.

        Current: PASS - Existing functionality should not break
        """
        cleaner = OrphanFileCleaner(project_root=project_with_local_and_orphans)
        orphans = cleaner.detect_orphans()

        # Should still detect orphan hook
        orphan_hooks = [o for o in orphans if o.category == "hook"]
        assert len(orphan_hooks) >= 1
        assert any("orphan_hook.py" in str(o.path) for o in orphan_hooks)

    def test_cleanup_still_works_for_non_protected_files(self, project_with_local_and_orphans):
        """Test that cleanup still deletes non-protected orphans.

        Current: PASS - Existing functionality should not break
        """
        cleaner = OrphanFileCleaner(project_root=project_with_local_and_orphans)

        # Verify orphan files exist before cleanup
        orphan_command = project_with_local_and_orphans / ".claude" / "commands" / "orphan-command.md"
        orphan_hook = project_with_local_and_orphans / ".claude" / "hooks" / "orphan_hook.py"
        assert orphan_command.exists()
        assert orphan_hook.exists()

        # Cleanup
        result = cleaner.cleanup_orphans(dry_run=False, confirm=False)

        # Orphan files should be deleted
        assert result.orphans_deleted >= 2
        assert not orphan_command.exists()
        assert not orphan_hook.exists()
