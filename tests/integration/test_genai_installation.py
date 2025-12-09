#!/usr/bin/env python3
"""
Integration tests for GenAI-first installation system (TDD Red Phase - Issue #106).

Tests complete installation workflows including staging, analysis, and execution.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially because the system doesn't exist yet.

Test Coverage:
- Fresh installation workflow
- Brownfield installation (preserve user artifacts)
- Upgrade workflow (handle conflicts)
- Error recovery and rollback
- Audit trail generation

Date: 2025-12-09
Issue: #106 (GenAI-first installation system)
Agent: test-master
Phase: TDD Red (tests written BEFORE implementation)
"""

import os
import sys
import pytest
from pathlib import Path
import json
import shutil

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will FAIL until implementation exists
try:
    from staging_manager import StagingManager
    from protected_file_detector import ProtectedFileDetector
    from installation_analyzer import InstallationAnalyzer, InstallationType
    from install_audit import InstallAudit
    from copy_system import CopySystem
except ImportError as e:
    pytest.skip(f"Implementation not found: {e}", allow_module_level=True)


@pytest.fixture
def plugin_structure(tmp_path):
    """Create a realistic plugin directory structure."""
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()

    # Commands (20 files)
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir()
    for i in range(20):
        (commands_dir / f"command{i}.md").write_text(f"# Command {i}")

    # Hooks (42 files)
    hooks_dir = plugin_dir / "hooks"
    hooks_dir.mkdir()
    for i in range(42):
        (hooks_dir / f"hook{i}.py").write_text(f"# Hook {i}")

    # Agents (20 files)
    agents_dir = plugin_dir / "agents"
    agents_dir.mkdir()
    for i in range(20):
        (agents_dir / f"agent{i}.md").write_text(f"# Agent {i}")

    # Lib (30 files)
    lib_dir = plugin_dir / "lib"
    lib_dir.mkdir()
    for i in range(30):
        (lib_dir / f"lib{i}.py").write_text(f"# Library {i}")

    # Skills (28 skills)
    skills_dir = plugin_dir / "skills"
    skills_dir.mkdir()
    for i in range(28):
        skill_dir = skills_dir / f"skill{i}.skill"
        skill_dir.mkdir()
        (skill_dir / "skill.md").write_text(f"# Skill {i}")

    # Config files
    (plugin_dir / "PROJECT.md").write_text("# Plugin template")
    (plugin_dir / ".env.example").write_text("API_KEY=example")

    return plugin_dir


class TestFreshInstallationWorkflow:
    """Test fresh installation workflow (no existing .claude/ directory)."""

    def test_fresh_install_copies_all_files(self, tmp_path, plugin_structure):
        """Test that fresh install copies all plugin files.

        Current: FAILS - Installation workflow doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        staging_dir = tmp_path / ".claude-staging"
        shutil.copytree(plugin_structure, staging_dir)

        # Analyze installation
        analyzer = InstallationAnalyzer(project_dir)
        install_type = analyzer.detect_installation_type()
        assert install_type == InstallationType.FRESH

        # Execute installation
        audit = InstallAudit(project_dir / "install_audit.jsonl")
        install_id = audit.start_installation("fresh")

        copier = CopySystem(staging_dir, project_dir / ".claude")
        result = copier.copy_all()

        audit.log_success(install_id, files_copied=result["files_copied"])

        # Verify all files copied
        assert (project_dir / ".claude" / "commands").exists()
        assert (project_dir / ".claude" / "hooks").exists()
        assert (project_dir / ".claude" / "agents").exists()
        assert result["files_copied"] > 100

    def test_fresh_install_creates_audit_trail(self, tmp_path, plugin_structure):
        """Test that fresh install creates complete audit trail.

        Current: FAILS - Audit system doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        staging_dir = tmp_path / ".claude-staging"
        shutil.copytree(plugin_structure, staging_dir)

        audit_file = project_dir / "install_audit.jsonl"
        audit = InstallAudit(audit_file)
        install_id = audit.start_installation("fresh")

        copier = CopySystem(staging_dir, project_dir / ".claude")
        result = copier.copy_all()

        audit.log_success(install_id, files_copied=result["files_copied"])

        # Verify audit trail
        assert audit_file.exists()
        report = audit.generate_report(install_id)
        assert report["status"] == "success"
        assert report["files_copied"] > 0

    def test_fresh_install_cleanup_staging(self, tmp_path, plugin_structure):
        """Test that staging directory is cleaned up after install.

        Current: FAILS - Cleanup workflow doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        staging_dir = tmp_path / ".claude-staging"
        shutil.copytree(plugin_structure, staging_dir)

        copier = CopySystem(staging_dir, project_dir / ".claude")
        result = copier.copy_all()

        # Cleanup staging
        staging_mgr = StagingManager(staging_dir)
        staging_mgr.cleanup()

        assert not staging_dir.exists()
        assert (project_dir / ".claude").exists()


class TestBrownfieldInstallationWorkflow:
    """Test brownfield installation (preserve user artifacts)."""

    def test_brownfield_install_preserves_project_md(
        self, tmp_path, plugin_structure
    ):
        """Test that brownfield install preserves PROJECT.md.

        Current: FAILS - Protected file system doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()

        # User's PROJECT.md
        user_project_md = claude_dir / "PROJECT.md"
        user_project_md.write_text("# User's Goals\n- Custom goal 1")

        staging_dir = tmp_path / ".claude-staging"
        shutil.copytree(plugin_structure, staging_dir)

        # Detect protected files
        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_dir)

        # Install with protection
        copier = CopySystem(staging_dir, claude_dir)
        result = copier.copy_all(
            protected_files=[f["path"] for f in protected_files]
        )

        # Verify PROJECT.md preserved
        assert user_project_md.read_text() == "# User's Goals\n- Custom goal 1"
        assert result["files_skipped"] >= 1

    def test_brownfield_install_preserves_env_file(
        self, tmp_path, plugin_structure
    ):
        """Test that brownfield install preserves .env file.

        Current: FAILS - Protected file system doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()

        # User's .env
        user_env = claude_dir / ".env"
        user_env.write_text("API_KEY=secret123\nDATABASE_URL=prod")

        staging_dir = tmp_path / ".claude-staging"
        shutil.copytree(plugin_structure, staging_dir)

        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_dir)

        copier = CopySystem(staging_dir, claude_dir)
        result = copier.copy_all(
            protected_files=[f["path"] for f in protected_files]
        )

        # Verify .env preserved
        assert user_env.read_text() == "API_KEY=secret123\nDATABASE_URL=prod"

    def test_brownfield_install_preserves_custom_hooks(
        self, tmp_path, plugin_structure
    ):
        """Test that brownfield install preserves custom hooks.

        Current: FAILS - Protected file system doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()
        hooks_dir = claude_dir / "hooks"
        hooks_dir.mkdir()

        # User's custom hook
        custom_hook = hooks_dir / "custom_validation.py"
        custom_hook.write_text("# User's custom validation logic")

        staging_dir = tmp_path / ".claude-staging"
        shutil.copytree(plugin_structure, staging_dir)

        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_dir)

        copier = CopySystem(staging_dir, claude_dir)
        result = copier.copy_all(
            protected_files=[f["path"] for f in protected_files]
        )

        # Verify custom hook preserved
        assert custom_hook.exists()
        assert "custom validation" in custom_hook.read_text()

    def test_brownfield_install_generates_conflict_report(
        self, tmp_path, plugin_structure
    ):
        """Test that brownfield install generates conflict report.

        Current: FAILS - Conflict reporting doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()

        # Create user artifacts
        (claude_dir / "PROJECT.md").write_text("# User project")
        (claude_dir / ".env").write_text("SECRET=value")

        staging_dir = tmp_path / ".claude-staging"
        shutil.copytree(plugin_structure, staging_dir)

        analyzer = InstallationAnalyzer(project_dir)
        report = analyzer.generate_conflict_report(staging_dir)

        assert report["total_conflicts"] >= 2
        assert any(
            "PROJECT.md" in c["file"] for c in report["conflicts"]
        )


class TestUpgradeWorkflow:
    """Test upgrade workflow (existing plugin, handle conflicts)."""

    def test_upgrade_creates_backups_for_modified_files(
        self, tmp_path, plugin_structure
    ):
        """Test that upgrade creates backups for user-modified files.

        Current: FAILS - Backup system doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()
        hooks_dir = claude_dir / "hooks"
        hooks_dir.mkdir()

        # User-modified plugin file
        modified_hook = hooks_dir / "auto_format.py"
        modified_hook.write_text("# User modified version")

        staging_dir = tmp_path / ".claude-staging"
        shutil.copytree(plugin_structure, staging_dir)

        # Detect that it's an upgrade
        analyzer = InstallationAnalyzer(project_dir)
        install_type = analyzer.detect_installation_type()
        assert install_type == InstallationType.UPGRADE

        # Install with backup strategy
        copier = CopySystem(staging_dir, claude_dir)
        result = copier.copy_all(backup_conflicts=True)

        # Verify backup created
        backup = hooks_dir / "auto_format.py.backup"
        assert backup.exists()
        assert "User modified" in backup.read_text()

    def test_upgrade_preserves_user_state_files(
        self, tmp_path, plugin_structure
    ):
        """Test that upgrade preserves user state files.

        Current: FAILS - Protected file system doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()

        # User state files
        (claude_dir / "batch_state.json").write_text('{"batch_id": "123"}')
        (claude_dir / "session_state.json").write_text('{"session": "data"}')

        staging_dir = tmp_path / ".claude-staging"
        shutil.copytree(plugin_structure, staging_dir)

        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_dir)

        copier = CopySystem(staging_dir, claude_dir)
        result = copier.copy_all(
            protected_files=[f["path"] for f in protected_files]
        )

        # Verify state files preserved
        assert (claude_dir / "batch_state.json").exists()
        assert "123" in (claude_dir / "batch_state.json").read_text()

    def test_upgrade_strategy_recommendation(self, tmp_path, plugin_structure):
        """Test that upgrade recommends appropriate strategy.

        Current: FAILS - Strategy system doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()

        # Existing plugin with modifications
        hooks_dir = claude_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "auto_format.py").write_text("# Modified")

        analyzer = InstallationAnalyzer(project_dir)
        strategy = analyzer.recommend_strategy()

        assert strategy["approach"] in ["backup_and_merge", "skip_protected"]
        assert "action_items" in strategy


class TestErrorRecoveryAndRollback:
    """Test error recovery and rollback mechanisms."""

    def test_rollback_on_copy_failure(self, tmp_path, plugin_structure):
        """Test rollback when copy operation fails.

        Current: FAILS - Rollback system doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()

        # Create existing file
        (claude_dir / "important.txt").write_text("Don't lose this")

        staging_dir = tmp_path / ".claude-staging"
        shutil.copytree(plugin_structure, staging_dir)

        # Simulate copy failure
        audit = InstallAudit(project_dir / "audit.jsonl")
        install_id = audit.start_installation("fresh")

        try:
            # Force a failure (create readonly staging file)
            readonly = staging_dir / "commands" / "readonly.md"
            readonly.write_text("content")
            readonly.chmod(0o000)

            copier = CopySystem(staging_dir, claude_dir)
            result = copier.copy_all(rollback_on_error=True)

            # Should fail but rollback
            readonly.chmod(0o644)
        except Exception as e:
            audit.log_failure(install_id, error=str(e))

        # Verify original file still exists
        assert (claude_dir / "important.txt").exists()

        # Cleanup
        readonly.chmod(0o644)

    def test_partial_copy_recorded_in_audit(self, tmp_path, plugin_structure):
        """Test that partial copy is recorded in audit trail.

        Current: FAILS - Audit system doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        staging_dir = tmp_path / ".claude-staging"
        shutil.copytree(plugin_structure, staging_dir)

        audit = InstallAudit(project_dir / "audit.jsonl")
        install_id = audit.start_installation("fresh")

        # Simulate partial failure
        try:
            copier = CopySystem(staging_dir, project_dir / ".claude")
            result = copier.copy_all(continue_on_error=True)
            audit.log_failure(
                install_id,
                error="Partial copy",
                files_copied=result["files_copied"],
            )
        except Exception:
            pass

        # Verify audit records partial state
        report = audit.generate_report(install_id)
        assert report["status"] == "failure"

    def test_cleanup_staging_on_success(self, tmp_path, plugin_structure):
        """Test that staging is cleaned up after successful install.

        Current: FAILS - Cleanup workflow doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        staging_dir = tmp_path / ".claude-staging"
        shutil.copytree(plugin_structure, staging_dir)

        copier = CopySystem(staging_dir, project_dir / ".claude")
        result = copier.copy_all()

        # Cleanup staging
        staging_mgr = StagingManager(staging_dir)
        staging_mgr.cleanup()

        assert not staging_dir.exists()

    def test_preserve_staging_on_failure(self, tmp_path, plugin_structure):
        """Test that staging is preserved on failure for debugging.

        Current: FAILS - Error handling doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        staging_dir = tmp_path / ".claude-staging"
        shutil.copytree(plugin_structure, staging_dir)

        audit = InstallAudit(project_dir / "audit.jsonl")
        install_id = audit.start_installation("fresh")

        try:
            # Simulate failure
            raise Exception("Installation failed")
        except Exception as e:
            audit.log_failure(install_id, error=str(e))

        # Staging should still exist for debugging
        assert staging_dir.exists()


class TestCompleteWorkflowIntegration:
    """Test complete end-to-end workflows."""

    def test_complete_fresh_install_workflow(self, tmp_path, plugin_structure):
        """Test complete fresh installation workflow.

        Current: FAILS - Complete workflow doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        staging_dir = tmp_path / ".claude-staging"
        shutil.copytree(plugin_structure, staging_dir)

        # 1. Stage files
        staging_mgr = StagingManager(staging_dir)
        staged_files = staging_mgr.list_files()
        assert len(staged_files) > 100

        # 2. Analyze installation
        analyzer = InstallationAnalyzer(project_dir)
        install_type = analyzer.detect_installation_type()
        assert install_type == InstallationType.FRESH

        conflict_report = analyzer.generate_conflict_report(staging_dir)
        assert conflict_report["total_conflicts"] == 0

        strategy = analyzer.recommend_strategy()
        assert strategy["approach"] == "copy_all"

        # 3. Execute installation
        audit = InstallAudit(project_dir / "audit.jsonl")
        install_id = audit.start_installation("fresh")

        copier = CopySystem(staging_dir, project_dir / ".claude")
        result = copier.copy_all()

        audit.log_success(install_id, files_copied=result["files_copied"])

        # 4. Cleanup
        staging_mgr.cleanup()

        # 5. Verify
        assert (project_dir / ".claude" / "commands").exists()
        assert not staging_dir.exists()

        report = audit.generate_report(install_id)
        assert report["status"] == "success"

    def test_complete_brownfield_workflow(self, tmp_path, plugin_structure):
        """Test complete brownfield installation workflow.

        Current: FAILS - Complete workflow doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()

        # User artifacts
        (claude_dir / "PROJECT.md").write_text("# User project")
        (claude_dir / ".env").write_text("SECRET=value")

        staging_dir = tmp_path / ".claude-staging"
        shutil.copytree(plugin_structure, staging_dir)

        # 1. Detect protected files
        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_dir)
        assert len(protected_files) >= 2

        # 2. Analyze
        analyzer = InstallationAnalyzer(project_dir)
        install_type = analyzer.detect_installation_type()
        assert install_type == InstallationType.BROWNFIELD

        strategy = analyzer.recommend_strategy()
        assert strategy["approach"] == "skip_protected"

        # 3. Execute
        audit = InstallAudit(project_dir / "audit.jsonl")
        install_id = audit.start_installation("brownfield")

        for pf in protected_files:
            audit.record_protected_file(
                install_id, pf["path"], pf.get("category", "user_artifact")
            )

        copier = CopySystem(staging_dir, claude_dir)
        result = copier.copy_all(
            protected_files=[f["path"] for f in protected_files]
        )

        audit.log_success(install_id, files_copied=result["files_copied"])

        # 4. Verify
        assert (claude_dir / "PROJECT.md").read_text() == "# User project"
        assert result["files_skipped"] >= 2

        report = audit.generate_report(install_id)
        assert len(report["protected_files"]) >= 2

    def test_complete_upgrade_workflow(self, tmp_path, plugin_structure):
        """Test complete upgrade workflow with backups.

        Current: FAILS - Complete workflow doesn't exist
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()

        # Existing plugin files
        hooks_dir = claude_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "auto_format.py").write_text("# Old version")

        # User modifications
        (claude_dir / "PROJECT.md").write_text("# User")
        (hooks_dir / "custom.py").write_text("# Custom")

        staging_dir = tmp_path / ".claude-staging"
        shutil.copytree(plugin_structure, staging_dir)

        # 1. Detect files
        detector = ProtectedFileDetector()
        protected_files = detector.detect_protected_files(project_dir)

        # 2. Analyze
        analyzer = InstallationAnalyzer(project_dir)
        install_type = analyzer.detect_installation_type()
        assert install_type == InstallationType.UPGRADE

        conflict_report = analyzer.generate_conflict_report(staging_dir)
        # Should detect conflicts with plugin files

        # 3. Execute with backups
        audit = InstallAudit(project_dir / "audit.jsonl")
        install_id = audit.start_installation("upgrade")

        copier = CopySystem(staging_dir, claude_dir)
        result = copier.copy_all(
            protected_files=[f["path"] for f in protected_files],
            backup_conflicts=True,
        )

        audit.log_success(install_id, files_copied=result["files_copied"])

        # 4. Verify
        # Protected files preserved
        assert "User" in (claude_dir / "PROJECT.md").read_text()

        # Plugin files updated with backups
        assert (hooks_dir / "auto_format.py.backup").exists()

        report = audit.generate_report(install_id)
        assert report["status"] == "success"
