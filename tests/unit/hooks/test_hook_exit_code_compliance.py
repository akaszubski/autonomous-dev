#!/usr/bin/env python3
"""
Compliance tests for standardized exit codes across all hooks.

Tests that all hooks in plugins/autonomous-dev/hooks/ follow exit code standards:
1. Import hook_exit_codes constants (no hardcoded 0/1/2)
2. Respect lifecycle constraints (PreToolUse/SubagentStop always exit 0)
3. Use symbolic constants instead of magic numbers

TDD Mode: These tests are written BEFORE implementation.
All tests should FAIL initially (hooks haven't been migrated yet).

Test Strategy:
- Static analysis of all hook files
- Check for imports of hook_exit_codes
- Detect hardcoded sys.exit(0/1/2) without constants
- Validate lifecycle-specific constraints
- Check for proper constant usage

Exit Code Standards:
- EXIT_SUCCESS (0): Success, continue workflow
- EXIT_WARNING (1): Warning, continue workflow
- EXIT_BLOCK (2): Error, block workflow

Lifecycle Constraints:
- PreToolUse: MUST always exit 0 (cannot block tool execution)
- SubagentStop: MUST always exit 0 (cannot block agent completion)
- PreSubagent: CAN exit 2 to block agent spawn

Coverage Target: 100% hook compliance

Date: 2026-01-01
Feature: Standardized exit codes across all hooks
Agent: test-master
Phase: TDD Red (tests written BEFORE migration)
Status: RED (all tests failing - hooks not migrated yet)
"""

import ast
import re
import sys
import pytest
from pathlib import Path
from typing import List, Tuple, Set

# Add lib directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "lib"
    ),
)

# Import will fail initially - module doesn't exist yet (TDD!)
try:
    from hook_exit_codes import (
        EXIT_SUCCESS,
        EXIT_WARNING,
        EXIT_BLOCK,
        LIFECYCLE_CONSTRAINTS,
    )
    IMPORT_SUCCESSFUL = True
except ImportError as e:
    IMPORT_SUCCESSFUL = False
    IMPORT_ERROR = str(e)

# Hooks directory
HOOKS_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "hooks"


def get_all_hook_files() -> List[Path]:
    """Get all Python hook files."""
    if not HOOKS_DIR.exists():
        return []
    return [f for f in HOOKS_DIR.glob("*.py") if f.name != "__init__.py"]


def parse_hook_file(hook_file: Path) -> ast.Module:
    """Parse hook file into AST."""
    try:
        with open(hook_file, "r") as f:
            return ast.parse(f.read(), filename=str(hook_file))
    except Exception as e:
        pytest.fail(f"Failed to parse {hook_file.name}: {e}")


def get_imports(tree: ast.Module) -> Set[str]:
    """Extract all imported symbols from AST."""
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "hook_exit_codes":
                for alias in node.names:
                    imports.add(alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if "hook_exit_codes" in alias.name:
                    imports.add(alias.name)
    return imports


def find_sys_exit_calls(tree: ast.Module) -> List[Tuple[int, int]]:
    """Find all sys.exit() calls and their arguments.

    Returns list of (line_number, exit_code) tuples.
    """
    exits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Check for sys.exit() or exit()
            if isinstance(node.func, ast.Attribute):
                if (isinstance(node.func.value, ast.Name) and
                    node.func.value.id == "sys" and
                    node.func.attr == "exit"):
                    # Found sys.exit()
                    if node.args and isinstance(node.args[0], ast.Num):
                        exits.append((node.lineno, node.args[0].n))
                    elif node.args and isinstance(node.args[0], ast.Constant):
                        exits.append((node.lineno, node.args[0].value))
    return exits


def find_hardcoded_returns(tree: ast.Module) -> List[Tuple[int, int]]:
    """Find return statements with hardcoded 0/1/2 values.

    Returns list of (line_number, return_value) tuples.
    """
    returns = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Return):
            if node.value:
                if isinstance(node.value, ast.Num):
                    val = node.value.n
                    if val in (0, 1, 2):
                        returns.append((node.lineno, val))
                elif isinstance(node.value, ast.Constant):
                    val = node.value.value
                    if val in (0, 1, 2):
                        returns.append((node.lineno, val))
    return returns


def get_hook_lifecycle(hook_file: Path) -> str:
    """Determine hook lifecycle from filename or content.

    Returns one of: PreToolUse, SubagentStop, PreSubagent, Unknown
    """
    # Read first 100 lines to find lifecycle comment
    try:
        with open(hook_file, "r") as f:
            lines = [f.readline() for _ in range(100)]
            content = "".join(lines)

            # Check for lifecycle marker in comments
            if "PreToolUse" in content or "pre_tool_use" in hook_file.name:
                return "PreToolUse"
            elif "SubagentStop" in content or "subagentstop" in hook_file.name.lower():
                return "SubagentStop"
            elif "PreSubagent" in content or "presubagent" in hook_file.name.lower():
                return "PreSubagent"

            # Default based on common patterns
            if "auto_git" in hook_file.name or "log_agent" in hook_file.name:
                return "SubagentStop"
            elif "unified_pre_tool" in hook_file.name or "pre_tool" in hook_file.name:
                return "PreToolUse"

    except Exception:
        pass

    return "Unknown"


class TestHookExitCodeImports:
    """Test that all hooks import exit code constants."""

    @pytest.mark.parametrize("hook_file", get_all_hook_files())
    def test_hook_imports_exit_codes(self, hook_file):
        """Test that hook imports hook_exit_codes constants."""
        tree = parse_hook_file(hook_file)
        imports = get_imports(tree)

        # Check if hook imports any exit code constants
        expected_imports = {"EXIT_SUCCESS", "EXIT_WARNING", "EXIT_BLOCK"}
        has_import = bool(imports & expected_imports)

        assert has_import, \
            f"{hook_file.name} should import at least one exit code constant from hook_exit_codes"

    @pytest.mark.parametrize("hook_file", get_all_hook_files())
    def test_hook_no_hardcoded_sys_exit(self, hook_file):
        """Test that hook doesn't use hardcoded sys.exit(0/1/2)."""
        tree = parse_hook_file(hook_file)
        exits = find_sys_exit_calls(tree)

        # Filter for hardcoded numeric exits
        hardcoded = [(line, code) for line, code in exits if code in (0, 1, 2)]

        if hardcoded:
            violations = "\n".join([f"  Line {line}: sys.exit({code})" for line, code in hardcoded])
            pytest.fail(
                f"{hook_file.name} uses hardcoded sys.exit() instead of constants:\n{violations}"
            )

    @pytest.mark.parametrize("hook_file", get_all_hook_files())
    def test_hook_no_hardcoded_returns(self, hook_file):
        """Test that hook doesn't return hardcoded 0/1/2 values."""
        tree = parse_hook_file(hook_file)
        returns = find_hardcoded_returns(tree)

        if returns:
            violations = "\n".join([f"  Line {line}: return {val}" for line, val in returns])
            pytest.fail(
                f"{hook_file.name} returns hardcoded exit codes instead of constants:\n{violations}"
            )


class TestLifecycleConstraints:
    """Test that hooks respect lifecycle-specific exit code constraints."""

    @pytest.mark.parametrize("hook_file", get_all_hook_files())
    def test_pretooluse_hooks_only_exit_success(self, hook_file):
        """Test that PreToolUse hooks only exit with EXIT_SUCCESS."""
        lifecycle = get_hook_lifecycle(hook_file)
        if lifecycle != "PreToolUse":
            pytest.skip(f"{hook_file.name} is not a PreToolUse hook")

        # Read hook file to check for non-zero exits
        with open(hook_file, "r") as f:
            content = f.read()

        # Check for EXIT_BLOCK or EXIT_WARNING usage
        if "EXIT_BLOCK" in content:
            pytest.fail(f"{hook_file.name} (PreToolUse) uses EXIT_BLOCK - must only exit 0")
        if "EXIT_WARNING" in content:
            pytest.fail(f"{hook_file.name} (PreToolUse) uses EXIT_WARNING - must only exit 0")

    @pytest.mark.parametrize("hook_file", get_all_hook_files())
    def test_subagentstop_hooks_only_exit_success(self, hook_file):
        """Test that SubagentStop hooks only exit with EXIT_SUCCESS."""
        lifecycle = get_hook_lifecycle(hook_file)
        if lifecycle != "SubagentStop":
            pytest.skip(f"{hook_file.name} is not a SubagentStop hook")

        # Read hook file to check for non-zero exits
        with open(hook_file, "r") as f:
            content = f.read()

        # Check for EXIT_BLOCK or EXIT_WARNING usage
        if "EXIT_BLOCK" in content:
            pytest.fail(f"{hook_file.name} (SubagentStop) uses EXIT_BLOCK - must only exit 0")
        if "EXIT_WARNING" in content:
            pytest.fail(f"{hook_file.name} (SubagentStop) uses EXIT_WARNING - must only exit 0")

    @pytest.mark.parametrize("hook_file", get_all_hook_files())
    def test_hook_has_lifecycle_comment(self, hook_file):
        """Test that hook has lifecycle documentation in header."""
        with open(hook_file, "r") as f:
            # Read first 50 lines (header)
            header = "".join([f.readline() for _ in range(50)])

        # Should have lifecycle marker in comments
        lifecycle_markers = ["PreToolUse", "SubagentStop", "PreSubagent"]
        has_marker = any(marker in header for marker in lifecycle_markers)

        assert has_marker, \
            f"{hook_file.name} should document its lifecycle in header comments"


class TestExitCodeConsistency:
    """Test consistent usage of exit codes across hooks."""

    def test_all_hooks_exist(self):
        """Test that hooks directory exists and has Python files."""
        assert HOOKS_DIR.exists(), f"Hooks directory not found: {HOOKS_DIR}"
        hook_files = get_all_hook_files()
        assert len(hook_files) > 0, "No hook files found"

    def test_hook_exit_codes_module_available(self):
        """Test that hook_exit_codes module is importable."""
        assert IMPORT_SUCCESSFUL, \
            f"hook_exit_codes module should be importable: {IMPORT_ERROR}"

    @pytest.mark.parametrize("hook_file", get_all_hook_files())
    def test_hook_imports_from_correct_location(self, hook_file):
        """Test that hook imports from hook_exit_codes (not local definition)."""
        with open(hook_file, "r") as f:
            content = f.read()

        # Check for local constant definitions (anti-pattern)
        local_definitions = [
            "EXIT_SUCCESS = 0",
            "EXIT_WARNING = 1",
            "EXIT_BLOCK = 2",
        ]

        for defn in local_definitions:
            assert defn not in content, \
                f"{hook_file.name} defines {defn} locally - should import from hook_exit_codes"


class TestSpecificHookMigrations:
    """Test specific hooks that need migration."""

    def test_auto_tdd_enforcer_migrated(self):
        """Test that auto_tdd_enforcer.py has been migrated to use constants."""
        hook_file = HOOKS_DIR / "auto_tdd_enforcer.py"
        if not hook_file.exists():
            pytest.skip("auto_tdd_enforcer.py not found")

        tree = parse_hook_file(hook_file)
        imports = get_imports(tree)

        # Should import EXIT_BLOCK and EXIT_SUCCESS
        assert "EXIT_BLOCK" in imports, \
            "auto_tdd_enforcer should import EXIT_BLOCK"
        assert "EXIT_SUCCESS" in imports, \
            "auto_tdd_enforcer should import EXIT_SUCCESS"

    def test_unified_pre_tool_migrated(self):
        """Test that unified_pre_tool.py has been migrated."""
        hook_file = HOOKS_DIR / "unified_pre_tool.py"
        if not hook_file.exists():
            pytest.skip("unified_pre_tool.py not found")

        tree = parse_hook_file(hook_file)
        imports = get_imports(tree)

        # PreToolUse should only import EXIT_SUCCESS
        assert "EXIT_SUCCESS" in imports, \
            "unified_pre_tool should import EXIT_SUCCESS"

    def test_unified_git_automation_migrated(self):
        """Test that unified_git_automation.py has been migrated."""
        hook_file = HOOKS_DIR / "unified_git_automation.py"
        if not hook_file.exists():
            pytest.skip("unified_git_automation.py not found")

        tree = parse_hook_file(hook_file)
        imports = get_imports(tree)

        # SubagentStop should only import EXIT_SUCCESS
        assert "EXIT_SUCCESS" in imports, \
            "unified_git_automation should import EXIT_SUCCESS"


class TestMigrationProgress:
    """Track migration progress across all hooks."""

    def test_migration_coverage(self):
        """Test what percentage of hooks have been migrated."""
        hook_files = get_all_hook_files()
        migrated = 0
        not_migrated = []

        for hook_file in hook_files:
            tree = parse_hook_file(hook_file)
            imports = get_imports(tree)

            if imports:  # Has any hook_exit_codes imports
                migrated += 1
            else:
                not_migrated.append(hook_file.name)

        total = len(hook_files)
        percentage = (migrated / total * 100) if total > 0 else 0

        # Should eventually reach 100%
        assert percentage == 100, \
            f"Only {migrated}/{total} hooks migrated ({percentage:.1f}%). " \
            f"Not migrated: {', '.join(not_migrated)}"


# Checkpoint tracking integration
if __name__ == "__main__":
    from pathlib import Path
    import sys

    # Portable path detection
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists() or (current / ".claude").exists():
            project_root = current
            break
        current = current.parent
    else:
        project_root = Path.cwd()

    # Add lib to path for imports
    lib_path = project_root / "plugins/autonomous-dev/lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))

        try:
            from agent_tracker import AgentTracker
            AgentTracker.save_agent_checkpoint(
                'test-master',
                'Test file 2/3 created: test_hook_exit_code_compliance.py (12 tests for all hooks)'
            )
            print("✅ Checkpoint saved")
        except ImportError:
            print("ℹ️ Checkpoint skipped (user project)")
