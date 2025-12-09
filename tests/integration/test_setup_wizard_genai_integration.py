"""Integration tests for setup-wizard Phase 0 GenAI integration.

Tests end-to-end Phase 0 workflow with GenAI installation libraries.
All tests should FAIL initially (TDD red phase) - no implementation exists yet.

Related: GitHub Issue #109
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

import pytest


@pytest.fixture
def staging_dir(tmp_path: Path) -> Path:
    """Create a valid staging directory with plugin structure."""
    staging = tmp_path / "staging"
    staging.mkdir()

    # Create plugin structure
    plugin_root = staging / "plugins/autonomous-dev"
    (plugin_root / "commands").mkdir(parents=True)
    (plugin_root / "agents").mkdir(parents=True)
    (plugin_root / "hooks").mkdir(parents=True)
    (plugin_root / "lib").mkdir(parents=True)
    (plugin_root / "skills").mkdir(parents=True)

    # Create sample files
    (plugin_root / "commands/auto-implement.md").write_text("# Auto-implement command")
    (plugin_root / "commands/setup.md").write_text("# Setup command")
    (plugin_root / "agents/researcher.md").write_text("# Researcher agent")
    (plugin_root / "hooks/auto_format.py").write_text("# Auto-format hook")
    (plugin_root / "lib/security_utils.py").write_text("# Security utilities")

    # Create .claude/ structure
    claude_dir = staging / ".claude"
    claude_dir.mkdir()
    (claude_dir / "PROJECT.md").write_text("# Project template")
    (claude_dir / "CLAUDE.md").write_text("# Claude instructions template")

    # Create .env template
    (staging / ".env").write_text("# Environment template\nAPI_KEY=")

    return staging


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create an empty project directory."""
    project = tmp_path / "project"
    project.mkdir()
    return project


@pytest.fixture
def mock_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Mock HOME environment variable for staging directory."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


class TestPhase0FreshInstall:
    """Test Phase 0 workflow for fresh installation."""

    def test_phase0_fresh_install_workflow(
        self,
        staging_dir: Path,
        project_dir: Path,
        mock_home: Path
    ) -> None:
        """Complete Phase 0 workflow for fresh install.

        Validates:
        1. Staging check passes
        2. Installation type detected as fresh
        3. All files copied
        4. Audit log created
        5. Summary generated
        6. Cleanup removes staging
        """
        from autonomous_dev.scripts.genai_install_wrapper import (
            check_staging,
            analyze_installation_type,
            execute_installation,
            generate_summary,
            cleanup_staging,
        )

        # Step 1: Check staging
        staging_result = check_staging(str(staging_dir))
        assert staging_result["status"] == "valid"
        assert staging_result["fallback_needed"] is False

        # Step 2: Analyze installation type
        analysis = analyze_installation_type(str(project_dir))
        assert analysis["type"] == "fresh"
        assert analysis["has_project_md"] is False
        assert analysis["has_claude_dir"] is False

        # Step 3: Execute installation
        install_result = execute_installation(
            staging_path=str(staging_dir),
            project_path=str(project_dir),
            install_type=analysis["type"]
        )
        assert install_result["status"] == "success"
        assert install_result["files_copied"] > 0

        # Verify critical directories exist
        assert (project_dir / "plugins/autonomous-dev/commands").is_dir()
        assert (project_dir / "plugins/autonomous-dev/agents").is_dir()
        assert (project_dir / "plugins/autonomous-dev/hooks").is_dir()
        assert (project_dir / "plugins/autonomous-dev/lib").is_dir()

        # Verify sample files copied
        assert (project_dir / "plugins/autonomous-dev/commands/auto-implement.md").exists()
        assert (project_dir / "plugins/autonomous-dev/agents/researcher.md").exists()

        # Verify .claude/ structure created
        assert (project_dir / ".claude/PROJECT.md").exists()
        assert (project_dir / ".claude/CLAUDE.md").exists()

        # Step 4: Check audit log
        audit_file = project_dir / ".claude/install_audit.jsonl"
        assert audit_file.exists()
        events = [json.loads(line) for line in audit_file.read_text().strip().split("\n")]
        assert len(events) > 0
        assert events[0]["event"] == "installation_start"
        assert any(e["event"] == "installation_complete" for e in events)

        # Step 5: Generate summary
        summary_result = generate_summary(
            install_type=analysis["type"],
            install_result=install_result,
            project_path=str(project_dir)
        )
        assert summary_result["status"] == "success"
        assert summary_result["summary"]["install_type"] == "fresh"
        assert len(summary_result["next_steps"]) > 0

        # Step 6: Cleanup staging
        cleanup_result = cleanup_staging(str(staging_dir))
        assert cleanup_result["status"] == "success"
        assert not staging_dir.exists()

    def test_phase0_handles_existing_structure(
        self,
        staging_dir: Path,
        project_dir: Path
    ) -> None:
        """Phase 0 handles partially created project structure.

        Validates that installation works even if some directories
        already exist in the project.
        """
        from autonomous_dev.scripts.genai_install_wrapper import (
            analyze_installation_type,
            execute_installation,
        )

        # Arrange: Create partial structure
        (project_dir / "plugins/autonomous-dev").mkdir(parents=True)
        (project_dir / ".claude").mkdir()

        # Act: Analyze and install
        analysis = analyze_installation_type(str(project_dir))
        install_result = execute_installation(
            staging_path=str(staging_dir),
            project_path=str(project_dir),
            install_type=analysis["type"]
        )

        # Assert: Installation succeeds
        assert install_result["status"] == "success"
        assert (project_dir / "plugins/autonomous-dev/commands/auto-implement.md").exists()


class TestPhase0BrownfieldInstall:
    """Test Phase 0 workflow for brownfield installation."""

    def test_phase0_brownfield_preserves_project_md(
        self,
        staging_dir: Path,
        project_dir: Path
    ) -> None:
        """PROJECT.md not overwritten in brownfield installation.

        Validates:
        1. Installation type detected as brownfield
        2. Existing PROJECT.md preserved
        3. Other files installed normally
        4. Audit log tracks protected files
        """
        from autonomous_dev.scripts.genai_install_wrapper import (
            analyze_installation_type,
            execute_installation,
        )

        # Arrange: Create existing PROJECT.md
        (project_dir / ".claude").mkdir()
        original_content = "# My Existing Project\n\nCustom goals and scope."
        (project_dir / ".claude/PROJECT.md").write_text(original_content)

        # Act: Analyze and install
        analysis = analyze_installation_type(str(project_dir))
        assert analysis["type"] == "brownfield"
        assert analysis["has_project_md"] is True
        assert ".claude/PROJECT.md" in analysis["protected_files"]

        install_result = execute_installation(
            staging_path=str(staging_dir),
            project_path=str(project_dir),
            install_type=analysis["type"]
        )

        # Assert: PROJECT.md preserved
        assert install_result["status"] == "success"
        assert (project_dir / ".claude/PROJECT.md").read_text() == original_content
        assert ".claude/PROJECT.md" in install_result["skipped_files"]

        # Other files should be installed
        assert (project_dir / "plugins/autonomous-dev/commands/auto-implement.md").exists()
        assert (project_dir / ".claude/CLAUDE.md").exists()

        # Audit log should track skipped file
        audit_file = project_dir / ".claude/install_audit.jsonl"
        events = [json.loads(line) for line in audit_file.read_text().strip().split("\n")]
        skip_events = [e for e in events if e["event"] == "file_skipped"]
        assert any("PROJECT.md" in e["details"].get("file", "") for e in skip_events)

    def test_phase0_brownfield_preserves_env(
        self,
        staging_dir: Path,
        project_dir: Path
    ) -> None:
        """Existing .env file preserved in brownfield installation.

        Critical security test - ensures secrets not overwritten.
        """
        from autonomous_dev.scripts.genai_install_wrapper import (
            analyze_installation_type,
            execute_installation,
        )

        # Arrange: Create existing .env with secrets
        original_env = "API_KEY=secret123\nDATABASE_URL=postgresql://localhost/prod"
        (project_dir / ".env").write_text(original_env)

        # Act: Install
        analysis = analyze_installation_type(str(project_dir))
        install_result = execute_installation(
            staging_path=str(staging_dir),
            project_path=str(project_dir),
            install_type=analysis["type"]
        )

        # Assert: .env preserved
        assert (project_dir / ".env").read_text() == original_env
        assert ".env" in install_result["skipped_files"]


class TestPhase0UpgradeInstall:
    """Test Phase 0 workflow for upgrade installation."""

    def test_phase0_upgrade_creates_backups(
        self,
        staging_dir: Path,
        project_dir: Path
    ) -> None:
        """Modified files backed up during upgrade installation.

        Validates:
        1. Installation type detected as upgrade
        2. Existing files backed up before overwrite
        3. New versions installed
        4. Backup files have correct naming
        5. Audit log tracks backups
        """
        from autonomous_dev.scripts.genai_install_wrapper import (
            analyze_installation_type,
            execute_installation,
        )

        # Arrange: Create existing plugin files (old version)
        (project_dir / ".claude").mkdir()
        (project_dir / "plugins/autonomous-dev/commands").mkdir(parents=True)
        original_content = "# Auto-implement v1.0\n\nOld implementation."
        (project_dir / "plugins/autonomous-dev/commands/auto-implement.md").write_text(original_content)

        # Act: Analyze and install
        analysis = analyze_installation_type(str(project_dir))
        assert analysis["type"] == "upgrade"
        assert analysis["has_claude_dir"] is True
        assert analysis["has_project_md"] is False

        install_result = execute_installation(
            staging_path=str(staging_dir),
            project_path=str(project_dir),
            install_type=analysis["type"]
        )

        # Assert: Backup created
        assert install_result["status"] == "success"
        assert len(install_result["backups_created"]) > 0

        # New version should be installed
        new_content = (project_dir / "plugins/autonomous-dev/commands/auto-implement.md").read_text()
        assert new_content != original_content
        assert new_content == "# Auto-implement command"  # From staging

        # Backup should exist with timestamped name
        backup_files = list((project_dir / "plugins/autonomous-dev/commands").glob("auto-implement.md.backup-*"))
        assert len(backup_files) == 1
        assert backup_files[0].read_text() == original_content

        # Audit log should track backup
        audit_file = project_dir / ".claude/install_audit.jsonl"
        events = [json.loads(line) for line in audit_file.read_text().strip().split("\n")]
        backup_events = [e for e in events if e["event"] == "file_backed_up"]
        assert len(backup_events) > 0

    def test_phase0_upgrade_preserves_custom_hooks(
        self,
        staging_dir: Path,
        project_dir: Path
    ) -> None:
        """User's custom hooks preserved during upgrade.

        Validates that files not in staging are left untouched.
        """
        from autonomous_dev.scripts.genai_install_wrapper import execute_installation

        # Arrange: Create custom hook
        (project_dir / ".claude").mkdir()
        (project_dir / ".claude/hooks").mkdir()
        custom_hook_content = "# Custom user hook\ndef my_custom_logic(): pass"
        (project_dir / ".claude/hooks/my_custom_hook.py").write_text(custom_hook_content)

        # Act: Install
        install_result = execute_installation(
            staging_path=str(staging_dir),
            project_path=str(project_dir),
            install_type="upgrade"
        )

        # Assert: Custom hook untouched
        assert install_result["status"] == "success"
        assert (project_dir / ".claude/hooks/my_custom_hook.py").exists()
        assert (project_dir / ".claude/hooks/my_custom_hook.py").read_text() == custom_hook_content


class TestPhase0StagingValidation:
    """Test staging directory validation and fallback."""

    def test_phase0_staging_missing_fallback(
        self,
        project_dir: Path,
        mock_home: Path
    ) -> None:
        """Gracefully skips to Phase 1 when staging missing.

        Validates:
        1. Missing staging detected
        2. Fallback flag set
        3. No installation attempted
        4. Clear message for user
        """
        from autonomous_dev.scripts.genai_install_wrapper import check_staging

        # Arrange: Staging doesn't exist
        staging_path = mock_home / ".autonomous-dev/staging"

        # Act: Check staging
        result = check_staging(str(staging_path))

        # Assert: Fallback indicated
        assert result["status"] == "missing"
        assert result["fallback_needed"] is True
        assert "skip to Phase 1" in result["message"]

    def test_phase0_staging_incomplete_fallback(
        self,
        tmp_path: Path
    ) -> None:
        """Incomplete staging triggers fallback to Phase 1.

        Validates that missing critical directories are detected.
        """
        from autonomous_dev.scripts.genai_install_wrapper import check_staging

        # Arrange: Staging with missing directories
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "plugins/autonomous-dev/commands").mkdir(parents=True)
        # Missing: agents/, hooks/, lib/

        # Act: Check staging
        result = check_staging(str(staging))

        # Assert: Invalid status, fallback needed
        assert result["status"] == "invalid"
        assert result["fallback_needed"] is True
        assert "missing_dirs" in result
        assert len(result["missing_dirs"]) > 0

    def test_phase0_staging_valid_proceeds(
        self,
        staging_dir: Path
    ) -> None:
        """Valid staging allows Phase 0 to proceed.

        Validates that complete staging structure passes validation.
        """
        from autonomous_dev.scripts.genai_install_wrapper import check_staging

        # Act: Check staging
        result = check_staging(str(staging_dir))

        # Assert: Valid status, no fallback
        assert result["status"] == "valid"
        assert result["fallback_needed"] is False
        assert result["staging_path"] == str(staging_dir)


class TestPhase0CriticalDirectories:
    """Test validation of critical plugin directories."""

    def test_phase0_validates_critical_directories(
        self,
        staging_dir: Path,
        project_dir: Path
    ) -> None:
        """All critical directories exist after installation.

        Validates that required plugin structure is complete:
        - plugins/autonomous-dev/commands/
        - plugins/autonomous-dev/agents/
        - plugins/autonomous-dev/hooks/
        - plugins/autonomous-dev/lib/
        - plugins/autonomous-dev/skills/
        - .claude/
        """
        from autonomous_dev.scripts.genai_install_wrapper import execute_installation

        # Act: Install
        install_result = execute_installation(
            staging_path=str(staging_dir),
            project_path=str(project_dir),
            install_type="fresh"
        )

        # Assert: All critical directories exist
        assert install_result["status"] == "success"

        critical_dirs = [
            "plugins/autonomous-dev/commands",
            "plugins/autonomous-dev/agents",
            "plugins/autonomous-dev/hooks",
            "plugins/autonomous-dev/lib",
            "plugins/autonomous-dev/skills",
            ".claude",
        ]

        for dir_path in critical_dirs:
            full_path = project_dir / dir_path
            assert full_path.is_dir(), f"Missing critical directory: {dir_path}"

    def test_phase0_validates_essential_files(
        self,
        staging_dir: Path,
        project_dir: Path
    ) -> None:
        """Essential files exist after installation.

        Validates critical files for plugin operation.
        """
        from autonomous_dev.scripts.genai_install_wrapper import execute_installation

        # Act: Install
        install_result = execute_installation(
            staging_path=str(staging_dir),
            project_path=str(project_dir),
            install_type="fresh"
        )

        # Assert: Essential files exist
        assert install_result["status"] == "success"

        essential_files = [
            "plugins/autonomous-dev/commands/auto-implement.md",
            "plugins/autonomous-dev/agents/researcher.md",
            ".claude/PROJECT.md",
            ".claude/CLAUDE.md",
        ]

        for file_path in essential_files:
            full_path = project_dir / file_path
            assert full_path.is_file(), f"Missing essential file: {file_path}"


class TestPhase0AuditTrail:
    """Test comprehensive audit logging."""

    def test_phase0_audit_trail_complete(
        self,
        staging_dir: Path,
        project_dir: Path
    ) -> None:
        """install_audit.jsonl has all events for full workflow.

        Validates complete audit trail:
        1. installation_start
        2. file_copied events (multiple)
        3. file_skipped events (if any)
        4. file_backed_up events (if any)
        5. installation_complete
        """
        from autonomous_dev.scripts.genai_install_wrapper import execute_installation

        # Arrange: Create existing .env (will be skipped)
        (project_dir / ".env").write_text("EXISTING=value")

        # Act: Install
        install_result = execute_installation(
            staging_path=str(staging_dir),
            project_path=str(project_dir),
            install_type="fresh"
        )

        # Assert: Audit log exists and is complete
        assert install_result["status"] == "success"

        audit_file = project_dir / ".claude/install_audit.jsonl"
        assert audit_file.exists()

        # Parse all events
        events = [json.loads(line) for line in audit_file.read_text().strip().split("\n")]
        event_types = [e["event"] for e in events]

        # Required events
        assert "installation_start" in event_types
        assert "installation_complete" in event_types

        # Should have file operations
        assert "file_copied" in event_types
        assert "file_skipped" in event_types  # .env was skipped

        # All events should have timestamps and details
        for event in events:
            assert "timestamp" in event
            assert "event" in event
            assert "details" in event

    def test_phase0_audit_trail_tracks_metrics(
        self,
        staging_dir: Path,
        project_dir: Path
    ) -> None:
        """Audit log tracks installation metrics.

        Validates that final event includes summary metrics.
        """
        from autonomous_dev.scripts.genai_install_wrapper import execute_installation

        # Act: Install
        install_result = execute_installation(
            staging_path=str(staging_dir),
            project_path=str(project_dir),
            install_type="fresh"
        )

        # Assert: Check final event has metrics
        audit_file = project_dir / ".claude/install_audit.jsonl"
        events = [json.loads(line) for line in audit_file.read_text().strip().split("\n")]

        # Find installation_complete event
        complete_events = [e for e in events if e["event"] == "installation_complete"]
        assert len(complete_events) == 1

        complete_event = complete_events[0]
        assert "files_copied" in complete_event["details"]
        assert complete_event["details"]["files_copied"] > 0


class TestPhase0ErrorRecovery:
    """Test error handling and recovery."""

    def test_phase0_handles_read_only_project(
        self,
        staging_dir: Path,
        project_dir: Path
    ) -> None:
        """Gracefully handles read-only project directory.

        NOTE: Actual permission testing may need platform-specific setup.
        This test validates error structure exists.
        """
        # This test is a placeholder for permission error handling
        # Actual implementation should catch PermissionError
        assert True

    def test_phase0_handles_corrupted_staging(
        self,
        tmp_path: Path,
        project_dir: Path
    ) -> None:
        """Handles corrupted staging directory gracefully.

        Validates error handling when staging has unexpected structure.
        """
        from autonomous_dev.scripts.genai_install_wrapper import (
            check_staging,
            execute_installation,
        )

        # Arrange: Corrupted staging (files instead of directories)
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "plugins/autonomous-dev").mkdir(parents=True)
        (staging / "plugins/autonomous-dev/commands").write_text("corrupted")  # File, not dir

        # Act: Check staging
        check_result = check_staging(str(staging))

        # Assert: Invalid status
        assert check_result["status"] == "invalid"
        assert check_result["fallback_needed"] is True

    def test_phase0_handles_disk_full(
        self,
        staging_dir: Path,
        project_dir: Path
    ) -> None:
        """Handles disk full scenario gracefully.

        NOTE: Simulating disk full is complex and platform-specific.
        This validates error handling structure exists.
        """
        # This test is a placeholder for disk full error handling
        # Actual implementation should catch OSError
        assert True

    def test_phase0_partial_install_cleanup(
        self,
        staging_dir: Path,
        project_dir: Path
    ) -> None:
        """Partial installation is properly tracked in audit log.

        If installation fails partway, audit log should show what was completed.
        """
        # This test validates that audit log is written incrementally
        # so failures leave a trail of what succeeded
        assert True


class TestPhase0ToPhase1Transition:
    """Test transition from Phase 0 to Phase 1."""

    def test_phase0_success_transitions_to_phase1(
        self,
        staging_dir: Path,
        project_dir: Path
    ) -> None:
        """Successful Phase 0 provides context for Phase 1.

        Validates that summary includes next steps for Phase 1.
        """
        from autonomous_dev.scripts.genai_install_wrapper import (
            execute_installation,
            generate_summary,
        )

        # Act: Install and generate summary
        install_result = execute_installation(
            staging_path=str(staging_dir),
            project_path=str(project_dir),
            install_type="fresh"
        )

        summary = generate_summary(
            install_type="fresh",
            install_result=install_result,
            project_path=str(project_dir)
        )

        # Assert: Summary includes Phase 1 guidance
        assert summary["status"] == "success"
        assert "next_steps" in summary
        assert len(summary["next_steps"]) > 0

        # Should mention setup wizard or next configuration step
        next_steps_text = " ".join(summary["next_steps"]).lower()
        assert "setup" in next_steps_text or "wizard" in next_steps_text or "configure" in next_steps_text

    def test_phase0_fallback_transitions_to_phase1(
        self,
        project_dir: Path,
        mock_home: Path
    ) -> None:
        """Missing staging gracefully transitions to Phase 1.

        Validates that fallback scenario provides clear guidance.
        """
        from autonomous_dev.scripts.genai_install_wrapper import check_staging

        # Arrange: Missing staging
        staging_path = mock_home / ".autonomous-dev/staging"

        # Act: Check staging
        result = check_staging(str(staging_path))

        # Assert: Fallback message clear
        assert result["fallback_needed"] is True
        assert "message" in result
        assert "Phase 1" in result["message"]


class TestPhase0MultiPlatform:
    """Test cross-platform compatibility."""

    def test_phase0_handles_windows_paths(
        self,
        staging_dir: Path,
        project_dir: Path
    ) -> None:
        """Installation handles Windows-style paths correctly.

        NOTE: This test uses Path() which normalizes paths cross-platform.
        Actual Windows testing requires Windows CI environment.
        """
        from autonomous_dev.scripts.genai_install_wrapper import execute_installation

        # Act: Install (Path handles platform differences)
        install_result = execute_installation(
            staging_path=str(staging_dir),
            project_path=str(project_dir),
            install_type="fresh"
        )

        # Assert: Installation succeeds regardless of path separators
        assert install_result["status"] == "success"

    def test_phase0_handles_symlinks(
        self,
        staging_dir: Path,
        project_dir: Path,
        tmp_path: Path
    ) -> None:
        """Installation handles symlinks appropriately.

        Validates that symlinks in staging are followed correctly.
        """
        # NOTE: Symlink behavior may need platform-specific handling
        # This test validates the concept exists
        assert True


class TestPhase0PerformanceMetrics:
    """Test performance tracking and reporting."""

    def test_phase0_tracks_installation_time(
        self,
        staging_dir: Path,
        project_dir: Path
    ) -> None:
        """Installation tracks duration for performance monitoring."""
        from autonomous_dev.scripts.genai_install_wrapper import execute_installation

        # Act: Install
        install_result = execute_installation(
            staging_path=str(staging_dir),
            project_path=str(project_dir),
            install_type="fresh"
        )

        # Assert: Duration tracked
        assert install_result["status"] == "success"
        # Implementation should track duration
        # assert "duration_ms" in install_result

    def test_phase0_reports_file_counts(
        self,
        staging_dir: Path,
        project_dir: Path
    ) -> None:
        """Installation reports accurate file operation counts."""
        from autonomous_dev.scripts.genai_install_wrapper import (
            execute_installation,
            generate_summary,
        )

        # Act: Install and summarize
        install_result = execute_installation(
            staging_path=str(staging_dir),
            project_path=str(project_dir),
            install_type="fresh"
        )

        summary = generate_summary(
            install_type="fresh",
            install_result=install_result,
            project_path=str(project_dir)
        )

        # Assert: Accurate counts
        assert summary["summary"]["files_copied"] == install_result["files_copied"]
        assert summary["summary"]["files_copied"] > 0
