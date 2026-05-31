"""Unit tests for the _is_batch_context helper (Issue #1133).

Validates that the centralized helper in unified_pre_tool.py recognizes
both signals — worktree-based cwd AND the BATCH_NO_WORKTREE env var —
so all three batch hook gates fire consistently in either mode.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = (
    PROJECT_ROOT
    / "plugins"
    / "autonomous-dev"
    / "hooks"
    / "unified_pre_tool.py"
)


def _load_hook_module():
    """Import unified_pre_tool.py as a module for white-box testing.

    The hook is a stand-alone script entry-point but defines library
    helpers at module scope. We import it without executing the
    ``if __name__ == "__main__"`` block.
    """
    spec = importlib.util.spec_from_file_location("unified_pre_tool", str(HOOK_PATH))
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load unified_pre_tool.py")
    module = importlib.util.module_from_spec(spec)
    # Insert the lib directory on sys.path so the module's imports resolve.
    lib_dir = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"
    if str(lib_dir) not in sys.path:
        sys.path.insert(0, str(lib_dir))
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def hook_module():
    return _load_hook_module()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Each test starts with BATCH_NO_WORKTREE unset."""
    monkeypatch.delenv("BATCH_NO_WORKTREE", raising=False)
    yield


class TestIsBatchContext:
    """The _is_batch_context helper recognizes both worktree and env var signals."""

    def test_is_batch_context_true_for_worktree_cwd(self, hook_module):
        assert hook_module._is_batch_context(
            "/Users/me/Dev/myrepo/.worktrees/batch-20260531"
        ) is True

    def test_is_batch_context_true_for_env_var_set(self, hook_module, monkeypatch):
        monkeypatch.setenv("BATCH_NO_WORKTREE", "1")
        assert hook_module._is_batch_context("/Users/me/Dev/myrepo") is True

    def test_is_batch_context_false_for_plain_cwd_no_env(self, hook_module):
        assert hook_module._is_batch_context("/Users/me/Dev/myrepo") is False

    def test_is_batch_context_true_for_env_var_true_or_yes(self, hook_module, monkeypatch):
        for v in ("true", "TRUE", "yes", "YES", "1"):
            monkeypatch.setenv("BATCH_NO_WORKTREE", v)
            assert hook_module._is_batch_context("/plain") is True, (
                f"Expected truthy result for BATCH_NO_WORKTREE={v!r}"
            )

    def test_is_batch_context_false_for_env_var_falsy(self, hook_module, monkeypatch):
        for v in ("", "0", "false", "no", "off"):
            monkeypatch.setenv("BATCH_NO_WORKTREE", v)
            assert hook_module._is_batch_context("/plain") is False, (
                f"Expected falsy result for BATCH_NO_WORKTREE={v!r}"
            )


class TestGatesFireInNoWorktreeMode:
    """The 3 batch hook gates each call _is_batch_context — verify presence.

    These tests are structural: they confirm the gate sites consult the
    centralized helper. Behavior tests (the gate actually firing on bad
    state) belong in the integration suite.

    Approach: split the source by line, find the lines mentioning each
    gate's distinguishing bypass-env-var, then check that _is_batch_context
    appears within a small window above each gate line.
    """

    def _find_gate_window(self, src: str, marker: str, window: int = 25) -> str:
        """Return the source slice ending at ``marker`` and reaching back ``window`` lines."""
        lines = src.splitlines()
        for i, line in enumerate(lines):
            if marker in line and "env vars don't propagate" not in line:
                start = max(0, i - window)
                return "\n".join(lines[start : i + 1])
        return ""

    def test_cia_gate_fires_in_no_worktree_mode(self):
        """The Batch CIA completion gate site uses _is_batch_context."""
        src = HOOK_PATH.read_text()
        # The actual gate site is at the env-var bypass check line. Find the
        # line `SKIP_BATCH_CIA_GATE` inside an `os.environ.get(...)` context
        # (not the error-message line which says "Set SKIP_BATCH_CIA_GATE=1").
        marker = 'os.environ.get("SKIP_BATCH_CIA_GATE"'
        window = self._find_gate_window(src, marker)
        assert window, "Could not locate the CIA gate bypass-check line"
        assert "_is_batch_context(cwd)" in window, (
            "Batch CIA completion gate site must call _is_batch_context(cwd) so "
            "the gate fires in --no-worktree mode too."
        )

    def test_doc_master_gate_fires_in_no_worktree_mode(self):
        """The Batch doc-master completion gate site uses _is_batch_context."""
        src = HOOK_PATH.read_text()
        marker = 'os.environ.get("SKIP_BATCH_DOC_MASTER_GATE"'
        window = self._find_gate_window(src, marker)
        assert window, "Could not locate the doc-master gate bypass-check line"
        assert "_is_batch_context(cwd)" in window, (
            "Batch doc-master completion gate site must call _is_batch_context(cwd) "
            "so the gate fires in --no-worktree mode too."
        )

    def test_agent_completeness_gate_fires_in_no_worktree_mode(self):
        """The agent completeness gate batch branch uses _is_batch_context."""
        src = HOOK_PATH.read_text()
        # The batch branch of the agent completeness gate is the third
        # call site of _is_batch_context(cwd) in the hook source.
        # All 3 must exist; we count by-line presence.
        count = sum(
            1 for line in src.splitlines() if "_is_batch_context(cwd)" in line
        )
        assert count >= 3, (
            f"Expected at least 3 call sites of _is_batch_context(cwd) "
            f"(one per batch gate), found {count}"
        )

    def test_skip_batch_cia_gate_still_bypasses(self):
        """The SKIP_BATCH_CIA_GATE env-var bypass remains intact.

        Even with BATCH_NO_WORKTREE=1 making _is_batch_context return True,
        the SKIP_BATCH_CIA_GATE env var must continue to bypass the CIA
        check. Structural verification: the bypass check sits INSIDE the
        _is_batch_context branch.
        """
        src = HOOK_PATH.read_text()
        lines = src.splitlines()
        ctx_idx = None
        for i, line in enumerate(lines):
            if "_is_batch_context(cwd):" in line and "if " in line:
                ctx_idx = i
                break
        assert ctx_idx is not None, "No _is_batch_context(cwd) check found"
        # Within the next 10 lines after the first _is_batch_context check
        # we expect to see the SKIP_BATCH_CIA_GATE bypass.
        window = "\n".join(lines[ctx_idx : ctx_idx + 10])
        assert "SKIP_BATCH_CIA_GATE" in window, (
            "SKIP_BATCH_CIA_GATE env-var bypass must still gate the CIA check "
            "after the _is_batch_context branch is entered."
        )
