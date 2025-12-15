#!/usr/bin/env python3
"""
Tests for Issue #146 - Add allowed-tools frontmatter to skills

Validates that all skill files have proper allowed-tools frontmatter:
1. All 28 skills have allowed-tools field
2. allowed-tools is a YAML list (not string)
3. Each skill has correct tools for its category:
   - Read-only skills (15): api-design, architecture-patterns, code-review,
     documentation-guide, error-handling-patterns, library-design-patterns,
     python-standards, security-patterns, skill-integration,
     skill-integration-templates, state-management-patterns,
     api-integration-patterns, agent-output-formats, project-alignment,
     consistency-enforcement
   - Read+Search skills (6): research-patterns, semantic-validation,
     cross-reference-validation, documentation-currency, advisor-triggers,
     project-alignment-validation
   - Read+Search+Bash skills (4): testing-guide, observability, git-workflow,
     github-workflow
   - Read+Write+Edit skills (3): database-design, file-organization,
     project-management
4. No dangerous broad access patterns (wildcards)
5. Tool names are valid Claude Code tools

See: https://github.com/akaszubski/autonomous-dev/issues/146
"""

import pytest
import yaml
from pathlib import Path
from typing import Dict, List, Set

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

# Valid Claude Code tools (comprehensive list)
VALID_TOOLS = {
    "Task", "Read", "Write", "Edit", "Bash", "Grep", "Glob",
    "WebSearch", "WebFetch", "TodoWrite", "TodoRead"
}

# Expected tool assignments per skill category (based on implementation plan)
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

# Dangerous tools that should be restricted
DANGEROUS_TOOLS = {"*", "all", "any"}


def parse_frontmatter(file_path: Path) -> Dict:
    """Parse YAML frontmatter from skill markdown file."""
    content = file_path.read_text(encoding='utf-8')

    if not content.startswith('---'):
        return {}

    # Find second ---
    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}

    frontmatter = parts[1].strip()
    try:
        return yaml.safe_load(frontmatter) or {}
    except yaml.YAMLError:
        return {}


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


class TestPhase1AllowedToolsFrontmatter:
    """Phase 1: Verify all skills have allowed-tools frontmatter field."""

    def test_all_skills_have_frontmatter(self):
        """All skill files should have valid YAML frontmatter."""
        skill_files = get_all_skill_files()
        assert len(skill_files) == 28, f"Expected 28 skills, found {len(skill_files)}"

        missing_frontmatter = []
        for skill_file in skill_files:
            frontmatter = parse_frontmatter(skill_file)
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
            frontmatter = parse_frontmatter(skill_file)
            if 'allowed-tools' not in frontmatter:
                missing_allowed_tools.append(get_skill_name(skill_file))

        assert not missing_allowed_tools, (
            f"Skills missing allowed-tools: field: {', '.join(missing_allowed_tools)}\n"
            "Phase 1 requires all skills to have allowed-tools: in frontmatter"
        )

    def test_expected_skills_exist(self):
        """All 28 expected skills should exist."""
        skill_files = get_all_skill_files()
        skill_names = {get_skill_name(f) for f in skill_files}

        for expected_skill in EXPECTED_TOOLS.keys():
            assert expected_skill in skill_names, (
                f"Expected skill {expected_skill} not found in {SKILLS_DIR}"
            )


class TestPhase2AllowedToolsDataType:
    """Phase 2: Verify allowed-tools is a YAML list (not string)."""

    def test_allowed_tools_is_list(self):
        """allowed-tools: field should be a list of strings."""
        skill_files = get_all_skill_files()
        invalid_types = []

        for skill_file in skill_files:
            frontmatter = parse_frontmatter(skill_file)
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
            frontmatter = parse_frontmatter(skill_file)
            if 'allowed-tools' in frontmatter:
                tools = frontmatter['allowed-tools']
                if isinstance(tools, list) and len(tools) == 0:
                    empty_tools.append(get_skill_name(skill_file))

        assert not empty_tools, (
            f"Skills with empty allowed-tools: list: {', '.join(empty_tools)}\n"
            "Every skill needs at least one tool"
        )


class TestPhase3CorrectToolAssignments:
    """Phase 3: Verify each skill has correct tools for its category."""

    @pytest.mark.parametrize("skill_name,expected_tools", [
        # Read-only skills (15)
        ("api-design", {"Read"}),
        ("architecture-patterns", {"Read"}),
        ("code-review", {"Read"}),
        ("documentation-guide", {"Read"}),
        ("error-handling-patterns", {"Read"}),
        ("library-design-patterns", {"Read"}),
        ("python-standards", {"Read"}),
        ("security-patterns", {"Read"}),
        ("skill-integration", {"Read"}),
        ("skill-integration-templates", {"Read"}),
        ("state-management-patterns", {"Read"}),
        ("api-integration-patterns", {"Read"}),
        ("agent-output-formats", {"Read"}),
        ("project-alignment", {"Read"}),
        ("consistency-enforcement", {"Read"}),
        # Read+Search skills (6)
        ("research-patterns", {"Read", "Grep", "Glob"}),
        ("semantic-validation", {"Read", "Grep", "Glob"}),
        ("cross-reference-validation", {"Read", "Grep", "Glob"}),
        ("documentation-currency", {"Read", "Grep", "Glob"}),
        ("advisor-triggers", {"Read", "Grep", "Glob"}),
        ("project-alignment-validation", {"Read", "Grep", "Glob"}),
        # Read+Search+Bash skills (4)
        ("testing-guide", {"Read", "Grep", "Glob", "Bash"}),
        ("observability", {"Read", "Grep", "Glob", "Bash"}),
        ("git-workflow", {"Read", "Grep", "Glob", "Bash"}),
        ("github-workflow", {"Read", "Grep", "Glob", "Bash"}),
        # Read+Write+Edit skills (3)
        ("database-design", {"Read", "Write", "Edit", "Grep", "Glob"}),
        ("file-organization", {"Read", "Write", "Edit", "Grep", "Glob"}),
        ("project-management", {"Read", "Write", "Edit", "Grep", "Glob"}),
    ])
    def test_skill_has_expected_tools(self, skill_name, expected_tools):
        """Verify skill has expected tool set."""
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        assert skill_file.exists(), f"Skill file {skill_name}/SKILL.md not found"

        frontmatter = parse_frontmatter(skill_file)
        actual_tools = set(frontmatter.get('allowed-tools', []))

        assert actual_tools == expected_tools, (
            f"{skill_name} tool assignment mismatch:\n"
            f"  Expected: {sorted(expected_tools)}\n"
            f"  Actual: {sorted(actual_tools)}\n"
            f"  Missing: {sorted(expected_tools - actual_tools)}\n"
            f"  Extra: {sorted(actual_tools - expected_tools)}"
        )

    def test_all_skills_match_expected_tools(self):
        """Verify all skills have exactly their expected tools."""
        mismatches = []

        for skill_name, expected_tools in EXPECTED_TOOLS.items():
            skill_file = SKILLS_DIR / skill_name / "SKILL.md"

            if not skill_file.exists():
                mismatches.append(f"{skill_name}: file not found")
                continue

            frontmatter = parse_frontmatter(skill_file)
            actual_tools = set(frontmatter.get('allowed-tools', []))

            if actual_tools != expected_tools:
                missing = expected_tools - actual_tools
                extra = actual_tools - expected_tools
                mismatches.append(
                    f"{skill_name}: missing={sorted(missing)}, extra={sorted(extra)}"
                )

        assert not mismatches, (
            f"Skill allowed-tools don't match expected assignments:\n" +
            "\n".join(f"  - {m}" for m in mismatches)
        )


class TestPhase4SecurityConstraints:
    """Phase 4: Verify no dangerous broad access patterns."""

    def test_no_wildcard_tools(self):
        """Skills should not use wildcard tools (*, all, any)."""
        skill_files = get_all_skill_files()
        dangerous_usage = []

        for skill_file in skill_files:
            frontmatter = parse_frontmatter(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            # Check for dangerous patterns
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
            frontmatter = parse_frontmatter(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            # Check for invalid tool names
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
            frontmatter = parse_frontmatter(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            if 'Task' in tools:
                task_violations.append(get_skill_name(skill_file))

        assert not task_violations, (
            f"Skills using Task tool: {', '.join(task_violations)}\n"
            "Task tool is reserved for commands and agents, not skills"
        )

    def test_no_todo_tools_in_skills(self):
        """Skills should not use TodoWrite/TodoRead (reserved for agents)."""
        skill_files = get_all_skill_files()
        todo_violations = []

        for skill_file in skill_files:
            frontmatter = parse_frontmatter(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            if 'TodoWrite' in tools or 'TodoRead' in tools:
                todo_violations.append(get_skill_name(skill_file))

        assert not todo_violations, (
            f"Skills using TodoWrite/TodoRead: {', '.join(todo_violations)}\n"
            "Todo tools are reserved for agent workflows, not skills"
        )


class TestPhase5ReadOnlySkills:
    """Phase 5: Verify read-only skills don't have Write/Edit/Bash tools."""

    def test_read_only_skills_no_write_tools(self):
        """Read-only skills should not have Write, Edit, or Bash tools."""
        violations = []

        for skill_name in READ_ONLY_SKILLS.keys():
            skill_file = SKILLS_DIR / skill_name / "SKILL.md"
            if not skill_file.exists():
                continue

            frontmatter = parse_frontmatter(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            # Should only have Read
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

            frontmatter = parse_frontmatter(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            if tools != {"Read"}:
                violations.append(f"{skill_name}: {sorted(tools)}")

        assert not violations, (
            f"Read-only skills without exactly [Read]:\n" +
            "\n".join(f"  - {v}" for v in violations) +
            "\n\nExpected exactly: ['Read']"
        )


class TestPhase6CategoryConsistency:
    """Phase 6: Verify tool assignment patterns within categories."""

    def test_read_search_skills_have_grep_glob(self):
        """Read+Search skills should have Read, Grep, and Glob."""
        violations = []

        for skill_name in READ_SEARCH_SKILLS.keys():
            skill_file = SKILLS_DIR / skill_name / "SKILL.md"
            if not skill_file.exists():
                continue

            frontmatter = parse_frontmatter(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            required = {"Read", "Grep", "Glob"}
            if tools != required:
                missing = required - tools
                extra = tools - required
                violations.append(
                    f"{skill_name}: missing={sorted(missing)}, extra={sorted(extra)}"
                )

        assert not violations, (
            f"Read+Search skills with incorrect tools:\n" +
            "\n".join(f"  - {v}" for v in violations) +
            "\n\nExpected: ['Read', 'Grep', 'Glob']"
        )

    def test_bash_skills_have_read_search_bash(self):
        """Read+Search+Bash skills should have Read, Grep, Glob, and Bash."""
        violations = []

        for skill_name in READ_SEARCH_BASH_SKILLS.keys():
            skill_file = SKILLS_DIR / skill_name / "SKILL.md"
            if not skill_file.exists():
                continue

            frontmatter = parse_frontmatter(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            required = {"Read", "Grep", "Glob", "Bash"}
            if tools != required:
                missing = required - tools
                extra = tools - required
                violations.append(
                    f"{skill_name}: missing={sorted(missing)}, extra={sorted(extra)}"
                )

        assert not violations, (
            f"Read+Search+Bash skills with incorrect tools:\n" +
            "\n".join(f"  - {v}" for v in violations) +
            "\n\nExpected: ['Read', 'Grep', 'Glob', 'Bash']"
        )

    def test_write_edit_skills_have_complete_toolset(self):
        """Read+Write+Edit skills should have Read, Write, Edit, Grep, Glob."""
        violations = []

        for skill_name in READ_WRITE_EDIT_SKILLS.keys():
            skill_file = SKILLS_DIR / skill_name / "SKILL.md"
            if not skill_file.exists():
                continue

            frontmatter = parse_frontmatter(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            required = {"Read", "Write", "Edit", "Grep", "Glob"}
            if tools != required:
                missing = required - tools
                extra = tools - required
                violations.append(
                    f"{skill_name}: missing={sorted(missing)}, extra={sorted(extra)}"
                )

        assert not violations, (
            f"Read+Write+Edit skills with incorrect tools:\n" +
            "\n".join(f"  - {v}" for v in violations) +
            "\n\nExpected: ['Read', 'Write', 'Edit', 'Grep', 'Glob']"
        )


class TestPhase7ToolHierarchy:
    """Phase 7: Verify tool hierarchy makes sense (no Bash without Grep/Glob)."""

    def test_bash_skills_have_search_tools(self):
        """Skills with Bash should also have Grep and Glob."""
        violations = []

        for skill_file in get_all_skill_files():
            frontmatter = parse_frontmatter(skill_file)
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
            frontmatter = parse_frontmatter(skill_file)
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
            frontmatter = parse_frontmatter(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            if ('Grep' in tools or 'Glob' in tools) and 'Read' not in tools:
                violations.append(get_skill_name(skill_file))

        assert not violations, (
            f"Search skills without Read tool: {', '.join(violations)}\n"
            "Skills using Grep/Glob need Read to view search results"
        )


class TestPhase8WebToolsRestriction:
    """Phase 8: Verify skills don't have web research tools."""

    def test_no_web_tools_in_skills(self):
        """Skills should not have WebSearch or WebFetch (reserved for agents)."""
        violations = []

        for skill_file in get_all_skill_files():
            frontmatter = parse_frontmatter(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            web_tools = {'WebSearch', 'WebFetch'}
            if tools & web_tools:
                violations.append(f"{get_skill_name(skill_file)}: {tools & web_tools}")

        assert not violations, (
            f"Skills with web research tools:\n" +
            "\n".join(f"  - {v}" for v in violations) +
            "\n\nWebSearch/WebFetch are reserved for research agents, not skills"
        )


class TestIntegrationAllowedTools:
    """Integration tests for complete allowed-tools implementation."""

    def test_complete_allowed_tools_coverage(self):
        """Verify all 28 skills have complete allowed-tools implementation."""
        # Check count
        skill_files = get_all_skill_files()
        assert len(skill_files) == 28

        # Check each has allowed-tools
        for skill_file in skill_files:
            frontmatter = parse_frontmatter(skill_file)
            skill_name = get_skill_name(skill_file)

            assert 'allowed-tools' in frontmatter, f"{skill_name} missing allowed-tools"

            # Check it's a valid list
            tools = frontmatter['allowed-tools']
            assert isinstance(tools, list), f"{skill_name} allowed-tools not a list"
            assert len(tools) > 0, f"{skill_name} has empty allowed-tools"

            # Check all are valid tools
            assert all(t in VALID_TOOLS for t in tools), (
                f"{skill_name} has invalid tools"
            )

    def test_expected_tools_match_reality(self):
        """EXPECTED_TOOLS constant should match actual frontmatter."""
        for skill_name, expected_tools in EXPECTED_TOOLS.items():
            skill_file = SKILLS_DIR / skill_name / "SKILL.md"
            assert skill_file.exists(), f"{skill_name}/SKILL.md not found"

            frontmatter = parse_frontmatter(skill_file)
            actual_tools = set(frontmatter.get('allowed-tools', []))

            assert actual_tools == expected_tools, (
                f"{skill_name} mismatch between EXPECTED_TOOLS and frontmatter"
            )

    def test_all_categories_represented(self):
        """Verify all 4 skill categories are represented."""
        assert len(READ_ONLY_SKILLS) == 15, "Expected 15 read-only skills"
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

    def test_all_phases_complete(self):
        """Verify all 8 phases of Issue #146 are complete."""
        skill_files = get_all_skill_files()

        # Phase 1: All have allowed-tools
        for skill_file in skill_files:
            frontmatter = parse_frontmatter(skill_file)
            assert 'allowed-tools' in frontmatter

        # Phase 2: All are lists
        for skill_file in skill_files:
            frontmatter = parse_frontmatter(skill_file)
            tools = frontmatter.get('allowed-tools', [])
            assert isinstance(tools, list)

        # Phase 3: Match expected assignments
        for skill_name, expected_tools in EXPECTED_TOOLS.items():
            skill_file = SKILLS_DIR / skill_name / "SKILL.md"
            frontmatter = parse_frontmatter(skill_file)
            actual_tools = set(frontmatter.get('allowed-tools', []))
            assert actual_tools == expected_tools

        # Phase 4: No wildcards
        for skill_file in skill_files:
            frontmatter = parse_frontmatter(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))
            assert not (tools & DANGEROUS_TOOLS)

        # Phase 5: Read-only skills correct
        for skill_name in READ_ONLY_SKILLS.keys():
            skill_file = SKILLS_DIR / skill_name / "SKILL.md"
            frontmatter = parse_frontmatter(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))
            assert tools == {"Read"}

        # Phase 6: Category consistency
        for skill_name in READ_SEARCH_SKILLS.keys():
            skill_file = SKILLS_DIR / skill_name / "SKILL.md"
            frontmatter = parse_frontmatter(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))
            assert tools == {"Read", "Grep", "Glob"}

        # Phase 7: Tool hierarchy
        for skill_file in skill_files:
            frontmatter = parse_frontmatter(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))
            if 'Bash' in tools:
                assert 'Grep' in tools and 'Glob' in tools

        # Phase 8: No web tools
        for skill_file in skill_files:
            frontmatter = parse_frontmatter(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))
            assert not ({'WebSearch', 'WebFetch'} & tools)


class TestEdgeCases:
    """Edge case testing for allowed-tools implementation."""

    def test_frontmatter_parsing_edge_cases(self):
        """Verify frontmatter parser handles edge cases."""
        # Test with minimal frontmatter
        test_content = """---
allowed-tools: [Read]
---
# Skill
"""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(test_content)
            f.flush()

            result = parse_frontmatter(Path(f.name))
            assert result == {'allowed-tools': ['Read']}

        Path(f.name).unlink()

    def test_duplicate_tools_not_allowed(self):
        """Skills should not list same tool twice."""
        duplicates = []

        for skill_file in get_all_skill_files():
            frontmatter = parse_frontmatter(skill_file)
            tools = frontmatter.get('allowed-tools', [])

            if len(tools) != len(set(tools)):
                duplicates.append(f"{get_skill_name(skill_file)}: {tools}")

        assert not duplicates, (
            f"Skills with duplicate tools:\n" +
            "\n".join(f"  - {d}" for d in duplicates)
        )

    def test_case_sensitivity_tools(self):
        """Tool names should be properly capitalized."""
        case_violations = []

        for skill_file in get_all_skill_files():
            frontmatter = parse_frontmatter(skill_file)
            tools = frontmatter.get('allowed-tools', [])

            for tool in tools:
                if tool.lower() in {t.lower() for t in VALID_TOOLS} and tool not in VALID_TOOLS:
                    case_violations.append(f"{get_skill_name(skill_file)}: {tool}")

        assert not case_violations, (
            f"Tools with incorrect capitalization:\n" +
            "\n".join(f"  - {v}" for v in case_violations) +
            f"\n\nValid tool names: {sorted(VALID_TOOLS)}"
        )

    def test_skill_file_structure(self):
        """Verify all skills follow SKILL.md file naming convention."""
        skill_dirs = [d for d in SKILLS_DIR.iterdir() if d.is_dir()]
        missing_skill_files = []

        for skill_dir in skill_dirs:
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                missing_skill_files.append(skill_dir.name)

        assert not missing_skill_files, (
            f"Skill directories missing SKILL.md file: {', '.join(missing_skill_files)}\n"
            "Each skill directory must contain a SKILL.md file"
        )


class TestToolMinimalism:
    """Verify skills don't over-request tools they don't need."""

    def test_read_only_skills_dont_have_search(self):
        """Read-only skills shouldn't have Grep/Glob if they don't search."""
        violations = []

        for skill_name in READ_ONLY_SKILLS.keys():
            skill_file = SKILLS_DIR / skill_name / "SKILL.md"
            if not skill_file.exists():
                continue

            frontmatter = parse_frontmatter(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            # Read-only should not have search tools
            search_tools = {'Grep', 'Glob'}
            if tools & search_tools:
                violations.append(f"{skill_name}: {tools & search_tools}")

        assert not violations, (
            f"Read-only skills with unnecessary search tools:\n" +
            "\n".join(f"  - {v}" for v in violations) +
            "\n\nRead-only skills should only request Read"
        )

    def test_no_skill_has_all_tools(self):
        """No skill should request all available tools."""
        violations = []

        for skill_file in get_all_skill_files():
            frontmatter = parse_frontmatter(skill_file)
            tools = set(frontmatter.get('allowed-tools', []))

            # No skill should need more than 5 tools
            if len(tools) > 5:
                violations.append(f"{get_skill_name(skill_file)}: {len(tools)} tools")

        assert not violations, (
            f"Skills requesting too many tools:\n" +
            "\n".join(f"  - {v}" for v in violations) +
            "\n\nSkills should request minimal tools needed for their function"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=line", "-q"])
