"""Shared pytest fixtures for all tests."""

import pytest
import sys
from pathlib import Path

# Import path_utils for cache reset
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))


@pytest.fixture(autouse=True)
def reset_path_utils_cache():
    """Reset path_utils cache before each test (autouse).

    This ensures tests that change working directory or create mock projects
    don't interfere with each other due to cached PROJECT_ROOT.
    """
    # Import here to avoid import errors if path_utils doesn't exist yet
    try:
        from path_utils import reset_project_root_cache
        reset_project_root_cache()
        yield
        reset_project_root_cache()  # Also reset after test
    except ImportError:
        # path_utils doesn't exist yet (old tests)
        yield


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
