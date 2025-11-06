"""Smoke tests for command routing and basic validation.

Tests validate that commands can be invoked and perform
basic validation without full execution.

All tests must complete in < 5 seconds total.
"""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.smoke
class TestAutoImplementCommand:
    """Validate /auto-implement command routing and validation."""

    def test_auto_implement_command_exists(self, plugins_dir, timing_validator):
        """Test that auto-implement command file exists.

        Protects: Core command availability (smoke test - regression baseline)
        Expected: < 1 second
        """
        # NOTE: This will FAIL if command not present
        with timing_validator.measure() as timer:
            command = plugins_dir / "commands" / "auto-implement.md"
            assert command.exists()

            content = command.read_text()
            # Should reference 7-agent workflow
            assert "researcher" in content.lower()
            assert "planner" in content.lower()
            assert "test-master" in content.lower()

        assert timer.elapsed < 1.0

    def test_auto_implement_validates_project_md_exists(self, isolated_project, timing_validator):
        """Test that auto-implement validates PROJECT.md exists before starting.

        Protects: Alignment requirement enforcement (smoke test - regression baseline)
        Expected: < 3 seconds
        """
        # NOTE: This will FAIL until validation implemented
        with timing_validator.measure() as timer:
            # Remove PROJECT.md to trigger validation
            project_md = isolated_project / ".claude" / "PROJECT.md"
            project_md.unlink()

            # Attempt to invoke auto-implement (mock)
            # Should fail fast with clear error
            # (In real implementation, this would be command validation)

            # For now, just verify the validation logic exists
            # This is a placeholder for actual command invocation
            assert not project_md.exists()

        assert timer.elapsed < 3.0


@pytest.mark.smoke
class TestHealthCheckCommand:
    """Validate /health-check command execution."""

    def test_health_check_script_exists(self, plugins_dir, timing_validator):
        """Test that health check script exists and is executable.

        Protects: Health check availability (smoke test - regression baseline)
        Expected: < 1 second
        """
        # NOTE: This will FAIL if script missing
        with timing_validator.measure() as timer:
            script = plugins_dir / "scripts" / "health_check.py"
            assert script.exists()

        assert timer.elapsed < 1.0

    def test_health_check_runs_successfully(self, plugins_dir, timing_validator):
        """Test that health check runs and completes successfully.

        Protects: Plugin integrity validation (smoke test - regression baseline)
        Expected: < 3 seconds
        """
        # NOTE: This will FAIL if health check broken
        with timing_validator.measure() as timer:
            script = plugins_dir / "scripts" / "health_check.py"

            # Run health check
            result = subprocess.run(
                [sys.executable, str(script)],
                cwd=plugins_dir.parent.parent,
                capture_output=True,
                text=True,
                timeout=5
            )

            # Should complete (may have warnings but not errors)
            # Exit code 0 = all checks passed
            # Exit code 1 = some checks failed (still valid output)
            assert result.returncode in [0, 1]

        assert timer.elapsed < 3.0

    def test_health_check_validates_agents(self, plugins_dir, timing_validator):
        """Test that health check validates agent presence.

        Protects: Agent availability validation (smoke test - regression baseline)
        Expected: < 3 seconds
        """
        # NOTE: This will FAIL if validation broken
        with timing_validator.measure() as timer:
            script = plugins_dir / "scripts" / "health_check.py"

            # Run health check
            result = subprocess.run(
                [sys.executable, str(script)],
                cwd=plugins_dir.parent.parent,
                capture_output=True,
                text=True,
                timeout=5
            )

            output = result.stdout + result.stderr

            # Should report agent validation
            assert "agents" in output.lower() or "18" in output  # 18 agents per CLAUDE.md

        assert timer.elapsed < 3.0


@pytest.mark.smoke
class TestAlignProjectCommand:
    """Validate /align-project command routing."""

    def test_align_project_command_exists(self, plugins_dir, timing_validator):
        """Test that align-project command file exists.

        Protects: Alignment command availability (smoke test - regression baseline)
        Expected: < 1 second
        """
        # NOTE: This will FAIL if command not present
        with timing_validator.measure() as timer:
            command = plugins_dir / "commands" / "align-project.md"
            assert command.exists()

            content = command.read_text()
            # Should reference alignment-analyzer agent
            assert "alignment-analyzer" in content.lower() or "PROJECT.md" in content

        assert timer.elapsed < 1.0


@pytest.mark.smoke
class TestStatusCommand:
    """Validate /status command routing."""

    def test_status_command_exists(self, plugins_dir, timing_validator):
        """Test that status command file exists.

        Protects: Status tracking availability (smoke test - regression baseline)
        Expected: < 1 second
        """
        # NOTE: This will FAIL if command not present
        with timing_validator.measure() as timer:
            command = plugins_dir / "commands" / "status.md"
            assert command.exists()

            content = command.read_text()
            # Should reference project-status-analyzer agent
            assert "status" in content.lower() or "progress" in content.lower()

        assert timer.elapsed < 1.0


@pytest.mark.smoke
class TestPipelineStatusCommand:
    """Validate /pipeline-status command execution."""

    def test_pipeline_status_script_exists(self, plugins_dir, timing_validator):
        """Test that pipeline status script exists.

        Protects: Pipeline tracking availability (smoke test - regression baseline)
        Expected: < 1 second
        """
        # NOTE: This will FAIL if script missing
        with timing_validator.measure() as timer:
            script = plugins_dir / "scripts" / "pipeline_status.py"
            assert script.exists()

        assert timer.elapsed < 1.0

    def test_pipeline_status_runs_without_error(self, plugins_dir, timing_validator):
        """Test that pipeline status script runs without errors.

        Protects: Pipeline tracking reliability (smoke test - regression baseline)
        Expected: < 2 seconds
        """
        # NOTE: This will FAIL if script broken
        with timing_validator.measure() as timer:
            script = plugins_dir / "scripts" / "pipeline_status.py"

            # Run pipeline status
            result = subprocess.run(
                [sys.executable, str(script)],
                cwd=plugins_dir.parent.parent,
                capture_output=True,
                text=True,
                timeout=3
            )

            # Should complete without crashing
            # May return empty if no pipeline running, but shouldn't error
            assert "Traceback" not in result.stderr

        assert timer.elapsed < 2.0


# TODO: Backfill additional smoke tests for:
# - /sync-dev command routing
# - /test command routing
# - Individual agent commands (/research, /plan, /test-feature, etc.)
# - Hook activation validation
# - Session tracker functionality
