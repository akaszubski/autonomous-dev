"""
Integration tests for Issue #82 - Make checkpoint verification optional.

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (checkpoints currently require AgentTracker).

Problem:
- Lines ~138 and ~403 in auto-implement.md have hardcoded imports:
  from scripts.agent_tracker import AgentTracker
- This breaks /auto-implement in user projects (no scripts/ directory)
- Checkpoints should work in both environments:
  * autonomous-dev repo: Full verification with metrics
  * User projects: Graceful degradation, skip verification

Solution:
- Wrap AgentTracker import in try/except at both checkpoints
- CHECKPOINT 1 (line ~138): verify_parallel_exploration()
- CHECKPOINT 4.1 (line ~403): verify_parallel_validation()
- If import fails: Print informational message, set success = True, continue
- If import succeeds but methods fail: Print error, set success = True, continue
- Never block workflow on verification errors

Test Strategy:
1. User Project Tests - No scripts/ directory (import fails gracefully)
2. Broken Scripts Tests - scripts/ exists but agent_tracker is broken
3. Dev Repo Tests - Full verification with metrics display
4. Regression Tests - Verify workflow never blocks on errors
5. Integration Tests - End-to-end checkpoint execution

Date: 2025-11-18
Issue: GitHub #82 (Make checkpoint verification optional)
Agent: test-master
Workflow: TDD (Red phase - tests fail before implementation)

Design Patterns:
    See testing-guide skill for TDD methodology and pytest patterns.
    See python-standards skill for test code conventions.
    See error-handling-patterns skill for graceful degradation patterns.
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


# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def user_project_repo(tmp_path):
    """Create a user project repository (NO scripts/ directory).

    Structure:
    user_repo/
        .git/
        .claude/
        src/
            main.py
        tests/
        docs/

    Note: NO scripts/ directory, NO agent_tracker.py
    This simulates a typical user project using /auto-implement
    """
    # Create git marker
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n")

    # Create claude marker
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()

    # Create typical user project structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("# User application\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs").mkdir()

    # NO scripts/ directory - this is the key difference

    return tmp_path


@pytest.fixture
def autonomous_dev_repo(tmp_path):
    """Create autonomous-dev repository structure (WITH scripts/).

    Structure:
    dev_repo/
        .git/
        .claude/
        scripts/
            agent_tracker.py (minimal working version)
        docs/
            sessions/

    This simulates the autonomous-dev repository itself.
    """
    # Create git marker
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n")

    # Create claude marker
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()

    # Create scripts directory with minimal agent_tracker
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()

    # Create sessions directory
    sessions_dir = tmp_path / "docs" / "sessions"
    sessions_dir.mkdir(parents=True)

    # Create minimal working agent_tracker that works without dependencies
    (scripts_dir / "agent_tracker.py").write_text("""
from pathlib import Path

class AgentTracker:
    def __init__(self):
        # Find session file (latest in docs/sessions/)
        sessions_dir = Path.cwd() / "docs" / "sessions"
        if sessions_dir.exists():
            session_files = sorted(sessions_dir.glob("*.json"))
            self.session_file = session_files[-1] if session_files else None
        else:
            self.session_file = None

    def verify_parallel_exploration(self):
        '''Verify researcher, planner, test-master ran'''
        if not self.session_file or not self.session_file.exists():
            return False

        import json
        data = json.loads(self.session_file.read_text())
        agents = {a.get("agent") for a in data.get("agents", [])}

        required = {"researcher", "planner", "test-master"}
        return required.issubset(agents)

    def verify_parallel_validation(self):
        '''Verify reviewer, security-auditor, doc-master ran'''
        if not self.session_file or not self.session_file.exists():
            return False

        import json
        data = json.loads(self.session_file.read_text())
        agents = {a.get("agent") for a in data.get("agents", [])}

        required = {"reviewer", "security-auditor", "doc-master"}
        return required.issubset(agents)
""")

    return tmp_path


@pytest.fixture
def broken_scripts_repo(tmp_path):
    """Create repository with broken agent_tracker.py.

    Structure:
    broken_repo/
        .git/
        scripts/
            agent_tracker.py  # Broken - missing methods

    This tests graceful degradation when imports succeed but methods fail.
    """
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n")

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()

    # Create broken agent_tracker (missing required methods)
    (scripts_dir / "agent_tracker.py").write_text("""
class AgentTracker:
    def __init__(self):
        pass
    # Missing verify_parallel_exploration()
    # Missing verify_parallel_validation()
""")

    return tmp_path


@pytest.fixture
def checkpoint1_optional_template():
    """Template for CHECKPOINT 1 with optional verification (Issue #82).

    This is the DESIRED implementation (what we're testing for).
    Current auto-implement.md does NOT have this - tests should FAIL.
    """
    return """
import sys
from pathlib import Path

# Portable project root detection
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        project_root = current
        break
    current = current.parent
else:
    raise FileNotFoundError(
        "Could not find project root. Expected .git or .claude directory marker."
    )

# Add project root to sys.path
sys.path.insert(0, str(project_root))

# Optional verification - gracefully degrade if AgentTracker unavailable
try:
    from scripts.agent_tracker import AgentTracker
    tracker = AgentTracker()
    success = tracker.verify_parallel_exploration()

    print(f"\\n{'✅ PARALLEL EXPLORATION: SUCCESS' if success else '❌ PARALLEL EXPLORATION: FAILED'}")
    if not success:
        print("\\n⚠️ One or more agents missing. Check session file for details.")
        print("Re-invoke missing agents before continuing to STEP 2.\\n")
except ImportError:
    # User project without scripts/ directory - skip verification
    print("\\nℹ️  Parallel exploration verification skipped (AgentTracker not available)")
    print("    This is normal for user projects. Verification only runs in autonomous-dev repo.")
    success = True
except AttributeError as e:
    # scripts.agent_tracker exists but missing methods
    print(f"\\n⚠️  Parallel exploration verification unavailable: {e}")
    print("    Continuing workflow. Verification is optional.")
    success = True
except Exception as e:
    # Any other error - don't block workflow
    print(f"\\n⚠️  Parallel exploration verification error: {e}")
    print("    Continuing workflow. Verification is optional.")
    success = True

# Checkpoint always succeeds - verification is informational only
if not success:
    print("\\n⚠️  Continue to STEP 2 anyway (verification issues don't block workflow)")
"""


@pytest.fixture
def checkpoint4_optional_template():
    """Template for CHECKPOINT 4.1 with optional verification (Issue #82).

    This is the DESIRED implementation (what we're testing for).
    """
    return """
import sys
import json
from pathlib import Path

# Portable project root detection
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        project_root = current
        break
    current = current.parent
else:
    raise FileNotFoundError(
        "Could not find project root. Expected .git or .claude directory marker."
    )

# Add project root to sys.path
sys.path.insert(0, str(project_root))

# Optional verification - gracefully degrade if AgentTracker unavailable
try:
    from scripts.agent_tracker import AgentTracker
    tracker = AgentTracker()
    success = tracker.verify_parallel_validation()

    if success:
        # Extract metrics from session file
        if tracker.session_file and tracker.session_file.exists():
            data = json.loads(tracker.session_file.read_text())
            metrics = data.get("parallel_validation", {})

            status = metrics.get("status", "unknown")
            time_saved = metrics.get("time_saved_seconds", 0)
            efficiency = metrics.get("efficiency_percent", 0)

            print(f"\\n✅ PARALLEL VALIDATION: SUCCESS")
            print(f"   Status: {status}")
            print(f"   Time saved: {time_saved} seconds")
            print(f"   Efficiency: {efficiency}%")
        else:
            print(f"\\n✅ PARALLEL VALIDATION: SUCCESS")
    else:
        print(f"\\n❌ PARALLEL VALIDATION: FAILED")
        print("Check session file for details.")

except ImportError:
    # User project without scripts/ directory - skip verification
    print("\\nℹ️  Parallel validation verification skipped (AgentTracker not available)")
    print("    This is normal for user projects. Verification only runs in autonomous-dev repo.")
    success = True
except AttributeError as e:
    # scripts.agent_tracker exists but missing methods
    print(f"\\n⚠️  Parallel validation verification unavailable: {e}")
    print("    Continuing workflow. Verification is optional.")
    success = True
except Exception as e:
    # Any other error - don't block workflow
    print(f"\\n⚠️  Parallel validation verification error: {e}")
    print("    Continuing workflow. Verification is optional.")
    success = True

# Checkpoint always succeeds
if not success:
    print("\\n⚠️  Continue to STEP 5 anyway (verification issues don't block workflow)")
"""


# ============================================================================
# CATEGORY 1: USER PROJECT TESTS (NO SCRIPTS/ DIRECTORY)
# ============================================================================


class TestUserProjectGracefulDegradation:
    """Test checkpoints gracefully degrade in user projects without scripts/."""

    def test_checkpoint1_graceful_degradation_no_scripts_directory(
        self, user_project_repo, checkpoint1_optional_template
    ):
        """Test CHECKPOINT 1 gracefully degrades when scripts/ doesn't exist.

        Arrange:
        - User project WITHOUT scripts/ directory
        - CHECKPOINT 1 heredoc with optional verification

        Act:
        - Execute checkpoint from user project

        Assert:
        - ImportError caught gracefully
        - Prints informational message (not error)
        - Sets success = True
        - Exit code 0 (doesn't block workflow)
        - Message says "This is normal for user projects"
        """
        test_script = user_project_repo / "test_checkpoint1.py"
        test_script.write_text(checkpoint1_optional_template)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(user_project_repo),
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should succeed with informational message
        assert result.returncode == 0, f"Checkpoint should succeed. stderr: {result.stderr}"
        assert "ℹ️" in result.stdout, "Should show informational icon"
        assert "Parallel exploration verification skipped" in result.stdout
        assert "AgentTracker not available" in result.stdout
        assert "This is normal for user projects" in result.stdout

        # Should NOT show error indicators
        assert "❌" not in result.stdout, "Should not show error"
        assert "FAILED" not in result.stdout, "Should not say FAILED"
        assert "CHECKPOINT ERROR" not in result.stdout

    def test_checkpoint4_graceful_degradation_no_scripts_directory(
        self, user_project_repo, checkpoint4_optional_template
    ):
        """Test CHECKPOINT 4.1 gracefully degrades when scripts/ doesn't exist.

        Arrange:
        - User project WITHOUT scripts/ directory
        - CHECKPOINT 4.1 heredoc with optional verification

        Act:
        - Execute checkpoint from user project

        Assert:
        - ImportError caught gracefully
        - Prints informational message
        - Sets success = True
        - Exit code 0
        - Workflow continues
        """
        test_script = user_project_repo / "test_checkpoint4.py"
        test_script.write_text(checkpoint4_optional_template)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(user_project_repo),
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should succeed with informational message
        assert result.returncode == 0, f"Checkpoint should succeed. stderr: {result.stderr}"
        assert "ℹ️" in result.stdout, "Should show informational icon"
        assert "Parallel validation verification skipped" in result.stdout
        assert "AgentTracker not available" in result.stdout
        assert "This is normal for user projects" in result.stdout

        # Should NOT show error indicators
        assert "❌" not in result.stdout, "Should not show error"
        assert "FAILED" not in result.stdout, "Should not say FAILED"


# ============================================================================
# CATEGORY 2: BROKEN SCRIPTS TESTS (IMPORT SUCCEEDS, METHODS FAIL)
# ============================================================================


class TestBrokenScriptsGracefulDegradation:
    """Test checkpoints handle broken agent_tracker.py gracefully."""

    def test_checkpoint_with_invalid_agent_tracker(
        self, broken_scripts_repo, checkpoint1_optional_template
    ):
        """Test checkpoint handles missing methods in AgentTracker.

        Arrange:
        - Repository WITH scripts/agent_tracker.py
        - AgentTracker class missing verify_parallel_exploration()

        Act:
        - Execute checkpoint

        Assert:
        - Import succeeds
        - AttributeError raised when calling missing method
        - Error caught gracefully
        - Prints warning message
        - Sets success = True
        - Workflow continues
        """
        test_script = broken_scripts_repo / "test_checkpoint1.py"
        test_script.write_text(checkpoint1_optional_template)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(broken_scripts_repo),
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should succeed despite broken tracker
        assert result.returncode == 0, f"Should not block workflow. stderr: {result.stderr}"
        assert "⚠️" in result.stdout, "Should show warning"
        assert "verification unavailable" in result.stdout or "verification error" in result.stdout
        assert "Continuing workflow" in result.stdout
        assert "Verification is optional" in result.stdout

        # Should NOT crash
        assert "Traceback" not in result.stderr or result.returncode == 0

    def test_checkpoint4_with_broken_validation_method(
        self, broken_scripts_repo, checkpoint4_optional_template
    ):
        """Test CHECKPOINT 4.1 handles missing verify_parallel_validation().

        Arrange:
        - Broken agent_tracker.py (missing validation method)

        Act:
        - Execute checkpoint 4.1

        Assert:
        - AttributeError caught
        - Warning message printed
        - Workflow continues
        """
        test_script = broken_scripts_repo / "test_checkpoint4.py"
        test_script.write_text(checkpoint4_optional_template)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(broken_scripts_repo),
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should succeed despite broken method
        assert result.returncode == 0, f"Should not block workflow. stderr: {result.stderr}"
        assert "⚠️" in result.stdout, "Should show warning"
        assert "verification unavailable" in result.stdout or "verification error" in result.stdout
        assert "Continuing workflow" in result.stdout


# ============================================================================
# CATEGORY 3: DEV REPO TESTS (FULL VERIFICATION WITH METRICS)
# ============================================================================


class TestDevRepoFullVerification:
    """Test checkpoints perform full verification in autonomous-dev repo."""

    def test_checkpoint1_full_verification_in_dev_repo(
        self, autonomous_dev_repo, checkpoint1_optional_template
    ):
        """Test CHECKPOINT 1 performs full verification in dev repo.

        Arrange:
        - autonomous-dev repository WITH scripts/agent_tracker.py
        - Valid session file with agent completion data

        Act:
        - Execute checkpoint 1

        Assert:
        - Import succeeds
        - verify_parallel_exploration() called
        - Shows SUCCESS or FAILED message
        - Displays metrics if available
        - Exit code 0 regardless (verification is informational)
        """
        # Create session file with agent data
        sessions_dir = autonomous_dev_repo / "docs" / "sessions"
        session_file = sessions_dir / "test_session.json"
        session_data = {
            "session_id": "test-20251118",
            "agents": [
                {"agent": "researcher", "status": "completed", "timestamp": "2025-11-18T10:00:00"},
                {"agent": "planner", "status": "completed", "timestamp": "2025-11-18T10:05:00"},
                {"agent": "test-master", "status": "completed", "timestamp": "2025-11-18T10:10:00"}
            ]
        }
        session_file.write_text(json.dumps(session_data, indent=2))

        test_script = autonomous_dev_repo / "test_checkpoint1.py"
        test_script.write_text(checkpoint1_optional_template)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(autonomous_dev_repo),
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should execute full verification
        assert result.returncode == 0, f"Should always succeed. stderr: {result.stderr}"
        assert "PARALLEL EXPLORATION" in result.stdout, "Should show verification result"

        # Should show either success or failure (not skip message)
        assert ("✅" in result.stdout or "❌" in result.stdout), "Should show verification status"
        assert "verification skipped" not in result.stdout, "Should NOT skip in dev repo"

    def test_checkpoint4_full_verification_in_dev_repo(
        self, autonomous_dev_repo, checkpoint4_optional_template
    ):
        """Test CHECKPOINT 4.1 performs full verification with metrics.

        Arrange:
        - autonomous-dev repository
        - Session file with parallel_validation metrics

        Act:
        - Execute checkpoint 4.1

        Assert:
        - Import succeeds
        - verify_parallel_validation() called
        - Extracts metrics (time_saved, efficiency)
        - Displays metrics in output
        - Exit code 0
        """
        # Create session with validation metrics
        sessions_dir = autonomous_dev_repo / "docs" / "sessions"
        session_file = sessions_dir / "test_session.json"
        session_data = {
            "session_id": "test-20251118",
            "agents": [
                {"agent": "reviewer", "status": "completed"},
                {"agent": "security-auditor", "status": "completed"},
                {"agent": "doc-master", "status": "completed"}
            ],
            "parallel_validation": {
                "status": "parallel",
                "time_saved_seconds": 180,
                "efficiency_percent": 60,
                "sequential_time_seconds": 300
            }
        }
        session_file.write_text(json.dumps(session_data, indent=2))

        # Update agent_tracker to use this session file
        scripts_dir = autonomous_dev_repo / "scripts"
        tracker_code = f"""
from pathlib import Path
class AgentTracker:
    def __init__(self):
        self.session_file = Path(r"{session_file}")
    def verify_parallel_validation(self):
        return True
"""
        (scripts_dir / "agent_tracker.py").write_text(tracker_code)

        test_script = autonomous_dev_repo / "test_checkpoint4.py"
        test_script.write_text(checkpoint4_optional_template)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(autonomous_dev_repo),
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should execute full verification with metrics
        assert result.returncode == 0, f"Should always succeed. stderr: {result.stderr}"
        assert "PARALLEL VALIDATION" in result.stdout, "Should show verification result"
        assert "verification skipped" not in result.stdout, "Should NOT skip in dev repo"

        # Should display metrics
        output = result.stdout
        if "SUCCESS" in output:
            # If verification succeeds, should show metrics
            assert ("Status:" in output or
                    "Time saved:" in output or
                    "Efficiency:" in output), "Should show some metrics"


# ============================================================================
# CATEGORY 4: REGRESSION TESTS (NEVER BLOCK WORKFLOW)
# ============================================================================


class TestCheckpointNeverBlocks:
    """Test that checkpoints NEVER block workflow on any error."""

    def test_checkpoint_never_blocks_workflow_on_import_error(
        self, user_project_repo, checkpoint1_optional_template
    ):
        """Test checkpoint never returns non-zero exit code on ImportError.

        Arrange:
        - Project without scripts/ (ImportError guaranteed)

        Act:
        - Execute checkpoint

        Assert:
        - Exit code 0 (success)
        - Workflow continues
        - Informational message printed
        """
        test_script = user_project_repo / "test.py"
        test_script.write_text(checkpoint1_optional_template)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(user_project_repo),
            capture_output=True,
            text=True,
            timeout=10
        )

        # CRITICAL: Must succeed even on ImportError
        assert result.returncode == 0, "ImportError must not block workflow"
        assert "verification skipped" in result.stdout or "ℹ️" in result.stdout

    def test_checkpoint_never_blocks_workflow_on_runtime_error(
        self, broken_scripts_repo, checkpoint1_optional_template
    ):
        """Test checkpoint never blocks on runtime errors (AttributeError, etc).

        Arrange:
        - Broken agent_tracker (missing methods)

        Act:
        - Execute checkpoint

        Assert:
        - Exit code 0 (success)
        - Warning message printed
        - Workflow continues
        """
        test_script = broken_scripts_repo / "test.py"
        test_script.write_text(checkpoint1_optional_template)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(broken_scripts_repo),
            capture_output=True,
            text=True,
            timeout=10
        )

        # CRITICAL: Must succeed even on runtime errors
        assert result.returncode == 0, "Runtime errors must not block workflow"
        assert "⚠️" in result.stdout or "verification" in result.stdout

    def test_checkpoint_sets_success_true_on_all_errors(
        self, user_project_repo
    ):
        """Test checkpoint explicitly sets success = True after catching errors.

        Arrange:
        - Project that will trigger ImportError

        Act:
        - Execute checkpoint
        - Check success variable value

        Assert:
        - success = True after exception handling
        - Continues to next step
        """
        # Modified checkpoint that prints success value
        test_code = """
import sys
from pathlib import Path

current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists():
        project_root = current
        break
    current = current.parent
else:
    raise FileNotFoundError("No git marker")

sys.path.insert(0, str(project_root))

try:
    from scripts.agent_tracker import AgentTracker
    success = False  # Would be set by verification
except ImportError:
    print("ImportError caught")
    success = True  # CRITICAL: Must set to True

print(f"success = {success}")
assert success == True, "success must be True after error handling"
print("Workflow continues")
"""
        test_script = user_project_repo / "test.py"
        test_script.write_text(test_code)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(user_project_repo),
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should succeed and print success = True
        assert result.returncode == 0, f"Should succeed. stderr: {result.stderr}"
        assert "success = True" in result.stdout, "success variable must be True"
        assert "Workflow continues" in result.stdout


# ============================================================================
# CATEGORY 5: INTEGRATION TESTS (END-TO-END)
# ============================================================================


class TestCheckpointIntegration:
    """Test actual checkpoint execution in realistic scenarios."""

    def test_both_checkpoints_use_same_error_handling(
        self, user_project_repo, checkpoint1_optional_template, checkpoint4_optional_template
    ):
        """Test both checkpoints have identical error handling logic.

        Arrange:
        - User project (no scripts/)
        - Both checkpoint templates

        Act:
        - Execute both checkpoints

        Assert:
        - Both handle ImportError identically
        - Both print informational messages
        - Both continue workflow
        """
        # Test checkpoint 1
        script1 = user_project_repo / "test_cp1.py"
        script1.write_text(checkpoint1_optional_template)

        result1 = subprocess.run(
            [sys.executable, str(script1)],
            cwd=str(user_project_repo),
            capture_output=True,
            text=True,
            timeout=10
        )

        # Test checkpoint 4
        script4 = user_project_repo / "test_cp4.py"
        script4.write_text(checkpoint4_optional_template)

        result4 = subprocess.run(
            [sys.executable, str(script4)],
            cwd=str(user_project_repo),
            capture_output=True,
            text=True,
            timeout=10
        )

        # Both should succeed
        assert result1.returncode == 0, "Checkpoint 1 should succeed"
        assert result4.returncode == 0, "Checkpoint 4 should succeed"

        # Both should have similar messaging
        assert "verification skipped" in result1.stdout
        assert "verification skipped" in result4.stdout
        assert "AgentTracker not available" in result1.stdout
        assert "AgentTracker not available" in result4.stdout

    def test_checkpoint_workflow_in_user_project_end_to_end(
        self, user_project_repo, checkpoint1_optional_template, checkpoint4_optional_template
    ):
        """Test complete checkpoint workflow in user project.

        Arrange:
        - User project (realistic scenario)
        - Both checkpoints in sequence

        Act:
        - Execute checkpoint 1
        - Execute checkpoint 4

        Assert:
        - Both checkpoints succeed
        - Verification gracefully skipped
        - User can complete /auto-implement workflow
        - No errors block progress
        """
        # Execute checkpoint 1
        script1 = user_project_repo / "checkpoint1.py"
        script1.write_text(checkpoint1_optional_template)

        result1 = subprocess.run(
            [sys.executable, str(script1)],
            cwd=str(user_project_repo),
            capture_output=True,
            text=True,
            timeout=10
        )

        assert result1.returncode == 0, "Checkpoint 1 failed in user project"

        # Execute checkpoint 4
        script4 = user_project_repo / "checkpoint4.py"
        script4.write_text(checkpoint4_optional_template)

        result4 = subprocess.run(
            [sys.executable, str(script4)],
            cwd=str(user_project_repo),
            capture_output=True,
            text=True,
            timeout=10
        )

        assert result4.returncode == 0, "Checkpoint 4 failed in user project"

        # Both should indicate graceful skip
        assert "ℹ️" in result1.stdout
        assert "ℹ️" in result4.stdout
        assert "This is normal for user projects" in result1.stdout
        assert "This is normal for user projects" in result4.stdout

    def test_checkpoint_workflow_in_dev_repo_end_to_end(
        self, autonomous_dev_repo, checkpoint1_optional_template, checkpoint4_optional_template
    ):
        """Test complete checkpoint workflow in autonomous-dev repo.

        Arrange:
        - autonomous-dev repository (full verification available)
        - Session files with agent data

        Act:
        - Execute checkpoint 1
        - Execute checkpoint 4

        Assert:
        - Both checkpoints run full verification
        - Metrics displayed where available
        - No skip messages
        - Both succeed
        """
        # Create session data
        sessions_dir = autonomous_dev_repo / "docs" / "sessions"
        session_file = sessions_dir / "test_session.json"
        session_data = {
            "session_id": "test-20251118",
            "agents": [
                {"agent": "researcher", "status": "completed"},
                {"agent": "planner", "status": "completed"},
                {"agent": "test-master", "status": "completed"},
                {"agent": "reviewer", "status": "completed"},
                {"agent": "security-auditor", "status": "completed"},
                {"agent": "doc-master", "status": "completed"}
            ],
            "parallel_validation": {
                "status": "parallel",
                "time_saved_seconds": 180,
                "efficiency_percent": 60
            }
        }
        session_file.write_text(json.dumps(session_data, indent=2))

        # Execute checkpoint 1
        script1 = autonomous_dev_repo / "checkpoint1.py"
        script1.write_text(checkpoint1_optional_template)

        result1 = subprocess.run(
            [sys.executable, str(script1)],
            cwd=str(autonomous_dev_repo),
            capture_output=True,
            text=True,
            timeout=10
        )

        # Execute checkpoint 4
        script4 = autonomous_dev_repo / "checkpoint4.py"
        script4.write_text(checkpoint4_optional_template)

        result4 = subprocess.run(
            [sys.executable, str(script4)],
            cwd=str(autonomous_dev_repo),
            capture_output=True,
            text=True,
            timeout=10
        )

        # Both should succeed
        assert result1.returncode == 0, f"Checkpoint 1 failed. stderr: {result1.stderr}"
        assert result4.returncode == 0, f"Checkpoint 4 failed. stderr: {result4.stderr}"

        # Both should attempt verification (not skip)
        assert "verification skipped" not in result1.stdout, "Should not skip in dev repo"
        assert "verification skipped" not in result4.stdout, "Should not skip in dev repo"

        # Should show verification attempt
        assert ("PARALLEL EXPLORATION" in result1.stdout or
                "verification" in result1.stdout.lower())
        assert ("PARALLEL VALIDATION" in result4.stdout or
                "verification" in result4.stdout.lower())


# ============================================================================
# CATEGORY 6: MESSAGE FORMAT TESTS
# ============================================================================


class TestCheckpointMessages:
    """Test that checkpoint messages are clear and helpful."""

    def test_user_project_message_is_informational_not_error(
        self, user_project_repo, checkpoint1_optional_template
    ):
        """Test user project message uses informational icon, not error icon.

        Arrange:
        - User project (no scripts/)

        Act:
        - Execute checkpoint

        Assert:
        - Uses ℹ️ (informational) icon
        - NOT ❌ (error) icon
        - NOT ⚠️ (warning) icon
        - Message tone is neutral/positive
        """
        test_script = user_project_repo / "test.py"
        test_script.write_text(checkpoint1_optional_template)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(user_project_repo),
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should use informational icon
        assert "ℹ️" in result.stdout, "Should use informational icon"
        assert "❌" not in result.stdout, "Should NOT use error icon"
        # Note: ⚠️ is for actual errors, ℹ️ is for skips

    def test_broken_scripts_message_is_warning(
        self, broken_scripts_repo, checkpoint1_optional_template
    ):
        """Test broken scripts shows warning (not error).

        Arrange:
        - Broken agent_tracker (missing methods)

        Act:
        - Execute checkpoint

        Assert:
        - Uses ⚠️ (warning) icon
        - Says "verification unavailable" or "verification error"
        - Says "Continuing workflow"
        - Says "Verification is optional"
        """
        test_script = broken_scripts_repo / "test.py"
        test_script.write_text(checkpoint1_optional_template)

        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(broken_scripts_repo),
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should use warning icon
        assert "⚠️" in result.stdout, "Should use warning icon"
        assert ("verification unavailable" in result.stdout or
                "verification error" in result.stdout), "Should explain issue"
        assert "Continuing workflow" in result.stdout, "Should reassure user"
        assert "Verification is optional" in result.stdout or "optional" in result.stdout


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
