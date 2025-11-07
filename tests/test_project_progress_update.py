"""
TDD Tests for PROJECT.md Auto-Update Feature (SubagentStop hook)

IMPORTANT: These tests are written FIRST (TDD red phase) before implementation.
All tests should FAIL initially - they describe the requirements.

Test Coverage:
1. ProjectMdUpdater class unit tests (atomic writes, security, regex updates)
2. SubagentStop hook unit tests (trigger conditions, agent invocation)
3. Integration tests (end-to-end workflow)

Security Requirements:
- CRITICAL: Validate all paths before file operations (no path traversal)
- CRITICAL: Detect and reject symlinks in file paths
- HIGH: Atomic file writes (temp file + rename pattern)
- HIGH: Backup before modification with timestamp
- MEDIUM: Validate PROJECT.md syntax after updates
- MEDIUM: Detect and handle merge conflicts

Feature Requirements:
- Hook triggers only after doc-master agent completes
- Hook requires pipeline completion (enforce_pipeline_complete.py passed)
- Hook invokes project-progress-tracker agent for assessment
- Hook parses YAML output from agent
- Hook updates PROJECT.md atomically
- Hook handles agent timeout gracefully
- Hook rolls back changes on failure

Following TDD principles - tests written before implementation.
Target: 80%+ coverage of security-critical and business-logic code paths.

Implementation Plan Reference:
- File: plugins/autonomous-dev/hooks/auto_update_project_progress.py (hook)
- File: plugins/autonomous-dev/lib/project_md_updater.py (library)
- Modified: plugins/autonomous-dev/agents/project-progress-tracker.md (YAML output)
- Modified: scripts/agent_tracker.py (SubagentStop lifecycle event)
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import subprocess
import pytest


# ============================================================================
# Unit Tests: ProjectMdUpdater Class
# ============================================================================


class TestProjectMdUpdaterAtomicWrites:
    """Test atomic write operations for PROJECT.md updates."""

    def test_atomic_write_uses_mkstemp_not_pid(self):
        """Test that atomic writes use tempfile.mkstemp() instead of PID-based naming.

        Security rationale: PID-based temp files create race condition vulnerability.
        - Attacker can predict temp filename (PID observable via /proc or ps)
        - mkstemp() uses cryptographic random suffix (unpredictable)
        - mkstemp() fails if file exists (atomic creation)

        TDD RED PHASE: This test will FAIL until implementation uses mkstemp().
        Current implementation uses: f".PROJECT_{os.getpid()}.tmp" (VULNERABLE)
        Expected implementation: tempfile.mkstemp() (SECURE)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "PROJECT.md"
            project_file.write_text("## GOALS\n- Goal 1: Build feature X (Target: 100%)\n")

            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
            from project_md_updater import ProjectMdUpdater

            updater = ProjectMdUpdater(project_file)

            # Mock mkstemp to verify it's called
            with patch('tempfile.mkstemp') as mock_mkstemp:
                # mkstemp returns (fd, path)
                mock_fd = 42
                mock_path = str(Path(tmpdir) / ".PROJECT.abc123.tmp")
                mock_mkstemp.return_value = (mock_fd, mock_path)

                # Mock os.write and os.close, plus Path.replace
                with patch('os.write') as mock_write, \
                     patch('os.close') as mock_close, \
                     patch('pathlib.Path.replace') as mock_replace:

                    updater.update_goal_progress({"Goal 1": 25})

                    # Assert: mkstemp called with correct parameters
                    mock_mkstemp.assert_called_once()
                    call_kwargs = mock_mkstemp.call_args[1]
                    assert call_kwargs['dir'] == str(tmpdir), \
                        "mkstemp should create temp file in same directory as target"
                    assert call_kwargs['prefix'] == '.PROJECT.', \
                        "mkstemp should use .PROJECT. prefix for clarity"
                    assert call_kwargs['suffix'] == '.tmp', \
                        "mkstemp should use .tmp suffix"
                    assert call_kwargs['text'] is False, \
                        "mkstemp should use binary mode for cross-platform compatibility"

                    # Assert: Content written via os.write (not Path.write_text)
                    mock_write.assert_called_once_with(mock_fd, b"## GOALS\n- Goal 1: Build feature X (Target: 100%, Current: 25%)\n")

                    # Assert: FD closed before rename
                    mock_close.assert_called_once_with(mock_fd)

    def test_atomic_write_closes_fd_on_error(self):
        """Test that file descriptor is closed even if write fails.

        Security rationale: Leaked file descriptors can cause resource exhaustion.
        - Each process has limited FD table (typically 1024 entries)
        - Unclosed FDs accumulate and cause "too many open files" errors
        - This is a form of resource exhaustion DoS

        TDD RED PHASE: This test will FAIL until implementation properly closes FD on error.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "PROJECT.md"
            project_file.write_text("## GOALS\n- Goal 1: Build feature X (Target: 100%)\n")

            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
            from project_md_updater import ProjectMdUpdater

            updater = ProjectMdUpdater(project_file)

            # Mock mkstemp to return a FD
            with patch('tempfile.mkstemp') as mock_mkstemp:
                mock_fd = 42
                mock_path = str(Path(tmpdir) / ".PROJECT.xyz789.tmp")
                mock_mkstemp.return_value = (mock_fd, mock_path)

                # Mock os.write to raise exception
                with patch('os.write') as mock_write, \
                     patch('os.close') as mock_close, \
                     patch('os.unlink') as mock_unlink:

                    mock_write.side_effect = OSError("Disk full")

                    # Act: Try to update (should fail)
                    with pytest.raises(IOError, match="Failed to write"):
                        updater.update_goal_progress({"Goal 1": 25})

                    # Assert: FD was closed despite error
                    mock_close.assert_called_once_with(mock_fd), \
                        "File descriptor MUST be closed even on error (prevents FD leak)"

                    # Assert: Temp file was cleaned up
                    mock_unlink.assert_called_once()
                    call_args = mock_unlink.call_args[0][0]
                    assert str(call_args) == mock_path, \
                        "Temp file MUST be deleted on error (prevents temp file accumulation)"

    def test_atomic_write_encodes_utf8_correctly(self):
        """Test that content is encoded as UTF-8 when writing via os.write().

        Security rationale: Encoding errors can cause data corruption or security issues.
        - Path.write_text() defaults to UTF-8 and handles encoding automatically
        - os.write() requires manual encoding to bytes
        - Incorrect encoding can truncate unicode characters (data loss)
        - Missing encoding can cause TypeError (availability issue)

        TDD RED PHASE: This test will FAIL until implementation encodes content properly.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "PROJECT.md"
            # Use unicode characters to test encoding
            project_file.write_text("## GOALS\n- Goal 1: Build 🔒 security system (Target: 100%)\n")

            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
            from project_md_updater import ProjectMdUpdater

            updater = ProjectMdUpdater(project_file)

            with patch('tempfile.mkstemp') as mock_mkstemp:
                mock_fd = 42
                mock_path = str(Path(tmpdir) / ".PROJECT.test.tmp")
                mock_mkstemp.return_value = (mock_fd, mock_path)

                with patch('os.write') as mock_write, \
                     patch('os.close') as mock_close, \
                     patch('pathlib.Path.replace') as mock_replace:

                    updater.update_goal_progress({"Goal 1": 50})

                    # Assert: Content passed to os.write is bytes (encoded)
                    mock_write.assert_called_once()
                    written_data = mock_write.call_args[0][1]
                    assert isinstance(written_data, bytes), \
                        "os.write requires bytes, not str"

                    # Assert: UTF-8 encoding preserves unicode
                    expected_content = "## GOALS\n- Goal 1: Build 🔒 security system (Target: 100%, Current: 50%)\n"
                    assert written_data == expected_content.encode('utf-8'), \
                        "Content must be UTF-8 encoded (preserves unicode characters)"

    def test_atomic_write_creates_temp_file_first(self):
        """Test that atomic writes use temp file before renaming to target.

        Security rationale: Prevents readers from seeing partial/corrupted data.
        If process crashes mid-write, original file remains intact.
        """
        # Arrange: Create test PROJECT.md
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "PROJECT.md"
            project_file.write_text("## GOALS\n- Goal 1: Build feature X (Target: 100%)\n")

            # Act: Import and use ProjectMdUpdater (will fail - not implemented)
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
            from project_md_updater import ProjectMdUpdater

            updater = ProjectMdUpdater(project_file)

            # Mock mkstemp instead of write_text
            with patch('tempfile.mkstemp') as mock_mkstemp:
                mock_fd = 42
                mock_path = str(Path(tmpdir) / ".PROJECT.test.tmp")
                mock_mkstemp.return_value = (mock_fd, mock_path)

                with patch('os.write'), patch('os.close'), \
                     patch('pathlib.Path.replace'):
                    updater.update_goal_progress({"Goal 1": 25})

                    # Assert: mkstemp was called (temp file created)
                    mock_mkstemp.assert_called_once(), \
                        "Atomic write should use mkstemp to create temp file first"

    def test_backup_includes_timestamp(self):
        """Test that backup file includes timestamp for traceability.

        Requirement: Before modifying PROJECT.md, create backup with timestamp.
        Format: PROJECT.md.backup.YYYYMMDD-HHMMSS
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "PROJECT.md"
            project_file.write_text("## GOALS\n- Goal 1: Build feature X (Target: 100%)\n")

            # Act: Update PROJECT.md
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
            from project_md_updater import ProjectMdUpdater

            updater = ProjectMdUpdater(project_file)
            updater.update_goal_progress({"Goal 1": 50})

            # Assert: Backup file created with timestamp
            backup_files = list(Path(tmpdir).glob("PROJECT.md.backup.*"))
            assert len(backup_files) == 1, "Should create exactly one backup file"

            backup_name = backup_files[0].name
            assert backup_name.startswith("PROJECT.md.backup."), "Backup should have .backup. prefix"

            # Verify timestamp format (YYYYMMDD-HHMMSS)
            timestamp_part = backup_name.split(".")[-1]
            assert len(timestamp_part) == 15, "Timestamp should be YYYYMMDD-HHMMSS (15 chars)"
            assert timestamp_part[8] == "-", "Timestamp should have hyphen separator"

    def test_symlink_detection_prevents_attack(self):
        """Test that symlinks in PROJECT.md path are rejected.

        Security: Symlinks can be used to write to arbitrary files.
        Example: PROJECT.md -> /etc/passwd (attacker escalates privileges)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            real_file = Path(tmpdir) / "real_project.md"
            real_file.write_text("## GOALS\n- Goal 1: [0%] Test\n")

            symlink_file = Path(tmpdir) / "PROJECT.md"
            symlink_file.symlink_to(real_file)

            # Act & Assert: Symlink should be rejected
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
            from project_md_updater import ProjectMdUpdater

            with pytest.raises(ValueError, match="Symlinks are not allowed"):
                ProjectMdUpdater(symlink_file)

    def test_path_traversal_blocked(self):
        """Test that path traversal attempts are blocked.

        Security: Prevent ../../etc/passwd style attacks.
        Example: PROJECT.md path contains '..' sequences
        """
        # Arrange: Create path with traversal attempt
        malicious_path = Path("/tmp/project/../../../etc/passwd")

        # Act & Assert: Path traversal should be rejected
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
        from project_md_updater import ProjectMdUpdater

        with pytest.raises(ValueError, match="Path outside project root|Path traversal"):
            ProjectMdUpdater(malicious_path)


class TestProjectMdUpdaterGoalUpdates:
    """Test goal progress updates in PROJECT.md."""

    def test_goal_progress_regex_replacement(self):
        """Test that goal progress percentage is updated correctly.

        Requirement: Update "Goal X: [Y%]" to "Goal X: [Z%]"
        Example: "- Goal 1: [0%] Build" -> "- Goal 1: [25%] Build"
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "PROJECT.md"
            original_content = """## GOALS

- Goal 1: Build authentication system (Target: 100%)
- Goal 2: Implement user dashboard (Target: 100%, Current: 50%)
"""
            project_file.write_text(original_content)

            # Act: Update Goal 1 progress to 25%
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
            from project_md_updater import ProjectMdUpdater

            updater = ProjectMdUpdater(project_file)
            updater.update_goal_progress({"Goal 1": 25})

            # Assert: Goal 1 updated, Goal 2 unchanged
            updated_content = project_file.read_text()
            assert "Current: 25%" in updated_content, \
                "Goal 1 progress should be updated to 25%"
            assert "Current: 50%" in updated_content, \
                "Goal 2 progress should remain unchanged"

    def test_metric_value_update(self):
        """Test that metric values are updated correctly.

        Requirement: Update metric values in GOALS section.
        Example: "Features completed: 5" -> "Features completed: 6"
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "PROJECT.md"
            original_content = """## GOALS

**Progress Metrics:**
- Features completed: 5
- Tests passing: 120
"""
            project_file.write_text(original_content)

            # Act: Update features completed to 6
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
            from project_md_updater import ProjectMdUpdater

            updater = ProjectMdUpdater(project_file)
            updater.update_metric("Features completed", 6)

            # Assert: Metric updated correctly
            updated_content = project_file.read_text()
            assert "Features completed: 6" in updated_content, \
                "Metric should be updated to new value"
            assert "Features completed: 5" not in updated_content, \
                "Old metric value should be replaced"
            assert "Tests passing: 120" in updated_content, \
                "Other metrics should remain unchanged"

    def test_multiple_goals_updated_correctly(self):
        """Test that multiple goals can be updated in single operation.

        Requirement: Support batch updates for efficiency.
        Example: Update Goal 1 and Goal 3 in single call.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "PROJECT.md"
            original_content = """## GOALS

- Goal 1: Authentication (Target: 100%)
- Goal 2: Dashboard (Target: 100%, Current: 25%)
- Goal 3: Reporting (Target: 100%, Current: 50%)
"""
            project_file.write_text(original_content)

            # Act: Update multiple goals
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
            from project_md_updater import ProjectMdUpdater

            updater = ProjectMdUpdater(project_file)
            updates = {
                "Goal 1": 30,
                "Goal 3": 75
            }
            updater.update_goal_progress(updates)

            # Assert: Both goals updated, Goal 2 unchanged
            updated_content = project_file.read_text()
            assert "Goal 1: Authentication (Target: 100%, Current: 30%)" in updated_content
            assert "Goal 2: Dashboard (Target: 100%, Current: 25%)" in updated_content  # Unchanged
            assert "Goal 3: Reporting (Target: 100%, Current: 75%)" in updated_content

    def test_project_md_syntax_validation(self):
        """Test that PROJECT.md syntax is validated after updates.

        Requirement: Ensure updates don't break PROJECT.md structure.
        Example: GOALS section still has proper headers after update.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "PROJECT.md"
            original_content = """# Project Context

## GOALS

- Goal 1: Test (Target: 100%)
"""
            project_file.write_text(original_content)

            # Act: Update goal
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
            from project_md_updater import ProjectMdUpdater

            updater = ProjectMdUpdater(project_file)
            updater.update_goal_progress({"Goal 1": 50})

            # Assert: Syntax validation passes
            result = updater.validate_syntax()
            assert result["valid"] is True, "PROJECT.md should have valid syntax"
            assert "## GOALS" in result.get("sections", []), \
                "GOALS section should still exist"

    def test_merge_conflict_detection(self):
        """Test that merge conflicts in PROJECT.md are detected.

        Requirement: Don't update PROJECT.md if merge conflict exists.
        Example: File contains <<<<<<< HEAD markers
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "PROJECT.md"
            conflicted_content = """## GOALS

<<<<<<< HEAD
- Goal 1: Feature A (Target: 100%, Current: 25%)
=======
- Goal 1: Feature A (Target: 100%, Current: 30%)
>>>>>>> branch-b
"""
            project_file.write_text(conflicted_content)

            # Act & Assert: Should reject update due to conflict
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
            from project_md_updater import ProjectMdUpdater

            updater = ProjectMdUpdater(project_file)

            with pytest.raises(ValueError, match="merge conflict detected"):
                updater.update_goal_progress({"Goal 1": 50})


# ============================================================================
# Unit Tests: SubagentStop Hook
# ============================================================================


class TestSubagentStopHookTriggers:
    """Test when the SubagentStop hook should trigger."""

    def test_hook_triggers_only_on_doc_master(self):
        """Test that hook only runs after doc-master agent completes.

        Requirement: PROJECT.md updates happen at end of pipeline.
        Rationale: Wait for all work to complete before assessing progress.
        """
        # Arrange: Mock SubagentStop event for different agents
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "hooks"))
        from auto_update_project_progress import should_trigger_update

        # Act & Assert: Only doc-master triggers update
        assert should_trigger_update("doc-master") is True, \
            "Should trigger after doc-master"
        assert should_trigger_update("researcher") is False, \
            "Should not trigger after researcher"
        assert should_trigger_update("implementer") is False, \
            "Should not trigger after implementer"
        assert should_trigger_update("security-auditor") is False, \
            "Should not trigger after security-auditor"

    def test_hook_requires_pipeline_complete(self):
        """Test that hook checks if pipeline completed before running.

        Requirement: Only update if all 7 agents ran successfully.
        Dependency: enforce_pipeline_complete.py hook must have passed.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Arrange: Create incomplete pipeline state
            session_file = Path(tmpdir) / "session.json"
            incomplete_session = {
                "session_id": "test-123",
                "agents": [
                    {"agent": "researcher", "status": "completed"},
                    {"agent": "planner", "status": "completed"},
                    # Missing: test-master, implementer, reviewer, security, doc-master
                ]
            }
            session_file.write_text(json.dumps(incomplete_session))

            # Act: Check if hook should run
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "hooks"))
            from auto_update_project_progress import check_pipeline_complete

            result = check_pipeline_complete(session_file)

            # Assert: Hook should not run on incomplete pipeline
            assert result is False, \
                "Should not run if pipeline incomplete"

    def test_hook_invokes_progress_tracker(self):
        """Test that hook invokes project-progress-tracker agent.

        Requirement: Use GenAI to assess progress against goals.
        Agent: project-progress-tracker analyzes completed work vs PROJECT.md
        """
        # Arrange: Mock subprocess call to agent
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "hooks"))
        from auto_update_project_progress import invoke_progress_tracker

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="assessment:\n  goal_1: 25\n  goal_2: 50"
            )

            # Act: Invoke progress tracker
            result = invoke_progress_tracker()

            # Assert: Agent was invoked with correct parameters
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "project-progress-tracker" in " ".join(call_args), \
                "Should invoke project-progress-tracker agent"

    def test_hook_parses_yaml_output(self):
        """Test that hook parses YAML output from progress tracker agent.

        Requirement: Agent returns assessment in YAML format.
        Format:
          assessment:
            goal_1: 25
            goal_2: 50
        """
        # Arrange: Mock YAML output from agent
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "hooks"))
        from auto_update_project_progress import parse_agent_output

        agent_output = """
assessment:
  goal_1: 25
  goal_2: 50
  features_completed: 3
"""

        # Act: Parse output
        result = parse_agent_output(agent_output)

        # Assert: Parsed correctly
        assert result["assessment"]["goal_1"] == 25
        assert result["assessment"]["goal_2"] == 50
        assert result["assessment"]["features_completed"] == 3

    def test_hook_handles_agent_timeout(self):
        """Test that hook handles agent timeout gracefully.

        Requirement: If agent takes too long (>30s), skip update.
        Rationale: Don't block pipeline if progress assessment hangs.
        """
        # Arrange: Mock timeout
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "hooks"))
        from auto_update_project_progress import invoke_progress_tracker

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd="agent", timeout=30
            )

            # Act: Invoke with timeout
            result = invoke_progress_tracker(timeout=30)

            # Assert: Returns gracefully without update
            assert result is None, "Should return None on timeout"
            # Hook should log warning but not crash

    def test_hook_rolls_back_on_failure(self):
        """Test that hook rolls back changes if update fails.

        Requirement: If PROJECT.md update fails, restore from backup.
        Example: Regex update fails, restore .backup file.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "PROJECT.md"
            original_content = "## GOALS\n- Goal 1: [0%] Test\n"
            project_file.write_text(original_content)

            # Arrange: Force update to fail
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "hooks"))
            from auto_update_project_progress import update_project_with_rollback

            # Mock updater to raise exception
            with patch('project_md_updater.ProjectMdUpdater.update_goal_progress') as mock_update:
                mock_update.side_effect = Exception("Update failed")

                # Act: Attempt update (should rollback)
                try:
                    update_project_with_rollback(project_file, {"Goal 1": 25})
                except Exception:
                    pass

                # Assert: Original content restored
                assert project_file.read_text() == original_content, \
                    "Should restore original content on failure"


# ============================================================================
# Integration Tests: End-to-End Workflow
# ============================================================================


class TestProjectProgressUpdateIntegration:
    """Integration tests for complete PROJECT.md update workflow."""

    def test_auto_implement_updates_project_md(self):
        """Test that /auto-implement workflow updates PROJECT.md at end.

        End-to-end test:
        1. Run /auto-implement for a feature
        2. All 7 agents execute successfully
        3. doc-master completes (triggers SubagentStop hook)
        4. progress-tracker agent assesses progress
        5. PROJECT.md updated atomically
        6. Backup created
        7. Git commit includes PROJECT.md
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Arrange: Set up project structure
            project_file = Path(tmpdir) / "PROJECT.md"
            project_file.write_text("""## GOALS

- Goal 1: Build authentication system (Target: 100%)
""")

            session_file = Path(tmpdir) / "session.json"
            complete_session = {
                "session_id": "test-integration",
                "agents": [
                    {"agent": "researcher", "status": "completed"},
                    {"agent": "planner", "status": "completed"},
                    {"agent": "test-master", "status": "completed"},
                    {"agent": "implementer", "status": "completed"},
                    {"agent": "reviewer", "status": "completed"},
                    {"agent": "security-auditor", "status": "completed"},
                    {"agent": "doc-master", "status": "completed"},
                ]
            }
            session_file.write_text(json.dumps(complete_session))

            # Act: Simulate SubagentStop hook after doc-master
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "hooks"))

            with patch('subprocess.run') as mock_agent:
                # Mock progress tracker output
                mock_agent.return_value = Mock(
                    returncode=0,
                    stdout="assessment:\n  goal_1: 25\n"
                )

                from auto_update_project_progress import run_hook
                run_hook(
                    agent_name="doc-master",
                    session_file=session_file,
                    project_file=project_file
                )

            # Assert: PROJECT.md updated
            updated_content = project_file.read_text()
            assert "Current: 25%" in updated_content, \
                "Goal progress should be updated"

            # Assert: Backup created
            backups = list(Path(tmpdir).glob("PROJECT.md.backup.*"))
            assert len(backups) == 1, "Backup should be created"

            # Original content preserved in backup
            assert backups[0].read_text() == \
                "## GOALS\n\n- Goal 1: Build authentication system (Target: 100%)\n", \
                "Backup should contain original content"

    def test_handles_missing_project_md(self):
        """Test graceful handling when PROJECT.md doesn't exist.

        Scenario: New project without PROJECT.md yet.
        Expected: Hook logs warning but doesn't crash.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Arrange: No PROJECT.md exists
            project_file = Path(tmpdir) / "PROJECT.md"
            # Don't create file

            # Act: Try to run hook
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "hooks"))
            from auto_update_project_progress import run_hook

            # Should not crash
            try:
                run_hook(
                    agent_name="doc-master",
                    session_file=Path(tmpdir) / "session.json",
                    project_file=project_file
                )
                result = "no_error"
            except FileNotFoundError:
                result = "error"

            # Assert: Handles missing file gracefully
            assert result == "no_error", \
                "Should handle missing PROJECT.md gracefully"

    def test_handles_merge_conflicts(self):
        """Test that hook skips update if PROJECT.md has merge conflicts.

        Scenario: User is resolving merge conflict in PROJECT.md.
        Expected: Hook detects conflict markers, skips update, logs warning.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Arrange: PROJECT.md with conflict markers
            project_file = Path(tmpdir) / "PROJECT.md"
            project_file.write_text("""## GOALS

<<<<<<< HEAD
- Goal 1: [25%] Feature A
=======
- Goal 1: [30%] Feature A
>>>>>>> feature-branch
""")

            # Act: Try to update
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "hooks"))
            from auto_update_project_progress import run_hook

            with patch('subprocess.run') as mock_agent:
                mock_agent.return_value = Mock(
                    returncode=0,
                    stdout="assessment:\n  goal_1: 50\n"
                )

                run_hook(
                    agent_name="doc-master",
                    session_file=Path(tmpdir) / "session.json",
                    project_file=project_file
                )

            # Assert: File unchanged (conflict markers still there)
            content = project_file.read_text()
            assert "<<<<<<< HEAD" in content, \
                "Should not modify file with conflict markers"
            assert "[50%]" not in content, \
                "Should not apply update to conflicted file"


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestProjectProgressEdgeCases:
    """Test edge cases and error conditions."""

    def test_atomic_write_windows_compatibility(self):
        """Test that atomic write works on Windows (different rename semantics).

        Security rationale: Windows requires target file deletion before rename.
        - POSIX: rename() atomically replaces target if exists
        - Windows: rename() fails if target exists (must delete first)
        - Solution: Use Path.replace() which handles both platforms

        TDD RED PHASE: This test will FAIL if implementation uses os.rename().
        Expected: Path(temp).replace(target) for cross-platform atomicity
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "PROJECT.md"
            project_file.write_text("## GOALS\n- Goal 1: Test (Target: 100%)\n")

            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
            from project_md_updater import ProjectMdUpdater

            updater = ProjectMdUpdater(project_file)

            # Mock mkstemp and track rename method used
            with patch('tempfile.mkstemp') as mock_mkstemp:
                mock_fd = 42
                mock_temp = Path(tmpdir) / ".PROJECT.win.tmp"
                mock_mkstemp.return_value = (mock_fd, str(mock_temp))

                # Create actual temp file for replace() to work
                mock_temp.write_text("## GOALS\n- Goal 1: Test (Target: 100%, Current: 25%)\n")

                with patch('os.write'), patch('os.close'):
                    # Spy on Path.replace (Windows-compatible)
                    with patch.object(Path, 'replace', wraps=mock_temp.replace) as mock_replace:
                        updater.update_goal_progress({"Goal 1": 25})

                        # Assert: Used Path.replace() not os.rename()
                        mock_replace.assert_called_once(), \
                            "Should use Path.replace() for Windows compatibility"

    def test_atomic_write_concurrent_writes_no_collision(self):
        """Test that concurrent writes don't collide due to mkstemp randomness.

        Security rationale: PID-based naming causes race conditions.
        - PID-based: Two processes with same PID can collide (PID reuse)
        - mkstemp: Cryptographic random suffix (collision probability ~0)

        TDD RED PHASE: This test verifies mkstemp creates unique files.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "PROJECT.md"
            project_file.write_text("## GOALS\n- Goal 1: Test (Target: 100%)\n")

            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
            from project_md_updater import ProjectMdUpdater

            # Simulate two concurrent updaters
            updater1 = ProjectMdUpdater(project_file)
            updater2 = ProjectMdUpdater(project_file)

            temp_files_created = []

            # Mock mkstemp to track temp file names
            original_mkstemp = tempfile.mkstemp

            def track_mkstemp(**kwargs):
                fd, path = original_mkstemp(**kwargs)
                temp_files_created.append(path)
                return fd, path

            with patch('tempfile.mkstemp', side_effect=track_mkstemp):
                with patch('os.write'), patch('os.close'):
                    # Both updaters create temp files
                    updater1._atomic_write("content1")
                    updater2._atomic_write("content2")

            # Assert: Temp files have different names (no collision)
            assert len(temp_files_created) == 2, \
                "Should create 2 temp files"
            assert temp_files_created[0] != temp_files_created[1], \
                "mkstemp should generate unique filenames (prevents race conditions)"

    def test_atomic_write_handles_enospc_error(self):
        """Test handling of ENOSPC (No space left on device) error.

        Security rationale: Disk full can cause availability issues.
        - Partial writes create corrupt files
        - Must clean up temp file to free space
        - Must close FD to free file table entry

        TDD RED PHASE: This test verifies proper cleanup on disk full.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "PROJECT.md"
            project_file.write_text("## GOALS\n- Goal 1: Test (Target: 100%)\n")

            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
            from project_md_updater import ProjectMdUpdater

            updater = ProjectMdUpdater(project_file)

            with patch('tempfile.mkstemp') as mock_mkstemp:
                mock_fd = 42
                mock_path = str(Path(tmpdir) / ".PROJECT.full.tmp")
                mock_mkstemp.return_value = (mock_fd, mock_path)

                with patch('os.write') as mock_write, \
                     patch('os.close') as mock_close, \
                     patch('os.unlink') as mock_unlink:

                    # Simulate ENOSPC (errno 28)
                    enospc_error = OSError(28, "No space left on device")
                    mock_write.side_effect = enospc_error

                    # Act: Try to write (should fail gracefully)
                    with pytest.raises(IOError, match="Failed to write"):
                        updater._atomic_write("new content")

                    # Assert: FD closed (prevents resource leak)
                    mock_close.assert_called_once_with(mock_fd), \
                        "Must close FD on ENOSPC to free resources"

                    # Assert: Temp file deleted (frees disk space)
                    mock_unlink.assert_called_once()
                    call_args = mock_unlink.call_args[0][0]
                    assert str(call_args) == mock_path, \
                        "Must delete temp file on ENOSPC to free space"

    def test_invalid_yaml_from_agent(self):
        """Test handling of invalid YAML from progress tracker."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "hooks"))
        from auto_update_project_progress import parse_agent_output

        invalid_yaml = "this is not: valid: yaml: at: all:"

        # Should handle parse error gracefully
        result = parse_agent_output(invalid_yaml)
        assert result is None or result == {}, \
            "Should handle invalid YAML gracefully"

    def test_negative_progress_percentage(self):
        """Test rejection of negative progress percentages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "PROJECT.md"
            project_file.write_text("## GOALS\n- Goal 1: Test (Target: 100%)\n")

            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
            from project_md_updater import ProjectMdUpdater

            updater = ProjectMdUpdater(project_file)

            with pytest.raises(ValueError, match="Invalid progress|percentage"):
                updater.update_goal_progress({"Goal 1": -10})

    def test_progress_percentage_over_100(self):
        """Test rejection of progress percentages over 100%."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "PROJECT.md"
            project_file.write_text("## GOALS\n- Goal 1: Test (Target: 100%)\n")

            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
            from project_md_updater import ProjectMdUpdater

            updater = ProjectMdUpdater(project_file)

            with pytest.raises(ValueError, match="Invalid progress|percentage"):
                updater.update_goal_progress({"Goal 1": 150})

    def test_concurrent_updates_to_project_md(self):
        """Test handling of concurrent updates to PROJECT.md.

        Scenario: Two /auto-implement pipelines run simultaneously.
        Expected: Last write wins, or detect conflict.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "PROJECT.md"
            project_file.write_text("## GOALS\n- Goal 1: Test (Target: 100%)\n")

            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
            from project_md_updater import ProjectMdUpdater

            # Simulate concurrent updates
            updater1 = ProjectMdUpdater(project_file)
            updater2 = ProjectMdUpdater(project_file)

            # Both try to update
            updater1.update_goal_progress({"Goal 1": 25})
            updater2.update_goal_progress({"Goal 1": 50})

            # Last write should win (atomic rename ensures consistency)
            content = project_file.read_text()
            assert "Current: 50%" in content or "Current: 25%" in content, \
                "One update should succeed"
            assert not ("Current: 50%" in content and "Current: 25%" in content), \
                "Should not have both values (corruption)"

    def test_empty_goals_section(self):
        """Test handling of PROJECT.md with empty GOALS section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "PROJECT.md"
            project_file.write_text("## GOALS\n\n## SCOPE\n")

            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
            from project_md_updater import ProjectMdUpdater

            updater = ProjectMdUpdater(project_file)

            # Should handle empty section gracefully
            result = updater.update_goal_progress({"Goal 1": 25})
            assert result is False or result is None, \
                "Should handle empty GOALS section gracefully"

    def test_malformed_goal_format(self):
        """Test handling of goals not in expected format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / "PROJECT.md"
            project_file.write_text("""## GOALS

- This is not a valid goal format
- Neither is this: missing percentage
- Goal 1 [wrong bracket position] 50%
""")

            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))
            from project_md_updater import ProjectMdUpdater

            updater = ProjectMdUpdater(project_file)

            # Should skip malformed goals
            result = updater.update_goal_progress({"Goal 1": 25})
            assert result is False or result is None, \
                "Should skip malformed goal formats"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
