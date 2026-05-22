"""Regression test for Issue #993: deprecation warning must surface on stderr.

The legacy ``log_block_with_recovery`` shim previously emitted its deprecation
via ``warnings.warn(..., DeprecationWarning)``. Python's default warning filter
SUPPRESSES ``DeprecationWarning`` raised from non-``__main__`` modules, so when
the hook code imported this shim the deprecation signal was silently swallowed
— operators stayed on the legacy API without ever seeing it was deprecated.

Fix (per Issue #993): emit a single ``[hook-recovery] DEPRECATION: ...`` line on
``sys.stderr`` directly. A module-level boolean flag
(``_legacy_warn_emitted``) gates the emission so it fires exactly once per
process — repeat calls in the same process must not re-emit.

Tests:

1. **First call** — stderr MUST contain the deprecation line.
2. **Second call (same process)** — second-call stderr MUST NOT re-emit the
   deprecation line (one-shot per process).
3. **Fresh process** — a subprocess that imports the module afresh MUST
   re-emit the deprecation line. This simulates the operator's real-world
   reload after restarting Claude Code or running a new hook process.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

# Make hook_recovery importable. tests/regression/test_*.py -> repo root is
# parents[2] (regression -> tests -> repo).
REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import hook_recovery  # noqa: E402


DEPRECATION_MARKER = "DEPRECATION: log_block_with_recovery is deprecated"


@pytest.fixture(autouse=True)
def _reset_legacy_warn_flag():
    """Reset the module-level flag before AND after each test.

    Without this reset, ordering between tests in the same process would
    leak state and the "first call emits" test would fail spuriously
    whenever it runs second.
    """
    hook_recovery._legacy_warn_emitted = False
    yield
    hook_recovery._legacy_warn_emitted = False


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch) -> Path:
    """Isolated project root with .claude/logs/ so the shim's downstream
    telemetry call has somewhere to write without polluting the repo."""
    (tmp_path / ".claude" / "logs").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".claude" / "config").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _capture_stderr(monkeypatch) -> list[str]:
    """Capture every ``sys.stderr.write`` into a list and return that list."""
    captured: list[str] = []
    original_write = sys.stderr.write

    def capture_write(text: str) -> int:
        captured.append(text)
        return original_write(text)

    monkeypatch.setattr(sys.stderr, "write", capture_write)
    # Flush calls also need to be no-ops or pass-through; the default
    # sys.stderr.flush is fine, so nothing else to patch.
    return captured


class TestIssue993DeprecationStderr:
    """Regression for #993 — deprecation must surface on stderr, once."""

    def test_first_call_emits_deprecation_on_stderr(
        self, project_dir, monkeypatch
    ):
        """First call to the deprecated shim must write the deprecation
        marker line directly to stderr (bypassing the warnings filter)."""
        captured = _capture_stderr(monkeypatch)

        hook_recovery.log_block_with_recovery(
            hook_name="unified_pre_tool.py",
            tool_name="Bash",
            block_reason="testing #993",
            recovery_hint="ignore",
        )

        joined = "".join(captured)
        assert DEPRECATION_MARKER in joined, (
            "Expected deprecation line on stderr but got:\n" + joined
        )
        # Sanity: the [hook-recovery] prefix should also be present so log
        # scrapers can grep for it.
        assert "[hook-recovery]" in joined
        # And the one-shot flag must now be set.
        assert hook_recovery._legacy_warn_emitted is True

    def test_second_call_does_not_re_emit_deprecation(
        self, project_dir, monkeypatch
    ):
        """One-shot semantics: second call in the same process MUST NOT
        re-emit the deprecation line (the flag stays set).
        """
        # Prime the flag by calling once (capturing stderr along the way so
        # the marker doesn't pollute the actual stderr of the test runner).
        first_captured = _capture_stderr(monkeypatch)
        hook_recovery.log_block_with_recovery(
            hook_name="unified_pre_tool.py",
            tool_name="Bash",
            block_reason="prime",
            recovery_hint="ignore",
        )
        # Confirm priming worked — flag is set, marker was emitted.
        assert hook_recovery._legacy_warn_emitted is True
        assert DEPRECATION_MARKER in "".join(first_captured)

        # Reset the capture list to isolate the SECOND call's stderr.
        first_captured.clear()

        # Second call in the same process.
        hook_recovery.log_block_with_recovery(
            hook_name="unified_pre_tool.py",
            tool_name="Bash",
            block_reason="second",
            recovery_hint="ignore",
        )

        joined_second = "".join(first_captured)
        assert DEPRECATION_MARKER not in joined_second, (
            "Deprecation line must NOT re-emit on subsequent calls; "
            "got stderr:\n" + joined_second
        )

    def test_fresh_process_reemits_deprecation(self, tmp_path: Path):
        """A new Python process must re-emit the deprecation line.

        Operator scenario: they restart Claude Code or a hook subprocess
        starts fresh — the deprecation MUST surface again so they can act
        on it. We simulate this with ``subprocess.run`` (a guaranteed
        clean module-level state, unlike ``importlib.reload`` which can
        keep references alive in pathological cases).
        """
        # The subprocess needs the same LIB_DIR on sys.path and to chdir
        # into a writable tmp so the shim's downstream telemetry call
        # has somewhere to write.
        script = textwrap.dedent(
            f"""
            import os
            import sys
            os.chdir({str(tmp_path)!r})
            os.makedirs(".claude/logs", exist_ok=True)
            sys.path.insert(0, {str(LIB_DIR)!r})
            import hook_recovery
            # Flag MUST be False at process startup (module-level default).
            assert hook_recovery._legacy_warn_emitted is False, (
                "_legacy_warn_emitted should default to False in a fresh process"
            )
            hook_recovery.log_block_with_recovery(
                hook_name="unified_pre_tool.py",
                tool_name="Bash",
                block_reason="fresh process",
                recovery_hint="ignore",
            )
            """
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, (
            f"Subprocess exited non-zero.\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        assert DEPRECATION_MARKER in result.stderr, (
            "Fresh process must re-emit the deprecation line; got stderr:\n"
            + result.stderr
        )
