"""Tests for plan_mode_exit_detector.py PostToolUse hook."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks directory to path for direct import
HOOKS_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

import plan_mode_exit_detector
from plan_mode_exit_detector import main, MARKER_PATH


@pytest.fixture(autouse=True)
def _force_in_adev_project(monkeypatch):
    """Issue #938: existing tests assume in-project context.

    The scope gate added by Issue #938 means tmp_path (a foreign project)
    would otherwise short-circuit before writing the marker. Patch the
    detector wrapper to True so legacy tests keep exercising in-project
    behavior. Scope/escape variants are covered in
    test_plan_exit_scope_check.py.
    """
    monkeypatch.setattr(
        plan_mode_exit_detector, "_is_adev_project_fn", lambda: True
    )
    # Ensure no escape-hatch env vars leak in from the developer's shell.
    for var in (
        "AUTONOMOUS_DEV_SKIP_PLAN_REVIEW",
        "AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT",
    ):
        monkeypatch.delenv(var, raising=False)


class TestPlanModeExitDetector:
    """Test marker file writing on ExitPlanMode tool use."""

    def test_exit_plan_mode_writes_marker(self, tmp_path: Path):
        """ExitPlanMode tool should create marker file."""
        input_data = json.dumps({"tool_name": "ExitPlanMode"})
        with (
            patch("sys.stdin") as mock_stdin,
            patch("os.getcwd", return_value=str(tmp_path)),
        ):
            mock_stdin.read.return_value = input_data
            result = main()

        assert result == 0
        marker_file = tmp_path / MARKER_PATH
        assert marker_file.exists()
        marker_data = json.loads(marker_file.read_text())
        assert "timestamp" in marker_data
        assert "session_id" in marker_data

    def test_non_exit_plan_mode_no_marker(self, tmp_path: Path):
        """Other tool names should not create marker."""
        input_data = json.dumps({"tool_name": "Write"})
        with (
            patch("sys.stdin") as mock_stdin,
            patch("os.getcwd", return_value=str(tmp_path)),
        ):
            mock_stdin.read.return_value = input_data
            result = main()

        assert result == 0
        marker_file = tmp_path / MARKER_PATH
        assert not marker_file.exists()

    def test_marker_includes_session_id(self, tmp_path: Path):
        """Marker should capture CLAUDE_SESSION_ID from environment."""
        input_data = json.dumps({"tool_name": "ExitPlanMode"})
        with (
            patch("sys.stdin") as mock_stdin,
            patch("os.getcwd", return_value=str(tmp_path)),
            patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test-session-42"}),
        ):
            mock_stdin.read.return_value = input_data
            main()

        marker_data = json.loads((tmp_path / MARKER_PATH).read_text())
        assert marker_data["session_id"] == "test-session-42"

    def test_missing_session_id_defaults_unknown(self, tmp_path: Path):
        """Missing CLAUDE_SESSION_ID should default to 'unknown'."""
        input_data = json.dumps({"tool_name": "ExitPlanMode"})
        env = os.environ.copy()
        env.pop("CLAUDE_SESSION_ID", None)
        with (
            patch("sys.stdin") as mock_stdin,
            patch("os.getcwd", return_value=str(tmp_path)),
            patch.dict(os.environ, env, clear=True),
        ):
            mock_stdin.read.return_value = input_data
            main()

        marker_data = json.loads((tmp_path / MARKER_PATH).read_text())
        assert marker_data["session_id"] == "unknown"

    def test_invalid_json_input_returns_zero(self):
        """Invalid JSON input should not crash, returns 0."""
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = "not valid json"
            result = main()

        assert result == 0

    def test_empty_tool_name_no_marker(self, tmp_path: Path):
        """Empty tool_name should not create marker."""
        input_data = json.dumps({"tool_name": ""})
        with (
            patch("sys.stdin") as mock_stdin,
            patch("os.getcwd", return_value=str(tmp_path)),
        ):
            mock_stdin.read.return_value = input_data
            result = main()

        assert result == 0
        assert not (tmp_path / MARKER_PATH).exists()

    def test_missing_tool_name_no_marker(self, tmp_path: Path):
        """Missing tool_name key should not create marker."""
        input_data = json.dumps({"other_key": "value"})
        with (
            patch("sys.stdin") as mock_stdin,
            patch("os.getcwd", return_value=str(tmp_path)),
        ):
            mock_stdin.read.return_value = input_data
            result = main()

        assert result == 0
        assert not (tmp_path / MARKER_PATH).exists()

    def test_creates_parent_directories(self, tmp_path: Path):
        """Should create .claude/ directory if it doesn't exist."""
        input_data = json.dumps({"tool_name": "ExitPlanMode"})
        # Ensure .claude doesn't exist
        assert not (tmp_path / ".claude").exists()
        with (
            patch("sys.stdin") as mock_stdin,
            patch("os.getcwd", return_value=str(tmp_path)),
        ):
            mock_stdin.read.return_value = input_data
            main()

        assert (tmp_path / ".claude").exists()
        assert (tmp_path / MARKER_PATH).exists()

    def test_exit_plan_mode_captures_tool_response(self, tmp_path: Path):
        """ExitPlanMode should capture plan content from tool_response."""
        input_data = json.dumps({
            "tool_name": "ExitPlanMode",
            "tool_response": {"plan": "## Phase 1\nBuild the thing\n## Phase 2\nTest the thing"}
        })
        with (
            patch("sys.stdin") as mock_stdin,
            patch("os.getcwd", return_value=str(tmp_path)),
        ):
            mock_stdin.read.return_value = input_data
            main()

        marker_data = json.loads((tmp_path / MARKER_PATH).read_text())
        assert "plan_content" in marker_data
        assert "Phase 1" in marker_data["plan_content"]

    def test_exit_plan_mode_no_tool_response_omits_plan_content(self, tmp_path: Path):
        """Missing tool_response should not include plan_content field."""
        input_data = json.dumps({"tool_name": "ExitPlanMode"})
        with (
            patch("sys.stdin") as mock_stdin,
            patch("os.getcwd", return_value=str(tmp_path)),
        ):
            mock_stdin.read.return_value = input_data
            main()

        marker_data = json.loads((tmp_path / MARKER_PATH).read_text())
        assert "plan_content" not in marker_data

    def test_plan_content_truncated_at_10k(self, tmp_path: Path):
        """Plan content should be truncated to 10,000 characters."""
        long_plan = "x" * 15000
        input_data = json.dumps({
            "tool_name": "ExitPlanMode",
            "tool_response": {"plan": long_plan}
        })
        with (
            patch("sys.stdin") as mock_stdin,
            patch("os.getcwd", return_value=str(tmp_path)),
        ):
            mock_stdin.read.return_value = input_data
            main()

        marker_data = json.loads((tmp_path / MARKER_PATH).read_text())
        assert len(marker_data["plan_content"]) == 10000

    def test_exit_plan_mode_captures_string_tool_response(self, tmp_path: Path):
        """String tool_response should be captured as plan_content."""
        input_data = json.dumps({
            "tool_name": "ExitPlanMode",
            "tool_response": "Plan: build feature X then test it"
        })
        with (
            patch("sys.stdin") as mock_stdin,
            patch("os.getcwd", return_value=str(tmp_path)),
        ):
            mock_stdin.read.return_value = input_data
            main()

        marker_data = json.loads((tmp_path / MARKER_PATH).read_text())
        assert "plan_content" in marker_data
        assert "build feature X" in marker_data["plan_content"]

    def test_exit_plan_mode_captures_content_field(self, tmp_path: Path):
        """tool_response with 'content' field (no 'plan') should be captured."""
        input_data = json.dumps({
            "tool_name": "ExitPlanMode",
            "tool_response": {"content": "Detailed plan content here"}
        })
        with (
            patch("sys.stdin") as mock_stdin,
            patch("os.getcwd", return_value=str(tmp_path)),
        ):
            mock_stdin.read.return_value = input_data
            main()

        marker_data = json.loads((tmp_path / MARKER_PATH).read_text())
        assert "plan_content" in marker_data
        assert "Detailed plan content here" in marker_data["plan_content"]

    def test_marker_includes_stage_field(self, tmp_path: Path):
        """Marker should include stage='plan_exited' field."""
        input_data = json.dumps({"tool_name": "ExitPlanMode"})
        with (
            patch("sys.stdin") as mock_stdin,
            patch("os.getcwd", return_value=str(tmp_path)),
        ):
            mock_stdin.read.return_value = input_data
            main()

        marker_data = json.loads((tmp_path / MARKER_PATH).read_text())
        assert marker_data["stage"] == "plan_exited"

    def test_outputs_system_message_json(self, tmp_path: Path, capsys):
        """ExitPlanMode should output JSON with systemMessage for plan-critic trigger."""
        input_data = json.dumps({"tool_name": "ExitPlanMode"})
        with (
            patch("sys.stdin") as mock_stdin,
            patch("os.getcwd", return_value=str(tmp_path)),
        ):
            mock_stdin.read.return_value = input_data
            main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "systemMessage" in output
        assert "plan-critic" in output["systemMessage"].lower()
        assert "hookSpecificOutput" in output
