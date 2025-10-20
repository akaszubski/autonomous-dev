"""
User Acceptance Tests (UAT) for autonomous-dev plugin.

Simulates real user workflows end-to-end:
- Plugin installation → setup → feature implementation
- /auto-implement workflow
- Hook execution workflow
- Context management workflow

These tests validate the COMPLETE user experience.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestPluginInstallation:
    """Test plugin installation workflow."""

    def test_plugin_structure_after_install(self):
        """Test plugin has correct structure after installation."""
        plugin_root = Path(__file__).parent.parent

        required_structure = {
            "agents": [
                "orchestrator.md",
                "researcher.md",
                "planner.md",
                "test-master.md",
                "implementer.md",
                "reviewer.md",
                "security-auditor.md",
                "doc-master.md",
            ],
            "skills": [
                "python-standards",
                "testing-guide",
                "security-patterns",
                "documentation-guide",
                "research-patterns",
                "engineering-standards",
            ],
            "commands": [
                "setup.md",
                "uninstall.md",
                "auto-implement.md",
                "align-project.md",
                "format.md",
                "test.md",
                "security-scan.md",
                "full-check.md",
                "commit.md",
            ],
            "hooks": [
                "auto_format.py",
                "auto_test.py",
                "security_scan.py",
            ],
            "templates": [
                "PROJECT.md",
                "settings.local.json",
            ],
        }

        for directory, files in required_structure.items():
            dir_path = plugin_root / directory
            assert dir_path.exists(), f"Missing directory: {directory}"

            for file in files:
                file_path = dir_path / file
                if dir_path.name == "skills":
                    file_path = dir_path / file / "SKILL.md"
                assert file_path.exists(), f"Missing file: {directory}/{file}"


class TestSetupWorkflow:
    """Test /setup command workflow."""

    def test_setup_creates_required_files(self, tmp_path, monkeypatch):
        """Test setup creates all required files in project."""
        monkeypatch.chdir(tmp_path)

        # Simulate plugin installation
        plugin_dir = tmp_path / ".claude" / "plugins" / "autonomous-dev"
        plugin_hooks = plugin_dir / "hooks"
        plugin_hooks.mkdir(parents=True)
        (plugin_hooks / "auto_format.py").write_text("# hook")
        (plugin_hooks / "auto_test.py").write_text("# hook")

        plugin_templates = plugin_dir / "templates"
        plugin_templates.mkdir(parents=True)
        (plugin_templates / "PROJECT.md").write_text("# Template")
        (plugin_templates / "settings.local.json").write_text('{"hooks":{}}')

        # Run setup with team preset
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from setup import SetupWizard

        wizard = SetupWizard(auto=True, preset="team")
        wizard.run()

        # Verify files created
        assert (tmp_path / ".claude" / "hooks" / "auto_format.py").exists()
        assert (tmp_path / ".claude" / "templates" / "PROJECT.md").exists()
        assert (tmp_path / ".claude" / "PROJECT.md").exists()
        assert (tmp_path / ".claude" / "settings.local.json").exists()
        assert (tmp_path / ".env").exists()
        assert (tmp_path / ".gitignore").exists()


class TestAutoImplementWorkflow:
    """Test /auto-implement workflow end-to-end."""

    def test_auto_implement_command_exists(self):
        """Test /auto-implement command is available."""
        commands_dir = Path(__file__).parent.parent / "commands"
        auto_impl = commands_dir / "auto-implement.md"
        assert auto_impl.exists()

    def test_auto_implement_mentions_agent_pipeline(self):
        """Test /auto-implement documents the agent pipeline."""
        commands_dir = Path(__file__).parent.parent / "commands"
        auto_impl = commands_dir / "auto-implement.md"
        content = auto_impl.read_text()

        # Should mention key agents
        assert "orchestrator" in content.lower()
        assert "researcher" in content.lower() or "research" in content.lower()
        assert "planner" in content.lower() or "plan" in content.lower()
        assert "test" in content.lower()
        assert "implement" in content.lower()

    def test_auto_implement_mentions_project_md(self):
        """Test /auto-implement mentions PROJECT.md validation."""
        commands_dir = Path(__file__).parent.parent / "commands"
        auto_impl = commands_dir / "auto-implement.md"
        content = auto_impl.read_text()

        assert "PROJECT.md" in content or "alignment" in content.lower()


class TestHookExecutionWorkflow:
    """Test hook execution workflow."""

    def test_slash_commands_workflow(self):
        """Test slash commands workflow (manual mode)."""
        commands_dir = Path(__file__).parent.parent / "commands"

        # Should have all manual commands
        assert (commands_dir / "format.md").exists()
        assert (commands_dir / "test.md").exists()
        assert (commands_dir / "security-scan.md").exists()
        assert (commands_dir / "full-check.md").exists()

    def test_automatic_hooks_workflow(self, tmp_path):
        """Test automatic hooks workflow configuration."""
        templates_dir = Path(__file__).parent.parent / "templates"
        settings_template = templates_dir / "settings.local.json"

        settings = json.loads(settings_template.read_text())

        # Should configure PostToolUse hooks
        assert "PostToolUse" in settings["hooks"]
        assert "Write" in settings["hooks"]["PostToolUse"]
        assert "Edit" in settings["hooks"]["PostToolUse"]

        # Should configure PreCommit hooks
        assert "PreCommit" in settings["hooks"]
        assert "*" in settings["hooks"]["PreCommit"]


class TestContextManagementWorkflow:
    """Test context management workflow."""

    def test_clear_context_documented(self):
        """Test /clear is documented in user workflows."""
        readme = Path(__file__).parent.parent / "README.md"
        quickstart = Path(__file__).parent.parent / "QUICKSTART.md"

        # Should mention /clear in at least one doc
        readme_content = readme.read_text() if readme.exists() else ""
        quickstart_content = quickstart.read_text() if quickstart.exists() else ""

        combined = readme_content + quickstart_content
        assert "/clear" in combined, "Context management (/clear) not documented"

    def test_session_logging_strategy_documented(self):
        """Test session logging strategy is documented."""
        readme = Path(__file__).parent.parent / "README.md"
        if readme.exists():
            content = readme.read_text()
            assert "session" in content.lower() or "context" in content.lower()


class TestAlignProjectWorkflow:
    """Test /align-project workflow."""

    def test_align_project_command_exists(self):
        """Test /align-project command exists."""
        commands_dir = Path(__file__).parent.parent / "commands"
        assert (commands_dir / "align-project.md").exists()

    def test_align_project_validates_structure(self):
        """Test /align-project validates project structure."""
        commands_dir = Path(__file__).parent.parent / "commands"
        align_cmd = commands_dir / "align-project.md"
        content = align_cmd.read_text()

        # Should validate against PROJECT.md
        assert "PROJECT.md" in content

        # Should check project structure
        assert "align" in content.lower() or "validate" in content.lower()


class TestUninstallWorkflow:
    """Test /uninstall workflow."""

    def test_uninstall_has_multiple_options(self):
        """Test /uninstall provides granular removal options."""
        commands_dir = Path(__file__).parent.parent / "commands"
        uninstall_cmd = commands_dir / "uninstall.md"
        content = uninstall_cmd.read_text()

        # Should have project-level and global options
        assert "project" in content.lower()
        assert "PROJECT.md" in content

        # Should distinguish between local and global removal
        assert "Option" in content or "[" in content

    def test_uninstall_preserves_project_md_option(self):
        """Test /uninstall has option to keep PROJECT.md."""
        commands_dir = Path(__file__).parent.parent / "commands"
        uninstall_cmd = commands_dir / "uninstall.md"
        content = uninstall_cmd.read_text()

        # Should have option to keep PROJECT.md
        assert "keep PROJECT.md" in content or "Keep PROJECT.md" in content


class TestFullUserJourney:
    """Test complete user journey from install to feature implementation."""

    def test_user_journey_happy_path(self, tmp_path, monkeypatch):
        """Test complete happy path user journey."""
        monkeypatch.chdir(tmp_path)

        # Step 1: Plugin installed (simulated)
        plugin_dir = tmp_path / ".claude" / "plugins" / "autonomous-dev"
        plugin_hooks = plugin_dir / "hooks"
        plugin_hooks.mkdir(parents=True)
        (plugin_hooks / "auto_format.py").write_text("# hook")

        plugin_templates = plugin_dir / "templates"
        plugin_templates.mkdir(parents=True)
        (plugin_templates / "PROJECT.md").write_text("""
# Project Goals

## GOALS
- Build a REST API
- 80%+ test coverage

## SCOPE
IN: CRUD operations
OUT: Admin UI

## CONSTRAINTS
- Python 3.11+
- < 100ms response time
        """)
        (plugin_templates / "settings.local.json").write_text('{"hooks":{}}')

        # Step 2: Run /setup
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from setup import SetupWizard

        wizard = SetupWizard(auto=True, preset="solo")
        wizard.run()

        # Verify setup completed
        assert (tmp_path / ".claude" / "hooks").exists()
        assert (tmp_path / ".claude" / "PROJECT.md").exists()

        # Step 3: Verify PROJECT.md has content
        project_md = tmp_path / ".claude" / "PROJECT.md"
        content = project_md.read_text()
        assert "GOALS" in content
        assert "SCOPE" in content
        assert "CONSTRAINTS" in content

        # Step 4: Verify commands are available (check docs)
        commands_dir = Path(__file__).parent.parent / "commands"
        assert (commands_dir / "auto-implement.md").exists()
        assert (commands_dir / "format.md").exists()
        assert (commands_dir / "test.md").exists()

        # Step 5: Verify /clear is documented
        readme = Path(__file__).parent.parent / "README.md"
        if readme.exists():
            readme_content = readme.read_text()
            assert "/clear" in readme_content


class TestErrorRecovery:
    """Test error recovery workflows."""

    def test_setup_fails_gracefully_without_plugin(self, tmp_path, monkeypatch):
        """Test setup fails gracefully if plugin not installed."""
        monkeypatch.chdir(tmp_path)

        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from setup import SetupWizard

        wizard = SetupWizard(auto=True, preset="team")
        # Should return early without crashing
        wizard.run()  # Will fail at verify_plugin_installation

        # Should not create any files
        assert not (tmp_path / ".claude" / "hooks").exists()

    def test_setup_handles_partial_installation(self, tmp_path, monkeypatch):
        """Test setup handles partial plugin installation."""
        monkeypatch.chdir(tmp_path)

        # Partial plugin (missing templates)
        plugin_dir = tmp_path / ".claude" / "plugins" / "autonomous-dev"
        plugin_hooks = plugin_dir / "hooks"
        plugin_hooks.mkdir(parents=True)
        (plugin_hooks / "auto_format.py").write_text("# hook")

        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from setup import SetupWizard

        wizard = SetupWizard(auto=True, preset="solo")
        wizard.run()

        # Should copy hooks but skip PROJECT.md (template missing)
        assert (tmp_path / ".claude" / "hooks").exists()
        # PROJECT.md won't be created without template


class TestDocumentationQuality:
    """Test documentation supports UAT."""

    def test_quickstart_has_complete_workflow(self):
        """Test QUICKSTART.md has complete workflow."""
        quickstart = Path(__file__).parent.parent / "QUICKSTART.md"
        if quickstart.exists():
            content = quickstart.read_text()

            # Should have installation steps
            assert "install" in content.lower()
            assert "/setup" in content or "setup" in content.lower()

            # Should have first feature example
            assert "feature" in content.lower()

    def test_readme_explains_architecture(self):
        """Test README explains architecture."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()

        # Should explain key concepts
        assert "agent" in content.lower()
        assert "skill" in content.lower() or "hook" in content.lower()
        assert "PROJECT.md" in content

    def test_install_template_guides_user(self):
        """Test INSTALL_TEMPLATE.md guides new users."""
        install_template = Path(__file__).parent.parent / "INSTALL_TEMPLATE.md"
        if install_template.exists():
            content = install_template.read_text()

            # Should have setup steps
            assert "/setup" in content or "setup" in content.lower()

            # Should explain what was installed
            assert "agent" in content.lower() or "skill" in content.lower()


class TestPerformanceExpectations:
    """Test performance expectations are documented."""

    def test_context_budget_documented(self):
        """Test context budget strategy is documented."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()

        # Should mention context management
        assert "/clear" in content or "context" in content.lower()

    def test_model_costs_documented(self):
        """Test model selection strategy is documented."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()

        # Should mention models or cost optimization
        assert "opus" in content.lower() or "haiku" in content.lower() or "sonnet" in content.lower()

    def test_file_size_limits_enforced(self):
        """Test file size limits are reasonable."""
        plugin_root = Path(__file__).parent.parent

        # No single file should be > 100KB
        for file in plugin_root.rglob("*.md"):
            if "node_modules" in str(file):
                continue
            size = file.stat().st_size
            assert size < 100_000, f"{file.name} is too large: {size} bytes"
