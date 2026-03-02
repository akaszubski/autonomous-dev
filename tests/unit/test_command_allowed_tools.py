#!/usr/bin/env python3
"""
Tests for command allowed-tools frontmatter.

Validates that all command files have proper allowed-tools frontmatter:
1. All commands have allowed-tools field (YAML list of strings)
2. No dangerous patterns (wildcards, duplicates)
3. Tool names are valid (cross-checked against policy file)
4. Structural patterns (read-only commands, Task+Read pairing, Bash+Grep+Glob)

See: https://github.com/akaszubski/autonomous-dev/issues/145

NOTE: Hardcoded tool sets and command-specific assertions were moved to
tests/genai/test_command_tool_assignments.py for semantic LLM-as-judge
validation. This file only contains structural/mechanical checks.
"""

import json
import pytest
import yaml
from pathlib import Path
from typing import Dict, List, Set

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
COMMANDS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands"
POLICY_FILE = PROJECT_ROOT / "plugins" / "autonomous-dev" / "config" / "auto_approve_policy.json"


def _load_valid_tools() -> set[str]:
    """Load valid tool names from policy file (single source of truth)."""
    with open(POLICY_FILE) as f:
        return set(json.load(f)["tools"]["always_allowed"])


VALID_TOOLS = _load_valid_tools()

# Dangerous tools that should be restricted
DANGEROUS_TOOLS = {"*", "all", "any"}

# Internal commands that inherit tools from their parent command
INTERNAL_COMMANDS = {"implement-batch.md", "implement-resume.md"}


def parse_frontmatter(file_path: Path) -> Dict:
    """Parse YAML frontmatter from command markdown file."""
    content = file_path.read_text(encoding='utf-8')

    if not content.startswith('---'):
        return {}

    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}

    frontmatter = parts[1].strip()
    try:
        return yaml.safe_load(frontmatter) or {}
    except yaml.YAMLError:
        return {}


def get_all_command_files() -> List[Path]:
    """Get all command markdown files."""
    return sorted(COMMANDS_DIR.glob("*.md"))


class TestAllowedToolsFrontmatter:
    """All commands must have valid allowed-tools frontmatter."""

    def test_all_commands_have_frontmatter(self):
        command_files = get_all_command_files()
        assert len(command_files) >= 7, f"Expected at least 7 commands, found {len(command_files)}"

        missing = [f.name for f in command_files if not parse_frontmatter(f)]
        assert not missing, f"Commands missing valid frontmatter: {missing}"

    def test_all_commands_have_allowed_tools_field(self):
        missing = [
            f.name for f in get_all_command_files()
            if 'allowed-tools' not in parse_frontmatter(f)
            and f.name not in INTERNAL_COMMANDS
        ]
        assert not missing, f"Commands missing allowed-tools field: {missing}"

    def test_allowed_tools_is_list_of_strings(self):
        invalid = []
        for cmd_file in get_all_command_files():
            fm = parse_frontmatter(cmd_file)
            tools = fm.get('allowed-tools')
            if tools is None:
                continue
            if not isinstance(tools, list):
                invalid.append(f"{cmd_file.name}: type={type(tools).__name__}")
            elif not all(isinstance(t, str) for t in tools):
                invalid.append(f"{cmd_file.name}: contains non-string items")
        assert not invalid, f"Invalid allowed-tools format:\n" + "\n".join(f"  - {i}" for i in invalid)

    def test_allowed_tools_not_empty(self):
        empty = [
            f.name for f in get_all_command_files()
            if isinstance(parse_frontmatter(f).get('allowed-tools'), list)
            and len(parse_frontmatter(f)['allowed-tools']) == 0
        ]
        assert not empty, f"Commands with empty allowed-tools: {empty}"


class TestSecurityConstraints:
    """No dangerous broad access patterns."""

    def test_no_wildcard_tools(self):
        violations = []
        for cmd_file in get_all_command_files():
            tools = set(parse_frontmatter(cmd_file).get('allowed-tools', []))
            bad = tools & DANGEROUS_TOOLS
            if bad:
                violations.append(f"{cmd_file.name}: {bad}")
        assert not violations, f"Wildcard tools found:\n" + "\n".join(f"  - {v}" for v in violations)

    def test_all_tools_are_valid(self):
        """All tools in allowed-tools must exist in the policy file's always_allowed."""
        invalid = []
        for cmd_file in get_all_command_files():
            tools = set(parse_frontmatter(cmd_file).get('allowed-tools', []))
            unknown = tools - VALID_TOOLS
            if unknown:
                invalid.append(f"{cmd_file.name}: {sorted(unknown)}")
        assert not invalid, (
            f"Commands with tools not in policy always_allowed:\n"
            + "\n".join(f"  - {t}" for t in invalid)
            + f"\n\nValid tools (from policy): {sorted(VALID_TOOLS)}"
        )

    def test_no_duplicate_tools(self):
        duplicates = []
        for cmd_file in get_all_command_files():
            tools = parse_frontmatter(cmd_file).get('allowed-tools', [])
            if len(tools) != len(set(tools)):
                duplicates.append(f"{cmd_file.name}: {tools}")
        assert not duplicates, f"Duplicate tools:\n" + "\n".join(f"  - {d}" for d in duplicates)

    def test_case_sensitivity(self):
        violations = []
        valid_lower = {t.lower(): t for t in VALID_TOOLS}
        for cmd_file in get_all_command_files():
            for tool in parse_frontmatter(cmd_file).get('allowed-tools', []):
                if tool.lower() in valid_lower and tool != valid_lower[tool.lower()]:
                    violations.append(f"{cmd_file.name}: '{tool}' should be '{valid_lower[tool.lower()]}'")
        assert not violations, f"Case errors:\n" + "\n".join(f"  - {v}" for v in violations)


class TestStructuralPatterns:
    """Tool assignment patterns that should hold across all commands."""

    def test_task_commands_have_read(self):
        """Commands with Task should also have Read."""
        incomplete = []
        for cmd_file in get_all_command_files():
            tools = set(parse_frontmatter(cmd_file).get('allowed-tools', []))
            if 'Task' in tools and 'Read' not in tools:
                incomplete.append(cmd_file.name)
        assert not incomplete, f"Task commands without Read: {incomplete}"

    def test_write_commands_have_read(self):
        """Commands with Write or Edit must also have Read."""
        incomplete = []
        for cmd_file in get_all_command_files():
            tools = set(parse_frontmatter(cmd_file).get('allowed-tools', []))
            if ('Write' in tools or 'Edit' in tools) and 'Read' not in tools:
                incomplete.append(cmd_file.name)
        assert not incomplete, f"Write/Edit commands without Read: {incomplete}"

    def test_no_legacy_manual_restrictions(self):
        """Commands should use frontmatter, not inline tool restrictions."""
        legacy_patterns = [
            "You cannot use Write",
            "You are not allowed to use",
            "Restricted tools:"
        ]
        violations = []
        for cmd_file in get_all_command_files():
            content = cmd_file.read_text(encoding='utf-8')
            found = [p for p in legacy_patterns if p in content]
            if found:
                violations.append(f"{cmd_file.name}: {found}")
        assert not violations, f"Legacy restrictions:\n" + "\n".join(f"  - {v}" for v in violations)


class TestEdgeCases:
    """Edge case testing for frontmatter parsing."""

    def test_frontmatter_parsing_minimal(self):
        import tempfile
        test_content = "---\nallowed-tools: [Read]\n---\n# Command\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(test_content)
            f.flush()
            result = parse_frontmatter(Path(f.name))
            assert result == {'allowed-tools': ['Read']}
        Path(f.name).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=line", "-q"])
