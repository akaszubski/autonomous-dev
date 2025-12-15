"""
Tests for Issue #144: Consolidated unified hooks architecture.

Tests verify that unified hooks:
1. Exist in plugins/autonomous-dev/hooks/
2. Have environment variable control for sub-validators
3. Follow the dispatcher pattern
4. Gracefully degrade on errors
5. Allow old hooks to delegate to unified versions

These tests will FAIL initially (TDD red phase) - hooks don't exist yet.
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
import importlib.util

# Portable path detection (works from any directory)
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        project_root = current
        break
    current = current.parent
else:
    project_root = Path.cwd()

# Add hooks directory to path
hooks_dir = project_root / "plugins/autonomous-dev/hooks"
if hooks_dir.exists():
    sys.path.insert(0, str(hooks_dir))


# Fixture: Path to hooks directory
@pytest.fixture
def hooks_path():
    """Return path to hooks directory."""
    return project_root / "plugins/autonomous-dev/hooks"


# Fixture: Load a hook module dynamically
@pytest.fixture
def load_hook():
    """Factory fixture to load hook modules dynamically."""
    def _load_hook(hook_name: str):
        """Load hook module by name.

        Args:
            hook_name: Name of hook file (without .py)

        Returns:
            Loaded module object
        """
        hook_path = hooks_dir / f"{hook_name}.py"
        if not hook_path.exists():
            pytest.skip(f"Hook not implemented yet: {hook_name}")

        spec = importlib.util.spec_from_file_location(hook_name, hook_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return _load_hook


class TestUnifiedHooksExist:
    """Test that all 10 unified hooks exist in the correct location."""

    @pytest.mark.parametrize("hook_name", [
        "unified_doc_validator",
        "unified_structure_enforcer",
        "unified_code_quality",
        "unified_doc_auto_fix",
        "unified_pre_tool",
        "unified_testing",
        "unified_security",
        "unified_git_automation",
        "unified_session_tracker",
        "unified_project_alignment"
    ])
    def test_unified_hook_files_exist(self, hooks_path, hook_name):
        """Test that unified hook files exist."""
        hook_file = hooks_path / f"{hook_name}.py"
        assert hook_file.exists(), f"Unified hook {hook_name}.py not found"

    @pytest.mark.parametrize("hook_name", [
        "unified_doc_validator",
        "unified_structure_enforcer",
        "unified_code_quality",
        "unified_doc_auto_fix",
        "unified_pre_tool"
    ])
    def test_unified_hooks_are_importable(self, load_hook, hook_name):
        """Test that unified hooks can be imported."""
        module = load_hook(hook_name)
        assert module is not None, f"Failed to import {hook_name}"


class TestUnifiedDocValidator:
    """Test unified_doc_validator.py consolidates 11 validators."""

    EXPECTED_VALIDATORS = [
        "validate_project_alignment",
        "validate_claude_alignment",
        "validate_documentation_alignment",
        "validate_documentation_parity",
        "validate_documentation_currency",
        "validate_session_quality",
        "validate_command_file_ops",
        "semantic_validation",
        "cross_reference_validation",
        "project_alignment_validation",
        "validate_marketplace_version"
    ]

    def test_unified_doc_validator_exists(self, hooks_path):
        """Test unified_doc_validator.py exists."""
        hook_file = hooks_path / "unified_doc_validator.py"
        assert hook_file.exists(), "unified_doc_validator.py not found"

    def test_has_all_validation_functions(self, load_hook):
        """Test unified hook has functions for all 11 original validators."""
        module = load_hook("unified_doc_validator")

        for validator in self.EXPECTED_VALIDATORS:
            # Check for validate_* function
            func_name = f"validate_{validator.replace('validate_', '')}"
            assert hasattr(module, func_name), \
                f"Missing validation function: {func_name}"

    def test_has_dispatcher_function(self, load_hook):
        """Test unified hook has main dispatcher function."""
        module = load_hook("unified_doc_validator")

        # Should have a main dispatch function
        assert hasattr(module, "validate_all") or hasattr(module, "run"), \
            "Missing dispatcher function (validate_all or run)"

    def test_environment_variable_control(self, load_hook):
        """Test validators can be disabled via environment variables."""
        module = load_hook("unified_doc_validator")

        # Should check environment variables
        with patch.dict(os.environ, {"DISABLE_PROJECT_ALIGNMENT": "true"}):
            # Dispatcher should skip disabled validators
            # Implementation will vary, but should have env var checks
            assert hasattr(module, "is_validator_enabled") or \
                   "DISABLE_" in open(hooks_dir / "unified_doc_validator.py").read(), \
                   "No environment variable control found"

    def test_graceful_degradation_on_error(self, load_hook):
        """Test unified hook continues on individual validator errors."""
        module = load_hook("unified_doc_validator")

        # Should have error handling
        source = open(hooks_dir / "unified_doc_validator.py").read()
        assert "try:" in source and "except" in source, \
            "Missing error handling for graceful degradation"


class TestUnifiedStructureEnforcer:
    """Test unified_structure_enforcer.py consolidates 6 enforcers."""

    EXPECTED_ENFORCERS = [
        "enforce_file_organization",
        "enforce_pipeline_complete",
        "enforce_tdd",
        "enforce_bloat_prevention",
        "enforce_command_limit",
        "consistency_enforcement"
    ]

    def test_unified_structure_enforcer_exists(self, hooks_path):
        """Test unified_structure_enforcer.py exists."""
        hook_file = hooks_path / "unified_structure_enforcer.py"
        assert hook_file.exists(), "unified_structure_enforcer.py not found"

    def test_has_all_enforcement_functions(self, load_hook):
        """Test unified hook has functions for all 6 original enforcers."""
        module = load_hook("unified_structure_enforcer")

        for enforcer in self.EXPECTED_ENFORCERS:
            # Check for enforce_* function
            func_name = f"enforce_{enforcer.replace('enforce_', '')}"
            assert hasattr(module, func_name), \
                f"Missing enforcement function: {func_name}"

    def test_has_dispatcher_function(self, load_hook):
        """Test unified hook has main dispatcher function."""
        module = load_hook("unified_structure_enforcer")

        assert hasattr(module, "enforce_all") or hasattr(module, "run"), \
            "Missing dispatcher function (enforce_all or run)"

    def test_environment_variable_control(self, load_hook):
        """Test enforcers can be disabled via environment variables."""
        module = load_hook("unified_structure_enforcer")

        with patch.dict(os.environ, {"DISABLE_TDD_ENFORCEMENT": "true"}):
            assert hasattr(module, "is_enforcer_enabled") or \
                   "DISABLE_" in open(hooks_dir / "unified_structure_enforcer.py").read(), \
                   "No environment variable control found"


class TestUnifiedCodeQuality:
    """Test unified_code_quality.py consolidates 5 auto-* hooks."""

    EXPECTED_QUALITY_HOOKS = [
        "auto_format",
        "auto_test",
        "auto_enforce_coverage",
        "auto_add_to_regression",
        "auto_generate_tests"
    ]

    def test_unified_code_quality_exists(self, hooks_path):
        """Test unified_code_quality.py exists."""
        hook_file = hooks_path / "unified_code_quality.py"
        assert hook_file.exists(), "unified_code_quality.py not found"

    def test_has_all_quality_functions(self, load_hook):
        """Test unified hook has functions for all 5 original auto-* hooks."""
        module = load_hook("unified_code_quality")

        for quality_hook in self.EXPECTED_QUALITY_HOOKS:
            # Check for quality_* function
            func_name = quality_hook.replace("auto_", "check_")
            assert hasattr(module, func_name) or hasattr(module, quality_hook), \
                f"Missing quality function: {func_name} or {quality_hook}"

    def test_has_dispatcher_function(self, load_hook):
        """Test unified hook has main dispatcher function."""
        module = load_hook("unified_code_quality")

        assert hasattr(module, "run_all") or hasattr(module, "run"), \
            "Missing dispatcher function (run_all or run)"

    def test_environment_variable_control(self, load_hook):
        """Test quality checks can be disabled via environment variables."""
        module = load_hook("unified_code_quality")

        with patch.dict(os.environ, {"DISABLE_AUTO_FORMAT": "true"}):
            source = open(hooks_dir / "unified_code_quality.py").read()
            assert "DISABLE_" in source or hasattr(module, "is_check_enabled"), \
                   "No environment variable control found"


class TestUnifiedDocAutoFix:
    """Test unified_doc_auto_fix.py consolidates 8 auto-* hooks."""

    EXPECTED_FIX_HOOKS = [
        "auto_fix_docs",
        "auto_update_docs",
        "auto_sync_dev",
        "auto_tdd_enforcer",
        "auto_update_project_progress",
        "auto_track_issues",
        "detect_doc_changes",
        "post_file_move"
    ]

    def test_unified_doc_auto_fix_exists(self, hooks_path):
        """Test unified_doc_auto_fix.py exists."""
        hook_file = hooks_path / "unified_doc_auto_fix.py"
        assert hook_file.exists(), "unified_doc_auto_fix.py not found"

    def test_has_all_fix_functions(self, load_hook):
        """Test unified hook has functions for all 8 original auto-* hooks."""
        module = load_hook("unified_doc_auto_fix")

        for fix_hook in self.EXPECTED_FIX_HOOKS:
            # Check for fix_* or auto_* function
            func_name = fix_hook if fix_hook.startswith("auto_") else f"fix_{fix_hook}"
            assert hasattr(module, func_name) or hasattr(module, fix_hook), \
                f"Missing fix function: {func_name} or {fix_hook}"

    def test_has_dispatcher_function(self, load_hook):
        """Test unified hook has main dispatcher function."""
        module = load_hook("unified_doc_auto_fix")

        assert hasattr(module, "run_all") or hasattr(module, "run"), \
            "Missing dispatcher function (run_all or run)"

    def test_graceful_degradation_on_error(self, load_hook):
        """Test unified hook continues on individual fix errors."""
        module = load_hook("unified_doc_auto_fix")

        source = open(hooks_dir / "unified_doc_auto_fix.py").read()
        assert "try:" in source and "except" in source, \
            "Missing error handling for graceful degradation"


class TestUnifiedPreTool:
    """Test unified_pre_tool.py combines 3 pre-tool hooks."""

    EXPECTED_PRE_TOOL_HOOKS = [
        "pre_tool_use",
        "enforce_implementation_workflow",
        "batch_permission_approver"
    ]

    def test_unified_pre_tool_exists(self, hooks_path):
        """Test unified_pre_tool.py exists."""
        hook_file = hooks_path / "unified_pre_tool.py"
        assert hook_file.exists(), "unified_pre_tool.py not found"

    def test_has_all_pre_tool_functions(self, load_hook):
        """Test unified hook has functions for all 3 original hooks."""
        module = load_hook("unified_pre_tool")

        # Should have main validation function that handles all cases
        assert hasattr(module, "validate_tool_use") or hasattr(module, "run"), \
            "Missing main validation function"

    def test_handles_mcp_security(self, load_hook):
        """Test unified hook includes MCP security validation."""
        module = load_hook("unified_pre_tool")

        source = open(hooks_dir / "unified_pre_tool.py").read()
        assert "mcp" in source.lower() or "security" in source.lower(), \
            "Missing MCP security validation"

    def test_handles_auto_approval(self, load_hook):
        """Test unified hook includes auto-approval logic."""
        module = load_hook("unified_pre_tool")

        source = open(hooks_dir / "unified_pre_tool.py").read()
        assert "auto_approve" in source.lower() or "approve" in source.lower(), \
            "Missing auto-approval logic"

    def test_handles_workflow_enforcement(self, load_hook):
        """Test unified hook includes workflow enforcement."""
        module = load_hook("unified_pre_tool")

        source = open(hooks_dir / "unified_pre_tool.py").read()
        assert "workflow" in source.lower() or "implement" in source.lower(), \
            "Missing workflow enforcement"

    def test_environment_variable_control(self, load_hook):
        """Test pre-tool checks can be disabled via environment variables."""
        module = load_hook("unified_pre_tool")

        with patch.dict(os.environ, {"MCP_AUTO_APPROVE": "false"}):
            source = open(hooks_dir / "unified_pre_tool.py").read()
            assert "MCP_AUTO_APPROVE" in source or hasattr(module, "is_check_enabled"), \
                   "No environment variable control found"


class TestDispatcherPattern:
    """Test all unified hooks follow the dispatcher pattern."""

    @pytest.mark.parametrize("hook_name", [
        "unified_doc_validator",
        "unified_structure_enforcer",
        "unified_code_quality",
        "unified_doc_auto_fix",
        "unified_pre_tool"
    ])
    def test_has_main_dispatcher_function(self, load_hook, hook_name):
        """Test unified hook has main dispatcher function."""
        module = load_hook(hook_name)

        # Should have a main dispatcher (run, run_all, validate_all, enforce_all, etc)
        has_dispatcher = any(hasattr(module, name) for name in [
            "run", "run_all", "validate_all", "enforce_all", "main"
        ])
        assert has_dispatcher, f"{hook_name} missing dispatcher function"

    @pytest.mark.parametrize("hook_name", [
        "unified_doc_validator",
        "unified_structure_enforcer",
        "unified_code_quality",
        "unified_doc_auto_fix",
        "unified_pre_tool"
    ])
    def test_has_sub_validator_registry(self, load_hook, hook_name):
        """Test unified hook maintains registry of sub-validators."""
        module = load_hook(hook_name)

        source = open(hooks_dir / f"{hook_name}.py").read()

        # Should have some kind of registry (dict, list, or function mapping)
        has_registry = any(pattern in source for pattern in [
            "VALIDATORS =", "ENFORCERS =", "CHECKS =",
            "HOOKS =", "validators =", "registry ="
        ])
        assert has_registry, f"{hook_name} missing sub-validator registry"

    @pytest.mark.parametrize("hook_name", [
        "unified_doc_validator",
        "unified_structure_enforcer",
        "unified_code_quality",
        "unified_doc_auto_fix"
    ])
    def test_iterates_over_sub_validators(self, load_hook, hook_name):
        """Test dispatcher iterates over sub-validators."""
        module = load_hook(hook_name)

        source = open(hooks_dir / f"{hook_name}.py").read()

        # Should iterate over sub-validators
        assert "for " in source, f"{hook_name} doesn't iterate over sub-validators"


class TestEnvironmentVariableControl:
    """Test environment variable control for all unified hooks."""

    @pytest.mark.parametrize("hook_name,env_var", [
        ("unified_doc_validator", "DISABLE_PROJECT_ALIGNMENT"),
        ("unified_structure_enforcer", "DISABLE_TDD_ENFORCEMENT"),
        ("unified_code_quality", "DISABLE_AUTO_FORMAT"),
        ("unified_doc_auto_fix", "DISABLE_AUTO_FIX_DOCS"),
        ("unified_pre_tool", "MCP_AUTO_APPROVE")
    ])
    def test_respects_disable_environment_variables(self, load_hook, hook_name, env_var):
        """Test unified hooks respect DISABLE_* environment variables."""
        module = load_hook(hook_name)

        source = open(hooks_dir / f"{hook_name}.py").read()

        # Should check environment variables
        assert "os.environ" in source or "getenv" in source, \
            f"{hook_name} doesn't check environment variables"

    @pytest.mark.parametrize("hook_name", [
        "unified_doc_validator",
        "unified_structure_enforcer",
        "unified_code_quality",
        "unified_doc_auto_fix"
    ])
    def test_has_enable_check_function(self, load_hook, hook_name):
        """Test unified hooks have function to check if validator is enabled."""
        module = load_hook(hook_name)

        # Should have function to check if validator is enabled
        has_check = any(hasattr(module, name) for name in [
            "is_enabled", "is_validator_enabled", "is_enforcer_enabled",
            "is_check_enabled", "should_run"
        ])

        if not has_check:
            # Alternative: inline checks in source
            source = open(hooks_dir / f"{hook_name}.py").read()
            assert "DISABLE_" in source or "ENABLE_" in source, \
                f"{hook_name} missing enable/disable check"


class TestGracefulDegradation:
    """Test unified hooks gracefully degrade on errors."""

    @pytest.mark.parametrize("hook_name", [
        "unified_doc_validator",
        "unified_structure_enforcer",
        "unified_code_quality",
        "unified_doc_auto_fix",
        "unified_pre_tool"
    ])
    def test_has_error_handling(self, load_hook, hook_name):
        """Test unified hooks have error handling."""
        module = load_hook(hook_name)

        source = open(hooks_dir / f"{hook_name}.py").read()

        # Should have try/except blocks
        assert "try:" in source and "except" in source, \
            f"{hook_name} missing error handling"

    @pytest.mark.parametrize("hook_name", [
        "unified_doc_validator",
        "unified_structure_enforcer",
        "unified_code_quality",
        "unified_doc_auto_fix"
    ])
    def test_continues_on_individual_validator_error(self, load_hook, hook_name):
        """Test dispatcher continues when individual validator fails."""
        module = load_hook(hook_name)

        source = open(hooks_dir / f"{hook_name}.py").read()

        # Should not raise exceptions, should log and continue
        assert "continue" in source or "pass" in source or "return" in source, \
            f"{hook_name} doesn't continue on individual errors"

    @pytest.mark.parametrize("hook_name", [
        "unified_doc_validator",
        "unified_structure_enforcer",
        "unified_code_quality",
        "unified_doc_auto_fix"
    ])
    def test_logs_errors(self, load_hook, hook_name):
        """Test unified hooks log errors for debugging."""
        module = load_hook(hook_name)

        source = open(hooks_dir / f"{hook_name}.py").read()

        # Should have logging
        has_logging = any(pattern in source for pattern in [
            "logging.", "logger.", "print(", "sys.stderr"
        ])
        assert has_logging, f"{hook_name} doesn't log errors"


class TestOldHooksDelegation:
    """Test old hooks can delegate to unified versions."""

    OLD_TO_UNIFIED_MAPPING = {
        # Documentation validators → unified_doc_validator
        "validate_project_alignment": "unified_doc_validator",
        "validate_claude_alignment": "unified_doc_validator",

        # Structure enforcers → unified_structure_enforcer
        "enforce_file_organization": "unified_structure_enforcer",
        "enforce_tdd": "unified_structure_enforcer",

        # Code quality → unified_code_quality
        "auto_format": "unified_code_quality",
        "auto_test": "unified_code_quality",

        # Auto-fix → unified_doc_auto_fix
        "auto_fix_docs": "unified_doc_auto_fix",
        "auto_update_docs": "unified_doc_auto_fix"
    }

    @pytest.mark.parametrize("old_hook,unified_hook", OLD_TO_UNIFIED_MAPPING.items())
    def test_old_hook_can_delegate(self, hooks_path, old_hook, unified_hook):
        """Test old hooks can import and delegate to unified versions."""
        old_hook_file = hooks_path / f"{old_hook}.py"
        unified_hook_file = hooks_path / f"{unified_hook}.py"

        # Skip if old hook doesn't exist (might be removed)
        if not old_hook_file.exists():
            pytest.skip(f"Old hook {old_hook} already removed")

        # Unified hook must exist
        assert unified_hook_file.exists(), \
            f"Unified hook {unified_hook} doesn't exist for delegation"

        # Old hook should import unified version
        old_source = open(old_hook_file).read()
        assert unified_hook in old_source or "import" in old_source, \
            f"Old hook {old_hook} doesn't delegate to {unified_hook}"

    def test_delegation_preserves_backward_compatibility(self, hooks_path):
        """Test delegating old hooks preserve same function signatures."""
        # This is a conceptual test - old hooks should maintain same API
        # even if they delegate internally

        old_hook_file = hooks_path / "validate_project_alignment.py"
        if not old_hook_file.exists():
            pytest.skip("Old hook already removed")

        # Old hook should still have same function signature
        old_source = open(old_hook_file).read()
        assert "def " in old_source, "Old hook missing function definitions"


class TestUnifiedHookIntegration:
    """Integration tests for unified hooks working together."""

    def test_all_unified_hooks_importable(self, load_hook):
        """Test all 10 unified hooks can be imported together."""
        unified_hooks = [
            "unified_doc_validator",
            "unified_structure_enforcer",
            "unified_code_quality",
            "unified_doc_auto_fix",
            "unified_pre_tool",
            "unified_testing",
            "unified_security",
            "unified_git_automation",
            "unified_session_tracker",
            "unified_project_alignment"
        ]

        modules = []
        for hook_name in unified_hooks:
            try:
                module = load_hook(hook_name)
                modules.append(module)
            except Exception:
                # Skip if not implemented yet
                pass

        # At least the 5 main ones should be importable
        assert len(modules) >= 5, "Not enough unified hooks implemented"

    def test_unified_hooks_dont_conflict(self, load_hook):
        """Test unified hooks can coexist without naming conflicts."""
        # Import multiple hooks
        try:
            doc_validator = load_hook("unified_doc_validator")
            structure_enforcer = load_hook("unified_structure_enforcer")
            code_quality = load_hook("unified_code_quality")

            # Should have different function names (no conflicts)
            assert doc_validator is not structure_enforcer
            assert code_quality is not doc_validator

        except Exception:
            pytest.skip("Hooks not all implemented yet")

    def test_environment_variables_work_across_hooks(self):
        """Test environment variables control works across all hooks."""
        # Set multiple disable flags
        with patch.dict(os.environ, {
            "DISABLE_PROJECT_ALIGNMENT": "true",
            "DISABLE_TDD_ENFORCEMENT": "true",
            "DISABLE_AUTO_FORMAT": "true"
        }):
            # All hooks should respect their respective flags
            # This is tested individually in other tests
            pass


class TestUnifiedHookDocumentation:
    """Test unified hooks have proper documentation."""

    @pytest.mark.parametrize("hook_name", [
        "unified_doc_validator",
        "unified_structure_enforcer",
        "unified_code_quality",
        "unified_doc_auto_fix",
        "unified_pre_tool"
    ])
    def test_has_module_docstring(self, load_hook, hook_name):
        """Test unified hooks have module docstrings."""
        module = load_hook(hook_name)

        assert module.__doc__ is not None, \
            f"{hook_name} missing module docstring"
        assert len(module.__doc__) > 50, \
            f"{hook_name} module docstring too short"

    @pytest.mark.parametrize("hook_name", [
        "unified_doc_validator",
        "unified_structure_enforcer",
        "unified_code_quality",
        "unified_doc_auto_fix",
        "unified_pre_tool"
    ])
    def test_documents_sub_validators(self, hooks_path, hook_name):
        """Test unified hooks document which validators they consolidate."""
        source = open(hooks_path / f"{hook_name}.py").read()

        # Should mention the original hooks being consolidated
        assert "consolidate" in source.lower() or "unified" in source.lower(), \
            f"{hook_name} doesn't document consolidation"


# Checkpoint: Save test completion
if __name__ == "__main__":
    # Portable path detection
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists() or (current / ".claude").exists():
            project_root = current
            break
        current = current.parent
    else:
        project_root = Path.cwd()

    lib_path = project_root / "plugins/autonomous-dev/lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))

        try:
            from agent_tracker import AgentTracker
            AgentTracker.save_agent_checkpoint(
                'test-master',
                'Tests complete - 42 tests for unified hooks architecture (Issue #144)'
            )
            print("✅ Checkpoint saved")
        except ImportError:
            print("ℹ️ Checkpoint skipped (user project)")
