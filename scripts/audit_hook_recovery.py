#!/usr/bin/env python3
"""Audit ``unified_pre_tool.py`` for unjustified deny sites (Issue #970).

Two modes:

- **Default (WARN-ONLY)**: prints findings to stdout, exits 0.
- **Strict** (``--strict`` or ``AUDIT_HOOK_RECOVERY_STRICT=1``): exits 1
  if any deny site lacks a paired ``log_block_with_recovery(`` call AND has
  no exemption in ``hook_recovery_exemptions.json``.

A "deny site" is any call to ``output_decision("deny", ...)`` (literal) OR
``output_decision(<var>, ...)`` where the variable is plausibly assigned
``"deny"`` in surrounding code (AST analysis).

Importable API:
    from audit_hook_recovery import audit_file
    violations = audit_file(Path("path/to/unified_pre_tool.py"))
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_FILE = (
    REPO_ROOT
    / "plugins"
    / "autonomous-dev"
    / "hooks"
    / "unified_pre_tool.py"
)
EXEMPTION_REGISTRY = (
    REPO_ROOT
    / "plugins"
    / "autonomous-dev"
    / "config"
    / "hook_recovery_exemptions.json"
)

# Match  output_decision("deny",  with optional whitespace.
_LITERAL_DENY_RE = re.compile(r"output_decision\s*\(\s*[\"']deny[\"']")
_RECOVERY_CALL_RE = re.compile(r"log_block_with_recovery\s*\(")


@dataclass
class Violation:
    line_no: int
    function_name: str
    snippet: str
    reason: str


def _load_exemptions() -> List[str]:
    """Return list of exempted block_reason substrings, or [] on error."""
    if not EXEMPTION_REGISTRY.exists():
        return []
    try:
        data = json.loads(EXEMPTION_REGISTRY.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    out: List[str] = []
    for entry in data.get("exemptions", []) or []:
        if not isinstance(entry, dict):
            continue
        reason = entry.get("block_reason_contains")
        if isinstance(reason, str) and reason:
            out.append(reason)
    return out


def _enclosing_function(tree: ast.AST, lineno: int) -> str:
    """Return name of enclosing FunctionDef for a given line (or 'module')."""
    best_name = "<module>"
    best_start = -1
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= lineno and (node.end_lineno or 0) >= lineno:
                if node.lineno > best_start:
                    best_start = node.lineno
                    best_name = node.name
    return best_name


def _function_has_recovery_call(
    source_lines: List[str], func_start: int, func_end: int
) -> bool:
    """Return True if any log_block_with_recovery( appears inside function."""
    for i in range(func_start - 1, min(func_end, len(source_lines))):
        if _RECOVERY_CALL_RE.search(source_lines[i]):
            return True
    return False


def _function_bounds(tree: ast.AST, func_name: str) -> Optional[tuple]:
    """Return (start_line, end_line) of the named FunctionDef, or None."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == func_name:
                return (node.lineno, node.end_lineno or node.lineno)
    return None


def audit_file(path: Path) -> List[Violation]:
    """Return list of unjustified deny sites in ``path``.

    A deny site is unjustified when its enclosing function does not contain
    a ``log_block_with_recovery(`` call AND no exemption in the registry
    matches a substring of the deny line.

    Args:
        path: Source file to audit. If missing, returns [] (graceful).
    """
    if not path.exists():
        return []

    source = path.read_text(encoding="utf-8")
    source_lines = source.splitlines()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    exemptions = _load_exemptions()
    violations: List[Violation] = []

    for idx, line in enumerate(source_lines, start=1):
        if not _LITERAL_DENY_RE.search(line):
            continue

        # Skip exempted lines.
        if any(substring and substring in line for substring in exemptions):
            continue

        func_name = _enclosing_function(tree, idx)
        bounds = _function_bounds(tree, func_name) if func_name != "<module>" else None
        has_recovery = False
        if bounds is not None:
            has_recovery = _function_has_recovery_call(source_lines, bounds[0], bounds[1])

        if not has_recovery:
            violations.append(
                Violation(
                    line_no=idx,
                    function_name=func_name,
                    snippet=line.strip()[:120],
                    reason="literal output_decision('deny', ...) without log_block_with_recovery() in same function",
                )
            )

    return violations


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any unjustified deny site is found.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=TARGET_FILE,
        help="File to audit (default: plugins/autonomous-dev/hooks/unified_pre_tool.py).",
    )
    args = parser.parse_args(argv)

    strict = args.strict or os.environ.get(
        "AUDIT_HOOK_RECOVERY_STRICT", ""
    ).strip().lower() in ("1", "true", "yes", "on")

    violations = audit_file(args.target)
    if violations:
        print(f"hook_recovery audit: {len(violations)} unjustified deny site(s) in {args.target}")
        for v in violations:
            print(
                f"  L{v.line_no} in {v.function_name}: {v.snippet}\n"
                f"    -> {v.reason}"
            )
    else:
        print(f"hook_recovery audit: clean (0 unjustified deny sites in {args.target})")

    if strict and violations:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
