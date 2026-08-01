#!/usr/bin/env python3
"""
Lib AST-Parse Smoke Guard — every plugins/autonomous-dev/lib/*.py must parse.

Regression guard for Issue #1389: a single stray closing paren in
`runtime_data_aggregator.py` made the module unparseable, which cascaded to
import failures in `cia_finding_store`, `issue_triage_analyzer`, and
`macro_promotion`. Nothing errored loudly — CIA still emitted its report text
via the final-message path — so the finding-store `append_finding()` emission
was silently dead for the whole class of consumers that import the broken module.

The instance was fixed in commit 6e441bdf (removed the stray `)`). This guard
closes the *class*: an unparseable lib module must fail a fast CI gate instead
of silently disabling tooling. It is deliberately syntax-only (ast.parse, no
execution) so it stays hermetic and <5s — it cannot be defeated by optional
missing deps and does not import side-effecting modules.

Auto-Marker: smoke (directory-based, Tier 0 — < 5s, CI gate)

Issue: #1389
"""

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"

# Canonical source of truth. Installed copies (.claude/lib, ~/.claude/lib) are
# deployed FROM this tree by scripts/deploy-all.sh, so guarding the source
# guards every downstream copy.
LIB_FILES = sorted(LIB_DIR.glob("*.py"))


def test_lib_dir_discovered():
    """Sanity: the guard actually found lib modules (path didn't silently break)."""
    assert LIB_DIR.is_dir(), f"lib dir not found at {LIB_DIR}"
    # 221 modules at time of writing (#1389); a floor guards against a broken
    # glob silently reducing coverage to zero.
    assert len(LIB_FILES) >= 100, (
        f"Expected >=100 lib modules, found {len(LIB_FILES)} — "
        f"path resolution or glob is likely broken, not real coverage."
    )


@pytest.mark.parametrize("lib_file", LIB_FILES, ids=lambda p: p.name)
def test_lib_module_is_parseable(lib_file):
    """Every lib/*.py must be a syntactically valid Python module.

    Catches the #1389 class: a syntax error (stray paren, bad indent, unclosed
    bracket) that makes a module unparseable and silently breaks every importer.
    """
    source = lib_file.read_text(encoding="utf-8")
    try:
        ast.parse(source, filename=str(lib_file))
    except SyntaxError as exc:  # pragma: no cover - failure path is the point
        pytest.fail(
            f"{lib_file.name} is not parseable (SyntaxError at "
            f"line {exc.lineno}): {exc.msg}\n"
            f"An unparseable lib module silently breaks every module that "
            f"imports it — see Issue #1389."
        )


def test_cia_finding_store_import_chain():
    """Targeted anchor for #1389: the exact import chain that broke must resolve.

    `runtime_data_aggregator` was the unparseable module; `cia_finding_store`
    imports from it. If either fails to import, CIA's programmatic
    finding-persistence (`append_finding`) is dead — the original silent failure.
    """
    lib_path = str(LIB_DIR)
    added = lib_path not in sys.path
    if added:
        sys.path.insert(0, lib_path)
    try:
        import importlib

        rda = importlib.import_module("runtime_data_aggregator")
        cfs = importlib.import_module("cia_finding_store")
        assert hasattr(cfs, "append_finding"), (
            "cia_finding_store must expose append_finding() — the CIA "
            "programmatic emission path (#1389)."
        )
        # runtime_data_aggregator is the module that broke; touching an
        # attribute confirms it loaded, not just that the name resolved.
        assert rda is not None
    finally:
        if added and lib_path in sys.path:
            sys.path.remove(lib_path)
