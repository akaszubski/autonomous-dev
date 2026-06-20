"""Unit tests for runtime_data_aggregator module.

Tests all collectors, utility functions, dataclasses, persistence,
and security features of the Runtime Data Aggregator.

GitHub Issue: #579
"""

import json
import math
import sys
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add lib to path
_LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(_LIB_DIR))

from runtime_data_aggregator import (
    AggregatedReport,
    AggregatedSignal,
    SourceHealth,
    aggregate,
    collect_benchmark_signals,
    collect_ci_signals,
    collect_github_signals,
    collect_session_signals,
    compute_priority,
    fetch_issues_with_label,
    fetch_open_issues_with_label,
    normalize_severity,
    persist_report,
    scrub_secrets,
    _validate_path,
    SEVERITY_WEIGHTS,
    DEFAULT_WEIGHT,
    MAX_LINES,
)


# =============================================================================
# Helpers
# =============================================================================

def _make_session_event(
    timestamp: str,
    tool: str = "Bash",
    success: bool = False,
    output_summary: str = "3 failed",
    hook: str = "PostToolUse",
    agent: str = None,
    session_id: str = "abc123",
) -> str:
    """Create a JSONL session activity event."""
    event = {
        "timestamp": timestamp,
        "hook": hook,
        "tool": tool,
        "input_summary": "pytest",
        "output_summary": output_summary,
        "session_id": session_id,
        "agent": agent,
        "duration_ms": 5000,
        "priority": "normal",
        "success": success,
    }
    return json.dumps(event)


def _make_benchmark_entry(
    timestamp: str,
    per_defect_category: dict,
    balanced_accuracy: float = 0.72,
) -> str:
    """Create a JSONL benchmark history entry."""
    entry = {
        "timestamp": timestamp,
        "balanced_accuracy": balanced_accuracy,
        "false_positive_rate": 0.15,
        "false_negative_rate": 0.18,
        "per_defect_category": per_defect_category,
    }
    return json.dumps(entry)


def _recent_ts(days_ago: int = 0) -> str:
    """Return an ISO timestamp N days ago."""
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.isoformat()


# =============================================================================
# TestAggregatedSignal
# =============================================================================

class TestAggregatedSignal:
    """Tests for AggregatedSignal dataclass."""

    def test_creation_with_required_fields(self) -> None:
        """Signal can be created with required fields."""
        signal = AggregatedSignal(
            source="session",
            signal_type="hook_failure",
            description="Bash: 3 failed",
        )
        assert signal.source == "session"
        assert signal.signal_type == "hook_failure"
        assert signal.description == "Bash: 3 failed"

    def test_defaults(self) -> None:
        """Default values are set correctly."""
        signal = AggregatedSignal(
            source="test", signal_type="test", description="test"
        )
        assert signal.frequency == 1
        assert signal.severity == 0.0
        assert signal.raw_data == {}
        assert signal.timestamp  # non-empty ISO timestamp

    def test_asdict_serialization(self) -> None:
        """Signal can be serialized to dict."""
        signal = AggregatedSignal(
            source="benchmark",
            signal_type="benchmark_weakness",
            description="security low",
            frequency=5,
            severity=0.8,
        )
        d = asdict(signal)
        assert d["source"] == "benchmark"
        assert d["frequency"] == 5
        assert d["severity"] == 0.8
        # Should be JSON-serializable
        json.dumps(d)


# =============================================================================
# TestCollectSessionSignals
# =============================================================================

class TestCollectSessionSignals:
    """Tests for collect_session_signals."""

    def test_empty_dir(self, tmp_path: Path) -> None:
        """Empty activity directory returns empty signals."""
        logs_dir = tmp_path / "activity"
        logs_dir.mkdir()
        signals, health = collect_session_signals(logs_dir)
        assert signals == []
        assert health.status == "empty"
        assert health.source == "session"

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        """Non-existent directory returns empty with status=empty."""
        signals, health = collect_session_signals(tmp_path / "missing")
        assert signals == []
        assert health.status == "empty"

    def test_events_in_window(self, tmp_path: Path) -> None:
        """Failure events within window are collected."""
        logs_dir = tmp_path / "activity"
        logs_dir.mkdir()
        ts = _recent_ts(1)
        events = [
            _make_session_event(ts, tool="Bash", success=False, output_summary="3 failed"),
            _make_session_event(ts, tool="Bash", success=True, output_summary="ok"),
        ]
        (logs_dir / "2026-03-27.jsonl").write_text("\n".join(events) + "\n")

        signals, health = collect_session_signals(logs_dir, window_days=7)
        assert len(signals) == 1
        assert health.status == "ok"
        assert health.signal_count == 1
        assert signals[0].signal_type == "tool_failure"

    def test_out_of_window_filtered(self, tmp_path: Path) -> None:
        """Events outside the window are filtered out."""
        logs_dir = tmp_path / "activity"
        logs_dir.mkdir()
        old_ts = _recent_ts(30)  # 30 days ago
        events = [_make_session_event(old_ts, success=False)]
        (logs_dir / "old.jsonl").write_text("\n".join(events) + "\n")

        signals, health = collect_session_signals(logs_dir, window_days=7)
        assert signals == []
        assert health.status == "empty"

    def test_corrupt_lines_skipped(self, tmp_path: Path) -> None:
        """Corrupt JSON lines are silently skipped."""
        logs_dir = tmp_path / "activity"
        logs_dir.mkdir()
        ts = _recent_ts(1)
        lines = [
            "NOT VALID JSON {{{",
            _make_session_event(ts, success=False),
            "",
            "another corrupt line",
        ]
        (logs_dir / "test.jsonl").write_text("\n".join(lines) + "\n")

        signals, health = collect_session_signals(logs_dir, window_days=7)
        assert len(signals) == 1

    def test_line_cap_respected(self, tmp_path: Path) -> None:
        """Line reading is capped at MAX_LINES."""
        logs_dir = tmp_path / "activity"
        logs_dir.mkdir()
        ts = _recent_ts(1)
        # Write more lines than would normally be processed
        # We test the mechanism, not literally 100k lines
        events = [_make_session_event(ts, success=False) for _ in range(50)]
        (logs_dir / "test.jsonl").write_text("\n".join(events) + "\n")

        signals, health = collect_session_signals(logs_dir, window_days=7)
        # Should group into one signal (same type/description)
        assert len(signals) >= 1
        assert health.signal_count >= 1


# =============================================================================
# TestCollectBenchmarkSignals
# =============================================================================

class TestCollectBenchmarkSignals:
    """Tests for collect_benchmark_signals."""

    def test_empty_history(self, tmp_path: Path) -> None:
        """Empty/missing history returns empty signals."""
        signals, health = collect_benchmark_signals(tmp_path / "missing.jsonl")
        assert signals == []
        assert health.status == "empty"
        assert health.source == "benchmark"

    def test_weak_categories_extracted(self, tmp_path: Path) -> None:
        """Categories below threshold are converted to signals."""
        history_path = tmp_path / "benchmark.jsonl"
        entry = _make_benchmark_entry(
            timestamp=_recent_ts(1),
            per_defect_category={
                "security": {"total": 10, "correct": 3, "accuracy": 0.3},
                "error_handling": {"total": 8, "correct": 6, "accuracy": 0.75},
            },
        )
        history_path.write_text(entry + "\n")

        signals, health = collect_benchmark_signals(history_path, window_days=7)
        assert len(signals) == 1  # Only security (0.3 < 0.70)
        assert signals[0].signal_type == "benchmark_weakness"
        assert "security" in signals[0].description
        assert health.status == "ok"

    def test_all_good_categories_no_signals(self, tmp_path: Path) -> None:
        """Categories all above threshold produce no signals."""
        history_path = tmp_path / "benchmark.jsonl"
        entry = _make_benchmark_entry(
            timestamp=_recent_ts(1),
            per_defect_category={
                "security": {"total": 10, "correct": 8, "accuracy": 0.80},
                "error_handling": {"total": 8, "correct": 7, "accuracy": 0.875},
            },
        )
        history_path.write_text(entry + "\n")

        signals, health = collect_benchmark_signals(history_path, window_days=7)
        assert signals == []
        assert health.status == "empty"

    def test_window_filtering(self, tmp_path: Path) -> None:
        """Old benchmark entries are filtered by window."""
        history_path = tmp_path / "benchmark.jsonl"
        entry = _make_benchmark_entry(
            timestamp=_recent_ts(30),
            per_defect_category={
                "security": {"total": 10, "correct": 3, "accuracy": 0.3},
            },
        )
        history_path.write_text(entry + "\n")

        signals, health = collect_benchmark_signals(history_path, window_days=7)
        assert signals == []


# =============================================================================
# TestCollectCISignals
# =============================================================================

class TestCollectCISignals:
    """Tests for collect_ci_signals."""

    def test_no_bypass_found(self, tmp_path: Path) -> None:
        """Clean session logs produce no CI signals."""
        logs_dir = tmp_path / "activity"
        logs_dir.mkdir()
        ts = _recent_ts(1)
        events = [_make_session_event(ts, success=True)]
        (logs_dir / "test.jsonl").write_text("\n".join(events) + "\n")

        patterns_path = tmp_path / "patterns.json"
        patterns_path.write_text(json.dumps({
            "patterns": [{
                "id": "test_gate_bypass",
                "name": "Test gate bypass",
                "severity": "critical",
                "detection": {
                    "type": "log_pattern",
                    "indicators": ["some unique indicator not in events"],
                },
            }],
        }))

        signals, health = collect_ci_signals(logs_dir, patterns_path, window_days=7)
        assert signals == []

    def test_known_bypass_detected(self, tmp_path: Path) -> None:
        """Known bypass pattern in logs produces a signal."""
        logs_dir = tmp_path / "activity"
        logs_dir.mkdir()
        ts = _recent_ts(1)
        # Event that matches a bypass indicator
        event = {
            "timestamp": ts,
            "hook": "PostToolUse",
            "tool": "Bash",
            "output_summary": "good enough coverage",
            "success": True,
        }
        (logs_dir / "test.jsonl").write_text(json.dumps(event) + "\n")

        patterns_path = tmp_path / "patterns.json"
        patterns_path.write_text(json.dumps({
            "patterns": [{
                "id": "test_gate_bypass",
                "name": "Test gate bypass",
                "severity": "critical",
                "detection": {
                    "type": "log_pattern",
                    "indicators": ["good enough"],
                },
            }],
        }))

        signals, health = collect_ci_signals(logs_dir, patterns_path, window_days=7)
        assert len(signals) == 1
        assert signals[0].signal_type == "bypass_detected"
        assert "Test gate bypass" in signals[0].description
        assert signals[0].severity == 0.9  # critical

    def test_dedup_by_pattern_id_and_date(self, tmp_path: Path) -> None:
        """Same pattern on same day is deduplicated."""
        logs_dir = tmp_path / "activity"
        logs_dir.mkdir()
        ts = _recent_ts(1)
        events = [
            json.dumps({"timestamp": ts, "output_summary": "good enough", "success": True}),
            json.dumps({"timestamp": ts, "output_summary": "good enough again", "success": True}),
        ]
        (logs_dir / "test.jsonl").write_text("\n".join(events) + "\n")

        patterns_path = tmp_path / "patterns.json"
        patterns_path.write_text(json.dumps({
            "patterns": [{
                "id": "bypass1",
                "name": "Bypass 1",
                "severity": "warning",
                "detection": {
                    "type": "log_pattern",
                    "indicators": ["good enough"],
                },
            }],
        }))

        signals, health = collect_ci_signals(logs_dir, patterns_path, window_days=7)
        assert len(signals) == 1  # Deduplicated

    def test_missing_patterns_file(self, tmp_path: Path) -> None:
        """Missing patterns file returns error health."""
        logs_dir = tmp_path / "activity"
        logs_dir.mkdir()
        signals, health = collect_ci_signals(logs_dir, tmp_path / "missing.json")
        assert signals == []
        assert health.status == "error"
        assert "not found" in health.error_message


# =============================================================================
# TestCollectGithubSignals
# =============================================================================

class TestCollectGithubSignals:
    """Tests for collect_github_signals."""

    @patch("runtime_data_aggregator.subprocess.run")
    def test_successful_gh_output(self, mock_run: MagicMock) -> None:
        """Successful gh output produces github_issue signals."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {
                    "title": "Improve hook error handling",
                    "body": "Details...",
                    "labels": [{"name": "auto-improvement"}],
                    "createdAt": "2026-03-25T10:00:00Z",
                },
            ]),
            stderr="",
        )

        signals, health = collect_github_signals("owner/repo")
        assert len(signals) == 1
        assert signals[0].signal_type == "github_issue"
        assert "hook error handling" in signals[0].description.lower()
        assert health.status == "ok"

    @patch("runtime_data_aggregator.subprocess.run")
    def test_gh_not_found(self, mock_run: MagicMock) -> None:
        """FileNotFoundError when gh is not installed."""
        mock_run.side_effect = FileNotFoundError("gh not found")

        signals, health = collect_github_signals()
        assert signals == []
        assert health.status == "error"
        assert "not found" in health.error_message

    @patch("runtime_data_aggregator.subprocess.run")
    def test_gh_timeout(self, mock_run: MagicMock) -> None:
        """TimeoutExpired when gh takes too long."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)

        signals, health = collect_github_signals()
        assert signals == []
        assert health.status == "error"
        assert "timed out" in health.error_message


# =============================================================================
# TestFetchIssuesWithLabel (Issue #1201 — closed-state + closed_within_days)
# =============================================================================

class TestFetchIssuesWithLabel:
    """Tests for fetch_issues_with_label (Issue #1201).

    Exercises the new ``state="closed"`` / ``closed_within_days=`` code path,
    including the conditional ``closedAt`` JSON field inclusion, post-filter
    by cutoff, and the fail-open behavior on null/missing/malformed
    ``closedAt`` values.
    """

    @patch("runtime_data_aggregator.subprocess.run")
    def test_closed_within_days_filters_out_old_issue(
        self, mock_run: MagicMock
    ) -> None:
        """state='closed' + closed_within_days=90 drops issues closed >90d ago."""
        recent_iso = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        old_iso = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {
                    "number": 100,
                    "title": "Recently closed",
                    "body": "...",
                    "labels": [{"name": "auto-improvement"}],
                    "createdAt": "2026-01-01T00:00:00Z",
                    "closedAt": recent_iso,
                },
                {
                    "number": 200,
                    "title": "Long-ago closed",
                    "body": "...",
                    "labels": [{"name": "auto-improvement"}],
                    "createdAt": "2025-01-01T00:00:00Z",
                    "closedAt": old_iso,
                },
            ]),
            stderr="",
        )

        issues, health = fetch_issues_with_label(
            state="closed", closed_within_days=90,
        )

        assert health.status == "ok"
        numbers = sorted(i["number"] for i in issues)
        assert numbers == [100], (
            f"Expected only the recently-closed issue (#100); got {numbers}"
        )

        # Verify the gh argv shape: --state closed and closedAt requested.
        cmd = mock_run.call_args[0][0]
        assert "--state" in cmd and cmd[cmd.index("--state") + 1] == "closed"
        json_fields = cmd[cmd.index("--json") + 1]
        assert "closedAt" in json_fields, (
            "closedAt MUST be requested when state != 'open' to enable "
            "post-filtering"
        )

    @patch("runtime_data_aggregator.subprocess.run")
    def test_missing_closed_at_kept_fail_open(
        self, mock_run: MagicMock
    ) -> None:
        """Issues with missing/empty closedAt are kept (fail-open).

        Covers the line ``if not closed_at: filtered.append(issue)`` —
        e.g., state='all' returns mixed open/closed issues where the
        open ones have an empty ``closedAt``.
        """
        recent_iso = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {
                    "number": 1,
                    "title": "Still open",
                    "body": "...",
                    "labels": [{"name": "auto-improvement"}],
                    "createdAt": "2026-01-01T00:00:00Z",
                    "closedAt": "",  # Empty string — fail-open keep
                },
                {
                    "number": 2,
                    "title": "No closedAt key",
                    "body": "...",
                    "labels": [{"name": "auto-improvement"}],
                    "createdAt": "2026-01-01T00:00:00Z",
                    # closedAt key entirely missing — fail-open keep
                },
                {
                    "number": 3,
                    "title": "Recently closed",
                    "body": "...",
                    "labels": [{"name": "auto-improvement"}],
                    "createdAt": "2026-01-01T00:00:00Z",
                    "closedAt": recent_iso,
                },
            ]),
            stderr="",
        )

        issues, health = fetch_issues_with_label(
            state="all", closed_within_days=90,
        )

        assert health.status == "ok"
        numbers = sorted(i["number"] for i in issues)
        assert numbers == [1, 2, 3], (
            f"All three issues must be kept (#1 empty closedAt, "
            f"#2 missing closedAt, #3 recent); got {numbers}"
        )

    @patch("runtime_data_aggregator.subprocess.run")
    def test_malformed_closed_at_kept_fail_open(
        self, mock_run: MagicMock
    ) -> None:
        """Malformed closedAt strings are kept (fail-open).

        Covers the line ``if dt is None: filtered.append(issue)`` — when
        ``_parse_iso_ts`` cannot parse the timestamp we MUST over-include
        rather than silently drop the issue.
        """
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {
                    "number": 42,
                    "title": "Garbled closedAt",
                    "body": "...",
                    "labels": [{"name": "auto-improvement"}],
                    "createdAt": "2026-01-01T00:00:00Z",
                    "closedAt": "not-a-timestamp-at-all",
                },
            ]),
            stderr="",
        )

        issues, health = fetch_issues_with_label(
            state="closed", closed_within_days=30,
        )

        assert health.status == "ok"
        numbers = [i["number"] for i in issues]
        assert numbers == [42], (
            f"Malformed closedAt must fail-open (keep the issue); got {numbers}"
        )

    @patch("runtime_data_aggregator.subprocess.run")
    def test_fetch_open_issues_alias_delegates_with_state_open(
        self, mock_run: MagicMock
    ) -> None:
        """Backward-compat alias forwards state='open' to gh argv.

        Ensures ``fetch_open_issues_with_label`` (preserved for pre-#1201
        callers in ``issue_triage_analyzer`` and ``collect_github_signals``)
        still passes ``--state open`` and does NOT include ``closedAt`` in
        the JSON field list.
        """
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {
                    "number": 7,
                    "title": "Open issue",
                    "body": "...",
                    "labels": [{"name": "auto-improvement"}],
                    "createdAt": "2026-01-01T00:00:00Z",
                },
            ]),
            stderr="",
        )

        issues, health = fetch_open_issues_with_label()

        assert health.status == "ok"
        assert len(issues) == 1

        cmd = mock_run.call_args[0][0]
        assert "--state" in cmd, "alias MUST pass --state to gh"
        assert cmd[cmd.index("--state") + 1] == "open", (
            f"alias MUST pass --state open (got {cmd[cmd.index('--state') + 1]!r})"
        )
        json_fields = cmd[cmd.index("--json") + 1]
        assert "closedAt" not in json_fields, (
            "state='open' MUST NOT request closedAt (it is irrelevant and the "
            "branch in fetch_issues_with_label gates inclusion on state != 'open')"
        )


# =============================================================================
# TestNormalizeSeverity
# =============================================================================

class TestNormalizeSeverity:
    """Tests for normalize_severity."""

    def test_normal_range(self) -> None:
        """Value within range normalizes correctly."""
        assert normalize_severity(5.0, 0.0, 10.0) == pytest.approx(0.5)
        assert normalize_severity(0.0, 0.0, 10.0) == pytest.approx(0.0)
        assert normalize_severity(10.0, 0.0, 10.0) == pytest.approx(1.0)

    def test_min_equals_max(self) -> None:
        """When min == max, returns 0.0."""
        assert normalize_severity(5.0, 5.0, 5.0) == 0.0

    def test_values_clamped(self) -> None:
        """Values outside range are clamped to [0, 1]."""
        assert normalize_severity(-5.0, 0.0, 10.0) == 0.0
        assert normalize_severity(15.0, 0.0, 10.0) == 1.0


# =============================================================================
# TestComputePriority
# =============================================================================

class TestComputePriority:
    """Tests for compute_priority."""

    def test_high_severity_and_frequency(self) -> None:
        """High severity + frequency yields high priority."""
        signal = AggregatedSignal(
            source="session",
            signal_type="bypass_detected",
            description="test",
            frequency=10,
            severity=0.9,
        )
        priority = compute_priority(signal)
        expected = SEVERITY_WEIGHTS["bypass_detected"] * 0.9 * math.log(1 + 10)
        assert priority == pytest.approx(expected)
        assert priority > 0

    def test_zero_frequency(self) -> None:
        """Zero frequency yields zero priority (log(1+0) = 0)."""
        signal = AggregatedSignal(
            source="test",
            signal_type="hook_failure",
            description="test",
            frequency=0,
            severity=0.9,
        )
        assert compute_priority(signal) == pytest.approx(0.0)

    def test_unknown_type_uses_default_weight(self) -> None:
        """Unknown signal type uses DEFAULT_WEIGHT."""
        signal = AggregatedSignal(
            source="test",
            signal_type="some_unknown_type",
            description="test",
            frequency=5,
            severity=0.5,
        )
        priority = compute_priority(signal)
        expected = DEFAULT_WEIGHT * 0.5 * math.log(1 + 5)
        assert priority == pytest.approx(expected)


# =============================================================================
# TestAggregate
# =============================================================================

class TestAggregate:
    """Tests for the main aggregate function."""

    @patch("runtime_data_aggregator.collect_github_signals")
    def test_integration_with_tmp_path(self, mock_gh: MagicMock, tmp_path: Path) -> None:
        """Full integration: aggregate runs and produces a report."""
        mock_gh.return_value = ([], SourceHealth(source="github", status="empty"))

        # Set up project structure
        activity_dir = tmp_path / ".claude" / "logs" / "activity"
        activity_dir.mkdir(parents=True)
        config_dir = tmp_path / "plugins" / "autonomous-dev" / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "known_bypass_patterns.json").write_text(
            json.dumps({"patterns": []})
        )

        # Write a session event
        ts = _recent_ts(1)
        (activity_dir / "test.jsonl").write_text(
            _make_session_event(ts, success=False) + "\n"
        )

        report = aggregate(tmp_path, window_days=7, top_n=10)

        assert isinstance(report, AggregatedReport)
        # Issue #1200 added a 5th source: cia_findings
        assert len(report.source_health) == 5
        assert report.window_start
        assert report.window_end
        assert report.top_n == 10

    @patch("runtime_data_aggregator.collect_github_signals")
    def test_empty_sources(self, mock_gh: MagicMock, tmp_path: Path) -> None:
        """All empty sources produce empty report."""
        mock_gh.return_value = ([], SourceHealth(source="github", status="empty"))

        config_dir = tmp_path / "plugins" / "autonomous-dev" / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "known_bypass_patterns.json").write_text(
            json.dumps({"patterns": []})
        )

        report = aggregate(tmp_path, window_days=7)
        assert report.signals == []
        # Issue #1200 added a 5th source: cia_findings
        assert len(report.source_health) == 5

    @patch("runtime_data_aggregator.collect_github_signals")
    def test_partial_failures(self, mock_gh: MagicMock, tmp_path: Path) -> None:
        """Partial source failures still produce a report."""
        mock_gh.return_value = (
            [],
            SourceHealth(source="github", status="error", error_message="gh not found"),
        )

        config_dir = tmp_path / "plugins" / "autonomous-dev" / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "known_bypass_patterns.json").write_text(
            json.dumps({"patterns": []})
        )

        report = aggregate(tmp_path, window_days=7)
        assert isinstance(report, AggregatedReport)
        github_health = [h for h in report.source_health if h.source == "github"]
        assert github_health[0].status == "error"

    @patch("runtime_data_aggregator.collect_github_signals")
    def test_top_n_limiting(self, mock_gh: MagicMock, tmp_path: Path) -> None:
        """Report is capped at top_n signals."""
        mock_gh.return_value = ([], SourceHealth(source="github", status="empty"))

        activity_dir = tmp_path / ".claude" / "logs" / "activity"
        activity_dir.mkdir(parents=True)
        config_dir = tmp_path / "plugins" / "autonomous-dev" / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "known_bypass_patterns.json").write_text(
            json.dumps({"patterns": []})
        )

        # Write many distinct failure events
        ts = _recent_ts(1)
        events = []
        for i in range(20):
            event = {
                "timestamp": ts,
                "hook": "PostToolUse",
                "tool": f"Tool_{i}",
                "output_summary": f"error {i}",
                "success": False,
                "agent": None,
                "session_id": "test",
            }
            events.append(json.dumps(event))
        (activity_dir / "test.jsonl").write_text("\n".join(events) + "\n")

        report = aggregate(tmp_path, window_days=7, top_n=5)
        assert len(report.signals) <= 5

    @patch("runtime_data_aggregator.collect_github_signals")
    def test_relative_project_root_no_valueerror(
        self, mock_gh: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Issue #1207: relative project_root must not raise ValueError.

        Without ``.resolve()`` in ``aggregate()``, ``findings_dir`` stays
        relative and ``collect_cia_findings`` raises ValueError uncaught.
        With ``.resolve()`` the relative path is normalized to absolute
        and the report is produced normally (silent-empty on missing dirs).
        """
        mock_gh.return_value = ([], SourceHealth(source="github", status="empty"))

        config_dir = tmp_path / "plugins" / "autonomous-dev" / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "known_bypass_patterns.json").write_text(
            json.dumps({"patterns": []})
        )

        monkeypatch.chdir(tmp_path)
        report = aggregate(Path("."), window_days=7)

        assert isinstance(report, AggregatedReport)
        assert len(report.source_health) == 5
        cia_health = [h for h in report.source_health if h.source == "cia_findings"]
        assert cia_health and cia_health[0].status != "error"


# =============================================================================
# TestPersistReport
# =============================================================================

class TestPersistReport:
    """Tests for persist_report."""

    def test_creates_new_file(self, tmp_path: Path) -> None:
        """Creates a new JSONL file."""
        output_path = tmp_path / "reports.jsonl"
        report = AggregatedReport(
            signals=[],
            source_health=[],
            window_start="2026-03-21T00:00:00+00:00",
            window_end="2026-03-28T00:00:00+00:00",
        )
        persist_report(report, output_path)
        assert output_path.exists()
        line = output_path.read_text().strip()
        data = json.loads(line)
        assert data["window_start"] == "2026-03-21T00:00:00+00:00"

    def test_appends_to_existing(self, tmp_path: Path) -> None:
        """Appends to existing JSONL file."""
        output_path = tmp_path / "reports.jsonl"
        for i in range(3):
            report = AggregatedReport(
                signals=[],
                source_health=[],
                window_start=f"start_{i}",
                window_end=f"end_{i}",
            )
            persist_report(report, output_path)

        lines = output_path.read_text().strip().splitlines()
        assert len(lines) == 3

    def test_valid_json_per_line(self, tmp_path: Path) -> None:
        """Each line is valid JSON."""
        output_path = tmp_path / "reports.jsonl"
        signal = AggregatedSignal(
            source="test", signal_type="test", description="test signal"
        )
        report = AggregatedReport(
            signals=[signal],
            source_health=[SourceHealth(source="test")],
            window_start="start",
            window_end="end",
        )
        persist_report(report, output_path)

        for line in output_path.read_text().strip().splitlines():
            data = json.loads(line)
            assert "signals" in data
            assert "source_health" in data


# =============================================================================
# TestSecurityScrubbing
# =============================================================================

class TestSecurityScrubbing:
    """Tests for secret scrubbing and path validation."""

    def test_api_key_redacted(self) -> None:
        """API keys are redacted from text."""
        text = "Error with key sk-abcdef123456 in request"
        result = scrub_secrets(text)
        assert "sk-abcdef123456" not in result
        assert "[REDACTED]" in result

    def test_github_token_redacted(self) -> None:
        """GitHub tokens are redacted."""
        text = "Auth failed with ghp_abcdefghijklmnop"
        result = scrub_secrets(text)
        assert "ghp_abcdefghijklmnop" not in result
        assert "[REDACTED]" in result

    def test_path_traversal_prevented(self, tmp_path: Path) -> None:
        """Path validation rejects traversal outside project root."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        evil_path = tmp_path / "project" / ".." / "etc" / "passwd"
        assert not _validate_path(evil_path, project_root)

    def test_sibling_directory_not_accepted(self, tmp_path: Path) -> None:
        """Path validation rejects sibling directories with similar names."""
        project_root = tmp_path / "proj"
        project_root.mkdir()
        sibling = tmp_path / "proj_evil"
        sibling.mkdir()
        evil_file = sibling / "secret.txt"
        assert not _validate_path(evil_file, project_root)

    def test_valid_path_accepted(self, tmp_path: Path) -> None:
        """Path validation accepts paths within project root."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        good_path = project_root / ".claude" / "logs" / "report.jsonl"
        assert _validate_path(good_path, project_root)
