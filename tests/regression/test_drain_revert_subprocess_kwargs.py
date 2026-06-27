"""Regression tests locking the Issue #1064 subprocess discipline in drain_revert.

Every subprocess.run call in drain_revert.py MUST pass explicit cwd= and env= kwargs.
This test uses AST parsing to verify the contract at the source level.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import List, Tuple

import pytest

_LIB = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
DRAIN_REVERT_PATH = _LIB / "drain_revert.py"


class SubprocessCallVisitor(ast.NodeVisitor):
    """AST visitor to find subprocess.run calls and analyze their kwargs."""
    
    def __init__(self):
        self.violations: List[Tuple[int, str]] = []
        self.subprocess_calls: List[Tuple[int, List[str]]] = []
    
    def visit_Call(self, node: ast.Call) -> None:
        """Check each function call for subprocess.run with proper kwargs."""
        # Check if this is subprocess.run
        if self._is_subprocess_run(node):
            lineno = node.lineno
            kwargs_names = [kw.arg for kw in node.keywords if kw.arg]
            
            self.subprocess_calls.append((lineno, kwargs_names))
            
            # Check required kwargs per Issue #1064
            missing = []
            if "cwd" not in kwargs_names:
                missing.append("cwd")
            if "env" not in kwargs_names:
                missing.append("env")
            if "timeout" not in kwargs_names:
                missing.append("timeout")
            if "check" not in kwargs_names:
                missing.append("check")
            if "capture_output" not in kwargs_names:
                missing.append("capture_output")
            if "text" not in kwargs_names:
                missing.append("text")
            
            if missing:
                self.violations.append((
                    lineno,
                    f"subprocess.run missing required kwargs: {', '.join(missing)}"
                ))
        
        self.generic_visit(node)
    
    def _is_subprocess_run(self, node: ast.Call) -> bool:
        """Check if a call node is subprocess.run."""
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "run":
                if isinstance(node.func.value, ast.Name):
                    return node.func.value.id == "subprocess"
        return False


class TestDrainRevertSubprocessKwargs:
    """Test that all subprocess.run calls follow Issue #1064 discipline."""
    
    def test_all_subprocess_calls_have_required_kwargs(self):
        """Every subprocess.run in drain_revert.py must have cwd, env, timeout, check, capture_output, text."""
        if not DRAIN_REVERT_PATH.exists():
            pytest.skip(f"drain_revert.py not found at {DRAIN_REVERT_PATH}")
        
        source = DRAIN_REVERT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(DRAIN_REVERT_PATH))
        
        visitor = SubprocessCallVisitor()
        visitor.visit(tree)
        
        if visitor.violations:
            violation_msgs = [f"Line {line}: {msg}" for line, msg in visitor.violations]
            pytest.fail(
                f"drain_revert.py violates Issue #1064 subprocess discipline:\n"
                + "\n".join(violation_msgs)
            )
        
        # Also verify we found at least some subprocess calls
        assert len(visitor.subprocess_calls) > 0, "No subprocess.run calls found in drain_revert.py"
    
    def test_no_shell_true(self):
        """Verify no subprocess call uses shell=True (security requirement)."""
        if not DRAIN_REVERT_PATH.exists():
            pytest.skip(f"drain_revert.py not found at {DRAIN_REVERT_PATH}")
        
        source = DRAIN_REVERT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(DRAIN_REVERT_PATH))
        
        class ShellTrueVisitor(ast.NodeVisitor):
            def __init__(self):
                self.shell_true_found = []
            
            def visit_Call(self, node: ast.Call) -> None:
                if self._is_subprocess_run(node):
                    for kw in node.keywords:
                        if kw.arg == "shell":
                            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                self.shell_true_found.append(node.lineno)
                self.generic_visit(node)
            
            def _is_subprocess_run(self, node: ast.Call) -> bool:
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "run":
                        if isinstance(node.func.value, ast.Name):
                            return node.func.value.id == "subprocess"
                return False
        
        visitor = ShellTrueVisitor()
        visitor.visit(tree)
        
        if visitor.shell_true_found:
            pytest.fail(
                f"drain_revert.py uses shell=True at lines: {visitor.shell_true_found}\n"
                "This violates security requirements (potential command injection)"
            )
    
    def test_sha_validation_pattern_exists(self):
        """Verify SHA_PATTERN regex is defined for CWE-88 hardening."""
        if not DRAIN_REVERT_PATH.exists():
            pytest.skip(f"drain_revert.py not found at {DRAIN_REVERT_PATH}")
        
        source = DRAIN_REVERT_PATH.read_text(encoding="utf-8")
        
        # Check for the SHA pattern definition
        assert "SHA_PATTERN" in source, "SHA_PATTERN not defined"
        assert r"^[0-9a-f]{40}$" in source, "SHA validation regex not strict enough"
    
    def test_all_public_functions_validate_sha(self):
        """Functions that accept SHA parameters must validate them."""
        if not DRAIN_REVERT_PATH.exists():
            pytest.skip(f"drain_revert.py not found at {DRAIN_REVERT_PATH}")
        
        source = DRAIN_REVERT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(DRAIN_REVERT_PATH))
        
        # Find functions that have 'sha' parameters
        class ShaParamVisitor(ast.NodeVisitor):
            def __init__(self):
                self.sha_functions = []
                self.validates_sha = []
            
            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                # Check if function has SHA parameters
                for arg in node.args.args:
                    if "sha" in arg.arg.lower():
                        self.sha_functions.append(node.name)
                        # Check if function body validates SHA
                        for child in ast.walk(node):
                            if isinstance(child, ast.Call):
                                if self._is_sha_validation(child):
                                    self.validates_sha.append(node.name)
                                    break
                        break
                self.generic_visit(node)
            
            def _is_sha_validation(self, node: ast.Call) -> bool:
                """Check if this is SHA_PATTERN.match() call."""
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "match":
                        if isinstance(node.func.value, ast.Name):
                            return node.func.value.id == "SHA_PATTERN"
                return False
        
        visitor = ShaParamVisitor()
        visitor.visit(tree)
        
        # Functions with SHA params that don't validate
        unvalidated = set(visitor.sha_functions) - set(visitor.validates_sha)
        
        # find_fix_commits, revert_drain_commit, reopen_issues_with_label should all validate
        expected_validators = {"find_fix_commits", "revert_drain_commit", "reopen_issues_with_label"}
        missing_validation = expected_validators - set(visitor.validates_sha)
        
        if missing_validation:
            pytest.fail(
                f"Functions not validating SHA input (CWE-88 vulnerability): {missing_validation}"
            )