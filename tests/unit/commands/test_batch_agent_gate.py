"""Tests for issue #363: per-issue agent count HARD GATE in batch-issues mode.

Validates:
1. known_bypass_patterns.json has batch_progressive_shortcutting pattern
2. expected_end_states for batch/batch-issues have all 9 required agents
3. implement-batch.md contains Per-Issue Agent Count HARD GATE text
"""

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "plugins/autonomous-dev/config/known_bypass_patterns.json"
BATCH_CMD_PATH = PROJECT_ROOT / "plugins/autonomous-dev/commands/implement-batch.md"

EXPECTED_NINE_AGENTS = [
    "researcher-local",
    "researcher",
    "planner",
    "test-master",
    "implementer",
    "reviewer",
    "security-auditor",
    "doc-master",
    "continuous-improvement-analyst",
]


class TestKnownBypassPatternsJson:
    """Validate known_bypass_patterns.json structure and content."""

    @pytest.fixture
    def config(self) -> dict:
        return json.loads(CONFIG_PATH.read_text())

    def test_valid_json(self):
        """Config file must be valid JSON."""
        data = json.loads(CONFIG_PATH.read_text())
        assert isinstance(data, dict)

    def test_batch_progressive_shortcutting_pattern_exists(self, config: dict):
        """Pattern batch_progressive_shortcutting must exist."""
        pattern_ids = [p["id"] for p in config["patterns"]]
        assert "batch_progressive_shortcutting" in pattern_ids

    def test_batch_progressive_shortcutting_structure(self, config: dict):
        """Pattern must have all required fields."""
        pattern = next(
            (p for p in config["patterns"] if p["id"] == "batch_progressive_shortcutting"),
            None,
        )
        assert pattern is not None, "Pattern not found"
        for field in ["id", "name", "description", "hard_gate", "detection", "severity"]:
            assert field in pattern, f"Missing field: {field}"
        assert pattern["severity"] == "critical"

    def test_batch_issues_required_agents_complete(self, config: dict):
        """batch-issues end state must require all 9 pipeline agents."""
        agents = config["expected_end_states"]["batch-issues"]["required_agents"]
        for agent in EXPECTED_NINE_AGENTS:
            assert agent in agents, f"Missing agent in batch-issues: {agent}"
        assert len(agents) >= len(EXPECTED_NINE_AGENTS)

    def test_batch_required_agents_complete(self, config: dict):
        """batch end state must require all 9 pipeline agents."""
        agents = config["expected_end_states"]["batch"]["required_agents"]
        for agent in EXPECTED_NINE_AGENTS:
            assert agent in agents, f"Missing agent in batch: {agent}"
        assert len(agents) >= len(EXPECTED_NINE_AGENTS)


class TestImplementBatchHardGate:
    """Validate implement-batch.md contains HARD GATE text."""

    @pytest.fixture
    def content(self) -> str:
        return BATCH_CMD_PATH.read_text()

    def test_per_issue_agent_count_hard_gate_present(self, content: str):
        """implement-batch.md must contain Per-Issue Agent Count HARD GATE."""
        assert "Per-Issue Agent Count" in content
        assert "HARD GATE" in content

    def test_forbidden_list_present(self, content: str):
        """implement-batch.md must contain FORBIDDEN list for batch agent verification."""
        assert "FORBIDDEN" in content
        # Should forbid skipping agents for later issues
        assert "Advancing to the next issue with fewer than 9 agents" in content
