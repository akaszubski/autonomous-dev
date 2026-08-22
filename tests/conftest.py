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

import hashlib
import os
import pytest
import shutil
import sys
import tempfile
from pathlib import Path
import types

# Add plugins directory to Python path for autonomous_dev imports
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

# Import path_utils for cache reset
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "lib"))

# =============================================================================
# GH-ISSUE COMMAND-CONTEXT MARKER ISOLATION (Issue #1609)
# =============================================================================
#
# /tmp/autonomous_dev_cmd_context.json is a GLOBAL SANCTIONING MARKER: its
# presence tells `_detect_gh_issue_create` and its sibling detectors in
# unified_pre_tool.py that an issue-creating command is legitimately in flight,
# so they PERMIT a command they would otherwise refuse.
#
# Measured on 2026-08-22, one variable changed, in a SERIAL run (no -n):
#     marker absent  -> pytest tests/unit/hooks/test_gh_issue_create_block.py
#                       -> 165 passed
#     marker present -> same command
#                       -> 49 failed, 116 passed   (all `assert None is not None`)
# The tests were right; the environment was lying to them. The suite's verdict
# depended on run order, and a developer who had merely filed an issue in an
# interactive session got the same 49 phantom failures.
#
# That measurement is SERIAL, and every explanation of the wide-run behaviour
# offered so far was serial too ("an unrelated module's cleanup happens to run
# first", "directory order puts the leaker after the victims"). Neither holds in
# CI. CI runs `pytest tests/unit/ -n auto`, `pytest tests/integration/ -n auto`
# and `pytest tests/regression/ -n auto` (.github/workflows/ci.yml:326, :332,
# :340), and the tests/unit/ job collects BOTH the known leaker
# (tests/unit/lib/test_daily_aggregate_manager.py) and the victims
# (tests/unit/hooks/test_gh_issue_create_block.py). Under xdist's default
# --dist load, tests are handed to workers one at a time in nondeterministic
# order, yet all workers share one machine and therefore ONE real
# /tmp/autonomous_dev_cmd_context.json. So under -n auto this is a
# nondeterministic cross-worker race, not an ordering fact.
#
# HOW MUCH OF CI THIS EXPLAINS IS UNVERIFIED. Three numbers have been offered
# (48-of-200, "zero", "wide runs are unaffected") and none is attributable
# without a CI log; a race does not have a fixed failure count. Do not repeat a
# figure here until a log supports it.
#
# The redirect below removes the coupling BY CONSTRUCTION rather than by
# cleaning up after it: every producer and consumer resolves the marker through
# $GH_ISSUE_CMD_CONTEXT_PATH (hooks/unified_pre_tool.py:GH_ISSUE_COMMAND_CONTEXT_PATH,
# lib/gh_issue_context.py:gh_issue_context_path), so pointing that variable at a
# per-run temp directory means tests cannot see or write the real path at all.
# This holds under -n auto as well: tempfile.mkdtemp() below runs at conftest
# IMPORT time and each xdist worker is a separate process that imports conftest
# itself, so every worker gets its own directory. Measured with -n 2 on
# 2026-08-22: gw0 -> autonomous-dev-gh-issue-ctx-j8to41pw,
# gw1 -> autonomous-dev-gh-issue-ctx-c1j9f0sr.
#
# This MUST run at conftest *import* time, not in a fixture: unified_pre_tool.py
# resolves its constant when the module is imported, and test modules import it
# during collection — which happens before any fixture runs.
_GH_ISSUE_CTX_ENV_VAR = "GH_ISSUE_CMD_CONTEXT_PATH"
_GH_ISSUE_CTX_REDIRECT_DIR = tempfile.mkdtemp(prefix="autonomous-dev-gh-issue-ctx-")
os.environ[_GH_ISSUE_CTX_ENV_VAR] = str(
    Path(_GH_ISSUE_CTX_REDIRECT_DIR) / "autonomous_dev_cmd_context.json"
)

# Second line of defence: snapshot the REAL path now and re-check at session
# finish, so a future writer that reaches it some other way fails the run
# loudly instead of silently sanctioning the tests that follow it.
#
# These imports are DELIBERATELY UNGUARDED. A `try/except ImportError` here
# would leave the watched path as None and turn pytest_sessionfinish into a
# no-op — a leak guard that cannot fail and therefore cannot inform, while the
# run still reports green. tests/conftest.py is only ever loaded from inside
# this repo, so the only thing that except-branch could catch is an actual
# breakage (the helper moved or renamed, or the repo root falling off
# sys.path), which is exactly the case that must be loud. An ImportError raised
# here is already fatal in pytest: the run aborts with a collection error naming
# the missing module, whereas a warning can be silenced by -W ignore /
# -p no:warnings or lost in a 2000-test summary. Fail closed.
from gh_issue_context import DEFAULT_CONTEXT_PATH as _GH_ISSUE_CTX_REAL_PATH

from tests.helpers.gh_issue_marker_guard import (
    describe_marker_leak as _describe_marker_leak,
    snapshot_marker as _snapshot_marker,
    watched_marker_path as _watched_marker_path,
)

_GH_ISSUE_CTX_WATCHED = _watched_marker_path(_GH_ISSUE_CTX_REAL_PATH)
_GH_ISSUE_CTX_BASELINE = _snapshot_marker(_GH_ISSUE_CTX_WATCHED)

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


def pytest_sessionfinish(session, exitstatus):
    """Fail the run if it contaminated the real gh-issue context marker (#1609).

    The redirect installed at import time means no test *should* be able to
    reach the real path. This checks that claim instead of assuming it: if the
    real marker was created, modified, or removed during the session, the run
    fails with a message naming the offender class.

    The baseline is never None — its imports are unguarded above precisely so
    that this comparison cannot silently degrade into a no-op.

    Also removes the per-run redirect directory.
    """
    try:
        finding = _describe_marker_leak(
            _GH_ISSUE_CTX_BASELINE,
            _snapshot_marker(_GH_ISSUE_CTX_WATCHED),
            _GH_ISSUE_CTX_WATCHED,
        )
        if finding:
            reporter = session.config.pluginmanager.getplugin("terminalreporter")
            if reporter is not None:
                reporter.write_sep("=", "gh-issue context marker leak")
                reporter.write_line(finding)
            else:  # pragma: no cover - no terminal (e.g. -p no:terminal)
                print(finding)
            session.exitstatus = 1
    finally:
        shutil.rmtree(_GH_ISSUE_CTX_REDIRECT_DIR, ignore_errors=True)


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


# =============================================================================
# AGENT-DISPATCH SENTINEL ISOLATION (Issue #1535)
# =============================================================================

_LIVE_REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _isolate_agent_dispatch_sentinel(request, tmp_path_factory, monkeypatch):
    """No test may touch the LIVE repo's authorization sentinel (Issue #1535).

    ``<repo>/.claude/local/active_agent_dispatch.json`` is the file that the
    Issue #1296 gate in ``unified_pre_tool.py`` consults to decide whether a
    Write/Edit to protected infrastructure (``agents/*.md``, ``commands/*.md``,
    ``hooks/*.py``, ``lib/*.py``, ``skills/*/SKILL.md``) is coming from a
    dispatched agent. A test run that arms it hands the coordinator a false
    "agent dispatched" authorization, and the Issue #1448 sliding TTL keeps it
    alive on ordinary session activity long after the run that created it.

    Two measured routes reached it, and only one of them is greppable:

      Route 1 (direct)   a test calls ``write()`` with no ``repo_root``.
      Route 2 (indirect) a test drives a hook with a Task/Agent ``PreToolUse``
                         payload and the HOOK calls ``write()`` — the test file
                         contains no ``write()`` call at all.

    Because route 2 is invisible to a call-site sweep, the interception is at
    the shared choke point ``agent_dispatch_sentinel._path()`` instead. Every
    production caller (writer, reader, clearer) uses its default no-arg branch,
    so one redirect covers both routes and any future test that drives a hook
    with an Agent payload.

    Two properties are preserved deliberately:

    - **The explicit-``repo_root`` branch is passed through verbatim**, so the
      30+ existing ``repo_root=tmp_path`` tests keep resolving to exactly the
      path they supplied.
    - **Only a resolution that lands on the LIVE repo is redirected.** Tests
      that legitimately exercise default-branch resolution against a temporary
      fake repo (``test_issue_1484_path_convergence.py`` chdir's into one) still
      get the real ``find_project_root`` answer. This keeps the fix scoped to
      the actual defect rather than blinding the tests that cover the resolver.

    Writer and reader are moved TOGETHER — that is what makes this correct.
    Redirecting only the test's ``write()`` (e.g. passing ``repo_root=tmp_path``
    at the call site) would decouple it from a hook reading the default path
    in-process, breaking ``test_install_manifest_allows_edit_inside_pipeline``.
    """
    try:
        import agent_dispatch_sentinel as ads
    except ImportError:
        # Sentinel module unavailable (e.g. running tests outside the plugin).
        yield
        return

    real_path = ads._path
    live_sentinel = _LIVE_REPO_ROOT / ads._SENTINEL_REL

    # Per-test directory under the session basetemp. Built lazily as a plain
    # path — never mkdir'd here — so the ~2000 tests that never touch the
    # sentinel pay nothing, and no test's own ``tmp_path`` gains a stray entry.
    isolated_root = (
        tmp_path_factory.getbasetemp()
        / "agent-dispatch-sentinel-isolation"
        / hashlib.sha1(request.node.nodeid.encode("utf-8")).hexdigest()[:16]
    )

    def _isolated(repo_root: "Path | None" = None) -> Path:
        """Stand-in for ``agent_dispatch_sentinel._path`` (see fixture docstring)."""
        if repo_root is not None:
            # Explicit branch: preserved verbatim (literal, un-normalized).
            return real_path(repo_root)
        resolved = real_path(None)
        if resolved == live_sentinel or resolved.resolve() == live_sentinel:
            return isolated_root / ads._SENTINEL_REL
        return resolved

    monkeypatch.setattr(ads, "_path", _isolated)
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
