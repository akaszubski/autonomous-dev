#!/usr/bin/env python3
"""
Consolidated Skills Tests

Combines tests from:
- test_feature_v3_43_0_skill_compliance.py (Issue #110 - 500-line limit)
- test_feature_v3_43_0_skill_loader.py (Issue #140 - Skill injection)
- test_feature_v3_43_0_skill_tools.py (Issue #146 - allowed-tools frontmatter)

Tests verify:
1. Structure: Line limits, frontmatter, keywords, documentation
2. Loading: Skill loading, injection, security, graceful degradation
3. Tools: allowed-tools frontmatter, tool assignments, security constraints
"""

import pytest
import sys
import yaml
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

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

# Add lib to path for skill_loader imports
lib_path = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(lib_path))

# =============================================================================
# CONSTANTS
# =============================================================================

# Maximum line count for SKILL.md files
MAX_LINES = 500

# Required frontmatter fields
REQUIRED_FIELDS = ["name", "description", "keywords"]

# Valid Claude Code tools (comprehensive list)
VALID_TOOLS = {
    "Task", "Read", "Write", "Edit", "Bash", "Grep", "Glob",
    "WebSearch", "WebFetch", "TodoWrite", "TodoRead"
}

# Dangerous tools that should be restricted
DANGEROUS_TOOLS = {"*", "all", "any"}

# Expected tool assignments per skill category (Issue #146)
READ_ONLY_SKILLS = {
    "api-design": {"Read"},
    "architecture-patterns": {"Read"},
    "code-review": {"Read"},
    "documentation-guide": {"Read"},
    "error-handling-patterns": {"Read"},
    "library-design-patterns": {"Read"},
    "python-standards": {"Read"},
    "security-patterns": {"Read"},
    "skill-integration": {"Read"},
    "skill-integration-templates": {"Read"},
    "state-management-patterns": {"Read"},
    "api-integration-patterns": {"Read"},
    "agent-output-formats": {"Read"},
    "project-alignment": {"Read"},
    "consistency-enforcement": {"Read"},
}

READ_SEARCH_SKILLS = {
    "research-patterns": {"Read", "Grep", "Glob"},
    "semantic-validation": {"Read", "Grep", "Glob"},
    "cross-reference-validation": {"Read", "Grep", "Glob"},
    "documentation-currency": {"Read", "Grep", "Glob"},
    "advisor-triggers": {"Read", "Grep", "Glob"},
    "project-alignment-validation": {"Read", "Grep", "Glob"},
}

READ_SEARCH_BASH_SKILLS = {
    "testing-guide": {"Read", "Grep", "Glob", "Bash"},
    "observability": {"Read", "Grep", "Glob", "Bash"},
    "git-workflow": {"Read", "Grep", "Glob", "Bash"},
    "github-workflow": {"Read", "Grep", "Glob", "Bash"},
}

READ_WRITE_EDIT_SKILLS = {
    "database-design": {"Read", "Write", "Edit", "Grep", "Glob"},
    "file-organization": {"Read", "Write", "Edit", "Grep", "Glob"},
    "project-management": {"Read", "Write", "Edit", "Grep", "Glob"},
}

# Combine all expected tools
EXPECTED_TOOLS = {}
EXPECTED_TOOLS.update(READ_ONLY_SKILLS)
EXPECTED_TOOLS.update(READ_SEARCH_SKILLS)
EXPECTED_TOOLS.update(READ_SEARCH_BASH_SKILLS)
EXPECTED_TOOLS.update(READ_WRITE_EDIT_SKILLS)

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


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


def parse_frontmatter_from_file(file_path: Path) -> Dict:
    """Parse YAML frontmatter from skill markdown file."""
    content = file_path.read_text(encoding='utf-8')
    frontmatter, _ = parse_frontmatter(content)
    return frontmatter or {}


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


def get_all_skill_files() -> List[Path]:
    """Get all skill SKILL.md files from subdirectories."""
    skill_files = []
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if skill_dir.is_dir():
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                skill_files.append(skill_file)
    return skill_files


def get_skill_name(skill_file: Path) -> str:
    """Extract skill name from file path."""
    return skill_file.parent.name


def count_lines(file_path: Path) -> int:
    """Count lines in a file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return len(f.readlines())


def extract_markdown_links(content: str) -> List[str]:
    """Extract all markdown links from content."""
    pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    return [match[1] for match in re.findall(pattern, content)]


# =============================================================================
# STRUCTURE TESTS (Issue #110 - 500-line limit, frontmatter, keywords)
# =============================================================================


class TestSkillLineCount:
    """Tests for skill line count compliance."""

    def test_skills_directory_exists(self):
        """Verify skills directory exists."""
        assert SKILLS_DIR.exists(), f"Skills directory not found: {SKILLS_DIR}"

    def test_skills_have_skill_file(self):
        """Verify each skill has a SKILL.md or skill.md file."""
        missing = []
        for skill_path in get_all_skill_paths():
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

    def test_no_duplicate_skill_names(self):
        """Verify no duplicate skill directory names."""
        names = [p.name for p in get_all_skill_paths()]
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

    def test_skills_exist(self):
        """Verify at least some skills exist."""
        skill_paths = get_all_skill_paths()
        assert len(skill_paths) > 0, "No skills found in skills directory"


# =============================================================================
# LOADER TESTS (Issue #140 - Skill injection)
# =============================================================================


class TestSkillLoaderImport:
    """Test skill_loader imports work correctly."""

    def test_skill_loader_imports(self):
        """Verify skill_loader can be imported."""
        from skill_loader import (
            AGENT_SKILL_MAP,
            load_skills_for_agent,
            load_skill_content,
            format_skills_for_prompt,
            get_skill_injection_for_agent,
            get_available_skills,
            parse_agent_skills,
        )
        assert AGENT_SKILL_MAP is not None


class TestAgentSkillMapping:
    """Test agent-skill mapping configuration."""

    def test_all_core_agents_have_mappings(self):
        """Core workflow agents should have skill mappings."""
        from skill_loader import AGENT_SKILL_MAP

        core_agents = [
            "implementer",
            "test-master",
            "reviewer",
            "security-auditor",
            "doc-master",
            "planner",
        ]
        for agent in core_agents:
            assert agent in AGENT_SKILL_MAP, f"Agent '{agent}' missing from AGENT_SKILL_MAP"
            assert len(AGENT_SKILL_MAP[agent]) > 0, f"Agent '{agent}' has no skills mapped"

    def test_agent_skill_map_has_8_agents(self):
        """Should have mappings for all 8 active agents (Issue #147)."""
        from skill_loader import AGENT_SKILL_MAP
        assert len(AGENT_SKILL_MAP) == 8, f"Expected 8 agents, got {len(AGENT_SKILL_MAP)}"

    def test_no_duplicate_skills_per_agent(self):
        """Each agent should not have duplicate skills."""
        from skill_loader import AGENT_SKILL_MAP
        for agent, skills in AGENT_SKILL_MAP.items():
            assert len(skills) == len(set(skills)), f"Agent '{agent}' has duplicate skills"


class TestSkillLoading:
    """Test skill content loading."""

    def test_load_skills_for_implementer(self):
        """Implementer should load python-standards, testing-guide, error-handling-patterns."""
        from skill_loader import load_skills_for_agent
        skills = load_skills_for_agent("implementer")
        assert "python-standards" in skills
        assert "testing-guide" in skills
        assert "error-handling-patterns" in skills
        assert len(skills) == 3

    def test_load_skills_for_security_auditor(self):
        """Security auditor should load security-patterns, error-handling-patterns."""
        from skill_loader import load_skills_for_agent
        skills = load_skills_for_agent("security-auditor")
        assert "security-patterns" in skills
        assert "error-handling-patterns" in skills
        assert len(skills) == 2

    def test_load_skill_content_returns_string(self):
        """Loaded skill content should be a non-empty string."""
        from skill_loader import load_skill_content
        content = load_skill_content("python-standards")
        assert content is not None
        assert isinstance(content, str)
        assert len(content) > 100  # SKILL.md should have substantial content

    def test_load_nonexistent_skill_returns_none(self):
        """Loading a nonexistent skill should return None."""
        from skill_loader import load_skill_content
        content = load_skill_content("nonexistent-skill-xyz")
        assert content is None

    def test_all_mapped_skills_exist(self):
        """All skills in AGENT_SKILL_MAP should exist and be loadable."""
        from skill_loader import AGENT_SKILL_MAP, load_skill_content
        all_skills = set()
        for skills in AGENT_SKILL_MAP.values():
            all_skills.update(skills)

        for skill_name in all_skills:
            content = load_skill_content(skill_name)
            assert content is not None, f"Skill '{skill_name}' not found or empty"
            assert len(content) > 50, f"Skill '{skill_name}' has insufficient content"


class TestSkillFormatting:
    """Test skill content formatting for prompt injection."""

    def test_format_skills_includes_xml_tags(self):
        """Formatted skills should include XML tags."""
        from skill_loader import format_skills_for_prompt
        skills = {"test-skill": "Test content here"}
        formatted = format_skills_for_prompt(skills)
        assert "<skills>" in formatted
        assert "</skills>" in formatted
        assert '<skill name="test-skill">' in formatted
        assert "</skill>" in formatted

    def test_format_empty_skills_returns_empty_string(self):
        """Empty skills dict should return empty string."""
        from skill_loader import format_skills_for_prompt
        formatted = format_skills_for_prompt({})
        assert formatted == ""

    def test_format_respects_line_limit(self):
        """Formatting should truncate if exceeding line limit."""
        from skill_loader import format_skills_for_prompt
        # Create a skill with many lines
        long_content = "\n".join(["line"] * 2000)
        skills = {"long-skill": long_content}
        formatted = format_skills_for_prompt(skills, max_total_lines=100)
        # Should be truncated
        assert "truncated" in formatted.lower() or len(formatted.split('\n')) < 150


class TestSkillConvenienceFunctions:
    """Test convenience functions."""

    def test_get_skill_injection_for_agent(self):
        """Convenience function should return formatted skills."""
        from skill_loader import get_skill_injection_for_agent
        injection = get_skill_injection_for_agent("implementer")
        assert injection is not None
        assert "<skills>" in injection
        assert "python-standards" in injection

    def test_get_skill_injection_for_unknown_agent(self):
        """Unknown agent should return empty string."""
        from skill_loader import get_skill_injection_for_agent
        injection = get_skill_injection_for_agent("unknown-agent-xyz")
        assert injection == ""

    def test_get_available_skills(self):
        """Should return list of available skill names."""
        from skill_loader import get_available_skills
        skills = get_available_skills()
        assert isinstance(skills, list)
        assert len(skills) >= 20  # We have 28 skills
        assert "python-standards" in skills
        assert "security-patterns" in skills


class TestSkillLoaderSecurity:
    """Test security features in skill loader."""

    def test_path_traversal_blocked(self):
        """Path traversal attempts should be blocked."""
        from skill_loader import load_skill_content
        content = load_skill_content("../../../etc/passwd")
        assert content is None

    def test_absolute_path_blocked(self):
        """Absolute paths should be blocked."""
        from skill_loader import load_skill_content
        content = load_skill_content("/etc/passwd")
        assert content is None

    def test_backslash_path_blocked(self):
        """Backslash paths should be blocked."""
        from skill_loader import load_skill_content
        content = load_skill_content("..\\..\\windows\\system32")
        assert content is None


class TestParseAgentSkills:
    """Test parsing agent frontmatter for skills."""

    def test_parse_returns_list(self):
        """parse_agent_skills should return a list."""
        from skill_loader import parse_agent_skills
        skills = parse_agent_skills("implementer")
        assert isinstance(skills, list)

    def test_parse_known_agent_returns_skills(self):
        """Known agent should return skills from mapping."""
        from skill_loader import parse_agent_skills
        skills = parse_agent_skills("implementer")
        assert len(skills) > 0
        assert "python-standards" in skills

    def test_parse_unknown_agent_returns_empty(self):
        """Unknown agent should return empty list."""
        from skill_loader import parse_agent_skills
        skills = parse_agent_skills("unknown-agent-xyz")
        assert skills == []


class TestSkillLoaderIntegration:
    """Integration tests for skill injection workflow."""

    def test_all_agents_can_load_skills(self):
        """All mapped agents should be able to load their skills."""
        from skill_loader import AGENT_SKILL_MAP, load_skills_for_agent
        for agent_name in AGENT_SKILL_MAP:
            skills = load_skills_for_agent(agent_name)
            expected_count = len(AGENT_SKILL_MAP[agent_name])
            assert len(skills) == expected_count, (
                f"Agent '{agent_name}' loaded {len(skills)} skills, expected {expected_count}"
            )

    def test_skill_injection_produces_reasonable_output(self):
        """Skill injection should produce reasonable token counts."""
        from skill_loader import get_skill_injection_for_agent
        for agent_name in ["implementer", "test-master", "security-auditor"]:
            injection = get_skill_injection_for_agent(agent_name)
            # Should be non-empty
            assert len(injection) > 100
            # Should be under reasonable limit (roughly 3000 lines * 4 chars = 12000)
            assert len(injection) < 100000, f"Agent '{agent_name}' injection too large"


# =============================================================================
# TOOLS TESTS (Issue #146 - allowed-tools frontmatter)
# =============================================================================


class TestAllowedToolsFrontmatter:
    """Verify all skills have allowed-tools frontmatter field."""

    def test_all_skills_have_frontmatter(self):
        """All skill files should have valid YAML frontmatter."""
        skill_files = get_all_skill_files()
        assert len(skill_files) >= 20, f"Expected at least 20 skills, found {len(skill_files)}"

        missing_frontmatter = []
        for skill_file in skill_files:
            frontmatter = parse_frontmatter_from_file(skill_file)
            if not frontmatter:
                missing_frontmatter.append(get_skill_name(skill_file))

        assert not missing_frontmatter, (
            f"Skills missing valid frontmatter: {', '.join(missing_frontmatter)}\n"
            "All skills must have YAML frontmatter"
        )

    def test_all_skills_have_allowed_tools_field(self):
        """All skill files should have allowed-tools: field in frontmatter."""
        skill_files = get_all_skill_files()
        missing_allowed_tools = []

        for skill_file in skill_files:
            frontmatter = parse_frontmatter_from_file(skill_file)
            if 'allowed-tools' not in frontmatter:
                missing_allowed_tools.append(get_skill_name(skill_file))

        assert not missing_allowed_tools, (
            f"Skills missing allowed-tools: field: {', '.join(missing_allowed_tools)}\n"
            "All skills require allowed-tools: in frontmatter"
        )

    def test_expected_skills_exist(self):
        """All 28 expected skills should exist."""
        skill_files = get_all_skill_files()
        skill_names = {get_skill_name(f) for f in skill_files}

        for expected_skill in EXPECTED_TOOLS.keys():
            assert expected_skill in skill_names, (
                f"Expected skill {expected_skill} not found in {SKILLS_DIR}"
            )


class TestAllowedToolsDataType:
    """Verify allowed-tools is a YAML list (not string)."""

    def test_allowed_tools_is_list(self):
        """allowed-tools: field should be a list of strings."""
        skill_files = get_all_skill_files()
        invalid_types = []

        for skill_file in skill_files:
            frontmatter = parse_frontmatter_from_file(skill_file)
            if 'allowed-tools' in frontmatter:
                tools = frontmatter['allowed-tools']
                if not isinstance(tools, list):
                    invalid_types.append(f"{get_skill_name(skill_file)}: {type(tools).__name__}")
                elif not all(isinstance(t, str) for t in tools):
                    invalid_types.append(f"{get_skill_name(skill_file)}: contains non-string items")

        assert not invalid_types, (
            f"Skills with invalid allowed-tools: type:\n" +
            "\n".join(f"  - {t}" for t in invalid_types) +
            "\n\nallowed-tools: must be a list of strings"
        )

    def test_allowed_tools_not_empty(self):
        """allowed-tools: should not be an empty list."""
        skill_files = get_all_skill_files()
        empty_tools = []

        for skill_file in skill_files:
            frontmatter = parse_frontmatter_from_file(skill_file)
            if 'allowed-tools' in frontmatter:
                tools = frontmatter['allowed-tools']
                if isinstance(tools, list) and len(tools) == 0:
                    empty_tools.append(get_skill_name(skill_file))

        assert not empty_tools, (
            f"Skills with empty allowed-tools: list: {', '.join(empty_tools)}\n"
            "Every skill needs at least one tool"
        )


class TestCorrectToolAssignments:
    """Verify each skill has correct tools for its category."""

    @pytest.mark.parametrize("skill_name,expected_tools", list(EXPECTED_TOOLS.items()),
                           ids=list(EXPECTED_TOOLS.keys()))
    def test_skill_has_expected_tools(self, skill_name, expected_tools):
        """Verify skill has expected tool set."""
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        assert skill_file.exists(), f"Skill file {skill_name}/SKILL.md not found"

        frontmatter = parse_frontmatter_from_file(skill_file)
        actual_tools = set(frontmatter.get('allowed-tools', []))

        assert actual_tools == expected_tools, (
            f"{skill_name} tool assignment mismatch:\n"
            f"  Expected: {sorted(expected_tools)}\n"
            f"  Actual: {sorted(actual_tools)}\n"
            f"  Missing: {sorted(expected_tools - actual_tools)}\n"
            f"  Extra: {sorted(actual_tools - expected_tools)}"
        )


class TestToolSecurityConstraints:
    """Verify no dangerous broad access patterns."""

    def test_no_wildcard_tools(self):
        """Skills should not use wildcard tools (*, all, any)."""
        skill_files = get_all_skill_files()
        dangerous_usage = []

        for skill_file in skill_files:
            frontmatter = parse_frontmatter_from_file(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            violations = tools & DANGEROUS_TOOLS
            if violations:
                dangerous_usage.append(f"{get_skill_name(skill_file)}: {violations}")

        assert not dangerous_usage, (
            f"Skills with dangerous wildcard tools:\n" +
            "\n".join(f"  - {u}" for u in dangerous_usage) +
            "\n\nWildcards bypass tool restrictions and are security risks"
        )

    def test_all_tools_are_valid(self):
        """All tools in allowed-tools should be valid Claude Code tools."""
        skill_files = get_all_skill_files()
        invalid_tools = []

        for skill_file in skill_files:
            frontmatter = parse_frontmatter_from_file(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            unknown = tools - VALID_TOOLS
            if unknown:
                invalid_tools.append(f"{get_skill_name(skill_file)}: {sorted(unknown)}")

        assert not invalid_tools, (
            f"Skills with invalid tool names:\n" +
            "\n".join(f"  - {t}" for t in invalid_tools) +
            f"\n\nValid tools: {sorted(VALID_TOOLS)}"
        )

    def test_no_task_tool_in_skills(self):
        """Skills should not use Task tool (reserved for commands/agents)."""
        skill_files = get_all_skill_files()
        task_violations = []

        for skill_file in skill_files:
            frontmatter = parse_frontmatter_from_file(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            if 'Task' in tools:
                task_violations.append(get_skill_name(skill_file))

        assert not task_violations, (
            f"Skills using Task tool: {', '.join(task_violations)}\n"
            "Task tool is reserved for commands and agents, not skills"
        )

    def test_no_web_tools_in_skills(self):
        """Skills should not have WebSearch or WebFetch (reserved for agents)."""
        skill_files = get_all_skill_files()
        violations = []

        for skill_file in skill_files:
            frontmatter = parse_frontmatter_from_file(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            web_tools = {'WebSearch', 'WebFetch'}
            if tools & web_tools:
                violations.append(f"{get_skill_name(skill_file)}: {tools & web_tools}")

        assert not violations, (
            f"Skills with web research tools:\n" +
            "\n".join(f"  - {v}" for v in violations) +
            "\n\nWebSearch/WebFetch are reserved for research agents, not skills"
        )


class TestReadOnlySkills:
    """Verify read-only skills don't have Write/Edit/Bash tools."""

    def test_read_only_skills_no_write_tools(self):
        """Read-only skills should not have Write, Edit, or Bash tools."""
        violations = []

        for skill_name in READ_ONLY_SKILLS.keys():
            skill_file = SKILLS_DIR / skill_name / "SKILL.md"
            if not skill_file.exists():
                continue

            frontmatter = parse_frontmatter_from_file(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            forbidden_tools = {'Write', 'Edit', 'Bash', 'WebSearch', 'WebFetch'}
            if tools & forbidden_tools:
                violations.append(f"{skill_name}: {tools & forbidden_tools}")

        assert not violations, (
            f"Read-only skills with forbidden tools:\n" +
            "\n".join(f"  - {v}" for v in violations) +
            "\n\nRead-only skills should only have Read tool"
        )

    def test_read_only_skills_have_exactly_read(self):
        """Read-only skills should have exactly [Read] tool."""
        violations = []

        for skill_name in READ_ONLY_SKILLS.keys():
            skill_file = SKILLS_DIR / skill_name / "SKILL.md"
            if not skill_file.exists():
                continue

            frontmatter = parse_frontmatter_from_file(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            if tools != {"Read"}:
                violations.append(f"{skill_name}: {sorted(tools)}")

        assert not violations, (
            f"Read-only skills without exactly [Read]:\n" +
            "\n".join(f"  - {v}" for v in violations) +
            "\n\nExpected exactly: ['Read']"
        )


class TestToolHierarchy:
    """Verify tool hierarchy makes sense (no Bash without Grep/Glob)."""

    def test_bash_skills_have_search_tools(self):
        """Skills with Bash should also have Grep and Glob."""
        violations = []

        for skill_file in get_all_skill_files():
            frontmatter = parse_frontmatter_from_file(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            if 'Bash' in tools:
                missing = []
                if 'Grep' not in tools:
                    missing.append('Grep')
                if 'Glob' not in tools:
                    missing.append('Glob')

                if missing:
                    violations.append(f"{get_skill_name(skill_file)}: missing {missing}")

        assert not violations, (
            f"Bash skills without search tools:\n" +
            "\n".join(f"  - {v}" for v in violations) +
            "\n\nBash skills should have Grep and Glob for file operations"
        )

    def test_write_edit_skills_have_search_tools(self):
        """Skills with Write/Edit should also have Grep and Glob."""
        violations = []

        for skill_file in get_all_skill_files():
            frontmatter = parse_frontmatter_from_file(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            if 'Write' in tools or 'Edit' in tools:
                missing = []
                if 'Grep' not in tools:
                    missing.append('Grep')
                if 'Glob' not in tools:
                    missing.append('Glob')

                if missing:
                    violations.append(f"{get_skill_name(skill_file)}: missing {missing}")

        assert not violations, (
            f"Write/Edit skills without search tools:\n" +
            "\n".join(f"  - {v}" for v in violations) +
            "\n\nWrite/Edit skills should have Grep and Glob for finding files"
        )

    def test_search_skills_have_read(self):
        """Skills with Grep/Glob should also have Read."""
        violations = []

        for skill_file in get_all_skill_files():
            frontmatter = parse_frontmatter_from_file(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            if ('Grep' in tools or 'Glob' in tools) and 'Read' not in tools:
                violations.append(get_skill_name(skill_file))

        assert not violations, (
            f"Search skills without Read tool: {', '.join(violations)}\n"
            "Skills using Grep/Glob need Read to view search results"
        )


class TestToolMinimalism:
    """Verify skills don't over-request tools they don't need."""

    def test_no_skill_has_all_tools(self):
        """No skill should request all available tools."""
        violations = []

        for skill_file in get_all_skill_files():
            frontmatter = parse_frontmatter_from_file(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            # No skill should need more than 5 tools
            if len(tools) > 5:
                violations.append(f"{get_skill_name(skill_file)}: {len(tools)} tools")

        assert not violations, (
            f"Skills requesting too many tools:\n" +
            "\n".join(f"  - {v}" for v in violations) +
            "\n\nSkills should request minimal tools needed for their function"
        )

    def test_no_duplicate_tools_listed(self):
        """Skills should not list same tool twice."""
        duplicates = []

        for skill_file in get_all_skill_files():
            frontmatter = parse_frontmatter_from_file(skill_file)
            tools = frontmatter.get('allowed-tools', [])

            if len(tools) != len(set(tools)):
                duplicates.append(f"{get_skill_name(skill_file)}: {tools}")

        assert not duplicates, (
            f"Skills with duplicate tools:\n" +
            "\n".join(f"  - {d}" for d in duplicates)
        )


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestSkillsIntegration:
    """Integration tests for complete skills implementation."""

    def test_complete_allowed_tools_coverage(self):
        """Verify all 28 skills have complete allowed-tools implementation."""
        skill_files = get_all_skill_files()
        assert len(skill_files) >= 20

        for skill_file in skill_files:
            frontmatter = parse_frontmatter_from_file(skill_file)
            skill_name = get_skill_name(skill_file)

            assert 'allowed-tools' in frontmatter, f"{skill_name} missing allowed-tools"

            tools = frontmatter['allowed-tools']
            assert isinstance(tools, list), f"{skill_name} allowed-tools not a list"
            assert len(tools) > 0, f"{skill_name} has empty allowed-tools"

            assert all(t in VALID_TOOLS for t in tools), (
                f"{skill_name} has invalid tools"
            )

    def test_all_categories_represented(self):
        """Verify all 4 skill categories are represented."""
        assert len(READ_ONLY_SKILLS) >= 10, "Expected at least 10 read-only skills"
        assert len(READ_SEARCH_SKILLS) == 6, "Expected 6 read+search skills"
        assert len(READ_SEARCH_BASH_SKILLS) == 4, "Expected 4 read+search+bash skills"
        assert len(READ_WRITE_EDIT_SKILLS) == 3, "Expected 3 read+write+edit skills"

        total = (
            len(READ_ONLY_SKILLS) +
            len(READ_SEARCH_SKILLS) +
            len(READ_SEARCH_BASH_SKILLS) +
            len(READ_WRITE_EDIT_SKILLS)
        )
        assert total == 28, f"Expected 28 total skills, got {total}"

    def test_no_skill_in_multiple_categories(self):
        """Each skill should be in exactly one category."""
        all_categories = [
            READ_ONLY_SKILLS,
            READ_SEARCH_SKILLS,
            READ_SEARCH_BASH_SKILLS,
            READ_WRITE_EDIT_SKILLS,
        ]

        duplicates = []
        for i, cat1 in enumerate(all_categories):
            for cat2 in all_categories[i+1:]:
                overlap = set(cat1.keys()) & set(cat2.keys())
                if overlap:
                    duplicates.extend(overlap)

        assert not duplicates, (
            f"Skills in multiple categories: {', '.join(duplicates)}\n"
            "Each skill should be in exactly one category"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=line", "-q"])
