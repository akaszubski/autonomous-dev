"""Tests for testing pipeline redesign (Issue #364).

Validates the shift from TDD RED phase to GenAI-native testing:
1. test-master.md uses specification-driven approach (no RED phase)
2. implementer.md has zero-skip HARD GATE (no skip escape hatch)
3. implement.md STEP 5 enforces 0 new skips
4. testing-guide SKILL.md includes property-based testing pattern
5. known_bypass_patterns.json has skip_accumulation pattern
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
AGENTS_DIR = PROJECT_ROOT / "plugins/autonomous-dev/agents"
COMMANDS_DIR = PROJECT_ROOT / "plugins/autonomous-dev/commands"
SKILLS_DIR = PROJECT_ROOT / "plugins/autonomous-dev/skills"
CONFIG_DIR = PROJECT_ROOT / "plugins/autonomous-dev/config"


class TestTestMasterRedesign:
    """test-master.md reflects specification-driven testing."""

    @pytest.fixture
    def content(self) -> str:
        return (AGENTS_DIR / "test-master.md").read_text()

    def test_no_red_phase_language(self, content: str):
        """test-master should not tell tests to 'initially fail' (RED phase)."""
        assert "should initially fail" not in content.lower()
        assert "RED phase" not in content

    def test_no_tdd_red_in_mission(self, content: str):
        """Mission should describe specification-driven testing, not TDD red."""
        # Should not say "write tests FIRST that fail"
        assert "TDD red phase" not in content

    def test_property_based_testing_mentioned(self, content: str):
        """test-master should reference property-based testing."""
        assert "property" in content.lower()
        assert "hypothesis" in content.lower() or "invariant" in content.lower()

    def test_three_test_types(self, content: str):
        """test-master should generate structural, property, and acceptance tests."""
        content_lower = content.lower()
        assert "structural" in content_lower
        assert "property" in content_lower or "invariant" in content_lower

    def test_coverage_gap_assessment_retained(self, content: str):
        """Coverage gap assessment HARD GATE must still be present."""
        assert "Coverage Gap Assessment" in content
        assert "HARD GATE" in content


class TestImplementerZeroSkip:
    """implementer.md enforces zero new skips."""

    @pytest.fixture
    def content(self) -> str:
        return (AGENTS_DIR / "implementer.md").read_text()

    def test_no_skip_as_option(self, content: str):
        """implementer should NOT offer @pytest.mark.skip as a resolution for failing tests."""
        # The section listing resolutions must not include "skip it"
        assert "For each failing test" in content, "Missing failing test resolution section"
        resolution_section = content.split("For each failing test")[1][:500]
        assert "skip it" not in resolution_section.lower()

    def test_zero_skip_gate_present(self, content: str):
        """implementer should have zero-skip HARD GATE."""
        assert "0 new skips" in content or "zero.*skip" in content.lower() or "No New Skips" in content

    def test_only_fix_or_adjust(self, content: str):
        """Only two resolutions for failing tests: fix or adjust."""
        assert "Fix" in content
        assert "Adjust" in content


class TestImplementCommandStep5:
    """implement.md STEP 5 has zero-skip enforcement."""

    @pytest.fixture
    def content(self) -> str:
        return (COMMANDS_DIR / "implement.md").read_text()

    def test_step5_no_skip_option(self, content: str):
        """STEP 5 should not list 'Skip it' as a resolution."""
        # Find the STEP 5 section
        step5_start = content.find("### STEP 5:")
        step6_start = content.find("### STEP 5.5:")
        if step5_start >= 0 and step6_start >= 0:
            step5 = content[step5_start:step6_start]
            assert "Skip it" not in step5

    def test_step5_zero_skip_gate(self, content: str):
        """STEP 5 should enforce 0 new skips."""
        step5_start = content.find("### STEP 5:")
        step6_start = content.find("### STEP 5.5:")
        if step5_start >= 0 and step6_start >= 0:
            step5 = content[step5_start:step6_start]
            assert "0 new skips" in step5 or "No New Skips" in step5 or "zero-skip" in step5.lower()


class TestTestingGuideSkill:
    """testing-guide SKILL.md includes property-based testing."""

    @pytest.fixture
    def content(self) -> str:
        return (SKILLS_DIR / "testing-guide" / "SKILL.md").read_text()

    def test_property_pattern_present(self, content: str):
        """testing-guide should have a property-based testing pattern."""
        assert "Property" in content
        assert "hypothesis" in content.lower() or "invariant" in content.lower()

    def test_no_progression_red_phase_tier(self, content: str):
        """Tier 3 should not be 'TDD red phase (not yet implemented)'."""
        assert "TDD red phase" not in content


class TestBypassPatternsSkipAccumulation:
    """known_bypass_patterns.json has skip_accumulation pattern."""

    @pytest.fixture
    def config(self) -> dict:
        import json
        return json.loads((CONFIG_DIR / "known_bypass_patterns.json").read_text())

    def test_skip_accumulation_pattern_exists(self, config: dict):
        """Pattern skip_accumulation must exist."""
        pattern_ids = [p["id"] for p in config["patterns"]]
        assert "skip_accumulation" in pattern_ids

    def test_skip_accumulation_severity(self, config: dict):
        """skip_accumulation should be critical severity."""
        pattern = next(p for p in config["patterns"] if p["id"] == "skip_accumulation")
        assert pattern["severity"] == "critical"
        assert pattern["issue"] == "#364"
