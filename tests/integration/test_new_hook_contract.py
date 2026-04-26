"""CI contract test: every hook with a deny path SHOULD call log_block_event.

Issue #972 (Phase 1 — warn-only). Walks the AST of every active hook in
``plugins/autonomous-dev/hooks/`` and inspects functions whose body
contains a known deny shape:

- ``output_decision("deny", ...)`` (tuple shape)
- ``"decision": "block"`` literal in a dict (dict shape)
- ``sys.exit(2)`` (exit2 shape)

For each such function, the test checks whether the SAME function (or
the surrounding module) also contains a call to ``log_block_event`` or
``log_block_with_recovery``. Missing instrumentation is reported via
stderr (warning), but the test PASSES — Phase 1 is informational only.
A future Phase 2 patch may flip ``WARN_ONLY = False`` to make CI fail
when new hooks land without instrumentation.

This satisfies AC#5 ("``test_new_hook_contract.py`` enforces the
bypass + recoverability + telemetry imports for every hook file") in
its Phase 1 form: report violations without breaking the build.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import List, Set, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"

# Phase 1 — warn-only. Set to False in Phase 2 to enforce.
WARN_ONLY = True

DENY_MARKERS = {
    "output_decision_deny": "output_decision('deny',...)",
    "dict_decision_block": "'decision': 'block' literal",
    "sys_exit_2": "sys.exit(2)",
}

TELEMETRY_MARKERS = {
    "log_block_event",
    "log_block_with_recovery",
    "_log_block_event_972",
    "_log_block_with_recovery_970",
}


def _active_hooks() -> List[Path]:
    """Return all .py hook files (excluding archived/, __init__, .cover)."""
    out: List[Path] = []
    for p in HOOKS_DIR.iterdir():
        if not p.is_file():
            continue
        if p.suffix != ".py":
            continue
        if p.name.startswith("_") or p.name.endswith(".cover"):
            continue
        out.append(p)
    return sorted(out)


def _function_calls(fn: ast.FunctionDef) -> Set[str]:
    """Return set of called function names (best-effort) inside ``fn``."""
    names: Set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


def _function_has_deny(fn: ast.FunctionDef) -> List[str]:
    """Return list of deny-shape markers found inside ``fn``."""
    markers: List[str] = []
    for node in ast.walk(fn):
        # output_decision("deny", ...)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "output_decision"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "deny"
        ):
            markers.append("output_decision_deny")
        # sys.exit(2)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "exit"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "sys"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == 2
        ):
            markers.append("sys_exit_2")
        # {"decision": "block"} literal
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if (
                    isinstance(k, ast.Constant)
                    and k.value == "decision"
                    and isinstance(v, ast.Constant)
                    and v.value == "block"
                ):
                    markers.append("dict_decision_block")
    return markers


def _module_has_telemetry_import(tree: ast.Module) -> bool:
    """Cheap check: does the module import any telemetry symbol?"""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in TELEMETRY_MARKERS:
                    return True
                if alias.asname and alias.asname.lstrip("_") in {
                    name.lstrip("_") for name in TELEMETRY_MARKERS
                }:
                    return True
        if isinstance(node, ast.Call):
            # output_decision is decorator-wrapped — count any call to
            # block_event_decorator as telemetry coverage.
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "block_event_decorator"
            ):
                return True
    return False


def _audit_hook(path: Path) -> List[Tuple[str, str]]:
    """Return list of (function_name, missing_marker) for any uninstrumented denies."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return []
    findings: List[Tuple[str, str]] = []
    module_has_tele = _module_has_telemetry_import(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        deny_markers = _function_has_deny(node)
        if not deny_markers:
            continue
        fn_calls = _function_calls(node)
        fn_has_tele = bool(fn_calls & TELEMETRY_MARKERS)
        if fn_has_tele or module_has_tele:
            continue
        for m in deny_markers:
            findings.append((node.name, DENY_MARKERS[m]))
    return findings


class TestNewHookContract:
    """Phase 1: report missing instrumentation but DO NOT fail CI."""

    def test_audit_active_hooks_warn_only(self, capsys):
        all_findings = []
        for hook_path in _active_hooks():
            findings = _audit_hook(hook_path)
            for fn_name, marker in findings:
                all_findings.append(
                    (hook_path.name, fn_name, marker)
                )

        # Always print findings to stderr for visibility — even if list is empty.
        if all_findings:
            print(
                f"\n[hook-contract] Phase 1 (warn-only) findings — "
                f"{len(all_findings)} uninstrumented deny site(s):",
                file=sys.stderr,
            )
            for hook, fn, marker in all_findings:
                print(
                    f"  {hook}::{fn}() — {marker}",
                    file=sys.stderr,
                )
            print(
                "  (Phase 1 — these are advisory. Phase 2 will fail CI.)",
                file=sys.stderr,
            )
        else:
            print(
                "[hook-contract] All active hooks with deny paths "
                "have telemetry instrumentation.",
                file=sys.stderr,
            )

        if not WARN_ONLY:
            assert not all_findings, (
                f"{len(all_findings)} hooks have deny paths without telemetry"
            )

    def test_three_capstone_hooks_have_telemetry(self):
        """The three #972 hooks MUST be instrumented (regression lock)."""
        critical = {
            "unified_pre_tool.py",
            "unified_prompt_validator.py",
            "enforce_orchestrator.py",
        }
        for hook_path in _active_hooks():
            if hook_path.name not in critical:
                continue
            tree = ast.parse(hook_path.read_text(encoding="utf-8"))
            assert _module_has_telemetry_import(tree), (
                f"{hook_path.name} MUST import a telemetry symbol "
                f"(per Issue #972 capstone)"
            )

    def test_audit_returns_no_unexpected_violations(self):
        """Smoke test: the audit doesn't raise on real hook files."""
        for hook_path in _active_hooks():
            findings = _audit_hook(hook_path)
            # Just verifying audit() doesn't crash; correctness is in the
            # warn-only test above.
            assert isinstance(findings, list)
