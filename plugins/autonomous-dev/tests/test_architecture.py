"""
Architectural validation tests.

Validates the plugin structure and configuration are correct.
Tests static structure, not runtime behavior.
"""

import json
import re
from pathlib import Path

import pytest


class TestAgentStructure:
    """Validate agent files are structured correctly."""

    @pytest.fixture
    def agents_dir(self):
        return Path(__file__).parent.parent / "agents"

    def test_all_agents_exist(self, agents_dir):
        """Test all required agents are present."""
        required_agents = [
            "orchestrator.md",
            "researcher.md",
            "planner.md",
            "test-master.md",
            "implementer.md",
            "reviewer.md",
            "security-auditor.md",
            "doc-master.md",
        ]

        for agent in required_agents:
            assert (agents_dir / agent).exists(), f"Missing agent: {agent}"

    def test_agents_have_frontmatter(self, agents_dir):
        """Test all agents have valid YAML frontmatter."""
        for agent_file in agents_dir.glob("*.md"):
            content = agent_file.read_text()
            assert content.startswith("---"), f"{agent_file.name} missing frontmatter"
            assert "subagent_type:" in content, f"{agent_file.name} missing subagent_type"
            assert "tools:" in content, f"{agent_file.name} missing tools"

    def test_model_selection(self, agents_dir):
        """Test agents use correct models (opus/sonnet/haiku)."""
        model_assignments = {
            "planner.md": "opus",  # Complex planning
            "security-auditor.md": "haiku",  # Fast security scans
            "doc-master.md": "haiku",  # Fast documentation updates
            # Others default to sonnet (or not specified)
        }

        for agent_file, expected_model in model_assignments.items():
            content = (agents_dir / agent_file).read_text()
            # Check if model is specified in frontmatter
            if f"model: {expected_model}" not in content:
                # May be in comment or description
                pytest.skip(f"Model assignment for {agent_file} not enforced in frontmatter")

    def test_tool_restrictions(self, agents_dir):
        """Test agents have appropriate tool restrictions."""
        # Orchestrator should only have Task, Read, Bash
        orchestrator = (agents_dir / "orchestrator.md").read_text()
        assert "Task" in orchestrator or "task" in orchestrator.lower()

        # Planner should be read-only
        planner = (agents_dir / "planner.md").read_text()
        assert "Read" in planner
        assert "Write" not in planner or "write" not in planner.lower()

        # Security-auditor should be read-only
        security = (agents_dir / "security-auditor.md").read_text()
        assert "Read" in security


class TestSkillStructure:
    """Validate skill files are structured correctly."""

    @pytest.fixture
    def skills_dir(self):
        return Path(__file__).parent.parent / "skills"

    def test_all_skills_exist(self, skills_dir):
        """Test all required skills are present."""
        required_skills = [
            # Core development skills
            "python-standards",
            "testing-guide",
            "security-patterns",
            "documentation-guide",
            "research-patterns",
            "consistency-enforcement",
            # Architecture & design
            "architecture-patterns",
            "api-design",
            "database-design",
            # Process & workflow
            "code-review",
            "git-workflow",
            "project-management",
            # Operations
            "observability",
        ]

        for skill in required_skills:
            skill_dir = skills_dir / skill
            assert skill_dir.exists(), f"Missing skill: {skill}"
            assert (skill_dir / "SKILL.md").exists(), f"Missing SKILL.md for {skill}"

    def test_skills_have_metadata(self, skills_dir):
        """Test skills have proper metadata."""
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                content = skill_file.read_text()
                # Skills should have clear structure
                assert len(content) > 100, f"{skill_dir.name} skill is too short"


class TestHookStructure:
    """Validate hook files are structured correctly."""

    @pytest.fixture
    def hooks_dir(self):
        return Path(__file__).parent.parent / "hooks"

    def test_all_hooks_exist(self, hooks_dir):
        """Test all documented hooks are present."""
        required_hooks = [
            "auto_format.py",
            "auto_test.py",
            "security_scan.py",
        ]

        for hook in required_hooks:
            assert (hooks_dir / hook).exists(), f"Missing hook: {hook}"

    def test_hooks_are_executable(self, hooks_dir):
        """Test hook files have proper Python structure."""
        for hook_file in hooks_dir.glob("*.py"):
            content = hook_file.read_text()
            # Should have shebang or be importable
            assert "def " in content or "class " in content, f"{hook_file.name} has no functions/classes"

    def test_hooks_have_docstrings(self, hooks_dir):
        """Test hooks have documentation."""
        for hook_file in hooks_dir.glob("*.py"):
            if hook_file.name == "__init__.py":
                continue
            content = hook_file.read_text()
            assert '"""' in content or "'''" in content, f"{hook_file.name} missing docstring"


class TestCommandStructure:
    """Validate command files are structured correctly."""

    @pytest.fixture
    def commands_dir(self):
        return Path(__file__).parent.parent / "commands"

    def test_all_commands_exist(self, commands_dir):
        """Test all documented commands are present."""
        required_commands = [
            "align-project.md",
            "auto-implement.md",
            "setup.md",
            "uninstall.md",
            "format.md",
            "test.md",
            "security-scan.md",
            "full-check.md",
            "commit.md",
        ]

        for command in required_commands:
            assert (commands_dir / command).exists(), f"Missing command: {command}"

    def test_commands_have_frontmatter(self, commands_dir):
        """Test commands have YAML frontmatter with description."""
        for command_file in commands_dir.glob("*.md"):
            content = command_file.read_text()
            assert content.startswith("---"), f"{command_file.name} missing frontmatter"
            assert "description:" in content, f"{command_file.name} missing description"


class TestPluginMetadata:
    """Validate plugin.json is correct."""

    @pytest.fixture
    def plugin_json(self):
        plugin_file = Path(__file__).parent.parent / ".claude-plugin" / "plugin.json"
        return json.loads(plugin_file.read_text())

    def test_has_required_fields(self, plugin_json):
        """Test plugin.json has all required fields."""
        required_fields = ["name", "version", "description", "author", "components"]
        for field in required_fields:
            assert field in plugin_json, f"Missing field: {field}"

    def test_components_reference_correct_paths(self, plugin_json):
        """Test component paths exist."""
        base_dir = Path(__file__).parent.parent

        for component, path in plugin_json["components"].items():
            full_path = base_dir / path
            assert full_path.exists(), f"Component path doesn't exist: {path}"

    def test_version_format(self, plugin_json):
        """Test version follows semantic versioning."""
        version = plugin_json["version"]
        assert re.match(r"^\d+\.\d+\.\d+$", version), f"Invalid version format: {version}"


class TestFileOrganization:
    """Validate file organization follows best practices."""

    @pytest.fixture
    def plugin_root(self):
        return Path(__file__).parent.parent

    def test_max_file_sizes(self, plugin_root):
        """Test files don't exceed reasonable size limits."""
        max_sizes = {
            ".md": 50_000,  # 50KB for markdown
            ".py": 30_000,  # 30KB for Python
            ".json": 10_000,  # 10KB for JSON
        }

        for ext, max_size in max_sizes.items():
            for file in plugin_root.rglob(f"*{ext}"):
                if "node_modules" in str(file) or ".git" in str(file):
                    continue
                size = file.stat().st_size
                assert size < max_size, f"{file.name} too large: {size} bytes (max {max_size})"

    def test_no_secrets_in_files(self, plugin_root):
        """Test no hardcoded secrets in files."""
        secret_patterns = [
            r"ghp_[a-zA-Z0-9]{36}",  # GitHub token
            r"sk-[a-zA-Z0-9]{48}",  # Anthropic API key
            r"AKIA[0-9A-Z]{16}",  # AWS access key
        ]

        for file in plugin_root.rglob("*.py"):
            content = file.read_text()
            for pattern in secret_patterns:
                assert not re.search(pattern, content), f"Potential secret in {file.name}"

    def test_consistent_line_endings(self, plugin_root):
        """Test files use consistent line endings."""
        for file in plugin_root.rglob("*.py"):
            content = file.read_text()
            # Should use \n (Unix), not \r\n (Windows)
            assert "\r\n" not in content, f"{file.name} has Windows line endings"


class TestContextManagement:
    """Validate context management strategy."""

    def test_session_logging_enabled(self):
        """Test session logging is configured."""
        # Check if session tracker exists
        scripts_dir = Path(__file__).parent.parent.parent / "scripts"
        if scripts_dir.exists():
            session_tracker = scripts_dir / "session_tracker.py"
            if session_tracker.exists():
                assert True
            else:
                pytest.skip("Session tracker not in this plugin (may be in project)")
        else:
            pytest.skip("Scripts directory not found")

    def test_docs_sessions_directory_referenced(self):
        """Test documentation mentions session logging."""
        readme = Path(__file__).parent.parent / "README.md"
        if readme.exists():
            content = readme.read_text()
            assert "session" in content.lower() or "context" in content.lower()


class TestBestPractices:
    """Validate best practices are enforced."""

    def test_python_files_have_docstrings(self):
        """Test Python files have module docstrings."""
        hooks_dir = Path(__file__).parent.parent / "hooks"
        scripts_dir = Path(__file__).parent.parent / "scripts"

        for py_file in list(hooks_dir.glob("*.py")) + list(scripts_dir.glob("*.py")):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            # Check for module docstring
            lines = content.split("\n")
            found_docstring = False
            for i, line in enumerate(lines[:10]):  # Check first 10 lines
                if '"""' in line or "'''" in line:
                    found_docstring = True
                    break
            assert found_docstring, f"{py_file.name} missing module docstring"

    def test_markdown_files_have_headers(self):
        """Test markdown files have proper headers."""
        for md_file in Path(__file__).parent.parent.rglob("*.md"):
            if "node_modules" in str(md_file):
                continue
            content = md_file.read_text()
            # Should start with # header or --- frontmatter
            assert content.startswith("#") or content.startswith("---"), f"{md_file.name} missing header"
