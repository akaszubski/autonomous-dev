"""Regression tests: Issue #1139 — baseline_guardrail wired into unified_pre_tool.py.

Tests the hook wiring at two levels:

1. Unit-level: the env-prefix stripping + git stash detection logic that the hook
   uses to decide when to call warn_if_baseline_missing, exercised directly.
2. Integration-level: verify warn_if_baseline_missing is loadable via the same
   importlib.util pattern used in the hook and produces the expected stderr output.

The guardrail MUST be advisory only — it MUST NOT block (deny) the tool call.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]
HOOK_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"

for _p in (str(HOOK_DIR), str(LIB_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---------------------------------------------------------------------------
# Helpers replicated from the hook's Issue #1139 block (to unit-test the logic)
# ---------------------------------------------------------------------------

def _hook_should_warn(command: str) -> bool:
    """Return True if the hook's env-prefix stripping + stash detection decides to check.

    Replicates the exact logic embedded in unified_pre_tool.py lines added for Issue #1139.
    """
    cmd = command.lstrip()
    # Strip leading VAR=val env prefixes (e.g. "FOO=bar git stash ...")
    while cmd and "=" in cmd.split(" ", 1)[0] and "/" not in cmd.split(" ", 1)[0]:
        cmd = cmd.split(" ", 1)[1] if " " in cmd else ""
    return cmd.startswith("git stash")


def _load_baseline_guardrail_via_importlib():
    """Load baseline_guardrail using the same importlib.util pattern as the hook."""
    bg_spec = importlib.util.spec_from_file_location(
        "baseline_guardrail",
        str(LIB_DIR / "baseline_guardrail.py"),
    )
    assert bg_spec is not None and bg_spec.loader is not None, (
        "Could not create spec for baseline_guardrail.py"
    )
    bg_mod = importlib.util.module_from_spec(bg_spec)
    bg_spec.loader.exec_module(bg_mod)
    return bg_mod


def _make_sentinel_without_baseline(tmp_path: Path) -> Path:
    """Return a pipeline sentinel that has NO baseline_cmd key."""
    sentinel = tmp_path / "implement_pipeline_state.json"
    sentinel.write_text(
        json.dumps(
            {
                "session_start": "2026-06-14T10:00:00",
                "mode": "full",
                "run_id": "test-1139-hook-wiring",
                "explicitly_invoked": True,
                # NOTE: intentionally no baseline_cmd key
            }
        )
    )
    return sentinel


def _make_sentinel_with_baseline(tmp_path: Path) -> Path:
    """Return a pipeline sentinel that HAS a valid baseline_cmd recorded."""
    sentinel = tmp_path / "implement_pipeline_state.json"
    sentinel.write_text(
        json.dumps(
            {
                "session_start": "2026-06-14T10:00:00",
                "mode": "full",
                "run_id": "test-1139-hook-wiring-with-baseline",
                "explicitly_invoked": True,
                "baseline_cmd": ["pytest", "tests/unit/", "--tb=no", "-q"],
                "baseline_count": 42,
            }
        )
    )
    return sentinel


# ---------------------------------------------------------------------------
# Tests — detection logic
# ---------------------------------------------------------------------------


class TestIssue1139StashDetectionLogic:
    """Unit tests for the env-prefix stripping + git stash detection in the hook."""

    def test_bare_git_stash_triggers_check(self) -> None:
        """'git stash' triggers the guardrail check. Regression for Issue #1139."""
        assert _hook_should_warn("git stash") is True

    def test_git_stash_with_subcommand_triggers_check(self) -> None:
        """'git stash pop' triggers the guardrail check. Regression for Issue #1139."""
        assert _hook_should_warn("git stash pop") is True

    def test_git_stash_with_leading_whitespace_triggers_check(self) -> None:
        """Leading whitespace is stripped before detection. Regression for Issue #1139."""
        assert _hook_should_warn("  git stash") is True

    def test_env_prefixed_git_stash_triggers_check(self) -> None:
        """'VAR=val git stash' triggers after env-prefix stripping. Regression #1139."""
        assert _hook_should_warn("FOO=bar git stash") is True

    def test_git_status_does_not_trigger_check(self) -> None:
        """'git status' does NOT trigger the guardrail. Regression for Issue #1139."""
        assert _hook_should_warn("git status") is False

    def test_git_commit_does_not_trigger_check(self) -> None:
        """'git commit' does NOT trigger the guardrail. Regression for Issue #1139."""
        assert _hook_should_warn("git commit -m 'msg'") is False

    def test_empty_command_does_not_trigger_check(self) -> None:
        """Empty command does NOT trigger the guardrail. Regression for Issue #1139."""
        assert _hook_should_warn("") is False


# ---------------------------------------------------------------------------
# Tests — guardrail invocation via importlib pattern (same as the hook uses)
# ---------------------------------------------------------------------------


class TestIssue1139GuardrailInvocationPattern:
    """Test the complete hook wiring pattern: importlib load + warn_if_baseline_missing."""

    def test_guardrail_loadable_via_importlib(self) -> None:
        """baseline_guardrail.py is loadable via importlib.util (same path as hook uses).

        Verifies the hook's dynamic import path is correct.
        Regression for Issue #1139 FINDING-1.
        """
        bg_mod = _load_baseline_guardrail_via_importlib()
        assert hasattr(bg_mod, "warn_if_baseline_missing"), (
            "baseline_guardrail module must expose warn_if_baseline_missing"
        )

    def test_warn_emitted_when_sentinel_exists_without_baseline(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """[BASELINE-MISSING-WARNING] in stderr when sentinel has no baseline_cmd.

        Full integration test of the hook wiring pattern: load via importlib,
        call with a sentinel missing baseline_cmd → warning on stderr.
        Regression for Issue #1139 FINDING-1.
        """
        sentinel = _make_sentinel_without_baseline(tmp_path)
        bg_mod = _load_baseline_guardrail_via_importlib()

        result = bg_mod.warn_if_baseline_missing(str(sentinel))

        assert result is True, "warn_if_baseline_missing should return True when baseline absent"
        captured = capsys.readouterr()
        assert "[BASELINE-MISSING-WARNING]" in captured.err, (
            f"Expected [BASELINE-MISSING-WARNING] in stderr, got: {captured.err!r}"
        )

    def test_no_warn_when_sentinel_has_baseline(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """No warning when sentinel contains a valid baseline_cmd.

        Normal pipeline case — STEP 1 ran. No warning should fire.
        Regression for Issue #1139 FINDING-1.
        """
        sentinel = _make_sentinel_with_baseline(tmp_path)
        bg_mod = _load_baseline_guardrail_via_importlib()

        result = bg_mod.warn_if_baseline_missing(str(sentinel))

        assert result is False, "warn_if_baseline_missing should return False when baseline present"
        captured = capsys.readouterr()
        assert "[BASELINE-MISSING-WARNING]" not in captured.err, (
            f"Unexpected warning in stderr: {captured.err!r}"
        )

    def test_no_warn_when_sentinel_does_not_exist(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """No warning when sentinel does not exist (pipeline not active).

        Guardrail must be a no-op outside pipeline.
        Regression for Issue #1139 FINDING-1.
        """
        non_existent = str(tmp_path / "does_not_exist.json")
        bg_mod = _load_baseline_guardrail_via_importlib()

        result = bg_mod.warn_if_baseline_missing(non_existent)

        assert result is False
        captured = capsys.readouterr()
        assert "[BASELINE-MISSING-WARNING]" not in captured.err

    def test_guardrail_never_raises_on_bad_input(self, tmp_path: Path) -> None:
        """warn_if_baseline_missing never raises (advisory contract).

        The guardrail must not crash the hook under any input.
        Regression for Issue #1139 FINDING-2 (narrow except clause).
        """
        bg_mod = _load_baseline_guardrail_via_importlib()

        # Malformed JSON
        bad = tmp_path / "malformed.json"
        bad.write_text("NOT { JSON }")
        try:
            result = bg_mod.warn_if_baseline_missing(str(bad))
            assert isinstance(result, bool)
        except Exception as exc:
            pytest.fail(f"warn_if_baseline_missing raised on malformed JSON: {exc}")

        # Empty string path
        try:
            result = bg_mod.warn_if_baseline_missing("")
            assert isinstance(result, bool)
        except Exception as exc:
            pytest.fail(f"warn_if_baseline_missing raised on empty string: {exc}")
