#!/usr/bin/env python3
"""
TDD Tests for Install Manifest Command Configuration - Issue #121

This module contains FAILING tests (RED phase) for verifying that the install
manifest (plugins/autonomous-dev/config/install_manifest.json) reflects the
simplified command structure (8 active commands).

Requirements (Issue #121):
1. Manifest contains exactly 8 command files
2. Manifest includes the new unified 'align' command
3. Manifest excludes all archived commands (13 commands)
4. All active commands are listed with correct paths

This test suite follows TDD principles:
- Tests written FIRST before manifest is updated
- Tests SHOULD FAIL until manifest updated
- Tests validate manifest structure, not command functionality

Author: test-master agent
Date: 2025-12-13
Issue: #121
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Set

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestInstallManifestStructure:
    """Test that install manifest exists and has correct structure."""

    @pytest.fixture
    def manifest_path(self):
        """Get path to install manifest."""
        return (
            Path(__file__).parent.parent.parent
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
    """Test that manifest lists exactly 8 active commands."""

    @pytest.fixture
    def manifest_data(self):
        """Load manifest JSON."""
        manifest_path = (
            Path(__file__).parent.parent.parent
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

    def test_manifest_has_9_commands(self, command_files):
        """Test that manifest lists exactly 9 command files.

        EXPECTATION: Exactly 9 command paths in manifest

        This validates the active commands:
        - 8 core workflow commands + 1 utility = 9 total
        - Archived: 12 commands (moved to commands/archive/)

        Active commands:
        * auto-implement
        * create-issue (enhanced in Issue #122)
        * align (unified)
        * setup
        * sync
        * status
        * health-check
        * pipeline-status
        * test
        """
        assert len(command_files) == 9, (
            f"Expected 9 command files in manifest, found {len(command_files)}\n"
            f"Actual files: {command_files}\n"
            "Expected 9 active commands:\n"
            "  1. auto-implement.md\n"
            "  2. create-issue.md\n"
            "  3. align.md (unified)\n"
            "  4. setup.md\n"
            "  5. sync.md\n"
            "  6. status.md\n"
            "  7. health-check.md\n"
            "  8. pipeline-status.md\n"
            "  9. test.md (utility)\n"
            "Archived (12): All others moved to commands/archive/\n"
            "See GitHub Issues #121, #122 for details"
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
            Path(__file__).parent.parent.parent
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


class TestManifestExcludesArchivedCommands:
    """Test that manifest excludes all 13 archived commands."""

    @pytest.fixture
    def command_files(self) -> List[str]:
        """Extract command file paths from manifest."""
        manifest_path = (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "config"
            / "install_manifest.json"
        )
        with open(manifest_path, "r") as f:
            data = json.load(f)
            return data.get("components", {}).get("commands", {}).get("files", [])

    def test_excludes_individual_agent_commands(self, command_files):
        """Test that individual agent commands excluded from manifest.

        RED PHASE: Should fail if individual agent commands still in manifest
        EXPECTATION: research, plan, test-feature, implement, review,
                     security-scan, update-docs NOT in files list

        RATIONALE: These are consolidated into /auto-implement and /align.
        """
        archived_agents = {
            "research.md",
            "plan.md",
            "test-feature.md",
            "implement.md",
            "review.md",
            "security-scan.md",
            "update-docs.md",
        }

        manifest_commands = {Path(f).name for f in command_files}
        found_archived = archived_agents & manifest_commands

        assert not found_archived, (
            f"Individual agent commands still in manifest: {found_archived}\n"
            "These should be removed (functionality in /auto-implement):\n"
            f"  {chr(10).join(sorted(found_archived))}\n"
            "Rationale: Consolidated into /auto-implement pipeline"
        )

    def test_excludes_utility_commands(self, command_files):
        """Test that utility commands excluded from manifest.

        RED PHASE: Should fail if utility commands still in manifest
        EXPECTATION: create-issue, update-plugin NOT in files list
        """
        archived_utilities = {
            "create-issue.md",
            "update-plugin.md",
        }

        manifest_commands = {Path(f).name for f in command_files}
        found_archived = archived_utilities & manifest_commands

        assert not found_archived, (
            f"Utility commands still in manifest: {found_archived}\n"
            "These should be removed:\n"
            f"  {chr(10).join(sorted(found_archived))}\n"
            "Rationale: Superseded by core workflow commands"
        )

    def test_excludes_batch_implement(self, command_files):
        """Test that batch-implement command excluded from manifest.

        RED PHASE: Should fail if batch-implement still in manifest
        EXPECTATION: batch-implement.md NOT in files list
        """
        manifest_commands = {Path(f).name for f in command_files}

        assert "batch-implement.md" not in manifest_commands, (
            f"batch-implement.md still in manifest\n"
            "This should be removed\n"
            "Rationale: Functionality consolidated into /auto-implement --batch"
        )

    def test_excludes_old_align_commands(self, command_files):
        """Test that old align commands excluded from manifest.

        RED PHASE: Should fail if old align commands still in manifest
        EXPECTATION: align-project, align-claude, align-project-retrofit NOT in files
        """
        old_align_commands = {
            "align-project.md",
            "align-claude.md",
            "align-project-retrofit.md",
        }

        manifest_commands = {Path(f).name for f in command_files}
        found_archived = old_align_commands & manifest_commands

        assert not found_archived, (
            f"Old align commands still in manifest: {found_archived}\n"
            "These should be removed and replaced with unified align.md:\n"
            f"  {chr(10).join(sorted(found_archived))}\n"
            "Use: /align --project | /align --claude | /align --retrofit instead"
        )


class TestManifestActiveCommandsPaths:
    """Test that manifest includes correct paths for all active commands."""

    @pytest.fixture
    def command_files(self) -> List[str]:
        """Extract command file paths from manifest."""
        manifest_path = (
            Path(__file__).parent.parent.parent
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

    def test_status_in_manifest(self, command_files):
        """Test that status.md is in manifest."""
        assert self._check_command_in_manifest(command_files, "status.md"), (
            "status.md not in manifest\n"
            "Expected: plugins/autonomous-dev/commands/status.md"
        )

    def test_health_check_in_manifest(self, command_files):
        """Test that health-check.md is in manifest."""
        assert self._check_command_in_manifest(command_files, "health-check.md"), (
            "health-check.md not in manifest\n"
            "Expected: plugins/autonomous-dev/commands/health-check.md"
        )

    def test_pipeline_status_in_manifest(self, command_files):
        """Test that pipeline-status.md is in manifest."""
        assert self._check_command_in_manifest(command_files, "pipeline-status.md"), (
            "pipeline-status.md not in manifest\n"
            "Expected: plugins/autonomous-dev/commands/pipeline-status.md"
        )

    def test_test_command_in_manifest(self, command_files):
        """Test that test.md is in manifest."""
        assert self._check_command_in_manifest(command_files, "test.md"), (
            "test.md not in manifest\n"
            "Expected: plugins/autonomous-dev/commands/test.md"
        )


if __name__ == "__main__":
    # Run with: pytest tests/unit/test_install_manifest_commands.py -v
    pytest.main([__file__, "-v"])
