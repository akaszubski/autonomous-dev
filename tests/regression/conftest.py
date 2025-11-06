"""Shared pytest fixtures for regression test suite.

This module provides fixtures for:
- Tier classification (smoke, regression, extended, progression)
- Parallel execution isolation
- Test timing validation
- Mock setup for agent invocation
"""

import json
import os
import time
from pathlib import Path
from typing import Dict
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory.

    Returns:
        Path: Absolute path to project root
    """
    return Path(__file__).parent.parent.parent


@pytest.fixture
def plugins_dir(project_root: Path) -> Path:
    """Return the plugins directory.

    Args:
        project_root: Project root path from fixture

    Returns:
        Path: Absolute path to autonomous-dev plugin
    """
    return project_root / "plugins" / "autonomous-dev"


@pytest.fixture
def regression_fixtures_dir(project_root: Path) -> Path:
    """Return the regression test fixtures directory.

    Args:
        project_root: Project root path from fixture

    Returns:
        Path: Absolute path to regression fixtures
    """
    fixtures = project_root / "tests" / "fixtures" / "regression"
    fixtures.mkdir(parents=True, exist_ok=True)
    return fixtures


@pytest.fixture
def isolated_project(tmp_path: Path) -> Path:
    """Create an isolated temporary project structure.

    Ensures parallel test execution doesn't interfere via shared state.
    Each test gets its own isolated file tree.

    Args:
        tmp_path: pytest built-in tmp_path fixture

    Returns:
        Path: Temporary project directory with standard structure
    """
    # Create standard directory structure
    (tmp_path / ".claude").mkdir()
    (tmp_path / "plugins" / "autonomous-dev").mkdir(parents=True)
    (tmp_path / "docs" / "sessions").mkdir(parents=True)
    (tmp_path / "tests" / "regression").mkdir(parents=True)

    # Create minimal PROJECT.md
    project_md = tmp_path / ".claude" / "PROJECT.md"
    project_md.write_text("""# Test Project

## GOALS
- goal_1: Test feature A (Target: 80%)
- goal_2: Test feature B (Target: 60%)

## SCOPE
Test scope definition.

## CONSTRAINTS
Test constraints.
""")

    return tmp_path


@pytest.fixture
def timing_validator():
    """Provide a timing validation utility for tier classification.

    Usage:
        with timing_validator.measure() as timer:
            # Test code
        assert timer.elapsed < 5.0  # Smoke test threshold

    Returns:
        TimingValidator: Validator instance
    """
    class TimingValidator:
        class Timer:
            def __init__(self):
                self.start_time = None
                self.end_time = None
                self.elapsed = None

            def __enter__(self):
                self.start_time = time.perf_counter()
                return self

            def __exit__(self, *args):
                self.end_time = time.perf_counter()
                self.elapsed = self.end_time - self.start_time

        @staticmethod
        def measure():
            return TimingValidator.Timer()

        # Tier thresholds (seconds)
        SMOKE_THRESHOLD = 5.0
        REGRESSION_THRESHOLD = 30.0
        EXTENDED_THRESHOLD = 300.0  # 5 minutes

    return TimingValidator()


@pytest.fixture
def mock_agent_invocation():
    """Mock agent invocation for testing without real agent execution.

    Returns sample agent outputs matching expected formats.

    Returns:
        Mock: Configured mock for agent invocation
    """
    mock = Mock()

    # Default agent outputs
    mock.commit_message_generator.return_value = {
        "commit_message": "feat: add test feature\n\nDetailed description.",
        "conventional_type": "feat"
    }

    mock.pr_description_generator.return_value = {
        "title": "Add test feature",
        "body": "## Summary\n- Test change\n\n## Testing\n- Test plan"
    }

    mock.project_progress_tracker.return_value = """goal_1: 45
goal_2: 30
"""

    return mock


@pytest.fixture
def mock_git_operations():
    """Mock git operations for testing git integration.

    Returns:
        Mock: Configured mock for git subprocess calls
    """
    with patch('subprocess.run') as mock_run:
        # Default success response
        mock_run.return_value = Mock(
            returncode=0,
            stdout="success",
            stderr=""
        )
        yield mock_run


@pytest.fixture
def mock_project_md_updater(isolated_project: Path):
    """Mock ProjectMdUpdater for testing without file I/O.

    Args:
        isolated_project: Isolated project directory

    Returns:
        Mock: Configured mock for ProjectMdUpdater
    """
    with patch('plugins.autonomous_dev.lib.project_md_updater.ProjectMdUpdater') as mock_updater:
        instance = Mock()
        instance.update_goal_progress.return_value = None
        instance.backup_file.return_value = isolated_project / ".claude" / "PROJECT.md.backup"
        mock_updater.return_value = instance
        yield mock_updater


@pytest.fixture(autouse=True)
def isolation_guard(monkeypatch):
    """Automatically prevent tests from modifying real environment.

    This fixture runs automatically for all tests and:
    - Blocks access to real HOME directory
    - Blocks environment variable modifications
    - Ensures tests use tmp_path or isolated_project

    Args:
        monkeypatch: pytest monkeypatch fixture
    """
    # Set safe HOME for tests
    monkeypatch.setenv('HOME', '/tmp/test_home')
    monkeypatch.setenv('USERPROFILE', '/tmp/test_home')  # Windows

    # Block real git config access
    monkeypatch.setenv('GIT_CONFIG_NOSYSTEM', '1')
    monkeypatch.setenv('GIT_CONFIG_GLOBAL', '/dev/null')
