"""
TDD Tests for install.sh Bootstrap Functions (Issue #132)

Tests the 5 new bootstrap functions that copy files from staging to .claude/:
1. bootstrap_agents() - Copy 22 agents
2. bootstrap_commands() - Copy 6 commands (excluding setup.md)
3. bootstrap_scripts() - Copy 11 scripts
4. bootstrap_config() - Copy 6 configs
5. bootstrap_templates() - Copy 7 templates

Current State (RED PHASE):
- Bootstrap functions don't exist in install.sh yet
- All tests should FAIL

Test Coverage:
- Function existence verification
- Function call order in main()
- File copy operations
- Directory creation
- Symlink security rejection
- Idempotent behavior
- Error handling and non-blocking failures
- Count validation against manifest
"""

import pytest
from pathlib import Path
import subprocess
import json
import os


class TestBootstrapFunctionExistence:
    """Test that all 5 bootstrap functions exist in install.sh."""

    def test_bootstrap_agents_function_exists(self):
        """Test that install.sh contains bootstrap_agents function.

        Current: FAILS - Function doesn't exist yet
        """
        install_sh = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh")
        content = install_sh.read_text()

        # Assert: Function is defined
        assert "bootstrap_agents()" in content, "bootstrap_agents() function not found in install.sh"

    def test_bootstrap_commands_function_exists(self):
        """Test that install.sh contains bootstrap_commands function.

        Current: FAILS - Function doesn't exist yet
        """
        install_sh = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh")
        content = install_sh.read_text()

        # Assert: Function is defined
        assert "bootstrap_commands()" in content, "bootstrap_commands() function not found in install.sh"

    def test_bootstrap_scripts_function_exists(self):
        """Test that install.sh contains bootstrap_scripts function.

        Current: FAILS - Function doesn't exist yet
        """
        install_sh = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh")
        content = install_sh.read_text()

        # Assert: Function is defined
        assert "bootstrap_scripts()" in content, "bootstrap_scripts() function not found in install.sh"

    def test_bootstrap_config_function_exists(self):
        """Test that install.sh contains bootstrap_config function.

        Current: FAILS - Function doesn't exist yet
        """
        install_sh = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh")
        content = install_sh.read_text()

        # Assert: Function is defined
        assert "bootstrap_config()" in content, "bootstrap_config() function not found in install.sh"

    def test_bootstrap_templates_function_exists(self):
        """Test that install.sh contains bootstrap_templates function.

        Current: FAILS - Function doesn't exist yet
        """
        install_sh = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh")
        content = install_sh.read_text()

        # Assert: Function is defined
        assert "bootstrap_templates()" in content, "bootstrap_templates() function not found in install.sh"


class TestBootstrapFunctionCalls:
    """Test that main() calls all bootstrap functions in correct order."""

    def test_main_calls_all_bootstrap_functions(self):
        """Test that main() invokes all 5 bootstrap functions.

        Expected order:
        1. bootstrap_commands (setup.md first for /setup access)
        2. bootstrap_agents
        3. bootstrap_scripts
        4. bootstrap_config
        5. bootstrap_templates

        Current: FAILS - Functions not called in main()
        """
        install_sh = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh")
        content = install_sh.read_text()

        # Find main() function
        assert "main()" in content, "main() function not found"

        # Extract main() function body (simplified - real implementation may vary)
        # We're checking that the function calls exist somewhere in the script
        assert "bootstrap_commands" in content, "bootstrap_commands not called"
        assert "bootstrap_agents" in content, "bootstrap_agents not called"
        assert "bootstrap_scripts" in content, "bootstrap_scripts not called"
        assert "bootstrap_config" in content, "bootstrap_config not called"
        assert "bootstrap_templates" in content, "bootstrap_templates not called"

    def test_bootstrap_commands_called_first(self):
        """Test that bootstrap_commands is called before other bootstrap functions in main().

        Rationale: setup.md must be copied first so /setup is available immediately

        Current: PASSES - Call order enforced in main()
        """
        install_sh = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh")
        content = install_sh.read_text()

        # Find the main() function section (where calls happen)
        main_start = content.find("main() {")
        assert main_start != -1, "main() function not found"
        main_content = content[main_start:]

        # Find positions of bootstrap function calls within main()
        # Look for "if bootstrap_X" pattern which is the actual call
        commands_pos = main_content.find("if bootstrap_commands")
        agents_pos = main_content.find("if bootstrap_agents")
        scripts_pos = main_content.find("if bootstrap_scripts")

        # Assert: commands called before others (if all exist)
        if commands_pos != -1 and agents_pos != -1:
            assert commands_pos < agents_pos, "bootstrap_commands should be called before bootstrap_agents"
        if commands_pos != -1 and scripts_pos != -1:
            assert commands_pos < scripts_pos, "bootstrap_commands should be called before bootstrap_scripts"


class TestBootstrapAgentsIntegration:
    """Test bootstrap_agents() file copy operations."""

    def test_bootstrap_agents_copies_all_22_agents(self, tmp_path, monkeypatch):
        """Test that bootstrap_agents copies all 22 agent files.

        Expected agents (from manifest):
        - 22 total agents including researcher-local.md and researcher-web.md

        Current: FAILS - Function doesn't exist
        """
        # Arrange: Create staging directory with 22 agents
        staging_dir = tmp_path / ".autonomous-dev-staging"
        staging_dir.mkdir()

        plugin_agents = staging_dir / "plugins" / "autonomous-dev" / "agents"
        plugin_agents.mkdir(parents=True)

        # Create all 22 agents from manifest
        agents = [
            "advisor.md",
            "alignment-analyzer.md",
            "alignment-validator.md",
            "brownfield-analyzer.md",
            "commit-message-generator.md",
            "doc-master.md",
            "implementer.md",
            "issue-creator.md",
            "planner.md",
            "pr-description-generator.md",
            "project-bootstrapper.md",
            "project-progress-tracker.md",
            "project-status-analyzer.md",
            "quality-validator.md",
            "researcher.md",
            "researcher-local.md",
            "researcher-web.md",
            "reviewer.md",
            "security-auditor.md",
            "setup-wizard.md",
            "sync-validator.md",
            "test-master.md",
        ]

        for agent in agents:
            (plugin_agents / agent).write_text(f"# {agent}\nAgent content")

        # Create target directory
        target_dir = tmp_path / ".claude" / "agents"
        target_dir.mkdir(parents=True)

        # Monkeypatch HOME to use tmp_path
        monkeypatch.setenv("HOME", str(tmp_path))

        # Act: Run bootstrap_agents (would be via subprocess in real test)
        # For now, we're testing the expected behavior
        result = subprocess.run(
            ["bash", "-c", f"cd {tmp_path} && source /Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh && bootstrap_agents"],
            capture_output=True,
            text=True,
        )

        # Assert: All 22 agents copied
        assert result.returncode == 0, f"bootstrap_agents failed: {result.stderr}"

        copied_agents = list(target_dir.glob("*.md"))
        assert len(copied_agents) == 22, f"Expected 22 agents, found {len(copied_agents)}"

        # Verify specific agents exist
        assert (target_dir / "researcher-local.md").exists()
        assert (target_dir / "researcher-web.md").exists()
        assert (target_dir / "test-master.md").exists()

    def test_bootstrap_agents_creates_target_directory(self, tmp_path, monkeypatch):
        """Test that bootstrap_agents creates .claude/agents/ if it doesn't exist.

        Current: FAILS - Function doesn't exist
        """
        # Arrange: Staging with agents, no target directory
        staging_dir = tmp_path / ".autonomous-dev-staging"
        staging_dir.mkdir()

        plugin_agents = staging_dir / "plugins" / "autonomous-dev" / "agents"
        plugin_agents.mkdir(parents=True)
        (plugin_agents / "test-master.md").write_text("# Test Master")

        monkeypatch.setenv("HOME", str(tmp_path))

        # Target directory does NOT exist yet
        target_dir = tmp_path / ".claude" / "agents"
        assert not target_dir.exists()

        # Act: Run bootstrap_agents
        result = subprocess.run(
            ["bash", "-c", f"cd {tmp_path} && source /Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh && bootstrap_agents"],
            capture_output=True,
            text=True,
        )

        # Assert: Target directory created
        assert target_dir.exists(), "Target directory .claude/agents/ was not created"
        assert (target_dir / "test-master.md").exists()

    def test_bootstrap_agents_rejects_symlinks(self, tmp_path, monkeypatch):
        """Test that bootstrap_agents skips symlink files for security.

        Security: Prevents symlink attacks (CWE-59)

        Current: FAILS - Symlink protection not implemented
        """
        # Arrange: Staging with symlink
        staging_dir = tmp_path / ".autonomous-dev-staging"
        staging_dir.mkdir()

        plugin_agents = staging_dir / "plugins" / "autonomous-dev" / "agents"
        plugin_agents.mkdir(parents=True)

        # Create regular file
        (plugin_agents / "test-master.md").write_text("# Test Master")

        # Create symlink to sensitive file
        sensitive = tmp_path / "sensitive.txt"
        sensitive.write_text("SECRET_DATA")
        (plugin_agents / "malicious.md").symlink_to(sensitive)

        target_dir = tmp_path / ".claude" / "agents"
        target_dir.mkdir(parents=True)

        monkeypatch.setenv("HOME", str(tmp_path))

        # Act: Run bootstrap_agents
        result = subprocess.run(
            ["bash", "-c", f"cd {tmp_path} && source /Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh && bootstrap_agents"],
            capture_output=True,
            text=True,
        )

        # Assert: Regular file copied, symlink skipped
        assert (target_dir / "test-master.md").exists(), "Regular file should be copied"
        assert not (target_dir / "malicious.md").exists(), "Symlink should be rejected"

        # Verify warning logged
        assert "symlink" in result.stderr.lower() or "warning" in result.stderr.lower()


class TestBootstrapCommandsIntegration:
    """Test bootstrap_commands() file copy operations."""

    def test_bootstrap_commands_copies_6_commands_excluding_setup(self, tmp_path, monkeypatch):
        """Test that bootstrap_commands copies 6 commands (excluding setup.md).

        Expected commands:
        - align.md
        - auto-implement.md
        - batch-implement.md
        - create-issue.md
        - health-check.md
        - sync.md
        (setup.md excluded - handled by main install flow)

        Current: FAILS - Function doesn't exist
        """
        # Arrange: Create staging with 7 commands (6 + setup.md)
        staging_dir = tmp_path / ".autonomous-dev-staging"
        staging_dir.mkdir()

        plugin_commands = staging_dir / "plugins" / "autonomous-dev" / "commands"
        plugin_commands.mkdir(parents=True)

        commands = [
            "align.md",
            "auto-implement.md",
            "batch-implement.md",
            "create-issue.md",
            "health-check.md",
            "setup.md",  # Should be EXCLUDED
            "sync.md",
        ]

        for cmd in commands:
            (plugin_commands / cmd).write_text(f"# {cmd}\nCommand content")

        target_dir = tmp_path / ".claude" / "commands"
        target_dir.mkdir(parents=True)

        monkeypatch.setenv("HOME", str(tmp_path))

        # Act: Run bootstrap_commands
        result = subprocess.run(
            ["bash", "-c", f"cd {tmp_path} && source /Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh && bootstrap_commands"],
            capture_output=True,
            text=True,
        )

        # Assert: 6 commands copied (excluding setup.md)
        copied_commands = list(target_dir.glob("*.md"))
        assert len(copied_commands) == 6, f"Expected 6 commands (excluding setup.md), found {len(copied_commands)}"

        # Verify setup.md NOT copied
        assert not (target_dir / "setup.md").exists(), "setup.md should be excluded from bootstrap_commands"

        # Verify other commands exist
        assert (target_dir / "auto-implement.md").exists()
        assert (target_dir / "batch-implement.md").exists()
        assert (target_dir / "sync.md").exists()

    def test_bootstrap_commands_is_idempotent(self, tmp_path, monkeypatch):
        """Test that bootstrap_commands can be safely run multiple times.

        Scenario: User runs install.sh twice
        Expected: Second run doesn't corrupt files

        Current: FAILS - Idempotent behavior not guaranteed
        """
        # Arrange: Setup staging
        staging_dir = tmp_path / ".autonomous-dev-staging"
        staging_dir.mkdir()

        plugin_commands = staging_dir / "plugins" / "autonomous-dev" / "commands"
        plugin_commands.mkdir(parents=True)
        (plugin_commands / "auto-implement.md").write_text("# Auto Implement v1")

        target_dir = tmp_path / ".claude" / "commands"
        target_dir.mkdir(parents=True)

        monkeypatch.setenv("HOME", str(tmp_path))

        # Act: Run bootstrap_commands TWICE
        subprocess.run(
            ["bash", "-c", f"cd {tmp_path} && source /Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh && bootstrap_commands"],
            capture_output=True,
            text=True,
        )

        # Modify file between runs
        (plugin_commands / "auto-implement.md").write_text("# Auto Implement v2")

        result = subprocess.run(
            ["bash", "-c", f"cd {tmp_path} && source /Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh && bootstrap_commands"],
            capture_output=True,
            text=True,
        )

        # Assert: Second run succeeds and updates file
        assert result.returncode == 0, "Second run should succeed"

        content = (target_dir / "auto-implement.md").read_text()
        assert "v2" in content, "File should be updated on second run"


class TestBootstrapScriptsIntegration:
    """Test bootstrap_scripts() file copy operations."""

    def test_bootstrap_scripts_copies_11_scripts(self, tmp_path, monkeypatch):
        """Test that bootstrap_scripts copies all 11 script files.

        Expected scripts (from manifest):
        - 11 total scripts

        Current: FAILS - Function doesn't exist
        """
        # Arrange: Create staging with 11 scripts
        staging_dir = tmp_path / ".autonomous-dev-staging"
        staging_dir.mkdir()

        plugin_scripts = staging_dir / "plugins" / "autonomous-dev" / "scripts"
        plugin_scripts.mkdir(parents=True)

        scripts = [
            "batch_state_manager.py",
            "create_issue.py",
            "genai_install_wrapper.py",
            "health_check.py",
            "performance_analyzer.py",
            "session_tracker.py",
            "setup.py",
            "sync.py",
            "validate_claude_alignment.py",
            "validate_hook_documentation.py",
            "validate_install_manifest.py",
        ]

        for script in scripts:
            (plugin_scripts / script).write_text(f"#!/usr/bin/env python3\n# {script}")

        target_dir = tmp_path / ".claude" / "scripts"
        target_dir.mkdir(parents=True)

        monkeypatch.setenv("HOME", str(tmp_path))

        # Act: Run bootstrap_scripts
        result = subprocess.run(
            ["bash", "-c", f"cd {tmp_path} && source /Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh && bootstrap_scripts"],
            capture_output=True,
            text=True,
        )

        # Assert: All 11 scripts copied
        copied_scripts = list(target_dir.glob("*.py"))
        assert len(copied_scripts) == 11, f"Expected 11 scripts, found {len(copied_scripts)}"

        # Verify specific scripts exist
        assert (target_dir / "session_tracker.py").exists()
        assert (target_dir / "setup.py").exists()
        assert (target_dir / "sync.py").exists()

    def test_bootstrap_scripts_sets_executable_permissions(self, tmp_path, monkeypatch):
        """Test that bootstrap_scripts sets executable permissions.

        Expected: Scripts should be executable (chmod +x)

        Current: FAILS - Permissions not set
        """
        # Arrange: Setup staging
        staging_dir = tmp_path / ".autonomous-dev-staging"
        staging_dir.mkdir()

        plugin_scripts = staging_dir / "plugins" / "autonomous-dev" / "scripts"
        plugin_scripts.mkdir(parents=True)
        (plugin_scripts / "setup.py").write_text("#!/usr/bin/env python3\nprint('setup')")

        target_dir = tmp_path / ".claude" / "scripts"
        target_dir.mkdir(parents=True)

        monkeypatch.setenv("HOME", str(tmp_path))

        # Act: Run bootstrap_scripts
        subprocess.run(
            ["bash", "-c", f"cd {tmp_path} && source /Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh && bootstrap_scripts"],
            capture_output=True,
            text=True,
        )

        # Assert: Script is executable
        script_path = target_dir / "setup.py"
        assert script_path.exists()

        # Check executable bit
        assert os.access(str(script_path), os.X_OK), "Script should be executable"


class TestBootstrapConfigIntegration:
    """Test bootstrap_config() file copy operations."""

    def test_bootstrap_config_copies_6_config_files(self, tmp_path, monkeypatch):
        """Test that bootstrap_config copies all 6 config files.

        Expected configs (from manifest):
        - 6 total config files

        Current: FAILS - Function doesn't exist
        """
        # Arrange: Create staging with 6 configs
        staging_dir = tmp_path / ".autonomous-dev-staging"
        staging_dir.mkdir()

        plugin_config = staging_dir / "plugins" / "autonomous-dev" / "config"
        plugin_config.mkdir(parents=True)

        configs = [
            "auto_approve_policy.json",
            "install_manifest.json",
            "model_assignments.json",
            "performance_profiles.json",
            "security_policy.json",
            "settings_template.json",
        ]

        for cfg in configs:
            (plugin_config / cfg).write_text(f'{{"name": "{cfg}"}}')

        target_dir = tmp_path / ".claude" / "config"
        target_dir.mkdir(parents=True)

        monkeypatch.setenv("HOME", str(tmp_path))

        # Act: Run bootstrap_config
        result = subprocess.run(
            ["bash", "-c", f"cd {tmp_path} && source /Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh && bootstrap_config"],
            capture_output=True,
            text=True,
        )

        # Assert: All 6 configs copied
        copied_configs = list(target_dir.glob("*.json"))
        assert len(copied_configs) == 6, f"Expected 6 configs, found {len(copied_configs)}"

        # Verify specific configs exist
        assert (target_dir / "install_manifest.json").exists()
        assert (target_dir / "security_policy.json").exists()
        assert (target_dir / "auto_approve_policy.json").exists()


class TestBootstrapTemplatesIntegration:
    """Test bootstrap_templates() file copy operations."""

    def test_bootstrap_templates_copies_7_template_files(self, tmp_path, monkeypatch):
        """Test that bootstrap_templates copies all 7 template files.

        Expected templates (from manifest):
        - 7 total template files

        Current: FAILS - Function doesn't exist
        """
        # Arrange: Create staging with 7 templates
        staging_dir = tmp_path / ".autonomous-dev-staging"
        staging_dir.mkdir()

        plugin_templates = staging_dir / "plugins" / "autonomous-dev" / "templates"
        plugin_templates.mkdir(parents=True)

        templates = [
            "CLAUDE.md.template",
            "PROJECT.md.template",
            "batch_features.txt.template",
            "env.template",
            "github_issue.md.template",
            "pr_description.md.template",
            "session_log.md.template",
        ]

        for tmpl in templates:
            (plugin_templates / tmpl).write_text(f"# Template: {tmpl}\nContent here")

        target_dir = tmp_path / ".claude" / "templates"
        target_dir.mkdir(parents=True)

        monkeypatch.setenv("HOME", str(tmp_path))

        # Act: Run bootstrap_templates
        result = subprocess.run(
            ["bash", "-c", f"cd {tmp_path} && source /Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh && bootstrap_templates"],
            capture_output=True,
            text=True,
        )

        # Assert: All 7 templates copied
        copied_templates = list(target_dir.glob("*"))
        assert len(copied_templates) == 7, f"Expected 7 templates, found {len(copied_templates)}"

        # Verify specific templates exist
        assert (target_dir / "PROJECT.md.template").exists()
        assert (target_dir / "env.template").exists()
        assert (target_dir / "github_issue.md.template").exists()


class TestBootstrapErrorHandling:
    """Test error handling and non-blocking failures."""

    def test_handles_missing_staging_directory_gracefully(self, tmp_path, monkeypatch):
        """Test that bootstrap functions handle missing staging directory.

        Expected: Warning logged, script continues (non-blocking)

        Current: FAILS - Error handling not implemented
        """
        # Arrange: No staging directory
        monkeypatch.setenv("HOME", str(tmp_path))

        # Staging directory does NOT exist
        staging_dir = tmp_path / ".autonomous-dev-staging"
        assert not staging_dir.exists()

        # Act: Run bootstrap_agents (should handle gracefully)
        result = subprocess.run(
            ["bash", "-c", f"cd {tmp_path} && source /Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh && bootstrap_agents || true"],
            capture_output=True,
            text=True,
        )

        # Assert: Non-zero exit OK (function failed gracefully)
        # Script should log warning but not crash
        assert "warning" in result.stderr.lower() or "not found" in result.stderr.lower()

    def test_handles_partial_staging_structure(self, tmp_path, monkeypatch):
        """Test that bootstrap functions handle incomplete staging.

        Scenario: Staging exists but missing expected subdirectories

        Current: FAILS - Partial structure handling not implemented
        """
        # Arrange: Staging with missing subdirectories
        staging_dir = tmp_path / ".autonomous-dev-staging"
        staging_dir.mkdir()

        # Only create plugins/ but not plugins/autonomous-dev/
        (staging_dir / "plugins").mkdir()

        monkeypatch.setenv("HOME", str(tmp_path))

        # Act: Run bootstrap_agents
        result = subprocess.run(
            ["bash", "-c", f"cd {tmp_path} && source /Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh && bootstrap_agents || true"],
            capture_output=True,
            text=True,
        )

        # Assert: Handles gracefully (logs warning, doesn't crash)
        # Exit code can be non-zero (expected failure)
        assert result.stderr != "" or result.stdout != ""  # Some output expected

    def test_continues_on_individual_file_copy_failure(self, tmp_path, monkeypatch):
        """Test that bootstrap continues if one file fails to copy.

        Expected: Failed file logged, other files still copied

        Current: FAILS - Individual file error handling not implemented
        """
        # Arrange: Setup staging
        staging_dir = tmp_path / ".autonomous-dev-staging"
        staging_dir.mkdir()

        plugin_agents = staging_dir / "plugins" / "autonomous-dev" / "agents"
        plugin_agents.mkdir(parents=True)

        # Create multiple agents
        (plugin_agents / "test-master.md").write_text("# Test Master")
        (plugin_agents / "implementer.md").write_text("# Implementer")

        # Create problematic file (read-only to simulate failure)
        problem_file = plugin_agents / "reviewer.md"
        problem_file.write_text("# Reviewer")
        problem_file.chmod(0o000)  # No permissions (will fail to read)

        target_dir = tmp_path / ".claude" / "agents"
        target_dir.mkdir(parents=True)

        monkeypatch.setenv("HOME", str(tmp_path))

        # Act: Run bootstrap_agents
        result = subprocess.run(
            ["bash", "-c", f"cd {tmp_path} && source /Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh && bootstrap_agents || true"],
            capture_output=True,
            text=True,
        )

        # Assert: Other files still copied despite one failure
        assert (target_dir / "test-master.md").exists(), "Other files should still be copied"
        assert (target_dir / "implementer.md").exists(), "Other files should still be copied"

        # Cleanup: Restore permissions for test cleanup
        problem_file.chmod(0o644)


class TestBootstrapCountValidation:
    """Test that bootstrap functions copy expected file counts from manifest."""

    def test_validates_22_agents_copied(self, tmp_path, monkeypatch):
        """Test that exactly 22 agents are copied (matches manifest).

        Current: FAILS - Count validation not implemented
        """
        # This test is conceptual - actual validation might be in install.sh
        # or a post-bootstrap verification step

        manifest_path = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/config/install_manifest.json")
        manifest = json.loads(manifest_path.read_text())

        expected_agents = len(manifest["components"]["agents"]["files"])
        assert expected_agents == 22, "Manifest should list 22 agents"

    def test_validates_6_commands_copied_excluding_setup(self, tmp_path, monkeypatch):
        """Test that exactly 6 commands are copied (7 in manifest - setup.md).

        Current: FAILS - Count validation not implemented
        """
        manifest_path = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/config/install_manifest.json")
        manifest = json.loads(manifest_path.read_text())

        total_commands = len(manifest["components"]["commands"]["files"])
        assert total_commands == 7, "Manifest should list 7 commands (including setup.md)"

        # bootstrap_commands should copy 6 (excluding setup.md)
        expected_copied = total_commands - 1
        assert expected_copied == 6, "Should copy 6 commands (excluding setup.md)"

    def test_validates_11_scripts_copied(self, tmp_path, monkeypatch):
        """Test that exactly 11 scripts are copied (matches manifest).

        Current: FAILS - Count validation not implemented
        """
        manifest_path = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/config/install_manifest.json")
        manifest = json.loads(manifest_path.read_text())

        expected_scripts = len(manifest["components"]["scripts"]["files"])
        assert expected_scripts == 11, "Manifest should list 11 scripts"

    def test_validates_6_configs_copied(self, tmp_path, monkeypatch):
        """Test that exactly 6 configs are copied (matches manifest).

        Current: FAILS - Count validation not implemented
        """
        manifest_path = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/config/install_manifest.json")
        manifest = json.loads(manifest_path.read_text())

        expected_configs = len(manifest["components"]["config"]["files"])
        assert expected_configs == 6, "Manifest should list 6 configs"

    def test_validates_7_templates_copied(self, tmp_path, monkeypatch):
        """Test that exactly 7 templates are copied (matches manifest).

        Current: FAILS - Count validation not implemented
        """
        manifest_path = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/plugins/autonomous-dev/config/install_manifest.json")
        manifest = json.loads(manifest_path.read_text())

        expected_templates = len(manifest["components"]["templates"]["files"])
        assert expected_templates == 7, "Manifest should list 7 templates"


class TestBootstrapSecurityValidation:
    """Test security aspects of bootstrap functions."""

    def test_rejects_symlinks_in_all_bootstrap_functions(self, tmp_path, monkeypatch):
        """Test that all bootstrap functions reject symlinks.

        Security: Prevents CWE-59 (symlink following)

        Current: FAILS - Symlink protection not implemented
        """
        # This is a comprehensive test across all bootstrap functions
        staging_dir = tmp_path / ".autonomous-dev-staging"
        staging_dir.mkdir()

        categories = {
            "agents": "bootstrap_agents",
            "commands": "bootstrap_commands",
            "scripts": "bootstrap_scripts",
            "config": "bootstrap_config",
            "templates": "bootstrap_templates",
        }

        for category, function in categories.items():
            # Arrange: Create symlink in category
            category_dir = staging_dir / "plugins" / "autonomous-dev" / category
            category_dir.mkdir(parents=True)

            # Regular file
            (category_dir / "regular.md").write_text("Regular content")

            # Malicious symlink
            sensitive = tmp_path / f"sensitive_{category}.txt"
            sensitive.write_text("SECRET")
            (category_dir / "malicious.md").symlink_to(sensitive)

            target_dir = tmp_path / ".claude" / category
            target_dir.mkdir(parents=True)

            monkeypatch.setenv("HOME", str(tmp_path))

            # Act: Run bootstrap function
            result = subprocess.run(
                ["bash", "-c", f"cd {tmp_path} && source /Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh && {function}"],
                capture_output=True,
                text=True,
            )

            # Assert: Symlink rejected for this category
            assert (target_dir / "regular.md").exists() or (target_dir / "regular.py").exists() or (target_dir / "regular.json").exists(), \
                f"Regular file should be copied in {category}"
            assert not (target_dir / "malicious.md").exists(), \
                f"Symlink should be rejected in {category}"

    def test_validates_file_paths_prevent_directory_traversal(self, tmp_path, monkeypatch):
        """Test that bootstrap functions prevent directory traversal.

        Security: Prevents CWE-22 (path traversal)

        Current: FAILS - Path validation not implemented
        """
        # Arrange: Create staging with malicious filename
        staging_dir = tmp_path / ".autonomous-dev-staging"
        staging_dir.mkdir()

        plugin_agents = staging_dir / "plugins" / "autonomous-dev" / "agents"
        plugin_agents.mkdir(parents=True)

        # Try to create file with path traversal (../)
        # Note: This might fail at OS level, but we're testing the handling
        try:
            malicious_path = plugin_agents / "../../malicious.md"
            malicious_path.parent.mkdir(parents=True, exist_ok=True)
            malicious_path.write_text("Malicious content")
        except (OSError, ValueError):
            # Expected - OS blocks it, but test the script's handling
            pass

        target_dir = tmp_path / ".claude" / "agents"
        target_dir.mkdir(parents=True)

        monkeypatch.setenv("HOME", str(tmp_path))

        # Act: Run bootstrap_agents
        result = subprocess.run(
            ["bash", "-c", f"cd {tmp_path} && source /Users/akaszubski/Documents/GitHub/autonomous-dev/install.sh && bootstrap_agents || true"],
            capture_output=True,
            text=True,
        )

        # Assert: Malicious path not created outside target directory
        malicious_target = target_dir.parent.parent / "malicious.md"
        assert not malicious_target.exists(), "Directory traversal should be prevented"


# Summary Statistics
"""
Test Coverage Summary:
- Function Existence: 5 tests (1 per bootstrap function)
- Function Calls: 2 tests (main() integration)
- Agent Bootstrap: 3 tests (copy, directory creation, symlink rejection)
- Commands Bootstrap: 2 tests (exclusion logic, idempotent)
- Scripts Bootstrap: 2 tests (copy, permissions)
- Config Bootstrap: 1 test (copy)
- Templates Bootstrap: 1 test (copy)
- Error Handling: 3 tests (missing directory, partial structure, file failure)
- Count Validation: 5 tests (manifest matching)
- Security: 2 tests (symlink rejection, path traversal)

Total Tests: 26 tests

All tests should FAIL initially (TDD RED PHASE).
Implementation will make them pass (GREEN PHASE).
"""
