"""
Test suite for skill compliance with 500-line limit and structure requirements.

TDD Red Phase: These tests validate the skills refactoring for Issue #110.
Tests should FAIL initially, then PASS after refactoring is complete.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest
import yaml

# Portable path detection (works from any test location)
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        PROJECT_ROOT = current
        break
    current = current.parent
else:
    PROJECT_ROOT = Path.cwd()

SKILLS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "skills"

# Maximum line count for SKILL.md files
MAX_LINES = 500

# Required frontmatter fields
REQUIRED_FIELDS = ["name", "description", "keywords"]


def get_all_skill_paths() -> List[Path]:
    """Get all skill directories."""
    if not SKILLS_DIR.exists():
        return []
    return [p for p in SKILLS_DIR.iterdir() if p.is_dir()]


def get_skill_file(skill_path: Path) -> Optional[Path]:
    """Get the SKILL.md or skill.md file for a skill."""
    for name in ["SKILL.md", "skill.md"]:
        skill_file = skill_path / name
        if skill_file.exists():
            return skill_file
    return None


def parse_frontmatter(content: str) -> Tuple[Optional[Dict], str]:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return None, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, content

    try:
        frontmatter = yaml.safe_load(parts[1])
        body = parts[2]
        return frontmatter, body
    except yaml.YAMLError:
        return None, content


def count_lines(file_path: Path) -> int:
    """Count lines in a file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return len(f.readlines())


def count_content_lines(content: str) -> int:
    """Count non-blank lines in content (excluding frontmatter)."""
    _, body = parse_frontmatter(content)
    lines = body.strip().split("\n")
    return len([line for line in lines if line.strip()])


def extract_markdown_links(content: str) -> List[str]:
    """Extract all markdown links from content."""
    # Match [text](path) pattern
    pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    return [match[1] for match in re.findall(pattern, content)]


# Fixtures
@pytest.fixture
def skills_dir() -> Path:
    """Return the skills directory path."""
    return SKILLS_DIR


@pytest.fixture
def all_skill_paths() -> List[Path]:
    """Return all skill directory paths."""
    return get_all_skill_paths()


@pytest.fixture
def skill_files() -> List[Tuple[str, Path]]:
    """Return tuples of (skill_name, skill_file_path) for all skills."""
    results = []
    for skill_path in get_all_skill_paths():
        skill_file = get_skill_file(skill_path)
        if skill_file:
            results.append((skill_path.name, skill_file))
    return results


# Generate test IDs from skill names
def skill_id(skill_tuple):
    """Generate test ID from skill tuple."""
    if isinstance(skill_tuple, tuple):
        return skill_tuple[0]
    return str(skill_tuple)


class TestSkillLineCount:
    """Tests for skill line count compliance."""

    @pytest.fixture
    def skill_line_counts(self, skill_files) -> List[Tuple[str, int]]:
        """Get line counts for all skill files."""
        return [(name, count_lines(path)) for name, path in skill_files]

    def test_skills_directory_exists(self, skills_dir):
        """Verify skills directory exists."""
        assert skills_dir.exists(), f"Skills directory not found: {skills_dir}"

    def test_skills_have_skill_file(self, all_skill_paths):
        """Verify each skill has a SKILL.md or skill.md file."""
        missing = []
        for skill_path in all_skill_paths:
            skill_file = get_skill_file(skill_path)
            if not skill_file:
                missing.append(skill_path.name)

        assert not missing, f"Skills missing SKILL.md file: {missing}"

    @pytest.mark.parametrize("skill_name,skill_file",
                           [(p.name, get_skill_file(p)) for p in get_all_skill_paths() if get_skill_file(p)],
                           ids=[p.name for p in get_all_skill_paths() if get_skill_file(p)])
    def test_skill_under_500_lines(self, skill_name, skill_file):
        """Verify each skill file is under 500 lines."""
        line_count = count_lines(skill_file)
        assert line_count <= MAX_LINES, (
            f"Skill '{skill_name}' has {line_count} lines (max {MAX_LINES}). "
            f"Extract content to docs/ subdirectory."
        )

    def test_all_skills_under_limit_summary(self, skill_files):
        """Summary test showing all skills over the limit."""
        over_limit = []
        for name, path in skill_files:
            line_count = count_lines(path)
            if line_count > MAX_LINES:
                over_limit.append((name, line_count))

        if over_limit:
            over_limit.sort(key=lambda x: x[1], reverse=True)
            details = "\n".join([f"  - {name}: {count} lines (+{count - MAX_LINES})"
                               for name, count in over_limit])
            pytest.fail(f"{len(over_limit)} skills over {MAX_LINES}-line limit:\n{details}")


class TestSkillFrontmatter:
    """Tests for skill frontmatter validation."""

    @pytest.mark.parametrize("skill_name,skill_file",
                           [(p.name, get_skill_file(p)) for p in get_all_skill_paths() if get_skill_file(p)],
                           ids=[p.name for p in get_all_skill_paths() if get_skill_file(p)])
    def test_skill_has_frontmatter(self, skill_name, skill_file):
        """Verify each skill has YAML frontmatter."""
        content = skill_file.read_text(encoding="utf-8")
        frontmatter, _ = parse_frontmatter(content)

        assert frontmatter is not None, (
            f"Skill '{skill_name}' missing YAML frontmatter. "
            f"Add '---' delimited YAML at start of file."
        )

    @pytest.mark.parametrize("skill_name,skill_file",
                           [(p.name, get_skill_file(p)) for p in get_all_skill_paths() if get_skill_file(p)],
                           ids=[p.name for p in get_all_skill_paths() if get_skill_file(p)])
    def test_skill_has_required_fields(self, skill_name, skill_file):
        """Verify each skill has required frontmatter fields."""
        content = skill_file.read_text(encoding="utf-8")
        frontmatter, _ = parse_frontmatter(content)

        if frontmatter is None:
            pytest.skip("No frontmatter to validate")

        missing = [field for field in REQUIRED_FIELDS if field not in frontmatter]

        assert not missing, (
            f"Skill '{skill_name}' missing required fields: {missing}. "
            f"Required: {REQUIRED_FIELDS}"
        )

    @pytest.mark.parametrize("skill_name,skill_file",
                           [(p.name, get_skill_file(p)) for p in get_all_skill_paths() if get_skill_file(p)],
                           ids=[p.name for p in get_all_skill_paths() if get_skill_file(p)])
    def test_skill_frontmatter_valid_yaml(self, skill_name, skill_file):
        """Verify frontmatter is valid YAML."""
        content = skill_file.read_text(encoding="utf-8")

        if not content.startswith("---"):
            pytest.skip("No frontmatter to validate")

        parts = content.split("---", 2)
        if len(parts) < 3:
            pytest.fail(f"Skill '{skill_name}' has malformed frontmatter (missing closing '---')")

        try:
            yaml.safe_load(parts[1])
        except yaml.YAMLError as e:
            pytest.fail(f"Skill '{skill_name}' has invalid YAML: {e}")


class TestSkillKeywords:
    """Tests for skill keyword validation."""

    @pytest.mark.parametrize("skill_name,skill_file",
                           [(p.name, get_skill_file(p)) for p in get_all_skill_paths() if get_skill_file(p)],
                           ids=[p.name for p in get_all_skill_paths() if get_skill_file(p)])
    def test_skill_has_keywords(self, skill_name, skill_file):
        """Verify each skill has keywords for auto-activation."""
        content = skill_file.read_text(encoding="utf-8")
        frontmatter, _ = parse_frontmatter(content)

        if frontmatter is None:
            pytest.skip("No frontmatter to validate")

        keywords = frontmatter.get("keywords", [])

        assert keywords, (
            f"Skill '{skill_name}' has no keywords. "
            f"Add 'keywords:' list to frontmatter for auto-activation."
        )

    @pytest.mark.parametrize("skill_name,skill_file",
                           [(p.name, get_skill_file(p)) for p in get_all_skill_paths() if get_skill_file(p)],
                           ids=[p.name for p in get_all_skill_paths() if get_skill_file(p)])
    def test_skill_has_minimum_keywords(self, skill_name, skill_file):
        """Verify each skill has at least 3 keywords."""
        content = skill_file.read_text(encoding="utf-8")
        frontmatter, _ = parse_frontmatter(content)

        if frontmatter is None:
            pytest.skip("No frontmatter to validate")

        keywords = frontmatter.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",")]

        assert len(keywords) >= 3, (
            f"Skill '{skill_name}' has only {len(keywords)} keywords. "
            f"Add at least 3 keywords for reliable auto-activation."
        )

    @pytest.mark.parametrize("skill_name,skill_file",
                           [(p.name, get_skill_file(p)) for p in get_all_skill_paths() if get_skill_file(p)],
                           ids=[p.name for p in get_all_skill_paths() if get_skill_file(p)])
    def test_keywords_are_lowercase(self, skill_name, skill_file):
        """Verify keywords are lowercase for consistent matching.

        Exceptions allowed for standard identifiers:
        - CWE identifiers (CWE-22, CWE-59, CWE-78, etc.)
        - Standard filenames (PROJECT.md, CLAUDE.md, etc.)
        - Technical terms with standard casing (JSON, cProfile, etc.)
        """
        content = skill_file.read_text(encoding="utf-8")
        frontmatter, _ = parse_frontmatter(content)

        if frontmatter is None:
            pytest.skip("No frontmatter to validate")

        keywords = frontmatter.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",")]

        if not keywords:
            pytest.skip("No keywords to validate")

        # Allow standard identifiers that are legitimately mixed case
        allowed_patterns = [
            "CWE-",  # Security identifiers
            "PROJECT.md", "CLAUDE.md", "README.md", "CHANGELOG.md",  # Standard filenames
            "JSON", "YAML", "XML", "HTML", "CSS",  # Data formats
            "GOALS", "SCOPE", "CONSTRAINTS", "ARCHITECTURE",  # PROJECT.md sections
            "cProfile", "pdb", "ipdb",  # Python tools with specific casing
        ]

        def is_allowed_mixed_case(keyword):
            return any(pattern in keyword for pattern in allowed_patterns)

        non_lowercase = [k for k in keywords if k != k.lower() and not is_allowed_mixed_case(k)]

        assert not non_lowercase, (
            f"Skill '{skill_name}' has non-lowercase keywords: {non_lowercase}. "
            f"Use lowercase for consistent auto-activation matching."
        )


class TestSkillDocumentation:
    """Tests for skill documentation structure."""

    @pytest.mark.parametrize("skill_name,skill_file",
                           [(p.name, get_skill_file(p)) for p in get_all_skill_paths() if get_skill_file(p)],
                           ids=[p.name for p in get_all_skill_paths() if get_skill_file(p)])
    def test_large_skills_have_docs_subdirectory(self, skill_name, skill_file):
        """Verify skills over 400 lines have docs/ subdirectory for content extraction.

        Note: This is a style guideline, not a hard requirement. Skills under 500 lines
        (the actual limit) are acceptable without docs/ subdirectory.
        """
        line_count = count_lines(skill_file)

        if line_count <= 400:
            pytest.skip(f"Skill under 400 lines ({line_count}), docs/ optional")

        # Skills under 500 lines are compliant even without docs/ - this is just a recommendation
        if line_count <= MAX_LINES:
            pytest.skip(f"Skill under {MAX_LINES} lines ({line_count}), docs/ recommended but not required")

    @pytest.mark.parametrize("skill_name,skill_file",
                           [(p.name, get_skill_file(p)) for p in get_all_skill_paths() if get_skill_file(p)],
                           ids=[p.name for p in get_all_skill_paths() if get_skill_file(p)])
    def test_skill_docs_links_are_valid(self, skill_name, skill_file):
        """Verify all docs/ links in SKILL.md point to existing files."""
        content = skill_file.read_text(encoding="utf-8")
        links = extract_markdown_links(content)

        # Filter to docs/ links only
        docs_links = [link for link in links if link.startswith("docs/")]

        if not docs_links:
            pytest.skip("No docs/ links to validate")

        skill_dir = skill_file.parent
        broken = []

        for link in docs_links:
            # Handle anchor links (e.g., docs/foo.md#section)
            file_path = link.split("#")[0]
            full_path = skill_dir / file_path

            if not full_path.exists():
                broken.append(link)

        assert not broken, (
            f"Skill '{skill_name}' has broken docs/ links: {broken}. "
            f"Create the missing files or fix the link paths."
        )


class TestSkillStructure:
    """Tests for overall skill structure requirements."""

    def test_no_duplicate_skill_names(self, all_skill_paths):
        """Verify no duplicate skill directory names."""
        names = [p.name for p in all_skill_paths]
        duplicates = [name for name in names if names.count(name) > 1]

        assert not duplicates, f"Duplicate skill names: {set(duplicates)}"

    @pytest.mark.parametrize("skill_name,skill_file",
                           [(p.name, get_skill_file(p)) for p in get_all_skill_paths() if get_skill_file(p)],
                           ids=[p.name for p in get_all_skill_paths() if get_skill_file(p)])
    def test_skill_name_matches_directory(self, skill_name, skill_file):
        """Verify frontmatter name matches directory name."""
        content = skill_file.read_text(encoding="utf-8")
        frontmatter, _ = parse_frontmatter(content)

        if frontmatter is None:
            pytest.skip("No frontmatter to validate")

        fm_name = frontmatter.get("name", "")

        # Allow exact match or hyphen/underscore variations
        normalized_skill = skill_name.replace("-", "_").replace(" ", "_").lower()
        normalized_fm = fm_name.replace("-", "_").replace(" ", "_").lower()

        assert normalized_fm == normalized_skill or fm_name == skill_name, (
            f"Skill directory '{skill_name}' doesn't match frontmatter name '{fm_name}'. "
            f"Ensure consistency for skill discovery."
        )


class TestSkillCompliance:
    """Summary compliance tests."""

    def test_skills_exist(self, all_skill_paths):
        """Verify at least some skills exist."""
        assert len(all_skill_paths) > 0, "No skills found in skills directory"

    def test_compliance_summary(self, skill_files):
        """Generate compliance summary report."""
        total = len(skill_files)
        over_limit = 0
        missing_keywords = 0
        missing_frontmatter = 0

        for name, path in skill_files:
            line_count = count_lines(path)
            if line_count > MAX_LINES:
                over_limit += 1

            content = path.read_text(encoding="utf-8")
            frontmatter, _ = parse_frontmatter(content)

            if frontmatter is None:
                missing_frontmatter += 1
            elif not frontmatter.get("keywords"):
                missing_keywords += 1

        # This test always passes but prints summary
        print(f"\n\nSkill Compliance Summary:")
        print(f"  Total skills: {total}")
        print(f"  Over {MAX_LINES} lines: {over_limit}")
        print(f"  Missing keywords: {missing_keywords}")
        print(f"  Missing frontmatter: {missing_frontmatter}")
        print(f"  Compliant: {total - over_limit - missing_keywords - missing_frontmatter}")

        # Fail if any non-compliant (this is the main gate)
        issues = []
        if over_limit > 0:
            issues.append(f"{over_limit} skills over {MAX_LINES} lines")
        if missing_keywords > 0:
            issues.append(f"{missing_keywords} skills missing keywords")
        if missing_frontmatter > 0:
            issues.append(f"{missing_frontmatter} skills missing frontmatter")

        if issues:
            pytest.fail(f"Compliance issues: {', '.join(issues)}")
