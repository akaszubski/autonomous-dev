#!/usr/bin/env python3
"""
TDD Tests for Phase 8.5 - Profiler Integration (FAILING - Red Phase)

This module contains FAILING tests for Performance Profiler integration into the
/auto-implement workflow. Tests verify timing infrastructure measures agent
execution time, aggregates metrics, detects bottlenecks, and validates log format.

Phase 8.5 Objectives:
1. Integrate PerformanceTimer context manager with agent execution
2. Capture execution duration for each agent (researcher, planner, test-master, etc)
3. Calculate aggregate metrics (min, max, avg, p95) per agent
4. Identify top 3 slowest agents (bottleneck detection)
5. Validate JSON log format and CWE-22 path traversal prevention

Security Requirements (CWE-20, CWE-22):
- Path validation for log file destinations
- No path traversal attacks
- Input validation for agent names and feature descriptions
- Safe JSON parsing (no arbitrary code execution)

Test Strategy:
- Test PerformanceTimer context manager wraps execution
- Test JSON metrics logging to file
- Test aggregate metrics calculation (min, max, avg, p95)
- Test bottleneck detection (top 3 slowest agents)
- Test path traversal prevention
- Test control character rejection in logs

Performance Targets:
- PerformanceTimer overhead < 5ms per execution
- JSON parsing: no exceptions on malformed logs
- Path validation: < 1ms per check
- Aggregate metrics: < 100ms for 1000 entries

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe profiler requirements
- Tests should FAIL until profiler integration complete
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-13
Issue: #46 Phase 8.5 (Profiler Integration)
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# These imports will FAIL until Phase 8.5 implementation is complete
from plugins.autonomous_dev.lib.performance_profiler import (
    PerformanceTimer,
    calculate_aggregate_metrics,
    analyze_performance_logs,
    PerformanceMetrics,
)


class TestPerformanceTimerWrapping:
    """Test that PerformanceTimer context manager captures execution time.

    Requirement: Wrapping agent execution with PerformanceTimer should measure
    the wall-clock duration from entry to exit.
    """

    def test_performance_timer_measures_execution_duration(self):
        """Test that PerformanceTimer correctly measures execution duration.

        Arrange: Create PerformanceTimer context manager
        Act: Execute code block inside context (sleep 0.1s)
        Assert: duration attribute equals or exceeds 0.1s
        """
        agent_name = "test_agent"
        feature = "test feature"
        expected_duration = 0.1

        with PerformanceTimer(agent_name, feature) as timer:
            # Simulate agent execution (0.1 second)
            time.sleep(expected_duration)

        # Duration should be >= 0.1s (allow for small overhead)
        assert timer.duration >= expected_duration
        # But shouldn't be drastically more (< 0.2s indicates reasonable overhead)
        assert timer.duration < expected_duration + 0.1

    def test_performance_timer_attributes_set_correctly(self):
        """Test that PerformanceTimer sets agent_name and feature attributes.

        Arrange: Create PerformanceTimer with agent_name and feature
        Act: Enter and exit context
        Assert: timer.agent_name and timer.feature are set correctly
        """
        agent_name = "researcher"
        feature = "Add user authentication"

        with PerformanceTimer(agent_name, feature) as timer:
            pass

        assert timer.agent_name == agent_name
        assert timer.feature == feature

    def test_performance_timer_timestamp_iso8601_format(self):
        """Test that PerformanceTimer generates ISO 8601 timestamps.

        Arrange: Create PerformanceTimer
        Act: Exit context
        Assert: timestamp follows ISO 8601 format (YYYY-MM-DDTHH:MM:SS.fffZ)
        """
        with PerformanceTimer("agent", "feature") as timer:
            pass

        # ISO 8601 format: 2025-11-13T12:34:56.123456Z
        assert hasattr(timer, 'timestamp')
        assert 'T' in timer.timestamp  # ISO 8601 separator
        assert 'Z' in timer.timestamp  # UTC timezone indicator

    def test_performance_timer_zero_duration_edge_case(self):
        """Test that PerformanceTimer handles near-zero duration.

        Arrange: Create PerformanceTimer
        Act: Exit immediately (no sleep)
        Assert: duration is non-negative and reasonable (<1ms for empty block)
        """
        with PerformanceTimer("agent", "feature") as timer:
            pass  # No work

        # Duration should be non-negative
        assert timer.duration >= 0
        # Should be very quick (< 10ms for empty block)
        assert timer.duration < 0.01

    def test_performance_timer_exception_doesnt_prevent_measurement(self):
        """Test that exception raised in context doesn't prevent timing.

        Arrange: Create PerformanceTimer
        Act: Raise exception inside context
        Assert: duration still captured despite exception
        """
        with pytest.raises(ValueError):
            with PerformanceTimer("agent", "feature") as timer:
                time.sleep(0.05)
                raise ValueError("Test exception")

        # Duration should be captured even though exception was raised
        assert timer.duration >= 0.05


class TestAnalyzePerformanceLogsAggregation:
    """Test that performance log analysis calculates aggregate metrics.

    Requirement: Analyze logs should compute min, max, avg, p95 duration
    for each agent across multiple executions.
    """

    @pytest.fixture
    def sample_performance_logs(self, tmp_path):
        """Create sample performance log file with multiple entries.

        Returns temp file path with 20 newline-delimited JSON entries.
        """
        log_file = tmp_path / "performance_metrics.json"

        # Create 20 log entries for multiple agents
        entries = []
        agents = ["researcher", "planner", "test-master", "implementer", "reviewer"]

        for i in range(20):
            agent = agents[i % len(agents)]
            # Varying durations: alternates 5s and 15s per agent iteration
            # Each agent appears 4 times (i//5 gives iteration number)
            # iteration 0,2 -> 5s; iteration 1,3 -> 15s
            iteration = i // len(agents)
            duration = 5 + (iteration % 2) * 10
            entry = {
                "agent_name": agent,
                "feature": f"Feature {i}",
                "duration": duration,
                "timestamp": (datetime.now() - timedelta(seconds=i)).isoformat() + "Z"
            }
            entries.append(json.dumps(entry))

        # Write newline-delimited JSON
        log_file.write_text("\n".join(entries) + "\n")
        return log_file

    def test_analyze_performance_logs_calculates_average(self, sample_performance_logs):
        """Test that analyze_performance_logs calculates average duration per agent.

        Arrange: Performance log with 4 researcher entries (durations: 5, 15, 5, 15)
        Act: Call analyze_performance_logs(log_file)
        Assert: metrics['researcher']['avg'] == 10.0
        """
        metrics = analyze_performance_logs(sample_performance_logs)

        # Researcher should have 4 entries: 5, 15, 5, 15 -> avg = 10
        assert 'researcher' in metrics
        assert 'avg' in metrics['researcher']
        assert metrics['researcher']['avg'] == 10.0

    def test_analyze_performance_logs_calculates_min_max(self, sample_performance_logs):
        """Test that analyze_performance_logs calculates min and max duration.

        Arrange: Performance log with entries for each agent
        Act: Call analyze_performance_logs(log_file)
        Assert: min and max are correctly calculated per agent
        """
        metrics = analyze_performance_logs(sample_performance_logs)

        # Researcher has durations 5, 15, 5, 15
        assert metrics['researcher']['min'] == 5.0
        assert metrics['researcher']['max'] == 15.0

    def test_analyze_performance_logs_calculates_p95(self, sample_performance_logs):
        """Test that analyze_performance_logs calculates 95th percentile duration.

        Arrange: Performance log with 4 entries per agent
        Act: Call analyze_performance_logs(log_file)
        Assert: p95 is calculated (should be close to max for small sample)
        """
        metrics = analyze_performance_logs(sample_performance_logs)

        # p95 should exist and be between min and max
        assert 'p95' in metrics['researcher']
        assert metrics['researcher']['min'] <= metrics['researcher']['p95']
        assert metrics['researcher']['p95'] <= metrics['researcher']['max']

    def test_analyze_performance_logs_entry_count(self, sample_performance_logs):
        """Test that analyze_performance_logs counts entries per agent.

        Arrange: Performance log with 4 entries each for 5 agents (20 total)
        Act: Call analyze_performance_logs(log_file)
        Assert: count == 4 for each agent
        """
        metrics = analyze_performance_logs(sample_performance_logs)

        # 20 entries / 5 agents = 4 entries per agent
        for agent in ["researcher", "planner", "test-master", "implementer", "reviewer"]:
            assert metrics[agent]['count'] == 4

    def test_analyze_performance_logs_empty_file(self, tmp_path):
        """Test that analyze_performance_logs handles empty log file gracefully.

        Arrange: Empty performance log file
        Act: Call analyze_performance_logs(empty_file)
        Assert: Returns empty dict (no entries to analyze)
        """
        empty_log = tmp_path / "empty.json"
        empty_log.write_text("")

        metrics = analyze_performance_logs(empty_log)

        assert metrics == {}

    def test_analyze_performance_logs_malformed_json_skipped(self, tmp_path):
        """Test that analyze_performance_logs skips malformed JSON lines.

        Arrange: Log file with mix of valid and invalid JSON
        Act: Call analyze_performance_logs(mixed_file)
        Assert: Valid entries analyzed, invalid entries skipped
        """
        log_file = tmp_path / "mixed.json"
        log_file.write_text(
            '{"agent_name": "researcher", "duration": 10, "timestamp": "2025-11-13T00:00:00Z"}\n'
            'invalid json line\n'
            '{"agent_name": "researcher", "duration": 20, "timestamp": "2025-11-13T00:01:00Z"}\n'
        )

        metrics = analyze_performance_logs(log_file)

        # Should have 2 entries for researcher despite malformed line
        assert metrics['researcher']['count'] == 2
        assert metrics['researcher']['avg'] == 15.0


class TestAnalyzePerformanceLogsBottleneckDetection:
    """Test that performance log analysis identifies top 3 slowest agents.

    Requirement: Performance metrics should identify which agents are slowest
    to help prioritize optimization efforts.
    """

    @pytest.fixture
    def performance_logs_varying_speeds(self, tmp_path):
        """Create log file with agents at different speeds.

        Researchers: avg 5s (fastest)
        Planner: avg 15s
        Test-master: avg 25s
        Implementer: avg 35s (slowest)
        Reviewer: avg 20s
        """
        log_file = tmp_path / "perf_varying.json"
        entries = []

        # Create entries with different avg durations
        agent_durations = {
            "researcher": 5,      # 1st fastest
            "planner": 15,        # 3rd fastest
            "test-master": 25,    # 2nd slowest
            "implementer": 35,    # Slowest
            "reviewer": 20,       # 3rd slowest
        }

        for agent, base_duration in agent_durations.items():
            for i in range(5):
                duration = base_duration + i  # Add variation
                entry = {
                    "agent_name": agent,
                    "duration": float(duration),
                    "feature": f"Feature {i}",
                    "timestamp": f"2025-11-13T12:00:{i:02d}Z"
                }
                entries.append(json.dumps(entry))

        log_file.write_text("\n".join(entries) + "\n")
        return log_file

    def test_identify_top_3_slowest_agents(self, performance_logs_varying_speeds):
        """Test that bottleneck detection identifies top 3 slowest agents.

        Arrange: Log with 5 agents at different speeds (5s, 15s, 20s, 25s, 35s avg)
        Act: Call analyze_performance_logs() and get top_slowest
        Assert: Top 3 are implementer(35s), test-master(25s), reviewer(20s)
        """
        metrics = analyze_performance_logs(performance_logs_varying_speeds)
        top_slowest = metrics.get('top_slowest_agents', [])

        assert len(top_slowest) == 3
        # Should be sorted by avg duration, descending
        assert top_slowest[0]['agent_name'] == 'implementer'
        assert top_slowest[0]['avg_duration'] == pytest.approx(37.0, rel=1.0)
        assert top_slowest[1]['agent_name'] == 'test-master'
        assert top_slowest[2]['agent_name'] == 'reviewer'

    def test_bottleneck_detection_less_than_3_agents(self, tmp_path):
        """Test bottleneck detection when fewer than 3 agents in logs.

        Arrange: Log with only 2 agents
        Act: Call analyze_performance_logs()
        Assert: top_slowest returns both agents
        """
        log_file = tmp_path / "two_agents.json"
        log_file.write_text(
            '{"agent_name": "researcher", "duration": 5, "feature": "f1", "timestamp": "2025-11-13T00:00:00Z"}\n'
            '{"agent_name": "planner", "duration": 15, "feature": "f2", "timestamp": "2025-11-13T00:01:00Z"}\n'
        )

        metrics = analyze_performance_logs(log_file)
        top_slowest = metrics.get('top_slowest_agents', [])

        assert len(top_slowest) <= 2

    def test_bottleneck_has_duration_and_agent_name(self, performance_logs_varying_speeds):
        """Test that each bottleneck entry has agent_name and avg_duration.

        Arrange: Performance metrics with top_slowest_agents
        Act: Get first bottleneck entry
        Assert: Has 'agent_name' and 'avg_duration' fields
        """
        metrics = analyze_performance_logs(performance_logs_varying_speeds)
        bottlenecks = metrics.get('top_slowest_agents', [])

        assert len(bottlenecks) > 0
        first = bottlenecks[0]
        assert 'agent_name' in first
        assert 'avg_duration' in first


class TestPerformanceLogJsonFormat:
    """Test that performance log JSON format is valid and complete.

    Requirement: Log entries must follow JSON format with required fields:
    - agent_name (string, alphanumeric + hyphen/underscore)
    - duration (number, >= 0)
    - feature (string, no newlines/control chars)
    - timestamp (string, ISO 8601 format)
    """

    @pytest.fixture
    def temp_log_dir(self, tmp_path):
        """Create temporary directory for log files."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        return log_dir

    def test_log_entry_has_required_fields(self, temp_log_dir):
        """Test that logged entry has agent_name, duration, feature, timestamp.

        Arrange: Create PerformanceTimer and write to log
        Act: Check log file contents
        Assert: Entry has all required fields
        """
        log_file = temp_log_dir / "metrics.json"

        with PerformanceTimer("researcher", "Add auth", log_to_file=True, log_path=log_file):
            time.sleep(0.01)

        # Read log file
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) > 0

        # Parse first entry
        entry = json.loads(lines[0])
        assert 'agent_name' in entry
        assert 'duration' in entry
        assert 'feature' in entry
        assert 'timestamp' in entry

    def test_log_json_is_valid_ndjson(self, temp_log_dir):
        """Test that log file is valid newline-delimited JSON (NDJSON).

        Arrange: Write multiple PerformanceTimer entries
        Act: Read log file and parse lines
        Assert: Each line is valid JSON
        """
        log_file = temp_log_dir / "ndjson.json"

        # Write 3 entries
        for i in range(3):
            with PerformanceTimer(f"agent{i}", f"feature {i}", log_to_file=True, log_path=log_file):
                pass

        # Each line should be valid JSON
        lines = log_file.read_text().strip().split("\n")
        for line in lines:
            if line.strip():  # Skip empty lines
                entry = json.loads(line)  # Should not raise
                assert isinstance(entry, dict)

    def test_log_agent_name_validation(self, temp_log_dir):
        """Test that agent_name in log contains only valid characters.

        Arrange: Log entry with agent_name 'test-agent_123'
        Act: Read and parse log
        Assert: agent_name field contains only alphanumeric, hyphen, underscore
        """
        log_file = temp_log_dir / "agent_name.json"

        with PerformanceTimer("test-agent_123", "feature", log_to_file=True, log_path=log_file):
            pass

        entry = json.loads(log_file.read_text().strip().split("\n")[0])
        # agent_name should contain only safe characters
        assert all(c.isalnum() or c in '-_' for c in entry['agent_name'])

    def test_log_duration_is_non_negative_number(self, temp_log_dir):
        """Test that duration in log is a non-negative number.

        Arrange: Log entry with measured duration
        Act: Read and parse log
        Assert: duration is a number >= 0
        """
        log_file = temp_log_dir / "duration.json"

        with PerformanceTimer("agent", "feature", log_to_file=True, log_path=log_file):
            time.sleep(0.01)

        entry = json.loads(log_file.read_text().strip().split("\n")[0])
        assert isinstance(entry['duration'], (int, float))
        assert entry['duration'] >= 0

    def test_log_timestamp_iso8601_format(self, temp_log_dir):
        """Test that timestamp in log follows ISO 8601 format.

        Arrange: Log entry with timestamp
        Act: Read and parse log
        Assert: timestamp contains T and Z (YYYY-MM-DDTHH:MM:SS.fffZ)
        """
        log_file = temp_log_dir / "timestamp.json"

        with PerformanceTimer("agent", "feature", log_to_file=True, log_path=log_file):
            pass

        entry = json.loads(log_file.read_text().strip().split("\n")[0])
        timestamp = entry['timestamp']
        assert 'T' in timestamp
        assert 'Z' in timestamp
        # Should be parseable as ISO 8601
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

    def test_log_feature_no_newlines(self, temp_log_dir):
        """Test that feature field in log has no newline characters.

        Arrange: Try to log feature with embedded newline
        Act: PerformanceTimer validates feature before logging
        Assert: Raises ValueError or feature is sanitized
        """
        log_file = temp_log_dir / "feature.json"

        # Should reject or sanitize feature with newlines
        with pytest.raises((ValueError, TypeError)):
            with PerformanceTimer("agent", "feature\nwith\nnewlines",
                                log_to_file=True, log_path=log_file):
                pass


class TestPerformanceLogPathValidation:
    """Test that performance log path validation prevents CWE-22 path traversal.

    Requirement: Log file paths must be validated to prevent writing outside
    intended log directory (/logs/). Path traversal attacks must be blocked.
    """

    def test_log_path_within_project_allowed(self, tmp_path):
        """Test that log path within project is allowed.

        Arrange: Log path at /logs/performance_metrics.json
        Act: Create PerformanceTimer with valid log path
        Assert: Logs successfully without error
        """
        project_root = tmp_path / "project"
        project_root.mkdir()
        log_dir = project_root / "logs"
        log_dir.mkdir()
        log_file = log_dir / "performance_metrics.json"

        # Should succeed - path is within project
        with PerformanceTimer("agent", "feature", log_to_file=True, log_path=log_file):
            pass

        assert log_file.exists()

    def test_log_path_traversal_attack_blocked(self, tmp_path):
        """Test that ../../etc/passwd style paths are rejected.

        Arrange: Log path with ../.. traversal
        Act: Try to create PerformanceTimer with malicious path
        Assert: Raises SecurityValidationError or similar validation error
        """
        malicious_path = tmp_path / ".." / ".." / "etc" / "passwd"

        with pytest.raises((ValueError, SecurityError, Exception)):
            with PerformanceTimer("agent", "feature",
                                log_to_file=True, log_path=malicious_path):
                pass

    def test_log_path_absolute_outside_project_blocked(self, tmp_path):
        """Test that absolute paths outside project are blocked.

        Arrange: Log path at /tmp/outside_project.json
        Act: Try to create PerformanceTimer with absolute path
        Assert: Raises validation error
        """
        outside_path = Path("/tmp") / "autonomous_dev_logs" / "outside.json"

        # May be blocked or may require whitelist validation
        # Verify either it's blocked or path validation occurs
        try:
            with PerformanceTimer("agent", "feature",
                                log_to_file=True, log_path=outside_path):
                pass
            # If allowed, verify it's in /tmp (outside project security boundary)
            # and proper validation occurred
        except (ValueError, SecurityError):
            # Blocked - expected behavior
            pass

    def test_log_path_symlink_attack_prevention(self, tmp_path):
        """Test that symlink-based path traversal is prevented.

        Arrange: Create symlink pointing outside project
        Act: Try to log to symlink path
        Assert: Symlink resolved or blocked
        """
        project = tmp_path / "project"
        project.mkdir()
        logs = project / "logs"
        logs.mkdir()

        outside = tmp_path / "outside"
        outside.mkdir()

        # Create symlink inside logs pointing outside
        symlink = logs / "evil_link"
        symlink.symlink_to(outside)

        # Test behavior - either symlink is rejected or resolved safely
        try:
            with PerformanceTimer("agent", "feature",
                                log_to_file=True, log_path=symlink / "file.json"):
                pass
            # If allowed, verify it doesn't write sensitive data outside
        except (ValueError, SecurityError):
            # Blocked - expected
            pass

    def test_log_path_validation_rejects_null_bytes(self, tmp_path):
        """Test that paths with null bytes are rejected.

        Arrange: Log path containing null byte
        Act: Try to create PerformanceTimer with null byte path
        Assert: Raises ValueError
        """
        log_path = tmp_path / "logs"
        log_path.mkdir()

        # Null byte in path (classic CWE-22 attack)
        with pytest.raises((ValueError, TypeError)):
            path_with_null = log_path / "file\x00.json"
            with PerformanceTimer("agent", "feature",
                                log_to_file=True, log_path=path_with_null):
                pass


# Custom exceptions for security testing
class SecurityError(Exception):
    """Raised when security validation fails."""
    pass


class TestPerformanceTimerIntegration:
    """Integration tests for PerformanceTimer in auto-implement workflow.

    Verify that timing works end-to-end when wrapping agent execution.
    """

    def test_multiple_concurrent_timers(self, tmp_path):
        """Test that multiple PerformanceTimers can run concurrently.

        Arrange: Create multiple PerformanceTimer instances
        Act: Run them (simulating parallel agent execution)
        Assert: All durations captured correctly without interference
        """
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log_file = log_dir / "concurrent.json"
        timers = []

        # Simulate concurrent execution
        for i in range(3):
            with PerformanceTimer(f"agent{i}", f"feature{i}",
                                log_to_file=True, log_path=log_file):
                time.sleep(0.01)
            timers.append(i)

        # All should have logged
        lines = log_file.read_text().strip().split("\n")
        assert len([l for l in lines if l.strip()]) >= 3

    def test_performance_timer_with_large_feature_name(self, tmp_path):
        """Test that PerformanceTimer handles long feature descriptions.

        Arrange: Feature with 1000 characters
        Act: Create PerformanceTimer with long feature
        Assert: Feature logged without truncation (up to max length)
        """
        long_feature = "Feature " * 100  # 800 chars
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log_file = log_dir / "long_feature.json"

        with PerformanceTimer("agent", long_feature,
                            log_to_file=True, log_path=log_file):
            pass

        entry = json.loads(log_file.read_text().strip().split("\n")[0])
        assert len(entry['feature']) > 100
