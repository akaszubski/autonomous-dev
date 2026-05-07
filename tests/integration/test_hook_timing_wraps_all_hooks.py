"""Integration test: every active hook wraps main() with HookTimer (Issue #1012).

Static AST + textual scan over ``plugins/autonomous-dev/hooks/*.py``
(top-level only, excluding ``archived/``). Each active hook MUST:

1. Define a ``HookTimer`` symbol at module level (either via
   ``from hook_timing import HookTimer`` or via the fallback no-op stub).
2. Reference ``HookTimer(`` at least once outside the import block — the
   hook actually uses the timer in a ``with`` statement somewhere.
3. Define a ``_timed_main`` function and pass it to the safe-main
   wrapper at the ``__main__`` block.

This guards against regression where someone adds a hook and forgets to
add timing wrap.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"


def _active_hooks() -> list[Path]:
    """Return all top-level hook files (skip archived/, skip __init__)."""
    return sorted(p for p in HOOKS_DIR.glob("*.py") if p.name != "__init__.py")


@pytest.fixture(scope="module")
def hook_files() -> list[Path]:
    return _active_hooks()


def test_at_least_24_active_hooks(hook_files):
    """Sanity: count is consistent with the issue."""
    assert len(hook_files) >= 24, (
        f"expected >=24 active hooks, found {len(hook_files)}"
    )


def test_every_active_hook_imports_HookTimer(hook_files):
    """Each hook references ``HookTimer`` at module level."""
    missing: list[str] = []
    for path in hook_files:
        src = path.read_text()
        # Either real import OR the fallback class definition.
        has_import = "from hook_timing import HookTimer" in src
        has_fallback = "class HookTimer" in src
        if not (has_import and has_fallback):
            # Both must be present — the import line + the fallback stub.
            missing.append(path.name)
    assert not missing, (
        "Hooks missing HookTimer import + fallback stub: "
        f"{missing}. Use the pattern from .claude/plans/issue-1012-W0-telemetry-plan.md "
        "step 3."
    )


def test_every_active_hook_wraps_main_with_timer(hook_files):
    """Each hook defines _timed_main that wraps main() in HookTimer."""
    missing: list[str] = []
    for path in hook_files:
        src = path.read_text()
        if "def _timed_main" not in src:
            missing.append(f"{path.name}: missing _timed_main def")
            continue
        if "HookTimer(" not in src:
            missing.append(f"{path.name}: never instantiates HookTimer")
            continue
        # The __main__ block must call _timed_main, not main directly.
        if "_safe_main_953(_timed_main)" not in src and "_hook_safe_main(_timed_main)" not in src:
            missing.append(
                f"{path.name}: __main__ block does not call safe_main(_timed_main)"
            )
    assert not missing, (
        "Hooks not wrapped per Issue #1012 spec:\n  " + "\n  ".join(missing)
    )


def test_no_active_hook_calls_safe_main_main_directly(hook_files):
    """Direct safe_main(main) calls bypass timing — must not exist."""
    bad: list[str] = []
    for path in hook_files:
        src = path.read_text()
        # The pre-1012 patterns: _safe_main_953(main) and _hook_safe_main(main)
        # must have been replaced with the _timed_main version.
        if "_safe_main_953(main)" in src or "_hook_safe_main(main)" in src:
            bad.append(path.name)
    assert not bad, (
        "Hooks still call safe_main(main) directly (bypasses timing): "
        f"{bad}"
    )


def test_HookTimer_fallback_is_no_op_stub(hook_files):
    """The fallback stub must define the four-method no-op contract."""
    for path in hook_files:
        src = path.read_text()
        # Verify the fallback class has the expected methods so a missing
        # hook_timing.py import does not crash the hook.
        assert "def __init__" in src, f"{path.name}: fallback missing __init__"
        assert "def __enter__" in src, f"{path.name}: fallback missing __enter__"
        assert "def __exit__" in src, f"{path.name}: fallback missing __exit__"
        assert "def set_decision_shape" in src, (
            f"{path.name}: fallback missing set_decision_shape"
        )


def test_each_hook_parses_as_valid_python(hook_files):
    """The wrap must not break syntax."""
    for path in hook_files:
        src = path.read_text()
        try:
            ast.parse(src)
        except SyntaxError as e:
            pytest.fail(f"{path.name} no longer parses: {e}")
