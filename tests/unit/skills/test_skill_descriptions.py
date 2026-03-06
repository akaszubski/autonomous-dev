#!/usr/bin/env python3
"""
TDD Tests for Skill Description Optimization (Issue #388 - Red Phase)

Validates that all SKILL.md description fields follow the optimized format:
1. Concrete capabilities (what it does)
2. "Use when" trigger conditions
3. TRIGGER keyword list
4. DO NOT TRIGGER exclusion list

These tests should FAIL initially since descriptions have not been updated yet.
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple

import pytest
import yaml

# --- Constants ---

SKILLS_DIR = (
    Path(__file__).resolve().parents[3]
    / "plugins"
    / "autonomous-dev"
    / "skills"
)

EXCLUDED_DIRS = {"archived", "__pycache__"}


# --- Helpers ---


def discover_active_skills() -> List[Path]:
    """Dynamically discover all active SKILL.md files."""
    skills = []
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if skill_dir.is_dir() and skill_dir.name not in EXCLUDED_DIRS:
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                skills.append(skill_file)
    return skills


def parse_yaml_frontmatter(skill_path: Path) -> Tuple[Dict, str]:
    """Parse YAML frontmatter from a SKILL.md file.

    Returns:
        Tuple of (parsed YAML dict, raw frontmatter string).

    Raises:
        ValueError: If no valid YAML frontmatter found.
    """
    content = skill_path.read_text(encoding="utf-8")
    # Match content between first two --- delimiters
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        raise ValueError(f"No YAML frontmatter found in {skill_path}")
    raw = match.group(1)
    parsed = yaml.safe_load(raw)
    return parsed, raw


# --- Fixtures ---


ACTIVE_SKILLS = discover_active_skills()
SKILL_NAMES = [s.parent.name for s in ACTIVE_SKILLS]


@pytest.fixture(scope="module")
def all_skill_data() -> Dict[str, Tuple[Dict, str]]:
    """Parse all skill frontmatter once for the module."""
    data = {}
    for skill_path in ACTIVE_SKILLS:
        name = skill_path.parent.name
        data[name] = parse_yaml_frontmatter(skill_path)
    return data


# --- TestSkillDescriptionCompleteness ---


class TestSkillDescriptionCompleteness:
    """Validates all skills follow the optimized description pattern."""

    @pytest.mark.parametrize("skill_path", ACTIVE_SKILLS, ids=SKILL_NAMES)
    def test_all_skills_have_description(self, skill_path: Path) -> None:
        """Every SKILL.md has a non-empty 'description' field in YAML frontmatter."""
        frontmatter, _ = parse_yaml_frontmatter(skill_path)
        desc = frontmatter.get("description", "")
        assert desc and isinstance(desc, str) and len(desc.strip()) > 0, (
            f"{skill_path.parent.name}: missing or empty 'description' field"
        )

    @pytest.mark.parametrize("skill_path", ACTIVE_SKILLS, ids=SKILL_NAMES)
    def test_descriptions_contain_use_when(self, skill_path: Path) -> None:
        """Every description contains 'Use when' trigger text."""
        frontmatter, _ = parse_yaml_frontmatter(skill_path)
        desc = frontmatter.get("description", "")
        assert re.search(r"[Uu]se when", desc), (
            f"{skill_path.parent.name}: description missing 'Use when' trigger conditions. "
            f"Current description: {desc!r}"
        )

    @pytest.mark.parametrize("skill_path", ACTIVE_SKILLS, ids=SKILL_NAMES)
    def test_descriptions_contain_trigger_keywords(self, skill_path: Path) -> None:
        """Every description contains a TRIGGER keyword section."""
        frontmatter, _ = parse_yaml_frontmatter(skill_path)
        desc = frontmatter.get("description", "")
        # Accept various formats: "TRIGGER:", "TRIGGER when", "TRIGGER keywords:"
        assert re.search(r"TRIGGER", desc, re.IGNORECASE), (
            f"{skill_path.parent.name}: description missing TRIGGER keyword section. "
            f"Current description: {desc!r}"
        )

    @pytest.mark.parametrize("skill_path", ACTIVE_SKILLS, ids=SKILL_NAMES)
    def test_descriptions_contain_do_not_trigger(self, skill_path: Path) -> None:
        """Every description contains DO NOT TRIGGER exclusion conditions."""
        frontmatter, _ = parse_yaml_frontmatter(skill_path)
        desc = frontmatter.get("description", "")
        assert re.search(r"DO NOT TRIGGER", desc, re.IGNORECASE), (
            f"{skill_path.parent.name}: description missing 'DO NOT TRIGGER' exclusion list. "
            f"Current description: {desc!r}"
        )

    @pytest.mark.parametrize("skill_path", ACTIVE_SKILLS, ids=SKILL_NAMES)
    def test_description_length_within_bounds(self, skill_path: Path) -> None:
        """Every description is between 100 and 500 characters."""
        frontmatter, _ = parse_yaml_frontmatter(skill_path)
        desc = frontmatter.get("description", "")
        length = len(desc)
        assert 100 <= length <= 500, (
            f"{skill_path.parent.name}: description length {length} chars "
            f"(expected 100-500). Current description: {desc!r}"
        )

    @pytest.mark.parametrize("skill_path", ACTIVE_SKILLS, ids=SKILL_NAMES)
    def test_yaml_frontmatter_valid(self, skill_path: Path) -> None:
        """Every SKILL.md has valid YAML frontmatter that parses without error."""
        try:
            frontmatter, _ = parse_yaml_frontmatter(skill_path)
        except (ValueError, yaml.YAMLError) as e:
            pytest.fail(
                f"{skill_path.parent.name}: invalid YAML frontmatter: {e}"
            )
        # Must have at minimum: name, description
        assert "name" in frontmatter, (
            f"{skill_path.parent.name}: frontmatter missing 'name' field"
        )
        assert "description" in frontmatter, (
            f"{skill_path.parent.name}: frontmatter missing 'description' field"
        )

    def test_all_active_skills_present(self) -> None:
        """At least 16 active skill directories exist (dynamic minimum threshold)."""
        skill_count = len(ACTIVE_SKILLS)
        assert skill_count >= 16, (
            f"Expected at least 16 active skills, found {skill_count}. "
            f"Skills found: {SKILL_NAMES}"
        )


# --- TestSkillDescriptionQuality ---


class TestSkillDescriptionQuality:
    """Validates description quality patterns (anti-pattern detection)."""

    @pytest.mark.parametrize("skill_path", ACTIVE_SKILLS, ids=SKILL_NAMES)
    def test_no_generic_enforcement_pattern(self, skill_path: Path) -> None:
        """No description starts with 'Enforcement skill for' (anti-pattern)."""
        frontmatter, _ = parse_yaml_frontmatter(skill_path)
        desc = frontmatter.get("description", "")
        assert not desc.startswith("Enforcement skill for"), (
            f"{skill_path.parent.name}: description uses generic 'Enforcement skill for' "
            f"anti-pattern. Descriptions should start with concrete capabilities. "
            f"Current: {desc!r}"
        )

    @pytest.mark.parametrize("skill_path", ACTIVE_SKILLS, ids=SKILL_NAMES)
    def test_descriptions_use_active_voice(self, skill_path: Path) -> None:
        """No description starts with 'A skill that' or 'This skill' (passive pattern)."""
        frontmatter, _ = parse_yaml_frontmatter(skill_path)
        desc = frontmatter.get("description", "").strip()
        passive_starts = ("A skill that", "This skill", "A skill for")
        for pattern in passive_starts:
            assert not desc.startswith(pattern), (
                f"{skill_path.parent.name}: description uses passive voice pattern "
                f"'{pattern}...'. Use active voice with concrete capabilities instead. "
                f"Current: {desc!r}"
            )

    def test_no_duplicate_descriptions(self) -> None:
        """All skill descriptions are unique (no copy-paste)."""
        descriptions: Dict[str, str] = {}
        duplicates: List[str] = []
        for skill_path in ACTIVE_SKILLS:
            name = skill_path.parent.name
            frontmatter, _ = parse_yaml_frontmatter(skill_path)
            desc = frontmatter.get("description", "").strip()
            if desc in descriptions.values():
                # Find which skill has the same description
                dup_name = [k for k, v in descriptions.items() if v == desc][0]
                duplicates.append(f"{name} == {dup_name}")
            descriptions[name] = desc
        assert not duplicates, (
            f"Duplicate descriptions found: {duplicates}"
        )
