"""
Regression tests for Issue #367: Intent-level pipeline validation.

Verifies that the pipeline intent validator infrastructure exists and
that supporting components (bypass patterns, CI analyst, session logger)
were updated correctly.

These tests verify the fix infrastructure exists and would break if removed.
"""

import json
from pathlib import Path

import pytest

# Portable project root detection
_current = Path.cwd()
while _current != _current.parent:
    if (_current / ".git").exists() or (_current / ".claude").exists():
        PROJECT_ROOT = _current
        break
    _current = _current.parent
else:
    PROJECT_ROOT = Path.cwd()

PLUGIN_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev"


class TestIssue367IntentValidatorExists:
    """Regression: pipeline_intent_validator.py must exist with required functions."""

    def test_validator_module_exists(self):
        """pipeline_intent_validator.py must exist in lib/."""
        path = PLUGIN_DIR / "lib" / "pipeline_intent_validator.py"
        assert path.exists(), (
            "Regression #367: plugins/autonomous-dev/lib/pipeline_intent_validator.py must exist"
        )

    def test_validator_has_required_functions(self):
        """Module must export all required public functions."""
        path = PLUGIN_DIR / "lib" / "pipeline_intent_validator.py"
        assert path.exists(), "Regression #367: module must exist"
        source = path.read_text()
        required = [
            "validate_pipeline_intent",
            "parse_session_logs",
            "validate_step_ordering",
            "detect_hard_gate_ordering",
            "detect_context_dropping",
            "detect_parallelization_violations",
        ]
        for func in required:
            assert f"def {func}" in source, (
                f"Regression #367: {func} must be defined in pipeline_intent_validator.py"
            )


class TestIssue367BypassPatternsUpdated:
    """Regression: known_bypass_patterns.json must include new intent-level patterns."""

    @pytest.fixture
    def config(self):
        path = PLUGIN_DIR / "config" / "known_bypass_patterns.json"
        assert path.exists(), "Regression #367: known_bypass_patterns.json must exist"
        return json.loads(path.read_text())

    def test_new_patterns_registered(self, config):
        """New intent-level patterns must be registered."""
        pattern_ids = {p["id"] for p in config["patterns"]}
        required = {
            "sequential_step_parallelized",
            "parallel_step_serialized",
            "context_dropping",
            "hard_gate_ordering_bypass",
            "reviewer_blocking_ignored",
        }
        missing = required - pattern_ids
        assert not missing, f"Regression #367: missing patterns: {missing}"

    def test_new_patterns_have_detection_rules(self, config):
        """Each new pattern must have detection + indicators."""
        new_ids = {
            "sequential_step_parallelized",
            "parallel_step_serialized",
            "context_dropping",
            "hard_gate_ordering_bypass",
            "reviewer_blocking_ignored",
        }
        for p in config["patterns"]:
            if p["id"] in new_ids:
                assert "detection" in p, (
                    f"Regression #367: pattern {p['id']} missing detection"
                )
                assert "indicators" in p["detection"], (
                    f"Regression #367: pattern {p['id']} missing detection.indicators"
                )


class TestIssue367CIAnalystUpdated:
    """Regression: continuous-improvement-analyst must reference intent validation."""

    @pytest.fixture
    def analyst_source(self):
        path = PLUGIN_DIR / "agents" / "continuous-improvement-analyst.md"
        assert path.exists(), "Regression #367: CI analyst agent must exist"
        return path.read_text()

    def test_analyst_has_intent_validation_section(self, analyst_source):
        """Agent must have 'Intent-Level Pipeline Validation' section."""
        assert "Intent-Level Pipeline Validation" in analyst_source, (
            "Regression #367: CI analyst must reference intent-level pipeline validation"
        )

    def test_analyst_references_8_quality_checks(self, analyst_source):
        """Agent must reference '8 Quality Checks'."""
        assert "8 Quality Checks" in analyst_source, (
            "Regression #367: CI analyst must reference 8 quality checks"
        )


class TestIssue367SessionLoggerWordCounts:
    """Regression: session_activity_logger must capture word counts."""

    @pytest.fixture
    def logger_source(self):
        path = PLUGIN_DIR / "hooks" / "session_activity_logger.py"
        assert path.exists(), "Regression #367: session_activity_logger.py must exist"
        return path.read_text()

    def test_logger_captures_prompt_word_count(self, logger_source):
        """Logger must capture prompt_word_count."""
        assert "prompt_word_count" in logger_source, (
            "Regression #367: session_activity_logger must capture prompt_word_count"
        )

    def test_logger_captures_result_word_count(self, logger_source):
        """Logger must capture result_word_count."""
        assert "result_word_count" in logger_source, (
            "Regression #367: session_activity_logger must capture result_word_count"
        )
