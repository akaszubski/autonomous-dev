"""
TDD Integration Tests for Issue #80 - Enhanced Install Orchestrator (Phase 4)

Tests the enhanced InstallOrchestrator that coordinates the complete
installation workflow with 100% file coverage.

Current State (RED PHASE):
- Enhanced orchestrator methods don't exist yet
- Backup/rollback enhancements don't exist
- All tests should FAIL

Test Coverage:
- Fresh installation with 201+ files
- Upgrade with conflict detection
- Automatic backup before changes
- Rollback on failure
- Marketplace directory detection
- Installation marker file tracking

GitHub Issue: #80
Agent: test-master
Date: 2025-11-19
"""

import pytest
from pathlib import Path
import json
import shutil
import time


class TestEnhancedFreshInstallation:
    """Test enhanced fresh installation workflow."""

    def test_fresh_install_copies_all_201_files(self, tmp_path):
        """Test that fresh install copies all 201+ files (100% coverage).

        Current install.sh: ~152 files (76%)
        Target: 201+ files (100%)

        Current: FAILS - Enhanced orchestrator doesn't exist
        """
        # Arrange: Create comprehensive plugin structure (201+ files)
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        file_count = 0

        # Commands: 20 files
        (plugin_dir / "commands").mkdir()
        for i in range(20):
            (plugin_dir / "commands" / f"command{i}.md").touch()
            file_count += 1

        # Hooks: 42 files
        (plugin_dir / "hooks").mkdir()
        for i in range(42):
            (plugin_dir / "hooks" / f"hook{i}.py").touch()
            file_count += 1

        # Agents: 20 files
        (plugin_dir / "agents").mkdir()
        for i in range(20):
            (plugin_dir / "agents" / f"agent{i}.md").touch()
            file_count += 1

        # Lib: 30 files (Python + nested)
        (plugin_dir / "lib").mkdir()
        for i in range(25):
            (plugin_dir / "lib" / f"lib{i}.py").touch()
            file_count += 1

        (plugin_dir / "lib" / "nested").mkdir()
        for i in range(5):
            (plugin_dir / "lib" / "nested" / f"utils{i}.py").touch()
            file_count += 1

        # Scripts: 10 files
        (plugin_dir / "scripts").mkdir()
        for i in range(10):
            script = plugin_dir / "scripts" / f"script{i}.py"
            script.write_text("#!/usr/bin/env python3\nprint('test')")
            file_count += 1

        # Skills: 27 skills × 4 files = 108 files
        (plugin_dir / "skills").mkdir()
        for i in range(27):
            skill_dir = plugin_dir / "skills" / f"skill{i}.skill"
            skill_dir.mkdir()
            (skill_dir / "skill.md").touch()
            file_count += 1

            (skill_dir / "docs").mkdir()
            (skill_dir / "docs" / "guide.md").touch()
            file_count += 1

            (skill_dir / "examples").mkdir()
            (skill_dir / "examples" / "example.py").touch()
            file_count += 1

        # Total: 20 + 42 + 20 + 30 + 10 + 108 = 230 files

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Act: Fresh install
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        result = orchestrator.fresh_install()

        # Assert: All files copied
        assert result.status == "success"
        assert result.files_copied == file_count
        assert result.coverage == 100.0

        # Verify structure
        claude_dir = project_dir / ".claude"
        assert (claude_dir / "commands").exists()
        assert (claude_dir / "hooks").exists()
        assert (claude_dir / "lib").exists()
        assert (claude_dir / "lib" / "nested").exists()
        assert (claude_dir / "scripts").exists()
        assert (claude_dir / "skills").exists()

    def test_fresh_install_sets_script_permissions(self, tmp_path):
        """Test that fresh install sets executable permissions on scripts/.

        Current: FAILS - Enhanced permission handling doesn't exist
        """
        # Arrange: Plugin with scripts
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "scripts").mkdir()
        script = plugin_dir / "scripts" / "setup.py"
        script.write_text("#!/usr/bin/env python3\nprint('setup')")

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Act: Fresh install
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        orchestrator.fresh_install()

        # Assert: Script is executable
        dest_script = project_dir / ".claude" / "scripts" / "setup.py"
        assert dest_script.exists()

        import stat
        assert dest_script.stat().st_mode & stat.S_IXUSR

    def test_fresh_install_creates_installation_marker(self, tmp_path):
        """Test that fresh install creates marker file with metadata.

        Marker: .claude/.autonomous-dev-installed
        Contains: version, timestamp, files_installed, coverage

        Current: FAILS - Enhanced marker creation doesn't exist
        """
        # Arrange: Plugin directory
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "test.md").touch()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Act: Fresh install
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        result = orchestrator.fresh_install()

        # Assert: Marker file created
        marker = project_dir / ".claude" / ".autonomous-dev-installed"
        assert marker.exists()

        with open(marker) as f:
            metadata = json.load(f)

        assert "version" in metadata
        assert "timestamp" in metadata
        assert "files_installed" in metadata
        assert "coverage" in metadata

        assert metadata["files_installed"] == result.files_copied
        assert metadata["coverage"] == 100.0

    def test_fresh_install_validates_99_5_percent_coverage(self, tmp_path):
        """Test that fresh install validates >=99.5% coverage.

        Current: FAILS - Enhanced validation doesn't exist
        """
        # Arrange: Plugin with 100 files
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        for i in range(100):
            (plugin_dir / f"file{i}.txt").touch()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Act: Fresh install
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        result = orchestrator.fresh_install()

        # Assert: Coverage validated
        assert result.coverage >= 99.5
        assert result.status == "success"


class TestEnhancedUpgradeInstallation:
    """Test enhanced upgrade installation workflow."""

    def test_upgrade_creates_backup_before_changes(self, tmp_path):
        """Test that upgrade creates timestamped backup.

        Backup location: .claude/.backup-<timestamp>/

        Current: FAILS - Enhanced backup doesn't exist
        """
        # Arrange: Existing installation
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "test.md").write_text("v1.0")

        project_dir = tmp_path / "project"
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir(parents=True)

        (claude_dir / "commands").mkdir()
        (claude_dir / "commands" / "test.md").write_text("v0.9")

        # Act: Upgrade
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        result = orchestrator.upgrade()

        # Assert: Backup created
        backup_dirs = [d for d in claude_dir.iterdir() if d.name.startswith(".backup-")]
        assert len(backup_dirs) == 1

        backup_dir = backup_dirs[0]
        assert (backup_dir / "commands" / "test.md").exists()
        assert (backup_dir / "commands" / "test.md").read_text() == "v0.9"

        # Backup directory path returned
        assert result.backup_dir == backup_dir

    def test_upgrade_detects_user_customizations(self, tmp_path):
        """Test that upgrade detects user-modified files.

        User files (modified after installation marker):
        - Should be flagged
        - Should not be overwritten without consent

        Current: FAILS - Customization detection doesn't exist
        """
        # Arrange: Initial installation
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "hooks").mkdir()
        hook = plugin_dir / "hooks" / "custom.py"
        hook.write_text("# Original")

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        orchestrator.fresh_install()

        # Wait to ensure different timestamp
        time.sleep(0.1)

        # User modifies file
        dest_hook = project_dir / ".claude" / "hooks" / "custom.py"
        dest_hook.write_text("# User customized")

        # Plugin also updates file
        hook.write_text("# Plugin v2.0")

        # Act: Upgrade
        result = orchestrator.upgrade()

        # Assert: Customization detected
        assert hasattr(result, "customizations_detected")
        assert result.customizations_detected > 0
        assert "hooks/custom.py" in result.customized_files

    def test_upgrade_preserves_user_added_files(self, tmp_path):
        """Test that upgrade preserves files added by user.

        Files not in plugin source:
        - Should be preserved
        - Should not be deleted

        Current: FAILS - User file preservation doesn't exist
        """
        # Arrange: Existing installation
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "builtin.md").touch()

        project_dir = tmp_path / "project"
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir(parents=True)

        (claude_dir / "commands").mkdir()
        (claude_dir / "commands" / "builtin.md").touch()

        # User adds custom file
        (claude_dir / "commands" / "custom.md").write_text("# User command")

        # Act: Upgrade
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        orchestrator.upgrade()

        # Assert: User file preserved
        assert (claude_dir / "commands" / "custom.md").exists()
        assert (claude_dir / "commands" / "custom.md").read_text() == "# User command"

    def test_upgrade_adds_new_files_from_plugin(self, tmp_path):
        """Test that upgrade adds new files from plugin.

        Current: FAILS - Enhanced upgrade doesn't exist
        """
        # Arrange: Initial installation
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "old.md").touch()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        orchestrator.fresh_install()

        # Plugin adds new files
        (plugin_dir / "commands" / "new1.md").touch()
        (plugin_dir / "commands" / "new2.md").touch()

        (plugin_dir / "lib").mkdir()
        (plugin_dir / "lib" / "new_utils.py").touch()

        # Act: Upgrade
        result = orchestrator.upgrade()

        # Assert: New files added
        claude_dir = project_dir / ".claude"
        assert (claude_dir / "commands" / "new1.md").exists()
        assert (claude_dir / "commands" / "new2.md").exists()
        assert (claude_dir / "lib" / "new_utils.py").exists()

        # Result shows files added
        assert hasattr(result, "files_added")
        assert result.files_added >= 3


class TestEnhancedRollback:
    """Test enhanced rollback mechanism."""

    def test_rollback_restores_from_backup_on_failure(self, tmp_path):
        """Test that rollback restores from backup on installation failure.

        Current: FAILS - Enhanced rollback doesn't exist
        """
        # Arrange: Existing installation
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()

        project_dir = tmp_path / "project"
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir(parents=True)

        (claude_dir / "commands").mkdir()
        original_file = claude_dir / "commands" / "test.md"
        original_file.write_text("original content")

        # Create backup
        backup_dir = claude_dir / ".backup-test"
        backup_dir.mkdir()
        (backup_dir / "commands").mkdir()
        (backup_dir / "commands" / "test.md").write_text("original content")

        # Simulate failed installation (corrupted file)
        original_file.write_text("corrupted content")

        # Act: Rollback
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        result = orchestrator.rollback(backup_dir)

        # Assert: Original content restored
        assert result.status == "success"
        assert original_file.read_text() == "original content"

    def test_rollback_logs_restoration_details(self, tmp_path):
        """Test that rollback logs what was restored.

        Current: FAILS - Enhanced logging doesn't exist
        """
        # Arrange: Backup directory
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()

        project_dir = tmp_path / "project"
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir(parents=True)

        backup_dir = claude_dir / ".backup-test"
        backup_dir.mkdir()
        (backup_dir / "file1.txt").write_text("backup1")
        (backup_dir / "file2.txt").write_text("backup2")

        # Act: Rollback
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        result = orchestrator.rollback(backup_dir)

        # Assert: Logs restoration
        assert hasattr(result, "files_restored")
        assert result.files_restored >= 2

    def test_rollback_handles_missing_backup_gracefully(self, tmp_path):
        """Test that rollback handles missing backup without crash.

        Current: FAILS - Enhanced error handling doesn't exist
        """
        # Arrange: No backup
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        nonexistent_backup = tmp_path / "nonexistent"

        # Act: Attempt rollback
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        result = orchestrator.rollback(nonexistent_backup)

        # Assert: Returns failure status but doesn't crash
        assert result.status == "failure" or result is False


class TestMarketplaceIntegration:
    """Test marketplace directory integration."""

    def test_auto_detects_marketplace_directory(self, tmp_path, monkeypatch):
        """Test that orchestrator auto-detects marketplace directory.

        Marketplace path:
        ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/

        Current: FAILS - Auto-detection doesn't exist
        """
        # Arrange: Set HOME to tmp_path
        monkeypatch.setenv("HOME", str(tmp_path))

        # Create marketplace structure
        marketplace_dir = tmp_path / ".claude" / "plugins" / "marketplaces" / "autonomous-dev"
        plugin_dir = marketplace_dir / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "test.md").touch()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Act: Auto-detect
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator.auto_detect(project_dir)
        result = orchestrator.fresh_install()

        # Assert: Installed from marketplace
        assert result.status == "success"
        assert (project_dir / ".claude" / "commands" / "test.md").exists()

    def test_from_marketplace_constructor(self, tmp_path):
        """Test that orchestrator can be created from marketplace path.

        Current: FAILS - from_marketplace() doesn't exist
        """
        # Arrange: Marketplace structure
        marketplace_dir = tmp_path / "marketplace"
        plugin_dir = marketplace_dir / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "test.md").touch()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Act: Create from marketplace
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator.from_marketplace(marketplace_dir, project_dir)
        result = orchestrator.fresh_install()

        # Assert: Installed successfully
        assert result.status == "success"
        assert (project_dir / ".claude" / "commands" / "test.md").exists()


class TestProgressReporting:
    """Test installation progress reporting."""

    def test_reports_progress_during_installation(self, tmp_path):
        """Test that orchestrator reports progress during installation.

        Current: FAILS - Progress reporting doesn't exist
        """
        # Arrange: Plugin with multiple files
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        for i in range(50):
            (plugin_dir / f"file{i}.txt").touch()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Progress tracking
        progress_updates = []

        def progress_callback(current, total, message):
            progress_updates.append({
                "current": current,
                "total": total,
                "message": message
            })

        # Act: Install with progress
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        orchestrator.fresh_install(progress_callback=progress_callback)

        # Assert: Progress reported
        assert len(progress_updates) > 0

        # Should have discovery, copy, validation phases
        messages = [u["message"] for u in progress_updates]
        assert any("discover" in m.lower() for m in messages)
        assert any("copy" in m.lower() or "installing" in m.lower() for m in messages)

    def test_shows_percentage_progress(self, tmp_path, capsys):
        """Test that orchestrator shows percentage progress.

        Output:
        [1/100] Copying file1.txt... (1%)
        [50/100] Copying file50.txt... (50%)
        [100/100] Copying file100.txt... (100%)

        Current: FAILS - Percentage display doesn't exist
        """
        # Arrange: Plugin with files
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        for i in range(20):
            (plugin_dir / f"file{i}.txt").touch()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Act: Install with progress display
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        orchestrator.fresh_install(show_progress=True)

        # Assert: Progress shown
        captured = capsys.readouterr()
        output = captured.out

        # Should show progress indicators
        assert "%" in output or "progress" in output.lower()


class TestInstallationEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_partial_installation_failure(self, tmp_path):
        """Test that orchestrator handles partial installation failure.

        Scenario:
        - Installation starts
        - Some files copied
        - Error occurs
        - Rollback restores original state

        Current: FAILS - Enhanced error handling doesn't exist
        """
        # Arrange: Plugin with files
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "file1.txt").touch()
        (plugin_dir / "file2.txt").touch()

        # Create problematic file
        problem_file = plugin_dir / "problem.txt"
        problem_file.touch()
        problem_file.chmod(0o000)  # Unreadable

        project_dir = tmp_path / "project"
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir(parents=True)

        # Existing content to preserve
        (claude_dir / "existing.txt").write_text("preserve me")

        try:
            # Act: Attempt installation
            from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator, InstallError

            orchestrator = InstallOrchestrator(plugin_dir, project_dir)

            with pytest.raises(InstallError):
                orchestrator.fresh_install()

            # Assert: Rollback occurred
            assert (claude_dir / "existing.txt").exists()
            assert (claude_dir / "existing.txt").read_text() == "preserve me"

        finally:
            # Cleanup
            try:
                problem_file.chmod(0o644)
            except:
                pass

    def test_validates_plugin_directory_exists(self, tmp_path):
        """Test that orchestrator validates plugin directory exists.

        Current: FAILS - Enhanced validation doesn't exist
        """
        # Arrange: Nonexistent plugin directory
        plugin_dir = tmp_path / "nonexistent"
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Act & Assert: Validation error
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator, InstallError

        with pytest.raises((InstallError, FileNotFoundError)) as exc_info:
            orchestrator = InstallOrchestrator(plugin_dir, project_dir)
            orchestrator.fresh_install()

        assert "not found" in str(exc_info.value).lower() or "does not exist" in str(exc_info.value).lower()

    def test_creates_claude_directory_if_missing(self, tmp_path):
        """Test that orchestrator creates .claude directory if missing.

        Current: FAILS - Enhanced setup doesn't exist
        """
        # Arrange: Project without .claude
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "test.txt").touch()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Act: Fresh install
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        orchestrator.fresh_install()

        # Assert: .claude created
        assert (project_dir / ".claude").exists()
        assert (project_dir / ".claude" / "test.txt").exists()

    def test_handles_concurrent_installations(self, tmp_path):
        """Test that orchestrator handles concurrent installation attempts.

        Lock file: .claude/.installation-lock

        Current: FAILS - Concurrency control doesn't exist
        """
        # Arrange: Plugin directory
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "test.txt").touch()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create lock file (simulate concurrent installation)
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()
        lock_file = claude_dir / ".installation-lock"
        lock_file.touch()

        # Act: Attempt installation
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator, InstallError

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)

        # Should detect lock and wait or fail gracefully
        try:
            result = orchestrator.fresh_install()
            # If it succeeds, lock should be cleared
            assert not lock_file.exists() or result.status == "success"
        except InstallError as e:
            # Or it should report lock conflict
            assert "lock" in str(e).lower() or "concurrent" in str(e).lower()
