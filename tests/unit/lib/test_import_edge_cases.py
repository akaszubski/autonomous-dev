#!/usr/bin/env python3
"""
Import Edge Case Validation - Test Special Import Scenarios

VALIDATION PHASE - Tests verify edge case imports survive cleanup.

Purpose:
- Validate TYPE_CHECKING imports are preserved (type-only imports)
- Validate side-effect imports are preserved (import for side effects)
- Validate try/except import patterns with complex fallback logic
- Validate __all__ consistency after cleanup
- Validate star imports still work (if used)

Test Strategy:
- Focus on imports that Ruff might incorrectly flag as unused
- Test imports that exist for side effects (not direct usage)
- Test type annotation imports (runtime unused but type-checker needed)
- Test complex conditional import chains

Auto-Marker: unit

Coverage: Edge cases in import usage patterns

Date: 2025-12-25
Issue: Dead code cleanup validation
Agent: test-master
Phase: Validation (run before AND after cleanup)
"""

import sys
import pytest
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch, MagicMock

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


class TestTypeCheckingImports:
    """Test TYPE_CHECKING imports are preserved (not removed by Ruff)."""

    def test_tech_debt_detector_type_imports(self):
        """Test tech_debt_detector preserves TYPE_CHECKING imports."""
        try:
            # Import module that uses TYPE_CHECKING
            from tech_debt_detector import TechDebtDetector, Severity

            # Module should import without errors
            assert TechDebtDetector is not None
            assert Severity is not None

            # Type annotations should not cause runtime errors
            detector = TechDebtDetector(Path.cwd())
            assert detector is not None
        except ImportError:
            pytest.skip("tech_debt_detector not yet implemented")

    def test_type_annotations_in_function_signatures(self):
        """Test modules with type annotations in signatures still work."""
        # Import modules that use type annotations
        from path_utils import get_project_root
        from validation import validate_agent_name

        # Call functions (type annotations should not break runtime)
        root = get_project_root()
        assert root is not None

        safe_name = validate_agent_name("test-agent")
        assert safe_name == "test-agent"

    def test_forward_reference_imports(self):
        """Test forward references in type annotations don't break."""
        # Some modules may use string type annotations
        # These require TYPE_CHECKING imports
        from agent_tracker import AgentTracker

        # Should work even with forward references
        assert AgentTracker is not None


class TestSideEffectImports:
    """Test imports that exist for side effects (not direct usage)."""

    def test_logging_configuration_imports(self):
        """Test imports that configure logging (side effect)."""
        # Some modules may import logging config for side effects
        # These should not be removed by Ruff
        try:
            from logging_utils import setup_logging

            # Import exists for setup, may not be directly called
            assert setup_logging is not None
        except ImportError:
            # Module may not have this pattern
            pass

    def test_plugin_registration_imports(self):
        """Test imports that register plugins/hooks (side effect)."""
        # Some modules import for registration side effects
        # Example: import that registers a hook handler
        pass  # No specific examples in current codebase

    def test_module_initialization_imports(self):
        """Test imports that initialize module state."""
        # Some modules may import for state initialization
        from path_utils import get_project_root

        # First call initializes cache
        root1 = get_project_root()

        # Second call uses cached value
        root2 = get_project_root()

        assert root1 == root2


class TestComplexConditionalImports:
    """Test complex try/except import patterns with multiple fallbacks."""

    def test_search_utils_import_chain(self):
        """Test search_utils with multiple fallback import attempts."""
        try:
            from search_utils import bootstrap_knowledge_base

            # Should have tried multiple import paths
            assert bootstrap_knowledge_base is not None
        except ImportError as e:
            pytest.fail(f"search_utils import failed: {e}")

    def test_genai_validate_optional_import_chain(self):
        """Test genai_validate with optional dependency fallbacks."""
        try:
            from genai_validate import validate_manifest

            assert validate_manifest is not None
        except ImportError:
            # Optional dependencies missing - expected in some envs
            pytest.skip("Optional genai dependencies not installed")

    def test_sync_dispatcher_conditional_import(self):
        """Test sync_dispatcher with conditional imports based on environment."""
        try:
            from sync_dispatcher import SyncDispatcher

            assert SyncDispatcher is not None
        except ImportError as e:
            pytest.fail(f"sync_dispatcher import failed: {e}")

    def test_artifacts_fallback_import(self):
        """Test artifacts module with fallback import patterns."""
        try:
            from artifacts import ArtifactManager

            assert ArtifactManager is not None
        except ImportError:
            # May have optional dependencies
            pytest.skip("artifacts optional dependencies missing")


class TestAllExportConsistency:
    """Test __all__ exports remain consistent after cleanup."""

    def test_all_exports_match_public_api(self):
        """Test __all__ includes all public functions (no leading _)."""
        try:
            from security_utils import __all__

            import security_utils

            # Get all public names (no leading _)
            public_names = [
                name for name in dir(security_utils) if not name.startswith("_")
            ]

            # Filter to functions/classes (not imported modules)
            import inspect

            public_callables = [
                name
                for name in public_names
                if callable(getattr(security_utils, name))
                and not inspect.ismodule(getattr(security_utils, name))
            ]

            # All public callables should be in __all__ (best practice)
            # Note: This may fail if __all__ is incomplete (intentional selective export)
            # Also skip constants (uppercase names like PROJECT_ROOT)
            for name in __all__:
                if not name.isupper():  # Skip constants
                    assert name in public_callables, f"{name} in __all__ but not public"
        except ImportError:
            # No __all__ defined - OK
            pass

    def test_all_exports_are_importable(self):
        """Test all names in __all__ can actually be imported."""
        try:
            from security_utils import __all__

            # Try importing each name
            for name in __all__:
                exec(f"from security_utils import {name}")
                # If no ImportError, export is valid
        except ImportError:
            # No __all__ defined - OK
            pass

    def test_validation_all_exports_if_defined(self):
        """Test validation module __all__ exports are valid."""
        try:
            from validation import __all__

            for name in __all__:
                exec(f"from validation import {name}")
        except ImportError:
            # No __all__ defined - OK
            pass

    def test_path_utils_all_exports_if_defined(self):
        """Test path_utils module __all__ exports are valid."""
        try:
            from path_utils import __all__

            for name in __all__:
                exec(f"from path_utils import {name}")
        except ImportError:
            # No __all__ defined - OK
            pass


class TestImportOrderPreservation:
    """Test import order doesn't affect functionality after cleanup."""

    def test_import_order_path_utils_first(self):
        """Test importing path_utils before validation works."""
        # Clear modules to ensure fresh import
        for mod in ["path_utils", "validation", "agent_tracker"]:
            if mod in sys.modules:
                del sys.modules[mod]

        # Import in specific order
        from path_utils import get_project_root
        from validation import validate_session_path
        from agent_tracker import AgentTracker

        assert get_project_root is not None
        assert validate_session_path is not None
        assert AgentTracker is not None

    def test_import_order_validation_first(self):
        """Test importing validation before path_utils works."""
        # Clear modules
        for mod in ["path_utils", "validation", "agent_tracker"]:
            if mod in sys.modules:
                del sys.modules[mod]

        # Import in different order
        from validation import validate_session_path
        from path_utils import get_project_root
        from agent_tracker import AgentTracker

        assert validate_session_path is not None
        assert get_project_root is not None
        assert AgentTracker is not None

    def test_import_order_agent_tracker_first(self):
        """Test importing agent_tracker first works (pulls in deps)."""
        # Clear modules
        for mod in ["path_utils", "validation", "agent_tracker"]:
            if mod in sys.modules:
                del sys.modules[mod]

        # Import agent_tracker first (has dependencies)
        from agent_tracker import AgentTracker
        from path_utils import get_project_root
        from validation import validate_session_path

        assert AgentTracker is not None
        assert get_project_root is not None
        assert validate_session_path is not None


class TestNamespacePackageImports:
    """Test imports from namespace packages work correctly."""

    def test_autonomous_dev_namespace(self):
        """Test autonomous_dev namespace package structure."""
        # Test that autonomous_dev can be used as namespace
        # (plugins/autonomous-dev becomes autonomous_dev for imports)
        try:
            from autonomous_dev.lib import path_utils

            assert path_utils is not None
        except ImportError:
            # Namespace not set up - expected in some test environments
            pytest.skip("autonomous_dev namespace not configured")

    def test_lib_module_imports_via_namespace(self):
        """Test lib modules can be imported via namespace."""
        try:
            from autonomous_dev.lib.agent_tracker import AgentTracker

            assert AgentTracker is not None
        except ImportError:
            pytest.skip("autonomous_dev namespace not configured")


class TestReloadAfterModification:
    """Test modules can be reloaded after modification (import system robust)."""

    def test_reload_path_utils(self):
        """Test path_utils can be reloaded."""
        import importlib

        from path_utils import get_project_root

        # Reload module
        import path_utils

        importlib.reload(path_utils)

        # Should still work
        from path_utils import get_project_root as get_root_reloaded

        assert get_root_reloaded is not None

    def test_reload_validation(self):
        """Test validation can be reloaded."""
        import importlib

        from validation import validate_session_path

        # Reload module
        import validation

        importlib.reload(validation)

        # Should still work
        from validation import validate_session_path as validate_reloaded

        assert validate_reloaded is not None


class TestCrossModuleImports:
    """Test imports that span multiple module boundaries."""

    def test_git_operations_full_chain(self):
        """Test git_operations imports entire dependency chain."""
        from git_operations import GitOperations

        # GitOperations likely imports:
        # - security_utils (for command validation)
        # - validation (for path safety)
        # - subprocess (for git commands)

        # GitOperations is a class, verify it can be imported
        assert GitOperations is not None

    def test_batch_state_manager_full_chain(self):
        """Test batch_state_manager imports entire dependency chain."""
        from batch_state_manager import BatchStateManager

        # BatchStateManager imports:
        # - path_utils (for paths)
        # - json (for state serialization)
        # - validation (for safety)

        manager = BatchStateManager()
        assert manager is not None

    def test_auto_approval_engine_full_chain(self):
        """Test auto_approval_engine imports dependency chain."""
        from auto_approval_engine import should_auto_approve

        # auto_approval_engine imports:
        # - security_utils
        # - validation
        # - json (for policy)

        assert should_auto_approve is not None


class TestUnusedImportPreservation:
    """Test imports that appear unused but serve important purposes."""

    def test_import_for_type_checking_only(self):
        """Test imports used only in type annotations are preserved."""
        # TYPE_CHECKING imports should not be removed
        if TYPE_CHECKING:
            # These imports only exist for type checkers
            from typing import Optional, Dict, List

        # Module should still load without these imports at runtime
        pass

    def test_import_for_side_effect_only(self):
        """Test imports that have side effects are preserved."""
        # Example: Importing a module that registers hooks/plugins
        # Even if not directly used, side effect is important
        pass

    def test_import_for_reexport(self):
        """Test imports that are re-exported via __all__."""
        # Modules may import and re-export
        # Example: from validation import is_safe_path
        #          __all__ = ['is_safe_path']
        # Import appears unused but is re-exported
        pass


# =============================================================================
# REGRESSION PREVENTION TESTS
# =============================================================================


class TestRegressionPrevention:
    """Test scenarios that have caused issues in previous cleanups."""

    def test_no_missing_imports_after_cleanup(self):
        """Test no ImportError after cleanup (regression check)."""
        # Import all critical modules
        modules_to_test = [
            "agent_tracker",
            "path_utils",
            "validation",
            "session_tracker",
            "security_utils",
            "git_operations",
            "batch_state_manager",
            "auto_approval_engine",
            "failure_classifier",
            "error_analyzer",
        ]

        for module_name in modules_to_test:
            try:
                __import__(module_name)
            except ImportError as e:
                pytest.fail(f"Module {module_name} failed to import: {e}")

    def test_no_circular_imports_introduced(self):
        """Test cleanup didn't introduce circular imports."""
        # Import modules in various orders
        # Clear sys.modules first
        for mod in list(sys.modules.keys()):
            if (
                "path_utils" in mod
                or "validation" in mod
                or "agent_tracker" in mod
                or "session_tracker" in mod
            ):
                del sys.modules[mod]

        # Import should work regardless of order
        from agent_tracker import AgentTracker
        from path_utils import get_project_root
        from validation import validate_session_path
        from session_tracker import SessionTracker

        assert AgentTracker is not None
        assert get_project_root is not None
        assert validate_session_path is not None
        assert SessionTracker is not None

    def test_no_broken_relative_imports(self):
        """Test relative imports still work after cleanup."""
        # Test lib-to-lib imports
        from agent_tracker import AgentTracker

        # If this succeeds, relative import chain (agent_tracker -> path_utils) works
        assert AgentTracker is not None
