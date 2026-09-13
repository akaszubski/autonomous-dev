"""Unit tests for enforce_prunable_threshold.py pre-commit hook -- Issue #863.

Tests the pre-commit hook that blocks commits when prunable test count
exceeds the configured threshold.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"))
sys.path.insert(0, str(REPO_ROOT / "plugins" / "autonomous-dev" / "lib"))


def _make_findings(count: int, prunable: bool = True) -> list:
    """Create a list of mock pruning findings."""
    findings = []
    for i in range(count):
        f = MagicMock()
        f.prunable = prunable
        findings.append(f)
    return findings


def _make_report(prunable_count: int, non_prunable_count: int = 0) -> MagicMock:
    """Create a mock PruningReport."""
    report = MagicMock()
    report.findings = (
        _make_findings(prunable_count, prunable=True)
        + _make_findings(non_prunable_count, prunable=False)
    )
    return report


class TestBelowThreshold:
    """Tests for counts at or below threshold (should pass)."""

    @patch("enforce_prunable_threshold.count_prunable")
    @patch("enforce_prunable_threshold.get_project_root")
    def test_below_threshold_passes(self, mock_root, mock_count):
        """50 prunable findings -- below threshold of 100 -- should exit 0."""
        mock_root.return_value = Path("/fake/project")
        mock_count.return_value = 50
        from enforce_prunable_threshold import main
        assert main() == 0

    @patch("enforce_prunable_threshold.count_prunable")
    @patch("enforce_prunable_threshold.get_project_root")
    def test_at_threshold_passes(self, mock_root, mock_count):
        """Exactly 100 prunable findings -- equal to threshold -- should exit 0 (> not >=)."""
        mock_root.return_value = Path("/fake/project")
        mock_count.return_value = 100
        from enforce_prunable_threshold import main
        assert main() == 0

    @patch("enforce_prunable_threshold.count_prunable")
    @patch("enforce_prunable_threshold.get_project_root")
    def test_zero_findings_passes(self, mock_root, mock_count):
        """Zero prunable findings should exit 0."""
        mock_root.return_value = Path("/fake/project")
        mock_count.return_value = 0
        from enforce_prunable_threshold import main
        assert main() == 0


class TestAboveThreshold:
    """Tests for counts above threshold (should block)."""

    @patch("enforce_prunable_threshold.count_prunable")
    @patch("enforce_prunable_threshold.get_project_root")
    def test_above_threshold_blocks(self, mock_root, mock_count):
        """150 prunable findings -- above threshold -- should exit 2."""
        mock_root.return_value = Path("/fake/project")
        mock_count.return_value = 150
        from enforce_prunable_threshold import main
        assert main() == 2

    @patch("enforce_prunable_threshold.count_prunable")
    @patch("enforce_prunable_threshold.get_project_root")
    def test_one_above_threshold_blocks(self, mock_root, mock_count):
        """101 prunable findings (one above threshold) should exit 2."""
        mock_root.return_value = Path("/fake/project")
        mock_count.return_value = 101
        from enforce_prunable_threshold import main
        assert main() == 2

    @patch("enforce_prunable_threshold.count_prunable")
    @patch("enforce_prunable_threshold.get_project_root")
    def test_block_message_includes_next_action(self, mock_root, mock_count, capsys):
        """Blocking message must contain REQUIRED NEXT ACTION (stick+carrot pattern)."""
        mock_root.return_value = Path("/fake/project")
        mock_count.return_value = 150
        from enforce_prunable_threshold import main
        main()
        captured = capsys.readouterr()
        assert "REQUIRED NEXT ACTION" in captured.err

    @patch("enforce_prunable_threshold.count_prunable")
    @patch("enforce_prunable_threshold.get_project_root")
    def test_block_message_includes_sweep_command(self, mock_root, mock_count, capsys):
        """Blocking message must reference /sweep --tests --prune."""
        mock_root.return_value = Path("/fake/project")
        mock_count.return_value = 200
        from enforce_prunable_threshold import main
        main()
        captured = capsys.readouterr()
        assert "/sweep --tests --prune" in captured.err


class TestGracefulDegradation:
    """Tests for graceful degradation on errors."""

    @patch("enforce_prunable_threshold.get_project_root")
    def test_analyzer_exception_graceful_degradation(self, mock_root):
        """If count_prunable raises RuntimeError, should exit 0 (graceful degradation)."""
        mock_root.return_value = Path("/fake/project")
        with patch("enforce_prunable_threshold.count_prunable", side_effect=RuntimeError("analyzer failed")):
            from enforce_prunable_threshold import main
            assert main() == 0

    @patch("enforce_prunable_threshold.get_project_root")
    def test_analyzer_exception_logs_to_stderr(self, mock_root, capsys):
        """If count_prunable raises, a diagnostic message must appear on stderr."""
        mock_root.return_value = Path("/fake/project")
        with patch("enforce_prunable_threshold.count_prunable", side_effect=RuntimeError("unexpected crash")):
            from enforce_prunable_threshold import main
            main()
        captured = capsys.readouterr()
        assert "enforce_prunable_threshold" in captured.err
        assert "analyzer error" in captured.err

    @patch("enforce_prunable_threshold.get_project_root")
    def test_no_project_root_passes(self, mock_root):
        """If get_project_root returns None, should exit 0."""
        mock_root.return_value = None
        from enforce_prunable_threshold import main
        assert main() == 0


class TestSkipEnvVar:
    """Tests for the SKIP_PRUNABLE_GATE environment variable."""

    @patch("enforce_prunable_threshold.count_prunable")
    @patch("enforce_prunable_threshold.get_project_root")
    def test_skip_env_var(self, mock_root, mock_count, monkeypatch):
        """SKIP_PRUNABLE_GATE=1 should exit 0 regardless of prunable count."""
        monkeypatch.setenv("SKIP_PRUNABLE_GATE", "1")
        mock_root.return_value = Path("/fake/project")
        mock_count.return_value = 9999  # Way above threshold
        from enforce_prunable_threshold import main
        assert main() == 0

    @patch("enforce_prunable_threshold.count_prunable")
    @patch("enforce_prunable_threshold.get_project_root")
    def test_no_skip_env_var_enforces(self, mock_root, mock_count, monkeypatch):
        """Without SKIP_PRUNABLE_GATE, gate should enforce normally."""
        monkeypatch.delenv("SKIP_PRUNABLE_GATE", raising=False)
        mock_root.return_value = Path("/fake/project")
        mock_count.return_value = 150
        from enforce_prunable_threshold import main
        assert main() == 2


class TestThresholdConstant:
    """Tests verifying the hook uses PRUNABLE_THRESHOLD from test_lifecycle_manager."""

    def test_uses_prunable_threshold_constant(self):
        """Hook must import PRUNABLE_THRESHOLD from test_lifecycle_manager."""
        import importlib
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "test_lifecycle_manager_check",
            str(REPO_ROOT / "plugins" / "autonomous-dev" / "lib" / "test_lifecycle_manager.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        # Don't exec — just verify the attribute exists at module level by reading source
        source = (REPO_ROOT / "plugins" / "autonomous-dev" / "lib" / "test_lifecycle_manager.py").read_text()
        assert "PRUNABLE_THRESHOLD" in source, "PRUNABLE_THRESHOLD constant must exist in test_lifecycle_manager.py"

        # Verify hook imports it (not a hardcoded value)
        hook_source = (
            REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "enforce_prunable_threshold.py"
        ).read_text()
        assert "from test_lifecycle_manager import PRUNABLE_THRESHOLD" in hook_source, (
            "Hook must import PRUNABLE_THRESHOLD from test_lifecycle_manager, not hardcode it"
        )


class TestCountPrunable:
    """Tests for the count_prunable helper function."""

    def test_count_prunable_filters_prunable_true(self):
        """count_prunable should only count findings where prunable=True."""
        mock_analyzer = MagicMock()
        mock_report = _make_report(prunable_count=3, non_prunable_count=5)
        mock_analyzer.analyze.return_value = mock_report

        with patch("enforce_prunable_threshold.TestPruningAnalyzer", return_value=mock_analyzer):
            from enforce_prunable_threshold import count_prunable
            result = count_prunable(Path("/fake/project"))

        assert result == 3  # Only counts prunable=True findings
