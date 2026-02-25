"""GenAI functional tests for STEP 9 continuous improvement enforcement quality.

Validates that the FORBIDDEN/REQUIRED items in STEP 9 are specific, actionable,
and coherent with the rest of the pipeline enforcement model.
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
IMPLEMENT_MD = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"


def _extract_section(content: str, pattern: str, end_pattern: str) -> str:
    """Extract a section from markdown content."""
    match = re.search(pattern + r".*?(?=" + end_pattern + r"|\Z)", content, re.DOTALL)
    return match.group(0) if match else ""


@pytest.mark.genai
class TestStep9EnforcementQuality:
    """Semantic validation that STEP 9 enforcement is coherent and actionable."""

    def test_forbidden_items_are_specific(self, genai):
        """Each FORBIDDEN item in STEP 9 should describe a concrete, detectable violation."""
        content = IMPLEMENT_MD.read_text()
        step9 = _extract_section(content, r"### STEP 9", r"\n---|\n# ")

        # Extract FORBIDDEN items
        forbidden_match = re.search(
            r"FORBIDDEN.*?\n((?:.*\n)*?)(?=\n\*\*|REQUIRED|\Z)", step9, re.DOTALL
        )
        forbidden_text = forbidden_match.group(0) if forbidden_match else step9

        result = genai.judge(
            question="Are these FORBIDDEN items specific and actionable?",
            context=forbidden_text,
            criteria=(
                "Each FORBIDDEN item should describe a concrete violation that can be "
                "detected by reading the pipeline output. Vague items like 'not doing it right' "
                "score 0. Items like 'Skipping the analyst invocation entirely' score 10. "
                "Deduct 2 per vague item. Deduct 3 if fewer than 3 items exist."
            ),
            category="architecture",
        )
        assert result["band"] != "hard_fail", result["reasoning"]

    def test_step9_coherent_with_coordinator(self, genai):
        """STEP 9 HARD GATE should be consistent with COORDINATOR FORBIDDEN LIST."""
        content = IMPLEMENT_MD.read_text()

        coordinator = _extract_section(
            content, r"COORDINATOR FORBIDDEN LIST", r"\nARGUMENTS|\n---|\n###"
        )
        step9 = _extract_section(content, r"### STEP 9", r"\n---|\n# ")

        combined = f"=== COORDINATOR FORBIDDEN LIST ===\n{coordinator}\n\n=== STEP 9 ===\n{step9}"

        result = genai.judge(
            question="Is STEP 9 enforcement coherent with the coordinator-level forbidden list?",
            context=combined,
            criteria=(
                "The coordinator forbidden list should mention STEP 9 or continuous improvement "
                "as something that must not be skipped. STEP 9 should have its own HARD GATE "
                "with FORBIDDEN items that are consistent (not contradictory) with the coordinator "
                "list. Score 10 if both sections reinforce each other. Deduct 5 if coordinator "
                "doesn't mention STEP 9 at all. Deduct 3 if they contradict."
            ),
            category="architecture",
        )
        assert result["band"] != "hard_fail", result["reasoning"]
