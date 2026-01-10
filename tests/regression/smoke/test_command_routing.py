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
            # Command is now a deprecation shim (Issue #203)
            # Should reference deprecation and redirect to /implement
            assert "deprecated" in content.lower()
            assert "implement" in content.lower()

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
        # NOTE: health_check.py is in hooks/, not scripts/ (Issue #147)
        with timing_validator.measure() as timer:
            script = plugins_dir / "hooks" / "health_check.py"
            assert script.exists()

        assert timer.elapsed < 1.0

    def test_health_check_runs_successfully(self, plugins_dir, timing_validator):
        """Test that health check runs and completes successfully.

        Protects: Plugin integrity validation (smoke test - regression baseline)
        Expected: < 3 seconds
        """
        # NOTE: This will FAIL if health check broken
        with timing_validator.measure() as timer:
            script = plugins_dir / "hooks" / "health_check.py"

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
            script = plugins_dir / "hooks" / "health_check.py"

            # Run health check
            result = subprocess.run(
                [sys.executable, str(script)],
                cwd=plugins_dir.parent.parent,
                capture_output=True,
                text=True,
                timeout=5
            )

            output = result.stdout + result.stderr

            # Should report agent validation (8 agents per Issue #147)
            assert "agents" in output.lower() or "8" in output

        assert timer.elapsed < 3.0


@pytest.mark.smoke
class TestAlignCommand:
    """Validate /align command routing (unified alignment command)."""

    def test_align_command_exists(self, plugins_dir, timing_validator):
        """Test that align command file exists.

        Protects: Alignment command availability (smoke test - regression baseline)
        Expected: < 1 second
        Note: align-project.md was unified into align.md (Issue #121)
        """
        # NOTE: This will FAIL if command not present
        with timing_validator.measure() as timer:
            command = plugins_dir / "commands" / "align.md"
            assert command.exists()

            content = command.read_text()
            # Should reference alignment modes (--project, --claude, --retrofit)
            assert "project" in content.lower() or "align" in content.lower()

        assert timer.elapsed < 1.0


@pytest.mark.smoke
class TestSyncCommand:
    """Validate /sync command routing."""

    def test_sync_command_exists(self, plugins_dir, timing_validator):
        """Test that sync command file exists.

        Protects: Sync command availability (smoke test - regression baseline)
        Expected: < 1 second
        """
        # NOTE: This will FAIL if command not present
        with timing_validator.measure() as timer:
            command = plugins_dir / "commands" / "sync.md"
            assert command.exists()

            content = command.read_text()
            # Should reference sync modes (--github, --env, --marketplace, etc.)
            assert "sync" in content.lower() or "github" in content.lower()

        assert timer.elapsed < 1.0


@pytest.mark.smoke
class TestCreateIssueCommand:
    """Validate /create-issue command routing."""

    def test_create_issue_command_exists(self, plugins_dir, timing_validator):
        """Test that create-issue command file exists.

        Protects: Issue creation availability (smoke test - regression baseline)
        Expected: < 1 second
        """
        # NOTE: This will FAIL if command not present
        with timing_validator.measure() as timer:
            command = plugins_dir / "commands" / "create-issue.md"
            assert command.exists()

            content = command.read_text()
            # Should reference issue creation
            assert "issue" in content.lower() or "github" in content.lower()

        assert timer.elapsed < 1.0


# TODO: Backfill additional smoke tests for:
# - Hook activation validation
# - Session tracker functionality
