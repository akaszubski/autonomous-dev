"""Shared pytest fixtures for all tests."""

import pytest
from pathlib import Path


@pytest.fixture
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def plugins_dir(project_root):
    """Return the plugins directory."""
    return project_root / "plugins" / "autonomous-dev"


@pytest.fixture
def scripts_dir(project_root):
    """Return the scripts directory."""
    return project_root / "scripts"


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project structure for testing."""
    # Create common directories
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs").mkdir()

    return tmp_path
