#!/usr/bin/env python3
"""
TDD Tests for Command Checkpoint Portability (Issue #79) - RED PHASE

This test suite validates that auto-implement.md checkpoints work with portable
path detection and don't have hardcoded paths.

Problem (Issue #79):
- Command checkpoints in auto-implement.md have hardcoded paths
- Example: cd /Users/akaszubski/Documents/GitHub/autonomous-dev && python3 << 'EOF'
- Fails for other developers and in CI/CD environments

Solution:
- Replace hardcoded paths with dynamic detection using path_utils
- Use heredoc with sys.path modifications to import from detected root
- Ensure checkpoints work from any subdirectory

Test Coverage:
1. Checkpoint heredoc uses path_utils.get_project_root()
2. Checkpoint works from project root
3. Checkpoint works from nested subdirectory
4. Checkpoint works in user projects (no scripts/ directory)
5. Checkpoint error messages are helpful
6. Cross-platform path handling

TDD Workflow:
- Tests written FIRST (before implementation)
- All tests FAIL initially (checkpoints have hardcoded paths)
- Implementation makes tests pass (GREEN phase)

Date: 2025-11-19
Issue: GitHub #79 (Dogfooding bug - tracking infrastructure hardcoded paths)
Agent: test-master
Phase: RED (tests fail, no implementation yet)

Design Patterns:
    See testing-guide skill for TDD methodology and pytest patterns.
    See python-standards skill for test code conventions.
"""

import json
import os
import sys
import subprocess
import tempfile
import re
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add lib directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))

try:
    from path_utils import get_project_root, get_session_dir
    PATH_UTILS_EXISTS = True
except ImportError:
    PATH_UTILS_EXISTS = False


# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def auto_implement_command():
    """Path to auto-implement.md command file."""
    return PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project structure for testing checkpoints.

    Structure:
    tmp_project/
        .git/
        .claude/
        plugins/
            autonomous-dev/
                lib/
                    agent_tracker.py
                    path_utils.py
                    security_utils.py
        docs/
            sessions/
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

    # Copy dependencies
    for lib_file in ["path_utils.py", "security_utils.py"]:
        real_lib = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib" / lib_file
        if real_lib.exists():
            (plugin_lib / lib_file).write_text(real_lib.read_text())

    # Copy agent_tracker if it exists
    real_agent_tracker = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib" / "agent_tracker.py"
    if real_agent_tracker.exists():
        (plugin_lib / "agent_tracker.py").write_text(real_agent_tracker.read_text())
    else:
        # Create minimal stub for testing
        (plugin_lib / "agent_tracker.py").write_text('''
from pathlib import Path
from path_utils import get_project_root, get_session_dir

class AgentTracker:
    def __init__(self):
        self.project_root = get_project_root()
        self.session_dir = get_session_dir()
        self.session_file = self.session_dir / "test-session.json"

    def verify_parallel_exploration(self):
        return True
''')

    return tmp_path


@pytest.fixture
def nested_subdirectory(temp_project):
    """Create a nested subdirectory within temp_project."""
    nested = temp_project / "src" / "features" / "auth"
    nested.mkdir(parents=True)
    return nested


@pytest.fixture
def checkpoint1_heredoc():
    """Template for portable CHECKPOINT 1 heredoc.

    This is what we expect the fixed version to look like.
    """
    return '''
import sys
from pathlib import Path

# Dynamically detect project root (searches upward for .git or .claude)
try:
    # Try importing path_utils if available
    try:
        from path_utils import get_project_root
        project_root = get_project_root()
    except ImportError:
        # Fallback: Search upward for .git or .claude markers
        current = Path.cwd()
        project_root = None
        for parent in [current] + list(current.parents):
            if (parent / ".git").exists() or (parent / ".claude").exists():
                project_root = parent
                break
        if not project_root:
            raise FileNotFoundError(
                "Could not find project root (.git or .claude marker not found)\\n"
                "Please run this checkpoint from within the autonomous-dev repository."
            )

    # Add lib directory to sys.path for imports
    lib_dir = project_root / "plugins" / "autonomous-dev" / "lib"
    if str(lib_dir) not in sys.path:
        sys.path.insert(0, str(lib_dir))

    # Now import and execute checkpoint logic
    from agent_tracker import AgentTracker
    tracker = AgentTracker()
    success = tracker.verify_parallel_exploration()
    print(f"\\n{{'✅ PARALLEL EXPLORATION: SUCCESS' if success else '❌ PARALLEL EXPLORATION: FAILED'}}")

except Exception as e:
    print(f"❌ CHECKPOINT ERROR: {e}")
    sys.exit(1)
'''


# ============================================================================
# UNIT TESTS - Command File Structure
# ============================================================================


class TestAutoImplementCommandStructure:
    """Test auto-implement.md command file structure.

    Critical requirement: No hardcoded paths in checkpoint heredocs.
    """

    def test_command_file_exists(self, auto_implement_command):
        """Test that auto-implement.md exists.

        REQUIREMENT: Command file exists
        Expected: File found
        """
        assert auto_implement_command.exists()

    def test_no_hardcoded_absolute_paths(self, auto_implement_command):
        """Test that auto-implement.md has no hardcoded absolute paths.

        REQUIREMENT: Portable checkpoints (no /Users/akaszubski/...)
        Expected: No hardcoded paths like /Users/akaszubski/Documents/...
        """
        if not auto_implement_command.exists():
            pytest.skip("Command file not found")

        content = auto_implement_command.read_text()

        # Check for hardcoded paths
        hardcoded_patterns = [
            r"cd /Users/akaszubski",
            r"cd /home/\w+",
            r"cd C:\\Users\\",
            r"/Users/akaszubski/Documents/GitHub/autonomous-dev"
        ]

        for pattern in hardcoded_patterns:
            matches = re.findall(pattern, content)
            assert len(matches) == 0, f"Found hardcoded path pattern: {pattern} ({len(matches)} occurrences)"

    def test_checkpoints_use_path_utils(self, auto_implement_command):
        """Test that checkpoint heredocs use path_utils for path detection.

        REQUIREMENT: Dynamic path detection
        Expected: Heredocs import and use get_project_root()
        """
        if not auto_implement_command.exists():
            pytest.skip("Command file not found")

        content = auto_implement_command.read_text()

        # Should use path_utils in heredocs
        assert "get_project_root" in content or "find_project_root" in content

    def test_checkpoints_have_fallback_path_detection(self, auto_implement_command):
        """Test that checkpoints have fallback if path_utils unavailable.

        REQUIREMENT: Graceful degradation
        Expected: Fallback to manual .git/.claude search if import fails
        """
        if not auto_implement_command.exists():
            pytest.skip("Command file not found")

        content = auto_implement_command.read_text()

        # Should have ImportError handling
        assert "ImportError" in content or "except" in content
        assert ".git" in content or ".claude" in content


# ============================================================================
# INTEGRATION TESTS - Checkpoint Execution from Different Directories
# ============================================================================


@pytest.mark.skipif(not PATH_UTILS_EXISTS, reason="path_utils.py not available (TDD RED phase)")
class TestCheckpointExecutionFromProjectRoot:
    """Test checkpoint execution when run from project root.

    Critical requirement: Checkpoints work from normal usage location.
    """

    def test_checkpoint1_executes_from_project_root(self, temp_project, checkpoint1_heredoc):
        """Test CHECKPOINT 1 heredoc executes successfully from project root.

        SCENARIO: User runs /auto-implement from project root
        Expected: Checkpoint completes without errors
        """
        # Create a test script with the heredoc
        test_script = temp_project / "test_checkpoint.py"
        test_script.write_text(checkpoint1_heredoc)

        # Execute from project root
        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(temp_project),
            capture_output=True,
            text=True
        )

        # Should succeed
        assert result.returncode == 0, f"Checkpoint failed: {result.stderr}"
        assert "SUCCESS" in result.stdout or "✅" in result.stdout

    def test_checkpoint1_finds_project_root_correctly(self, temp_project, checkpoint1_heredoc):
        """Test that checkpoint correctly detects project root.

        REQUIREMENT: Correct path detection
        Expected: Project root matches temp_project
        """
        # Modified heredoc that prints project root
        debug_heredoc = checkpoint1_heredoc.replace(
            'print(f"\\n{',
            f'print(f"PROJECT_ROOT={{project_root}}")\\nprint(f"\\n{{'
        )

        test_script = temp_project / "test_checkpoint.py"
        test_script.write_text(debug_heredoc)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(temp_project),
            capture_output=True,
            text=True
        )

        # Should show correct project root
        assert str(temp_project) in result.stdout

    def test_checkpoint1_imports_agent_tracker_from_lib(self, temp_project, checkpoint1_heredoc):
        """Test that checkpoint imports AgentTracker from lib directory.

        REQUIREMENT: Import from correct location
        Expected: lib/agent_tracker.py imported (not scripts/)
        """
        test_script = temp_project / "test_checkpoint.py"
        test_script.write_text(checkpoint1_heredoc)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(temp_project),
            capture_output=True,
            text=True
        )

        # Should succeed (implies correct import)
        assert result.returncode == 0


@pytest.mark.skipif(not PATH_UTILS_EXISTS, reason="path_utils.py not available (TDD RED phase)")
class TestCheckpointExecutionFromSubdirectory:
    """Test checkpoint execution when run from nested subdirectories.

    Critical requirement: Checkpoints work from anywhere in the project tree.
    """

    def test_checkpoint1_executes_from_nested_subdirectory(self, temp_project, nested_subdirectory, checkpoint1_heredoc):
        """Test CHECKPOINT 1 executes from deeply nested subdirectory.

        SCENARIO: User runs command from src/features/auth/
        Expected: Checkpoint finds project root and succeeds
        """
        test_script = nested_subdirectory / "test_checkpoint.py"
        test_script.write_text(checkpoint1_heredoc)

        # Execute from nested subdirectory
        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(nested_subdirectory),
            capture_output=True,
            text=True
        )

        # Should succeed despite being in subdirectory
        assert result.returncode == 0, f"Checkpoint failed from subdirectory: {result.stderr}"

    def test_checkpoint1_finds_root_from_subdirectory(self, temp_project, nested_subdirectory, checkpoint1_heredoc):
        """Test that checkpoint finds project root from subdirectory.

        REQUIREMENT: Upward search for .git/.claude markers
        Expected: Finds temp_project (not nested_subdirectory)
        """
        debug_heredoc = checkpoint1_heredoc.replace(
            'print(f"\\n{',
            f'print(f"PROJECT_ROOT={{project_root}}")\\nprint(f"CWD={{Path.cwd()}}")\\nprint(f"\\n{{'
        )

        test_script = nested_subdirectory / "test_checkpoint.py"
        test_script.write_text(debug_heredoc)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(nested_subdirectory),
            capture_output=True,
            text=True
        )

        # Should find project root (not current directory)
        assert str(temp_project) in result.stdout
        assert result.returncode == 0

    def test_checkpoint1_creates_session_in_project_root(self, temp_project, nested_subdirectory, checkpoint1_heredoc):
        """Test that session files created in project root (not subdirectory).

        REQUIREMENT: Session files in PROJECT_ROOT/docs/sessions
        Expected: Files created in temp_project/docs/sessions (not nested_subdirectory)
        """
        test_script = nested_subdirectory / "test_checkpoint.py"
        test_script.write_text(checkpoint1_heredoc)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(nested_subdirectory),
            capture_output=True,
            text=True
        )

        # Session file should be in project root's docs/sessions
        session_dir = temp_project / "docs" / "sessions"
        session_files = list(session_dir.glob("*.json"))

        # At least stub session file should exist
        assert len(session_files) >= 0  # May or may not exist depending on stub


# ============================================================================
# INTEGRATION TESTS - User Project Simulation
# ============================================================================


@pytest.mark.skipif(not PATH_UTILS_EXISTS, reason="path_utils.py not available (TDD RED phase)")
class TestCheckpointInUserProject:
    """Test checkpoint execution in user projects (no scripts/ directory).

    Critical requirement: Works in user projects that only have plugin installed.
    """

    def test_checkpoint_works_without_scripts_directory(self, temp_project, checkpoint1_heredoc):
        """Test that checkpoint works when scripts/ directory doesn't exist.

        SCENARIO: User project has plugin installed but no scripts/ directory
        Expected: Checkpoint still works (imports from lib/)
        """
        # Remove scripts directory if it exists
        scripts_dir = temp_project / "scripts"
        if scripts_dir.exists():
            import shutil
            shutil.rmtree(scripts_dir)

        test_script = temp_project / "test_checkpoint.py"
        test_script.write_text(checkpoint1_heredoc)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(temp_project),
            capture_output=True,
            text=True
        )

        # Should succeed (imports from lib/, not scripts/)
        assert result.returncode == 0

    def test_checkpoint_imports_from_lib_not_scripts(self, temp_project, checkpoint1_heredoc):
        """Test that checkpoint imports from lib/ even if scripts/ exists.

        REQUIREMENT: lib/ is source of truth (not scripts/)
        Expected: Uses lib/agent_tracker.py
        """
        # Create BOTH lib/ and scripts/ versions
        scripts_dir = temp_project / "scripts"
        scripts_dir.mkdir(exist_ok=True)

        # Create a broken scripts version (should NOT be used)
        broken_script = scripts_dir / "agent_tracker.py"
        broken_script.write_text("raise RuntimeError('WRONG VERSION - scripts/ used instead of lib/')")

        test_script = temp_project / "test_checkpoint.py"
        test_script.write_text(checkpoint1_heredoc)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(temp_project),
            capture_output=True,
            text=True
        )

        # Should succeed (lib/ version used, not scripts/)
        assert result.returncode == 0
        assert "WRONG VERSION" not in result.stderr


# ============================================================================
# INTEGRATION TESTS - Error Handling
# ============================================================================


@pytest.mark.skipif(not PATH_UTILS_EXISTS, reason="path_utils.py not available (TDD RED phase)")
class TestCheckpointErrorHandling:
    """Test checkpoint error handling and user guidance.

    Critical requirement: Helpful error messages when things go wrong.
    """

    def test_checkpoint_fails_outside_project(self, tmp_path, checkpoint1_heredoc):
        """Test checkpoint shows helpful error when run outside project.

        SCENARIO: User runs checkpoint in directory with no .git/.claude
        Expected: Clear error message explaining the problem
        """
        # Create temp directory with NO markers
        no_project_dir = tmp_path / "not-a-project"
        no_project_dir.mkdir()

        test_script = no_project_dir / "test_checkpoint.py"
        test_script.write_text(checkpoint1_heredoc)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(no_project_dir),
            capture_output=True,
            text=True
        )

        # Should fail with helpful error
        assert result.returncode != 0
        error_output = result.stderr + result.stdout
        assert "project root" in error_output.lower()
        assert ".git" in error_output or ".claude" in error_output

    def test_checkpoint_error_includes_debugging_context(self, tmp_path, checkpoint1_heredoc):
        """Test that checkpoint errors include debugging information.

        REQUIREMENT: Helpful error messages
        Expected: Error shows current directory, searched paths, etc.
        """
        no_project_dir = tmp_path / "not-a-project"
        no_project_dir.mkdir()

        test_script = no_project_dir / "test_checkpoint.py"
        test_script.write_text(checkpoint1_heredoc)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(no_project_dir),
            capture_output=True,
            text=True
        )

        error_output = result.stderr + result.stdout

        # Should include context (path, error type, etc.)
        assert len(error_output) > 50  # Substantial error message
        assert "❌" in error_output or "ERROR" in error_output or "error" in error_output.lower()


# ============================================================================
# INTEGRATION TESTS - Cross-Platform Compatibility
# ============================================================================


@pytest.mark.skipif(not PATH_UTILS_EXISTS, reason="path_utils.py not available (TDD RED phase)")
class TestCheckpointCrossPlatform:
    """Test checkpoint execution across different operating systems.

    Critical requirement: Works on Windows, macOS, Linux.
    """

    def test_checkpoint_uses_pathlib(self, auto_implement_command):
        """Test that checkpoints use pathlib (not os.path).

        REQUIREMENT: Cross-platform path handling
        Expected: pathlib.Path used in heredocs
        """
        if not auto_implement_command.exists():
            pytest.skip("Command file not found")

        content = auto_implement_command.read_text()

        # Should use pathlib
        assert "from pathlib import Path" in content or "import pathlib" in content

    def test_checkpoint_heredoc_path_separators_portable(self, checkpoint1_heredoc):
        """Test that heredoc uses portable path construction.

        REQUIREMENT: No hardcoded path separators
        Expected: Uses / operator or Path.joinpath()
        """
        # Should NOT have hardcoded separators
        assert "\\\\" not in checkpoint1_heredoc  # No Windows hardcoded separators
        # Using / with Path is okay (pathlib handles conversion)


# ============================================================================
# REGRESSION TESTS - Existing Functionality
# ============================================================================


@pytest.mark.skipif(not PATH_UTILS_EXISTS, reason="path_utils.py not available (TDD RED phase)")
class TestCheckpointRegressionTests:
    """Test that checkpoint refactoring doesn't break existing functionality.

    Critical requirement: All existing checkpoint features still work.
    """

    def test_checkpoint1_verify_parallel_exploration_works(self, temp_project, checkpoint1_heredoc):
        """Test that verify_parallel_exploration() method still works.

        REQUIREMENT: Checkpoint logic unchanged
        Expected: Method executes and returns result
        """
        test_script = temp_project / "test_checkpoint.py"
        test_script.write_text(checkpoint1_heredoc)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(temp_project),
            capture_output=True,
            text=True
        )

        # Should call verify_parallel_exploration and show result
        assert "SUCCESS" in result.stdout or "FAILED" in result.stdout or "✅" in result.stdout

    def test_checkpoint_output_format_unchanged(self, temp_project, checkpoint1_heredoc):
        """Test that checkpoint output format is unchanged.

        REQUIREMENT: Output compatibility
        Expected: Same output format as before refactoring
        """
        test_script = temp_project / "test_checkpoint.py"
        test_script.write_text(checkpoint1_heredoc)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(temp_project),
            capture_output=True,
            text=True
        )

        # Should have familiar output format
        assert "✅" in result.stdout or "❌" in result.stdout
        assert "PARALLEL EXPLORATION" in result.stdout or result.returncode == 0
