#!/usr/bin/env python3
"""
Tests for Install Manifest Command Configuration

This module verifies that the install manifest
(plugins/autonomous-dev/config/install_manifest.json) contains all active commands.

Requirements:
1. Manifest contains all active command files (23 as of v3.44.0)
2. Manifest includes both unified commands and individual agent commands
3. All active commands are listed with correct paths
4. Manifest structure is valid JSON

Author: test-master agent
Date: 2025-12-13, Updated: 2026-01-02
Issue: #121, Updated for current command count
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

    def test_manifest_has_commands_section(self, manifest_data):
        """Test that manifest has 'commands' section.

        RED PHASE: Should fail if commands section missing
        EXPECTATION: manifest_data['components']['commands'] exists
        """
        assert "components" in manifest_data, (
            "Manifest missing 'components' section\n"
            "Expected: manifest['components']['commands'] section"
        )
        assert "commands" in manifest_data["components"], (
            "Manifest missing 'commands' in components\n"
            "Expected: manifest['components']['commands'] section"
        )

    def test_manifest_commands_has_files(self, manifest_data):
        """Test that commands section has 'files' array.

        RED PHASE: Should fail if files array missing
        EXPECTATION: manifest_data['components']['commands']['files'] is list
        """
        commands = manifest_data.get("components", {}).get("commands", {})
        assert "files" in commands, (
            "Commands section missing 'files' array\n"
            "Expected: manifest['components']['commands']['files']"
        )
        assert isinstance(commands["files"], list), (
            "Commands files is not a list\n"
            f"Expected: array, got: {type(commands['files'])}"
        )


class TestManifestCommandCount:
    """Test that manifest lists all active commands."""

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
    def command_files(self, manifest_data) -> List[str]:
        """Extract command file paths from manifest."""
        return manifest_data.get("components", {}).get("commands", {}).get("files", [])

    def test_manifest_has_23_commands(self, command_files):
        """Test that manifest lists all 23 active command files.

        EXPECTATION: Exactly 23 command paths in manifest

        Active commands include:
        - Core: auto-implement, batch-implement, setup, sync, health-check
        - Alignment: align, align-project, align-claude, align-project-retrofit
        - Individual agents: research, plan, test-feature, implement, review, etc.
        - Utility: advise, create-issue, status, worktree, etc.
        """
        assert len(command_files) == 23, (
            f"Expected 23 command files in manifest, found {len(command_files)}\n"
            f"Actual files: {sorted([Path(f).name for f in command_files])}\n"
        )

    def test_manifest_command_paths_format(self, command_files):
        """Test that all command paths follow expected format.

        RED PHASE: Should fail if paths don't match pattern
        EXPECTATION: All paths follow: plugins/autonomous-dev/commands/*.md
        """
        expected_prefix = "plugins/autonomous-dev/commands/"
        invalid_paths = [f for f in command_files if not f.startswith(expected_prefix)]

        assert not invalid_paths, (
            f"Invalid command paths found: {invalid_paths}\n"
            f"Expected all paths to start with: {expected_prefix}\n"
            f"Fix: Update manifest paths to correct format"
        )


class TestManifestIncludesAlignCommand:
    """Test that manifest includes the new unified 'align' command."""

    @pytest.fixture
    def command_files(self) -> List[str]:
        """Extract command file paths from manifest."""
        manifest_path = (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "config"
            / "install_manifest.json"
        )
        with open(manifest_path, "r") as f:
            data = json.load(f)
            return data.get("components", {}).get("commands", {}).get("files", [])

    def test_includes_align_command(self, command_files):
        """Test that manifest includes align.md command.

        RED PHASE: Should fail until align.md added to manifest
        EXPECTATION: "plugins/autonomous-dev/commands/align.md" in files list

        RATIONALE: Issue #121 consolidates align-project, align-claude, and
                   align-project-retrofit into single /align command.
        """
        align_paths = [f for f in command_files if "/align.md" in f]
        assert align_paths, (
            f"align.md not found in manifest commands\n"
            f"Expected: plugins/autonomous-dev/commands/align.md\n"
            f"Actual files: {command_files}\n"
            "Fix: Add align.md to manifest under components.commands.files\n"
            "Note: align.md replaces align-project.md, align-claude.md, "
            "and align-project-retrofit.md"
        )

    def test_align_command_singular_instance(self, command_files):
        """Test that align command appears exactly once in manifest.

        RED PHASE: Should fail if duplicate align entries exist
        EXPECTATION: Exactly one path containing '/align.md'
        """
        align_paths = [f for f in command_files if "/align.md" in f]
        assert len(align_paths) == 1, (
            f"Expected 1 align.md entry, found {len(align_paths)}\n"
            f"Duplicate entries: {align_paths}\n"
            "Fix: Remove duplicate align.md entries from manifest"
        )


class TestManifestIncludesAgentCommands:
    """Test that manifest includes individual agent commands for convenience."""

    @pytest.fixture
    def command_files(self) -> List[str]:
        """Extract command file paths from manifest."""
        manifest_path = (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "config"
            / "install_manifest.json"
        )
        with open(manifest_path, "r") as f:
            data = json.load(f)
            return data.get("components", {}).get("commands", {}).get("files", [])

    def test_includes_individual_agent_commands(self, command_files):
        """Test that individual agent commands are in manifest.

        These provide quick access to individual pipeline stages.
        """
        agent_commands = {
            "research.md",
            "plan.md",
            "test-feature.md",
            "implement.md",
            "review.md",
            "security-scan.md",
            "update-docs.md",
        }

        manifest_commands = {Path(f).name for f in command_files}
        found_agents = agent_commands & manifest_commands

        assert found_agents == agent_commands, (
            f"Missing individual agent commands: {agent_commands - found_agents}\n"
            "These should be included for quick access to pipeline stages"
        )

    def test_includes_utility_commands(self, command_files):
        """Test that utility commands are in manifest."""
        utility_commands = {
            "update-plugin.md",
            "status.md",
            "pipeline-status.md",
            "test.md",
        }

        manifest_commands = {Path(f).name for f in command_files}
        found_utils = utility_commands & manifest_commands

        assert found_utils == utility_commands, (
            f"Missing utility commands: {utility_commands - found_utils}\n"
        )

    def test_includes_batch_implement(self, command_files):
        """Test that batch-implement command is in manifest.

        EXPECTATION: batch-implement.md IS in files list
        """
        manifest_commands = {Path(f).name for f in command_files}

        assert "batch-implement.md" in manifest_commands, (
            f"batch-implement.md missing from manifest\n"
            "This should be included for multi-feature processing\n"
        )

    def test_includes_align_commands(self, command_files):
        """Test that all align commands are in manifest.

        Both unified and individual align commands are active.
        """
        align_commands = {
            "align.md",
            "align-project.md",
            "align-claude.md",
            "align-project-retrofit.md",
        }

        manifest_commands = {Path(f).name for f in command_files}
        found_align = align_commands & manifest_commands

        assert found_align == align_commands, (
            f"Missing align commands: {align_commands - found_align}\n"
        )


class TestManifestActiveCommandsPaths:
    """Test that manifest includes correct paths for all active commands."""

    @pytest.fixture
    def command_files(self) -> List[str]:
        """Extract command file paths from manifest."""
        manifest_path = (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "config"
            / "install_manifest.json"
        )
        with open(manifest_path, "r") as f:
            data = json.load(f)
            return data.get("components", {}).get("commands", {}).get("files", [])

    def _check_command_in_manifest(self, command_files: List[str], filename: str) -> bool:
        """Helper: Check if command file is in manifest."""
        expected_path = f"plugins/autonomous-dev/commands/{filename}"
        return expected_path in command_files

    def test_auto_implement_in_manifest(self, command_files):
        """Test that auto-implement.md is in manifest."""
        assert self._check_command_in_manifest(
            command_files, "auto-implement.md"
        ), (
            "auto-implement.md not in manifest\n"
            "Expected: plugins/autonomous-dev/commands/auto-implement.md"
        )

    def test_setup_in_manifest(self, command_files):
        """Test that setup.md is in manifest."""
        assert self._check_command_in_manifest(command_files, "setup.md"), (
            "setup.md not in manifest\n"
            "Expected: plugins/autonomous-dev/commands/setup.md"
        )

    def test_sync_in_manifest(self, command_files):
        """Test that sync.md is in manifest."""
        assert self._check_command_in_manifest(command_files, "sync.md"), (
            "sync.md not in manifest\n"
            "Expected: plugins/autonomous-dev/commands/sync.md"
        )

    def test_health_check_in_manifest(self, command_files):
        """Test that health-check.md is in manifest."""
        assert self._check_command_in_manifest(command_files, "health-check.md"), (
            "health-check.md not in manifest\n"
            "Expected: plugins/autonomous-dev/commands/health-check.md"
        )

    def test_batch_implement_in_manifest(self, command_files):
        """Test that batch-implement.md is in manifest."""
        assert self._check_command_in_manifest(command_files, "batch-implement.md"), (
            "batch-implement.md not in manifest\n"
            "Expected: plugins/autonomous-dev/commands/batch-implement.md"
        )

    def test_create_issue_in_manifest(self, command_files):
        """Test that create-issue.md is in manifest."""
        assert self._check_command_in_manifest(command_files, "create-issue.md"), (
            "create-issue.md not in manifest\n"
            "Expected: plugins/autonomous-dev/commands/create-issue.md"
        )


if __name__ == "__main__":
    # Run with: pytest tests/unit/test_install_manifest_commands.py -v
    pytest.main([__file__, "-v"])
