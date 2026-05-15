"""Regression tests for Issue #712: Batch CIA hook-level enforcement.

Verifies that the batch CIA gate is properly wired across all components:
- pipeline_completion_state.py has verify_batch_cia_completions
- unified_pre_tool.py references the gate
- known_bypass_patterns.json has the entry
- implement-batch.md documents the hook enforcement

Issue: #712
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestIssue712Wiring:
    """Verify all components of the batch CIA gate are wired together."""

    def test_verify_function_exists_in_completion_state(self) -> None:
        """pipeline_completion_state.py exports verify_batch_cia_completions."""
        path = REPO_ROOT / "plugins/autonomous-dev/lib/pipeline_completion_state.py"
        content = path.read_text()
        assert "def verify_batch_cia_completions" in content

    def test_unified_pre_tool_references_batch_cia(self) -> None:
        """unified_pre_tool.py references the batch CIA verification."""
        path = REPO_ROOT / "plugins/autonomous-dev/hooks/unified_pre_tool.py"
        content = path.read_text()
        assert "_check_batch_cia_completions" in content
        assert "verify_batch_cia" in content

    def test_known_bypass_patterns_has_entry(self) -> None:
        """known_bypass_patterns.json has batch_last_issue_cia_skip."""
        path = REPO_ROOT / "plugins/autonomous-dev/config/known_bypass_patterns.json"
        data = json.loads(path.read_text())
        patterns = data.get("patterns", [])
        ids = [p["id"] for p in patterns]
        assert "batch_last_issue_cia_skip" in ids

        # Verify severity is critical
        pattern = next(p for p in patterns if p["id"] == "batch_last_issue_cia_skip")
        assert pattern["severity"] == "critical"
        assert pattern["issue"] == "#712"

    def test_implement_batch_references_hook_enforcement(self) -> None:
        """implement-batch.md documents hook-level CIA enforcement."""
        path = REPO_ROOT / "plugins/autonomous-dev/commands/implement-batch.md"
        content = path.read_text()
        assert "Hook" in content or "hook" in content
        assert "CIA" in content or "cia" in content.lower()
        assert "712" in content

    def test_escape_hatch_documented_in_both_files(self) -> None:
        """SKIP_BATCH_CIA_GATE is referenced in both lib and hook."""
        lib_path = REPO_ROOT / "plugins/autonomous-dev/lib/pipeline_completion_state.py"
        hook_path = REPO_ROOT / "plugins/autonomous-dev/hooks/unified_pre_tool.py"

        lib_content = lib_path.read_text()
        hook_content = hook_path.read_text()

        assert "SKIP_BATCH_CIA_GATE" in lib_content
        assert "SKIP_BATCH_CIA_GATE" in hook_content
