"""GenAI functional tests for Coverage Gap Assessment HARD GATE quality.

Validates semantic quality of the new HARD GATE section using LLM-as-judge.
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
TEST_MASTER = PROJECT_ROOT / "plugins" / "autonomous-dev" / "agents" / "test-master.md"
IMPLEMENT_CMD = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"


@pytest.mark.genai
class TestCoverageGapGateQuality:
    """Semantic validation of Coverage Gap Assessment content."""

    def test_decision_table_completeness(self, genai):
        """Decision table should map all common change types to appropriate test types."""
        content = TEST_MASTER.read_text()
        start = content.find("## HARD GATE: Coverage Gap Assessment (Run FIRST)")
        if start == -1:
            pytest.fail("Coverage Gap Assessment section not found")

        # Extract table lines (need 3500+ chars to reach FORBIDDEN block)
        section = content[start:start + 3500]
        table_lines = [
            l.strip() for l in section.split("\n")
            if l.strip().startswith("|") and l.strip().endswith("|")
        ]

        result = genai.judge(
            question="Does this decision table comprehensively map change types to test types?",
            context="\n".join(table_lines),
            criteria=(
                "Table should cover: API/endpoint changes, business logic, config/schema, "
                "UI/frontend, data model, and error handling changes. Each should map to "
                "specific test types (unit, integration, edge case, GenAI). "
                "Deduct 2 per missing major category. Deduct 1 if test type recommendations are vague."
            ),
            category="prompt_quality",
        )
        assert result.get("pass", False), result.get("reasoning", "No reasoning")

    def test_forbidden_list_actionable(self, genai):
        """FORBIDDEN list items should be specific and actionable, not vague."""
        content = TEST_MASTER.read_text()
        start = content.find("## HARD GATE: Coverage Gap Assessment (Run FIRST)")
        if start == -1:
            pytest.fail("Coverage Gap Assessment section not found")

        section = content[start:start + 3500]
        # Extract lines after FORBIDDEN
        forbidden_pos = section.find("**FORBIDDEN**")
        if forbidden_pos == -1:
            pytest.fail("FORBIDDEN keyword not found")

        forbidden_block = section[forbidden_pos:forbidden_pos + 600]

        result = genai.judge(
            question="Are these FORBIDDEN behaviors specific and actionable?",
            context=forbidden_block,
            criteria=(
                "Each forbidden item should describe a specific bad behavior that a model "
                "might actually do, not vague platitudes. Good: 'Writing tests without "
                "checking which files changed'. Bad: 'Being careless'. "
                "Deduct 3 per vague item. Deduct 2 if fewer than 3 items."
            ),
            category="prompt_quality",
        )
        assert result.get("pass", False), result.get("reasoning", "No reasoning")

    def test_cross_file_coherence(self, genai):
        """STEP 4 and test-master gap assessment should be coherent."""
        impl_content = IMPLEMENT_CMD.read_text()
        tm_content = TEST_MASTER.read_text()

        # Extract STEP 4
        step4_match = re.search(r"(###\s+STEP\s+4.*?)(?=###\s+STEP\s+5)", impl_content, re.DOTALL)
        step4 = step4_match.group(1) if step4_match else "STEP 4 NOT FOUND"

        # Extract gap assessment section
        gap_start = tm_content.find("Coverage Gap Assessment")
        gap_text = tm_content[gap_start:gap_start + 1500] if gap_start != -1 else "SECTION NOT FOUND"

        result = genai.judge(
            question="Are these two sections coherent? Does STEP 4 pass what test-master expects?",
            context=f"=== STEP 4 (implement.md) ===\n{step4}\n\n=== Coverage Gap Assessment (test-master.md) ===\n{gap_text}",
            criteria=(
                "STEP 4 should mention passing a file list and GenAI infra status. "
                "test-master should expect to receive these inputs and use them in gap assessment. "
                "The handoff should be clear and unambiguous. "
                "Deduct 5 if either section is missing. Deduct 3 if inputs don't match."
            ),
            category="cross_file",
        )
        assert result.get("pass", False), result.get("reasoning", "No reasoning")
