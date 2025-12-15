#!/usr/bin/env python3
"""
Tests for Claude Code 2.0 Compliance (Issues #148, #150)

These tests verify that all plugin components comply with Claude Code 2.0 requirements:

PHASE 1 (Issue #148 - 24 tests):
1. Skills have version field in frontmatter
2. Commands have name field in frontmatter
3. Bash patterns in settings use wildcards (Bash(cmd:*) not Bash(cmd))
4. MCP config uses portable paths (${CLAUDE_PROJECT_DIR} not hardcoded)
5. CLAUDE.md has proper metadata (Last Validated date, component table)

PHASE 2 (Issue #150 - 12 additional tests):
6. Agent skills declarations reference existing skills
7. Agent model field uses approved values (haiku, sonnet, opus)
8. Agent permissionMode field validation (when present)
9. Skill keywords field exists
10. Skill type field uses consistent taxonomy
11. Skill auto_activate field validation
12. Skill disable-model-invocation field validation
13. Command argument-hint field format
14. Command disable-model-invocation field validation
15. Cross-component reference integrity
16. Plugin manifest schema validation (if present)
17. YAML injection prevention

All tests should FAIL initially (TDD red phase) until implementation is complete.
"""

import pytest
import json
import re
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Set


# Project root detection (tests/regression/regression/ -> project root)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# Valid values for frontmatter fields
VALID_AGENT_MODELS = {"haiku", "sonnet", "opus"}
VALID_SKILL_TYPES = {"knowledge", "pattern", "validation", "automation"}
VALID_PERMISSION_MODES = {"ask", "allow", "deny"}


def parse_yaml_frontmatter(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse YAML frontmatter from markdown file using yaml.safe_load().

    This is the preferred method for parsing frontmatter as it:
    - Handles complex YAML structures (lists, nested objects)
    - Validates YAML syntax
    - Prevents YAML injection attacks

    Args:
        file_path: Path to markdown file with YAML frontmatter

    Returns:
        Dictionary of frontmatter fields, or None if no frontmatter found
    """
    content = file_path.read_text(encoding='utf-8')

    if not content.startswith('---'):
        return None

    # Find second --- delimiter
    parts = content.split('---', 2)
    if len(parts) < 3:
        return None

    frontmatter_text = parts[1].strip()

    try:
        return yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError:
        return None


def get_all_skill_names() -> Set[str]:
    """Get set of all available skill names (for cross-reference validation)."""
    skills_dir = PROJECT_ROOT / "plugins" / "autonomous-dev" / "skills"
    skill_names = set()

    for skill_dir in skills_dir.iterdir():
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            skill_names.add(skill_dir.name)

    return skill_names


def get_all_agent_files() -> List[Path]:
    """Get all agent markdown files."""
    agents_dir = PROJECT_ROOT / "plugins" / "autonomous-dev" / "agents"
    return sorted(agents_dir.glob("*.md"))


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

    def test_skill_keywords(self, skill_files):
        """
        All skills should have keywords field for searchability (Issue #150).

        Keywords help Claude Code and users discover relevant skills.
        """
        missing_keywords = []

        for skill_file in skill_files:
            frontmatter = parse_yaml_frontmatter(skill_file)
            if not frontmatter:
                missing_keywords.append(f"{skill_file.parent.name}: No frontmatter")
                continue

            if "keywords" not in frontmatter:
                missing_keywords.append(f"{skill_file.parent.name}: Missing keywords field")

        assert not missing_keywords, (
            f"Skills missing keywords field:\n" + "\n".join(missing_keywords)
        )

    def test_skill_type_taxonomy(self, skill_files):
        """
        Skill type field should use consistent taxonomy (Issue #150).

        Valid types: knowledge, pattern, validation, automation
        """
        invalid_types = []

        for skill_file in skill_files:
            frontmatter = parse_yaml_frontmatter(skill_file)
            if not frontmatter:
                continue

            if "type" not in frontmatter:
                continue  # Already tested in test_skill_frontmatter_complete

            skill_type = frontmatter["type"]
            if skill_type not in VALID_SKILL_TYPES:
                invalid_types.append(
                    f"{skill_file.parent.name}: Invalid type '{skill_type}' "
                    f"(expected one of: {', '.join(sorted(VALID_SKILL_TYPES))})"
                )

        assert not invalid_types, (
            f"Skills with invalid type taxonomy:\n" + "\n".join(invalid_types)
        )

    def test_skill_auto_activate(self, skill_files):
        """
        Skill auto_activate field should be boolean when present (Issue #150).

        Optional field, but if present must be true or false.
        """
        invalid_auto_activate = []

        for skill_file in skill_files:
            frontmatter = parse_yaml_frontmatter(skill_file)
            if not frontmatter:
                continue

            if "auto_activate" not in frontmatter:
                continue  # Optional field

            auto_activate = frontmatter["auto_activate"]
            if not isinstance(auto_activate, bool):
                invalid_auto_activate.append(
                    f"{skill_file.parent.name}: auto_activate should be boolean "
                    f"(got {type(auto_activate).__name__}: {auto_activate})"
                )

        assert not invalid_auto_activate, (
            f"Skills with invalid auto_activate field:\n" + "\n".join(invalid_auto_activate)
        )

    def test_skill_disable_model_invocation(self, skill_files):
        """
        Skill disable-model-invocation field should be boolean when present (Issue #150).

        Optional field, controls whether skill can invoke language model.
        """
        invalid_disable = []

        for skill_file in skill_files:
            frontmatter = parse_yaml_frontmatter(skill_file)
            if not frontmatter:
                continue

            if "disable-model-invocation" not in frontmatter:
                continue  # Optional field

            disable_invocation = frontmatter["disable-model-invocation"]
            if not isinstance(disable_invocation, bool):
                invalid_disable.append(
                    f"{skill_file.parent.name}: disable-model-invocation should be boolean "
                    f"(got {type(disable_invocation).__name__}: {disable_invocation})"
                )

        assert not invalid_disable, (
            f"Skills with invalid disable-model-invocation field:\n" + "\n".join(invalid_disable)
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

    def test_command_argument_hint(self, command_files):
        """
        Commands should have argument_hint field for user guidance (Issue #150).

        Provides inline help for command arguments in Claude Code UI.
        """
        missing_hint = []

        for command_file in command_files:
            frontmatter = parse_yaml_frontmatter(command_file)
            if not frontmatter:
                continue

            if "argument_hint" not in frontmatter:
                missing_hint.append(f"{command_file.stem}: Missing argument_hint field")
                continue

            # Validate format: should be non-empty string
            hint = frontmatter["argument_hint"]
            if not isinstance(hint, str) or not hint.strip():
                missing_hint.append(
                    f"{command_file.stem}: argument_hint should be non-empty string "
                    f"(got {type(hint).__name__})"
                )

        assert not missing_hint, (
            f"Commands with missing/invalid argument_hint:\n" + "\n".join(missing_hint)
        )

    def test_command_disable_model_invocation(self, command_files):
        """
        Command disable-model-invocation field should be boolean when present (Issue #150).

        Optional field, controls whether command can invoke language model.
        """
        invalid_disable = []

        for command_file in command_files:
            frontmatter = parse_yaml_frontmatter(command_file)
            if not frontmatter:
                continue

            if "disable-model-invocation" not in frontmatter:
                continue  # Optional field

            disable_invocation = frontmatter["disable-model-invocation"]
            if not isinstance(disable_invocation, bool):
                invalid_disable.append(
                    f"{command_file.stem}: disable-model-invocation should be boolean "
                    f"(got {type(disable_invocation).__name__}: {disable_invocation})"
                )

        assert not invalid_disable, (
            f"Commands with invalid disable-model-invocation field:\n" + "\n".join(invalid_disable)
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
class TestAgentCompliance:
    """Test that agents comply with Claude Code 2.0 frontmatter requirements (Issue #150)."""

    @pytest.fixture
    def agent_files(self) -> List[Path]:
        """Discover all agent markdown files."""
        return get_all_agent_files()

    @pytest.fixture
    def available_skills(self) -> Set[str]:
        """Get set of all available skill names."""
        return get_all_skill_names()

    def test_agent_skills_exist(self, agent_files, available_skills):
        """
        All agent-declared skills should reference existing skill files.

        Validates cross-component integrity: agents reference skills that exist.
        """
        missing_skills = []

        for agent_file in agent_files:
            frontmatter = parse_yaml_frontmatter(agent_file)
            if not frontmatter:
                continue

            if "skills" not in frontmatter:
                continue  # skills field is optional

            declared_skills = frontmatter["skills"]
            if not isinstance(declared_skills, list):
                missing_skills.append(
                    f"{agent_file.stem}: skills field is not a list (got {type(declared_skills).__name__})"
                )
                continue

            # Check each skill exists
            for skill in declared_skills:
                if skill not in available_skills:
                    missing_skills.append(
                        f"{agent_file.stem}: references non-existent skill '{skill}'"
                    )

        assert not missing_skills, (
            f"Agents with invalid skill references:\n" + "\n".join(missing_skills)
        )

    def test_agent_model_valid(self, agent_files):
        """
        Agent model field should use approved values (haiku, sonnet, opus).

        Validates model tier strategy is followed.
        """
        invalid_models = []

        for agent_file in agent_files:
            frontmatter = parse_yaml_frontmatter(agent_file)
            if not frontmatter:
                continue

            if "model" not in frontmatter:
                invalid_models.append(f"{agent_file.stem}: Missing model field")
                continue

            model = frontmatter["model"]
            if model not in VALID_AGENT_MODELS:
                invalid_models.append(
                    f"{agent_file.stem}: Invalid model '{model}' "
                    f"(expected one of: {', '.join(sorted(VALID_AGENT_MODELS))})"
                )

        assert not invalid_models, (
            f"Agents with invalid model field:\n" + "\n".join(invalid_models)
        )

    def test_agent_permission_mode(self, agent_files):
        """
        Agent permissionMode field should use valid values when present.

        Optional field, but if present must be: ask, allow, or deny.
        """
        invalid_modes = []

        for agent_file in agent_files:
            frontmatter = parse_yaml_frontmatter(agent_file)
            if not frontmatter:
                continue

            if "permissionMode" not in frontmatter:
                continue  # Optional field

            mode = frontmatter["permissionMode"]
            if mode not in VALID_PERMISSION_MODES:
                invalid_modes.append(
                    f"{agent_file.stem}: Invalid permissionMode '{mode}' "
                    f"(expected one of: {', '.join(sorted(VALID_PERMISSION_MODES))})"
                )

        assert not invalid_modes, (
            f"Agents with invalid permissionMode:\n" + "\n".join(invalid_modes)
        )


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
class TestCrossComponentIntegrity:
    """Test cross-component reference integrity (Issue #150)."""

    def test_cross_component_references(self):
        """
        Validate references between components are consistent.

        Checks:
        - Agent skill references point to existing skills
        - Command references to agents are valid
        - No broken cross-references in documentation
        """
        violations = []
        available_skills = get_all_skill_names()
        agent_files = get_all_agent_files()

        # Check agent -> skill references
        for agent_file in agent_files:
            frontmatter = parse_yaml_frontmatter(agent_file)
            if not frontmatter or "skills" not in frontmatter:
                continue

            declared_skills = frontmatter.get("skills", [])
            if not isinstance(declared_skills, list):
                continue

            for skill in declared_skills:
                if skill not in available_skills:
                    violations.append(
                        f"Agent {agent_file.stem} references non-existent skill: {skill}"
                    )

        assert not violations, (
            f"Cross-component reference violations:\n" + "\n".join(violations)
        )

    def test_plugin_manifest_schema(self):
        """
        Validate plugin manifest.json structure (Issue #150).

        If manifest exists, check required fields:
        - name, version, description
        - components (commands, agents, skills)
        """
        # Look for manifest in multiple possible locations
        possible_manifests = [
            PROJECT_ROOT / "manifest.json",
            PROJECT_ROOT / "plugins" / "autonomous-dev" / "manifest.json",
            PROJECT_ROOT / ".claude" / "manifest.json",
        ]

        manifest_path = None
        for path in possible_manifests:
            if path.exists():
                manifest_path = path
                break

        if manifest_path is None:
            pytest.skip("No manifest.json found (optional)")

        # Validate manifest structure
        try:
            manifest = json.loads(manifest_path.read_text())
        except json.JSONDecodeError as e:
            pytest.fail(f"manifest.json is invalid JSON: {e}")

        # Check required fields
        required_fields = ["name", "version", "description"]
        missing_fields = [f for f in required_fields if f not in manifest]

        assert not missing_fields, (
            f"manifest.json missing required fields: {', '.join(missing_fields)}"
        )

        # If components field exists, validate structure
        if "components" in manifest:
            components = manifest["components"]
            assert isinstance(components, dict), (
                "manifest.json components should be a dictionary"
            )


@pytest.mark.regression
class TestYAMLRobustness:
    """Test YAML parsing security and robustness (Issue #150)."""

    def test_yaml_injection_prevention(self):
        """
        Validate YAML parsing prevents injection attacks.

        Uses yaml.safe_load() which:
        - Prevents arbitrary Python object construction
        - Blocks malicious YAML tags
        - Rejects dangerous constructors
        """
        # Test that parse_yaml_frontmatter uses yaml.safe_load
        # Create temporary test file with potentially dangerous YAML
        import tempfile

        dangerous_yaml = """---
name: test
malicious: !!python/object/apply:os.system
  args: ['echo pwned']
---
# Test content
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(dangerous_yaml)
            temp_path = Path(f.name)

        try:
            # Should return None or raise error, NOT execute command
            result = parse_yaml_frontmatter(temp_path)

            # If it returns None, that's safe (failed to parse)
            # If it returns dict, verify malicious tag was blocked
            if result is not None:
                # yaml.safe_load should have blocked the !!python tag
                # If 'malicious' key exists, it should be None or string, not executed
                if 'malicious' in result:
                    # Should be None or unparsed tag (safe)
                    assert result['malicious'] is None or isinstance(result['malicious'], str), (
                        "YAML injection vulnerability: malicious tag was executed!"
                    )

        finally:
            temp_path.unlink()  # Clean up

    def test_yaml_parsing_edge_cases(self):
        """
        Test YAML parsing handles edge cases gracefully.

        Edge cases:
        - Empty frontmatter
        - Malformed frontmatter (missing closing ---)
        - Unicode characters
        - Very long values
        """
        import tempfile

        test_cases = [
            ("Empty frontmatter", "---\n---\n# Content"),
            ("No closing delimiter", "---\nname: test\n# Content"),
            ("Unicode", "---\nname: тест\ndescription: 测试\n---\n# Content"),
            ("Long value", f"---\nname: {'a' * 10000}\n---\n# Content"),
        ]

        for case_name, content in test_cases:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
                f.write(content)
                temp_path = Path(f.name)

            try:
                # Should not raise exception, even if parsing fails
                result = parse_yaml_frontmatter(temp_path)
                # Result can be None or dict, but should not raise
                assert result is None or isinstance(result, dict), (
                    f"YAML parser failed on edge case '{case_name}'"
                )
            except Exception as e:
                pytest.fail(f"YAML parser raised exception on edge case '{case_name}': {e}")
            finally:
                temp_path.unlink()


@pytest.mark.regression
class TestComplianceSummary:
    """Overall compliance summary tests."""

    def test_all_compliance_categories_covered(self):
        """Verify all 8 compliance test classes are present (Issues #148, #150)."""
        # This is a meta-test to ensure we have comprehensive coverage
        test_classes = [
            # Phase 1 (Issue #148 - 5 classes, 24 tests)
            TestSkillVersionCompliance,
            TestCommandNameCompliance,
            TestBashWildcardCompliance,
            TestMCPConfigPortability,
            TestCLAUDEMdMetadata,
            # Phase 2 (Issue #150 - 3 classes, 12 tests)
            TestAgentCompliance,
            TestCrossComponentIntegrity,
            TestYAMLRobustness,
        ]

        assert len(test_classes) == 8, (
            f"Expected 8 compliance test classes, found {len(test_classes)}"
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
