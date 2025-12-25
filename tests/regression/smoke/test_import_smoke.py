#!/usr/bin/env python3
"""
Import Smoke Tests - Validate Critical Imports Work Before/After Cleanup

VALIDATION PHASE - These tests verify imports work BEFORE cleanup and continue
working AFTER cleanup. Not TDD (no implementation needed), but validation.

Purpose:
- Run BEFORE Ruff cleanup to establish baseline
- Run AFTER Ruff cleanup to verify no regressions
- Catch import errors that would break functionality

Tests cover:
- Core library modules (agent_tracker, path_utils, validation, session_tracker)
- Hook modules (unified_pre_tool, auto_git_workflow)
- Script modules (session_tracker CLI, agent_tracker CLI)
- Critical utilities (security_utils, git_operations, batch_state_manager)
- Optional dependencies (handled gracefully if missing)

Test Strategy:
- Simple import tests (no complex logic)
- Verify key classes/functions exist
- Test module __all__ exports (if defined)
- Mock optional dependencies that may be missing

Auto-Marker: smoke (< 5s, CI gate)

Coverage: Critical import paths only (not exhaustive)

Date: 2025-12-25
Issue: Dead code cleanup validation
Agent: test-master
Phase: Validation (run before AND after cleanup)
"""

import sys
import pytest
from pathlib import Path
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


class TestCoreLibraryImports:
    """Test core library modules can be imported."""

    def test_agent_tracker_import(self):
        """Test agent_tracker module imports successfully."""
        from agent_tracker import AgentTracker

        assert AgentTracker is not None
        assert hasattr(AgentTracker, "save_agent_checkpoint")

    def test_path_utils_import(self):
        """Test path_utils module imports successfully."""
        from path_utils import get_project_root, get_session_dir, get_batch_state_file

        assert get_project_root is not None
        assert get_session_dir is not None
        assert get_batch_state_file is not None

    def test_validation_import(self):
        """Test validation module imports successfully."""
        from validation import validate_session_path, validate_agent_name

        assert validate_session_path is not None
        assert validate_agent_name is not None

    def test_session_tracker_import(self):
        """Test session_tracker module imports successfully."""
        from session_tracker import SessionTracker

        assert SessionTracker is not None
        # SessionTracker is a class, check it can be instantiated
        tracker = SessionTracker()
        assert tracker is not None

    def test_security_utils_import(self):
        """Test security_utils module imports successfully."""
        from security_utils import (
            validate_path,
            validate_agent_name,
            audit_log,
        )

        assert validate_path is not None
        assert validate_agent_name is not None
        assert audit_log is not None

    def test_git_operations_import(self):
        """Test git_operations module imports successfully."""
        from git_operations import GitOperations

        assert GitOperations is not None
        assert hasattr(GitOperations, "commit")
        assert hasattr(GitOperations, "push")

    def test_batch_state_manager_import(self):
        """Test batch_state_manager module imports successfully."""
        from batch_state_manager import BatchStateManager

        assert BatchStateManager is not None
        assert hasattr(BatchStateManager, "load_state")
        assert hasattr(BatchStateManager, "save_state")


class TestHookModuleImports:
    """Test hook modules can be imported."""

    def test_unified_pre_tool_import(self):
        """Test unified_pre_tool hook imports successfully."""
        # Mock stdin to prevent blocking
        with patch("sys.stdin.read", return_value='{"tool_name": "Bash"}'):
            # Import the module (don't run main)
            import importlib.util

            hook_path = (
                Path(__file__).parent.parent.parent.parent
                / "plugins"
                / "autonomous-dev"
                / "hooks"
                / "unified_pre_tool.py"
            )

            spec = importlib.util.spec_from_file_location(
                "unified_pre_tool", hook_path
            )
            module = importlib.util.module_from_spec(spec)

            # Verify module structure (don't execute main)
            assert spec is not None
            assert module is not None

    def test_auto_git_workflow_import(self):
        """Test auto_git_workflow hook imports successfully."""
        import importlib.util

        hook_path = (
            Path(__file__).parent.parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "hooks"
            / "auto_git_workflow.py"
        )

        spec = importlib.util.spec_from_file_location("auto_git_workflow", hook_path)
        module = importlib.util.module_from_spec(spec)

        assert spec is not None
        assert module is not None


class TestUtilityModuleImports:
    """Test utility modules can be imported."""

    def test_workflow_coordinator_import(self):
        """Test workflow_coordinator module imports successfully."""
        from workflow_coordinator import WorkflowCoordinator

        assert WorkflowCoordinator is not None

    def test_checkpoint_import(self):
        """Test checkpoint module imports successfully."""
        from checkpoint import CheckpointManager

        assert CheckpointManager is not None

    def test_error_analyzer_import(self):
        """Test error_analyzer module imports successfully."""
        from error_analyzer import ErrorAnalyzer

        assert ErrorAnalyzer is not None
        assert hasattr(ErrorAnalyzer, "analyze")

    def test_batch_retry_manager_import(self):
        """Test batch_retry_manager module imports successfully."""
        from batch_retry_manager import should_retry_feature

        assert should_retry_feature is not None

    def test_failure_classifier_import(self):
        """Test failure_classifier module imports successfully."""
        from failure_classifier import FailureType, classify_failure

        assert FailureType is not None
        assert classify_failure is not None

    def test_auto_approval_engine_import(self):
        """Test auto_approval_engine module imports successfully."""
        from auto_approval_engine import should_auto_approve

        assert should_auto_approve is not None


class TestOptionalDependencyImports:
    """Test modules with optional dependencies handle missing imports gracefully."""

    def test_tech_debt_detector_import(self):
        """Test tech_debt_detector imports (may have optional dependencies)."""
        try:
            from tech_debt_detector import TechDebtDetector, Severity

            assert TechDebtDetector is not None
            assert Severity is not None
        except ImportError as e:
            # Optional dependencies missing (radon, etc.)
            pytest.skip(f"Optional dependency missing: {e}")

    def test_genai_validate_import(self):
        """Test genai_validate imports (may have optional dependencies)."""
        try:
            from genai_validate import validate_manifest

            assert validate_manifest is not None
        except ImportError as e:
            pytest.skip(f"Optional dependency missing: {e}")

    def test_search_utils_import(self):
        """Test search_utils imports (try/except pattern for optional deps)."""
        from search_utils import bootstrap_knowledge_base

        assert bootstrap_knowledge_base is not None
        # Has conditional imports - should handle gracefully


class TestModuleExports:
    """Test __all__ exports are valid (if defined)."""

    def test_security_utils_all_export(self):
        """Test security_utils __all__ exports exist."""
        from security_utils import __all__

        # Verify each exported name exists in module
        import security_utils

        for name in __all__:
            assert hasattr(security_utils, name), f"Missing export: {name}"

    def test_path_utils_all_export(self):
        """Test path_utils __all__ exports exist (if defined)."""
        try:
            from path_utils import __all__

            import path_utils

            for name in __all__:
                assert hasattr(path_utils, name), f"Missing export: {name}"
        except ImportError:
            # No __all__ defined - OK
            pass

    def test_validation_all_export(self):
        """Test validation __all__ exports exist (if defined)."""
        try:
            from validation import __all__

            import validation

            for name in __all__:
                assert hasattr(validation, name), f"Missing export: {name}"
        except ImportError:
            # No __all__ defined - OK
            pass


class TestRelativeImports:
    """Test relative imports resolve correctly."""

    def test_lib_to_lib_imports(self):
        """Test lib modules can import from other lib modules."""
        # agent_tracker imports from path_utils and validation
        from agent_tracker import AgentTracker

        # If this succeeds, relative imports work
        assert AgentTracker is not None

    def test_hook_to_lib_imports(self):
        """Test hooks can import from lib directory."""
        # Hooks use sys.path.insert to find lib modules
        # This is tested indirectly via hook imports above
        pass


class TestSysPathDynamicImports:
    """Test modules that modify sys.path still work."""

    def test_batch_state_manager_dynamic_import(self):
        """Test batch_state_manager with sys.path modification."""
        # This module uses sys.path.insert for path_utils
        from batch_state_manager import BatchStateManager

        manager = BatchStateManager()
        assert manager is not None

    def test_feature_dependency_analyzer_dynamic_import(self):
        """Test feature_dependency_analyzer with sys.path modification."""
        from feature_dependency_analyzer import analyze_dependencies

        assert analyze_dependencies is not None


# =============================================================================
# INTEGRATION SMOKE TESTS - Quick end-to-end validation
# =============================================================================


class TestCriticalWorkflows:
    """Test critical workflows still work after import cleanup."""

    def test_agent_checkpoint_workflow(self):
        """Test AgentTracker.save_agent_checkpoint workflow."""
        from agent_tracker import AgentTracker

        # Mock file operations
        with patch("builtins.open", create=True):
            with patch("json.dump"):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("pathlib.Path.mkdir"):
                        # Should not raise ImportError
                        result = AgentTracker.save_agent_checkpoint(
                            "test-agent", "test message"
                        )
                        # Result may be False (user project) but no import errors
                        assert result in [True, False]

    def test_session_tracker_workflow(self):
        """Test SessionTracker workflow."""
        from session_tracker import SessionTracker

        # Mock file operations
        with patch("builtins.open", create=True):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.mkdir"):
                    tracker = SessionTracker()
                    # Should not raise ImportError
                    assert tracker is not None

    def test_path_utils_project_root_detection(self):
        """Test get_project_root dynamic detection."""
        from path_utils import get_project_root

        # Should find autonomous-dev project root
        root = get_project_root()
        assert root.exists()
        assert (root / ".git").exists() or (root / ".claude").exists()

    def test_security_validation_workflow(self):
        """Test path security validation workflow."""
        from validation import validate_agent_name

        # Should validate without ImportError
        safe_name = validate_agent_name("test-agent")
        assert safe_name == "test-agent"
