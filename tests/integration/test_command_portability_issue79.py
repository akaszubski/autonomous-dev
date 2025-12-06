#!/usr/bin/env python3
"""
TDD Integration Tests for Command Portability (Issue #79 - FAILING - Red Phase)

This module contains FAILING integration tests that verify commands use
portable paths and library imports (not subprocess anti-pattern).

Problem Statement (GitHub Issue #79):
- auto-implement.md uses hardcoded paths in subprocess calls
- batch-implement.md uses hardcoded paths for agent_tracker.py
- pipeline-status.md uses subprocess instead of library imports
- Commands stall for 7+ hours when paths don't match

Solution Requirements:
1. Remove subprocess anti-pattern from all commands
2. Use library imports (from plugins.autonomous_dev.lib import AgentTracker)
3. Use portable path detection (path_utils.get_project_root())
4. Work from any directory (not just project root)
5. Work on any machine (not developer-specific paths)

Test Strategy:
- Integration tests for command execution
- Verify no subprocess calls to agent_tracker.py
- Test execution from various directories
- Verify portable path detection
- Test on fresh install (simulated)

Test Coverage Target: 100% of command portability scenarios

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe requirements
- Tests should FAIL until implementation is complete
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-12-07
Issue: GitHub #79
Phase: TDD Red Phase
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch, call

import pytest

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.mark.integration
class TestAutoImplementPortability:
    """Test auto-implement.md uses portable paths and library imports.

    Critical requirement: CHECKPOINT 1 and CHECKPOINT 4.1 must use library imports
    (not subprocess calls to scripts/agent_tracker.py).
    """

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project structure."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        (project_root / ".claude").mkdir()
        (project_root / "docs" / "sessions").mkdir(parents=True)

        # Create minimal PROJECT.md
        (project_root / ".claude" / "PROJECT.md").write_text("# Test Project")

        return project_root

    def test_auto_implement_checkpoint1_no_subprocess(self, temp_project):
        """Test that CHECKPOINT 1 does not use subprocess calls.

        REQUIREMENT: Replace subprocess with library imports
        Expected: No subprocess.run() or os.system() calls for agent_tracker.py
        """
        # Read auto-implement.md
        cmd_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"
        assert cmd_file.exists(), "auto-implement.md not found"

        with open(cmd_file) as f:
            content = f.read()

        # Find CHECKPOINT 1 section
        checkpoint1_start = content.find("CHECKPOINT 1")
        checkpoint1_end = content.find("CHECKPOINT 2", checkpoint1_start)
        checkpoint1_section = content[checkpoint1_start:checkpoint1_end]

        # Verify no subprocess calls
        subprocess_patterns = [
            "subprocess.run",
            "subprocess.call",
            "os.system",
            "scripts/agent_tracker.py",
        ]

        for pattern in subprocess_patterns:
            assert pattern not in checkpoint1_section, \
                f"CHECKPOINT 1 still uses subprocess anti-pattern: {pattern}"

        # Verify library import pattern
        assert "from plugins.autonomous_dev.lib" in content or \
               "from autonomous_dev.lib" in content, \
               "auto-implement.md missing library import"

    def test_auto_implement_checkpoint41_no_subprocess(self, temp_project):
        """Test that CHECKPOINT 4.1 does not use subprocess calls.

        REQUIREMENT: Replace subprocess with library imports
        Expected: No subprocess.run() or os.system() calls for verify_parallel_exploration
        """
        # Read auto-implement.md
        cmd_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"

        with open(cmd_file) as f:
            content = f.read()

        # Find CHECKPOINT 4.1 section
        checkpoint41_start = content.find("CHECKPOINT 4.1")
        checkpoint41_end = content.find("CHECKPOINT 4", checkpoint41_start + 20)
        checkpoint41_section = content[checkpoint41_start:checkpoint41_end]

        # Verify no subprocess calls
        subprocess_patterns = [
            "subprocess.run",
            "subprocess.call",
            "os.system",
            "scripts/",
        ]

        for pattern in subprocess_patterns:
            assert pattern not in checkpoint41_section, \
                f"CHECKPOINT 4.1 still uses subprocess anti-pattern: {pattern}"

    def test_auto_implement_uses_portable_paths(self, temp_project):
        """Test that auto-implement.md uses portable path detection.

        REQUIREMENT: Use path_utils.get_project_root() (not hardcoded paths)
        Expected: References to path_utils or get_project_root()
        """
        cmd_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands" / "auto-implement.md"

        with open(cmd_file) as f:
            content = f.read()

        # Verify portable path patterns
        portable_patterns = [
            "get_project_root",
            "path_utils",
            "portable path",
        ]

        has_portable = any(pattern in content for pattern in portable_patterns)
        assert has_portable, \
            "auto-implement.md does not reference portable path detection"

    def test_auto_implement_checkpoints_work_from_subdirectory(self, temp_project, monkeypatch):
        """Test that checkpoint verification works from subdirectories.

        REQUIREMENT: Portable path detection must work from any directory
        Expected: Checkpoints resolve paths from PROJECT_ROOT (not cwd)
        """
        # Create nested subdirectory
        nested_dir = temp_project / "src" / "lib" / "utils"
        nested_dir.mkdir(parents=True)
        monkeypatch.chdir(nested_dir)

        # Import checkpoint verification function (will fail until implemented)
        try:
            from plugins.autonomous_dev.lib.agent_tracker import AgentTracker
            from plugins.autonomous_dev.lib.path_utils import get_project_root

            # Verify it finds project root correctly
            root = get_project_root()
            assert root == temp_project, \
                f"get_project_root() returned {root}, expected {temp_project}"

        except ImportError as e:
            pytest.fail(f"Cannot import checkpoint libraries: {e}")


@pytest.mark.integration
class TestBatchImplementPortability:
    """Test batch-implement.md uses portable paths and library imports.

    Critical requirement: Remove subprocess calls to agent_tracker.py.
    """

    def test_batch_implement_no_subprocess_calls(self):
        """Test that batch-implement.md does not use subprocess for agent tracking.

        REQUIREMENT: Replace subprocess with library imports
        Expected: No subprocess calls to scripts/agent_tracker.py
        """
        cmd_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands" / "batch-implement.md"
        assert cmd_file.exists(), "batch-implement.md not found"

        with open(cmd_file) as f:
            content = f.read()

        # Verify no subprocess anti-pattern
        subprocess_patterns = [
            "subprocess.run",
            "subprocess.call",
            "scripts/agent_tracker.py",
            "python scripts/",
        ]

        for pattern in subprocess_patterns:
            assert pattern not in content, \
                f"batch-implement.md still uses subprocess anti-pattern: {pattern}"

    def test_batch_implement_uses_library_imports(self):
        """Test that batch-implement.md uses library imports.

        REQUIREMENT: Import AgentTracker from lib (not subprocess)
        Expected: References to 'from plugins.autonomous_dev.lib import'
        """
        cmd_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands" / "batch-implement.md"

        with open(cmd_file) as f:
            content = f.read()

        # Verify library import pattern
        library_patterns = [
            "from plugins.autonomous_dev.lib",
            "from autonomous_dev.lib",
            "import AgentTracker",
        ]

        has_library = any(pattern in content for pattern in library_patterns)
        assert has_library, \
            "batch-implement.md does not use library imports"


@pytest.mark.integration
class TestPipelineStatusPortability:
    """Test pipeline-status.md uses library imports (not subprocess).

    Critical requirement: Remove subprocess anti-pattern from pipeline-status command.
    """

    def test_pipeline_status_no_subprocess(self):
        """Test that pipeline-status.md does not use subprocess.

        REQUIREMENT: Use library imports instead of subprocess
        Expected: No subprocess calls to scripts/
        """
        cmd_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands" / "pipeline-status.md"
        assert cmd_file.exists(), "pipeline-status.md not found"

        with open(cmd_file) as f:
            content = f.read()

        # Verify no subprocess anti-pattern
        subprocess_patterns = [
            "subprocess.run",
            "subprocess.call",
            "python scripts/",
        ]

        for pattern in subprocess_patterns:
            assert pattern not in content, \
                f"pipeline-status.md still uses subprocess anti-pattern: {pattern}"

    def test_pipeline_status_uses_library_imports(self):
        """Test that pipeline-status.md uses library imports.

        REQUIREMENT: Import AgentTracker directly
        Expected: Uses 'from plugins.autonomous_dev.lib import AgentTracker'
        """
        cmd_file = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands" / "pipeline-status.md"

        with open(cmd_file) as f:
            content = f.read()

        # Verify library import pattern
        assert "from plugins.autonomous_dev.lib" in content or \
               "from autonomous_dev.lib" in content, \
               "pipeline-status.md does not use library imports"


@pytest.mark.integration
class TestFreshInstallPortability:
    """Test that commands work on fresh install (non-developer machine).

    Critical requirement: No hardcoded developer-specific paths.
    """

    @pytest.fixture
    def fresh_install_path(self, tmp_path):
        """Simulate fresh install location (not developer path)."""
        install_dir = tmp_path / "different" / "user" / "projects" / "myapp"
        install_dir.mkdir(parents=True)
        (install_dir / ".git").mkdir()
        (install_dir / ".claude").mkdir()
        return install_dir

    def test_no_hardcoded_developer_paths(self):
        """Test that commands do not contain hardcoded developer paths.

        REQUIREMENT: No paths like /Users/akaszubski/... in commands
        Expected: All paths use portable path detection
        """
        commands_dir = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands"
        command_files = [
            "auto-implement.md",
            "batch-implement.md",
            "pipeline-status.md",
        ]

        for cmd_file in command_files:
            file_path = commands_dir / cmd_file
            if not file_path.exists():
                continue

            with open(file_path) as f:
                content = f.read()

            # Check for hardcoded paths
            hardcoded_patterns = [
                "/Users/akaszubski",
                "/Users/specific_user",
                "C:\\Users\\developer",
                "/home/specific_user",
            ]

            for pattern in hardcoded_patterns:
                assert pattern not in content, \
                    f"{cmd_file} contains hardcoded developer path: {pattern}"

    def test_portable_path_detection_works_anywhere(self, fresh_install_path, monkeypatch):
        """Test that portable path detection works in any installation location.

        REQUIREMENT: Works on any machine (not developer-specific)
        Expected: get_project_root() finds correct path
        """
        monkeypatch.chdir(fresh_install_path)

        # Import and test portable path detection
        from plugins.autonomous_dev.lib.path_utils import get_project_root, reset_project_root_cache

        # Reset cache (in case previous tests cached different path)
        reset_project_root_cache()

        # Verify it finds correct root
        root = get_project_root(use_cache=False)
        assert root == fresh_install_path, \
            f"Portable path detection failed: got {root}, expected {fresh_install_path}"


@pytest.mark.integration
@pytest.mark.slow
class TestDogfoodingWorkflow:
    """Test that autonomous-dev works on itself (dogfooding).

    Critical requirement: Plugin must work when developing plugin itself.
    """

    @pytest.mark.timeout(300)  # 5 minute timeout (not 7 hours)
    def test_auto_implement_does_not_stall(self):
        """Test that /auto-implement does not stall for 7+ hours.

        REQUIREMENT: Fix dogfooding bug (GitHub Issue #79)
        Expected: Checkpoints complete in reasonable time (<5 min)
        """
        # This is a placeholder - actual implementation would run /auto-implement
        # For now, just verify checkpoint infrastructure is available
        from plugins.autonomous_dev.lib.agent_tracker import AgentTracker
        from plugins.autonomous_dev.lib.path_utils import get_project_root

        # Verify checkpoint saving works
        try:
            # This will fail until save_agent_checkpoint() is implemented
            AgentTracker.save_agent_checkpoint(
                agent_name="researcher",
                message="Dogfooding test"
            )
        except AttributeError as e:
            if "save_agent_checkpoint" in str(e):
                pytest.fail("save_agent_checkpoint() not implemented yet")
            raise

    def test_checkpoint_verification_finds_agent_tracker(self):
        """Test that checkpoint verification can find AgentTracker in autonomous-dev repo.

        REQUIREMENT: Dogfooding should use full verification (not graceful skip)
        Expected: AgentTracker library is importable
        """
        try:
            from plugins.autonomous_dev.lib.agent_tracker import AgentTracker
            assert hasattr(AgentTracker, '__init__'), "AgentTracker not properly imported"
        except ImportError as e:
            pytest.fail(f"Cannot import AgentTracker in autonomous-dev repo: {e}")


# Summary of test failures expected:
# - CHECKPOINT 1 still uses subprocess (test_auto_implement_checkpoint1_no_subprocess)
# - CHECKPOINT 4.1 still uses subprocess (test_auto_implement_checkpoint41_no_subprocess)
# - auto-implement.md missing portable paths (test_auto_implement_uses_portable_paths)
# - Checkpoints don't work from subdirectory (test_auto_implement_checkpoints_work_from_subdirectory)
# - batch-implement.md uses subprocess (test_batch_implement_no_subprocess_calls)
# - batch-implement.md missing library imports (test_batch_implement_uses_library_imports)
# - pipeline-status.md uses subprocess (test_pipeline_status_no_subprocess)
# - pipeline-status.md missing library imports (test_pipeline_status_uses_library_imports)
# - Commands contain hardcoded paths (test_no_hardcoded_developer_paths)
# - Portable paths don't work anywhere (test_portable_path_detection_works_anywhere)
# - /auto-implement stalls (test_auto_implement_does_not_stall)
# - AgentTracker not importable (test_checkpoint_verification_finds_agent_tracker)
#
# Total: 12 tests, all FAILING until implementation is complete
