"""
Regression tests for Issues #354/#355: Pipeline completeness and bypass detection.

Bug #354: Continuous improvement analyst doesn't check whether pipeline runs
completed all expected terminal actions for their mode.

Bug #355: Analyst doesn't detect when the model itself bypasses pipeline intent
(test gate bypass, stubbing, step skipping, context compression).

Fix: known_bypass_patterns.json registry with detection rules, expected end-states
per pipeline mode, and softened language indicators. Analyst updated with sections
6 (pipeline completeness) and 7 (bypass detection).

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


class TestIssue355BypassPatternsRegistry:
    """Regression: bypass patterns registry must exist and cover all historical bugs."""

    @pytest.fixture
    def config(self):
        path = PLUGIN_DIR / "config" / "known_bypass_patterns.json"
        return json.loads(path.read_text())

    def test_registry_file_exists(self):
        """known_bypass_patterns.json must exist."""
        assert (PLUGIN_DIR / "config" / "known_bypass_patterns.json").exists(), (
            "Regression #355: bypass patterns registry must exist"
        )

    def test_all_historical_bugs_covered(self, config):
        """All historical bypass bugs must have entries in the registry."""
        pattern_issues = {p.get("issue") for p in config["patterns"]}
        historical = {"#206", "#310", "#348", "#353"}
        missing = historical - pattern_issues
        assert not missing, f"Regression #355: missing patterns for issues: {missing}"

    def test_patterns_have_detection_rules(self, config):
        """Each pattern must have detection indicators."""
        for p in config["patterns"]:
            assert "detection" in p, f"Regression #355: pattern {p['id']} missing detection"
            assert "indicators" in p["detection"], (
                f"Regression #355: pattern {p['id']} missing detection indicators"
            )
            assert len(p["detection"]["indicators"]) > 0, (
                f"Regression #355: pattern {p['id']} has empty indicators"
            )

    def test_expected_end_states_cover_all_modes(self, config):
        """Expected end-states must cover all pipeline modes."""
        modes = set(config["expected_end_states"].keys())
        required = {"full_pipeline", "quick", "batch", "batch-issues"}
        missing = required - modes
        assert not missing, f"Regression #354: missing end-states for modes: {missing}"

    def test_softened_language_indicators_exist(self, config):
        """Softened language indicators must exist for bypass detection."""
        indicators = config.get("softened_language_indicators", [])
        assert len(indicators) >= 5, (
            "Regression #355: need at least 5 softened language indicators"
        )
        # Must include the most common bypass phrase
        assert "good enough" in indicators, (
            "Regression #355: 'good enough' must be in softened language indicators"
        )


class TestIssue354AnalystPipelineCompleteness:
    """Regression: analyst must check pipeline completeness."""

    def test_analyst_has_pipeline_completeness_section(self):
        """continuous-improvement-analyst.md must have pipeline completeness section."""
        content = (PLUGIN_DIR / "agents" / "continuous-improvement-analyst.md").read_text()
        assert "Pipeline Completeness" in content, (
            "Regression #354: analyst must have pipeline completeness section"
        )

    def test_analyst_has_bypass_detection_section(self):
        """continuous-improvement-analyst.md must have bypass detection section."""
        content = (PLUGIN_DIR / "agents" / "continuous-improvement-analyst.md").read_text()
        assert "Bypass Detection" in content or "Intent Bypass" in content, (
            "Regression #355: analyst must have bypass detection section"
        )

    def test_analyst_references_bypass_patterns_json(self):
        """Analyst must reference known_bypass_patterns.json."""
        content = (PLUGIN_DIR / "agents" / "continuous-improvement-analyst.md").read_text()
        assert "known_bypass_patterns.json" in content, (
            "Regression #355: analyst must reference bypass patterns registry"
        )

    def test_analyst_output_has_incomplete_finding_type(self):
        """Analyst output format must include [INCOMPLETE] finding type."""
        content = (PLUGIN_DIR / "agents" / "continuous-improvement-analyst.md").read_text()
        assert "[INCOMPLETE]" in content, (
            "Regression #354: analyst output must have [INCOMPLETE] finding type"
        )

    def test_analyst_output_has_bypass_finding_type(self):
        """Analyst output format must include [BYPASS] finding type."""
        content = (PLUGIN_DIR / "agents" / "continuous-improvement-analyst.md").read_text()
        assert "[BYPASS]" in content, (
            "Regression #355: analyst output must have [BYPASS] finding type"
        )

    def test_analyst_output_has_new_bypass_finding_type(self):
        """Analyst output format must include [NEW-BYPASS] for novel patterns."""
        content = (PLUGIN_DIR / "agents" / "continuous-improvement-analyst.md").read_text()
        assert "[NEW-BYPASS]" in content, (
            "Regression #355: analyst must detect novel bypass patterns"
        )


class TestIssue354SessionLoggerPipelineActions:
    """Regression: session logger must tag pipeline-relevant actions."""

    def test_logger_detects_git_push(self):
        """session_activity_logger.py must tag git push commands."""
        content = (PLUGIN_DIR / "hooks" / "session_activity_logger.py").read_text()
        assert "git push" in content, (
            "Regression #354: logger must detect git push"
        )
        assert "pipeline_action" in content, (
            "Regression #354: logger must use pipeline_action field"
        )

    def test_logger_detects_issue_close(self):
        """session_activity_logger.py must tag gh issue close commands."""
        content = (PLUGIN_DIR / "hooks" / "session_activity_logger.py").read_text()
        assert "gh issue close" in content, (
            "Regression #354: logger must detect gh issue close"
        )

    def test_logger_detects_agent_invocations(self):
        """session_activity_logger.py must tag Task agent invocations."""
        content = (PLUGIN_DIR / "hooks" / "session_activity_logger.py").read_text()
        assert "agent_invocation" in content, (
            "Regression #354: logger must tag agent invocations"
        )
