#!/usr/bin/env python3
"""
Tests for auto_enforce_coverage hook environment variable configuration.

Tests the MIN_COVERAGE and COVERAGE_REPORT environment variable support.
"""

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

# Add hooks to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))


class TestCoverageThresholdConfiguration:
    """Tests for MIN_COVERAGE environment variable."""

    def test_default_threshold_is_70(self):
        """Default coverage threshold should be 70%."""
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("MIN_COVERAGE", None)
            # Import fresh to get new threshold
            import importlib
            import auto_enforce_coverage
            importlib.reload(auto_enforce_coverage)

            threshold = auto_enforce_coverage._get_coverage_threshold()
            assert threshold == 70.0

    def test_custom_threshold_from_env(self):
        """MIN_COVERAGE should set custom threshold."""
        with mock.patch.dict(os.environ, {"MIN_COVERAGE": "85"}):
            import importlib
            import auto_enforce_coverage
            importlib.reload(auto_enforce_coverage)

            threshold = auto_enforce_coverage._get_coverage_threshold()
            assert threshold == 85.0

    def test_invalid_threshold_uses_default(self):
        """Invalid MIN_COVERAGE value should use default 70%."""
        with mock.patch.dict(os.environ, {"MIN_COVERAGE": "invalid"}):
            import importlib
            import auto_enforce_coverage
            importlib.reload(auto_enforce_coverage)

            threshold = auto_enforce_coverage._get_coverage_threshold()
            assert threshold == 70.0

    def test_zero_threshold_allowed(self):
        """Zero threshold should be allowed (disables enforcement)."""
        with mock.patch.dict(os.environ, {"MIN_COVERAGE": "0"}):
            import importlib
            import auto_enforce_coverage
            importlib.reload(auto_enforce_coverage)

            threshold = auto_enforce_coverage._get_coverage_threshold()
            assert threshold == 0.0

    def test_100_percent_threshold_allowed(self):
        """100% threshold should be allowed."""
        with mock.patch.dict(os.environ, {"MIN_COVERAGE": "100"}):
            import importlib
            import auto_enforce_coverage
            importlib.reload(auto_enforce_coverage)

            threshold = auto_enforce_coverage._get_coverage_threshold()
            assert threshold == 100.0

    def test_decimal_threshold_allowed(self):
        """Decimal threshold values should be allowed."""
        with mock.patch.dict(os.environ, {"MIN_COVERAGE": "75.5"}):
            import importlib
            import auto_enforce_coverage
            importlib.reload(auto_enforce_coverage)

            threshold = auto_enforce_coverage._get_coverage_threshold()
            assert threshold == 75.5


class TestCoverageReportConfiguration:
    """Tests for COVERAGE_REPORT environment variable."""

    def test_default_report_path(self):
        """Default report path should be coverage.json."""
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("COVERAGE_REPORT", None)
            import importlib
            import auto_enforce_coverage
            importlib.reload(auto_enforce_coverage)

            # COVERAGE_REPORT should end with coverage.json
            assert auto_enforce_coverage.COVERAGE_REPORT.endswith("coverage.json")

    def test_custom_report_path(self):
        """COVERAGE_REPORT should allow custom path."""
        with mock.patch.dict(os.environ, {"COVERAGE_REPORT": "/tmp/my_coverage.xml"}):
            import importlib
            import auto_enforce_coverage
            importlib.reload(auto_enforce_coverage)

            assert auto_enforce_coverage.COVERAGE_REPORT == "/tmp/my_coverage.xml"
