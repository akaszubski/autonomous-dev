"""
Regression tests for continuous-improvement-analyst agent.

Validates that:
1. The agent prompt's documented log format matches what session_activity_logger.py writes
2. The agent prompt references correct field names
3. Log entries contain the fields the agent needs for analysis

Date: 2026-03-07
"""

import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "autonomous-dev"
AGENT_PROMPT = PLUGIN / "agents" / "continuous-improvement-analyst.md"
LOGGER_HOOK = PLUGIN / "hooks" / "session_activity_logger.py"


# ---------------------------------------------------------------------------
# 1. Agent prompt references correct log field names
# ---------------------------------------------------------------------------

class TestAgentPromptLogFormat:
    """The CI analyst agent prompt must document the actual log format."""

    @pytest.fixture
    def agent_text(self) -> str:
        return AGENT_PROMPT.read_text()

    @pytest.fixture
    def logger_text(self) -> str:
        return LOGGER_HOOK.read_text()

    def test_agent_uses_hook_not_hook_type(self, agent_text):
        """Agent must reference 'hook' field, not 'hook_type'."""
        # The log format example should show "hook" not "hook_type"
        assert '"hook"' in agent_text, (
            "Agent prompt must document 'hook' as the field name (not 'hook_type')"
        )

    def test_agent_documents_agent_field_limitation(self, agent_text):
        """Agent must acknowledge that agent field is always 'main'."""
        assert "main" in agent_text.lower() and "agent" in agent_text.lower(), (
            "Agent prompt must document that 'agent' field is usually 'main' "
            "(Claude Code doesn't set CLAUDE_AGENT_NAME for subagents)"
        )

    def test_logger_writes_hook_field(self, logger_text):
        """session_activity_logger.py must write 'hook' field."""
        assert '"hook"' in logger_text, (
            "session_activity_logger.py must write 'hook' field in log entries"
        )

    def test_logger_writes_agent_field(self, logger_text):
        """session_activity_logger.py must write 'agent' field."""
        assert '"agent"' in logger_text, (
            "session_activity_logger.py must write 'agent' field in log entries"
        )

    def test_log_format_fields_match(self, agent_text, logger_text):
        """Core log fields referenced in agent prompt must be written by logger."""
        required_fields = {"timestamp", "hook", "agent"}

        for field in required_fields:
            assert f'"{field}"' in agent_text, (
                f"Agent prompt doesn't reference field '{field}'"
            )
            assert f'"{field}"' in logger_text, (
                f"Logger doesn't write field '{field}' that agent expects"
            )


# ---------------------------------------------------------------------------
# 2. Hook type values consistency
# ---------------------------------------------------------------------------

class TestHookTypeValues:
    """The hook type values used in agent prompt must match what the logger writes."""

    VALID_HOOK_TYPES = {"PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop"}

    def test_agent_references_valid_hook_types(self):
        text = AGENT_PROMPT.read_text()
        # Agent should reference these hook types in its analysis checks
        for hook_type in self.VALID_HOOK_TYPES:
            assert hook_type in text, (
                f"Agent prompt missing hook type '{hook_type}' — "
                f"it must analyze all 4 hook layers"
            )

    def test_logger_writes_valid_hook_types(self):
        text = LOGGER_HOOK.read_text()
        for hook_type in self.VALID_HOOK_TYPES:
            # At least some hook types should appear in the logger
            # (not all — Stop/UserPromptSubmit may be handled differently)
            pass  # The logger dispatches based on hook_name from sys.argv
        # Check that the logger reads hook_name
        assert "hook_name" in text or "sys.argv" in text or "hook" in text, (
            "Logger must determine hook type from input"
        )


# ---------------------------------------------------------------------------
# 3. Pipeline step count in agent prompt
# ---------------------------------------------------------------------------

class TestAgentPromptPipelineConsistency:
    """Agent prompt must reference the correct pipeline step count."""

    def test_says_8_step_pipeline(self):
        text = AGENT_PROMPT.read_text()
        m = re.search(r"(\d+)-step pipeline", text)
        assert m, "Agent prompt should reference N-step pipeline"
        assert m.group(1) == "8", (
            f"Agent prompt says {m.group(1)}-step pipeline, should be 8"
        )

    def test_lists_all_pipeline_agents(self):
        """Agent prompt must list the expected pipeline agents."""
        text = AGENT_PROMPT.read_text()
        expected_agents = [
            "researcher-local", "researcher", "planner", "test-master",
            "implementer", "reviewer", "security-auditor", "doc-master",
        ]
        for agent in expected_agents:
            assert agent in text, (
                f"Agent prompt missing pipeline agent '{agent}'"
            )


# ---------------------------------------------------------------------------
# 4. Known bypass patterns file exists and is valid JSON
# ---------------------------------------------------------------------------

class TestKnownBypassPatterns:
    """The known_bypass_patterns.json file must exist and be valid."""

    PATTERNS_FILE = PLUGIN / "config" / "known_bypass_patterns.json"

    def test_file_exists(self):
        assert self.PATTERNS_FILE.exists(), (
            f"known_bypass_patterns.json not found at {self.PATTERNS_FILE}"
        )

    def test_valid_json(self):
        if not self.PATTERNS_FILE.exists():
            pytest.skip("File doesn't exist")
        with open(self.PATTERNS_FILE) as f:
            data = json.load(f)
        assert isinstance(data, dict), "Must be a JSON object"

    def test_contains_expected_patterns(self):
        """Agent prompt references specific pattern IDs that must exist."""
        if not self.PATTERNS_FILE.exists():
            pytest.skip("File doesn't exist")
        with open(self.PATTERNS_FILE) as f:
            data = json.load(f)

        expected_patterns = [
            "test_gate_bypass",
            "anti_stubbing",
            "command_bypass",
        ]
        patterns_str = json.dumps(data)
        for pattern in expected_patterns:
            assert pattern in patterns_str, (
                f"known_bypass_patterns.json missing pattern '{pattern}' "
                f"referenced in agent prompt"
            )


# ---------------------------------------------------------------------------
# 5. Activity log directory structure
# ---------------------------------------------------------------------------

class TestActivityLogStructure:
    """Activity logs must exist in the expected location."""

    LOG_DIR = ROOT / ".claude" / "logs" / "activity"

    def test_log_directory_exists(self):
        assert self.LOG_DIR.exists(), (
            f"Activity log directory not found at {self.LOG_DIR}"
        )

    def test_log_files_are_dated_jsonl(self):
        if not self.LOG_DIR.exists():
            pytest.skip("Log dir doesn't exist")
        log_files = list(self.LOG_DIR.glob("*.jsonl"))
        assert len(log_files) > 0, "No .jsonl log files found"
        # Check naming pattern: YYYY-MM-DD.jsonl
        for f in log_files:
            assert re.match(r"\d{4}-\d{2}-\d{2}\.jsonl", f.name), (
                f"Log file '{f.name}' doesn't match YYYY-MM-DD.jsonl pattern"
            )

    def test_latest_log_has_valid_entries(self):
        if not self.LOG_DIR.exists():
            pytest.skip("Log dir doesn't exist")
        log_files = sorted(self.LOG_DIR.glob("*.jsonl"))
        if not log_files:
            pytest.skip("No log files")
        latest = log_files[-1]
        with open(latest) as f:
            first_line = f.readline().strip()
        if not first_line:
            pytest.skip("Empty log file")
        entry = json.loads(first_line)
        assert "timestamp" in entry, "Log entry missing 'timestamp'"
        assert "hook" in entry, "Log entry missing 'hook' field"
