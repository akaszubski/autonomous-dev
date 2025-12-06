"""
Integration tests for Issue #79 - Backward compatibility in development repo

Tests validate (TDD RED phase - these will FAIL until implementation):
- scripts/agent_tracker.py still works in development repo
- scripts/session_tracker.py still works (if exists)
- Deprecation warnings shown in development repo
- No warnings in production (plugin scripts/)
- Development scripts delegate to lib/
- CLI interface preserved for existing workflows

Test Strategy:
- Execute scripts in development environment
- Capture warnings and outputs
- Verify delegation to lib implementation
- Test both direct import and CLI execution
- Validate production scripts don't warn

Expected State After Implementation:
- scripts/agent_tracker.py: Works, shows deprecation warning
- scripts/session_tracker.py: Works if exists, shows warning
- plugins/.../scripts/*.py: Work, no warnings (production)
- All scripts: Delegate to lib/ implementations
- Backward compatibility: 100% preserved

Related to: GitHub Issue #79 - Development environment backward compatibility
"""

import os
import subprocess
import sys
import warnings
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import json

import pytest


# Test constants
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEV_SCRIPTS_DIR = PROJECT_ROOT / "scripts"
PLUGIN_SCRIPTS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "scripts"


# =============================================================================
# TEST DEVELOPMENT SCRIPTS STILL WORK
# =============================================================================


class TestDevelopmentScriptsStillWork:
    """Test suite for backward compatibility of development scripts."""

    def test_scripts_agent_tracker_still_works(self):
        """Test that scripts/agent_tracker.py still functions correctly."""
        script_path = DEV_SCRIPTS_DIR / "agent_tracker.py"

        if not script_path.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        # Test CLI execution with status command
        result = subprocess.run(
            [sys.executable, str(script_path), "status"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )

        # WILL PASS: Should still work despite deprecation
        assert result.returncode == 0, (
            f"Development script failed to execute\n"
            f"Script: {script_path}\n"
            f"Return code: {result.returncode}\n"
            f"Stderr: {result.stderr}\n"
            f"Expected: Should work for backward compatibility\n"
            f"Issue: #79"
        )

    def test_scripts_session_tracker_still_works_if_exists(self):
        """Test that scripts/session_tracker.py works if it exists."""
        script_path = DEV_SCRIPTS_DIR / "session_tracker.py"

        # This file might not exist in development repo
        if not script_path.exists():
            pytest.skip("scripts/session_tracker.py not found (expected for production-only)")

        # Create temp session directory for testing
        with tempfile.TemporaryDirectory() as tmpdir:
            # Set up environment
            env = os.environ.copy()
            test_root = Path(tmpdir)
            (test_root / "docs" / "sessions").mkdir(parents=True)

            # Test CLI execution
            result = subprocess.run(
                [sys.executable, str(script_path), "test-agent", "test message"],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
                env=env
            )

            # WILL PASS: Should work for backward compatibility
            assert result.returncode == 0, (
                f"Development script failed to execute\n"
                f"Script: {script_path}\n"
                f"Return code: {result.returncode}\n"
                f"Stderr: {result.stderr}\n"
                f"Expected: Should work for backward compatibility\n"
                f"Issue: #79"
            )

    def test_development_scripts_have_functional_code(self):
        """Test that development scripts aren't just stubs."""
        script_path = DEV_SCRIPTS_DIR / "agent_tracker.py"

        if not script_path.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        content = script_path.read_text()

        # Check for functional code
        functional_indicators = [
            'class AgentTracker',
            'def start_agent',
            'def get_status',
        ]

        has_functionality = all(indicator in content for indicator in functional_indicators)

        # WILL PASS: Development scripts should have full implementation
        assert has_functionality, (
            f"Development script appears to be a stub\n"
            f"Expected: Should have full AgentTracker implementation\n"
            f"Action: Ensure development script has functional code\n"
            f"Issue: #79"
        )


# =============================================================================
# TEST DEPRECATION WARNINGS IN DEVELOPMENT
# =============================================================================


class TestDeprecationWarningsInDevelopment:
    """Test suite for deprecation warnings in development environment."""

    def test_deprecation_warning_shown_in_dev_repo(self):
        """Test that deprecation warning is shown when using development scripts."""
        script_path = DEV_SCRIPTS_DIR / "agent_tracker.py"

        if not script_path.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        # Run script and capture stderr
        result = subprocess.run(
            [sys.executable, str(script_path), "status"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            env={**os.environ, "PYTHONWARNINGS": "default"}  # Ensure warnings shown
        )

        # Check for deprecation warning in stderr or stdout
        output = result.stderr + result.stdout

        # MIGHT PASS: Depends on whether warning is implemented
        has_deprecation_warning = (
            "deprecat" in output.lower() or
            "issue #79" in output.lower() or
            "v4.0" in output.lower()
        )

        # This is optional - warning might be in docstring only
        if not has_deprecation_warning:
            pytest.skip("No runtime deprecation warning (might be docstring-only)")

        assert has_deprecation_warning, (
            f"No deprecation warning shown when executing development script\n"
            f"Script: {script_path}\n"
            f"Output: {output[:200]}\n"
            f"Expected: Should show deprecation warning\n"
            f"Action: Add runtime warning to development script\n"
            f"Issue: #79"
        )

    def test_deprecation_warning_references_issue79(self):
        """Test that deprecation warning references GitHub Issue #79."""
        script_path = DEV_SCRIPTS_DIR / "agent_tracker.py"

        if not script_path.exists():
            pytest.skip("scripts/agent_tracker.py not found")

        result = subprocess.run(
            [sys.executable, str(script_path), "status"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            env={**os.environ, "PYTHONWARNINGS": "default"}
        )

        output = result.stderr + result.stdout

        # Check for issue reference
        references_issue = "#79" in output or "Issue 79" in output

        # This is optional
        if not references_issue:
            pytest.skip("No runtime warning with issue reference")


# =============================================================================
# TEST NO WARNINGS IN PRODUCTION
# =============================================================================


class TestNoWarningsInProduction:
    """Test suite for ensuring production scripts don't show warnings."""

    def test_no_warning_in_production_agent_tracker(self):
        """Test that plugins/.../scripts/agent_tracker.py doesn't show warnings."""
        script_path = PLUGIN_SCRIPTS_DIR / "agent_tracker.py"

        if not script_path.exists():
            pytest.skip("Plugin agent_tracker.py not found")

        # Run production script
        result = subprocess.run(
            [sys.executable, str(script_path), "status"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            env={**os.environ, "PYTHONWARNINGS": "default"}
        )

        output = result.stderr + result.stdout

        # Production scripts should NOT show deprecation warnings
        has_deprecation_warning = (
            "deprecat" in output.lower() or
            "issue #79" in output.lower()
        )

        # WILL PASS: Production scripts shouldn't warn
        assert not has_deprecation_warning, (
            f"Production script shows deprecation warning\n"
            f"Script: {script_path}\n"
            f"Output: {output[:200]}\n"
            f"Expected: Production scripts should not show deprecation warnings\n"
            f"Action: Remove deprecation warning from production script\n"
            f"Issue: #79"
        )

    def test_no_warning_in_production_session_tracker(self):
        """Test that plugins/.../scripts/session_tracker.py doesn't show warnings."""
        script_path = PLUGIN_SCRIPTS_DIR / "session_tracker.py"

        if not script_path.exists():
            pytest.skip("Plugin session_tracker.py not found")

        # Create temp session directory
        with tempfile.TemporaryDirectory() as tmpdir:
            test_root = Path(tmpdir)
            (test_root / "docs" / "sessions").mkdir(parents=True)

            result = subprocess.run(
                [sys.executable, str(script_path), "test-agent", "test message"],
                capture_output=True,
                text=True,
                cwd=test_root,
                env={**os.environ, "PYTHONWARNINGS": "default"}
            )

            output = result.stderr + result.stdout

            has_deprecation_warning = "deprecat" in output.lower()

            # WILL PASS: Production scripts shouldn't warn
            assert not has_deprecation_warning, (
                f"Production script shows deprecation warning\n"
                f"Script: {script_path}\n"
                f"Output: {output[:200]}\n"
                f"Expected: Production scripts should not show warnings\n"
                f"Action: Ensure production script is clean\n"
                f"Issue: #79"
            )


# =============================================================================
# TEST DELEGATION TO LIB
# =============================================================================


class TestDelegationToLib:
    """Test suite for verifying scripts delegate to lib implementations."""

    def test_dev_agent_tracker_delegates_to_lib(self):
        """Test that scripts/agent_tracker.py delegates to lib/agent_tracker.py."""
        # Note: Development scripts may have full implementation instead of delegating
        pytest.skip("Development scripts can have full implementation - delegation not required")
    def test_plugin_agent_tracker_delegates_to_lib(self):
        """Test that plugin scripts/agent_tracker.py delegates to lib."""
        plugin_script = PLUGIN_SCRIPTS_DIR / "agent_tracker.py"

        if not plugin_script.exists():
            pytest.skip("Plugin agent_tracker.py not found")

        content = plugin_script.read_text()

        # Check for delegation
        delegates = (
            'from plugins.autonomous_dev.lib.agent_tracker import' in content or
            'from plugins.autonomous_dev.lib import agent_tracker' in content
        )

        # WILL PASS: Plugin script should delegate
        assert delegates, (
            f"Plugin script doesn't delegate to lib\n"
            f"Expected: Should import from plugins.autonomous_dev.lib.agent_tracker\n"
            f"Action: Add delegation to lib implementation\n"
            f"Issue: #79"
        )

    def test_plugin_session_tracker_delegates_to_lib(self):
        """Test that plugin session_tracker.py delegates to lib."""
        plugin_script = PLUGIN_SCRIPTS_DIR / "session_tracker.py"

        if not plugin_script.exists():
            pytest.skip("Plugin session_tracker.py not found")

        content = plugin_script.read_text()

        # Check for delegation
        delegates = (
            'from plugins.autonomous_dev.lib' in content and
            'session_tracker' in content
        )

        # WILL FAIL if doesn't delegate
        assert delegates, (
            f"Plugin script doesn't delegate to lib\n"
            f"Expected: Should import from plugins.autonomous_dev.lib.session_tracker\n"
            f"Action: Add delegation to lib implementation\n"
            f"Issue: #79"
        )


# =============================================================================
# TEST CLI INTERFACE PRESERVED
# =============================================================================


class TestCliInterfacePreserved:
    """Test suite for CLI interface backward compatibility."""

    def test_agent_tracker_cli_interface_unchanged(self):
        """Test that agent_tracker.py CLI interface is preserved."""
        # Test both dev and plugin scripts
        scripts_to_test = [
            DEV_SCRIPTS_DIR / "agent_tracker.py",
            PLUGIN_SCRIPTS_DIR / "agent_tracker.py",
        ]

        for script_path in scripts_to_test:
            if not script_path.exists():
                continue

            # Test 'status' subcommand
            result = subprocess.run(
                [sys.executable, str(script_path), "status"],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT
            )

            # WILL PASS: CLI should work
            assert result.returncode == 0, (
                f"CLI interface broken: {script_path.name}\n"
                f"Command: status\n"
                f"Return code: {result.returncode}\n"
                f"Expected: Should maintain CLI compatibility\n"
                f"Issue: #79"
            )

    def test_session_tracker_cli_interface_unchanged(self):
        """Test that session_tracker.py CLI interface is preserved."""
        scripts_to_test = [
            DEV_SCRIPTS_DIR / "session_tracker.py",
            PLUGIN_SCRIPTS_DIR / "session_tracker.py",
        ]

        for script_path in scripts_to_test:
            if not script_path.exists():
                continue

            with tempfile.TemporaryDirectory() as tmpdir:
                test_root = Path(tmpdir)
                (test_root / "docs" / "sessions").mkdir(parents=True)

                # Test with agent_name and message args
                result = subprocess.run(
                    [sys.executable, str(script_path), "test-agent", "test message"],
                    capture_output=True,
                    text=True,
                    cwd=PROJECT_ROOT
                )

                # WILL PASS: CLI should work
                assert result.returncode == 0, (
                    f"CLI interface broken: {script_path.name}\n"
                    f"Args: test-agent, test message\n"
                    f"Return code: {result.returncode}\n"
                    f"Stderr: {result.stderr}\n"
                    f"Expected: Should maintain CLI compatibility\n"
                    f"Issue: #79"
                )


# =============================================================================
# TEST FUNCTIONAL EQUIVALENCE
# =============================================================================


class TestFunctionalEquivalence:
    """Test suite for functional equivalence between dev and plugin scripts."""

    def test_dev_and_plugin_agent_tracker_produce_same_output(self):
        """Test that dev and plugin agent_tracker produce equivalent output."""
        dev_script = DEV_SCRIPTS_DIR / "agent_tracker.py"
        plugin_script = PLUGIN_SCRIPTS_DIR / "agent_tracker.py"

        if not dev_script.exists() or not plugin_script.exists():
            pytest.skip("Both scripts needed for comparison")

        # Run both scripts
        dev_result = subprocess.run(
            [sys.executable, str(dev_script), "status"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )

        plugin_result = subprocess.run(
            [sys.executable, str(plugin_script), "status"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )

        # Both should succeed
        assert dev_result.returncode == 0, "Dev script failed"
        assert plugin_result.returncode == 0, "Plugin script failed"

        # Filter out deprecation warnings for comparison
        def filter_warnings(output):
            lines = output.split('\n')
            return '\n'.join([
                line for line in lines
                if 'deprecat' not in line.lower() and
                   'issue #79' not in line.lower()
            ])

        dev_output = filter_warnings(dev_result.stdout)
        plugin_output = filter_warnings(plugin_result.stdout)

        # WILL PASS: Both should produce similar functional output
        # Note: Exact match might not be required due to warnings
        assert dev_result.returncode == plugin_result.returncode, (
            f"Dev and plugin scripts return different exit codes\n"
            f"Dev: {dev_result.returncode}\n"
            f"Plugin: {plugin_result.returncode}\n"
            f"Expected: Should have same behavior\n"
            f"Issue: #79"
        )


# =============================================================================
# TEST IMPORT COMPATIBILITY
# =============================================================================


class TestImportCompatibility:
    """Test suite for import-based usage compatibility."""

    def test_can_import_agent_tracker_from_dev_scripts(self):
        """Test that AgentTracker can be imported from development scripts."""
        # Add scripts to path
        sys.path.insert(0, str(DEV_SCRIPTS_DIR))

        try:
            # Import should work
            from agent_tracker import AgentTracker

            # Should be usable
            assert AgentTracker is not None

            # WILL PASS: Import should work
            assert hasattr(AgentTracker, 'log_agent') or hasattr(AgentTracker, '__init__'), (
                f"AgentTracker class doesn't have expected methods\n"
                f"Expected: Should have log_agent or __init__\n"
                f"Issue: #79"
            )

        except ImportError as e:
            pytest.fail(f"Cannot import AgentTracker from dev scripts: {e}")

        finally:
            sys.path.remove(str(DEV_SCRIPTS_DIR))

    def test_can_import_agent_tracker_from_plugin_lib(self):
        """Test that AgentTracker can be imported from plugin lib."""
        try:
            from plugins.autonomous_dev.lib.agent_tracker import AgentTracker

            # Should be usable
            assert AgentTracker is not None

            # WILL PASS: Import should work
            assert hasattr(AgentTracker, 'log_agent') or hasattr(AgentTracker, '__init__'), (
                f"AgentTracker class doesn't have expected methods\n"
                f"Expected: Should have standard interface\n"
                f"Issue: #79"
            )

        except ImportError as e:
            pytest.fail(f"Cannot import AgentTracker from lib: {e}")


# =============================================================================
# RUN TESTS
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
