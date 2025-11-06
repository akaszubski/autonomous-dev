"""Smoke tests for plugin loading and initialization.

Tests validate that the plugin loads without errors and
critical resources are available.

All tests must complete in < 5 seconds total.
"""

import sys
from pathlib import Path

import pytest


@pytest.mark.smoke
class TestPluginStructure:
    """Validate plugin directory structure and essential files."""

    def test_plugin_directory_exists(self, plugins_dir, timing_validator):
        """Test that plugin directory exists and is accessible.

        Protects: Plugin installation (smoke test - regression baseline)
        Expected: < 1 second
        """
        # NOTE: This will FAIL if plugin not installed
        with timing_validator.measure() as timer:
            assert plugins_dir.exists()
            assert plugins_dir.is_dir()
            assert plugins_dir.name == "autonomous-dev"

        assert timer.elapsed < 1.0

    def test_plugin_manifest_exists(self, plugins_dir, timing_validator):
        """Test that plugin manifest file exists.

        Protects: Plugin metadata availability (smoke test - regression baseline)
        Expected: < 1 second
        """
        # NOTE: This will FAIL if plugin.json not present
        with timing_validator.measure() as timer:
            manifest = plugins_dir / "plugin.json"
            assert manifest.exists()

            # Validate it's valid JSON
            import json
            data = json.loads(manifest.read_text())
            assert "name" in data
            assert data["name"] == "autonomous-dev"

        assert timer.elapsed < 1.0

    def test_agents_directory_exists(self, plugins_dir, timing_validator):
        """Test that agents directory exists with expected agents.

        Protects: Agent availability (smoke test - regression baseline)
        Expected: < 1 second
        """
        # NOTE: This will FAIL if agents directory missing
        with timing_validator.measure() as timer:
            agents_dir = plugins_dir / "agents"
            assert agents_dir.exists()
            assert agents_dir.is_dir()

            # Check for at least some core agents
            agent_files = list(agents_dir.glob("*.md"))
            assert len(agent_files) >= 18  # Current agent count per CLAUDE.md

        assert timer.elapsed < 1.0

    def test_commands_directory_exists(self, plugins_dir, timing_validator):
        """Test that commands directory exists with expected commands.

        Protects: Command availability (smoke test - regression baseline)
        Expected: < 1 second
        """
        # NOTE: This will FAIL if commands directory missing
        with timing_validator.measure() as timer:
            commands_dir = plugins_dir / "commands"
            assert commands_dir.exists()
            assert commands_dir.is_dir()

            # Check for at least some core commands
            command_files = list(commands_dir.glob("*.md"))
            assert len(command_files) >= 8  # Core workflow commands

        assert timer.elapsed < 1.0

    def test_hooks_directory_exists(self, plugins_dir, timing_validator):
        """Test that hooks directory exists with expected hooks.

        Protects: Hook availability (smoke test - regression baseline)
        Expected: < 1 second
        """
        # NOTE: This will FAIL if hooks directory missing
        with timing_validator.measure() as timer:
            hooks_dir = plugins_dir / "hooks"
            assert hooks_dir.exists()
            assert hooks_dir.is_dir()

            # Check for at least some core hooks
            hook_files = list(hooks_dir.glob("*.py"))
            assert len(hook_files) >= 9  # Core hooks per CLAUDE.md

        assert timer.elapsed < 1.0


@pytest.mark.smoke
class TestPluginImports:
    """Validate that plugin modules can be imported without errors."""

    def test_plugin_lib_importable(self, plugins_dir, timing_validator):
        """Test that plugin lib modules can be imported.

        Protects: Library module availability (smoke test - regression baseline)
        Expected: < 2 seconds
        """
        # NOTE: This will FAIL if import errors exist
        with timing_validator.measure() as timer:
            # Add to path
            lib_dir = plugins_dir / "lib"
            sys.path.insert(0, str(lib_dir))

            try:
                # Import key modules (will fail if syntax errors)
                import project_md_updater
                import auto_implement_git_integration
                import git_operations
                import pr_automation

                # Verify key classes exist
                assert hasattr(project_md_updater, 'ProjectMdUpdater')
                assert hasattr(auto_implement_git_integration, 'execute_step8_git_operations')
                assert hasattr(git_operations, 'GitOperations')
                assert hasattr(pr_automation, 'PrAutomation')

            finally:
                sys.path.pop(0)

        assert timer.elapsed < 2.0

    def test_plugin_scripts_importable(self, plugins_dir, timing_validator):
        """Test that plugin scripts can be imported.

        Protects: Script availability (smoke test - regression baseline)
        Expected: < 2 seconds
        """
        # NOTE: This will FAIL if import errors exist
        with timing_validator.measure() as timer:
            # Add to path
            scripts_dir = plugins_dir / "scripts"
            sys.path.insert(0, str(scripts_dir))

            try:
                # Import key scripts (will fail if syntax errors)
                import health_check
                import session_tracker
                import invoke_agent

                # Verify key functions/classes exist
                assert hasattr(health_check, 'PluginHealthCheck')
                assert hasattr(session_tracker, 'track_agent_event')
                assert hasattr(invoke_agent, 'invoke_agent')

            finally:
                sys.path.pop(0)

        assert timer.elapsed < 2.0


@pytest.mark.smoke
class TestPluginConfiguration:
    """Validate plugin configuration files exist and are valid."""

    def test_env_example_exists(self, project_root, timing_validator):
        """Test that .env.example exists with required variables.

        Protects: Configuration template (smoke test - regression baseline)
        Expected: < 1 second
        """
        # NOTE: This will FAIL if .env.example missing or incomplete
        with timing_validator.measure() as timer:
            env_example = project_root / ".env.example"
            assert env_example.exists()

            content = env_example.read_text()

            # Check for required variables (per v3.4.0)
            assert "AUTO_GIT_ENABLED" in content
            assert "AUTO_GIT_PUSH" in content
            assert "AUTO_GIT_PR" in content

        assert timer.elapsed < 1.0

    def test_gitignore_exists_and_protects_env(self, project_root, timing_validator):
        """Test that .gitignore exists and protects .env files.

        Protects: Security - prevent credential leaks (smoke test - regression baseline)
        Expected: < 1 second
        """
        # NOTE: This will FAIL if .gitignore missing or incomplete
        with timing_validator.measure() as timer:
            gitignore = project_root / ".gitignore"
            assert gitignore.exists()

            content = gitignore.read_text()

            # Must gitignore .env files (security requirement)
            assert ".env" in content or "*.env" in content

        assert timer.elapsed < 1.0

    def test_project_md_exists(self, project_root, timing_validator):
        """Test that PROJECT.md exists with required sections.

        Protects: Project alignment system (smoke test - regression baseline)
        Expected: < 1 second
        """
        # NOTE: This will FAIL if PROJECT.md missing or incomplete
        with timing_validator.measure() as timer:
            project_md = project_root / ".claude" / "PROJECT.md"
            assert project_md.exists()

            content = project_md.read_text()

            # Check for required sections (per alignment system)
            assert "## GOALS" in content
            assert "## SCOPE" in content
            assert "## CONSTRAINTS" in content

        assert timer.elapsed < 1.0
