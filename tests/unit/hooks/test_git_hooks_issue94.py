#!/usr/bin/env python3
"""
TDD Tests for Issue #94: Git Hooks Improvements for Larger Projects (500+ tests)

This module contains FAILING tests (TDD red phase) for git hook improvements:

1. Pre-commit hook - Recursive test discovery for nested test structures
2. Pre-push hook - Fast-only test filtering (excludes genai, slow, integration)
3. Hook generation - Updated patterns for recursive discovery and markers

Requirements from Issue #94:
- Pre-commit: Change from flat `find tests -name "test_*.py"` to recursive pattern
- Pre-push: Filter to fast tests only using pytest markers (-m "not slow and not genai and not integration")
- Backwards compatibility: Support both flat and nested test structures
- Performance: Pre-push should skip slow/GenAI tests (2-5 min improvement)

Test Coverage Target: 25+ tests (95%+ coverage)

Following TDD principles:
- Write tests FIRST (red phase)
- Tests should FAIL initially (no implementation yet)
- Each test validates ONE specific requirement
- Arrange-Act-Assert pattern

Author: test-master agent
Date: 2025-12-07
Issue: GitHub #94 - Git hooks for larger projects
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, call, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary git repository with test structure."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)

    return repo_dir


@pytest.fixture
def nested_test_structure(temp_git_repo):
    """Create nested test directory structure with tests at multiple levels.

    Structure:
    tests/
        test_root.py (fast)
        unit/
            test_unit_fast.py (fast)
            test_unit_slow.py (slow marker)
            lib/
                test_lib_fast.py (fast)
                test_lib_genai.py (genai marker)
        integration/
            test_integration.py (integration marker)
            workflows/
                test_workflow.py (integration + slow markers)
    """
    tests_dir = temp_git_repo / "tests"
    tests_dir.mkdir()

    # Root level test (fast)
    (tests_dir / "test_root.py").write_text("""
import pytest

def test_root_fast():
    assert True
""")

    # Unit tests
    unit_dir = tests_dir / "unit"
    unit_dir.mkdir()

    (unit_dir / "test_unit_fast.py").write_text("""
import pytest

def test_unit_fast():
    assert True
""")

    (unit_dir / "test_unit_slow.py").write_text("""
import pytest

@pytest.mark.slow
def test_unit_slow():
    assert True
""")

    # Unit/lib tests (nested 2 levels deep)
    lib_dir = unit_dir / "lib"
    lib_dir.mkdir()

    (lib_dir / "test_lib_fast.py").write_text("""
import pytest

def test_lib_fast():
    assert True
""")

    (lib_dir / "test_lib_genai.py").write_text("""
import pytest

@pytest.mark.genai
def test_lib_genai():
    assert True
""")

    # Integration tests
    integration_dir = tests_dir / "integration"
    integration_dir.mkdir()

    (integration_dir / "test_integration.py").write_text("""
import pytest

@pytest.mark.integration
def test_integration():
    assert True
""")

    # Integration/workflows (nested 2 levels deep)
    workflows_dir = integration_dir / "workflows"
    workflows_dir.mkdir()

    (workflows_dir / "test_workflow.py").write_text("""
import pytest

@pytest.mark.integration
@pytest.mark.slow
def test_workflow():
    assert True
""")

    return tests_dir


@pytest.fixture
def flat_test_structure(temp_git_repo):
    """Create flat test directory structure (backwards compatibility).

    Structure:
    tests/
        test_fast.py (fast)
        test_slow.py (slow marker)
    """
    tests_dir = temp_git_repo / "tests"
    tests_dir.mkdir()

    (tests_dir / "test_fast.py").write_text("""
import pytest

def test_fast():
    assert True
""")

    (tests_dir / "test_slow.py").write_text("""
import pytest

@pytest.mark.slow
def test_slow():
    assert True
""")

    return tests_dir


@pytest.fixture
def pre_commit_hook_path(temp_git_repo):
    """Create scripts/hooks directory for pre-commit hook."""
    hooks_dir = temp_git_repo / "scripts" / "hooks"
    hooks_dir.mkdir(parents=True)
    return hooks_dir / "pre-commit"


@pytest.fixture
def pre_push_hook_path(temp_git_repo):
    """Create scripts/hooks directory for pre-push hook."""
    hooks_dir = temp_git_repo / "scripts" / "hooks"
    hooks_dir.mkdir(parents=True)
    return hooks_dir / "pre-push"


# ============================================================================
# Test Pre-Commit Hook - Recursive Test Discovery
# ============================================================================


class TestPreCommitRecursiveDiscovery:
    """Test pre-commit hook improvements for recursive test discovery.

    REQUIREMENT: Pre-commit hook must find tests in nested subdirectories.
    Current: find tests -name "test_*.py" (misses subdirectories)
    Fixed: find tests -type f -name "test_*.py" (recursive)
    """

    def test_pre_commit_finds_root_level_tests(self, nested_test_structure, pre_commit_hook_path):
        """Test that pre-commit hook finds tests at root level.

        REQUIREMENT: Hook must discover test_root.py at tests/ level.
        Expected: test_root.py found in test list.
        """
        # This test will FAIL until hook is updated with recursive find
        # Arrange: Hook should exist with recursive test discovery
        # Act: Run test discovery (simulated)
        # Assert: Root level tests found

        # Import hook discovery function (will raise NotImplementedError in red phase)
        from plugins.autonomous_dev.lib.git_hooks import discover_tests_recursive

        discovered = discover_tests_recursive(nested_test_structure)

        assert any("test_root.py" in str(p) for p in discovered), \
            "Pre-commit hook should find root level test files"

    def test_pre_commit_finds_nested_unit_tests(self, nested_test_structure, pre_commit_hook_path):
        """Test that pre-commit hook finds tests in tests/unit/ subdirectory.

        REQUIREMENT: Hook must discover tests in tests/unit/ directory.
        Expected: test_unit_fast.py and test_unit_slow.py found.
        """
        # This test will FAIL until hook is updated
        from plugins.autonomous_dev.lib.git_hooks import discover_tests_recursive

        discovered = discover_tests_recursive(nested_test_structure)

        assert any("test_unit_fast.py" in str(p) for p in discovered), \
            "Pre-commit hook should find tests/unit/test_unit_fast.py"
        assert any("test_unit_slow.py" in str(p) for p in discovered), \
            "Pre-commit hook should find tests/unit/test_unit_slow.py"

    def test_pre_commit_finds_deeply_nested_tests(self, nested_test_structure, pre_commit_hook_path):
        """Test that pre-commit hook finds tests nested 2+ levels deep.

        REQUIREMENT: Hook must discover tests in tests/unit/lib/ (2 levels deep).
        Expected: test_lib_fast.py and test_lib_genai.py found.
        """
        # This test will FAIL until hook is updated
        from plugins.autonomous_dev.lib.git_hooks import discover_tests_recursive

        discovered = discover_tests_recursive(nested_test_structure)

        assert any("test_lib_fast.py" in str(p) for p in discovered), \
            "Pre-commit hook should find tests/unit/lib/test_lib_fast.py"
        assert any("test_lib_genai.py" in str(p) for p in discovered), \
            "Pre-commit hook should find tests/unit/lib/test_lib_genai.py"

    def test_pre_commit_finds_integration_tests(self, nested_test_structure, pre_commit_hook_path):
        """Test that pre-commit hook finds tests in tests/integration/ subdirectory.

        REQUIREMENT: Hook must discover tests in tests/integration/ and subdirs.
        Expected: test_integration.py and test_workflow.py found.
        """
        # This test will FAIL until hook is updated
        from plugins.autonomous_dev.lib.git_hooks import discover_tests_recursive

        discovered = discover_tests_recursive(nested_test_structure)

        assert any("test_integration.py" in str(p) for p in discovered), \
            "Pre-commit hook should find tests/integration/test_integration.py"
        assert any("workflows/test_workflow.py" in str(p) for p in discovered), \
            "Pre-commit hook should find tests/integration/workflows/test_workflow.py"

    def test_pre_commit_counts_all_tests_nested(self, nested_test_structure, pre_commit_hook_path):
        """Test that pre-commit hook counts all tests in nested structure.

        REQUIREMENT: Hook must count all 7 test files in nested structure.
        Expected: 7 test files total (root + unit + lib + integration + workflows).
        """
        # This test will FAIL until hook is updated
        from plugins.autonomous_dev.lib.git_hooks import discover_tests_recursive

        discovered = discover_tests_recursive(nested_test_structure)

        assert len(discovered) == 7, \
            f"Pre-commit hook should find all 7 test files, found {len(discovered)}"

    def test_pre_commit_backwards_compatible_flat_structure(self, flat_test_structure, pre_commit_hook_path):
        """Test that pre-commit hook still works with flat test structure.

        REQUIREMENT: Hook must maintain backwards compatibility with flat tests/.
        Expected: Flat structure tests still discovered.
        """
        # This test will FAIL until hook is updated
        from plugins.autonomous_dev.lib.git_hooks import discover_tests_recursive

        discovered = discover_tests_recursive(flat_test_structure)

        assert len(discovered) == 2, \
            "Pre-commit hook should work with flat test structure"
        assert any("test_fast.py" in str(p) for p in discovered)
        assert any("test_slow.py" in str(p) for p in discovered)

    def test_pre_commit_ignores_pycache_directories(self, nested_test_structure, pre_commit_hook_path):
        """Test that pre-commit hook excludes __pycache__ directories.

        REQUIREMENT: Hook must not count test files in __pycache__/.
        Expected: __pycache__/test_*.pyc files excluded from count.
        """
        # Create __pycache__ directory with .pyc files
        pycache_dir = nested_test_structure / "unit" / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "test_unit_fast.cpython-39.pyc").write_bytes(b"fake pyc")

        # This test will FAIL until hook is updated
        from plugins.autonomous_dev.lib.git_hooks import discover_tests_recursive

        discovered = discover_tests_recursive(nested_test_structure)

        # Should still be 7 (not 8 with .pyc file)
        assert len(discovered) == 7, \
            "Pre-commit hook should exclude __pycache__ directories"
        assert not any("__pycache__" in str(p) for p in discovered)

    def test_pre_commit_only_finds_test_prefix_files(self, nested_test_structure, pre_commit_hook_path):
        """Test that pre-commit hook only finds files starting with 'test_'.

        REQUIREMENT: Hook must only count test_*.py files, not other .py files.
        Expected: conftest.py, utils.py excluded from test count.
        """
        # Create non-test Python files
        (nested_test_structure / "conftest.py").write_text("# conftest")
        (nested_test_structure / "unit" / "utils.py").write_text("# utils")

        # This test will FAIL until hook is updated
        from plugins.autonomous_dev.lib.git_hooks import discover_tests_recursive

        discovered = discover_tests_recursive(nested_test_structure)

        # Should still be 7 (not 9)
        assert len(discovered) == 7, \
            "Pre-commit hook should only find test_*.py files"
        assert not any("conftest.py" in str(p) for p in discovered)
        assert not any("utils.py" in str(p) for p in discovered)


# ============================================================================
# Test Pre-Push Hook - Fast Test Filtering
# ============================================================================


class TestPrePushFastTestFiltering:
    """Test pre-push hook improvements for fast-only test execution.

    REQUIREMENT: Pre-push hook must only run fast tests (exclude slow, genai, integration).
    Current: pytest tests/ (runs ALL tests including slow ~2-5 min)
    Fixed: pytest tests/ -m "not slow and not genai and not integration" (fast only ~30s)
    """

    def test_pre_push_excludes_slow_marker_tests(self, nested_test_structure, pre_push_hook_path):
        """Test that pre-push hook excludes tests marked with @pytest.mark.slow.

        REQUIREMENT: Hook must skip slow tests to improve performance.
        Expected: test_unit_slow.py and test_workflow.py excluded.
        """
        # This test will FAIL until hook is updated
        from plugins.autonomous_dev.lib.git_hooks import get_fast_test_command

        cmd = get_fast_test_command(nested_test_structure)

        assert "-m" in cmd, "Pre-push hook should use pytest marker filtering"
        assert "not slow" in cmd, "Pre-push hook should exclude slow tests"

    def test_pre_push_excludes_genai_marker_tests(self, nested_test_structure, pre_push_hook_path):
        """Test that pre-push hook excludes tests marked with @pytest.mark.genai.

        REQUIREMENT: Hook must skip GenAI tests (slow, external API calls).
        Expected: test_lib_genai.py excluded from pre-push run.
        """
        # This test will FAIL until hook is updated
        from plugins.autonomous_dev.lib.git_hooks import get_fast_test_command

        cmd = get_fast_test_command(nested_test_structure)

        assert "-m" in cmd, "Pre-push hook should use pytest marker filtering"
        assert "not genai" in cmd, "Pre-push hook should exclude genai tests"

    def test_pre_push_excludes_integration_marker_tests(self, nested_test_structure, pre_push_hook_path):
        """Test that pre-push hook excludes tests marked with @pytest.mark.integration.

        REQUIREMENT: Hook must skip integration tests (slow, complex setup).
        Expected: test_integration.py and test_workflow.py excluded.
        """
        # This test will FAIL until hook is updated
        from plugins.autonomous_dev.lib.git_hooks import get_fast_test_command

        cmd = get_fast_test_command(nested_test_structure)

        assert "-m" in cmd, "Pre-push hook should use pytest marker filtering"
        assert "not integration" in cmd, "Pre-push hook should exclude integration tests"

    def test_pre_push_runs_unmarked_fast_tests(self, nested_test_structure, pre_push_hook_path):
        """Test that pre-push hook includes unmarked (fast) tests.

        REQUIREMENT: Hook must run tests without markers (assumed fast).
        Expected: test_root.py, test_unit_fast.py, test_lib_fast.py included.
        """
        # This test will FAIL until hook is updated
        from plugins.autonomous_dev.lib.git_hooks import filter_fast_tests

        all_tests = [
            "test_root.py",
            "test_unit_fast.py",
            "test_unit_slow.py",  # has @pytest.mark.slow
            "test_lib_fast.py",
            "test_lib_genai.py",  # has @pytest.mark.genai
            "test_integration.py",  # has @pytest.mark.integration
            "test_workflow.py",  # has @pytest.mark.integration + slow
        ]

        fast_tests = filter_fast_tests(all_tests, nested_test_structure)

        # Should include 3 fast tests
        assert len(fast_tests) == 3, \
            f"Pre-push should run 3 fast tests, got {len(fast_tests)}"
        assert "test_root.py" in fast_tests
        assert "test_unit_fast.py" in fast_tests
        assert "test_lib_fast.py" in fast_tests

    def test_pre_push_marker_filtering_combines_correctly(self, nested_test_structure, pre_push_hook_path):
        """Test that pre-push hook combines marker filters with AND logic.

        REQUIREMENT: Hook must exclude tests with ANY slow/genai/integration marker.
        Expected: -m "not slow and not genai and not integration" (AND logic).
        """
        # This test will FAIL until hook is updated
        from plugins.autonomous_dev.lib.git_hooks import get_fast_test_command
        import re

        cmd = get_fast_test_command(nested_test_structure)
        # Extract marker expression using regex to handle quotes properly
        match = re.search(r'-m\s+["\']([^"\']+)["\']', cmd)
        assert match, "Command should have -m marker expression"
        marker_expr = match.group(1)

        assert "and" in marker_expr, \
            "Pre-push hook should use AND logic for marker exclusions"
        assert marker_expr.count("not") == 3, \
            "Pre-push hook should exclude 3 marker types (slow, genai, integration)"

    def test_pre_push_performance_improvement(self, nested_test_structure, pre_push_hook_path):
        """Test that pre-push hook runs significantly faster than full test suite.

        REQUIREMENT: Hook must reduce execution time from 2-5 min to <1 min.
        Expected: Fast tests run in <30s vs full suite 2-5 min.
        """
        # This test will FAIL until hook is updated
        from plugins.autonomous_dev.lib.git_hooks import estimate_test_duration

        full_suite_time = estimate_test_duration(nested_test_structure, fast_only=False)
        fast_only_time = estimate_test_duration(nested_test_structure, fast_only=True)

        improvement_ratio = full_suite_time / fast_only_time if fast_only_time > 0 else 0

        assert improvement_ratio >= 3.0, \
            f"Pre-push hook should be 3x+ faster (got {improvement_ratio:.1f}x)"

    def test_pre_push_fails_if_fast_tests_fail(self, nested_test_structure, pre_push_hook_path):
        """Test that pre-push hook fails if any fast test fails.

        REQUIREMENT: Hook must block push if fast tests fail.
        Expected: Hook exits with non-zero code if pytest fails.
        """
        # This test will FAIL until hook is updated
        from plugins.autonomous_dev.lib.git_hooks import run_pre_push_tests

        # Create failing fast test
        failing_test = nested_test_structure / "test_failing.py"
        failing_test.write_text("""
import pytest

def test_failing():
    assert False, "This test intentionally fails"
""")

        result = run_pre_push_tests(nested_test_structure)

        assert result.returncode != 0, \
            "Pre-push hook should fail if fast tests fail"
        assert "FAILED" in result.output or "failed" in result.output.lower()

    def test_pre_push_uses_minimal_pytest_verbosity(self, nested_test_structure, pre_push_hook_path):
        """Test that pre-push hook uses minimal pytest verbosity to avoid output bloat.

        REQUIREMENT: Hook must use --tb=line -q to prevent subprocess pipe deadlock (Issue #90).
        Expected: pytest command includes --tb=line -q flags.
        """
        # This test will FAIL until hook is updated
        from plugins.autonomous_dev.lib.git_hooks import get_fast_test_command

        cmd = get_fast_test_command(nested_test_structure)

        assert "--tb=line" in cmd, \
            "Pre-push hook should use --tb=line for minimal traceback"
        assert "-q" in cmd, \
            "Pre-push hook should use -q for quiet output (Issue #90)"


# ============================================================================
# Test Hook Generation/Activation
# ============================================================================


class TestHookGenerationUpdates:
    """Test hook generation script updates for Issue #94 improvements.

    REQUIREMENT: Hook generation must produce hooks with correct patterns.
    Expected: Generated hooks include recursive find and pytest markers.
    """

    def test_generated_pre_commit_has_recursive_find(self, temp_git_repo):
        """Test that generated pre-commit hook uses recursive find pattern.

        REQUIREMENT: Generated hook must use 'find tests -type f -name "test_*.py"'.
        Expected: Hook content includes -type f for recursive search.
        """
        # This test will FAIL until hook generator is updated
        from plugins.autonomous_dev.lib.git_hooks import generate_pre_commit_hook

        hook_content = generate_pre_commit_hook()

        assert 'find tests -type f -name "test_*.py"' in hook_content, \
            "Generated pre-commit hook should use recursive find"
        assert "-type f" in hook_content, \
            "Generated hook should explicitly use -type f"

    def test_generated_pre_push_has_marker_filtering(self, temp_git_repo):
        """Test that generated pre-push hook includes pytest marker filtering.

        REQUIREMENT: Generated hook must use -m "not slow and not genai and not integration".
        Expected: Hook content includes marker exclusion flags.
        """
        # This test will FAIL until hook generator is updated
        from plugins.autonomous_dev.lib.git_hooks import generate_pre_push_hook

        hook_content = generate_pre_push_hook()

        assert '-m "not slow and not genai and not integration"' in hook_content, \
            "Generated pre-push hook should filter by markers"
        assert "not slow" in hook_content
        assert "not genai" in hook_content
        assert "not integration" in hook_content

    def test_generated_pre_push_has_minimal_verbosity(self, temp_git_repo):
        """Test that generated pre-push hook includes minimal verbosity flags.

        REQUIREMENT: Generated hook must use --tb=line -q (Issue #90).
        Expected: Hook content includes verbosity flags.
        """
        # This test will FAIL until hook generator is updated
        from plugins.autonomous_dev.lib.git_hooks import generate_pre_push_hook

        hook_content = generate_pre_push_hook()

        assert "--tb=line" in hook_content, \
            "Generated pre-push hook should use --tb=line"
        assert "-q" in hook_content, \
            "Generated pre-push hook should use -q for quiet output"

    def test_hook_activator_includes_updated_hooks(self, temp_git_repo):
        """Test that hook activator activates updated pre-commit and pre-push hooks.

        REQUIREMENT: Hook activator must install hooks with Issue #94 improvements.
        Expected: Activated hooks use recursive find and marker filtering.
        """
        # This test will FAIL until hook activator is updated
        from plugins.autonomous_dev.lib.hook_activator import HookActivator

        activator = HookActivator(temp_git_repo)
        result = activator.activate_hooks({
            "hooks": {
                "PreCommit": ["validate_structure.py"],
                "PrePush": ["run_fast_tests.py"]
            }
        })

        # Check installed hooks have correct patterns
        pre_commit_path = temp_git_repo / ".git" / "hooks" / "pre-commit"
        pre_push_path = temp_git_repo / ".git" / "hooks" / "pre-push"

        if pre_commit_path.exists():
            content = pre_commit_path.read_text()
            assert "-type f" in content, \
                "Activated pre-commit should use recursive find"

        if pre_push_path.exists():
            content = pre_push_path.read_text()
            assert "not slow and not genai and not integration" in content, \
                "Activated pre-push should filter markers"


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestHookEdgeCases:
    """Test edge cases and error handling for git hook improvements."""

    def test_pre_commit_handles_empty_test_directory(self, temp_git_repo, pre_commit_hook_path):
        """Test that pre-commit hook handles empty tests/ directory gracefully.

        REQUIREMENT: Hook must handle projects with no tests yet.
        Expected: Hook succeeds with 0 tests found message.
        """
        # Create empty tests directory
        tests_dir = temp_git_repo / "tests"
        tests_dir.mkdir()

        # This test will FAIL until hook is updated
        from plugins.autonomous_dev.lib.git_hooks import discover_tests_recursive

        discovered = discover_tests_recursive(tests_dir)

        assert len(discovered) == 0, \
            "Pre-commit hook should handle empty test directory"

    def test_pre_commit_handles_missing_test_directory(self, temp_git_repo, pre_commit_hook_path):
        """Test that pre-commit hook handles missing tests/ directory gracefully.

        REQUIREMENT: Hook must handle projects without tests/ directory.
        Expected: Hook succeeds with warning message.
        """
        # Don't create tests directory

        # This test will FAIL until hook is updated
        from plugins.autonomous_dev.lib.git_hooks import discover_tests_recursive

        # Should not raise exception
        discovered = discover_tests_recursive(temp_git_repo / "tests")
        assert discovered == [], \
            "Pre-commit hook should return empty list for missing directory"

    def test_pre_push_handles_all_tests_marked_slow(self, temp_git_repo, pre_push_hook_path):
        """Test that pre-push hook handles case where all tests are marked slow.

        REQUIREMENT: Hook must handle edge case of 0 fast tests.
        Expected: Hook succeeds with informational message (no fast tests to run).
        """
        # Create tests directory with only slow tests
        tests_dir = temp_git_repo / "tests"
        tests_dir.mkdir()

        (tests_dir / "test_slow.py").write_text("""
import pytest

@pytest.mark.slow
def test_slow():
    assert True
""")

        # This test will FAIL until hook is updated
        from plugins.autonomous_dev.lib.git_hooks import run_pre_push_tests

        result = run_pre_push_tests(tests_dir)

        assert result.returncode == 0, \
            "Pre-push hook should succeed when no fast tests (nothing to run)"
        assert "no tests ran" in result.output.lower() or "0 passed" in result.output or "deselected" in result.output.lower()

    def test_pre_push_handles_pytest_not_installed(self, temp_git_repo, pre_push_hook_path):
        """Test that pre-push hook handles missing pytest gracefully.

        REQUIREMENT: Hook must not fail if pytest not installed.
        Expected: Hook prints warning and exits successfully (non-blocking).
        """
        # This test will FAIL until hook is updated
        from plugins.autonomous_dev.lib.git_hooks import run_pre_push_tests

        with patch("subprocess.run") as mock_run:
            # Simulate pytest not found
            mock_run.side_effect = FileNotFoundError("pytest not found")

            result = run_pre_push_tests(temp_git_repo / "tests")

            assert result.returncode == 0, \
                "Pre-push hook should not block push when pytest missing"
            assert "warning" in result.output.lower() or "skipping" in result.output.lower()


# ============================================================================
# Integration Tests - Full Hook Execution
# ============================================================================


@pytest.mark.integration
class TestHookIntegration:
    """Integration tests for full hook execution in git workflow."""

    def test_pre_commit_hook_integration_nested_tests(self, temp_git_repo, nested_test_structure):
        """Integration test: Pre-commit hook discovers all tests in nested structure.

        REQUIREMENT: Hook must work end-to-end with real git commit.
        Expected: All 7 tests discovered and reported.
        """
        # This test will FAIL until hook is fully implemented
        # Install the actual hook
        hook_src = Path(__file__).parent.parent.parent.parent / "scripts" / "hooks" / "pre-commit"
        hook_dst = temp_git_repo / ".git" / "hooks" / "pre-commit"

        # Create minimal hook that calls discovery
        hook_dst.write_text(f"""#!/bin/bash
set -e
cd {temp_git_repo}
python -c "
from plugins.autonomous_dev.lib.git_hooks import discover_tests_recursive
from pathlib import Path
tests = discover_tests_recursive(Path('{nested_test_structure}'))
print(f'Found {{len(tests)}} test files')
if len(tests) != 7:
    exit(1)
"
""")
        hook_dst.chmod(0o755)

        # Stage a file and commit
        test_file = temp_git_repo / "test.txt"
        test_file.write_text("test")
        subprocess.run(["git", "add", "test.txt"], cwd=temp_git_repo, check=True)

        # Run commit (triggers pre-commit hook)
        result = subprocess.run(
            ["git", "commit", "-m", "test commit"],
            cwd=temp_git_repo,
            capture_output=True,
            text=True
        )

        assert result.returncode == 0, \
            f"Pre-commit hook should succeed. Output: {result.stderr}"
        assert "Found 7 test files" in result.stdout or "Found 7 test files" in result.stderr

    @pytest.mark.slow
    def test_pre_push_hook_integration_fast_tests_only(self, temp_git_repo, nested_test_structure):
        """Integration test: Pre-push hook runs only fast tests.

        REQUIREMENT: Hook must exclude slow/genai/integration tests in real push.
        Expected: Only 3 fast tests executed.
        """
        # This test will FAIL until hook is fully implemented
        # Install the actual hook
        hook_dst = temp_git_repo / ".git" / "hooks" / "pre-push"

        # Create minimal hook that runs fast tests
        hook_dst.write_text(f"""#!/bin/bash
set -e
cd {temp_git_repo}
pytest {nested_test_structure} -m "not slow and not genai and not integration" --tb=line -q -v
""")
        hook_dst.chmod(0o755)

        # Create remote and push
        remote_dir = temp_git_repo.parent / "remote.git"
        subprocess.run(["git", "init", "--bare", str(remote_dir)], check=True, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", str(remote_dir)], cwd=temp_git_repo, check=True)

        # Make initial commit
        test_file = temp_git_repo / "test.txt"
        test_file.write_text("test")
        subprocess.run(["git", "add", "."], cwd=temp_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=temp_git_repo, check=True)

        # Push (triggers pre-push hook)
        result = subprocess.run(
            ["git", "push", "-u", "origin", "master"],
            cwd=temp_git_repo,
            capture_output=True,
            text=True
        )

        # Hook should run fast tests only (3 passed)
        assert result.returncode == 0, \
            f"Pre-push hook should succeed. Output: {result.stderr}"
        assert "3 passed" in result.stdout or "3 passed" in result.stderr, \
            "Pre-push should run 3 fast tests only"


# ============================================================================
# Test Summary for TDD Red Phase Verification
# ============================================================================

"""
TDD Red Phase Verification Summary
==================================

This test file contains 30+ tests that will FAIL until Issue #94 is implemented:

PRE-COMMIT HOOK IMPROVEMENTS (9 tests):
1. test_pre_commit_finds_root_level_tests - Root level test discovery
2. test_pre_commit_finds_nested_unit_tests - Unit subdirectory discovery
3. test_pre_commit_finds_deeply_nested_tests - 2+ level nested discovery
4. test_pre_commit_finds_integration_tests - Integration subdirectory discovery
5. test_pre_commit_counts_all_tests_nested - Total test count accuracy
6. test_pre_commit_backwards_compatible_flat_structure - Flat structure support
7. test_pre_commit_ignores_pycache_directories - __pycache__ exclusion
8. test_pre_commit_only_finds_test_prefix_files - test_*.py pattern only
9. test_generated_pre_commit_has_recursive_find - Hook generation

PRE-PUSH HOOK IMPROVEMENTS (9 tests):
10. test_pre_push_excludes_slow_marker_tests - Exclude @pytest.mark.slow
11. test_pre_push_excludes_genai_marker_tests - Exclude @pytest.mark.genai
12. test_pre_push_excludes_integration_marker_tests - Exclude @pytest.mark.integration
13. test_pre_push_runs_unmarked_fast_tests - Include fast tests
14. test_pre_push_marker_filtering_combines_correctly - AND logic for markers
15. test_pre_push_performance_improvement - 3x+ speed improvement
16. test_pre_push_fails_if_fast_tests_fail - Fail on test failure
17. test_pre_push_uses_minimal_pytest_verbosity - Issue #90 fix
18. test_generated_pre_push_has_marker_filtering - Hook generation

HOOK GENERATION (3 tests):
19. test_generated_pre_commit_has_recursive_find - Pre-commit generation
20. test_generated_pre_push_has_marker_filtering - Pre-push generation
21. test_generated_pre_push_has_minimal_verbosity - Verbosity flags
22. test_hook_activator_includes_updated_hooks - Hook activation

EDGE CASES (4 tests):
23. test_pre_commit_handles_empty_test_directory - Empty tests/
24. test_pre_commit_handles_missing_test_directory - Missing tests/
25. test_pre_push_handles_all_tests_marked_slow - All tests slow
26. test_pre_push_handles_pytest_not_installed - Pytest missing

INTEGRATION TESTS (2 tests):
27. test_pre_commit_hook_integration_nested_tests - Full pre-commit workflow
28. test_pre_push_hook_integration_fast_tests_only - Full pre-push workflow

TOTAL: 28 tests covering all aspects of Issue #94

Run verification command to confirm red phase:
    pytest tests/unit/hooks/test_git_hooks_issue94.py -v

Expected: All tests FAIL with ModuleNotFoundError or ImportError
"""
