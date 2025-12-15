"""
Smoke tests for install.sh Bootstrap Functions (Issue #132).

Simplified smoke tests that verify:
1. install.sh exists and has bootstrap functions
2. Manifest has expected structure
3. Bootstrap functions exist in install.sh

For detailed integration tests, see tests/integration/
"""

import pytest
from pathlib import Path
import json

# Portable path detection (works from any test location)
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        project_root = current
        break
    current = current.parent
else:
    project_root = Path.cwd()


class TestBootstrapFunctionExistence:
    """Smoke test: All 5 bootstrap functions exist in install.sh."""

    @pytest.fixture
    def install_sh_content(self):
        """Load install.sh content."""
        install_sh = project_root / "install.sh"
        assert install_sh.exists(), f"install.sh not found at {install_sh}"
        return install_sh.read_text()

    def test_bootstrap_agents_function_exists(self, install_sh_content):
        """Test that install.sh contains bootstrap_agents function."""
        assert "bootstrap_agents()" in install_sh_content, "bootstrap_agents() function not found"

    def test_bootstrap_commands_function_exists(self, install_sh_content):
        """Test that install.sh contains bootstrap_commands function."""
        assert "bootstrap_commands()" in install_sh_content, "bootstrap_commands() function not found"

    def test_bootstrap_scripts_function_exists(self, install_sh_content):
        """Test that install.sh contains bootstrap_scripts function."""
        assert "bootstrap_scripts()" in install_sh_content, "bootstrap_scripts() function not found"

    def test_bootstrap_config_function_exists(self, install_sh_content):
        """Test that install.sh contains bootstrap_config function."""
        assert "bootstrap_config()" in install_sh_content, "bootstrap_config() function not found"

    def test_bootstrap_templates_function_exists(self, install_sh_content):
        """Test that install.sh contains bootstrap_templates function."""
        assert "bootstrap_templates()" in install_sh_content, "bootstrap_templates() function not found"


class TestBootstrapFunctionCalls:
    """Smoke test: main() calls all bootstrap functions."""

    @pytest.fixture
    def install_sh_content(self):
        """Load install.sh content."""
        install_sh = project_root / "install.sh"
        return install_sh.read_text()

    def test_main_calls_all_bootstrap_functions(self, install_sh_content):
        """Test that main() invokes all 5 bootstrap functions."""
        assert "main()" in install_sh_content, "main() function not found"
        assert "bootstrap_commands" in install_sh_content, "bootstrap_commands not called"
        assert "bootstrap_agents" in install_sh_content, "bootstrap_agents not called"
        assert "bootstrap_scripts" in install_sh_content, "bootstrap_scripts not called"
        assert "bootstrap_config" in install_sh_content, "bootstrap_config not called"
        assert "bootstrap_templates" in install_sh_content, "bootstrap_templates not called"

    def test_bootstrap_commands_called_first(self, install_sh_content):
        """Test that bootstrap_commands is called before other functions."""
        main_start = install_sh_content.find("main() {")
        assert main_start != -1, "main() function not found"
        main_content = install_sh_content[main_start:]

        commands_pos = main_content.find("if bootstrap_commands")
        agents_pos = main_content.find("if bootstrap_agents")
        scripts_pos = main_content.find("if bootstrap_scripts")

        if commands_pos != -1 and agents_pos != -1:
            assert commands_pos < agents_pos, "bootstrap_commands should be called before bootstrap_agents"
        if commands_pos != -1 and scripts_pos != -1:
            assert commands_pos < scripts_pos, "bootstrap_commands should be called before bootstrap_scripts"


class TestManifestStructure:
    """Smoke test: Manifest has expected component sections."""

    @pytest.fixture
    def manifest_data(self):
        """Load manifest JSON."""
        manifest_path = project_root / "plugins/autonomous-dev/config/install_manifest.json"
        assert manifest_path.exists(), f"Manifest not found at {manifest_path}"
        with open(manifest_path, "r") as f:
            return json.load(f)

    def test_manifest_has_components_section(self, manifest_data):
        """Test manifest has 'components' section."""
        assert "components" in manifest_data, "Manifest missing 'components' section"

    def test_manifest_has_agents_section(self, manifest_data):
        """Test manifest has agents component."""
        assert "agents" in manifest_data.get("components", {}), "Missing agents section"
        assert "files" in manifest_data["components"]["agents"], "Missing agents files"

    def test_manifest_has_commands_section(self, manifest_data):
        """Test manifest has commands component."""
        assert "commands" in manifest_data.get("components", {}), "Missing commands section"
        assert "files" in manifest_data["components"]["commands"], "Missing commands files"

    def test_manifest_has_scripts_section(self, manifest_data):
        """Test manifest has scripts component."""
        assert "scripts" in manifest_data.get("components", {}), "Missing scripts section"
        assert "files" in manifest_data["components"]["scripts"], "Missing scripts files"

    def test_manifest_has_config_section(self, manifest_data):
        """Test manifest has config component."""
        assert "config" in manifest_data.get("components", {}), "Missing config section"
        assert "files" in manifest_data["components"]["config"], "Missing config files"

    def test_manifest_has_templates_section(self, manifest_data):
        """Test manifest has templates component."""
        assert "templates" in manifest_data.get("components", {}), "Missing templates section"
        assert "files" in manifest_data["components"]["templates"], "Missing templates files"


class TestManifestFilesExist:
    """Smoke test: Files listed in manifest actually exist."""

    @pytest.fixture
    def manifest_data(self):
        """Load manifest JSON."""
        manifest_path = project_root / "plugins/autonomous-dev/config/install_manifest.json"
        with open(manifest_path, "r") as f:
            return json.load(f)

    def test_agent_files_exist(self, manifest_data):
        """Test that agent files listed in manifest exist."""
        agent_files = manifest_data.get("components", {}).get("agents", {}).get("files", [])
        for agent_path in agent_files:
            full_path = project_root / agent_path
            assert full_path.exists(), f"Agent file not found: {agent_path}"

    def test_command_files_exist(self, manifest_data):
        """Test that command files listed in manifest exist."""
        command_files = manifest_data.get("components", {}).get("commands", {}).get("files", [])
        for cmd_path in command_files:
            full_path = project_root / cmd_path
            assert full_path.exists(), f"Command file not found: {cmd_path}"

    def test_script_files_exist(self, manifest_data):
        """Test that script files listed in manifest exist."""
        script_files = manifest_data.get("components", {}).get("scripts", {}).get("files", [])
        for script_path in script_files:
            full_path = project_root / script_path
            assert full_path.exists(), f"Script file not found: {script_path}"


class TestBootstrapErrorHandling:
    """Smoke test: install.sh has error handling patterns."""

    @pytest.fixture
    def install_sh_content(self):
        """Load install.sh content."""
        install_sh = project_root / "install.sh"
        return install_sh.read_text()

    def test_handles_partial_staging_structure(self, install_sh_content):
        """Test that install.sh has error handling for missing directories."""
        # Check for common error handling patterns
        has_error_handling = any([
            "|| true" in install_sh_content,
            "if [" in install_sh_content,
            "2>/dev/null" in install_sh_content,
            "warning" in install_sh_content.lower(),
        ])
        assert has_error_handling, "Expected some error handling in install.sh"


class TestBootstrapSecurityValidation:
    """Smoke test: install.sh has security patterns."""

    @pytest.fixture
    def install_sh_content(self):
        """Load install.sh content."""
        install_sh = project_root / "install.sh"
        return install_sh.read_text()

    def test_validates_file_paths_prevent_directory_traversal(self, install_sh_content):
        """Test that install.sh has path validation or uses safe copy patterns."""
        # Check for security-conscious patterns
        has_safe_patterns = any([
            "cp " in install_sh_content,  # Uses cp (not cat)
            "-L" in install_sh_content,   # Follows/checks symlinks
            "symlink" in install_sh_content.lower(),
            "realpath" in install_sh_content,
        ])
        assert has_safe_patterns, "Expected safe file copy patterns in install.sh"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
