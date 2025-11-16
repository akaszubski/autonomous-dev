"""
TDD Integration Tests for Installation System (Issue #80 - Phase 4)

Tests the complete installation workflow including fresh install,
upgrades, rollback, and marketplace integration.

Current State (RED PHASE):
- Complete installation system doesn't exist yet
- All tests should FAIL

Test Coverage:
- Fresh installation workflow
- Upgrade with preservation of customizations
- Rollback on failure
- Marketplace distribution flow
- Health check validation
"""

import pytest
from pathlib import Path
import subprocess
import json
import shutil


class TestFreshInstallation:
    """Test fresh installation workflow."""

    def test_fresh_install_copies_all_files(self, tmp_path):
        """Test that fresh install copies all 201+ files.

        Workflow:
        1. Run install.sh
        2. Verify all files copied
        3. Validate 100% coverage

        Current: FAILS - New install.sh doesn't exist
        """
        # Arrange: Create plugin structure
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Create comprehensive structure
        categories = {
            "commands": 20,
            "hooks": 42,
            "agents": 20,
            "lib": 30,
            "scripts": 10,
        }

        for category, count in categories.items():
            cat_dir = plugin_dir / category
            cat_dir.mkdir()
            for i in range(count):
                ext = ".md" if category in ["commands", "agents"] else ".py"
                (cat_dir / f"{category}{i}{ext}").touch()

        # Create skills (27 skills × 5 files = 135 files)
        skills_dir = plugin_dir / "skills"
        skills_dir.mkdir()
        for i in range(27):
            skill = skills_dir / f"skill{i}.skill"
            skill.mkdir()
            (skill / "skill.md").touch()
            (skill / "docs").mkdir()
            (skill / "docs" / "guide.md").touch()
            (skill / "examples").mkdir()
            (skill / "examples" / "example.md").touch()

        # Total: 20 + 42 + 20 + 30 + 10 + 135 = 257 files

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Act: Run fresh install
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        result = orchestrator.fresh_install()

        # Assert: All files copied
        assert result.status == "success"
        assert result.files_copied == 257
        assert result.coverage == 100.0

        # Verify directory structure
        assert (project_dir / ".claude" / "commands").exists()
        assert (project_dir / ".claude" / "hooks").exists()
        assert (project_dir / ".claude" / "lib").exists()
        assert (project_dir / ".claude" / "scripts").exists()

    def test_fresh_install_creates_directory_structure(self, tmp_path):
        """Test that fresh install creates .claude directory structure.

        Expected structure:
        .claude/
        ├── commands/
        ├── hooks/
        ├── agents/
        ├── skills/
        ├── lib/
        ├── scripts/
        └── templates/

        Current: FAILS - InstallOrchestrator doesn't exist
        """
        # Arrange: Plugin with minimal structure
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "test.md").touch()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Act: Fresh install
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        orchestrator.fresh_install()

        # Assert: Directory structure created
        claude_dir = project_dir / ".claude"
        assert claude_dir.exists()
        assert (claude_dir / "commands").exists()
        assert (claude_dir / "commands" / "test.md").exists()

    def test_fresh_install_sets_executable_permissions(self, tmp_path):
        """Test that fresh install sets executable permissions on scripts.

        Current: FAILS - InstallOrchestrator doesn't exist
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

        import os
        import stat
        file_stat = dest_script.stat()
        assert file_stat.st_mode & stat.S_IXUSR

    def test_fresh_install_creates_marker_file(self, tmp_path):
        """Test that fresh install creates marker file for tracking.

        Marker file: .claude/.autonomous-dev-installed
        Contains: version, timestamp, file count

        Current: FAILS - InstallOrchestrator doesn't exist
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
        orchestrator.fresh_install()

        # Assert: Marker file created
        marker = project_dir / ".claude" / ".autonomous-dev-installed"
        assert marker.exists()

        with open(marker) as f:
            metadata = json.load(f)

        assert "version" in metadata
        assert "timestamp" in metadata
        assert "files_installed" in metadata
        assert metadata["files_installed"] > 0


class TestUpgradeInstallation:
    """Test upgrade installation workflow."""

    def test_upgrade_preserves_user_customizations(self, tmp_path):
        """Test that upgrade preserves user-modified files.

        Scenario:
        1. Initial install with default files
        2. User modifies .claude/hooks/custom.py
        3. Upgrade to new version
        4. User customization preserved

        Current: FAILS - Upgrade system doesn't exist
        """
        # Arrange: Initial installation
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "hooks").mkdir()
        (plugin_dir / "hooks" / "auto_format.py").write_text("# Default hook")

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        orchestrator.fresh_install()

        # User customizes hook
        custom_hook = project_dir / ".claude" / "hooks" / "custom.py"
        custom_hook.write_text("# User custom hook\ndef custom(): pass")

        # Update plugin with new files
        (plugin_dir / "hooks" / "new_hook.py").write_text("# New hook")

        # Act: Upgrade
        result = orchestrator.upgrade()

        # Assert: User customization preserved
        assert custom_hook.exists()
        assert custom_hook.read_text() == "# User custom hook\ndef custom(): pass"

        # New files added
        assert (project_dir / ".claude" / "hooks" / "new_hook.py").exists()

    def test_upgrade_updates_modified_plugin_files(self, tmp_path):
        """Test that upgrade updates files modified in plugin.

        Scenario:
        1. Install v1 with hook.py (version A)
        2. Plugin updates hook.py (version B)
        3. Upgrade
        4. hook.py updated to version B

        Current: FAILS - Upgrade system doesn't exist
        """
        # Arrange: Initial installation
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "hooks").mkdir()
        hook = plugin_dir / "hooks" / "auto_format.py"
        hook.write_text("# Version 1.0")

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        orchestrator.fresh_install()

        # Plugin updated
        hook.write_text("# Version 2.0\n# New feature added")

        # Act: Upgrade
        result = orchestrator.upgrade()

        # Assert: File updated
        dest_hook = project_dir / ".claude" / "hooks" / "auto_format.py"
        assert "Version 2.0" in dest_hook.read_text()
        assert "New feature added" in dest_hook.read_text()

    def test_upgrade_detects_conflicts(self, tmp_path):
        """Test that upgrade detects conflicts between user edits and plugin updates.

        Current: FAILS - Upgrade system doesn't exist
        """
        # Arrange: Initial installation
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "hooks").mkdir()
        hook = plugin_dir / "hooks" / "shared.py"
        hook.write_text("# Original version")

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        orchestrator.fresh_install()

        # User modifies file
        dest_hook = project_dir / ".claude" / "hooks" / "shared.py"
        dest_hook.write_text("# User modified version")

        # Plugin also modifies file
        hook.write_text("# Plugin updated version")

        # Act: Upgrade (should detect conflict)
        result = orchestrator.upgrade()

        # Assert: Conflict detected
        assert result["conflicts"] > 0
        assert "shared.py" in result["conflict_list"]

    def test_upgrade_creates_backup_before_changes(self, tmp_path):
        """Test that upgrade creates backup before making changes.

        Backup location: .claude/.backup-<timestamp>/

        Current: FAILS - Upgrade system doesn't exist
        """
        # Arrange: Existing installation
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "test.md").write_text("original")

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)
        orchestrator.fresh_install()

        # Update plugin
        (plugin_dir / "commands" / "test.md").write_text("updated")

        # Act: Upgrade
        result = orchestrator.upgrade()

        # Assert: Backup created
        claude_dir = project_dir / ".claude"
        backup_dirs = [d for d in claude_dir.iterdir() if d.name.startswith(".backup-")]
        assert len(backup_dirs) == 1

        backup_file = backup_dirs[0] / "commands" / "test.md"
        assert backup_file.exists()
        assert backup_file.read_text() == "original"


class TestRollbackMechanism:
    """Test rollback on installation failure."""

    def test_rollback_on_copy_failure(self, tmp_path):
        """Test that installation rolls back on copy failure.

        Scenario:
        1. Start installation
        2. Copy fails midway
        3. Rollback restores original state

        Current: FAILS - Rollback system doesn't exist
        """
        # Arrange: Plugin with files
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "test1.md").touch()
        (plugin_dir / "commands" / "test2.md").touch()

        # Create protected file that will cause copy to fail
        (plugin_dir / "commands" / "protected.md").touch()
        (plugin_dir / "commands" / "protected.md").chmod(0o000)

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create existing installation
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "existing.txt").write_text("should be preserved")

        # Act: Attempt installation (should fail)
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator, InstallError

        orchestrator = InstallOrchestrator(plugin_dir, project_dir)

        try:
            orchestrator.fresh_install()
            pytest.fail("Should have raised InstallError")
        except InstallError as e:
            # Expected failure
            pass
        finally:
            # Cleanup: Restore permissions
            (plugin_dir / "commands" / "protected.md").chmod(0o644)

        # Assert: Rollback occurred
        assert (claude_dir / "existing.txt").exists()
        assert (claude_dir / "existing.txt").read_text() == "should be preserved"

        # Partial installation files removed
        assert not (claude_dir / "commands" / "test1.md").exists()

    def test_rollback_restores_from_backup(self, tmp_path):
        """Test that rollback restores from backup on upgrade failure.

        Current: FAILS - Rollback system doesn't exist
        """
        # Arrange: Existing installation
        project_dir = tmp_path / "project"
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir(parents=True)

        (claude_dir / "commands").mkdir()
        original_file = claude_dir / "commands" / "test.md"
        original_file.write_text("original content")

        # Create backup
        backup_dir = claude_dir / ".backup-20241117"
        backup_dir.mkdir()
        (backup_dir / "commands").mkdir()
        (backup_dir / "commands" / "test.md").write_text("original content")

        # Simulate failed upgrade (file partially modified)
        original_file.write_text("corrupted content")

        # Act: Rollback
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator(Path("/tmp/fake"), project_dir)
        orchestrator.rollback(backup_dir)

        # Assert: Original content restored
        assert original_file.read_text() == "original content"


class TestMarketplaceIntegration:
    """Test marketplace distribution workflow."""

    def test_install_from_marketplace_directory(self, tmp_path):
        """Test installation from marketplace directory structure.

        Marketplace path:
        ~/.claude/plugins/marketplaces/autonomous-dev/plugins/autonomous-dev/

        Current: FAILS - Marketplace integration doesn't exist
        """
        # Arrange: Create marketplace structure
        marketplace_dir = tmp_path / ".claude" / "plugins" / "marketplaces" / "autonomous-dev"
        plugin_dir = marketplace_dir / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "auto-implement.md").touch()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Act: Install from marketplace
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator.from_marketplace(
            marketplace_dir, project_dir
        )
        result = orchestrator.fresh_install()

        # Assert: Installed successfully
        assert result.status == "success"
        assert (project_dir / ".claude" / "commands" / "auto-implement.md").exists()

    def test_auto_detects_marketplace_directory(self, tmp_path, monkeypatch):
        """Test that installer auto-detects marketplace directory.

        Current: FAILS - Auto-detection doesn't exist
        """
        # Arrange: Set HOME to tmp_path
        monkeypatch.setenv("HOME", str(tmp_path))

        marketplace_dir = tmp_path / ".claude" / "plugins" / "marketplaces" / "autonomous-dev"
        plugin_dir = marketplace_dir / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "test.md").touch()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Act: Auto-detect and install
        from plugins.autonomous_dev.lib.install_orchestrator import InstallOrchestrator

        orchestrator = InstallOrchestrator.auto_detect(project_dir)
        result = orchestrator.fresh_install()

        # Assert: Installed from detected location
        assert result.status == "success"
        assert (project_dir / ".claude" / "commands" / "test.md").exists()


class TestHealthCheckIntegration:
    """Test /health-check integration with installation."""

    def test_health_check_validates_installation(self, tmp_path):
        """Test that /health-check validates installation completeness.

        Current: FAILS - Health check integration doesn't exist
        """
        # Arrange: Incomplete installation
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        for i in range(10):
            (plugin_dir / f"file{i}.txt").touch()

        project_dir = tmp_path / "project"
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir(parents=True)

        # Only 7 of 10 files
        for i in range(7):
            (claude_dir / f"file{i}.txt").touch()

        # Act: Run health check
        from plugins.autonomous_dev.hooks.health_check import run_health_check

        result = run_health_check(project_dir)

        # Assert: Installation issues detected
        assert result["installation"]["status"] == "incomplete"
        assert result["installation"]["coverage"] == 70.0
        assert result["installation"]["missing_files"] == 3

    def test_health_check_reports_perfect_installation(self, tmp_path):
        """Test that health check reports success for complete installation.

        Current: FAILS - Health check integration doesn't exist
        """
        # Arrange: Complete installation
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        files = ["commands/test.md", "lib/utils.py", "scripts/setup.py"]
        for file_path in files:
            file = plugin_dir / file_path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.touch()

        project_dir = tmp_path / "project"
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir(parents=True)

        for file_path in files:
            file = claude_dir / file_path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.touch()

        # Act: Run health check
        from plugins.autonomous_dev.hooks.health_check import run_health_check

        result = run_health_check(project_dir)

        # Assert: Perfect installation
        assert result["installation"]["status"] == "complete"
        assert result["installation"]["coverage"] == 100.0


class TestBashScriptIntegration:
    """Test Bash script wrapper for installation."""

    def test_bash_script_runs_installation(self, tmp_path):
        """Test that install.sh bash script runs installation.

        Current: FAILS - New install.sh doesn't exist
        """
        # Arrange: Create plugin structure
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "test.md").touch()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create install.sh script
        install_script = project_dir / "install.sh"
        install_script.write_text("""#!/usr/bin/env bash
python -m lib.install_orchestrator "$@"
""")
        install_script.chmod(0o755)

        # Act: Run script
        result = subprocess.run(
            [str(install_script)],
            cwd=project_dir,
            capture_output=True,
            text=True,
            env={
                "PLUGIN_DIR": str(plugin_dir),
                "PROJECT_DIR": str(project_dir),
            }
        )

        # Assert: Installation succeeded
        assert result.returncode == 0
        assert (project_dir / ".claude" / "commands" / "test.md").exists()

    def test_bash_script_reports_progress(self, tmp_path):
        """Test that install.sh reports progress during installation.

        Expected output:
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        🚀 Autonomous Dev Plugin - Installation
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        📊 Discovering files...
        ✅ Found 201 files

        📋 Copying files...
        [1/201] commands/auto-implement.md... ✅
        ...

        Current: FAILS - New install.sh doesn't exist
        """
        # Arrange: Plugin with files
        plugin_dir = tmp_path / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        (plugin_dir / "commands").mkdir()
        (plugin_dir / "commands" / "test.md").touch()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        install_script = tmp_path / "install.sh"
        # Mock script that shows progress
        install_script.write_text("""#!/usr/bin/env bash
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Autonomous Dev Plugin - Installation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Discovering files..."
echo "✅ Found 1 files"
""")
        install_script.chmod(0o755)

        # Act: Run script
        result = subprocess.run(
            [str(install_script)],
            capture_output=True,
            text=True
        )

        # Assert: Progress displayed
        assert "Installation" in result.stdout
        assert "Discovering files" in result.stdout
        assert "Found 1 files" in result.stdout

    def test_bash_script_validates_prerequisites(self, tmp_path):
        """Test that install.sh validates prerequisites before installation.

        Prerequisites:
        - Python 3.8+
        - Plugin installed via /plugin install
        - Write permissions on project directory

        Current: FAILS - Prerequisite checks don't exist
        """
        # Arrange: Missing plugin directory
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        install_script = tmp_path / "install.sh"
        install_script.write_text("""#!/usr/bin/env bash
if [ ! -d "$PLUGIN_DIR" ]; then
    echo "❌ Plugin not found"
    echo "Please install via: /plugin install autonomous-dev"
    exit 1
fi
""")
        install_script.chmod(0o755)

        # Act: Run script
        result = subprocess.run(
            [str(install_script)],
            capture_output=True,
            text=True,
            env={"PLUGIN_DIR": str(tmp_path / "nonexistent")}
        )

        # Assert: Prerequisite check failed
        assert result.returncode == 1
        assert "Plugin not found" in result.stdout
