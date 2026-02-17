"""Unit tests for pipeline action detection in session_activity_logger.

Tests that the _summarize_input function correctly tags pipeline-relevant
actions (git push, issue close, test runs, agent invocations) for use by
the continuous-improvement-analyst.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks path for import
_WORKTREE_ROOT = Path(__file__).parent.parent.parent.parent
_HOOKS_PATH = _WORKTREE_ROOT / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(_HOOKS_PATH))

from session_activity_logger import _summarize_input


class TestPipelineActionDetection:
    """Tests for pipeline_action tagging in _summarize_input."""

    def test_git_push_detected(self):
        result = _summarize_input("Bash", {"command": "git push origin master"})
        assert result["pipeline_action"] == "git_push"

    def test_git_push_with_flags(self):
        result = _summarize_input("Bash", {"command": "git push -u origin feature-branch"})
        assert result["pipeline_action"] == "git_push"

    def test_gh_issue_close_detected(self):
        result = _summarize_input("Bash", {"command": 'gh issue close 353 -c "Implemented in abc123"'})
        assert result["pipeline_action"] == "issue_close"

    def test_git_commit_detected(self):
        result = _summarize_input("Bash", {"command": 'git commit -m "feat: add feature"'})
        assert result["pipeline_action"] == "git_commit"

    def test_pytest_detected(self):
        result = _summarize_input("Bash", {"command": "pytest tests/ --tb=short -q"})
        assert result["pipeline_action"] == "test_run"

    def test_python_pytest_detected(self):
        result = _summarize_input("Bash", {"command": "python -m pytest tests/unit/ -v"})
        assert result["pipeline_action"] == "test_run"

    def test_pipeline_state_detected(self):
        result = _summarize_input("Bash", {"command": 'echo \'{"mode": "batch"}\' > /tmp/implement_pipeline_state.json'})
        assert result["pipeline_action"] == "pipeline_state"

    def test_regular_bash_no_pipeline_action(self):
        result = _summarize_input("Bash", {"command": "ls -la"})
        assert "pipeline_action" not in result

    def test_task_agent_invocation(self):
        result = _summarize_input("Task", {"description": "Implement feature", "subagent_type": "implementer"})
        assert result["pipeline_action"] == "agent_invocation"
        assert result["subagent_type"] == "implementer"

    def test_read_no_pipeline_action(self):
        result = _summarize_input("Read", {"file_path": "/some/file.py"})
        assert "pipeline_action" not in result

    def test_write_no_pipeline_action(self):
        result = _summarize_input("Write", {"file_path": "/some/file.py", "content": "hello"})
        assert "pipeline_action" not in result


class TestBypassPatternsConfig:
    """Tests for known_bypass_patterns.json structure and completeness."""

    @pytest.fixture
    def patterns_config(self):
        config_path = _WORKTREE_ROOT / "plugins" / "autonomous-dev" / "config" / "known_bypass_patterns.json"
        return json.loads(config_path.read_text())

    def test_config_loads_valid_json(self, patterns_config):
        assert "patterns" in patterns_config
        assert "expected_end_states" in patterns_config
        assert "softened_language_indicators" in patterns_config

    def test_all_patterns_have_required_fields(self, patterns_config):
        for pattern in patterns_config["patterns"]:
            assert "id" in pattern, f"Pattern missing 'id': {pattern}"
            assert "name" in pattern, f"Pattern missing 'name': {pattern.get('id')}"
            assert "description" in pattern, f"Pattern missing 'description': {pattern.get('id')}"
            assert "detection" in pattern, f"Pattern missing 'detection': {pattern.get('id')}"
            assert "severity" in pattern, f"Pattern missing 'severity': {pattern.get('id')}"
            assert pattern["severity"] in ("critical", "warning", "info"), (
                f"Invalid severity '{pattern['severity']}' for {pattern['id']}"
            )

    def test_all_detection_types_valid(self, patterns_config):
        valid_types = {"log_pattern", "file_content", "congruence", "pipeline_completeness", "agent_io"}
        for pattern in patterns_config["patterns"]:
            dtype = pattern["detection"]["type"]
            assert dtype in valid_types, f"Invalid detection type '{dtype}' for {pattern['id']}"

    def test_expected_end_states_cover_all_modes(self, patterns_config):
        states = patterns_config["expected_end_states"]
        assert "full_pipeline" in states
        assert "quick" in states
        assert "batch-issues" in states
        assert "batch" in states

    def test_batch_issues_requires_issue_close(self, patterns_config):
        batch_issues = patterns_config["expected_end_states"]["batch-issues"]
        assert "issue_close" in batch_issues["required_actions"]

    def test_batch_issues_requires_git_push(self, patterns_config):
        batch_issues = patterns_config["expected_end_states"]["batch-issues"]
        assert "git_push" in batch_issues["required_actions"]

    def test_known_patterns_match_historical_issues(self, patterns_config):
        """Verify all historical bypass issues are represented."""
        pattern_ids = {p["id"] for p in patterns_config["patterns"]}
        assert "test_gate_bypass" in pattern_ids  # #206
        assert "anti_stubbing" in pattern_ids  # #310
        assert "hook_registration_skip" in pattern_ids  # #348
        assert "missing_terminal_actions" in pattern_ids  # #353

    def test_softened_language_not_empty(self, patterns_config):
        indicators = patterns_config["softened_language_indicators"]
        assert len(indicators) >= 5
        assert "good enough" in indicators

    def test_pattern_ids_unique(self, patterns_config):
        ids = [p["id"] for p in patterns_config["patterns"]]
        assert len(ids) == len(set(ids)), f"Duplicate pattern IDs: {[x for x in ids if ids.count(x) > 1]}"
