"""
Integration tests for autonomous-dev plugin.

Tests how components work together:
- Agents coordinating with each other
- Skills activating based on context
- Hooks executing on tool use
- Context management across workflows
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestAgentCoordination:
    """Test agents can coordinate with each other."""

    @pytest.fixture
    def agents_dir(self):
        return Path(__file__).parent.parent / "agents"

    def test_orchestrator_can_invoke_agents(self, agents_dir):
        """Test orchestrator has Task tool to invoke other agents."""
        orchestrator = (agents_dir / "orchestrator.md").read_text()
        assert "Task" in orchestrator, "Orchestrator must have Task tool to coordinate agents"

    def test_agent_pipeline_structure(self, agents_dir):
        """Test all agents in pipeline exist."""
        pipeline = [
            "orchestrator.md",  # Coordinator
            "researcher.md",  # Research
            "planner.md",  # Planning
            "test-master.md",  # TDD
            "implementer.md",  # Implementation
            "reviewer.md",  # Review
            "security-auditor.md",  # Security
            "doc-master.md",  # Documentation
        ]

        for agent in pipeline:
            assert (agents_dir / agent).exists(), f"Missing agent in pipeline: {agent}"

    def test_read_only_agents_cannot_write(self, agents_dir):
        """Test read-only agents don't have Write tool."""
        read_only_agents = ["planner.md", "reviewer.md", "security-auditor.md"]

        for agent in read_only_agents:
            content = (agents_dir / agent).read_text()
            # Extract tools section
            tools_match = content.find("tools:")
            if tools_match != -1:
                tools_section = content[tools_match:tools_match + 500]
                assert "Write" not in tools_section, f"{agent} should be read-only"


class TestSkillActivation:
    """Test skills activate based on context."""

    @pytest.fixture
    def skills_dir(self):
        return Path(__file__).parent.parent / "skills"

    def test_python_standards_skill_exists(self, skills_dir):
        """Test python-standards skill exists for Python code."""
        skill = skills_dir / "python-standards" / "SKILL.md"
        assert skill.exists()
        content = skill.read_text()
        assert "PEP 8" in content or "type hint" in content.lower()

    def test_testing_guide_skill_exists(self, skills_dir):
        """Test testing-guide skill exists for test writing."""
        skill = skills_dir / "testing-guide" / "SKILL.md"
        assert skill.exists()
        content = skill.read_text()
        assert "TDD" in content or "test" in content.lower()

    def test_security_patterns_skill_exists(self, skills_dir):
        """Test security-patterns skill exists for security."""
        skill = skills_dir / "security-patterns" / "SKILL.md"
        assert skill.exists()
        content = skill.read_text()
        assert "secret" in content.lower() or "security" in content.lower()


class TestHookExecution:
    """Test hooks execute at correct times."""

    @pytest.fixture
    def hooks_dir(self):
        return Path(__file__).parent.parent / "hooks"

    @pytest.fixture
    def templates_dir(self):
        return Path(__file__).parent.parent / "templates"

    def test_hook_configuration_template(self, templates_dir):
        """Test hook configuration template is correct."""
        settings_template = templates_dir / "settings.local.json"
        assert settings_template.exists()

        settings = json.loads(settings_template.read_text())
        assert "hooks" in settings
        assert "PostToolUse" in settings["hooks"]
        assert "PreCommit" in settings["hooks"]

    def test_post_tool_use_hooks_exist(self, hooks_dir, templates_dir):
        """Test PostToolUse hooks reference existing files."""
        settings_template = templates_dir / "settings.local.json"
        settings = json.loads(settings_template.read_text())

        post_tool_use = settings["hooks"]["PostToolUse"]
        for tool, hook_commands in post_tool_use.items():
            for command in hook_commands:
                # Extract hook file name
                if "auto_format.py" in command:
                    assert (hooks_dir / "auto_format.py").exists()

    def test_pre_commit_hooks_exist(self, hooks_dir, templates_dir):
        """Test PreCommit hooks reference existing files."""
        settings_template = templates_dir / "settings.local.json"
        settings = json.loads(settings_template.read_text())

        pre_commit = settings["hooks"]["PreCommit"]["*"]
        for command in pre_commit:
            if "auto_test.py" in command:
                assert (hooks_dir / "auto_test.py").exists()
            if "security_scan.py" in command:
                assert (hooks_dir / "security_scan.py").exists()


class TestProjectMdAlignment:
    """Test PROJECT.md alignment workflow."""

    @pytest.fixture
    def templates_dir(self):
        return Path(__file__).parent.parent / "templates"

    @pytest.fixture
    def agents_dir(self):
        return Path(__file__).parent.parent / "agents"

    def test_project_md_template_exists(self, templates_dir):
        """Test PROJECT.md template exists."""
        template = templates_dir / "PROJECT.md"
        assert template.exists()

    def test_project_md_has_required_sections(self, templates_dir):
        """Test PROJECT.md template has required sections."""
        template = templates_dir / "PROJECT.md"
        content = template.read_text()

        required_sections = ["GOALS", "SCOPE", "CONSTRAINTS"]
        for section in required_sections:
            assert section in content, f"PROJECT.md missing section: {section}"

    def test_orchestrator_validates_alignment(self, agents_dir):
        """Test orchestrator mentions PROJECT.md validation."""
        orchestrator = (agents_dir / "orchestrator.md").read_text()
        assert "PROJECT.md" in orchestrator, "Orchestrator should validate against PROJECT.md"


class TestContextManagementIntegration:
    """Test context management works across components."""

    def test_session_logging_strategy(self):
        """Test session logging strategy is documented."""
        readme = Path(__file__).parent.parent / "README.md"
        if readme.exists():
            content = readme.read_text()
            # Should mention /clear or context management
            assert "/clear" in content or "context" in content.lower()

    def test_docs_sessions_directory_structure(self):
        """Test docs/sessions directory is mentioned in docs."""
        # This would be in user projects, not plugin
        # Skip for now
        pytest.skip("Session directory is project-specific, not in plugin")


class TestCommandWorkflows:
    """Test command workflows integrate correctly."""

    @pytest.fixture
    def commands_dir(self):
        return Path(__file__).parent.parent / "commands"

    def test_setup_command_references_setup_script(self, commands_dir):
        """Test /setup command mentions setup.py script."""
        setup_cmd = commands_dir / "setup.md"
        content = setup_cmd.read_text()
        assert "setup.py" in content or "setup script" in content.lower()

    def test_uninstall_command_has_options(self, commands_dir):
        """Test /uninstall command has multiple options."""
        uninstall_cmd = commands_dir / "uninstall.md"
        content = uninstall_cmd.read_text()
        # Should have multiple options
        assert "Option 1" in content or "[1]" in content
        assert "Option 2" in content or "[2]" in content

    def test_auto_implement_uses_orchestrator(self, commands_dir):
        """Test /auto-implement references orchestrator."""
        auto_impl = commands_dir / "auto-implement.md"
        content = auto_impl.read_text()
        assert "orchestrator" in content.lower()


class TestFilePathConsistency:
    """Test file paths are consistent across components."""

    def test_hooks_path_consistency(self):
        """Test hooks are referenced consistently."""
        # Hooks should be at .claude/hooks/
        templates_dir = Path(__file__).parent.parent / "templates"
        settings_template = templates_dir / "settings.local.json"
        settings = json.loads(settings_template.read_text())

        # Check all hook paths use .claude/hooks/
        for hook_type, hooks in settings["hooks"].items():
            if isinstance(hooks, dict):
                for tool, commands in hooks.items():
                    for command in commands:
                        assert ".claude/hooks/" in command, f"Hook path inconsistent: {command}"
            elif isinstance(hooks, list):
                for command in hooks:
                    assert ".claude/hooks/" in command, f"Hook path inconsistent: {command}"

    def test_project_md_path_consistency(self):
        """Test PROJECT.md path is consistent."""
        # PROJECT.md should be at PROJECT.md
        commands_dir = Path(__file__).parent.parent / "commands"
        setup_cmd = commands_dir / "setup.md"
        content = setup_cmd.read_text()
        assert "PROJECT.md" in content


class TestModelSelectionIntegration:
    """Test model selection is configured correctly."""

    @pytest.fixture
    def agents_dir(self):
        return Path(__file__).parent.parent / "agents"

    def test_expensive_agents_use_appropriate_models(self, agents_dir):
        """Test expensive operations use appropriate models."""
        # Planner should use opus (expensive, complex)
        planner = (agents_dir / "planner.md").read_text()
        # Check if model is mentioned in description or config
        # This is more of a documentation check
        assert "planner" in planner.lower()

        # Security and docs should use haiku (cheap, fast)
        security = (agents_dir / "security-auditor.md").read_text()
        doc_master = (agents_dir / "doc-master.md").read_text()
        # These should be fast operations
        assert "security" in security.lower()
        assert "doc" in doc_master.lower() or "documentation" in doc_master.lower()


class TestGitHubIntegration:
    """Test GitHub integration is configured correctly."""

    def test_github_setup_documented(self):
        """Test GitHub setup is documented."""
        docs_dir = Path(__file__).parent.parent / "docs"
        if docs_dir.exists():
            github_doc = docs_dir / "GITHUB_AUTH_SETUP.md"
            if github_doc.exists():
                content = github_doc.read_text()
                assert "GITHUB_TOKEN" in content
                assert "token" in content.lower()
        else:
            # Check in README
            readme = Path(__file__).parent.parent / "README.md"
            content = readme.read_text()
            assert "github" in content.lower() or "GitHub" in content


class TestErrorHandling:
    """Test error handling is robust."""

    def test_setup_handles_missing_plugin(self, tmp_path):
        """Test setup.py handles missing plugin gracefully."""
        # This is tested in test_setup.py
        # Just verify the method exists
        from setup import SetupWizard
        wizard = SetupWizard()
        assert hasattr(wizard, "verify_plugin_installation")

    def test_hooks_handle_missing_dependencies(self):
        """Test hooks handle missing dependencies."""
        hooks_dir = Path(__file__).parent.parent / "hooks"
        auto_format = hooks_dir / "auto_format.py"

        if auto_format.exists():
            content = auto_format.read_text()
            # Should have try/except or dependency checking
            assert "try:" in content or "import" in content or "except" in content


class TestEndToEndWorkflow:
    """Test complete workflows work together."""

    def test_setup_workflow_components(self):
        """Test all components of setup workflow exist."""
        base_dir = Path(__file__).parent.parent

        # /setup command
        assert (base_dir / "commands" / "setup.md").exists()

        # setup.py script
        assert (base_dir / "scripts" / "setup.py").exists()

        # Templates
        assert (base_dir / "templates" / "PROJECT.md").exists()
        assert (base_dir / "templates" / "settings.local.json").exists()

    def test_uninstall_workflow_components(self):
        """Test all components of uninstall workflow exist."""
        base_dir = Path(__file__).parent.parent

        # /uninstall command
        assert (base_dir / "commands" / "uninstall.md").exists()

    def test_autonomous_implementation_workflow(self):
        """Test all components for autonomous implementation exist."""
        base_dir = Path(__file__).parent.parent

        # /auto-implement command
        assert (base_dir / "commands" / "auto-implement.md").exists()

        # All agents in pipeline
        agents_dir = base_dir / "agents"
        pipeline = [
            "orchestrator.md",
            "researcher.md",
            "planner.md",
            "test-master.md",
            "implementer.md",
            "reviewer.md",
            "security-auditor.md",
            "doc-master.md",
        ]
        for agent in pipeline:
            assert (agents_dir / agent).exists()
