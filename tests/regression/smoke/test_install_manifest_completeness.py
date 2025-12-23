#!/usr/bin/env python3
"""
TDD Tests for Install Manifest Completeness Audit - Issue #159

This module contains FAILING tests (RED phase) for verifying that the install
manifest (plugins/autonomous-dev/config/install_manifest.json) includes all
orphaned files discovered during audit.

Problem (Issue #159):
- 21 agent files exist on disk, but only 8 are in manifest (13 missing)
- 6 hooks exist on disk but are missing from manifest
- 7 libs exist on disk but are missing from manifest
- Deprecated commands should NOT be in manifest

Requirements (Issue #159):
1. All 21 agent files on disk must be in manifest
2. All 6 missing hooks must be added to manifest
3. All 7 missing libs must be added to manifest
4. Deprecated commands must NOT be in manifest
5. Manifest version must be bumped from current version

This test suite follows TDD principles:
- Tests written FIRST before manifest is updated
- Tests SHOULD FAIL until manifest updated
- Tests validate completeness, not functionality

Author: test-master agent
Date: 2025-12-24
Issue: #159
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Set

import pytest

# Portable path detection (works from any test location)
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        project_root = current
        break
    current = current.parent
else:
    project_root = Path.cwd()

# Add project root to path for imports
sys.path.insert(0, str(project_root))


# Constants - Expected files based on audit
EXPECTED_AGENTS = {
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
    "researcher-local.md",
    "researcher.md",
    "reviewer.md",
    "security-auditor.md",
    "setup-wizard.md",
    "sync-validator.md",
    "test-master.md",
}

EXPECTED_COMMANDS = {
    "advise.md",
    "align.md",
    "auto-implement.md",
    "batch-implement.md",
    "create-issue.md",
    "health-check.md",
    "setup.md",
    "sync.md",
}

DEPRECATED_COMMANDS = {
    "align-project.md",
    "align-claude.md",
    "align-project-retrofit.md",
    "update-plugin.md",
    "implement.md",
    "research.md",
    "plan.md",
    "review.md",
    "test-feature.md",
    "test.md",
    "security-scan.md",
    "update-docs.md",
    "pipeline-status.md",
    "status.md",
}

MISSING_HOOKS = {
    "detect_feature_request.py",
    "log_agent_completion.py",
    "session_tracker.py",
    "auto_update_project_progress.py",
    "batch_permission_approver.py",
    "unified_pre_tool_use.py",
}

MISSING_LIBS = {
    "genai_validate.py",
    "math_utils.py",
    "search_utils.py",
    "mcp_profile_manager.py",
    "mcp_server_detector.py",
    "git_hooks.py",
    "validate_documentation_parity.py",
}


class TestInstallManifestStructure:
    """Test that install manifest exists and has correct structure."""

    @pytest.fixture
    def manifest_path(self):
        """Get path to install manifest."""
        return (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "config"
            / "install_manifest.json"
        )

    @pytest.fixture
    def manifest_data(self, manifest_path):
        """Load and parse manifest JSON."""
        assert manifest_path.exists(), f"Manifest not found at {manifest_path}"
        with open(manifest_path, "r") as f:
            return json.load(f)

    def test_manifest_exists(self, manifest_path):
        """Test that install manifest file exists.

        RED PHASE: Should fail if manifest not found
        EXPECTATION: File at plugins/autonomous-dev/config/install_manifest.json
        """
        assert manifest_path.exists(), (
            f"Manifest not found at {manifest_path}\n"
            "Expected: plugins/autonomous-dev/config/install_manifest.json"
        )

    def test_manifest_is_valid_json(self, manifest_path):
        """Test that manifest is valid JSON.

        RED PHASE: Should fail if manifest has JSON syntax errors
        EXPECTATION: File parses successfully as JSON
        """
        try:
            with open(manifest_path, "r") as f:
                json.load(f)
        except json.JSONDecodeError as e:
            pytest.fail(
                f"Manifest JSON is invalid: {e}\n"
                f"File: {manifest_path}\n"
                "Fix: Ensure valid JSON syntax"
            )

    def test_manifest_has_components_section(self, manifest_data):
        """Test that manifest has 'components' section with all required subsections.

        RED PHASE: Should fail if required sections missing
        EXPECTATION: manifest_data['components'] contains agents, commands, hooks, libs
        """
        assert "components" in manifest_data, (
            "Manifest missing 'components' section\n"
            "Expected: manifest['components'] with subsections"
        )

        required_sections = ["agents", "commands", "hooks", "lib", "scripts", "config", "templates", "skills"]
        missing = [s for s in required_sections if s not in manifest_data["components"]]

        assert not missing, (
            f"Manifest missing required component sections: {missing}\n"
            f"Expected: {required_sections}\n"
            f"Found: {list(manifest_data['components'].keys())}"
        )


class TestManifestAgentCompleteness:
    """Test that manifest includes all 21 agent files on disk."""

    @pytest.fixture
    def manifest_data(self):
        """Load manifest JSON."""
        manifest_path = (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "config"
            / "install_manifest.json"
        )
        with open(manifest_path, "r") as f:
            return json.load(f)

    @pytest.fixture
    def manifest_agents(self, manifest_data) -> Set[str]:
        """Extract agent filenames from manifest."""
        files = manifest_data.get("components", {}).get("agents", {}).get("files", [])
        return {Path(f).name for f in files}

    def test_manifest_has_21_agents(self, manifest_agents):
        """Test that manifest lists exactly 21 agent files.

        RED PHASE: Should FAIL until all 21 agents added to manifest
        EXPECTATION: Exactly 21 agent paths in manifest

        Active agents (21 total):
        - advisor.md, alignment-analyzer.md, alignment-validator.md
        - brownfield-analyzer.md, commit-message-generator.md
        - doc-master.md, implementer.md, issue-creator.md
        - planner.md, pr-description-generator.md
        - project-bootstrapper.md, project-progress-tracker.md
        - project-status-analyzer.md, quality-validator.md
        - researcher-local.md, researcher.md, reviewer.md
        - security-auditor.md, setup-wizard.md
        - sync-validator.md, test-master.md
        """
        assert len(manifest_agents) == 21, (
            f"Expected 21 agent files in manifest, found {len(manifest_agents)}\n"
            f"Current manifest agents: {sorted(manifest_agents)}\n"
            f"Expected agents: {sorted(EXPECTED_AGENTS)}\n"
            f"Missing: {sorted(EXPECTED_AGENTS - manifest_agents)}\n"
            f"Extra: {sorted(manifest_agents - EXPECTED_AGENTS)}\n"
        )

    def test_all_expected_agents_in_manifest(self, manifest_agents):
        """Test that all expected agent files are in manifest.

        RED PHASE: Should FAIL until all agents added
        EXPECTATION: All 21 agents from EXPECTED_AGENTS set are in manifest
        """
        missing = EXPECTED_AGENTS - manifest_agents
        assert not missing, (
            f"Missing {len(missing)} agent files from manifest:\n"
            f"  {chr(10).join(sorted(missing))}\n\n"
            "These files exist on disk but are not in manifest.\n"
            "Add them to plugins/autonomous-dev/config/install_manifest.json\n"
            "under components.agents.files with path:\n"
            "  plugins/autonomous-dev/agents/<filename>"
        )

    def test_no_extra_agents_in_manifest(self, manifest_agents):
        """Test that manifest doesn't include unexpected agent files.

        RED PHASE: Should FAIL if manifest contains agents not on disk
        EXPECTATION: All manifest agents are in EXPECTED_AGENTS set
        """
        extra = manifest_agents - EXPECTED_AGENTS
        assert not extra, (
            f"Manifest contains {len(extra)} unexpected agent files:\n"
            f"  {chr(10).join(sorted(extra))}\n\n"
            "These agents are in manifest but not expected.\n"
            "Remove them or add to EXPECTED_AGENTS if they should exist."
        )

    def test_missing_13_orphaned_agents(self, manifest_agents):
        """Test that the 13 orphaned agents from audit are now in manifest.

        RED PHASE: Should FAIL until orphaned agents added
        EXPECTATION: advisor, alignment-analyzer, alignment-validator,
                     brownfield-analyzer, commit-message-generator,
                     pr-description-generator, project-bootstrapper,
                     project-progress-tracker, project-status-analyzer,
                     quality-validator, researcher, setup-wizard,
                     sync-validator are all in manifest
        """
        orphaned_agents = {
            "advisor.md",
            "alignment-analyzer.md",
            "alignment-validator.md",
            "brownfield-analyzer.md",
            "commit-message-generator.md",
            "pr-description-generator.md",
            "project-bootstrapper.md",
            "project-progress-tracker.md",
            "project-status-analyzer.md",
            "quality-validator.md",
            "researcher.md",
            "setup-wizard.md",
            "sync-validator.md",
        }

        missing = orphaned_agents - manifest_agents
        assert not missing, (
            f"Missing {len(missing)} orphaned agents from manifest:\n"
            f"  {chr(10).join(sorted(missing))}\n\n"
            "These were discovered during Issue #159 audit.\n"
            "They exist on disk but are missing from manifest."
        )


class TestManifestCommandCompleteness:
    """Test that manifest includes correct command files."""

    @pytest.fixture
    def manifest_data(self):
        """Load manifest JSON."""
        manifest_path = (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "config"
            / "install_manifest.json"
        )
        with open(manifest_path, "r") as f:
            return json.load(f)

    @pytest.fixture
    def manifest_commands(self, manifest_data) -> Set[str]:
        """Extract command filenames from manifest."""
        files = manifest_data.get("components", {}).get("commands", {}).get("files", [])
        return {Path(f).name for f in files}

    def test_manifest_has_8_commands(self, manifest_commands):
        """Test that manifest lists exactly 8 command files.

        EXPECTATION: Exactly 8 active commands in manifest
        """
        assert len(manifest_commands) == 8, (
            f"Expected 8 command files in manifest, found {len(manifest_commands)}\n"
            f"Current manifest commands: {sorted(manifest_commands)}\n"
            f"Expected commands: {sorted(EXPECTED_COMMANDS)}\n"
            f"Missing: {sorted(EXPECTED_COMMANDS - manifest_commands)}\n"
            f"Extra: {sorted(manifest_commands - EXPECTED_COMMANDS)}\n"
        )

    def test_all_expected_commands_in_manifest(self, manifest_commands):
        """Test that all expected command files are in manifest.

        EXPECTATION: All 8 commands from EXPECTED_COMMANDS set are in manifest
        """
        missing = EXPECTED_COMMANDS - manifest_commands
        assert not missing, (
            f"Missing {len(missing)} command files from manifest:\n"
            f"  {chr(10).join(sorted(missing))}\n\n"
            "These active commands should be in manifest."
        )

    def test_deprecated_commands_not_in_manifest(self, manifest_commands):
        """Test that deprecated commands are NOT in manifest.

        RED PHASE: May FAIL if deprecated commands still in manifest
        EXPECTATION: None of the deprecated commands are in manifest

        Deprecated commands should be in archive/ directory:
        - align-project.md, align-claude.md, align-project-retrofit.md
        - update-plugin.md, implement.md, research.md, plan.md
        - review.md, test-feature.md, test.md, security-scan.md
        - update-docs.md, pipeline-status.md, status.md
        """
        deprecated_found = manifest_commands & DEPRECATED_COMMANDS
        assert not deprecated_found, (
            f"Found {len(deprecated_found)} deprecated commands in manifest:\n"
            f"  {chr(10).join(sorted(deprecated_found))}\n\n"
            "These commands should NOT be in manifest.\n"
            "They should be archived in commands/archive/ directory.\n"
            "Remove them from components.commands.files in manifest."
        )


class TestManifestHookCompleteness:
    """Test that manifest includes all required hook files."""

    @pytest.fixture
    def manifest_data(self):
        """Load manifest JSON."""
        manifest_path = (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "config"
            / "install_manifest.json"
        )
        with open(manifest_path, "r") as f:
            return json.load(f)

    @pytest.fixture
    def manifest_hooks(self, manifest_data) -> Set[str]:
        """Extract hook filenames from manifest."""
        files = manifest_data.get("components", {}).get("hooks", {}).get("files", [])
        return {Path(f).name for f in files}

    @pytest.fixture
    def disk_hooks(self) -> Set[str]:
        """Get all Python hook files from disk."""
        hooks_dir = project_root / "plugins" / "autonomous-dev" / "hooks"
        if not hooks_dir.exists():
            return set()
        return {f.name for f in hooks_dir.glob("*.py")}

    def test_missing_hooks_added_to_manifest(self, manifest_hooks):
        """Test that the 6 missing hooks from audit are now in manifest.

        RED PHASE: Should FAIL until missing hooks added
        EXPECTATION: detect_feature_request.py, log_agent_completion.py,
                     session_tracker.py, auto_update_project_progress.py,
                     batch_permission_approver.py, unified_pre_tool_use.py
                     are all in manifest
        """
        missing = MISSING_HOOKS - manifest_hooks
        assert not missing, (
            f"Missing {len(missing)} hook files from manifest:\n"
            f"  {chr(10).join(sorted(missing))}\n\n"
            "These hooks were discovered during Issue #159 audit.\n"
            "They exist on disk but are missing from manifest.\n"
            "Add them to components.hooks.files in manifest."
        )

    def test_all_disk_hooks_in_manifest(self, manifest_hooks, disk_hooks):
        """Test that all Python hooks on disk are in manifest.

        RED PHASE: Should FAIL if any disk hooks missing from manifest
        EXPECTATION: Every .py file in hooks/ directory is in manifest
        """
        missing = disk_hooks - manifest_hooks
        assert not missing, (
            f"Found {len(missing)} hook files on disk not in manifest:\n"
            f"  {chr(10).join(sorted(missing))}\n\n"
            "All hook files on disk should be in manifest.\n"
            "Add them to components.hooks.files in manifest."
        )

    def test_no_phantom_hooks_in_manifest(self, manifest_hooks, disk_hooks):
        """Test that manifest doesn't include hooks that don't exist on disk.

        RED PHASE: Should FAIL if manifest contains hooks not on disk
        EXPECTATION: Every manifest hook exists on disk
        """
        phantom = manifest_hooks - disk_hooks
        assert not phantom, (
            f"Found {len(phantom)} hook files in manifest not on disk:\n"
            f"  {chr(10).join(sorted(phantom))}\n\n"
            "These hooks are in manifest but don't exist.\n"
            "Remove them from manifest or create the missing files."
        )


class TestManifestLibCompleteness:
    """Test that manifest includes all required library files."""

    @pytest.fixture
    def manifest_data(self):
        """Load manifest JSON."""
        manifest_path = (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "config"
            / "install_manifest.json"
        )
        with open(manifest_path, "r") as f:
            return json.load(f)

    @pytest.fixture
    def manifest_libs(self, manifest_data) -> Set[str]:
        """Extract lib filenames from manifest."""
        files = manifest_data.get("components", {}).get("lib", {}).get("files", [])
        return {Path(f).name for f in files}

    @pytest.fixture
    def disk_libs(self) -> Set[str]:
        """Get all Python lib files from disk."""
        lib_dir = project_root / "plugins" / "autonomous-dev" / "lib"
        if not lib_dir.exists():
            return set()
        return {f.name for f in lib_dir.glob("*.py")}

    def test_missing_libs_added_to_manifest(self, manifest_libs):
        """Test that the 7 missing libs from audit are now in manifest.

        RED PHASE: Should FAIL until missing libs added
        EXPECTATION: genai_validate.py, math_utils.py, search_utils.py,
                     mcp_profile_manager.py, mcp_server_detector.py,
                     git_hooks.py, validate_documentation_parity.py
                     are all in manifest
        """
        missing = MISSING_LIBS - manifest_libs
        assert not missing, (
            f"Missing {len(missing)} lib files from manifest:\n"
            f"  {chr(10).join(sorted(missing))}\n\n"
            "These libs were discovered during Issue #159 audit.\n"
            "They exist on disk but are missing from manifest.\n"
            "Add them to components.lib.files in manifest."
        )

    def test_all_disk_libs_in_manifest(self, manifest_libs, disk_libs):
        """Test that all Python libs on disk are in manifest.

        RED PHASE: Should FAIL if any disk libs missing from manifest
        EXPECTATION: Every .py file in lib/ directory is in manifest
        """
        missing = disk_libs - manifest_libs
        assert not missing, (
            f"Found {len(missing)} lib files on disk not in manifest:\n"
            f"  {chr(10).join(sorted(missing))}\n\n"
            "All lib files on disk should be in manifest.\n"
            "Add them to components.lib.files in manifest."
        )

    def test_no_phantom_libs_in_manifest(self, manifest_libs, disk_libs):
        """Test that manifest doesn't include libs that don't exist on disk.

        RED PHASE: Should FAIL if manifest contains libs not on disk
        EXPECTATION: Every manifest lib exists on disk
        """
        phantom = manifest_libs - disk_libs
        assert not phantom, (
            f"Found {len(phantom)} lib files in manifest not on disk:\n"
            f"  {chr(10).join(sorted(phantom))}\n\n"
            "These libs are in manifest but don't exist.\n"
            "Remove them from manifest or create the missing files."
        )


class TestManifestVersionBump:
    """Test that manifest version is properly bumped."""

    @pytest.fixture
    def manifest_data(self):
        """Load manifest JSON."""
        manifest_path = (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "config"
            / "install_manifest.json"
        )
        with open(manifest_path, "r") as f:
            return json.load(f)

    def test_version_bumped_from_3_40_0(self, manifest_data):
        """Test that version is bumped from current 3.40.0.

        RED PHASE: Should FAIL if version not bumped
        EXPECTATION: Version > 3.40.0 (suggest 3.41.0 or higher)
        """
        current_version = manifest_data.get("version", "0.0.0")

        # Parse version components
        try:
            major, minor, patch = map(int, current_version.split("."))
        except (ValueError, AttributeError):
            pytest.fail(
                f"Invalid version format in manifest: {current_version}\n"
                "Expected: semantic version (e.g., 3.41.0)"
            )

        # Version should be greater than 3.40.0
        assert (major, minor, patch) > (3, 40, 0), (
            f"Manifest version not bumped: {current_version}\n"
            "Expected: Version > 3.40.0 (e.g., 3.41.0)\n"
            "Issue #159 requires version bump for completeness audit"
        )

    def test_version_format_valid(self, manifest_data):
        """Test that version follows semantic versioning format.

        EXPECTATION: Version in format MAJOR.MINOR.PATCH
        """
        version = manifest_data.get("version", "")
        parts = version.split(".")

        assert len(parts) == 3, (
            f"Version doesn't follow semantic versioning: {version}\n"
            "Expected: MAJOR.MINOR.PATCH (e.g., 3.41.0)"
        )

        for part in parts:
            assert part.isdigit(), (
                f"Version contains non-numeric component: {version}\n"
                f"Invalid part: {part}\n"
                "Expected: All components numeric (e.g., 3.41.0)"
            )

    def test_generated_date_updated(self, manifest_data):
        """Test that 'generated' date is updated.

        EXPECTATION: Date should be recent (not older than current date)
        """
        generated = manifest_data.get("generated", "")

        assert generated, (
            "Manifest missing 'generated' field\n"
            "Expected: Date in YYYY-MM-DD format"
        )

        # Validate date format (YYYY-MM-DD)
        from datetime import datetime
        try:
            date_obj = datetime.strptime(generated, "%Y-%m-%d")
            current_date = datetime.now()

            # Date should not be in the future
            assert date_obj <= current_date, (
                f"Generated date is in the future: {generated}\n"
                "Expected: Date <= current date"
            )
        except ValueError:
            pytest.fail(
                f"Invalid date format in manifest: {generated}\n"
                "Expected: YYYY-MM-DD format (e.g., 2025-12-24)"
            )


class TestManifestPathFormats:
    """Test that all manifest paths follow correct format."""

    @pytest.fixture
    def manifest_data(self):
        """Load manifest JSON."""
        manifest_path = (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "config"
            / "install_manifest.json"
        )
        with open(manifest_path, "r") as f:
            return json.load(f)

    def test_agent_paths_format(self, manifest_data):
        """Test that all agent paths follow expected format.

        EXPECTATION: All paths start with plugins/autonomous-dev/agents/
        """
        files = manifest_data.get("components", {}).get("agents", {}).get("files", [])
        expected_prefix = "plugins/autonomous-dev/agents/"

        invalid = [f for f in files if not f.startswith(expected_prefix)]
        assert not invalid, (
            f"Found {len(invalid)} agent paths with invalid format:\n"
            f"  {chr(10).join(invalid)}\n\n"
            f"Expected all paths to start with: {expected_prefix}"
        )

    def test_command_paths_format(self, manifest_data):
        """Test that all command paths follow expected format.

        EXPECTATION: All paths start with plugins/autonomous-dev/commands/
        """
        files = manifest_data.get("components", {}).get("commands", {}).get("files", [])
        expected_prefix = "plugins/autonomous-dev/commands/"

        invalid = [f for f in files if not f.startswith(expected_prefix)]
        assert not invalid, (
            f"Found {len(invalid)} command paths with invalid format:\n"
            f"  {chr(10).join(invalid)}\n\n"
            f"Expected all paths to start with: {expected_prefix}"
        )

    def test_hook_paths_format(self, manifest_data):
        """Test that all hook paths follow expected format.

        EXPECTATION: All paths start with plugins/autonomous-dev/hooks/
        """
        files = manifest_data.get("components", {}).get("hooks", {}).get("files", [])
        expected_prefix = "plugins/autonomous-dev/hooks/"

        invalid = [f for f in files if not f.startswith(expected_prefix)]
        assert not invalid, (
            f"Found {len(invalid)} hook paths with invalid format:\n"
            f"  {chr(10).join(invalid)}\n\n"
            f"Expected all paths to start with: {expected_prefix}"
        )

    def test_lib_paths_format(self, manifest_data):
        """Test that all lib paths follow expected format.

        EXPECTATION: All paths start with plugins/autonomous-dev/lib/
        """
        files = manifest_data.get("components", {}).get("lib", {}).get("files", [])
        expected_prefix = "plugins/autonomous-dev/lib/"

        invalid = [f for f in files if not f.startswith(expected_prefix)]
        assert not invalid, (
            f"Found {len(invalid)} lib paths with invalid format:\n"
            f"  {chr(10).join(invalid)}\n\n"
            f"Expected all paths to start with: {expected_prefix}"
        )


if __name__ == "__main__":
    # Run with: pytest tests/regression/smoke/test_install_manifest_completeness.py -v
    pytest.main([__file__, "-v"])
