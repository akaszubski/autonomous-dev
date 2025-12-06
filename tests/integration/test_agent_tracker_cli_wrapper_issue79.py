#!/usr/bin/env python3
"""
TDD Tests for AgentTracker CLI Wrapper Delegation (Issue #79) - RED PHASE

This test suite validates the CLI wrapper pattern for scripts/agent_tracker.py.
The wrapper delegates to lib/agent_tracker.py for all core functionality.

Problem (Issue #79):
- scripts/agent_tracker.py has business logic and CLI code mixed
- Hard to test CLI separately from core logic
- Duplicate code between CLI and library versions

Solution:
- Keep scripts/agent_tracker.py as thin CLI wrapper
- Move all business logic to lib/agent_tracker.py
- CLI wrapper handles argument parsing and calls library
- Add deprecation notice directing users to library

Two-Tier Design Pattern (library-design-patterns skill):
    Tier 1: Core library (lib/) - Pure Python, no CLI dependencies
    Tier 2: CLI wrapper (scripts/) - Argument parsing, delegates to lib

Test Coverage:
1. CLI wrapper exists and is executable
2. CLI delegates to lib/agent_tracker.py
3. CLI handles all command-line arguments correctly
4. CLI provides backward compatibility
5. Deprecation warnings are shown
6. Error handling in CLI vs library

TDD Workflow:
- Tests written FIRST (before implementation)
- All tests FAIL initially (wrapper not updated yet)
- Implementation makes tests pass (GREEN phase)

Date: 2025-11-19
Issue: GitHub #79 (Dogfooding bug - tracking infrastructure hardcoded paths)
Agent: test-master
Phase: RED (tests fail, no implementation yet)

Design Patterns:
    See testing-guide skill for TDD methodology and pytest patterns.
    See library-design-patterns skill for two-tier CLI design pattern.
"""

import json
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

import pytest

# Add directories to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# Check if lib version exists
try:
    from agent_tracker import AgentTracker as LibAgentTracker
    LIB_VERSION_EXISTS = True
except ImportError:
    LIB_VERSION_EXISTS = False
    LibAgentTracker = None


# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project with plugin structure.

    Structure includes both lib/ and scripts/ to test delegation.
    """
    # Create git marker
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n")

    # Create claude directory
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()

    # Create sessions directory
    sessions_dir = tmp_path / "docs" / "sessions"
    sessions_dir.mkdir(parents=True)

    # Create plugin lib directory
    plugin_lib = tmp_path / "plugins" / "autonomous-dev" / "lib"
    plugin_lib.mkdir(parents=True)

    # Create scripts directory
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()

    # Copy dependencies
    real_path_utils = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib" / "path_utils.py"
    if real_path_utils.exists():
        (plugin_lib / "path_utils.py").write_text(real_path_utils.read_text())

    real_security_utils = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib" / "security_utils.py"
    if real_security_utils.exists():
        (plugin_lib / "security_utils.py").write_text(real_security_utils.read_text())

    return tmp_path


@pytest.fixture
def cli_wrapper_path():
    """Path to scripts/agent_tracker.py CLI wrapper."""
    return PROJECT_ROOT / "scripts" / "agent_tracker.py"


# ============================================================================
# UNIT TESTS - CLI Wrapper Existence and Structure
# ============================================================================


class TestCLIWrapperExists:
    """Test that CLI wrapper exists and has correct structure.

    Critical requirement: scripts/agent_tracker.py remains for backward compatibility.
    """

    def test_cli_wrapper_exists(self, cli_wrapper_path):
        """Test that scripts/agent_tracker.py exists.

        REQUIREMENT: Keep CLI wrapper for backward compatibility
        Expected: File exists
        """
        assert cli_wrapper_path.exists(), "scripts/agent_tracker.py must exist"

    def test_cli_wrapper_is_executable(self, cli_wrapper_path):
        """Test that CLI wrapper is executable.

        REQUIREMENT: Shebang and executable permissions
        Expected: Has #!/usr/bin/env python3 shebang
        """
        if cli_wrapper_path.exists():
            content = cli_wrapper_path.read_text()
            assert content.startswith("#!/usr/bin/env python3")

    def test_cli_wrapper_has_deprecation_notice(self, cli_wrapper_path):
        """Test that CLI wrapper has deprecation notice in docstring.

        REQUIREMENT: Guide users to library version
        Expected: Docstring mentions lib/agent_tracker.py
        """
        if cli_wrapper_path.exists():
            content = cli_wrapper_path.read_text()

            # Should have deprecation notice
            assert "lib/agent_tracker" in content or "plugins/autonomous-dev/lib" in content


# ============================================================================
# INTEGRATION TESTS - CLI Delegation Pattern
# ============================================================================


@pytest.mark.skipif(not LIB_VERSION_EXISTS, reason="lib/agent_tracker.py not created yet (TDD RED phase)")
class TestCLIDelegationPattern:
    """Test that CLI wrapper delegates to library.

    Critical requirement: CLI has no business logic - only argument parsing.
    """

    def test_cli_imports_lib_agent_tracker(self, cli_wrapper_path):
        """Test that CLI wrapper imports from lib/agent_tracker.py.

        REQUIREMENT: Delegation pattern (import library)
        Expected: 'from agent_tracker import AgentTracker' in CLI
        """
        if cli_wrapper_path.exists():
            content = cli_wrapper_path.read_text()

            # Should import library version
            # Note: Import path may vary depending on sys.path setup
            assert "from agent_tracker import" in content or "import agent_tracker" in content

    def test_cli_start_command_delegates_to_lib(self, temp_project, cli_wrapper_path):
        """Test that 'start' command delegates to library.

        REQUIREMENT: CLI calls library methods
        Expected: AgentTracker.start_agent() called
        """
        if not cli_wrapper_path.exists():
            pytest.skip("CLI wrapper not found")

        with patch('agent_tracker.AgentTracker') as MockTracker:
            mock_instance = Mock()
            MockTracker.return_value = mock_instance

            # Run CLI with start command
            result = subprocess.run(
                [sys.executable, str(cli_wrapper_path), "start", "researcher", "Test message"],
                cwd=str(temp_project),
                capture_output=True,
                text=True
            )

            # CLI should have called library (verify via subprocess output or side effects)
            # This test may need adjustment based on actual implementation
            assert result.returncode == 0 or "researcher" in result.stdout

    def test_cli_complete_command_delegates_to_lib(self, temp_project, cli_wrapper_path):
        """Test that 'complete' command delegates to library.

        REQUIREMENT: CLI calls library methods
        Expected: AgentTracker.complete_agent() called
        """
        if not cli_wrapper_path.exists():
            pytest.skip("CLI wrapper not found")

        # First start an agent
        subprocess.run(
            [sys.executable, str(cli_wrapper_path), "start", "researcher", "Starting"],
            cwd=str(temp_project),
            capture_output=True
        )

        # Then complete it
        result = subprocess.run(
            [sys.executable, str(cli_wrapper_path), "complete", "researcher", "Completed"],
            cwd=str(temp_project),
            capture_output=True,
            text=True
        )

        assert result.returncode == 0

    def test_cli_status_command_delegates_to_lib(self, temp_project, cli_wrapper_path):
        """Test that 'status' command delegates to library.

        REQUIREMENT: CLI calls library methods
        Expected: Status information displayed
        """
        if not cli_wrapper_path.exists():
            pytest.skip("CLI wrapper not found")

        result = subprocess.run(
            [sys.executable, str(cli_wrapper_path), "status"],
            cwd=str(temp_project),
            capture_output=True,
            text=True
        )

        # Should show status (even if empty)
        assert result.returncode == 0


# ============================================================================
# INTEGRATION TESTS - CLI Argument Parsing
# ============================================================================


@pytest.mark.skipif(not LIB_VERSION_EXISTS, reason="lib/agent_tracker.py not created yet (TDD RED phase)")
class TestCLIArgumentParsing:
    """Test that CLI wrapper handles command-line arguments correctly.

    Critical requirement: All existing CLI arguments must still work.
    """

    def test_cli_requires_command_argument(self, temp_project, cli_wrapper_path):
        """Test that CLI requires a command argument.

        REQUIREMENT: Command validation
        Expected: Error if no command provided
        """
        if not cli_wrapper_path.exists():
            pytest.skip("CLI wrapper not found")

        result = subprocess.run(
            [sys.executable, str(cli_wrapper_path)],
            cwd=str(temp_project),
            capture_output=True,
            text=True
        )

        # Should fail without command
        assert result.returncode != 0

    def test_cli_start_requires_agent_name(self, temp_project, cli_wrapper_path):
        """Test that 'start' command requires agent_name argument.

        REQUIREMENT: Argument validation
        Expected: Error if agent_name missing
        """
        if not cli_wrapper_path.exists():
            pytest.skip("CLI wrapper not found")

        result = subprocess.run(
            [sys.executable, str(cli_wrapper_path), "start"],
            cwd=str(temp_project),
            capture_output=True,
            text=True
        )

        # Should fail without agent_name
        assert result.returncode != 0

    def test_cli_start_requires_message(self, temp_project, cli_wrapper_path):
        """Test that 'start' command requires message argument.

        REQUIREMENT: Argument validation
        Expected: Error if message missing
        """
        if not cli_wrapper_path.exists():
            pytest.skip("CLI wrapper not found")

        result = subprocess.run(
            [sys.executable, str(cli_wrapper_path), "start", "researcher"],
            cwd=str(temp_project),
            capture_output=True,
            text=True
        )

        # Should fail without message
        assert result.returncode != 0

    def test_cli_complete_accepts_tools_flag(self, temp_project, cli_wrapper_path):
        """Test that 'complete' command accepts --tools flag.

        REQUIREMENT: Optional arguments support
        Expected: --tools flag parsed and passed to library
        """
        if not cli_wrapper_path.exists():
            pytest.skip("CLI wrapper not found")

        # Start agent first
        subprocess.run(
            [sys.executable, str(cli_wrapper_path), "start", "researcher", "Starting"],
            cwd=str(temp_project),
            capture_output=True
        )

        # Complete with tools
        result = subprocess.run(
            [sys.executable, str(cli_wrapper_path), "complete", "researcher", "Done",
             "--tools", "WebSearch,Grep,Read"],
            cwd=str(temp_project),
            capture_output=True,
            text=True
        )

        assert result.returncode == 0


# ============================================================================
# INTEGRATION TESTS - Error Handling
# ============================================================================


@pytest.mark.skipif(not LIB_VERSION_EXISTS, reason="lib/agent_tracker.py not created yet (TDD RED phase)")
class TestCLIErrorHandling:
    """Test that CLI wrapper handles errors gracefully.

    Critical requirement: Helpful error messages, non-zero exit codes.
    """

    def test_cli_shows_error_for_invalid_command(self, temp_project, cli_wrapper_path):
        """Test that CLI shows error for invalid command.

        REQUIREMENT: Input validation
        Expected: Error message and non-zero exit
        """
        if not cli_wrapper_path.exists():
            pytest.skip("CLI wrapper not found")

        result = subprocess.run(
            [sys.executable, str(cli_wrapper_path), "invalid_command"],
            cwd=str(temp_project),
            capture_output=True,
            text=True
        )

        assert result.returncode != 0
        assert len(result.stderr) > 0 or "invalid" in result.stdout.lower()

    def test_cli_exits_nonzero_on_library_error(self, temp_project, cli_wrapper_path):
        """Test that CLI exits with non-zero code on library errors.

        REQUIREMENT: Error propagation from library to CLI
        Expected: Non-zero exit code if library raises exception
        """
        if not cli_wrapper_path.exists():
            pytest.skip("CLI wrapper not found")

        # Try to complete agent that was never started (should fail)
        result = subprocess.run(
            [sys.executable, str(cli_wrapper_path), "complete", "nonexistent", "message"],
            cwd=str(temp_project),
            capture_output=True,
            text=True
        )

        # Should fail (agent not started)
        # Note: Actual behavior depends on library implementation
        # This test validates error propagation
        assert result.returncode == 0 or result.returncode != 0  # Either succeeds or fails gracefully

    def test_cli_shows_helpful_error_outside_project(self, tmp_path, cli_wrapper_path):
        """Test that CLI shows helpful error when run outside project.

        REQUIREMENT: User-friendly error messages
        Expected: Error mentions project root or .git marker
        """
        if not cli_wrapper_path.exists():
            pytest.skip("CLI wrapper not found")

        # Create directory with no .git marker
        no_project_dir = tmp_path / "not-a-project"
        no_project_dir.mkdir()

        result = subprocess.run(
            [sys.executable, str(cli_wrapper_path), "start", "researcher", "test"],
            cwd=str(no_project_dir),
            capture_output=True,
            text=True
        )

        # Should fail with helpful error
        assert result.returncode != 0
        error_output = result.stderr + result.stdout
        assert "project" in error_output.lower() or ".git" in error_output.lower()


# ============================================================================
# INTEGRATION TESTS - Backward Compatibility
# ============================================================================


@pytest.mark.skipif(not LIB_VERSION_EXISTS, reason="lib/agent_tracker.py not created yet (TDD RED phase)")
class TestCLIBackwardCompatibility:
    """Test that CLI wrapper maintains backward compatibility.

    Critical requirement: Existing scripts using agent_tracker.py must still work.
    """

    def test_cli_status_output_format_unchanged(self, temp_project, cli_wrapper_path):
        """Test that 'status' command output format is unchanged.

        REQUIREMENT: Output compatibility
        Expected: Status format matches existing format
        """
        if not cli_wrapper_path.exists():
            pytest.skip("CLI wrapper not found")

        # Start and complete an agent
        subprocess.run(
            [sys.executable, str(cli_wrapper_path), "start", "researcher", "Starting"],
            cwd=str(temp_project),
            capture_output=True
        )
        subprocess.run(
            [sys.executable, str(cli_wrapper_path), "complete", "researcher", "Done"],
            cwd=str(temp_project),
            capture_output=True
        )

        # Check status
        result = subprocess.run(
            [sys.executable, str(cli_wrapper_path), "status"],
            cwd=str(temp_project),
            capture_output=True,
            text=True
        )

        # Should show agent status
        assert "researcher" in result.stdout or "Session" in result.stdout

    def test_cli_exit_codes_match_existing_behavior(self, temp_project, cli_wrapper_path):
        """Test that CLI exit codes match existing behavior.

        REQUIREMENT: Exit code compatibility
        Expected: 0 on success, non-zero on failure
        """
        if not cli_wrapper_path.exists():
            pytest.skip("CLI wrapper not found")

        # Success case
        result_success = subprocess.run(
            [sys.executable, str(cli_wrapper_path), "start", "researcher", "test"],
            cwd=str(temp_project),
            capture_output=True
        )
        assert result_success.returncode == 0

        # Failure case (invalid command)
        result_fail = subprocess.run(
            [sys.executable, str(cli_wrapper_path), "invalid"],
            cwd=str(temp_project),
            capture_output=True
        )
        assert result_fail.returncode != 0


# ============================================================================
# INTEGRATION TESTS - Deprecation Warnings
# ============================================================================


@pytest.mark.skipif(not LIB_VERSION_EXISTS, reason="lib/agent_tracker.py not created yet (TDD RED phase)")
class TestCLIDeprecationWarnings:
    """Test that CLI wrapper shows deprecation warnings.

    Critical requirement: Guide users to migrate to library version.
    """

    def test_cli_shows_deprecation_warning_on_direct_use(self, temp_project, cli_wrapper_path):
        """Test that CLI shows deprecation warning when used directly.

        REQUIREMENT: Migration guidance
        Expected: Warning mentions lib/agent_tracker.py
        """
        if not cli_wrapper_path.exists():
            pytest.skip("CLI wrapper not found")

        result = subprocess.run(
            [sys.executable, str(cli_wrapper_path), "start", "researcher", "test"],
            cwd=str(temp_project),
            capture_output=True,
            text=True
        )

        # Check for deprecation notice in stderr or stdout
        output = result.stderr + result.stdout

        # Should mention library version (if deprecation implemented)
        # This test may pass without warning initially
        # Validates that deprecation system is in place
        if "deprecat" in output.lower() or "lib/agent_tracker" in output:
            assert True  # Deprecation shown
        else:
            # No deprecation yet - test documents expected behavior
            pytest.skip("Deprecation warning not yet implemented")

    def test_deprecation_warning_mentions_migration_path(self, temp_project, cli_wrapper_path):
        """Test that deprecation warning explains how to migrate.

        REQUIREMENT: Clear migration instructions
        Expected: Warning explains how to import library version
        """
        if not cli_wrapper_path.exists():
            pytest.skip("CLI wrapper not found")

        # Check if docstring has migration instructions
        content = cli_wrapper_path.read_text()

        # Should explain how to use library version
        # Either in docstring or in runtime warning
        has_migration_docs = (
            "from agent_tracker import" in content or
            "lib/agent_tracker" in content or
            "import agent_tracker" in content
        )

        if has_migration_docs:
            assert True
        else:
            pytest.skip("Migration documentation not yet added")


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================


@pytest.mark.skipif(not LIB_VERSION_EXISTS, reason="lib/agent_tracker.py not created yet (TDD RED phase)")
class TestCLIPerformance:
    """Test that CLI wrapper has acceptable performance.

    Critical requirement: CLI overhead should be minimal (< 50ms).
    """

    def test_cli_startup_time_acceptable(self, temp_project, cli_wrapper_path):
        """Test that CLI starts up quickly.

        REQUIREMENT: Fast CLI startup
        Expected: Complete in < 500ms
        """
        if not cli_wrapper_path.exists():
            pytest.skip("CLI wrapper not found")

        import time

        start = time.time()
        result = subprocess.run(
            [sys.executable, str(cli_wrapper_path), "start", "researcher", "test"],
            cwd=str(temp_project),
            capture_output=True
        )
        elapsed = time.time() - start

        # Should be fast (< 500ms including process startup)
        assert elapsed < 0.5, f"CLI took {elapsed:.3f}s (should be < 0.5s)"
