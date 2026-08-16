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

# Required frontmatter fields.
# 'keywords' was stripped from every active skill by e64d5563 (the same commit
# that consolidated the skill roster). Activation triggers now live inside
# 'description' via the "TRIGGER when:" pattern documented in
# skills/DESCRIPTION_PATTERN.md. The only frontmatter still declaring
# 'keywords:' is under skills/archived/.
REQUIRED_FIELDS = ["name", "description", "allowed-tools"]

# Marker that introduces the comma-separated activation keywords inside
# a skill description (see skills/DESCRIPTION_PATTERN.md).
TRIGGER_MARKER = "TRIGGER when:"

# Minimum activation keywords a skill must declare for reliable auto-activation.
MIN_TRIGGER_KEYWORDS = 3

# Valid Claude Code tools (comprehensive list)
VALID_TOOLS = {
    "Task", "Read", "Write", "Edit", "Bash", "Grep", "Glob",
    "WebSearch", "WebFetch", "TodoWrite", "TodoRead"
}

# Dangerous tools that should be restricted
DANGEROUS_TOOLS = {"*", "all", "any"}

# Directories under skills/ that are not active skills and must be skipped
# everywhere this file enumerates skills.
EXCLUDED_SKILL_DIRS = {"archived"}

# =============================================================================
# POLICY CONSTANTS
# =============================================================================
# The skill ROSTER is derived from disk (see get_skill_tool_map) so it cannot
# drift when a skill is added, renamed, or merged. The POLICY below stays
# explicit so a risky capability still requires a conscious human edit to this
# file. Do NOT derive these from disk -- that would make the test unable to
# fail, which is the opposite of the goal.

# Maximum number of tools any single skill may request. Skills should request
# the minimal tool set needed for their function.
MAX_TOOLS_PER_SKILL = 5

# Web-research tools. Granting a skill network access is a privileged decision.
WEB_TOOLS = {"WebSearch", "WebFetch"}

# Only these skills may request WEB_TOOLS. Adding an entry here is a deliberate
# grant of network access and must be a conscious edit, never auto-blessed from
# whatever happens to be on disk.
WEB_TOOL_ALLOWLIST = {"research-patterns", "planning-workflow"}

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
    """Get all active skill directories (excludes EXCLUDED_SKILL_DIRS)."""
    if not SKILLS_DIR.exists():
        return []
    return sorted(
        p for p in SKILLS_DIR.iterdir()
        if p.is_dir() and p.name not in EXCLUDED_SKILL_DIRS
    )


def get_skill_file(skill_path: Path) -> Optional[Path]:
    """Get the SKILL.md or skill.md file for a skill."""
    for name in ["SKILL.md", "skill.md"]:
        skill_file = skill_path / name
        if skill_file.exists():
            return skill_file
    return None


def get_all_skill_files() -> List[Path]:
    """Get all active skill SKILL.md files (excludes EXCLUDED_SKILL_DIRS)."""
    skill_files = []
    for skill_dir in get_all_skill_paths():
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            skill_files.append(skill_file)
    return skill_files


def get_declared_tools(skill_file: Path) -> Set[str]:
    """Read the allowed-tools set a skill declares in its frontmatter."""
    frontmatter = parse_frontmatter_from_file(skill_file)
    tools = frontmatter.get("allowed-tools", [])
    if not isinstance(tools, list):
        return set()
    return {t for t in tools if isinstance(t, str)}


def get_skill_tool_map() -> Dict[str, Set[str]]:
    """Derive the skill roster from disk: {skill_name: declared tools}.

    This is the ROSTER half of the contract -- it is read from the filesystem
    at collection time so it can never drift from the shipped skills. The
    POLICY half (MAX_TOOLS_PER_SKILL, WEB_TOOL_ALLOWLIST) stays hardcoded
    above on purpose.
    """
    return {
        get_skill_name(skill_file): get_declared_tools(skill_file)
        for skill_file in get_all_skill_files()
    }


def get_skill_name(skill_file: Path) -> str:
    """Extract skill name from file path."""
    return skill_file.parent.name


def count_lines(file_path: Path) -> int:
    """Count lines in a file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return len(f.readlines())


def extract_trigger_keywords(description: str) -> List[str]:
    """Pull the comma-separated activation keywords out of a description.

    Replaces the removed 'keywords:' frontmatter list. Returns [] when the
    description declares no TRIGGER section.
    """
    if TRIGGER_MARKER not in description:
        return []

    tail = description.split(TRIGGER_MARKER, 1)[1]
    # Stop at the exclusion clause when present.
    tail = re.split(r"DO NOT TRIGGER when:", tail, maxsplit=1)[0]
    return [kw.strip(" .") for kw in tail.split(",") if kw.strip(" .")]


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


class TestSkillTriggers:
    """Tests for skill activation triggers.

    These replace the old 'keywords:' frontmatter tests. That field was
    stripped from every active skill by e64d5563 and the convention moved to
    the "TRIGGER when:" clause inside 'description'
    (skills/DESCRIPTION_PATTERN.md). The intent -- every skill must declare
    enough activation triggers to be discoverable -- is preserved below
    against the current convention.

    The old test_keywords_are_lowercase assertion is deliberately NOT ported:
    it existed because the removed 'keywords:' list was matched mechanically,
    where case mattered. Description triggers are matched semantically and
    legitimately contain proper identifiers (API, ADR, PEP 8, OWASP, TDD).
    """

    @pytest.mark.parametrize("skill_name,skill_file",
                           [(p.name, get_skill_file(p)) for p in get_all_skill_paths() if get_skill_file(p)],
                           ids=[p.name for p in get_all_skill_paths() if get_skill_file(p)])
    def test_skill_declares_triggers(self, skill_name, skill_file):
        """Verify each skill declares activation triggers in its description."""
        content = skill_file.read_text(encoding="utf-8")
        frontmatter, _ = parse_frontmatter(content)

        assert frontmatter is not None, f"Skill '{skill_name}' has no frontmatter"

        description = frontmatter.get("description", "")
        assert TRIGGER_MARKER in description, (
            f"Skill '{skill_name}' description has no '{TRIGGER_MARKER}' clause. "
            f"See skills/DESCRIPTION_PATTERN.md for the required format."
        )

    @pytest.mark.parametrize("skill_name,skill_file",
                           [(p.name, get_skill_file(p)) for p in get_all_skill_paths() if get_skill_file(p)],
                           ids=[p.name for p in get_all_skill_paths() if get_skill_file(p)])
    def test_skill_has_minimum_triggers(self, skill_name, skill_file):
        """Verify each skill declares at least MIN_TRIGGER_KEYWORDS triggers."""
        content = skill_file.read_text(encoding="utf-8")
        frontmatter, _ = parse_frontmatter(content)

        assert frontmatter is not None, f"Skill '{skill_name}' has no frontmatter"

        triggers = extract_trigger_keywords(frontmatter.get("description", ""))
        assert len(triggers) >= MIN_TRIGGER_KEYWORDS, (
            f"Skill '{skill_name}' declares only {len(triggers)} activation "
            f"triggers ({triggers}), need at least {MIN_TRIGGER_KEYWORDS} "
            f"for reliable auto-activation."
        )

    @pytest.mark.parametrize("skill_name,skill_file",
                           [(p.name, get_skill_file(p)) for p in get_all_skill_paths() if get_skill_file(p)],
                           ids=[p.name for p in get_all_skill_paths() if get_skill_file(p)])
    def test_skill_declares_exclusions(self, skill_name, skill_file):
        """Verify each skill declares when it should NOT activate.

        Exclusions are half of the trigger contract -- a skill that only says
        when to fire will over-activate.
        """
        content = skill_file.read_text(encoding="utf-8")
        frontmatter, _ = parse_frontmatter(content)

        assert frontmatter is not None, f"Skill '{skill_name}' has no frontmatter"

        description = frontmatter.get("description", "")
        assert "DO NOT TRIGGER when:" in description, (
            f"Skill '{skill_name}' description has no 'DO NOT TRIGGER when:' "
            f"clause. See skills/DESCRIPTION_PATTERN.md."
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

    def test_agent_skill_map_covers_pipeline_agents(self):
        """Should have mappings for at least the core pipeline agents.

        Was 'assert len(AGENT_SKILL_MAP) == 8' (Issue #147). A hardcoded
        component count is the documented #1 test anti-pattern here -- it
        broke as soon as the roster grew to 13. Threshold + structural check
        replaces it.
        """
        from skill_loader import AGENT_SKILL_MAP
        assert len(AGENT_SKILL_MAP) >= 8, (
            f"Expected at least 8 mapped agents, got {len(AGENT_SKILL_MAP)}"
        )
        for agent in ("implementer", "planner", "reviewer", "security-auditor"):
            assert agent in AGENT_SKILL_MAP, f"Core agent '{agent}' unmapped"

    def test_no_duplicate_skills_per_agent(self):
        """Each agent should not have duplicate skills."""
        from skill_loader import AGENT_SKILL_MAP
        for agent, skills in AGENT_SKILL_MAP.items():
            assert len(skills) == len(set(skills)), f"Agent '{agent}' has duplicate skills"


class TestSkillLoading:
    """Test skill content loading."""

    def test_load_skills_for_implementer(self):
        """Implementer should load python-standards, testing-guide, error-handling.

        Skill renamed from 'error-handling-patterns' by e64d5563 (Issue #1526).
        """
        from skill_loader import load_skills_for_agent
        skills = load_skills_for_agent("implementer")
        assert "python-standards" in skills
        assert "testing-guide" in skills
        assert "error-handling" in skills
        assert len(skills) == 3

    def test_load_skills_for_security_auditor(self):
        """Security auditor should load security-patterns, error-handling.

        Skill renamed from 'error-handling-patterns' by e64d5563 (Issue #1526).
        """
        from skill_loader import load_skills_for_agent
        skills = load_skills_for_agent("security-auditor")
        assert "security-patterns" in skills
        assert "error-handling" in skills
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


class TestIssue1526DanglingSkillMap:
    """Regression: AGENT_SKILL_MAP must never name a skill that is not on disk.

    Commit e64d5563 (2026-03-18) renamed 'error-handling-patterns' to
    'error-handling' and archived 'project-management' without updating
    AGENT_SKILL_MAP. The loader treated the missing skills as nothing to do,
    so implementer, security-auditor and planner silently ran with fewer
    skills than they declared for five months. See Issue #1526.
    """

    def test_regression_issue_1526_no_dangling_skill_map_entries(self):
        """The invariant: every mapped skill resolves to a real SKILL.md."""
        from skill_loader import AGENT_SKILL_MAP, find_dangling_skills

        dangling = find_dangling_skills(AGENT_SKILL_MAP, skills_dir=SKILLS_DIR)
        assert dangling == {}, (
            f"AGENT_SKILL_MAP names skills with no SKILL.md on disk: {dangling}\n"
            f"Expected: every mapped skill has {SKILLS_DIR}/<skill>/SKILL.md\n"
            "Fix: repoint the entry to the renamed skill or remove it (Issue #1526)"
        )

    def test_regression_issue_1526_renamed_skills_repointed(self):
        """The three specific agents carry their intended skills."""
        from skill_loader import AGENT_SKILL_MAP

        assert "error-handling" in AGENT_SKILL_MAP["implementer"]
        assert "error-handling" in AGENT_SKILL_MAP["security-auditor"]
        assert "planning-workflow" in AGENT_SKILL_MAP["planner"]
        for agent in ("implementer", "security-auditor", "planner"):
            assert "error-handling-patterns" not in AGENT_SKILL_MAP[agent]
            assert "project-management" not in AGENT_SKILL_MAP[agent]

    def test_regression_issue_1526_dangling_entry_detected(self):
        """The pre-fix map must be reported as dangling, not silently skipped."""
        from skill_loader import find_dangling_skills

        pre_fix_map = {
            "planner": ["architecture-patterns", "project-management"],
            "implementer": ["python-standards", "testing-guide", "error-handling-patterns"],
            "security-auditor": ["security-patterns", "error-handling-patterns"],
        }
        dangling = find_dangling_skills(pre_fix_map, skills_dir=SKILLS_DIR)
        assert dangling == {
            "planner": ["project-management"],
            "implementer": ["error-handling-patterns"],
            "security-auditor": ["error-handling-patterns"],
        }, f"Pre-fix map should be flagged, got: {dangling}"

    def test_regression_issue_1526_dangling_entry_warns_loudly(self, capsys):
        """A dangling entry emits a loud, actionable warning on stderr."""
        from skill_loader import validate_agent_skill_map

        pre_fix_map = {
            "security-auditor": ["security-patterns", "error-handling-patterns"],
        }
        dangling = validate_agent_skill_map(pre_fix_map, skills_dir=SKILLS_DIR)
        captured = capsys.readouterr()

        assert dangling == {"security-auditor": ["error-handling-patterns"]}
        assert "error-handling-patterns" in captured.err
        assert "security-auditor" in captured.err
        assert "SKILL.md" in captured.err

    def test_regression_issue_1526_valid_map_is_silent(self, capsys):
        """Negative control: a valid map produces no error and no warning.

        Without this, a check that fires on everything would look like a pass
        and train readers to ignore the warning.
        """
        from skill_loader import validate_agent_skill_map

        valid_map = {
            "security-auditor": ["security-patterns", "error-handling"],
            "implementer": ["python-standards", "testing-guide", "error-handling"],
            "planner": ["architecture-patterns", "planning-workflow"],
        }
        dangling = validate_agent_skill_map(valid_map, skills_dir=SKILLS_DIR)
        captured = capsys.readouterr()

        assert dangling == {}, f"Valid map wrongly flagged: {dangling}"
        assert captured.err == "", f"Valid map emitted a warning: {captured.err!r}"
        assert captured.out == "", f"Valid map emitted output: {captured.out!r}"

    def test_regression_issue_1526_shipped_map_loads_silently(self, capsys):
        """The shipped map, validated end-to-end, is clean and silent."""
        from skill_loader import AGENT_SKILL_MAP, validate_agent_skill_map

        dangling = validate_agent_skill_map(AGENT_SKILL_MAP, skills_dir=SKILLS_DIR)
        captured = capsys.readouterr()

        assert dangling == {}
        assert captured.err == "", f"Shipped map emitted a warning: {captured.err!r}"


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

    def test_every_active_skill_dir_has_skill_md(self):
        """Every active skill directory must contain a SKILL.md.

        POLICY. The roster comes from disk, so this catches a directory that
        was added under skills/ without the file that makes it a skill.
        Directories in EXCLUDED_SKILL_DIRS are not skills and are skipped.
        """
        missing = [
            path.name for path in get_all_skill_paths()
            if not (path / "SKILL.md").exists()
        ]

        assert not missing, (
            f"Skill directories without SKILL.md: {sorted(missing)}\n"
            f"Add SKILL.md, or add the directory to EXCLUDED_SKILL_DIRS "
            f"if it is not a skill."
        )

    def test_roster_is_derived_from_disk_and_non_empty(self):
        """The roster must be discovered from disk, not hardcoded."""
        roster = get_skill_tool_map()

        assert roster, f"No skills discovered in {SKILLS_DIR}"
        assert len(roster) >= 20, (
            f"Only {len(roster)} skills discovered, expected at least 20"
        )
        for skill_name in roster:
            assert (SKILLS_DIR / skill_name / "SKILL.md").exists(), (
                f"Roster entry '{skill_name}' has no SKILL.md on disk"
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
    """Verify each skill on disk complies with the tool POLICY.

    Replaces the previous hardcoded four-bucket roster (Issue #1523). The
    buckets could not express reality -- 6 of 20 skills have unique tool
    signatures -- and drifted silently for five months after the skill
    consolidation in e64d5563. The roster is now enumerated from disk;
    what is asserted against it is policy, not a copy of the answer.
    """

    @pytest.mark.parametrize("skill_name", sorted(get_skill_tool_map()))
    def test_skill_declares_only_valid_tools(self, skill_name):
        """POLICY: each skill declares a non-empty set of real tool names."""
        tools = get_skill_tool_map()[skill_name]

        assert tools, f"{skill_name} declares an empty allowed-tools list"

        unknown = tools - VALID_TOOLS
        assert not unknown, (
            f"{skill_name} declares unknown tools: {sorted(unknown)}\n"
            f"Valid tools: {sorted(VALID_TOOLS)}"
        )

    @pytest.mark.parametrize("skill_name", sorted(get_skill_tool_map()))
    def test_skill_within_tool_budget(self, skill_name):
        """POLICY: no skill requests more than MAX_TOOLS_PER_SKILL tools."""
        tools = get_skill_tool_map()[skill_name]

        assert len(tools) <= MAX_TOOLS_PER_SKILL, (
            f"{skill_name} requests {len(tools)} tools "
            f"(max {MAX_TOOLS_PER_SKILL}): {sorted(tools)}\n"
            f"Reduce the skill's tool set. Do NOT raise MAX_TOOLS_PER_SKILL "
            f"to make this pass."
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

    def test_only_allowlisted_skills_have_web_tools(self):
        """POLICY: only explicitly approved skills may request WebSearch/WebFetch.

        Network access is a privileged capability. The allowlist is hardcoded
        on purpose: granting it must be a conscious edit to this test, never
        auto-blessed from whatever happens to be on disk.
        """
        violations = []

        for skill_name, tools in sorted(get_skill_tool_map().items()):
            granted = tools & WEB_TOOLS
            if granted and skill_name not in WEB_TOOL_ALLOWLIST:
                violations.append(f"{skill_name}: {sorted(granted)}")

        assert not violations, (
            "Skills requesting web-research tools without being on the "
            "allowlist:\n" +
            "\n".join(f"  - {v}" for v in violations) +
            f"\n\nApproved skills: {sorted(WEB_TOOL_ALLOWLIST)}\n"
            "Remove the tools from the skill. Do NOT widen the allowlist to "
            "make this pass -- report it instead."
        )

    def test_web_tool_allowlist_has_no_stale_entries(self):
        """POLICY: the allowlist must not outlive the skills it names.

        Reverse direction of the allowlist check -- stops the grant list from
        accumulating entries for skills that were renamed, merged, or no
        longer use the network.
        """
        roster = get_skill_tool_map()

        unknown = sorted(name for name in WEB_TOOL_ALLOWLIST if name not in roster)
        assert not unknown, (
            f"WEB_TOOL_ALLOWLIST names skills that do not exist: {unknown}\n"
            "Remove the stale entries."
        )

        unused = sorted(
            name for name in WEB_TOOL_ALLOWLIST if not (roster[name] & WEB_TOOLS)
        )
        assert not unused, (
            f"WEB_TOOL_ALLOWLIST grants network access to skills that do not "
            f"request it: {unused}\n"
            "Revoke the unused grants."
        )


class TestLeastPrivilege:
    """Verify privileged tools are always paired with the ability to read.

    The previous version of this class asserted a hardcoded read-only bucket
    ("these named skills must have exactly [Read]"), which is a copy of the
    answer rather than a policy -- it went stale the moment a skill was
    renamed. These assertions are derived from disk and still able to fail.
    """

    def test_write_capable_skills_can_read(self):
        """POLICY: a skill that can modify files must be able to read them."""
        violations = [
            f"{name}: {sorted(tools)}"
            for name, tools in sorted(get_skill_tool_map().items())
            if (tools & {"Write", "Edit"}) and "Read" not in tools
        ]

        assert not violations, (
            "Skills that can write/edit but cannot read:\n" +
            "\n".join(f"  - {v}" for v in violations) +
            "\n\nBlind writes overwrite content the skill never inspected"
        )

    def test_bash_capable_skills_can_read(self):
        """POLICY: a skill that can execute commands must be able to read."""
        violations = [
            f"{name}: {sorted(tools)}"
            for name, tools in sorted(get_skill_tool_map().items())
            if "Bash" in tools and "Read" not in tools
        ]

        assert not violations, (
            "Skills with Bash but no Read:\n" +
            "\n".join(f"  - {v}" for v in violations) +
            "\n\nBash skills need Read to inspect what they act on"
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

            # POLICY: preserved limit, do not raise it to make a skill pass
            if len(tools) > MAX_TOOLS_PER_SKILL:
                violations.append(
                    f"{get_skill_name(skill_file)}: {len(tools)} tools "
                    f"{sorted(tools)}"
                )

        assert not violations, (
            f"Skills requesting more than {MAX_TOOLS_PER_SKILL} tools:\n" +
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
        """Verify every active skill has a complete allowed-tools declaration."""
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

    def test_roster_matches_skill_directories_exactly(self):
        """The derived roster and the active skill directories must agree.

        Replaces the old hardcoded category-count assertions (>=10 read-only,
        ==6 read+search, ==4 read+search+bash, ==3 read+write+edit, ==28
        total). Those counted a stale in-test copy of the roster against
        itself and so could never detect the real drift.
        """
        roster = set(get_skill_tool_map())
        dirs_with_skill_md = {
            path.name for path in get_all_skill_paths()
            if (path / "SKILL.md").exists()
        }

        assert roster == dirs_with_skill_md, (
            f"Roster/disk mismatch:\n"
            f"  In roster only: {sorted(roster - dirs_with_skill_md)}\n"
            f"  On disk only: {sorted(dirs_with_skill_md - roster)}"
        )

    def test_excluded_dirs_are_not_treated_as_skills(self):
        """EXCLUDED_SKILL_DIRS must never appear in the roster.

        'archived/' has no SKILL.md by design; treating it as a skill was the
        source of the 'Skills missing SKILL.md file: [archived]' failure.
        """
        roster = set(get_skill_tool_map())
        leaked = sorted(EXCLUDED_SKILL_DIRS & roster)

        assert not leaked, f"Excluded directories leaked into roster: {leaked}"

        enumerated = {path.name for path in get_all_skill_paths()}
        assert not (EXCLUDED_SKILL_DIRS & enumerated), (
            f"Excluded directories still enumerated: "
            f"{sorted(EXCLUDED_SKILL_DIRS & enumerated)}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=line", "-q"])
