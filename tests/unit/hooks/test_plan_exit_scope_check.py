"""Tests for plan_mode_exit_detector.py scope/escape behavior (Issue #938, flipped #1361).

Issue #1361 flipped the polarity from opt-in (only enforce in autonomous-dev repos
or with AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT=1) to default-ON in every repo, subject
to two opt-outs:
    AUTONOMOUS_DEV_SKIP_PLAN_REVIEW=<truthy>   (env var, cross-session)
    .claude/SKIP_PLAN_REVIEW                   (sentinel file)

Plus the universal Issue #969 bypass (short-circuits earlier in main()):
    AUTONOMOUS_DEV_BYPASS=<truthy>             (env var)
    .claude/.bypass                            (file flag, walks up chain)

``AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT`` is deprecated — enforcement is now the
default; setting it emits a stderr notice but is otherwise a no-op.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks directory to path for direct import.
HOOKS_DIR = (
    Path(__file__).resolve().parents[3]
    / "plugins"
    / "autonomous-dev"
    / "hooks"
)
sys.path.insert(0, str(HOOKS_DIR))

import plan_mode_exit_detector  # noqa: E402
from plan_mode_exit_detector import MARKER_PATH, main  # noqa: E402


# ============================================================================
# Helpers
# ============================================================================


def _run_main(input_data: dict) -> int:
    """Invoke main() with stubbed stdin reading the supplied JSON."""
    with patch("sys.stdin") as mock_stdin:
        mock_stdin.read.return_value = json.dumps(input_data)
        return main()


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear all Issue #938/#1361 escape/enforcement env vars."""
    for var in (
        "AUTONOMOUS_DEV_SKIP_PLAN_REVIEW",
        "AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT",
        "AUTONOMOUS_DEV_BYPASS",
    ):
        monkeypatch.delenv(var, raising=False)


# ============================================================================
# Foreign-project default enforcement (Issue #1361 polarity flip)
# ============================================================================


class TestForeignProjectDefaultEnforce:
    """Default behavior outside autonomous-dev repos: enforcement fires (#1361)."""

    def test_foreign_project_default_writes_marker_and_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        """AC-1: Foreign project + no bypass → marker written, plan-critic message.

        Under the #1361 polarity flip, foreign projects are no longer silently
        skipped — enforcement is default-ON. The scope check was deleted.
        """
        _clear_env(monkeypatch)
        # Force "foreign project" — detector returns False.
        monkeypatch.setattr(
            plan_mode_exit_detector, "_is_adev_project_fn", lambda: False
        )
        monkeypatch.chdir(tmp_path)

        result = _run_main({"tool_name": "ExitPlanMode"})

        assert result == 0
        # AC-1: marker MUST be written in foreign projects now.
        assert (tmp_path / MARKER_PATH).exists(), (
            "Post-#1361: foreign project must receive a plan-exit marker"
        )
        captured = capsys.readouterr()
        assert captured.out, "Post-#1361: foreign project must emit systemMessage"
        output = json.loads(captured.out)
        assert "plan-critic" in output["systemMessage"].lower()

    def test_foreign_project_with_bypass_file_short_circuits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        """AC-2: Foreign project + ``.claude/.bypass`` → silent no-op.

        The universal Issue #969 bypass short-circuits in the hook preamble
        before this test's scope check. No marker, no output.
        """
        _clear_env(monkeypatch)
        monkeypatch.setattr(
            plan_mode_exit_detector, "_is_adev_project_fn", lambda: False
        )
        monkeypatch.chdir(tmp_path)
        # Drop the universal bypass sentinel.
        (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".claude" / ".bypass").write_text("")

        result = _run_main({"tool_name": "ExitPlanMode"})

        assert result == 0
        # ``.claude/.bypass`` fully short-circuits — no marker.
        assert not (tmp_path / MARKER_PATH).exists(), (
            "AC-2: .claude/.bypass must short-circuit before marker write"
        )
        captured = capsys.readouterr()
        # The bypass path produces no user-facing output.
        assert captured.out == "", (
            f"AC-2: .claude/.bypass must be silent, got: {captured.out!r}"
        )

    def test_foreign_project_with_bypass_env_short_circuits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        """AC-2 variant: Foreign project + ``AUTONOMOUS_DEV_BYPASS=1`` → silent no-op."""
        _clear_env(monkeypatch)
        monkeypatch.setenv("AUTONOMOUS_DEV_BYPASS", "1")
        monkeypatch.setattr(
            plan_mode_exit_detector, "_is_adev_project_fn", lambda: False
        )
        monkeypatch.chdir(tmp_path)

        result = _run_main({"tool_name": "ExitPlanMode"})

        assert result == 0
        assert not (tmp_path / MARKER_PATH).exists()

    def test_foreign_project_with_skip_env_emits_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        """AC-4: Foreign project + skip env var → bypass warning fires unconditionally.

        Post-#1361 the "warning only in autonomous-dev repos" special case is
        gone — enforcement is default-ON everywhere, so the bypass warning is
        emitted everywhere too.
        """
        _clear_env(monkeypatch)
        monkeypatch.setenv("AUTONOMOUS_DEV_SKIP_PLAN_REVIEW", "1")
        monkeypatch.setattr(
            plan_mode_exit_detector, "_is_adev_project_fn", lambda: False
        )
        monkeypatch.chdir(tmp_path)

        result = _run_main({"tool_name": "ExitPlanMode"})

        assert result == 0
        assert not (tmp_path / MARKER_PATH).exists()
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "BYPASS" in output["systemMessage"]
        assert "AUTONOMOUS_DEV_SKIP_PLAN_REVIEW" in output["systemMessage"]


# ============================================================================
# In-project default and escape behavior
# ============================================================================


class TestInProjectBehavior:
    """Default and escape behavior inside autonomous-dev repos (AC-3)."""

    def test_in_project_no_escape_writes_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        """AC-3: In-project + no escape → existing behavior preserved (marker + msg)."""
        _clear_env(monkeypatch)
        monkeypatch.setattr(
            plan_mode_exit_detector, "_is_adev_project_fn", lambda: True
        )
        monkeypatch.chdir(tmp_path)

        result = _run_main({"tool_name": "ExitPlanMode"})

        assert result == 0
        marker_file = tmp_path / MARKER_PATH
        assert marker_file.exists(), "In-project must write marker"
        marker_data = json.loads(marker_file.read_text())
        assert marker_data["stage"] == "plan_exited"

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "plan-critic" in output["systemMessage"].lower()
        # The new message should advertise all three escape hatches.
        assert "--skip-review" in output["systemMessage"]
        assert "AUTONOMOUS_DEV_SKIP_PLAN_REVIEW" in output["systemMessage"]
        assert "SKIP_PLAN_REVIEW" in output["systemMessage"]

    def test_in_project_with_skip_env_no_marker_emits_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        """AC-4: In-project + env var → no marker + user-visible bypass warning."""
        _clear_env(monkeypatch)
        monkeypatch.setenv("AUTONOMOUS_DEV_SKIP_PLAN_REVIEW", "true")
        monkeypatch.setattr(
            plan_mode_exit_detector, "_is_adev_project_fn", lambda: True
        )
        monkeypatch.chdir(tmp_path)

        result = _run_main({"tool_name": "ExitPlanMode"})

        assert result == 0
        assert not (tmp_path / MARKER_PATH).exists(), (
            "Escape hatch must prevent marker write"
        )

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        msg = output["systemMessage"]
        assert "BYPASS" in msg
        assert "AUTONOMOUS_DEV_SKIP_PLAN_REVIEW" in msg

    def test_in_project_with_sentinel_no_marker_emits_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        """AC-5: In-project + sentinel file → no marker + warning naming sentinel."""
        _clear_env(monkeypatch)
        monkeypatch.setattr(
            plan_mode_exit_detector, "_is_adev_project_fn", lambda: True
        )
        monkeypatch.chdir(tmp_path)
        # Drop the sentinel.
        (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".claude" / "SKIP_PLAN_REVIEW").write_text("")

        result = _run_main({"tool_name": "ExitPlanMode"})

        assert result == 0
        assert not (tmp_path / MARKER_PATH).exists()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        msg = output["systemMessage"]
        assert "BYPASS" in msg
        assert "SKIP_PLAN_REVIEW" in msg


# ============================================================================
# Deprecated GLOBAL_ENFORCEMENT env var (Issue #1361)
# ============================================================================


class TestGlobalEnforcementDeprecated:
    """AC-6: AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT is deprecated — no-op with stderr notice."""

    def test_global_enforcement_still_writes_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """AC-6 (part 1): GLOBAL_ENFORCEMENT=1 in foreign repo still enforces.

        Because enforcement is now the default, setting the deprecated var is
        effectively a no-op on behavior — the marker gets written either way.
        """
        _clear_env(monkeypatch)
        monkeypatch.setenv("AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT", "1")
        monkeypatch.setattr(
            plan_mode_exit_detector, "_is_adev_project_fn", lambda: False
        )
        monkeypatch.chdir(tmp_path)

        result = _run_main({"tool_name": "ExitPlanMode"})

        assert result == 0
        assert (tmp_path / MARKER_PATH).exists(), (
            "Post-#1361: enforcement default-ON — marker must be written"
        )

    def test_global_enforcement_emits_deprecation_notice(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        """AC-6 (part 2): GLOBAL_ENFORCEMENT=1 emits stderr deprecation notice."""
        _clear_env(monkeypatch)
        monkeypatch.setenv("AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT", "1")
        monkeypatch.setattr(
            plan_mode_exit_detector, "_is_adev_project_fn", lambda: True
        )
        monkeypatch.chdir(tmp_path)

        _run_main({"tool_name": "ExitPlanMode"})

        captured = capsys.readouterr()
        assert "DEPRECATION" in captured.err, (
            f"AC-6: expected deprecation notice on stderr, got: {captured.err!r}"
        )
        assert "AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT" in captured.err

    def test_no_deprecation_notice_when_var_unset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        """Companion to AC-6: no notice when the deprecated var is not set."""
        _clear_env(monkeypatch)
        monkeypatch.setattr(
            plan_mode_exit_detector, "_is_adev_project_fn", lambda: True
        )
        monkeypatch.chdir(tmp_path)

        _run_main({"tool_name": "ExitPlanMode"})

        captured = capsys.readouterr()
        assert "DEPRECATION" not in captured.err

    def test_escape_wins_over_global_enforcement(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        """Both env vars set → SKIP escape wins (no marker).

        Post-#1361 the warning fires unconditionally (default-ON enforcement),
        so the bypass warning is emitted even in foreign projects.
        """
        _clear_env(monkeypatch)
        monkeypatch.setenv("AUTONOMOUS_DEV_SKIP_PLAN_REVIEW", "1")
        monkeypatch.setenv("AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT", "1")
        monkeypatch.setattr(
            plan_mode_exit_detector, "_is_adev_project_fn", lambda: False
        )
        monkeypatch.chdir(tmp_path)

        result = _run_main({"tool_name": "ExitPlanMode"})

        assert result == 0
        assert not (tmp_path / MARKER_PATH).exists()
        # Post-#1361: warning fires everywhere (foreign projects too).
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "BYPASS" in output["systemMessage"]


# ============================================================================
# Truthy parsing
# ============================================================================


class TestTruthyVariants:
    """All canonical truthy values must trigger bypass."""

    @pytest.mark.parametrize("truthy", ["1", "true", "TRUE", "yes", "on"])
    def test_truthy_variants_all_bypass(
        self,
        truthy: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """1/true/TRUE/yes/on all bypass the writer hook."""
        _clear_env(monkeypatch)
        monkeypatch.setenv("AUTONOMOUS_DEV_SKIP_PLAN_REVIEW", truthy)
        monkeypatch.setattr(
            plan_mode_exit_detector, "_is_adev_project_fn", lambda: True
        )
        monkeypatch.chdir(tmp_path)

        result = _run_main({"tool_name": "ExitPlanMode"})

        assert result == 0
        assert not (tmp_path / MARKER_PATH).exists(), (
            f"Truthy value {truthy!r} should have bypassed but marker was written"
        )
