#!/usr/bin/env python3
"""Tests for new FIX_SIGNALS and LABEL_FIX additions in batch_mode_detector.

Acceptance criteria for Issue #1109:
  AC1: New signal strings in FIX_SIGNALS route issue titles to PipelineMode.FIX.
  AC2: "auto-improvement" in LABEL_FIX routes to PipelineMode.FIX via label.

Issue: #1109
"""

import sys
from pathlib import Path

import pytest

# Add lib to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins/autonomous-dev/lib"))

from batch_mode_detector import (
    FIX_SIGNALS,
    LABEL_FIX,
    PipelineMode,
    detect_issue_mode,
)


class TestNewFIXSignalsRouteToFix:
    """AC1: Each new signal added in Issue #1109 routes to PipelineMode.FIX."""

    def test_false_positive_in_title(self) -> None:
        """'false positive' in title should route to FIX."""
        result = detect_issue_mode("[CI] false positive in guard")
        assert result.mode == PipelineMode.FIX

    def test_false_positive_hyphenated(self) -> None:
        """'false-positive' (hyphenated) in title should route to FIX."""
        result = detect_issue_mode("Address false-positive in hook")
        assert result.mode == PipelineMode.FIX

    def test_guard_fires_signal(self) -> None:
        """'guard fires' in title should route to FIX."""
        result = detect_issue_mode("Gate guard fires on valid input")
        assert result.mode == PipelineMode.FIX

    def test_blocked_signal(self) -> None:
        """'blocked' in title should route to FIX."""
        result = detect_issue_mode("Implementer blocked by stale deny cache")
        assert result.mode == PipelineMode.FIX

    def test_hardening_signal(self) -> None:
        """'hardening' in title should route to FIX."""
        result = detect_issue_mode("Security hardening for hook gate")
        assert result.mode == PipelineMode.FIX

    def test_missing_check_signal(self) -> None:
        """'missing check' in title should route to FIX."""
        result = detect_issue_mode("Add missing check in validator")
        assert result.mode == PipelineMode.FIX

    def test_ci_prefix_signal(self) -> None:
        """'[ci]' prefix in title should route to FIX (Issue #1109 AC1)."""
        result = detect_issue_mode("[CI] false positive in guard")
        assert result.mode == PipelineMode.FIX


class TestAutoImprovementLabel:
    """AC2: 'auto-improvement' label routes to PipelineMode.FIX via label source."""

    def test_auto_improvement_label_routes_to_fix(self) -> None:
        """'auto-improvement' label must trigger FIX mode with source='label'."""
        result = detect_issue_mode("X", labels=["auto-improvement"])
        assert result.mode == PipelineMode.FIX
        assert result.source == "label"
        assert result.confidence == 1.0

    def test_auto_improvement_label_is_in_label_fix_list(self) -> None:
        """'auto-improvement' must be present in LABEL_FIX constant."""
        assert "auto-improvement" in LABEL_FIX

    def test_auto_improvement_label_case_insensitive(self) -> None:
        """Label matching is case-insensitive; 'Auto-Improvement' should also work."""
        result = detect_issue_mode("Some issue", labels=["Auto-Improvement"])
        assert result.mode == PipelineMode.FIX
        assert result.source == "label"

    def test_new_signals_present_in_fix_signals_list(self) -> None:
        """Verify all 12 new signals from Issue #1109 are in FIX_SIGNALS."""
        new_signals = [
            "false positive",
            "false-positive",
            "guard fires",
            "blocks",
            "blocked",
            "stale",
            "hardening",
            "umbrella",
            "missing check",
            "misclass",
            "drift",
            "[ci]",
        ]
        for signal in new_signals:
            assert signal in FIX_SIGNALS, f"Expected '{signal}' in FIX_SIGNALS"
