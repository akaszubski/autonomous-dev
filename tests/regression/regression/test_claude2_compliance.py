#!/usr/bin/env python3
"""
Tests for Claude Code 2.0 Compliance (Issue #148)

These tests verify that all plugin components comply with Claude Code 2.0 requirements:
1. Skills have version field in frontmatter
2. Commands have name field in frontmatter
3. Bash patterns in settings use wildcards (Bash(cmd:*) not Bash(cmd))
4. MCP config uses portable paths (${CLAUDE_PROJECT_DIR} not hardcoded)
5. CLAUDE.md has proper metadata (Last Validated date, component table)

All tests should FAIL initially (TDD red phase) until implementation is complete.
"""

import pytest
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional


# Project root detection (tests/regression/regression/ -> project root)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


@pytest.mark.regression
class TestSkillVersionCompliance:
    """Test that all skills have version field in frontmatter."""

    @pytest.fixture
    def skill_files(self) -> List[Path]:
        """Discover all skill SKILL.md files."""
        skills_dir = PROJECT_ROOT / "plugins" / "autonomous-dev" / "skills"
        return list(skills_dir.glob("*/SKILL.md"))

    def test_all_skills_discovered(self, skill_files):
        """Should discover exactly 28 skill files."""
        assert len(skill_files) == 28, f"Expected 28 skills, found {len(skill_files)}"

    def test_all_skills_have_version_field(self, skill_files):
        """All skills should have version: field in YAML frontmatter."""
        missing_version = []

        for skill_file in skill_files:
            frontmatter = self._parse_frontmatter(skill_file)
            if frontmatter is None:
                missing_version.append(f"{skill_file.parent.name}: No frontmatter")
                continue

            if "version" not in frontmatter:
                missing_version.append(f"{skill_file.parent.name}: Missing version field")

        assert not missing_version, (
            f"Skills missing version field:\n" + "\n".join(missing_version)
        )

    def test_skill_version_format(self, skill_files):
        """Version field should follow semantic versioning (X.Y.Z)."""
        invalid_versions = []
        semver_pattern = re.compile(r'^\d+\.\d+\.\d+$')

        for skill_file in skill_files:
            frontmatter = self._parse_frontmatter(skill_file)
            if frontmatter and "version" in frontmatter:
                version = str(frontmatter["version"])
                if not semver_pattern.match(version):
                    invalid_versions.append(
                        f"{skill_file.parent.name}: Invalid version '{version}' (expected X.Y.Z)"
                    )

        assert not invalid_versions, (
            f"Skills with invalid version format:\n" + "\n".join(invalid_versions)
        )

    def test_skill_frontmatter_complete(self, skill_files):
        """Skills should have all required frontmatter fields."""
        required_fields = ["name", "type", "description", "version", "allowed-tools"]
        incomplete_skills = []

        for skill_file in skill_files:
            frontmatter = self._parse_frontmatter(skill_file)
            if not frontmatter:
                incomplete_skills.append(f"{skill_file.parent.name}: No frontmatter")
                continue

            missing_fields = [f for f in required_fields if f not in frontmatter]
            if missing_fields:
                incomplete_skills.append(
                    f"{skill_file.parent.name}: Missing {', '.join(missing_fields)}"
                )

        assert not incomplete_skills, (
            f"Skills with incomplete frontmatter:\n" + "\n".join(incomplete_skills)
        )

    @staticmethod
    def _parse_frontmatter(file_path: Path) -> Optional[Dict[str, Any]]:
        """Parse YAML frontmatter from markdown file."""
        content = file_path.read_text()

        # Match YAML frontmatter between --- delimiters
        match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if not match:
            return None

        frontmatter_text = match.group(1)
        frontmatter = {}

        # Simple YAML parser for our needs (handles strings, lists, booleans)
        for line in frontmatter_text.split('\n'):
            if ':' not in line:
                continue

            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()

            # Handle lists [item1, item2]
            if value.startswith('[') and value.endswith(']'):
                items = value[1:-1].split(',')
                frontmatter[key] = [item.strip() for item in items]
            # Handle booleans
            elif value.lower() in ('true', 'false'):
                frontmatter[key] = value.lower() == 'true'
            # Handle strings
            else:
                frontmatter[key] = value

        return frontmatter


@pytest.mark.regression
class TestCommandNameCompliance:
    """Test that all commands have name field in frontmatter."""

    @pytest.fixture
    def command_files(self) -> List[Path]:
        """Discover all command markdown files."""
        commands_dir = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands"
        return list(commands_dir.glob("*.md"))

    def test_all_commands_discovered(self, command_files):
        """Should discover exactly 7 command files."""
        assert len(command_files) == 7, f"Expected 7 commands, found {len(command_files)}"

    def test_all_commands_have_name_field(self, command_files):
        """All commands should have name: field in YAML frontmatter."""
        missing_name = []

        for command_file in command_files:
            frontmatter = self._parse_frontmatter(command_file)
            if frontmatter is None:
                missing_name.append(f"{command_file.stem}: No frontmatter")
                continue

            if "name" not in frontmatter:
                missing_name.append(f"{command_file.stem}: Missing name field")

        assert not missing_name, (
            f"Commands missing name field:\n" + "\n".join(missing_name)
        )

    def test_command_name_matches_filename(self, command_files):
        """Command name field should match filename (without .md)."""
        mismatches = []

        for command_file in command_files:
            frontmatter = self._parse_frontmatter(command_file)
            if frontmatter and "name" in frontmatter:
                expected_name = command_file.stem
                actual_name = frontmatter["name"]
                if actual_name != expected_name:
                    mismatches.append(
                        f"{command_file.stem}: name='{actual_name}' (expected '{expected_name}')"
                    )

        assert not mismatches, (
            f"Commands with name/filename mismatch:\n" + "\n".join(mismatches)
        )

    def test_command_frontmatter_complete(self, command_files):
        """Commands should have all required frontmatter fields."""
        required_fields = ["name", "description", "allowed-tools"]
        incomplete_commands = []

        for command_file in command_files:
            frontmatter = self._parse_frontmatter(command_file)
            if not frontmatter:
                incomplete_commands.append(f"{command_file.stem}: No frontmatter")
                continue

            missing_fields = [f for f in required_fields if f not in frontmatter]
            if missing_fields:
                incomplete_commands.append(
                    f"{command_file.stem}: Missing {', '.join(missing_fields)}"
                )

        assert not incomplete_commands, (
            f"Commands with incomplete frontmatter:\n" + "\n".join(incomplete_commands)
        )

    @staticmethod
    def _parse_frontmatter(file_path: Path) -> Optional[Dict[str, Any]]:
        """Parse YAML frontmatter from markdown file."""
        content = file_path.read_text()

        # Match YAML frontmatter between --- delimiters
        match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if not match:
            return None

        frontmatter_text = match.group(1)
        frontmatter = {}

        # Simple YAML parser for our needs
        for line in frontmatter_text.split('\n'):
            if ':' not in line:
                continue

            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()

            # Handle lists [item1, item2]
            if value.startswith('[') and value.endswith(']'):
                items = value[1:-1].split(',')
                frontmatter[key] = [item.strip() for item in items]
            # Handle booleans
            elif value.lower() in ('true', 'false'):
                frontmatter[key] = value.lower() == 'true'
            # Handle strings
            else:
                frontmatter[key] = value

        return frontmatter


@pytest.mark.regression
class TestBashWildcardCompliance:
    """Test that settings templates use Bash(cmd:*) not Bash(cmd)."""

    @pytest.fixture
    def settings_templates(self) -> List[Path]:
        """Discover all settings template JSON files."""
        templates_dir = PROJECT_ROOT / "plugins" / "autonomous-dev" / "templates"
        return list(templates_dir.glob("settings.*.json"))

    def test_settings_templates_discovered(self, settings_templates):
        """Should discover at least 5 settings template files."""
        assert len(settings_templates) >= 5, (
            f"Expected at least 5 settings templates, found {len(settings_templates)}"
        )

    def test_bash_patterns_use_wildcards(self, settings_templates):
        """Bash patterns in settings should use wildcards (Bash(cmd:*))."""
        violations = []

        for settings_file in settings_templates:
            data = json.loads(settings_file.read_text())

            # Check permissions.allow list
            if "permissions" in data and "allow" in data["permissions"]:
                for permission in data["permissions"]["allow"]:
                    if not isinstance(permission, str):
                        continue

                    # Check for Bash patterns without wildcards
                    if permission.startswith("Bash(") and ":" in permission:
                        # Extract command part: Bash(git:status) -> git:status
                        cmd_part = permission[5:-1]  # Remove "Bash(" and ")"
                        if ":" in cmd_part:
                            cmd, args = cmd_part.split(":", 1)
                            # Should have wildcard after colon
                            if not args.startswith("*") and args != "*":
                                violations.append(
                                    f"{settings_file.name}: '{permission}' should be 'Bash({cmd}:*)'"
                                )

        assert not violations, (
            f"Bash patterns without wildcards:\n" + "\n".join(violations)
        )

    def test_no_bare_bash_commands(self, settings_templates):
        """Settings should not have bare Bash(cmd) without arguments."""
        violations = []

        for settings_file in settings_templates:
            data = json.loads(settings_file.read_text())

            if "permissions" in data and "allow" in data["permissions"]:
                for permission in data["permissions"]["allow"]:
                    if not isinstance(permission, str):
                        continue

                    # Check for Bash(cmd) without colon (bare command)
                    if permission.startswith("Bash(") and ":" not in permission:
                        # Exception: "Bash(*)" is allowed as catch-all
                        if permission != "Bash(*)":
                            violations.append(
                                f"{settings_file.name}: '{permission}' should specify arguments (use 'Bash(cmd:*)')"
                            )

        assert not violations, (
            f"Bare Bash commands found:\n" + "\n".join(violations)
        )

    def test_settings_have_permission_structure(self, settings_templates):
        """All settings templates should have permissions.allow structure."""
        missing_structure = []

        for settings_file in settings_templates:
            data = json.loads(settings_file.read_text())

            if "permissions" not in data:
                missing_structure.append(f"{settings_file.name}: Missing 'permissions' key")
            elif "allow" not in data["permissions"]:
                missing_structure.append(f"{settings_file.name}: Missing 'permissions.allow' key")
            elif not isinstance(data["permissions"]["allow"], list):
                missing_structure.append(f"{settings_file.name}: 'permissions.allow' is not a list")

        assert not missing_structure, (
            f"Settings with invalid permission structure:\n" + "\n".join(missing_structure)
        )


@pytest.mark.regression
class TestMCPConfigPortability:
    """Test that MCP config uses portable paths."""

    @pytest.fixture
    def mcp_config_template(self) -> Optional[Path]:
        """Find MCP config template file."""
        # Check multiple possible locations
        possible_paths = [
            PROJECT_ROOT / ".mcp" / "config.template.json",
            PROJECT_ROOT / "plugins" / "autonomous-dev" / ".mcp" / "config.template.json",
            PROJECT_ROOT / "templates" / "mcp" / "config.template.json",
        ]

        for path in possible_paths:
            if path.exists():
                return path

        return None

    def test_mcp_config_template_exists(self, mcp_config_template):
        """MCP config template should exist for portable installation."""
        assert mcp_config_template is not None, (
            "MCP config template not found. Expected at .mcp/config.template.json"
        )

    def test_mcp_config_uses_portable_paths(self, mcp_config_template):
        """MCP config should use ${CLAUDE_PROJECT_DIR} instead of hardcoded paths."""
        if mcp_config_template is None:
            pytest.skip("MCP config template not found")

        data = json.loads(mcp_config_template.read_text())
        hardcoded_paths = []

        # Check for hardcoded absolute paths in server configurations
        if "mcpServers" in data:
            for server_name, server_config in data["mcpServers"].items():
                # Check args array for hardcoded paths
                if "args" in server_config:
                    for i, arg in enumerate(server_config["args"]):
                        if not isinstance(arg, str):
                            continue

                        # Detect absolute paths (starts with / or C:\ or similar)
                        if (arg.startswith("/") or
                            (len(arg) > 2 and arg[1] == ":" and arg[2] in ("/", "\\"))):
                            # Should use ${CLAUDE_PROJECT_DIR} instead
                            hardcoded_paths.append(
                                f"{server_name}.args[{i}]: '{arg}' should use '${{CLAUDE_PROJECT_DIR}}'"
                            )

        assert not hardcoded_paths, (
            f"Hardcoded paths in MCP config:\n" + "\n".join(hardcoded_paths)
        )

    def test_mcp_config_has_required_servers(self, mcp_config_template):
        """MCP config should include essential servers."""
        if mcp_config_template is None:
            pytest.skip("MCP config template not found")

        data = json.loads(mcp_config_template.read_text())
        required_servers = ["filesystem", "git"]
        missing_servers = []

        if "mcpServers" not in data:
            missing_servers.append("No mcpServers configuration")
        else:
            for server in required_servers:
                if server not in data["mcpServers"]:
                    missing_servers.append(f"Missing '{server}' server")

        assert not missing_servers, (
            f"MCP config missing required servers:\n" + "\n".join(missing_servers)
        )

    def test_mcp_config_valid_json(self, mcp_config_template):
        """MCP config template should be valid JSON."""
        if mcp_config_template is None:
            pytest.skip("MCP config template not found")

        try:
            json.loads(mcp_config_template.read_text())
        except json.JSONDecodeError as e:
            pytest.fail(f"MCP config template is not valid JSON: {e}")


@pytest.mark.regression
class TestCLAUDEMdMetadata:
    """Test that CLAUDE.md has proper metadata."""

    @pytest.fixture
    def claude_md(self) -> Path:
        """Get CLAUDE.md file."""
        return PROJECT_ROOT / "CLAUDE.md"

    def test_claude_md_exists(self, claude_md):
        """CLAUDE.md should exist at project root."""
        assert claude_md.exists(), "CLAUDE.md not found at project root"

    def test_claude_md_has_last_validated_date(self, claude_md):
        """CLAUDE.md should have 'Last Validated' date in header."""
        content = claude_md.read_text()

        # Look for "Last Validated: YYYY-MM-DD" pattern
        pattern = re.compile(r'\*\*Last Validated\*\*:\s*\d{4}-\d{2}-\d{2}', re.MULTILINE)
        match = pattern.search(content)

        assert match is not None, (
            "CLAUDE.md missing 'Last Validated' date. "
            "Expected format: **Last Validated**: YYYY-MM-DD"
        )

    def test_claude_md_has_component_version_table(self, claude_md):
        """CLAUDE.md should have component version table."""
        content = claude_md.read_text()

        # Look for markdown table with Component and Version columns
        # Should have headers and at least one row
        table_pattern = re.compile(
            r'\|\s*Component\s*\|\s*Version\s*\|.*?\n'
            r'\|[-\s|]+\|.*?\n'
            r'\|[^|]+\|[^|]+\|',
            re.MULTILINE | re.DOTALL
        )
        match = table_pattern.search(content)

        assert match is not None, (
            "CLAUDE.md missing component version table. "
            "Expected table with Component and Version columns"
        )

    def test_claude_md_component_table_has_required_components(self, claude_md):
        """Component table should list core components (commands, agents, skills, hooks)."""
        content = claude_md.read_text()

        required_components = ["Commands", "Agents", "Skills", "Hooks"]
        missing_components = []

        for component in required_components:
            # Look for component in a table row: | Component | Version |
            pattern = re.compile(rf'\|\s*{component}\s*\|', re.IGNORECASE)
            if not pattern.search(content):
                missing_components.append(component)

        assert not missing_components, (
            f"CLAUDE.md component table missing components:\n" +
            "\n".join(missing_components)
        )

    def test_claude_md_has_last_updated_date(self, claude_md):
        """CLAUDE.md should have 'Last Updated' date in header."""
        content = claude_md.read_text()

        # Look for "Last Updated: YYYY-MM-DD" pattern (near top of file)
        # Check first 1000 characters to ensure it's in the header
        header = content[:1000]
        pattern = re.compile(r'\*\*Last Updated\*\*:\s*\d{4}-\d{2}-\d{2}', re.MULTILINE)
        match = pattern.search(header)

        assert match is not None, (
            "CLAUDE.md missing 'Last Updated' date in header. "
            "Expected format: **Last Updated**: YYYY-MM-DD"
        )

    def test_claude_md_dates_are_valid(self, claude_md):
        """All dates in CLAUDE.md should be valid YYYY-MM-DD format."""
        content = claude_md.read_text()

        # Find all dates in YYYY-MM-DD format
        date_pattern = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
        invalid_dates = []

        for match in date_pattern.finditer(content):
            year, month, day = match.groups()
            year, month, day = int(year), int(month), int(day)

            # Basic validation
            if not (2020 <= year <= 2030):
                invalid_dates.append(f"{match.group()}: Invalid year {year}")
            if not (1 <= month <= 12):
                invalid_dates.append(f"{match.group()}: Invalid month {month}")
            if not (1 <= day <= 31):
                invalid_dates.append(f"{match.group()}: Invalid day {day}")

        assert not invalid_dates, (
            f"CLAUDE.md contains invalid dates:\n" + "\n".join(invalid_dates)
        )


@pytest.mark.regression
class TestComplianceSummary:
    """Overall compliance summary tests."""

    def test_all_compliance_categories_covered(self):
        """Verify all 5 compliance categories are tested."""
        # This is a meta-test to ensure we have comprehensive coverage
        test_classes = [
            TestSkillVersionCompliance,
            TestCommandNameCompliance,
            TestBashWildcardCompliance,
            TestMCPConfigPortability,
            TestCLAUDEMdMetadata,
        ]

        assert len(test_classes) == 5, (
            f"Expected 5 compliance test classes, found {len(test_classes)}"
        )

    def test_project_root_detection(self):
        """Project root should be correctly detected."""
        assert PROJECT_ROOT.exists(), f"Project root not found: {PROJECT_ROOT}"
        assert (PROJECT_ROOT / "CLAUDE.md").exists(), (
            f"CLAUDE.md not found at project root: {PROJECT_ROOT}"
        )
        assert (PROJECT_ROOT / "plugins" / "autonomous-dev").exists(), (
            f"Plugin directory not found at: {PROJECT_ROOT / 'plugins' / 'autonomous-dev'}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
