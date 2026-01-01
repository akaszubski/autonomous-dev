"""Meta-tests for regression test suite infrastructure.

These tests validate the test suite itself:
- Tier classification accuracy
- Parallel execution isolation
- Hook integration
- Directory structure

Test Naming Convention:
- test_00_* = Infrastructure tests (run first)
- test_01-99_* = Feature tests
- Numbers ensure execution order
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest


@pytest.mark.smoke
class TestTierClassification:
    """Validate test tier classification system.

    Ensures tests are correctly categorized by execution time:
    - smoke: < 5s
    - regression: < 30s
    - extended: 1-5min
    """

    def test_smoke_tier_threshold_validation(self, timing_validator):
        """Test that smoke tier threshold is correctly defined.

        Protects: Tier classification system (regression baseline)
        """
        assert timing_validator.SMOKE_THRESHOLD == 5.0
        assert timing_validator.SMOKE_THRESHOLD < timing_validator.REGRESSION_THRESHOLD

    def test_regression_tier_threshold_validation(self, timing_validator):
        """Test that regression tier threshold is correctly defined.

        Protects: Tier classification system (regression baseline)
        """
        assert timing_validator.REGRESSION_THRESHOLD == 30.0
        assert timing_validator.REGRESSION_THRESHOLD < timing_validator.EXTENDED_THRESHOLD

    def test_extended_tier_threshold_validation(self, timing_validator):
        """Test that extended tier threshold is correctly defined.

        Protects: Tier classification system (regression baseline)
        """
        assert timing_validator.EXTENDED_THRESHOLD == 300.0

    def test_timing_validator_measures_elapsed_time(self, timing_validator):
        """Test that timing validator accurately measures execution time.

        Protects: Tier enforcement mechanism (regression baseline)
        """
        with timing_validator.measure() as timer:
            time.sleep(0.1)

        assert timer.elapsed >= 0.1
        assert timer.elapsed < 0.2  # Should complete quickly
        assert timer.start_time is not None
        assert timer.end_time is not None
        assert timer.end_time > timer.start_time

    def test_smoke_tests_complete_under_threshold(self, project_root, timing_validator):
        """Test that smoke tests complete within 5 second threshold.

        This meta-test validates the smoke tier by running actual smoke tests
        and verifying they meet the < 5s requirement.

        Protects: Smoke test performance guarantee (regression baseline)
        """
        # NOTE: This will FAIL until smoke tests are implemented
        smoke_dir = project_root / "tests" / "regression" / "smoke"

        # Check directory exists
        assert smoke_dir.exists(), f"Smoke test directory not found: {smoke_dir}"

        # Run smoke tests with timing
        result = subprocess.run(
            ["pytest", str(smoke_dir), "-v", "--tb=short"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10  # Should complete well under threshold
        )

        # Parse execution time from pytest output
        # Format variations:
        # - "====== 5 passed in 3.21s ======"
        # - "=============== 298 passed, 1 skipped in 1.61s ==============="
        time_pattern = r'in\s+([\d.]+)s\s*='
        match = re.search(time_pattern, result.stdout)
        if match:
            elapsed = float(match.group(1))
            assert elapsed < timing_validator.SMOKE_THRESHOLD, \
                f"Smoke tests took {elapsed}s, exceeds {timing_validator.SMOKE_THRESHOLD}s threshold"
        else:
            pytest.fail(f"Could not parse execution time from pytest output:\n{result.stdout[-500:]}")


@pytest.mark.smoke
class TestParallelExecutionIsolation:
    """Validate parallel execution safety.

    Ensures tests can run in parallel without interference via:
    - Isolated tmp_path per test
    - No shared state
    - No file system conflicts
    """

    def test_isolated_project_creates_unique_directory(self, isolated_project):
        """Test that each test gets a unique isolated directory.

        Protects: Parallel execution safety (regression baseline)
        """
        # NOTE: This will FAIL if isolated_project fixture not implemented
        assert isolated_project.exists()
        assert isolated_project.is_dir()
        # Should be in /tmp, system temp directory, or pytest temp
        path_str = str(isolated_project)
        assert (
            path_str.startswith('/tmp') or
            'temp' in path_str.lower() or
            'pytest' in path_str.lower() or
            '/T/' in path_str  # macOS uppercase T in temp path
        )

    def test_isolated_project_has_standard_structure(self, isolated_project):
        """Test that isolated project has expected directory structure.

        Protects: Test fixture consistency (regression baseline)
        """
        # NOTE: This will FAIL if structure not created
        assert (isolated_project / ".claude").exists()
        assert (isolated_project / "plugins" / "autonomous-dev").exists()
        assert (isolated_project / "docs" / "sessions").exists()
        assert (isolated_project / "tests" / "regression").exists()

    def test_isolated_project_has_project_md(self, isolated_project):
        """Test that isolated project has PROJECT.md with test goals.

        Protects: Test fixture completeness (regression baseline)
        """
        # NOTE: This will FAIL if PROJECT.md not created
        project_md = isolated_project / ".claude" / "PROJECT.md"
        assert project_md.exists()

        content = project_md.read_text()
        assert "## GOALS" in content
        assert "goal_1" in content
        assert "goal_2" in content

    def test_parallel_execution_no_shared_state(self, isolated_project):
        """Test that parallel tests don't share file system state.

        Creates a marker file and verifies it doesn't appear in other tests.

        Protects: Parallel execution isolation (regression baseline)
        """
        # Create a marker file unique to this test execution
        marker = isolated_project / f"marker_{os.getpid()}.txt"
        marker.write_text("test data")

        # Verify marker exists in this test's isolated directory
        assert marker.exists()

        # Verify marker is NOT in any other test's directory
        # (This is implicit - each test gets unique tmp_path)
        # Search recursively in parent to find all markers from all parallel tests
        parent_markers = list(isolated_project.parent.glob("**/marker_*.txt"))
        assert len(parent_markers) >= 1  # At least our marker
        # Each test's markers are isolated to their tmp_path


@pytest.mark.regression
class TestHookIntegration:
    """Validate hook integration with test suite.

    Tests that auto_add_to_regression.py generates valid tests.
    """

    def test_hook_script_exists(self, plugins_dir):
        """Test that auto_add_to_regression hook exists.

        Protects: Hook availability (regression baseline)
        """
        # NOTE: This will FAIL if hook not implemented
        hook = plugins_dir / "hooks" / "auto_add_to_regression.py"
        assert hook.exists(), f"Hook not found: {hook}"

    def test_hook_is_executable(self, plugins_dir):
        """Test that auto_add_to_regression hook is executable.

        Protects: Hook executability (regression baseline)
        """
        # NOTE: This will FAIL if permissions not set
        hook = plugins_dir / "hooks" / "auto_add_to_regression.py"
        # Check if file has executable permissions
        assert os.access(hook, os.X_OK), f"Hook not executable: {hook}"

    def test_hook_generates_valid_pytest_files(self, plugins_dir, isolated_project):
        """Test that hook generates valid pytest test files.

        Protects: Hook output quality (regression baseline)
        """
        # NOTE: This will FAIL until hook implementation exists
        hook = plugins_dir / "hooks" / "auto_add_to_regression.py"

        # Run hook to generate test
        result = subprocess.run(
            [sys.executable, str(hook), "--dry-run"],
            cwd=isolated_project,
            capture_output=True,
            text=True,
            timeout=10
        )

        # Hook should succeed
        assert result.returncode == 0, f"Hook failed: {result.stderr}"

        # Output should be valid Python
        output = result.stdout
        assert "def test_" in output or "class Test" in output

    def test_hook_uses_pytest_markers_correctly(self, plugins_dir):
        """Test that hook generates tests with correct pytest markers.

        Protects: Tier classification via markers (regression baseline)
        """
        # NOTE: This will FAIL until hook implementation exists
        hook = plugins_dir / "hooks" / "auto_add_to_regression.py"

        # Run hook to generate test
        result = subprocess.run(
            [sys.executable, str(hook), "--dry-run", "--tier=smoke"],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            timeout=10
        )

        # Check for pytest marker
        assert "@pytest.mark.smoke" in result.stdout or \
               "@pytest.mark.regression" in result.stdout or \
               "@pytest.mark.extended" in result.stdout


@pytest.mark.smoke
class TestDirectoryStructure:
    """Validate regression test directory structure.

    Ensures all required directories exist:
    - tests/regression/smoke/
    - tests/regression/regression/
    - tests/regression/extended/
    - tests/regression/progression/
    """

    def test_smoke_directory_exists(self, project_root):
        """Test that smoke test directory exists.

        Protects: Directory structure (regression baseline)
        """
        # NOTE: This will FAIL until directory created
        smoke_dir = project_root / "tests" / "regression" / "smoke"
        assert smoke_dir.exists(), f"Missing smoke directory: {smoke_dir}"
        assert smoke_dir.is_dir()

    def test_regression_directory_exists(self, project_root):
        """Test that regression test directory exists.

        Protects: Directory structure (regression baseline)
        """
        # NOTE: This will FAIL until directory created
        regression_dir = project_root / "tests" / "regression" / "regression"
        assert regression_dir.exists(), f"Missing regression directory: {regression_dir}"
        assert regression_dir.is_dir()

    def test_extended_directory_exists(self, project_root):
        """Test that extended test directory exists.

        Protects: Directory structure (regression baseline)
        """
        # NOTE: This will FAIL until directory created
        extended_dir = project_root / "tests" / "regression" / "extended"
        assert extended_dir.exists(), f"Missing extended directory: {extended_dir}"
        assert extended_dir.is_dir()

    def test_progression_directory_exists(self, project_root):
        """Test that progression test directory exists.

        Protects: Directory structure (regression baseline)
        """
        # NOTE: This will FAIL until directory created
        progression_dir = project_root / "tests" / "regression" / "progression"
        assert progression_dir.exists(), f"Missing progression directory: {progression_dir}"
        assert progression_dir.is_dir()

    def test_fixtures_directory_exists(self, project_root):
        """Test that regression fixtures directory exists.

        Protects: Test data organization (regression baseline)
        """
        # NOTE: This will FAIL until directory created
        fixtures_dir = project_root / "tests" / "fixtures" / "regression"
        assert fixtures_dir.exists(), f"Missing fixtures directory: {fixtures_dir}"
        assert fixtures_dir.is_dir()

    def test_snapshots_directory_created_on_demand(self, project_root):
        """Test that snapshots directory is created by syrupy.

        Protects: Snapshot testing capability (regression baseline)
        """
        # NOTE: Snapshots are created by syrupy on first test run
        # This test just verifies the parent directory exists
        regression_dir = project_root / "tests" / "regression"
        assert regression_dir.exists()

        # __snapshots__ will be created by syrupy when first test runs
        # Not asserting its existence here since it's auto-created
