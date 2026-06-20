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
import types

# Add plugins directory to Python path for autonomous_dev imports
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

# Import path_utils for cache reset
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))

# Create alias for plugins.autonomous_dev -> plugins/autonomous-dev
# This allows tests to import from plugins.autonomous_dev.lib.X
_AD_HYPHEN_DIR = Path(__file__).parent.parent / "plugins" / "autonomous-dev"
if _AD_HYPHEN_DIR.exists() and "plugins.autonomous_dev" not in sys.modules:
    # Create virtual packages in sys.modules
    if "plugins" not in sys.modules:
        plugins_pkg = types.ModuleType("plugins")
        plugins_pkg.__path__ = [str(_AD_HYPHEN_DIR.parent)]  # plugins/
        sys.modules["plugins"] = plugins_pkg
    
    # Create the autonomous_dev subpackage pointing to autonomous-dev/
    autonomous_dev_pkg = types.ModuleType("plugins.autonomous_dev")
    autonomous_dev_pkg.__path__ = [str(_AD_HYPHEN_DIR)]  # plugins/autonomous-dev/
    sys.modules["plugins.autonomous_dev"] = autonomous_dev_pkg
    
    # Also create lib subpackage
    lib_pkg = types.ModuleType("plugins.autonomous_dev.lib")
    lib_pkg.__path__ = [str(_AD_HYPHEN_DIR / "lib")]  # plugins/autonomous-dev/lib/
    sys.modules["plugins.autonomous_dev.lib"] = lib_pkg


# =============================================================================
# COVERAGE THRESHOLD FOR PARTIAL RUNS (Issue #699)
# =============================================================================

def _is_partial_test_run(config) -> bool:
    """Detect if pytest is running a subset of tests (not the full suite).

    When running a single file like ``pytest tests/unit/hooks/test_foo.py``,
    the global ``--cov-fail-under`` threshold from pytest.ini is unreachable
    because only a tiny fraction of the source is exercised.  This helper
    returns True when the invocation targets specific files, test nodes, or
    marker/keyword filters — all of which indicate a partial run.
    """
    args = config.args  # CLI positional arguments (files / dirs / nodeids)

    for arg in args:
        # Specific .py file or nodeid (contains ::)
        if arg.endswith(".py") or "::" in arg:
            return True

    # -k (keyword filter) or -m (marker filter) also produce partial runs
    keyword_expr = config.getoption("-k", default="")
    marker_expr = config.getoption("-m", default="")
    if keyword_expr or marker_expr:
        return True

    return False


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    """Suppress --cov-fail-under for partial test runs.

    Full suite runs (``pytest`` or ``pytest tests/``) keep the threshold
    defined in pytest.ini so CI enforcement is preserved.

    Uses trylast=True to ensure the pytest-cov plugin has already been
    registered before we modify its options.
    """
    if _is_partial_test_run(config):
        # The pytest-cov plugin stores its own copy of the options namespace
        # (early_config.known_args_namespace), which is a *different* object
        # from config.option.  We must set cov_fail_under on both to be safe.
        if hasattr(config.option, "cov_fail_under"):
            config.option.cov_fail_under = 0

        cov_plugin = config.pluginmanager.getplugin("_cov")
        if cov_plugin and hasattr(cov_plugin, "options"):
            cov_plugin.options.cov_fail_under = 0


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

# Import tier registry as source of truth for directory -> marker mapping.
# Falls back to hardcoded dict if import fails (e.g. running tests outside project).
try:
    from tier_registry import build_directory_markers
    DIRECTORY_MARKERS = build_directory_markers()
except ImportError:
    # Fallback: hardcoded markers (keep in sync with tier_registry.py)
    DIRECTORY_MARKERS = {
        "genai/": ["genai", "acceptance"],
        "regression/smoke/": ["smoke"],
        "e2e/": ["e2e", "slow"],
        "integration/": ["integration"],
        "regression/regression/": ["regression"],
        "regression/extended/": ["extended", "slow"],
        "property/": ["property", "slow"],
        "regression/progression/": ["progression", "tdd_red"],
        "unit/": ["unit"],
        "hooks/": ["hooks", "unit"],
        "security/": ["unit"],
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


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print tier distribution summary after test runs."""
    try:
        from tier_registry import get_tier_for_path
    except ImportError:
        return  # Skip if tier_registry not available

    stats = terminalreporter.stats
    all_items = []
    for key in ("passed", "failed", "error", "skipped"):
        all_items.extend(stats.get(key, []))

    if not all_items:
        return

    distribution: dict = {}
    for item in all_items:
        fspath = str(getattr(item, "fspath", getattr(item, "nodeid", "")))
        tier = get_tier_for_path(fspath)
        tier_id = tier.tier_id if tier else "unknown"
        distribution[tier_id] = distribution.get(tier_id, 0) + 1

    terminalreporter.write_sep("=", "Tier Distribution (Diamond Model)")
    for tier_id in sorted(distribution.keys()):
        terminalreporter.write_line(f"  {tier_id}: {distribution[tier_id]} tests")


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
