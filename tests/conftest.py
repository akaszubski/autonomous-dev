"""Shared pytest fixtures for all tests.

Auto-Marker System:
Tests are automatically marked based on their file location:
- tests/regression/smoke/     -> @pytest.mark.smoke (Tier 0 - < 5s, CI gate)
- tests/regression/regression/ -> @pytest.mark.regression (Tier 1 - < 30s)
- tests/regression/extended/   -> @pytest.mark.extended (Tier 2 - < 5min)
- tests/regression/progression/ -> @pytest.mark.progression (Tier 3 - TDD)
- tests/unit/                  -> @pytest.mark.unit
- tests/integration/           -> @pytest.mark.integration
- tests/security/              -> Inherits from location + security focus
- tests/hooks/                 -> @pytest.mark.hooks

Run specific tiers:
  pytest -m smoke              # Smoke tests only (fast, CI gate)
  pytest -m regression         # Regression tests
  pytest -m "smoke or regression"  # Both
  pytest -m "not slow"         # Exclude slow tests
"""

import pytest
import sys
from pathlib import Path

# Add plugins directory to Python path for autonomous_dev imports
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

# Import path_utils for cache reset
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))


# =============================================================================
# PYTEST OPTIONS
# =============================================================================

def pytest_addoption(parser):
    """Register custom command-line options."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests (skipped by default)"
    )


# =============================================================================
# AUTO-MARKER SYSTEM
# Automatically applies pytest markers based on file location
# =============================================================================

# Map directory patterns to markers
DIRECTORY_MARKERS = {
    "regression/smoke": ["smoke"],
    "regression/regression": ["regression"],
    "regression/extended": ["extended", "slow"],
    "regression/progression": ["progression", "tdd_red"],
    "unit/": ["unit"],
    "integration/": ["integration"],
    "security/": ["unit"],  # Security tests are unit tests
    "hooks/": ["hooks", "unit"],
}


def pytest_collection_modifyitems(config, items):
    """Auto-apply markers to tests based on their file location.

    This hook runs after test collection and automatically adds markers
    so tests don't need manual @pytest.mark decorators.
    """
    for item in items:
        # Get the test file path relative to tests/
        fspath = str(item.fspath)

        # Apply markers based on directory
        for dir_pattern, markers in DIRECTORY_MARKERS.items():
            if dir_pattern in fspath:
                for marker_name in markers:
                    marker = getattr(pytest.mark, marker_name)
                    item.add_marker(marker)
                break  # Only match first pattern


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
