"""Tests for Issue #386: Batch issues grouped into one pipeline pass.

Validates:
1. known_bypass_patterns.json has batch_group_pipeline pattern (CRITICAL severity)
2. implement-batch.md references per-issue pipeline state tracking
3. expected_end_states for batch-issues mentions per-issue requirements
"""

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "plugins/autonomous-dev/config/known_bypass_patterns.json"
BATCH_CMD_PATH = PROJECT_ROOT / "plugins/autonomous-dev/commands/implement-batch.md"

EXPECTED_DEFAULT_AGENTS = [
    "researcher-local",
    "researcher",
    "planner",
    "implementer",
    "reviewer",
    "security-auditor",
    "doc-master",
    "continuous-improvement-analyst",
]


class TestBatchGroupPipelinePattern:
    """Validate batch_group_pipeline bypass pattern in known_bypass_patterns.json."""

    @pytest.fixture
    def config(self) -> dict:
        return json.loads(CONFIG_PATH.read_text())

    @pytest.fixture
    def patterns(self, config: dict) -> list:
        return config["patterns"]

    @pytest.fixture
    def pattern_ids(self, patterns: list) -> list:
        return [p["id"] for p in patterns]

    def test_batch_group_pipeline_pattern_exists(self, pattern_ids: list):
        """known_bypass_patterns.json must have a batch_group_pipeline pattern."""
        assert "batch_group_pipeline" in pattern_ids, (
            "Missing 'batch_group_pipeline' pattern in known_bypass_patterns.json. "
            "Issue #386 requires this pattern to detect when multiple issues are "
            "grouped into a single pipeline pass instead of separate passes."
        )

    def test_batch_group_pipeline_severity_critical(self, patterns: list):
        """batch_group_pipeline severity must be CRITICAL."""
        pattern = next(
            (p for p in patterns if p["id"] == "batch_group_pipeline"), None
        )
        assert pattern is not None, "Pattern batch_group_pipeline not found"
        assert pattern["severity"] == "critical", (
            f"Expected severity 'critical', got '{pattern['severity']}'. "
            "Grouping issues into one pipeline is a critical violation."
        )

    def test_batch_group_pipeline_detection_rules(self, patterns: list):
        """Detection rules must mention 'single pipeline' or 'grouped' behavior."""
        pattern = next(
            (p for p in patterns if p["id"] == "batch_group_pipeline"), None
        )
        assert pattern is not None, "Pattern batch_group_pipeline not found"
        assert "detection" in pattern, "Pattern missing 'detection' field"
        assert "indicators" in pattern["detection"], "Detection missing 'indicators'"

        indicators_text = " ".join(pattern["detection"]["indicators"]).lower()
        has_single_pipeline = "single pipeline" in indicators_text
        has_grouped = "group" in indicators_text
        has_combined = "combin" in indicators_text
        assert has_single_pipeline or has_grouped or has_combined, (
            f"Detection indicators should mention 'single pipeline', 'group', or 'combine'. "
            f"Got: {pattern['detection']['indicators']}"
        )

    def test_batch_group_pipeline_distinct_from_progressive(self, patterns: list):
        """batch_group_pipeline must be a different pattern from batch_progressive_shortcutting."""
        group_pattern = next(
            (p for p in patterns if p["id"] == "batch_group_pipeline"), None
        )
        progressive_pattern = next(
            (p for p in patterns if p["id"] == "batch_progressive_shortcutting"), None
        )
        assert group_pattern is not None, "Pattern batch_group_pipeline not found"
        assert progressive_pattern is not None, (
            "Pattern batch_progressive_shortcutting not found"
        )
        # They must have different descriptions
        assert group_pattern["description"] != progressive_pattern["description"], (
            "batch_group_pipeline and batch_progressive_shortcutting must have "
            "different descriptions -- they are distinct bypass patterns."
        )


class TestPerIssuePipelineState:
    """Validate implement-batch.md references per-issue pipeline state tracking."""

    @pytest.fixture
    def batch_content(self) -> str:
        return BATCH_CMD_PATH.read_text()

    def test_implement_batch_references_pipeline_state(self, batch_content: str):
        """implement-batch.md must mention pipeline_state or create_pipeline for per-issue tracking."""
        content_lower = batch_content.lower()
        has_pipeline_state = "pipeline_state" in content_lower or "pipeline state" in content_lower
        has_create_pipeline = "create_pipeline" in content_lower or "create pipeline" in content_lower
        has_per_issue_pipeline = "per-issue pipeline" in content_lower or "per issue pipeline" in content_lower
        assert has_pipeline_state or has_create_pipeline or has_per_issue_pipeline, (
            "implement-batch.md must reference pipeline state tracking per issue. "
            "Issue #386 requires creating a NEW pipeline state for each issue."
        )

    def test_implement_batch_per_issue_state_reset(self, batch_content: str):
        """implement-batch.md must say to create a NEW pipeline state per issue (not reuse)."""
        content_lower = batch_content.lower()
        has_new = "new pipeline" in content_lower or "fresh pipeline" in content_lower
        has_reset = "reset" in content_lower and "pipeline" in content_lower
        has_separate = "separate pipeline" in content_lower
        has_per_issue_new = "per-issue" in content_lower and ("new" in content_lower or "separate" in content_lower)
        assert has_new or has_reset or has_separate or has_per_issue_new, (
            "implement-batch.md must explicitly state that each issue gets a NEW/fresh/separate "
            "pipeline state, not a reused one from the previous issue."
        )

    def test_implement_batch_pipeline_cleanup_per_issue(self, batch_content: str):
        """implement-batch.md must say to cleanup pipeline state between issues."""
        content_lower = batch_content.lower()
        has_cleanup = "cleanup" in content_lower or "clean up" in content_lower or "clear" in content_lower
        has_pipeline_ref = "pipeline" in content_lower
        has_between = "between" in content_lower or "after each" in content_lower or "per issue" in content_lower
        assert has_cleanup and has_pipeline_ref and has_between, (
            "implement-batch.md must describe cleanup of pipeline state between issues. "
            "Without cleanup, state from issue N bleeds into issue N+1, causing the "
            "grouping bug described in Issue #386."
        )


class TestBatchExpectedEndStates:
    """Validate expected_end_states for batch-issues mode."""

    @pytest.fixture
    def config(self) -> dict:
        return json.loads(CONFIG_PATH.read_text())

    @pytest.fixture
    def end_states(self, config: dict) -> dict:
        return config.get("expected_end_states", {})

    def test_batch_issues_expected_end_state_exists(self, end_states: dict):
        """expected_end_states must have a batch-issues entry."""
        assert "batch-issues" in end_states, (
            "Missing 'batch-issues' in expected_end_states. "
            "This is needed to validate that each issue in a batch gets the full pipeline."
        )

    def test_batch_issues_requires_default_agents(self, end_states: dict):
        """batch-issues expected end state must list all default required agents."""
        batch_issues = end_states.get("batch-issues", {})
        required_agents = batch_issues.get("required_agents", [])
        for agent in EXPECTED_DEFAULT_AGENTS:
            assert agent in required_agents, (
                f"Agent '{agent}' missing from batch-issues required_agents. "
                f"All default pipeline agents must be required per issue."
            )

    def test_batch_issues_expected_end_state_per_issue(self, end_states: dict):
        """batch-issues expected end state or its description must mention 'per issue' or 'per_issue'."""
        batch_issues = end_states.get("batch-issues", {})
        # Check all string values in the end state for per-issue language
        state_text = json.dumps(batch_issues).lower()
        has_per_issue = "per issue" in state_text or "per_issue" in state_text or "per-issue" in state_text
        # Also check if there's a note/description field
        has_note = "note" in batch_issues or "description" in batch_issues
        assert has_per_issue or has_note, (
            "batch-issues expected_end_states should mention 'per issue' or include "
            "a note/description clarifying that the required agents apply to EACH issue, "
            "not the batch as a whole. This is the core fix for Issue #386."
        )
