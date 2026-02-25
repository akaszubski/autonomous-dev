"""Tests for Coverage Gap Assessment HARD GATE in test-master.md.

TDD Red Phase: These tests validate the structural and content requirements
for the new Coverage Gap Assessment section in test-master.md, and the
corresponding STEP 4 updates in implement.md.

Tests will FAIL until the implementation is applied.
"""

import re
from pathlib import Path

import pytest

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
TEST_MASTER = PROJECT_ROOT / "plugins" / "autonomous-dev" / "agents" / "test-master.md"
IMPLEMENT_CMD = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"


class TestCoverageGapAssessmentHardGate:
    """Verify test-master.md contains Coverage Gap Assessment HARD GATE."""

    @pytest.fixture(autouse=True)
    def load_content(self):
        self.content = TEST_MASTER.read_text()

    def test_hard_gate_section_exists(self):
        """Coverage Gap Assessment HARD GATE section must exist."""
        assert "## HARD GATE: Coverage Gap Assessment" in self.content

    def test_decision_table_exists(self):
        """Section must contain a decision table mapping change types to test types."""
        # Find the section
        section_start = self.content.find("Coverage Gap Assessment")
        assert section_start != -1, "Coverage Gap Assessment section not found"
        section_text = self.content[section_start:]

        # Must have a markdown table with pipe characters
        table_lines = [
            line for line in section_text.split("\n")
            if line.strip().startswith("|") and line.strip().endswith("|")
        ]
        assert len(table_lines) >= 4, (
            f"Decision table should have header + separator + at least 2 data rows, "
            f"found {len(table_lines)} table lines"
        )

    def test_decision_table_has_required_change_types(self):
        """Decision table must cover key change types."""
        section_start = self.content.find("Coverage Gap Assessment")
        section_text = self.content[section_start:]

        required_types = ["API", "logic", "config", "UI"]
        found = []
        for ct in required_types:
            if re.search(rf"\|\s*.*{ct}.*\s*\|", section_text, re.IGNORECASE):
                found.append(ct)

        missing = set(required_types) - set(found)
        assert not missing, f"Decision table missing change types: {missing}"

    def test_forbidden_list_exists(self):
        """Section must contain a FORBIDDEN list."""
        section_start = self.content.find("Coverage Gap Assessment")
        assert section_start != -1
        section_text = self.content[section_start:]

        assert "FORBIDDEN" in section_text, "FORBIDDEN list not found in Coverage Gap Assessment"

    def test_forbidden_list_has_items(self):
        """FORBIDDEN list must have concrete forbidden behaviors."""
        section_start = self.content.find("Coverage Gap Assessment")
        section_text = self.content[section_start:]

        # Find FORBIDDEN keyword and check for bullet items after it
        forbidden_pos = section_text.find("FORBIDDEN")
        after_forbidden = section_text[forbidden_pos:forbidden_pos + 500]
        bullets = [l for l in after_forbidden.split("\n") if l.strip().startswith("- ")]
        assert len(bullets) >= 2, f"FORBIDDEN list needs at least 2 items, found {len(bullets)}"

    def test_gap_summary_output_required(self):
        """Section must require a gap summary output before writing tests."""
        section_start = self.content.find("Coverage Gap Assessment")
        section_text = self.content[section_start:]

        # Should mention gap summary / output format
        assert re.search(r"gap\s+summary", section_text, re.IGNORECASE), (
            "Section must require a gap summary output"
        )

    def test_existing_hard_gate_still_present(self):
        """The existing 'No Hardcoded Counts' HARD GATE must not be removed."""
        assert "## HARD GATE: No Hardcoded Counts" in self.content


class TestWorkflowReferencesGapAssessment:
    """Verify Workflow section references gap assessment."""

    def test_workflow_mentions_gap_assessment(self):
        content = TEST_MASTER.read_text()
        workflow_start = content.find("## Workflow")
        assert workflow_start != -1, "Workflow section not found"
        workflow_text = content[workflow_start:]

        assert re.search(r"gap\s+assess", workflow_text, re.IGNORECASE), (
            "Workflow section must reference gap assessment as a step"
        )


class TestImplementStepFourUpdates:
    """Verify implement.md STEP 4 passes file list and GenAI infra status."""

    @pytest.fixture(autouse=True)
    def load_content(self):
        self.content = IMPLEMENT_CMD.read_text()

    def _get_step4_text(self) -> str:
        """Extract STEP 4 section text."""
        match = re.search(r"###\s+STEP\s+4.*", self.content)
        assert match, "STEP 4 not found in implement.md"
        start = match.start()
        # Find next STEP or end
        next_step = re.search(r"###\s+STEP\s+5", self.content[start + 10:])
        if next_step:
            return self.content[start:start + 10 + next_step.start()]
        return self.content[start:]

    def test_step4_mentions_file_list(self):
        """STEP 4 must mention passing file list to test-master."""
        step4 = self._get_step4_text()
        assert re.search(r"file\s+list", step4, re.IGNORECASE), (
            "STEP 4 must mention passing file list to test-master"
        )

    def test_step4_mentions_genai_infra_status(self):
        """STEP 4 must mention passing GenAI infrastructure status."""
        step4 = self._get_step4_text()
        assert re.search(r"genai|GenAI", step4), (
            "STEP 4 must mention GenAI infrastructure status"
        )

    def test_step4_no_broken_markdown(self):
        """STEP 4 should not have broken markdown (unclosed fences, etc.)."""
        step4 = self._get_step4_text()
        # Count code fences - should be even
        fence_count = step4.count("```")
        assert fence_count % 2 == 0, f"Unclosed code fence in STEP 4 ({fence_count} fences)"


class TestCrossFileConsistency:
    """Verify consistency between implement.md STEP 4 and test-master.md expectations."""

    def test_step4_passes_what_test_master_expects(self):
        """What STEP 4 says to pass must match what test-master expects to receive."""
        impl_content = IMPLEMENT_CMD.read_text()
        tm_content = TEST_MASTER.read_text()

        # test-master should mention receiving/expecting file list
        gap_section_start = tm_content.find("Coverage Gap Assessment")
        assert gap_section_start != -1, "Coverage Gap Assessment not in test-master.md"
        gap_text = tm_content[gap_section_start:]

        # Both should reference file list concept
        assert re.search(r"file", gap_text, re.IGNORECASE), (
            "test-master Coverage Gap Assessment should reference files to analyze"
        )

    def test_no_broken_markdown_test_master(self):
        """test-master.md should have valid markdown structure."""
        content = TEST_MASTER.read_text()
        # All code fences should be paired
        fence_count = content.count("```")
        assert fence_count % 2 == 0, f"Unclosed code fence in test-master.md ({fence_count})"

        # All ## headers should have text after them
        for line in content.split("\n"):
            if line.startswith("## "):
                assert len(line.strip()) > 3, f"Empty header found: '{line}'"
