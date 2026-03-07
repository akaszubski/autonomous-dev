"""Unit tests for batch processing parallelism limits (Issue #399).

Validates that implement-batch.md contains:
1. Background agent drain HARD GATE between issues
2. STEP 9 foreground requirement during batch
3. Max 2 concurrent background agents limit
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
IMPLEMENT_BATCH_MD = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-batch.md"
IMPLEMENT_MD = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"


@pytest.fixture
def batch_content() -> str:
    """Load implement-batch.md content."""
    assert IMPLEMENT_BATCH_MD.exists(), f"implement-batch.md not found at {IMPLEMENT_BATCH_MD}"
    return IMPLEMENT_BATCH_MD.read_text()


@pytest.fixture
def implement_content() -> str:
    """Load implement.md content."""
    assert IMPLEMENT_MD.exists(), f"implement.md not found at {IMPLEMENT_MD}"
    return IMPLEMENT_MD.read_text()


class TestBackgroundAgentDrainGate:
    """implement-batch.md must have a HARD GATE for draining background agents between issues."""

    def test_batch_has_background_drain_gate(self, batch_content: str):
        """implement-batch.md must contain background agent drain HARD GATE."""
        assert "Background Agent Drain" in batch_content, (
            "implement-batch.md is missing 'Background Agent Drain' gate. "
            "Background agents must be drained between issues to prevent memory exhaustion."
        )

    def test_drain_gate_is_hard_gate(self, batch_content: str):
        """The background agent drain must be a HARD GATE."""
        # Find the drain section and verify it contains HARD GATE
        drain_pos = batch_content.find("Background Agent Drain")
        assert drain_pos != -1, "Background Agent Drain section not found"
        # Check nearby text for HARD GATE designation
        section = batch_content[max(0, drain_pos - 200):drain_pos + 500]
        assert "HARD GATE" in section, (
            "Background Agent Drain is not designated as HARD GATE. "
            "Must be blocking to prevent memory exhaustion."
        )

    def test_drain_gate_forbids_background_step9_in_batch(self, batch_content: str):
        """Batch mode must forbid run_in_background for STEP 9."""
        assert "run_in_background: false" in batch_content or "foreground" in batch_content.lower(), (
            "implement-batch.md must specify that STEP 9 runs in foreground during batch. "
            "Background STEP 9 agents accumulate across issues and exhaust memory."
        )


class TestMaxConcurrentBackgroundAgents:
    """implement-batch.md must enforce max 2 concurrent background agents."""

    def test_batch_has_max_concurrent_limit(self, batch_content: str):
        """implement-batch.md must specify max concurrent background agents."""
        assert "2" in batch_content and "concurrent" in batch_content.lower(), (
            "implement-batch.md must specify max 2 concurrent background agents."
        )

    def test_batch_forbids_fire_and_forget(self, batch_content: str):
        """implement-batch.md must forbid fire-and-forget agent launches."""
        assert "fire-and-forget" in batch_content.lower(), (
            "implement-batch.md must explicitly forbid fire-and-forget agent launches "
            "without tracking task IDs for later drain."
        )


class TestBatchIssuesModeReferences:
    """Batch issues mode must reference the drain gate and foreground STEP 9."""

    def test_batch_issues_references_foreground_step9(self, batch_content: str):
        """Batch issues mode section must mention foreground STEP 9."""
        # Find the BATCH ISSUES MODE section
        issues_pos = batch_content.find("# BATCH ISSUES MODE")
        assert issues_pos != -1, "BATCH ISSUES MODE section not found"
        issues_section = batch_content[issues_pos:]
        assert "foreground" in issues_section.lower(), (
            "BATCH ISSUES MODE section must reference foreground STEP 9 requirement."
        )

    def test_batch_issues_references_drain_gate(self, batch_content: str):
        """Batch issues mode section must reference background agent drain."""
        issues_pos = batch_content.find("# BATCH ISSUES MODE")
        assert issues_pos != -1, "BATCH ISSUES MODE section not found"
        issues_section = batch_content[issues_pos:]
        assert "drain" in issues_section.lower() or "background" in issues_section.lower(), (
            "BATCH ISSUES MODE section must reference background agent drain requirement."
        )
