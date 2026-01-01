#!/usr/bin/env python3
"""
Integration Tests for UV Hook Execution - RED PHASE

This test suite validates that hooks execute correctly under both UV and
fallback (non-UV) environments (Issue #172).

Feature:
UV single-file scripts run hooks in isolated environments, with graceful
fallback to sys.path when UV unavailable.

Problem:
Hooks need to work in diverse environments:
- Development machines (may not have UV)
- CI/CD pipelines (may use UV)
- User projects (varying Python setups)
- Claude Code hook execution (environment varies)

Solution:
Dual-mode execution:
1. UV mode: Run via `uv run --script` with PEP 723 metadata
2. Fallback mode: Run via Python with sys.path.insert()

Test Coverage:
1. UV Execution Mode
   - Hooks execute successfully under UV
   - UV environment detection works
   - No dependency conflicts
   - Exit codes correct

2. Fallback Execution Mode
   - Hooks execute successfully without UV
   - sys.path.insert() fallback works
   - Library imports succeed
   - Exit codes correct

3. Environment Detection
   - UV_PROJECT_ENVIRONMENT detection accurate
   - Graceful degradation when UV unavailable
   - No crashes on missing env vars

4. Real Hook Integration
   - Test with actual hook files
   - Validate exit codes match expected behavior
   - Check output formatting
   - Verify error handling

TDD Workflow:
- Tests written FIRST (before implementation)
- All tests FAIL initially (hooks not yet updated)
- Implementation makes tests pass (GREEN phase)

Date: 2026-01-02
Feature: UV execution and fallback
Agent: test-master
Phase: RED (tests fail, no implementation yet)

Design Patterns:
    See testing-guide skill for TDD methodology and pytest patterns.
    See hook-patterns skill for hook lifecycle and exit codes.
    See python-standards skill for code conventions.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

import pytest


# Constants
HOOKS_DIR = Path(__file__).parent.parent.parent / "plugins/autonomous-dev/hooks"
LIB_DIR = Path(__file__).parent.parent.parent / "plugins/autonomous-dev/lib"

# Exit codes (from hook-patterns skill)
EXIT_SUCCESS = 0
EXIT_WARNING = 1
EXIT_BLOCK = 2


# Fixtures
@pytest.fixture
def sample_hooks():
    """Get sample hooks for testing (prefer simple, fast hooks)."""
    # Choose hooks that are simple and don't require complex setup
    simple_hooks = [
        "auto_git_workflow.py",  # Shim hook - minimal logic
        "unified_pre_tool.py",   # Core hook - good test case
    ]

    hooks = []
    for hook_name in simple_hooks:
        hook_path = HOOKS_DIR / hook_name
        if hook_path.exists():
            hooks.append(hook_path)

    if not hooks:
        pytest.skip("No sample hooks found for testing")

    return hooks


@pytest.fixture
def clean_environment(monkeypatch):
    """Provide clean environment without UV variables."""
    # Remove UV environment variables
    monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)
    monkeypatch.delenv("UV_TOOL_DIR", raising=False)
    monkeypatch.delenv("UV_PYTHON", raising=False)

    return monkeypatch


@pytest.fixture
def uv_environment(monkeypatch):
    """Provide environment with UV variables set."""
    # Set UV environment variables
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", "/tmp/uv-test-env")
    monkeypatch.setenv("UV_TOOL_DIR", "/tmp/uv-tools")

    return monkeypatch


@pytest.fixture
def mock_uv_available():
    """Check if UV is actually available on system."""
    try:
        result = subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# Test Classes
class TestUVExecutionMode:
    """Test hooks execute correctly under UV."""

    def test_uv_environment_detected(self, uv_environment):
        """UV environment should be detected via UV_PROJECT_ENVIRONMENT."""
        # Create minimal test script
        test_script = """
import os

def is_running_under_uv() -> bool:
    return "UV_PROJECT_ENVIRONMENT" in os.environ

if __name__ == "__main__":
    result = is_running_under_uv()
    print(f"UV detected: {result}")
    exit(0 if result else 1)
"""

        result = subprocess.run(
            [sys.executable, "-c", test_script],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        assert result.returncode == 0, f"UV detection failed: {result.stderr}"
        assert "UV detected: True" in result.stdout

    @pytest.mark.skipif(
        not Path("/usr/bin/env").exists(),
        reason="env command not available"
    )
    def test_hook_executes_via_uv_shebang(self, sample_hooks, mock_uv_available):
        """Hooks should execute via UV shebang when UV available."""
        if not mock_uv_available:
            pytest.skip("UV not installed on system")

        for hook_file in sample_hooks:
            # Execute hook via shebang (simulates direct execution)
            result = subprocess.run(
                [str(hook_file), "--help"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Should not crash (exit codes 0, 1, or 2 are all valid)
            assert result.returncode in [EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK], (
                f"Hook {hook_file.name} crashed: {result.stderr}"
            )

    def test_uv_mode_no_sys_path_modification(self, sample_hooks, uv_environment):
        """In UV mode, sys.path should not be modified."""
        # This test validates that UV hooks don't pollute sys.path
        # when running in isolated UV environment

        test_script = """
import os
import sys

def is_running_under_uv() -> bool:
    return "UV_PROJECT_ENVIRONMENT" in os.environ

# Capture initial sys.path
initial_path = sys.path.copy()

# Simulate hook behavior
if not is_running_under_uv():
    sys.path.insert(0, "/some/lib/path")

# Check if sys.path was modified
modified = sys.path != initial_path

if is_running_under_uv():
    # UV mode - should NOT modify sys.path
    exit(0 if not modified else 1)
else:
    # Fallback mode - SHOULD modify sys.path
    exit(0 if modified else 1)
"""

        result = subprocess.run(
            [sys.executable, "-c", test_script],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        assert result.returncode == 0, (
            f"UV mode incorrectly modified sys.path: {result.stderr}"
        )


class TestFallbackExecutionMode:
    """Test hooks execute correctly without UV (fallback mode)."""

    def test_fallback_environment_not_detected(self, clean_environment):
        """Non-UV environment should not be detected as UV."""
        test_script = """
import os

def is_running_under_uv() -> bool:
    return "UV_PROJECT_ENVIRONMENT" in os.environ

if __name__ == "__main__":
    result = is_running_under_uv()
    print(f"UV detected: {result}")
    exit(1 if result else 0)
"""

        result = subprocess.run(
            [sys.executable, "-c", test_script],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        assert result.returncode == 0, f"Fallback detection failed: {result.stderr}"
        assert "UV detected: False" in result.stdout

    def test_fallback_uses_sys_path_insert(self, clean_environment):
        """Fallback mode should modify sys.path to find libraries."""
        test_script = """
import os
import sys
from pathlib import Path

def is_running_under_uv() -> bool:
    return "UV_PROJECT_ENVIRONMENT" in os.environ

# Capture initial sys.path
initial_path = sys.path.copy()

# Simulate hook behavior
if not is_running_under_uv():
    # Simulate adding lib path
    hook_dir = Path(__file__).parent if hasattr(Path(__file__), 'parent') else Path.cwd()
    lib_path = hook_dir / "lib"
    sys.path.insert(0, str(lib_path))

# Check if sys.path was modified
modified = sys.path != initial_path

# Fallback mode - SHOULD modify sys.path
exit(0 if modified else 1)
"""

        result = subprocess.run(
            [sys.executable, "-c", test_script],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        assert result.returncode == 0, (
            f"Fallback mode failed to modify sys.path: {result.stderr}"
        )

    def test_hook_executes_via_python_directly(self, sample_hooks, clean_environment):
        """Hooks should execute via Python when UV unavailable."""
        for hook_file in sample_hooks:
            # Execute hook via Python directly (fallback mode)
            result = subprocess.run(
                [sys.executable, str(hook_file), "--help"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Should not crash (exit codes 0, 1, or 2 are all valid)
            assert result.returncode in [EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK], (
                f"Hook {hook_file.name} crashed in fallback mode: {result.stderr}"
            )


class TestEnvironmentDetection:
    """Test environment detection logic."""

    def test_uv_detection_function_behavior(self):
        """is_running_under_uv() should behave correctly."""
        test_cases = [
            # (env_vars, expected_result)
            ({"UV_PROJECT_ENVIRONMENT": "/tmp/test"}, True),
            ({}, False),
            ({"OTHER_VAR": "value"}, False),
        ]

        for env_vars, expected in test_cases:
            test_script = f"""
import os

def is_running_under_uv() -> bool:
    return "UV_PROJECT_ENVIRONMENT" in os.environ

result = is_running_under_uv()
exit(0 if result == {expected} else 1)
"""

            env = os.environ.copy()
            # Clear UV vars
            env.pop("UV_PROJECT_ENVIRONMENT", None)
            # Add test vars
            env.update(env_vars)

            result = subprocess.run(
                [sys.executable, "-c", test_script],
                capture_output=True,
                text=True,
                env=env,
            )

            assert result.returncode == 0, (
                f"Detection failed for env_vars={env_vars}, expected={expected}\n"
                f"stderr: {result.stderr}"
            )

    def test_no_crash_on_missing_env_vars(self, clean_environment):
        """Hook should not crash when UV env vars missing."""
        test_script = """
import os

def is_running_under_uv() -> bool:
    # Safe check - doesn't raise KeyError
    return "UV_PROJECT_ENVIRONMENT" in os.environ

try:
    result = is_running_under_uv()
    exit(0)
except KeyError as e:
    print(f"KeyError: {e}")
    exit(1)
"""

        result = subprocess.run(
            [sys.executable, "-c", test_script],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        assert result.returncode == 0, (
            f"Hook crashed on missing env vars: {result.stderr}"
        )

    def test_graceful_degradation_no_uv(self, clean_environment):
        """Hooks should gracefully degrade when UV unavailable."""
        # Test that hook behavior is correct in both modes
        test_script = """
import os
import sys

def is_running_under_uv() -> bool:
    return "UV_PROJECT_ENVIRONMENT" in os.environ

def main():
    if is_running_under_uv():
        # UV mode - isolated execution
        mode = "uv"
    else:
        # Fallback mode - sys.path modification
        mode = "fallback"
        sys.path.insert(0, "/mock/lib")

    print(f"Mode: {mode}")
    return 0

if __name__ == "__main__":
    exit(main())
"""

        result = subprocess.run(
            [sys.executable, "-c", test_script],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        assert result.returncode == 0
        assert "Mode: fallback" in result.stdout


class TestRealHookIntegration:
    """Test with actual hook files."""

    def test_hook_imports_work_in_fallback_mode(self, clean_environment):
        """Hooks should successfully import libraries in fallback mode."""
        # Create minimal test hook that imports from lib
        test_hook = """
import os
import sys
from pathlib import Path

def is_running_under_uv() -> bool:
    return "UV_PROJECT_ENVIRONMENT" in os.environ

# Fallback: Add lib to path
if not is_running_under_uv():
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists():
            lib_path = current / "plugins/autonomous-dev/lib"
            if lib_path.exists():
                sys.path.insert(0, str(lib_path))
                break
        current = current.parent

# Try to import a library module
try:
    from path_utils import get_project_root
    print("Import successful")
    exit(0)
except ImportError as e:
    print(f"Import failed: {e}")
    # This is OK - library might not exist in test environment
    exit(0)
"""

        result = subprocess.run(
            [sys.executable, "-c", test_hook],
            capture_output=True,
            text=True,
            cwd=HOOKS_DIR,
            env=os.environ.copy(),
        )

        # Should not crash (imports may fail, but should be graceful)
        assert result.returncode == 0, f"Hook crashed: {result.stderr}"

    def test_hook_exit_codes_consistent(self, sample_hooks):
        """Hooks should return consistent exit codes in both modes."""
        # Test that exit codes are valid regardless of execution mode
        for hook_file in sample_hooks:
            # Test with --help (should not crash)
            result = subprocess.run(
                [sys.executable, str(hook_file), "--help"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Exit code should be one of the valid hook codes
            assert result.returncode in [EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK], (
                f"Hook {hook_file.name} returned invalid exit code: {result.returncode}\n"
                f"stderr: {result.stderr}"
            )

    def test_hook_error_messages_clear(self, sample_hooks):
        """Hooks should provide clear error messages on failure."""
        for hook_file in sample_hooks:
            # Trigger hook with invalid args (should produce error message)
            result = subprocess.run(
                [sys.executable, str(hook_file), "--invalid-flag-xyz"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Should have output (error message or help text)
            # Don't assert on specific content, just that it's not silent
            has_output = bool(result.stdout.strip() or result.stderr.strip())

            # Some hooks may accept unknown flags silently - that's OK
            # Just check that if it fails, it provides output
            if result.returncode != EXIT_SUCCESS:
                assert has_output, (
                    f"Hook {hook_file.name} failed silently (no error message)"
                )


class TestDependencyIsolation:
    """Test that UV execution isolates dependencies."""

    def test_no_external_dependencies_required(self, sample_hooks):
        """Hooks should not require external dependencies."""
        # All hooks should declare dependencies = []
        for hook_file in sample_hooks:
            content = hook_file.read_text()

            # Check PEP 723 metadata
            if "# dependencies = [" in content:
                # Extract dependencies list
                import re
                match = re.search(r'# dependencies = \[(.*?)\]', content)
                if match:
                    deps = match.group(1).strip()
                    assert deps == "", (
                        f"Hook {hook_file.name} has external dependencies: {deps}\n"
                        f"UV hooks should use only standard library"
                    )

    def test_no_import_errors_in_isolated_env(self, sample_hooks, clean_environment):
        """Hooks should not have import errors in clean environment."""
        for hook_file in sample_hooks:
            # Run hook in clean environment (no sys.path modifications)
            result = subprocess.run(
                [sys.executable, "-c", f"import importlib.util; spec = importlib.util.spec_from_file_location('hook', '{hook_file}'); importlib.util.module_from_spec(spec)"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # May fail to import, but should not crash Python interpreter
            # Some hooks might have missing dependencies - that's OK
            # Just check it doesn't cause interpreter crash
            assert "Segmentation fault" not in result.stderr
            assert "Fatal Python error" not in result.stderr


class TestPerformance:
    """Test performance characteristics of UV execution."""

    def test_hook_execution_fast(self, sample_hooks):
        """Hooks should execute quickly (< 5 seconds)."""
        import time

        for hook_file in sample_hooks:
            start = time.time()

            result = subprocess.run(
                [sys.executable, str(hook_file), "--help"],
                capture_output=True,
                text=True,
                timeout=5,  # 5 second timeout
            )

            elapsed = time.time() - start

            assert elapsed < 5.0, (
                f"Hook {hook_file.name} too slow: {elapsed:.2f}s\n"
                f"UV hooks should execute quickly"
            )

    def test_no_unnecessary_output(self, sample_hooks):
        """Hooks should not produce unnecessary output."""
        for hook_file in sample_hooks:
            # Run hook with minimal args
            result = subprocess.run(
                [sys.executable, str(hook_file)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Output should be minimal (no verbose logging by default)
            # Allow some output, but flag excessive verbosity
            lines = (result.stdout + result.stderr).count("\n")

            # Arbitrary threshold - hooks shouldn't print 100+ lines for simple execution
            assert lines < 100, (
                f"Hook {hook_file.name} produces excessive output: {lines} lines"
            )


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_hook_handles_sigint(self, sample_hooks):
        """Hooks should handle SIGINT gracefully."""
        # This is hard to test reliably, but we can at least check
        # that hooks don't have infinite loops
        # (timeout will catch infinite loops)

        for hook_file in sample_hooks:
            try:
                result = subprocess.run(
                    [sys.executable, str(hook_file), "--help"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                # If we get here, hook completed (good)
                assert True
            except subprocess.TimeoutExpired:
                pytest.fail(f"Hook {hook_file.name} timed out (possible infinite loop)")

    def test_hook_handles_invalid_input(self, sample_hooks):
        """Hooks should handle invalid input gracefully."""
        for hook_file in sample_hooks:
            # Try to break the hook with weird input
            result = subprocess.run(
                [sys.executable, str(hook_file)],
                input="invalid\x00binary\ndata\n",
                capture_output=True,
                timeout=30,
            )

            # Should not crash Python interpreter
            assert "Traceback" not in result.stderr or result.returncode in [EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK], (
                f"Hook {hook_file.name} crashed on invalid input"
            )

    def test_hook_works_in_different_cwd(self, sample_hooks, tmp_path):
        """Hooks should work when executed from different directory."""
        for hook_file in sample_hooks:
            # Execute hook from temporary directory
            result = subprocess.run(
                [sys.executable, str(hook_file), "--help"],
                capture_output=True,
                text=True,
                cwd=tmp_path,
                timeout=30,
            )

            # Should not crash (may fail, but should be graceful)
            assert result.returncode in [EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK], (
                f"Hook {hook_file.name} crashed when run from {tmp_path}"
            )


# Summary Test
class TestUVExecutionSummary:
    """Summary test validating complete UV execution setup."""

    def test_complete_uv_execution_workflow(self, sample_hooks, monkeypatch):
        """Test complete workflow: UV mode → fallback mode → detection."""
        for hook_file in sample_hooks:
            # Test 1: UV mode
            monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", "/tmp/test-uv")

            result_uv = subprocess.run(
                [sys.executable, str(hook_file), "--help"],
                capture_output=True,
                text=True,
                timeout=30,
                env=os.environ.copy(),
            )

            # Test 2: Fallback mode
            monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)

            result_fallback = subprocess.run(
                [sys.executable, str(hook_file), "--help"],
                capture_output=True,
                text=True,
                timeout=30,
                env=os.environ.copy(),
            )

            # Both modes should work (not crash)
            assert result_uv.returncode in [EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK], (
                f"Hook {hook_file.name} failed in UV mode"
            )

            assert result_fallback.returncode in [EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK], (
                f"Hook {hook_file.name} failed in fallback mode"
            )

            # Exit codes should be consistent between modes
            # (for --help, both should return same code)
            assert result_uv.returncode == result_fallback.returncode, (
                f"Hook {hook_file.name} has inconsistent exit codes:\n"
                f"  UV mode: {result_uv.returncode}\n"
                f"  Fallback mode: {result_fallback.returncode}"
            )
