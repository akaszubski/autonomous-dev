"""Tests for plan_mode_exit_detector.py scope/escape behavior (Issue #938).

Covers the precedence ladder:
    escape (env var or sentinel) > scope (autonomous-dev repo) > default (no-op)

The detector hook is deployed both per-project (plugins/autonomous-dev/hooks/)
and user-globally (~/.claude/hooks/). When deployed globally it must NOT fire
inside foreign projects unless AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT=1 is set.
Three escape hatches bypass enforcement in any project:
    AUTONOMOUS_DEV_SKIP_PLAN_REVIEW=<truthy>   (env var)
    .claude/SKIP_PLAN_REVIEW                   (sentinel file)
    /implement --skip-review                   (one-shot, plan-only)
"""

import json
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
    """Clear all Issue #938 escape/enforcement env vars."""
    for var in (
        "AUTONOMOUS_DEV_SKIP_PLAN_REVIEW",
        "AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT",
    ):
        monkeypatch.delenv(var, raising=False)


# ============================================================================
# Foreign-project scope behavior
# ============================================================================


class TestForeignProjectScope:
    """Default behavior outside autonomous-dev repos: silent no-op."""

    def test_foreign_project_no_marker_no_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        """Foreign project + no env vars → no marker, no systemMessage."""
        _clear_env(monkeypatch)
        # Force "foreign project" — detector returns False.
        monkeypatch.setattr(
            plan_mode_exit_detector, "_is_adev_project_fn", lambda: False
        )
        monkeypatch.chdir(tmp_path)

        result = _run_main({"tool_name": "ExitPlanMode"})

        assert result == 0
        assert not (tmp_path / MARKER_PATH).exists(), (
            "Foreign project must NOT receive a plan-exit marker"
        )
        captured = capsys.readouterr()
        assert captured.out == "", (
            f"Foreign project must produce no stdout, got: {captured.out!r}"
        )

    def test_foreign_project_with_skip_env_no_marker_no_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        """Foreign project + skip env var → silent no-op (no warning).

        The escape hatch bypasses, but because we're out of scope no
        user-visible warning is emitted (warnings only fire in-project).
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
        assert captured.out == ""


# ============================================================================
# In-project default and escape behavior
# ============================================================================


class TestInProjectBehavior:
    """Default and escape behavior inside autonomous-dev repos."""

    def test_in_project_no_escape_writes_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        """In-project + no escape → existing behavior preserved (marker + msg)."""
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
        """In-project + env var → no marker + user-visible bypass warning."""
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
        """In-project + sentinel file → no marker + warning naming sentinel."""
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
# Global enforcement opt-in
# ============================================================================


class TestGlobalEnforcement:
    """AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT re-enables hook in foreign projects."""

    def test_global_enforcement_in_foreign_project_writes_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Foreign project + GLOBAL_ENFORCEMENT=1 → marker is written."""
        _clear_env(monkeypatch)
        monkeypatch.setenv("AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT", "1")
        monkeypatch.setattr(
            plan_mode_exit_detector, "_is_adev_project_fn", lambda: False
        )
        monkeypatch.chdir(tmp_path)

        result = _run_main({"tool_name": "ExitPlanMode"})

        assert result == 0
        assert (tmp_path / MARKER_PATH).exists(), (
            "GLOBAL_ENFORCEMENT must re-enable marker writes in foreign projects"
        )

    def test_escape_wins_over_global_enforcement(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        """Both env vars set → escape wins (no marker).

        Foreign project + escape = silent (no warning) per design.
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
        # Foreign project + escape = silent.
        captured = capsys.readouterr()
        assert captured.out == ""


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
