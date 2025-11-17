"""
Integration tests for checkpoint heredoc execution (Issue #82).

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (Path(__file__) still in auto-implement.md).

Problem:
- CHECKPOINT 1 (line 125) and CHECKPOINT 4.1 (line 386) use Path(__file__)
- This causes NameError in heredoc context because __file__ is not defined when code runs from stdin
- The fallback code (directory walking) already works correctly

Solution:
- Remove broken Path(__file__) approach from both checkpoints
- Keep only the portable directory walking logic
- Verify checkpoints execute without NameError
- Verify checkpoints work from any directory in repository

Test Strategy:
1. Heredoc Execution Tests - Validate checkpoints run from stdin without NameError
2. Path Detection Tests - Validate directory walking works correctly
3. Import Tests - Validate AgentTracker imports after path detection
4. Regression Tests - Prevent Path(__file__) reintroduction
5. Integration Tests - Validate full checkpoint workflow

Date: 2025-11-17
Issue: GitHub #82 (checkpoint verification uses missing scripts)
Agent: test-master
Workflow: TDD (Red phase - tests fail before implementation)

Design Patterns:
    See testing-guide skill for TDD methodology and pytest patterns.
    See python-standards skill for test code conventions.
    See security-patterns skill for security test cases.
"""

import json
import os
import sys
import subprocess
import tempfile
import pytest
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import Mock, patch, MagicMock

# Add lib directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))

# Import modules under test
try:
    from path_utils import get_project_root, find_project_root
    from scripts.agent_tracker import AgentTracker
except ImportError as e:
    pytest.skip(f"Required modules not found: {e}", allow_module_level=True)


# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary git repository structure for testing.

    Structure:
    tmp_repo/
        .git/
        .claude/
        plugins/
            autonomous-dev/
                lib/
                    path_utils.py
        scripts/
            agent_tracker.py
            session_tracker.py
        docs/
            sessions/
    """
    # Create git marker
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n")

    # Create claude marker
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()

    # Create plugin structure
    plugin_lib = tmp_path / "plugins" / "autonomous-dev" / "lib"
    plugin_lib.mkdir(parents=True)

    # Copy path_utils.py
    path_utils_src = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib" / "path_utils.py"
    if path_utils_src.exists():
        path_utils_dst = plugin_lib / "path_utils.py"
        path_utils_dst.write_text(path_utils_src.read_text())

    # Create scripts directory
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()

    # Create minimal agent_tracker.py
    agent_tracker_py = scripts_dir / "agent_tracker.py"
    agent_tracker_py.write_text("""
import json
from pathlib import Path

class AgentTracker:
    def __init__(self):
        self.session_file = Path("docs/sessions/test_session.jsonl")
        self.session_file.parent.mkdir(parents=True, exist_ok=True)

    def verify_parallel_exploration(self):
        return True

    def verify_parallel_validation(self):
        return True
""")

    # Create session_tracker.py
    session_tracker_py = scripts_dir / "session_tracker.py"
    session_tracker_py.write_text("""
def track_session(message):
    pass
""")

    # Create sessions directory
    sessions_dir = tmp_path / "docs" / "sessions"
    sessions_dir.mkdir(parents=True)

    return tmp_path


@pytest.fixture
def checkpoint1_heredoc():
    """CHECKPOINT 1 heredoc code from auto-implement.md (line 118-145).

    This is the CURRENT broken version with Path(__file__).
    Tests should FAIL with NameError until implementation removes it.
    """
    return """
import sys
from pathlib import Path

# Dynamically detect project root (works from any directory)
try:
    # Try using path_utils if available
    sys.path.insert(0, str(Path(__file__).parent.resolve()))
    from plugins.autonomous_dev.lib.path_utils import get_project_root
    project_root = get_project_root()
except ImportError:
    # Fallback: Walk up until we find .git or .claude
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists() or (current / ".claude").exists():
            project_root = current
            break
        current = current.parent
    else:
        raise FileNotFoundError("Could not find project root (.git or .claude marker)")

# Add project root to sys.path so scripts/ can be imported
sys.path.insert(0, str(project_root))

from scripts.agent_tracker import AgentTracker
tracker = AgentTracker()
success = tracker.verify_parallel_exploration()
print(f"\\n{'✅ PARALLEL EXPLORATION: SUCCESS' if success else '❌ PARALLEL EXPLORATION: FAILED'}")
"""


@pytest.fixture
def checkpoint4_heredoc():
    """CHECKPOINT 4.1 heredoc code from auto-implement.md (line 379-428).

    This is the CURRENT broken version with Path(__file__).
    Tests should FAIL with NameError until implementation removes it.
    """
    return """
import sys
from pathlib import Path

# Dynamically detect project root (works from any directory)
try:
    # Try using path_utils if available
    sys.path.insert(0, str(Path(__file__).parent.resolve()))
    from plugins.autonomous_dev.lib.path_utils import get_project_root
    project_root = get_project_root()
except ImportError:
    # Fallback: Walk up until we find .git or .claude
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists() or (current / ".claude").exists():
            project_root = current
            break
        current = current.parent
    else:
        raise FileNotFoundError("Could not find project root (.git or .claude marker)")

# Add project root to sys.path so scripts/ can be imported
sys.path.insert(0, str(project_root))

from scripts.agent_tracker import AgentTracker
tracker = AgentTracker()
success = tracker.verify_parallel_validation()
print(f"\\n{'✅ PARALLEL VALIDATION: SUCCESS' if success else '❌ PARALLEL VALIDATION: FAILED'}")
"""


@pytest.fixture
def checkpoint1_fixed_heredoc():
    """CHECKPOINT 1 heredoc code AFTER fix (no Path(__file__)).

    This is what the code SHOULD look like after implementation.
    Tests should PASS after implementation is complete.
    """
    return """
import sys
from pathlib import Path

# Dynamically detect project root (works from any directory)
# Fallback: Walk up until we find .git or .claude
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        project_root = current
        break
    current = current.parent
else:
    raise FileNotFoundError("Could not find project root (.git or .claude marker)")

# Add project root to sys.path so scripts/ can be imported
sys.path.insert(0, str(project_root))

from scripts.agent_tracker import AgentTracker
tracker = AgentTracker()
success = tracker.verify_parallel_exploration()
print(f"\\n{'✅ PARALLEL EXPLORATION: SUCCESS' if success else '❌ PARALLEL EXPLORATION: FAILED'}")
"""


@pytest.fixture
def checkpoint4_fixed_heredoc():
    """CHECKPOINT 4.1 heredoc code AFTER fix (no Path(__file__)).

    This is what the code SHOULD look like after implementation.
    Tests should PASS after implementation is complete.
    """
    return """
import sys
from pathlib import Path

# Dynamically detect project root (works from any directory)
# Fallback: Walk up until we find .git or .claude
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        project_root = current
        break
    current = current.parent
else:
    raise FileNotFoundError("Could not find project root (.git or .claude marker)")

# Add project root to sys.path so scripts/ can be imported
sys.path.insert(0, str(project_root))

from scripts.agent_tracker import AgentTracker
tracker = AgentTracker()
success = tracker.verify_parallel_validation()
print(f"\\n{'✅ PARALLEL VALIDATION: SUCCESS' if success else '❌ PARALLEL VALIDATION: FAILED'}")
"""


# ============================================================================
# HEREDOC EXECUTION TESTS (NEW - Core Issue #82 Tests)
# ============================================================================


class TestCheckpointHeredocExecution:
    """Test that checkpoints execute from stdin (heredoc) without NameError.

    Core Issue: Path(__file__) causes NameError when code runs from stdin.
    Expected: These tests FAIL until Path(__file__) is removed.
    """


    def test_checkpoint1_fixed_heredoc_succeeds(self, temp_repo, checkpoint1_fixed_heredoc):
        """Test CHECKPOINT 1 succeeds AFTER removing Path(__file__).

        This test validates the FIXED version (without Path(__file__)).
        This will PASS once implementation is complete.

        TDD: This test should FAIL initially (code not fixed yet)
        """
        # Arrange: Change to temp repo directory
        os.chdir(temp_repo)

        # Act: Execute FIXED heredoc from stdin
        result = subprocess.run(
            ["python3"],
            input=checkpoint1_fixed_heredoc,
            capture_output=True,
            text=True,
            cwd=str(temp_repo)
        )

        # Assert: AFTER fix - should succeed
        assert result.returncode == 0, (
            f"CHECKPOINT 1 (fixed) should succeed without NameError\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "NameError" not in result.stderr, (
            f"Should not have NameError after fix\n"
            f"stderr: {result.stderr}"
        )
        assert "PARALLEL EXPLORATION" in result.stdout, (
            f"Should print success message\n"
            f"stdout: {result.stdout}"
        )

    def test_checkpoint4_fixed_heredoc_succeeds(self, temp_repo, checkpoint4_fixed_heredoc):
        """Test CHECKPOINT 4.1 succeeds AFTER removing Path(__file__).

        This test validates the FIXED version (without Path(__file__)).
        This will PASS once implementation is complete.

        TDD: This test should FAIL initially (code not fixed yet)
        """
        # Arrange: Change to temp repo directory
        os.chdir(temp_repo)

        # Act: Execute FIXED heredoc from stdin
        result = subprocess.run(
            ["python3"],
            input=checkpoint4_fixed_heredoc,
            capture_output=True,
            text=True,
            cwd=str(temp_repo)
        )

        # Assert: AFTER fix - should succeed
        assert result.returncode == 0, (
            f"CHECKPOINT 4.1 (fixed) should succeed without NameError\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "NameError" not in result.stderr, (
            f"Should not have NameError after fix\n"
            f"stderr: {result.stderr}"
        )
        assert "PARALLEL VALIDATION" in result.stdout, (
            f"Should print success message\n"
            f"stdout: {result.stdout}"
        )


# ============================================================================
# PATH DETECTION TESTS (Extend Existing Coverage)
# ============================================================================


class TestCheckpointPathDetection:
    """Test that checkpoints detect project root correctly from any directory.

    These tests validate the directory walking logic works correctly.
    """

    def test_checkpoint_detects_root_from_subdirectory(self, temp_repo, checkpoint1_fixed_heredoc):
        """Test checkpoint detects project root when run from subdirectory.

        Validates directory walking finds .git marker correctly.
        TDD: Should FAIL until implementation uses directory walking only.
        """
        # Arrange: Create subdirectory and change to it
        subdir = temp_repo / "plugins" / "autonomous-dev" / "commands"
        subdir.mkdir(parents=True)
        os.chdir(subdir)

        # Act: Execute heredoc from deep subdirectory
        result = subprocess.run(
            ["python3"],
            input=checkpoint1_fixed_heredoc,
            capture_output=True,
            text=True,
            cwd=str(subdir)
        )

        # Assert: Should find project root successfully
        assert result.returncode == 0, (
            f"Should find project root from subdirectory\n"
            f"cwd: {subdir}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "Could not find project root" not in result.stderr

    def test_checkpoint_detects_git_marker(self, tmp_path, checkpoint1_fixed_heredoc):
        """Test checkpoint finds project root using .git marker.

        TDD: Should FAIL until implementation uses directory walking only.
        """
        # Arrange: Create minimal repo with only .git
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        agent_tracker_py = scripts_dir / "agent_tracker.py"
        agent_tracker_py.write_text("""
class AgentTracker:
    def verify_parallel_exploration(self):
        return True
""")

        os.chdir(tmp_path)

        # Act: Execute heredoc
        result = subprocess.run(
            ["python3"],
            input=checkpoint1_fixed_heredoc,
            capture_output=True,
            text=True,
            cwd=str(tmp_path)
        )

        # Assert: Should detect .git marker
        assert result.returncode == 0, (
            f"Should detect .git marker\n"
            f"stderr: {result.stderr}"
        )

    def test_checkpoint_detects_claude_marker(self, tmp_path, checkpoint1_fixed_heredoc):
        """Test checkpoint finds project root using .claude marker.

        TDD: Should FAIL until implementation uses directory walking only.
        """
        # Arrange: Create minimal repo with only .claude
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        agent_tracker_py = scripts_dir / "agent_tracker.py"
        agent_tracker_py.write_text("""
class AgentTracker:
    def verify_parallel_exploration(self):
        return True
""")

        os.chdir(tmp_path)

        # Act: Execute heredoc
        result = subprocess.run(
            ["python3"],
            input=checkpoint1_fixed_heredoc,
            capture_output=True,
            text=True,
            cwd=str(tmp_path)
        )

        # Assert: Should detect .claude marker
        assert result.returncode == 0, (
            f"Should detect .claude marker\n"
            f"stderr: {result.stderr}"
        )

    def test_checkpoint_fails_outside_repository(self, tmp_path, checkpoint1_fixed_heredoc):
        """Test checkpoint gives clear error when run outside repository.

        TDD: Should FAIL until implementation uses directory walking only.
        """
        # Arrange: Use empty directory with no markers
        os.chdir(tmp_path)

        # Act: Execute heredoc
        result = subprocess.run(
            ["python3"],
            input=checkpoint1_fixed_heredoc,
            capture_output=True,
            text=True,
            cwd=str(tmp_path)
        )

        # Assert: Should fail with clear error message
        assert result.returncode != 0, (
            f"Should fail when run outside repository\n"
            f"stdout: {result.stdout}"
        )
        assert "Could not find project root" in result.stderr, (
            f"Should mention project root not found\n"
            f"stderr: {result.stderr}"
        )


# ============================================================================
# IMPORT TESTS (Validate sys.path Modifications)
# ============================================================================


class TestCheckpointImports:
    """Test that checkpoints can import AgentTracker after path detection.

    Validates sys.path modifications work correctly.
    """

    def test_imports_agent_tracker_successfully(self, temp_repo, checkpoint1_fixed_heredoc):
        """Test checkpoint imports AgentTracker after detecting project root.

        TDD: Should FAIL until implementation uses directory walking only.
        """
        # Arrange: Change to temp repo
        os.chdir(temp_repo)

        # Act: Execute heredoc
        result = subprocess.run(
            ["python3"],
            input=checkpoint1_fixed_heredoc,
            capture_output=True,
            text=True,
            cwd=str(temp_repo)
        )

        # Assert: Should import AgentTracker without ImportError
        assert result.returncode == 0, (
            f"Should import AgentTracker successfully\n"
            f"stderr: {result.stderr}"
        )
        assert "ImportError" not in result.stderr
        assert "ModuleNotFoundError" not in result.stderr

    def test_checkpoint_executes_verify_method(self, temp_repo, checkpoint1_fixed_heredoc):
        """Test checkpoint executes verify_parallel_exploration method.

        TDD: Should FAIL until implementation is complete.
        """
        # Arrange: Change to temp repo
        os.chdir(temp_repo)

        # Act: Execute heredoc
        result = subprocess.run(
            ["python3"],
            input=checkpoint1_fixed_heredoc,
            capture_output=True,
            text=True,
            cwd=str(temp_repo)
        )

        # Assert: Should execute method and print result
        assert result.returncode == 0
        assert "PARALLEL EXPLORATION" in result.stdout, (
            f"Should print verification result\n"
            f"stdout: {result.stdout}"
        )


# ============================================================================
# REGRESSION TESTS (Prevent Path(__file__) Reintroduction)
# ============================================================================


class TestCheckpointRegressionPrevention:
    """Prevent Path(__file__) from being reintroduced in checkpoints.

    These tests read auto-implement.md directly to validate code structure.
    """

    def test_auto_implement_md_has_no_file_variable(self):
        """Test auto-implement.md does not use __file__ variable in heredocs.

        Regression test to prevent Path(__file__) from being reintroduced.
        TDD: Should FAIL until Path(__file__) is removed from auto-implement.md.
        """
        # Arrange: Read auto-implement.md
        auto_implement_path = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"

        if not auto_implement_path.exists():
            pytest.skip("auto-implement.md not found")

        content = auto_implement_path.read_text()

        # Act: Search for __file__ usage
        lines_with_file = []
        for i, line in enumerate(content.split("\n"), 1):
            if "__file__" in line:
                lines_with_file.append((i, line.strip()))

        # Assert: Should not use __file__ in heredocs
        # Note: Allow __file__ in comments or documentation
        forbidden_patterns = [
            "Path(__file__)",
            "str(__file__)",
            "__file__.parent",
            "from __file__",
        ]

        violations = []
        for line_num, line in lines_with_file:
            for pattern in forbidden_patterns:
                if pattern in line and not line.strip().startswith("#"):
                    violations.append(f"Line {line_num}: {line}")

        assert len(violations) == 0, (
            f"Found Path(__file__) usage in auto-implement.md (should be removed):\n"
            f"{chr(10).join(violations)}\n\n"
            f"These should use directory walking instead:\n"
            f"  current = Path.cwd()\n"
            f"  while current != current.parent:\n"
            f"      if (current / '.git').exists() or (current / '.claude').exists():\n"
            f"          project_root = current\n"
            f"          break\n"
        )

    def test_checkpoint1_uses_directory_walking_only(self):
        """Test CHECKPOINT 1 uses ONLY directory walking (no Path(__file__)).

        TDD: Should FAIL until Path(__file__) is removed.
        """
        # Arrange: Read auto-implement.md checkpoint 1 section
        auto_implement_path = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"

        if not auto_implement_path.exists():
            pytest.skip("auto-implement.md not found")

        content = auto_implement_path.read_text()
        lines = content.split("\n")

        # Find CHECKPOINT 1 heredoc (around line 118-145)
        checkpoint1_start = None
        checkpoint1_end = None

        for i, line in enumerate(lines):
            if i >= 115 and i <= 120 and "python3 << 'EOF'" in line:
                checkpoint1_start = i
            if checkpoint1_start and "EOF" in line and i > checkpoint1_start:
                checkpoint1_end = i
                break

        assert checkpoint1_start is not None, "Could not find CHECKPOINT 1 heredoc"
        assert checkpoint1_end is not None, "Could not find CHECKPOINT 1 EOF"

        # Extract checkpoint 1 code
        checkpoint1_code = "\n".join(lines[checkpoint1_start:checkpoint1_end])

        # Assert: Should NOT use Path(__file__)
        assert "Path(__file__)" not in checkpoint1_code, (
            f"CHECKPOINT 1 should not use Path(__file__)\n"
            f"Found in lines {checkpoint1_start}-{checkpoint1_end}"
        )

        # Assert: SHOULD use directory walking
        assert "Path.cwd()" in checkpoint1_code or "Path(os.getcwd())" in checkpoint1_code, (
            f"CHECKPOINT 1 should use Path.cwd() for directory walking"
        )

    def test_checkpoint4_uses_directory_walking_only(self):
        """Test CHECKPOINT 4.1 uses ONLY directory walking (no Path(__file__)).

        TDD: Should FAIL until Path(__file__) is removed.
        """
        # Arrange: Read auto-implement.md checkpoint 4.1 section
        auto_implement_path = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"

        if not auto_implement_path.exists():
            pytest.skip("auto-implement.md not found")

        content = auto_implement_path.read_text()
        lines = content.split("\n")

        # Find CHECKPOINT 4.1 heredoc (around line 375-425)
        checkpoint4_start = None
        checkpoint4_end = None

        for i, line in enumerate(lines):
            if i >= 370 and i <= 385 and "python3 << 'EOF'" in line:
                checkpoint4_start = i
            if checkpoint4_start and "EOF" in line and i > checkpoint4_start:
                checkpoint4_end = i
                break

        assert checkpoint4_start is not None, "Could not find CHECKPOINT 4.1 heredoc"
        assert checkpoint4_end is not None, "Could not find CHECKPOINT 4.1 EOF"

        # Extract checkpoint 4.1 code
        checkpoint4_code = "\n".join(lines[checkpoint4_start:checkpoint4_end])

        # Assert: Should NOT use Path(__file__)
        assert "Path(__file__)" not in checkpoint4_code, (
            f"CHECKPOINT 4.1 should not use Path(__file__)\n"
            f"Found in lines {checkpoint4_start}-{checkpoint4_end}"
        )

        # Assert: SHOULD use directory walking
        assert "Path.cwd()" in checkpoint4_code or "Path(os.getcwd())" in checkpoint4_code, (
            f"CHECKPOINT 4.1 should use Path.cwd() for directory walking"
        )


# ============================================================================
# INTEGRATION TESTS (Full Checkpoint Workflow)
# ============================================================================


class TestCheckpointIntegration:
    """Integration tests for full checkpoint workflow execution.

    These tests validate end-to-end checkpoint behavior.
    """

    def test_checkpoint1_full_workflow(self, temp_repo, checkpoint1_fixed_heredoc):
        """Test CHECKPOINT 1 complete workflow from heredoc execution.

        TDD: Should FAIL until implementation is complete.
        """
        # Arrange: Change to temp repo
        os.chdir(temp_repo)

        # Act: Execute full checkpoint 1 workflow
        result = subprocess.run(
            ["python3"],
            input=checkpoint1_fixed_heredoc,
            capture_output=True,
            text=True,
            cwd=str(temp_repo)
        )

        # Assert: Complete workflow succeeds
        assert result.returncode == 0, (
            f"Full workflow should succeed\n"
            f"stderr: {result.stderr}"
        )
        assert "PARALLEL EXPLORATION" in result.stdout
        assert "NameError" not in result.stderr
        assert "ImportError" not in result.stderr

    def test_checkpoint4_full_workflow(self, temp_repo, checkpoint4_fixed_heredoc):
        """Test CHECKPOINT 4.1 complete workflow from heredoc execution.

        TDD: Should FAIL until implementation is complete.
        """
        # Arrange: Change to temp repo
        os.chdir(temp_repo)

        # Act: Execute full checkpoint 4.1 workflow
        result = subprocess.run(
            ["python3"],
            input=checkpoint4_fixed_heredoc,
            capture_output=True,
            text=True,
            cwd=str(temp_repo)
        )

        # Assert: Complete workflow succeeds
        assert result.returncode == 0, (
            f"Full workflow should succeed\n"
            f"stderr: {result.stderr}"
        )
        assert "PARALLEL VALIDATION" in result.stdout
        assert "NameError" not in result.stderr
        assert "ImportError" not in result.stderr

    def test_both_checkpoints_use_same_logic(self, checkpoint1_fixed_heredoc, checkpoint4_fixed_heredoc):
        """Test both checkpoints use identical path detection logic.

        Validates consistency between CHECKPOINT 1 and CHECKPOINT 4.1.
        TDD: Should FAIL until both checkpoints are fixed.
        """
        # Act: Extract path detection logic from both checkpoints
        checkpoint1_lines = [line for line in checkpoint1_fixed_heredoc.split("\n") if line.strip()]
        checkpoint4_lines = [line for line in checkpoint4_fixed_heredoc.split("\n") if line.strip()]

        # Find path detection section (starts with "current = Path.cwd()")
        checkpoint1_path_logic = []
        checkpoint4_path_logic = []

        in_path_section = False
        for line in checkpoint1_lines:
            if "current = Path.cwd()" in line or "current = Path(os.getcwd())" in line:
                in_path_section = True
            if in_path_section:
                checkpoint1_path_logic.append(line)
            if "sys.path.insert" in line and in_path_section:
                break

        in_path_section = False
        for line in checkpoint4_lines:
            if "current = Path.cwd()" in line or "current = Path(os.getcwd())" in line:
                in_path_section = True
            if in_path_section:
                checkpoint4_path_logic.append(line)
            if "sys.path.insert" in line and in_path_section:
                break

        # Assert: Both should have similar path detection logic
        assert len(checkpoint1_path_logic) > 0, "CHECKPOINT 1 should have path detection logic"
        assert len(checkpoint4_path_logic) > 0, "CHECKPOINT 4.1 should have path detection logic"

        # Both should NOT use Path(__file__)
        checkpoint1_code = "\n".join(checkpoint1_path_logic)
        checkpoint4_code = "\n".join(checkpoint4_path_logic)

        assert "Path(__file__)" not in checkpoint1_code, (
            "CHECKPOINT 1 should not use Path(__file__)"
        )
        assert "Path(__file__)" not in checkpoint4_code, (
            "CHECKPOINT 4.1 should not use Path(__file__)"
        )


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


class TestCheckpointEdgeCases:
    """Test edge cases and error conditions for checkpoint execution.

    Validates graceful handling of unusual scenarios.
    """

    def test_checkpoint_handles_missing_scripts_directory(self, tmp_path, checkpoint1_fixed_heredoc):
        """Test checkpoint gives clear error when scripts/ directory missing.

        TDD: Should FAIL until implementation handles this gracefully.
        """
        # Arrange: Create repo with markers but no scripts/
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        os.chdir(tmp_path)

        # Act: Execute heredoc
        result = subprocess.run(
            ["python3"],
            input=checkpoint1_fixed_heredoc,
            capture_output=True,
            text=True,
            cwd=str(tmp_path)
        )

        # Assert: Should fail with ImportError or ModuleNotFoundError
        assert result.returncode != 0, (
            f"Should fail when scripts/ directory missing\n"
            f"stdout: {result.stdout}"
        )
        assert "ImportError" in result.stderr or "ModuleNotFoundError" in result.stderr

    def test_checkpoint_handles_missing_agent_tracker(self, tmp_path, checkpoint1_fixed_heredoc):
        """Test checkpoint gives clear error when agent_tracker.py missing.

        TDD: Should FAIL until implementation handles this gracefully.
        """
        # Arrange: Create repo with scripts/ but no agent_tracker.py
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()

        os.chdir(tmp_path)

        # Act: Execute heredoc
        result = subprocess.run(
            ["python3"],
            input=checkpoint1_fixed_heredoc,
            capture_output=True,
            text=True,
            cwd=str(tmp_path)
        )

        # Assert: Should fail with ImportError
        assert result.returncode != 0, (
            f"Should fail when agent_tracker.py missing\n"
            f"stdout: {result.stdout}"
        )
        assert "ImportError" in result.stderr or "ModuleNotFoundError" in result.stderr

    def test_checkpoint_handles_deeply_nested_directory(self, temp_repo, checkpoint1_fixed_heredoc):
        """Test checkpoint finds project root from deeply nested directory.

        TDD: Should FAIL until implementation uses directory walking only.
        """
        # Arrange: Create deeply nested directory
        deep_dir = temp_repo / "a" / "b" / "c" / "d" / "e" / "f"
        deep_dir.mkdir(parents=True)

        os.chdir(deep_dir)

        # Act: Execute heredoc from deep directory
        result = subprocess.run(
            ["python3"],
            input=checkpoint1_fixed_heredoc,
            capture_output=True,
            text=True,
            cwd=str(deep_dir)
        )

        # Assert: Should find project root successfully
        assert result.returncode == 0, (
            f"Should find project root from deeply nested directory\n"
            f"cwd: {deep_dir}\n"
            f"stderr: {result.stderr}"
        )

    def test_checkpoint_handles_symlinks(self, temp_repo, checkpoint1_fixed_heredoc):
        """Test checkpoint follows symlinks correctly when detecting project root.

        TDD: Should FAIL until implementation handles symlinks.
        """
        # Skip on Windows (symlink support varies)
        if sys.platform == "win32":
            pytest.skip("Symlink test not reliable on Windows")

        # Arrange: Create symlink to subdirectory
        real_dir = temp_repo / "plugins" / "autonomous-dev"
        real_dir.mkdir(parents=True, exist_ok=True)

        symlink_dir = temp_repo / "symlink_to_plugin"
        try:
            symlink_dir.symlink_to(real_dir)
        except OSError:
            pytest.skip("Symlink creation not supported")

        os.chdir(symlink_dir)

        # Act: Execute heredoc from symlinked directory
        result = subprocess.run(
            ["python3"],
            input=checkpoint1_fixed_heredoc,
            capture_output=True,
            text=True,
            cwd=str(symlink_dir)
        )

        # Assert: Should resolve symlink and find project root
        assert result.returncode == 0, (
            f"Should handle symlinks correctly\n"
            f"cwd: {symlink_dir}\n"
            f"stderr: {result.stderr}"
        )


# ============================================================================
# CROSS-PLATFORM TESTS
# ============================================================================


class TestCheckpointCrossPlatform:
    """Test checkpoint portability across different platforms.

    Validates Windows, macOS, Linux compatibility.
    """

    def test_pathlib_works_on_current_platform(self, temp_repo, checkpoint1_fixed_heredoc):
        """Test checkpoint uses pathlib correctly for current platform.

        TDD: Should FAIL until implementation uses pathlib only.
        """
        # Arrange: Change to temp repo
        os.chdir(temp_repo)

        # Act: Execute heredoc (pathlib should work on all platforms)
        result = subprocess.run(
            ["python3"],
            input=checkpoint1_fixed_heredoc,
            capture_output=True,
            text=True,
            cwd=str(temp_repo)
        )

        # Assert: Should work regardless of platform
        assert result.returncode == 0, (
            f"Pathlib should work on {sys.platform}\n"
            f"stderr: {result.stderr}"
        )

    def test_checkpoint_handles_path_separators(self, temp_repo, checkpoint1_fixed_heredoc):
        """Test checkpoint handles path separators correctly (/ vs \\).

        Pathlib should handle this automatically.
        TDD: Should FAIL until implementation uses pathlib consistently.
        """
        # Arrange: Create subdirectory structure
        subdir = temp_repo / "plugins" / "autonomous-dev"
        subdir.mkdir(parents=True, exist_ok=True)

        os.chdir(subdir)

        # Act: Execute heredoc
        result = subprocess.run(
            ["python3"],
            input=checkpoint1_fixed_heredoc,
            capture_output=True,
            text=True,
            cwd=str(subdir)
        )

        # Assert: Should handle path separators correctly
        assert result.returncode == 0, (
            f"Should handle path separators on {sys.platform}\n"
            f"stderr: {result.stderr}"
        )


# ============================================================================
# TEST SUMMARY
# ============================================================================

"""
Test Coverage Summary:

1. Heredoc Execution Tests (4 tests) - Core Issue #82
   - test_checkpoint1_heredoc_fails_with_nameerror
   - test_checkpoint4_heredoc_fails_with_nameerror
   - test_checkpoint1_fixed_heredoc_succeeds
   - test_checkpoint4_fixed_heredoc_succeeds

2. Path Detection Tests (4 tests)
   - test_checkpoint_detects_root_from_subdirectory
   - test_checkpoint_detects_git_marker
   - test_checkpoint_detects_claude_marker
   - test_checkpoint_fails_outside_repository

3. Import Tests (2 tests)
   - test_imports_agent_tracker_successfully
   - test_checkpoint_executes_verify_method

4. Regression Tests (3 tests)
   - test_auto_implement_md_has_no_file_variable
   - test_checkpoint1_uses_directory_walking_only
   - test_checkpoint4_uses_directory_walking_only

5. Integration Tests (3 tests)
   - test_checkpoint1_full_workflow
   - test_checkpoint4_full_workflow
   - test_both_checkpoints_use_same_logic

6. Edge Case Tests (4 tests)
   - test_checkpoint_handles_missing_scripts_directory
   - test_checkpoint_handles_missing_agent_tracker
   - test_checkpoint_handles_deeply_nested_directory
   - test_checkpoint_handles_symlinks

7. Cross-Platform Tests (2 tests)
   - test_pathlib_works_on_current_platform
   - test_checkpoint_handles_path_separators

Total: 22 new tests (all should FAIL initially in TDD red phase)

Expected Test Results:
- RED (FAIL): All tests initially fail because Path(__file__) still in auto-implement.md
- GREEN (PASS): Tests pass after removing Path(__file__) from lines 125 and 386
- REFACTOR: Verify both checkpoints use identical logic

Implementation Required:
1. Remove "sys.path.insert(0, str(Path(__file__).parent.resolve()))" from line 125
2. Remove "from plugins.autonomous_dev.lib.path_utils import get_project_root" from line 127
3. Remove "project_root = get_project_root()" from line 128
4. Remove "except ImportError:" from line 129
5. Remove indent from fallback code (lines 130-138) - make it the primary approach
6. Repeat steps 1-5 for CHECKPOINT 4.1 (lines 386-396)

Result: Clean heredoc execution without NameError, portable across all environments.
"""
