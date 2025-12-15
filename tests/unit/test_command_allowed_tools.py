#!/usr/bin/env python3
"""
Tests for Issue #145 - Add allowed-tools frontmatter to commands

Validates that all command files have proper allowed-tools frontmatter:
1. All 7 commands have allowed-tools field
2. allowed-tools is a YAML list (not string)
3. Each command has correct tools for its function
4. No commands have dangerous broad access (e.g., wildcards)
5. Read-only commands don't have Write tools
6. Web research commands have WebSearch/WebFetch
7. Tool names are valid Claude Code tools

See: https://github.com/akaszubski/autonomous-dev/issues/145
"""

import pytest
import yaml
from pathlib import Path
from typing import Dict, List, Set

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
COMMANDS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands"

# Valid Claude Code tools (comprehensive list)
VALID_TOOLS = {
    "Task", "Read", "Write", "Edit", "Bash", "Grep", "Glob",
    "WebSearch", "WebFetch", "TodoWrite", "TodoRead"
}

# Expected tool assignments per command (based on implementation plan)
EXPECTED_TOOLS = {
    "auto-implement.md": {
        "Task", "Read", "Write", "Edit", "Bash", "Grep", "Glob", "WebSearch", "WebFetch"
    },
    "batch-implement.md": {
        "Task", "Read", "Write", "Bash", "Grep", "Glob"
    },
    "create-issue.md": {
        "Task", "Read", "Bash", "Grep", "Glob"
    },
    "align.md": {
        "Task", "Read", "Write", "Edit", "Grep", "Glob"
    },
    "setup.md": {
        "Task", "Read", "Write", "Bash", "Grep", "Glob"
    },
    "sync.md": {
        "Task", "Read", "Write", "Bash", "Grep", "Glob"
    },
    "health-check.md": {
        "Read", "Bash", "Grep", "Glob"
    }
}

# Commands that should NOT have Write tools (read-only)
READ_ONLY_COMMANDS = {"health-check.md"}

# Commands that should have web research tools
WEB_RESEARCH_COMMANDS = {"auto-implement.md"}

# Dangerous tools that should be restricted
DANGEROUS_TOOLS = {"*", "all", "any"}


def parse_frontmatter(file_path: Path) -> Dict:
    """Parse YAML frontmatter from command markdown file."""
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


def get_all_command_files() -> List[Path]:
    """Get all command markdown files."""
    return sorted(COMMANDS_DIR.glob("*.md"))


class TestPhase1AllowedToolsFrontmatter:
    """Phase 1: Verify all commands have allowed-tools frontmatter field."""

    def test_all_commands_have_frontmatter(self):
        """All command files should have valid YAML frontmatter."""
        command_files = get_all_command_files()
        assert len(command_files) >= 7, f"Expected at least 7 commands, found {len(command_files)}"

        missing_frontmatter = []
        for cmd_file in command_files:
            frontmatter = parse_frontmatter(cmd_file)
            if not frontmatter:
                missing_frontmatter.append(cmd_file.name)

        assert not missing_frontmatter, (
            f"Commands missing valid frontmatter: {', '.join(missing_frontmatter)}\n"
            "All commands must have YAML frontmatter"
        )

    def test_all_commands_have_allowed_tools_field(self):
        """All command files should have allowed-tools: field in frontmatter."""
        command_files = get_all_command_files()
        missing_allowed_tools = []

        for cmd_file in command_files:
            frontmatter = parse_frontmatter(cmd_file)
            if 'allowed-tools' not in frontmatter:
                missing_allowed_tools.append(cmd_file.name)

        assert not missing_allowed_tools, (
            f"Commands missing allowed-tools: field: {', '.join(missing_allowed_tools)}\n"
            "Phase 1 requires all commands to have allowed-tools: in frontmatter"
        )

    def test_expected_commands_exist(self):
        """All 7 expected commands should exist."""
        command_files = get_all_command_files()
        command_names = {f.name for f in command_files}

        for expected_cmd in EXPECTED_TOOLS.keys():
            assert expected_cmd in command_names, (
                f"Expected command {expected_cmd} not found in {COMMANDS_DIR}"
            )


class TestPhase2AllowedToolsDataType:
    """Phase 2: Verify allowed-tools is a YAML list (not string)."""

    def test_allowed_tools_is_list(self):
        """allowed-tools: field should be a list of strings."""
        command_files = get_all_command_files()
        invalid_types = []

        for cmd_file in command_files:
            frontmatter = parse_frontmatter(cmd_file)
            if 'allowed-tools' in frontmatter:
                tools = frontmatter['allowed-tools']
                if not isinstance(tools, list):
                    invalid_types.append(f"{cmd_file.name}: {type(tools).__name__}")
                elif not all(isinstance(t, str) for t in tools):
                    invalid_types.append(f"{cmd_file.name}: contains non-string items")

        assert not invalid_types, (
            f"Commands with invalid allowed-tools: type:\n" +
            "\n".join(f"  - {t}" for t in invalid_types) +
            "\n\nallowed-tools: must be a list of strings"
        )

    def test_allowed_tools_not_empty(self):
        """allowed-tools: should not be an empty list."""
        command_files = get_all_command_files()
        empty_tools = []

        for cmd_file in command_files:
            frontmatter = parse_frontmatter(cmd_file)
            if 'allowed-tools' in frontmatter:
                tools = frontmatter['allowed-tools']
                if isinstance(tools, list) and len(tools) == 0:
                    empty_tools.append(cmd_file.name)

        assert not empty_tools, (
            f"Commands with empty allowed-tools: list: {', '.join(empty_tools)}\n"
            "Every command needs at least one tool"
        )


class TestPhase3CorrectToolAssignments:
    """Phase 3: Verify each command has correct tools for its function."""

    @pytest.mark.parametrize("cmd_name,expected_tools", [
        ("auto-implement.md", {"Task", "Read", "Write", "Edit", "Bash", "Grep", "Glob", "WebSearch", "WebFetch"}),
        ("batch-implement.md", {"Task", "Read", "Write", "Bash", "Grep", "Glob"}),
        ("create-issue.md", {"Task", "Read", "Bash", "Grep", "Glob"}),
        ("align.md", {"Task", "Read", "Write", "Edit", "Grep", "Glob"}),
        ("setup.md", {"Task", "Read", "Write", "Bash", "Grep", "Glob"}),
        ("sync.md", {"Task", "Read", "Write", "Bash", "Grep", "Glob"}),
        ("health-check.md", {"Read", "Bash", "Grep", "Glob"}),
    ])
    def test_command_has_expected_tools(self, cmd_name, expected_tools):
        """Verify command has expected tool set."""
        cmd_file = COMMANDS_DIR / cmd_name
        assert cmd_file.exists(), f"Command file {cmd_name} not found"

        frontmatter = parse_frontmatter(cmd_file)
        actual_tools = set(frontmatter.get('allowed-tools', []))

        assert actual_tools == expected_tools, (
            f"{cmd_name} tool assignment mismatch:\n"
            f"  Expected: {sorted(expected_tools)}\n"
            f"  Actual: {sorted(actual_tools)}\n"
            f"  Missing: {sorted(expected_tools - actual_tools)}\n"
            f"  Extra: {sorted(actual_tools - expected_tools)}"
        )

    def test_all_commands_match_expected_tools(self):
        """Verify all commands have exactly their expected tools."""
        mismatches = []

        for cmd_name, expected_tools in EXPECTED_TOOLS.items():
            cmd_file = COMMANDS_DIR / cmd_name

            if not cmd_file.exists():
                mismatches.append(f"{cmd_name}: file not found")
                continue

            frontmatter = parse_frontmatter(cmd_file)
            actual_tools = set(frontmatter.get('allowed-tools', []))

            if actual_tools != expected_tools:
                missing = expected_tools - actual_tools
                extra = actual_tools - expected_tools
                mismatches.append(
                    f"{cmd_name}: missing={sorted(missing)}, extra={sorted(extra)}"
                )

        assert not mismatches, (
            f"Command allowed-tools don't match expected assignments:\n" +
            "\n".join(f"  - {m}" for m in mismatches)
        )


class TestPhase4SecurityConstraints:
    """Phase 4: Verify no dangerous broad access patterns."""

    def test_no_wildcard_tools(self):
        """Commands should not use wildcard tools (*, all, any)."""
        command_files = get_all_command_files()
        dangerous_usage = []

        for cmd_file in command_files:
            frontmatter = parse_frontmatter(cmd_file)
            tools = set(frontmatter.get('allowed-tools', []))

            # Check for dangerous patterns
            violations = tools & DANGEROUS_TOOLS
            if violations:
                dangerous_usage.append(f"{cmd_file.name}: {violations}")

        assert not dangerous_usage, (
            f"Commands with dangerous wildcard tools:\n" +
            "\n".join(f"  - {u}" for u in dangerous_usage) +
            "\n\nWildcards bypass tool restrictions and are security risks"
        )

    def test_all_tools_are_valid(self):
        """All tools in allowed-tools should be valid Claude Code tools."""
        command_files = get_all_command_files()
        invalid_tools = []

        for cmd_file in command_files:
            frontmatter = parse_frontmatter(cmd_file)
            tools = set(frontmatter.get('allowed-tools', []))

            # Check for invalid tool names
            unknown = tools - VALID_TOOLS
            if unknown:
                invalid_tools.append(f"{cmd_file.name}: {sorted(unknown)}")

        assert not invalid_tools, (
            f"Commands with invalid tool names:\n" +
            "\n".join(f"  - {t}" for t in invalid_tools) +
            f"\n\nValid tools: {sorted(VALID_TOOLS)}"
        )

    def test_no_todo_tools_in_commands(self):
        """Commands should not use TodoWrite/TodoRead (reserved for agents)."""
        command_files = get_all_command_files()
        todo_violations = []

        for cmd_file in command_files:
            frontmatter = parse_frontmatter(cmd_file)
            tools = set(frontmatter.get('allowed-tools', []))

            if 'TodoWrite' in tools or 'TodoRead' in tools:
                todo_violations.append(cmd_file.name)

        assert not todo_violations, (
            f"Commands using TodoWrite/TodoRead: {', '.join(todo_violations)}\n"
            "Todo tools are reserved for agent workflows, not commands"
        )


class TestPhase5ReadOnlyCommands:
    """Phase 5: Verify read-only commands don't have Write tools."""

    def test_health_check_is_read_only(self):
        """health-check.md should not have Write or Edit tools."""
        cmd_file = COMMANDS_DIR / "health-check.md"
        assert cmd_file.exists(), "health-check.md not found"

        frontmatter = parse_frontmatter(cmd_file)
        tools = set(frontmatter.get('allowed-tools', []))

        # Should not have write capabilities
        write_tools = {'Write', 'Edit'}
        violations = tools & write_tools

        assert not violations, (
            f"health-check.md has write tools: {violations}\n"
            "Health check should be read-only (validation only)"
        )

    def test_read_only_commands_follow_policy(self):
        """All read-only commands should not have Write or Edit."""
        violations = []

        for cmd_name in READ_ONLY_COMMANDS:
            cmd_file = COMMANDS_DIR / cmd_name
            if not cmd_file.exists():
                continue

            frontmatter = parse_frontmatter(cmd_file)
            tools = set(frontmatter.get('allowed-tools', []))

            write_tools = {'Write', 'Edit'}
            if tools & write_tools:
                violations.append(f"{cmd_name}: {tools & write_tools}")

        assert not violations, (
            f"Read-only commands with write tools:\n" +
            "\n".join(f"  - {v}" for v in violations)
        )

    def test_create_issue_no_write_tools(self):
        """create-issue.md should not have Write (uses gh CLI)."""
        cmd_file = COMMANDS_DIR / "create-issue.md"
        assert cmd_file.exists(), "create-issue.md not found"

        frontmatter = parse_frontmatter(cmd_file)
        tools = set(frontmatter.get('allowed-tools', []))

        # create-issue uses gh CLI, not Write tool
        assert 'Write' not in tools, (
            "create-issue.md should not have Write tool (uses gh CLI via Bash)"
        )


class TestPhase6WebResearchTools:
    """Phase 6: Verify web research commands have WebSearch/WebFetch."""

    def test_auto_implement_has_web_tools(self):
        """auto-implement.md should have WebSearch and WebFetch for research."""
        cmd_file = COMMANDS_DIR / "auto-implement.md"
        assert cmd_file.exists(), "auto-implement.md not found"

        frontmatter = parse_frontmatter(cmd_file)
        tools = set(frontmatter.get('allowed-tools', []))

        assert 'WebSearch' in tools, "auto-implement.md missing WebSearch"
        assert 'WebFetch' in tools, "auto-implement.md missing WebFetch"

    def test_web_research_commands_complete(self):
        """Commands needing web research should have both WebSearch and WebFetch."""
        incomplete = []

        for cmd_name in WEB_RESEARCH_COMMANDS:
            cmd_file = COMMANDS_DIR / cmd_name
            if not cmd_file.exists():
                continue

            frontmatter = parse_frontmatter(cmd_file)
            tools = set(frontmatter.get('allowed-tools', []))

            # Need both tools for complete web research
            if 'WebSearch' not in tools or 'WebFetch' not in tools:
                missing = []
                if 'WebSearch' not in tools:
                    missing.append('WebSearch')
                if 'WebFetch' not in tools:
                    missing.append('WebFetch')
                incomplete.append(f"{cmd_name}: missing {missing}")

        assert not incomplete, (
            f"Web research commands incomplete:\n" +
            "\n".join(f"  - {i}" for i in incomplete)
        )

    def test_non_research_commands_no_web_tools(self):
        """Commands not doing web research should not have WebSearch/WebFetch."""
        violations = []

        for cmd_name in EXPECTED_TOOLS.keys():
            if cmd_name in WEB_RESEARCH_COMMANDS:
                continue

            cmd_file = COMMANDS_DIR / cmd_name
            if not cmd_file.exists():
                continue

            frontmatter = parse_frontmatter(cmd_file)
            tools = set(frontmatter.get('allowed-tools', []))

            web_tools = {'WebSearch', 'WebFetch'}
            if tools & web_tools:
                violations.append(f"{cmd_name}: {tools & web_tools}")

        assert not violations, (
            f"Non-research commands with web tools:\n" +
            "\n".join(f"  - {v}" for v in violations) +
            "\n\nOnly auto-implement.md should have web research tools"
        )


class TestPhase7ToolConsistency:
    """Phase 7: Verify tool assignment consistency and patterns."""

    def test_all_commands_have_task_or_read(self):
        """All commands should have at least Task or Read for basic operation."""
        missing_basic = []

        for cmd_file in get_all_command_files():
            frontmatter = parse_frontmatter(cmd_file)
            tools = set(frontmatter.get('allowed-tools', []))

            if 'Task' not in tools and 'Read' not in tools:
                missing_basic.append(cmd_file.name)

        assert not missing_basic, (
            f"Commands without Task or Read: {', '.join(missing_basic)}\n"
            "Commands need at least Task or Read for basic functionality"
        )

    def test_commands_with_task_pattern(self):
        """Commands using Task tool should have supporting tools."""
        incomplete = []

        for cmd_file in get_all_command_files():
            frontmatter = parse_frontmatter(cmd_file)
            tools = set(frontmatter.get('allowed-tools', []))

            if 'Task' in tools:
                # Task commands typically need Read for context
                if 'Read' not in tools:
                    incomplete.append(f"{cmd_file.name}: Task without Read")

        assert not incomplete, (
            f"Commands with incomplete Task patterns:\n" +
            "\n".join(f"  - {i}" for i in incomplete) +
            "\n\nTask commands typically need Read for context"
        )

    def test_bash_commands_have_grep_glob(self):
        """Commands with Bash should also have Grep/Glob for file operations."""
        incomplete = []

        for cmd_file in get_all_command_files():
            frontmatter = parse_frontmatter(cmd_file)
            tools = set(frontmatter.get('allowed-tools', []))

            if 'Bash' in tools:
                # Bash commands typically need Grep and Glob
                missing = []
                if 'Grep' not in tools:
                    missing.append('Grep')
                if 'Glob' not in tools:
                    missing.append('Glob')

                if missing:
                    incomplete.append(f"{cmd_file.name}: missing {missing}")

        assert not incomplete, (
            f"Bash commands with incomplete file tools:\n" +
            "\n".join(f"  - {i}" for i in incomplete) +
            "\n\nBash commands should have Grep and Glob for file operations"
        )


class TestIntegrationAllowedTools:
    """Integration tests for complete allowed-tools implementation."""

    def test_complete_allowed_tools_coverage(self):
        """Verify all 7 commands have complete allowed-tools implementation."""
        # Check count
        command_files = get_all_command_files()
        assert len(command_files) >= 7

        # Check each has allowed-tools
        for cmd_file in command_files:
            frontmatter = parse_frontmatter(cmd_file)
            assert 'allowed-tools' in frontmatter, f"{cmd_file.name} missing allowed-tools"

            # Check it's a valid list
            tools = frontmatter['allowed-tools']
            assert isinstance(tools, list), f"{cmd_file.name} allowed-tools not a list"
            assert len(tools) > 0, f"{cmd_file.name} has empty allowed-tools"

            # Check all are valid tools
            assert all(t in VALID_TOOLS for t in tools), (
                f"{cmd_file.name} has invalid tools"
            )

    def test_expected_tools_match_reality(self):
        """EXPECTED_TOOLS constant should match actual frontmatter."""
        for cmd_name, expected_tools in EXPECTED_TOOLS.items():
            cmd_file = COMMANDS_DIR / cmd_name
            assert cmd_file.exists(), f"{cmd_name} not found"

            frontmatter = parse_frontmatter(cmd_file)
            actual_tools = set(frontmatter.get('allowed-tools', []))

            assert actual_tools == expected_tools, (
                f"{cmd_name} mismatch between EXPECTED_TOOLS and frontmatter"
            )

    def test_no_regression_to_manual_restrictions(self):
        """Commands should not have manual tool restriction code."""
        # This would indicate a regression to pre-Issue #145 state
        for cmd_file in get_all_command_files():
            content = cmd_file.read_text(encoding='utf-8')

            # Check for legacy manual restrictions
            legacy_patterns = [
                "You cannot use Write",
                "You are not allowed to use",
                "Tools available:",
                "Restricted tools:"
            ]

            violations = []
            for pattern in legacy_patterns:
                if pattern in content:
                    violations.append(pattern)

            assert not violations, (
                f"{cmd_file.name} has legacy manual tool restrictions:\n" +
                "\n".join(f"  - {v}" for v in violations) +
                "\n\nUse allowed-tools frontmatter instead"
            )

    def test_all_phases_complete(self):
        """Verify all 7 phases of Issue #145 are complete."""
        command_files = get_all_command_files()

        # Phase 1: All have allowed-tools
        for cmd_file in command_files:
            frontmatter = parse_frontmatter(cmd_file)
            assert 'allowed-tools' in frontmatter

        # Phase 2: All are lists
        for cmd_file in command_files:
            frontmatter = parse_frontmatter(cmd_file)
            tools = frontmatter.get('allowed-tools', [])
            assert isinstance(tools, list)

        # Phase 3: Match expected assignments
        for cmd_name, expected_tools in EXPECTED_TOOLS.items():
            cmd_file = COMMANDS_DIR / cmd_name
            frontmatter = parse_frontmatter(cmd_file)
            actual_tools = set(frontmatter.get('allowed-tools', []))
            assert actual_tools == expected_tools

        # Phase 4: No wildcards
        for cmd_file in command_files:
            frontmatter = parse_frontmatter(cmd_file)
            tools = set(frontmatter.get('allowed-tools', []))
            assert not (tools & DANGEROUS_TOOLS)

        # Phase 5: Read-only commands work
        for cmd_name in READ_ONLY_COMMANDS:
            cmd_file = COMMANDS_DIR / cmd_name
            frontmatter = parse_frontmatter(cmd_file)
            tools = set(frontmatter.get('allowed-tools', []))
            assert not ({'Write', 'Edit'} & tools)

        # Phase 6: Web research works
        for cmd_name in WEB_RESEARCH_COMMANDS:
            cmd_file = COMMANDS_DIR / cmd_name
            frontmatter = parse_frontmatter(cmd_file)
            tools = set(frontmatter.get('allowed-tools', []))
            assert 'WebSearch' in tools and 'WebFetch' in tools

        # Phase 7: All tools valid
        for cmd_file in command_files:
            frontmatter = parse_frontmatter(cmd_file)
            tools = set(frontmatter.get('allowed-tools', []))
            assert tools.issubset(VALID_TOOLS)


class TestEdgeCases:
    """Edge case testing for allowed-tools implementation."""

    def test_frontmatter_parsing_edge_cases(self):
        """Verify frontmatter parser handles edge cases."""
        # Test with minimal frontmatter
        test_content = """---
allowed-tools: [Read]
---
# Command
"""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(test_content)
            f.flush()

            result = parse_frontmatter(Path(f.name))
            assert result == {'allowed-tools': ['Read']}

        Path(f.name).unlink()

    def test_duplicate_tools_not_allowed(self):
        """Commands should not list same tool twice."""
        duplicates = []

        for cmd_file in get_all_command_files():
            frontmatter = parse_frontmatter(cmd_file)
            tools = frontmatter.get('allowed-tools', [])

            if len(tools) != len(set(tools)):
                duplicates.append(f"{cmd_file.name}: {tools}")

        assert not duplicates, (
            f"Commands with duplicate tools:\n" +
            "\n".join(f"  - {d}" for d in duplicates)
        )

    def test_case_sensitivity_tools(self):
        """Tool names should be properly capitalized."""
        case_violations = []

        for cmd_file in get_all_command_files():
            frontmatter = parse_frontmatter(cmd_file)
            tools = frontmatter.get('allowed-tools', [])

            for tool in tools:
                if tool.lower() in {t.lower() for t in VALID_TOOLS} and tool not in VALID_TOOLS:
                    case_violations.append(f"{cmd_file.name}: {tool}")

        assert not case_violations, (
            f"Tools with incorrect capitalization:\n" +
            "\n".join(f"  - {v}" for v in case_violations) +
            f"\n\nValid tool names: {sorted(VALID_TOOLS)}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=line", "-q"])
