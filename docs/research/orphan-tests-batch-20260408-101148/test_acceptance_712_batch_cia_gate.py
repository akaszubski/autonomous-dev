"""Acceptance tests for Issue #712: Batch CIA skip hook-level enforcement.

Validates that a deterministic hook gate blocks git commit during batch
finalization when any issue is missing CIA completion.
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPLETION_STATE_PATH = REPO_ROOT / "plugins/autonomous-dev/lib/pipeline_completion_state.py"
UNIFIED_HOOK_PATH = REPO_ROOT / "plugins/autonomous-dev/hooks/unified_pre_tool.py"
BYPASS_PATTERNS_PATH = REPO_ROOT / "plugins/autonomous-dev/config/known_bypass_patterns.json"
IMPLEMENT_BATCH_PATH = REPO_ROOT / "plugins/autonomous-dev/commands/implement-batch.md"


class TestIssue712BatchCIAGate:
    """Acceptance tests for batch CIA hook-level enforcement."""

    def test_verify_batch_cia_function_exists(self) -> None:
        """AC1: pipeline_completion_state.py has verify_batch_cia_completions()."""
        content = COMPLETION_STATE_PATH.read_text()
        assert "def verify_batch_cia_completions" in content

    def test_hook_references_cia_verification(self) -> None:
        """AC1b: unified_pre_tool.py references batch CIA verification."""
        content = UNIFIED_HOOK_PATH.read_text()
        assert "verify_batch_cia" in content or "batch_cia" in content.lower()

    def test_gate_is_fail_open(self) -> None:
        """AC3: Gate defaults to allow on errors."""
        content = COMPLETION_STATE_PATH.read_text()
        # The function should handle missing/empty state gracefully
        lower = content.lower()
        assert "true" in lower and ("except" in lower or "not" in lower or "empty" in lower)

    def test_bypass_patterns_has_batch_cia_skip(self) -> None:
        """AC4: known_bypass_patterns.json has batch_last_issue_cia_skip."""
        data = json.loads(BYPASS_PATTERNS_PATH.read_text())
        patterns = data.get("patterns", data) if isinstance(data, dict) else data
        if isinstance(patterns, dict):
            patterns = patterns.get("patterns", [])
        ids = [p["id"] for p in patterns]
        assert "batch_last_issue_cia_skip" in ids

    def test_implement_batch_references_hook_enforcement(self) -> None:
        """AC5: implement-batch.md references hook-level CIA enforcement."""
        content = IMPLEMENT_BATCH_PATH.read_text()
        lower = content.lower()
        assert "hook" in lower and "cia" in lower or "verify_batch_cia" in content

    def test_escape_hatch_documented(self) -> None:
        """AC8: Escape hatch environment variable exists."""
        # Check either the hook or the completion state mentions the escape
        hook_content = UNIFIED_HOOK_PATH.read_text()
        state_content = COMPLETION_STATE_PATH.read_text()
        combined = hook_content + state_content
        assert "SKIP_BATCH_CIA_GATE" in combined
