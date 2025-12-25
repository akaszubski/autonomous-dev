#!/usr/bin/env python3
"""
Dynamic Import Tests - Validate sys.path.insert Patterns and Conditional Imports

VALIDATION PHASE - Tests verify dynamic import mechanisms work before/after cleanup.

Purpose:
- Validate modules that use sys.path.insert still find dependencies
- Validate try/except import patterns handle missing optional deps
- Validate TYPE_CHECKING imports are preserved (not removed by Ruff)
- Validate __all__ exports remain intact

Test Strategy:
- Mock missing dependencies to test graceful fallback
- Verify sys.path.insert patterns work from various directories
- Test conditional imports with both success and failure paths
- Verify type-checking-only imports don't cause runtime errors

Auto-Marker: unit

Coverage: Dynamic import patterns across codebase

Date: 2025-12-25
Issue: Dead code cleanup validation
Agent: test-master
Phase: Validation (run before AND after cleanup)
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import importlib
import importlib.util

# Ensure plugins directory is in path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "plugins"))
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)


class TestSysPathInsertPatterns:
    """Test modules using sys.path.insert to find dependencies."""

    def test_batch_state_manager_finds_path_utils(self):
        """Test batch_state_manager can find path_utils via sys.path.insert."""
        # Import fresh (clear from sys.modules if already loaded)
        if "batch_state_manager" in sys.modules:
            del sys.modules["batch_state_manager"]

        from batch_state_manager import BatchStateManager

        # If import succeeds, sys.path.insert worked
        assert BatchStateManager is not None

    def test_feature_dependency_analyzer_finds_deps(self):
        """Test feature_dependency_analyzer finds dependencies via sys.path."""
        if "feature_dependency_analyzer" in sys.modules:
            del sys.modules["feature_dependency_analyzer"]

        from feature_dependency_analyzer import analyze_dependencies

        assert analyze_dependencies is not None

    def test_agent_tracker_finds_validation(self):
        """Test agent_tracker finds validation module via sys.path."""
        if "agent_tracker" in sys.modules:
            del sys.modules["agent_tracker"]

        from agent_tracker import AgentTracker

        # AgentTracker imports validation - if this works, path resolution works
        assert AgentTracker is not None

    def test_hook_modules_find_lib_deps(self):
        """Test hooks can find lib modules via sys.path modification."""
        # Test that hooks successfully import lib modules
        # (indirect test - if hook loads, sys.path.insert worked)

        # Load auto_git_workflow.py
        hook_path = (
            Path(__file__).parent.parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "hooks"
            / "auto_git_workflow.py"
        )

        spec = importlib.util.spec_from_file_location("auto_git_workflow", hook_path)
        assert spec is not None

        # Don't execute (avoid side effects), but verify it can be loaded
        module = importlib.util.module_from_spec(spec)
        assert module is not None


class TestConditionalImports:
    """Test try/except import patterns handle optional dependencies."""

    def test_search_utils_missing_ripgrep(self):
        """Test search_utils handles missing ripgrep gracefully."""
        # Mock ripgrep as missing
        with patch.dict(sys.modules, {"ripgrep": None}):
            # Should still import successfully
            from search_utils import bootstrap_knowledge_base

            assert bootstrap_knowledge_base is not None

    def test_genai_validate_missing_deps(self):
        """Test genai_validate handles missing optional dependencies."""
        # Try importing - should either succeed or raise ImportError
        # (which we catch and skip)
        try:
            from genai_validate import validate_manifest

            assert validate_manifest is not None
        except ImportError:
            # Optional dependencies missing - expected in some environments
            pytest.skip("Optional dependencies not installed")

    def test_mcp_permission_validator_conditional_imports(self):
        """Test mcp_permission_validator try/except imports work."""
        try:
            from mcp_permission_validator import MCPPermissionValidator

            assert MCPPermissionValidator is not None
        except ImportError as e:
            # If this fails, it's a real error (not optional dependency)
            pytest.fail(f"Required import failed: {e}")

    def test_sync_dispatcher_conditional_imports(self):
        """Test sync_dispatcher handles conditional imports."""
        try:
            from sync_dispatcher import SyncDispatcher

            assert SyncDispatcher is not None
        except ImportError as e:
            pytest.fail(f"Required import failed: {e}")

    def test_artifacts_conditional_imports(self):
        """Test artifacts module handles conditional imports."""
        try:
            from artifacts import ArtifactManager

            assert ArtifactManager is not None
        except ImportError as e:
            # Check if this is optional dependency
            if "optional" in str(e).lower():
                pytest.skip("Optional dependency missing")
            else:
                pytest.fail(f"Required import failed: {e}")


class TestTypeCheckingImports:
    """Test TYPE_CHECKING imports are preserved and don't cause runtime errors."""

    def test_tech_debt_detector_type_checking(self):
        """Test tech_debt_detector TYPE_CHECKING imports preserved."""
        # Import the module
        try:
            from tech_debt_detector import TechDebtDetector

            # TYPE_CHECKING imports should not cause runtime errors
            # (they're only used by type checkers, not at runtime)
            detector = TechDebtDetector(Path.cwd())
            assert detector is not None
        except ImportError:
            pytest.skip("tech_debt_detector not yet implemented or missing deps")

    def test_type_annotations_dont_break_runtime(self):
        """Test that type annotations using TYPE_CHECKING don't break runtime."""
        # Import modules that use TYPE_CHECKING
        from path_utils import get_project_root

        # Should work at runtime even if type checker imports are missing
        root = get_project_root()
        assert root is not None


class TestAllExports:
    """Test __all__ exports remain valid after cleanup."""

    def test_security_utils_all_complete(self):
        """Test security_utils __all__ includes all public functions."""
        try:
            from security_utils import __all__

            import security_utils

            # Verify each exported name exists
            for name in __all__:
                assert hasattr(
                    security_utils, name
                ), f"__all__ exports missing: {name}"

            # Verify common functions are exported
            assert "validate_path" in __all__
            assert "audit_log" in __all__
        except ImportError:
            # No __all__ defined - OK
            pass

    def test_validation_exports_if_defined(self):
        """Test validation module exports (if __all__ defined)."""
        try:
            from validation import __all__

            import validation

            for name in __all__:
                assert hasattr(validation, name), f"__all__ exports missing: {name}"
        except ImportError:
            # No __all__ defined - acceptable
            pass

    def test_path_utils_exports_if_defined(self):
        """Test path_utils module exports (if __all__ defined)."""
        try:
            from path_utils import __all__

            import path_utils

            for name in __all__:
                assert hasattr(path_utils, name), f"__all__ exports missing: {name}"
        except ImportError:
            # No __all__ defined - acceptable
            pass


class TestRelativeImportResolution:
    """Test relative imports between lib modules resolve correctly."""

    def test_agent_tracker_imports_path_utils(self):
        """Test agent_tracker successfully imports path_utils."""
        from agent_tracker import AgentTracker

        # If this succeeds, relative import chain worked
        # agent_tracker -> path_utils
        assert AgentTracker is not None

    def test_agent_tracker_imports_validation(self):
        """Test agent_tracker successfully imports validation."""
        from agent_tracker import AgentTracker

        # agent_tracker -> validation
        assert AgentTracker is not None

    def test_session_tracker_imports_path_utils(self):
        """Test session_tracker successfully imports path_utils."""
        from session_tracker import SessionTracker

        # session_tracker -> path_utils
        assert SessionTracker is not None

    def test_batch_state_manager_imports_path_utils(self):
        """Test batch_state_manager successfully imports path_utils."""
        from batch_state_manager import BatchStateManager

        # batch_state_manager -> path_utils
        assert BatchStateManager is not None

    def test_git_operations_import_chain(self):
        """Test git_operations import chain resolves."""
        from git_operations import GitOperations

        # May import from validation, security_utils, etc.
        assert GitOperations is not None


class TestImportFromVariousDirectories:
    """Test imports work from different working directories."""

    def test_import_from_project_root(self, tmp_path, monkeypatch):
        """Test imports work when cwd is project root."""
        # Change to temp directory (simulate project root)
        monkeypatch.chdir(tmp_path)

        # Add plugins to path
        plugins_path = (
            Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev"
        )
        sys.path.insert(0, str(plugins_path / "lib"))

        # Import should still work
        from path_utils import get_project_root

        assert get_project_root is not None

    def test_import_from_subdirectory(self, tmp_path, monkeypatch):
        """Test imports work when cwd is subdirectory."""
        # Create subdirectory
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        monkeypatch.chdir(subdir)

        # Add plugins to path
        plugins_path = (
            Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev"
        )
        sys.path.insert(0, str(plugins_path / "lib"))

        # Import should still work
        from path_utils import get_project_root

        assert get_project_root is not None

    def test_import_from_tests_directory(self, monkeypatch):
        """Test imports work when cwd is tests directory."""
        tests_dir = Path(__file__).parent.parent.parent
        monkeypatch.chdir(tests_dir)

        # Import should still work (conftest.py sets up path)
        from path_utils import get_project_root

        assert get_project_root is not None


class TestOptionalDependencyFallback:
    """Test modules gracefully handle missing optional dependencies."""

    def test_search_utils_without_optional_tools(self):
        """Test search_utils works without ripgrep/fzf installed."""
        # Mock subprocess to simulate missing tools
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("ripgrep not found")

            from search_utils import bootstrap_knowledge_base

            # Should still import (may have limited functionality)
            assert bootstrap_knowledge_base is not None

    def test_tech_debt_detector_without_radon(self):
        """Test tech_debt_detector handles missing radon gracefully."""
        # Mock radon import failure
        with patch.dict(sys.modules, {"radon": None}):
            try:
                from tech_debt_detector import TechDebtDetector

                # Should import (may skip complexity analysis)
                assert TechDebtDetector is not None
            except ImportError:
                # Acceptable if module hasn't implemented fallback yet
                pytest.skip("tech_debt_detector requires radon")


class TestCircularImportPrevention:
    """Test that import cleanup doesn't introduce circular imports."""

    def test_no_circular_import_path_utils_validation(self):
        """Test path_utils and validation don't circularly import."""
        # Import both modules
        from path_utils import get_project_root
        from validation import validate_session_path

        # If both import without error, no circular dependency
        assert get_project_root is not None
        assert validate_session_path is not None

    def test_no_circular_import_agent_session_trackers(self):
        """Test agent_tracker and session_tracker don't circularly import."""
        from agent_tracker import AgentTracker
        from session_tracker import SessionTracker

        # Both should import successfully
        assert AgentTracker is not None
        assert SessionTracker is not None

    def test_no_circular_import_git_operations_chain(self):
        """Test git_operations import chain has no cycles."""
        from git_operations import GitOperations
        from security_utils import validate_path
        from validation import validate_session_path

        # All should import without circular dependency
        assert GitOperations is not None
        assert validate_path is not None
        assert validate_session_path is not None


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestImportEdgeCases:
    """Test edge cases in import behavior."""

    def test_import_after_sys_modules_clear(self):
        """Test re-importing after clearing sys.modules."""
        # Import module
        from path_utils import get_project_root

        # Clear from sys.modules
        if "path_utils" in sys.modules:
            del sys.modules["path_utils"]

        # Re-import should work
        from path_utils import get_project_root as get_root_2

        assert get_root_2 is not None

    def test_import_with_modified_sys_path(self, monkeypatch):
        """Test imports work with modified sys.path."""
        # Temporarily modify sys.path
        original_path = sys.path.copy()

        try:
            # Add extra path
            sys.path.insert(0, "/tmp/fake_path")

            # Import should still work (finds correct module)
            from path_utils import get_project_root

            assert get_project_root is not None
        finally:
            # Restore sys.path
            sys.path[:] = original_path

    def test_import_with_namespace_conflict(self):
        """Test imports work even with local variable name conflicts."""
        # Create local variable with same name as module
        path_utils = "fake_value"

        # Import should still work (uses different namespace)
        from path_utils import get_project_root

        assert get_project_root is not None
        assert path_utils == "fake_value"  # Local variable unchanged
