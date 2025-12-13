#!/usr/bin/env python3
"""
TDD Tests for Command Archive Structure - Issue #121

This module contains FAILING tests (RED phase) for the command simplification
from 20 to 8 active commands. Tests verify that archived commands are properly
organized and documented.

Requirements (Issue #121):
1. Archive directory structure exists at plugins/autonomous-dev/commands/archive/
2. Exactly 13 commands should be archived (20 total - 7 remaining active)
3. Archive README documents archived commands and migration path
4. All archived commands have proper documentation

This test suite follows TDD principles:
- Tests are written FIRST (before implementation)
- Tests SHOULD FAIL until archive structure is properly implemented
- Tests validate the STRUCTURE of the archive, not its content

Author: test-master agent
Date: 2025-12-13
Issue: #121
"""

import os
import sys
import json
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestArchiveDirectoryStructure:
    """Test that command archive directory structure exists and is properly organized."""

    @pytest.fixture
    def commands_dir(self):
        """Get path to commands directory."""
        return Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "commands"

    @pytest.fixture
    def archive_dir(self, commands_dir):
        """Get path to archive directory."""
        return commands_dir / "archive"

    def test_archive_directory_exists(self, archive_dir):
        """Test that archive directory exists.

        RED PHASE: Should fail if archive directory not found
        EXPECTATION: Directory exists at plugins/autonomous-dev/commands/archive/
        """
        assert archive_dir.exists(), (
            f"Archive directory not found at {archive_dir}\n"
            "Expected: plugins/autonomous-dev/commands/archive/ directory"
        )

    def test_archive_is_directory(self, archive_dir):
        """Test that archive path is actually a directory.

        RED PHASE: Should fail if archive is not a directory
        EXPECTATION: Path is a valid directory, not a file
        """
        assert archive_dir.is_dir(), (
            f"Archive path exists but is not a directory: {archive_dir}\n"
            "Expected: directory, got: {archive_dir.stat().st_mode}"
        )

    def test_archive_directory_readable(self, archive_dir):
        """Test that archive directory is readable.

        RED PHASE: Should fail if directory permissions are incorrect
        EXPECTATION: Directory has read permissions
        """
        assert os.access(archive_dir, os.R_OK), (
            f"Archive directory is not readable: {archive_dir}\n"
            "Fix: Check directory permissions"
        )

    def test_archive_readme_exists(self, archive_dir):
        """Test that archive has documentation (README).

        RED PHASE: Should fail until README is created
        EXPECTATION: README.md exists in archive directory explaining archived commands
        CONTEXT: Archive should document:
            - Why commands were archived
            - Migration path for users
            - How to restore archived commands if needed
        """
        readme_path = archive_dir / "README.md"
        assert readme_path.exists(), (
            f"Archive README not found at {readme_path}\n"
            "Expected: plugins/autonomous-dev/commands/archive/README.md\n"
            "Content should document:\n"
            "  1. Why commands were archived\n"
            "  2. Which commands are archived\n"
            "  3. Migration path for users\n"
            "  4. How to restore if needed"
        )

    def test_archive_readme_is_file(self, archive_dir):
        """Test that archive README is a file, not directory.

        RED PHASE: Should fail if README is mistyped as directory
        EXPECTATION: README.md is a file
        """
        readme_path = archive_dir / "README.md"
        assert readme_path.is_file(), (
            f"Archive README exists but is not a file: {readme_path}\n"
            f"Is directory: {readme_path.is_dir()}\n"
            "Expected: plugins/autonomous-dev/commands/archive/README.md (file)"
        )


class TestArchivedCommandsPresent:
    """Test that all archived commands are present in the archive directory."""

    @pytest.fixture
    def archive_dir(self):
        """Get path to archive directory."""
        return (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "commands"
            / "archive"
        )

    def test_archived_commands_count(self, archive_dir):
        """Test that exactly 13 commands are archived.

        RED PHASE: Should fail until all commands are moved to archive
        EXPECTATION: 13 .md files in archive/ (20 total - 8 active = 13 archived, excluding pre-existing uninstall.md)

        Breakdown:
        - Active (8): auto-implement, align, setup, sync, status, health-check, pipeline-status, test
        - Archived (13): All others moved to archive/ (not counting pre-existing files like uninstall.md)
        """
        # Count .md files in archive (excluding README.md and pre-existing files like uninstall.md)
        md_files = [f for f in archive_dir.glob("*.md") if f.name not in ["README.md", "uninstall.md"]]
        archived_count = len(md_files)

        assert archived_count == 13, (
            f"Expected 13 archived commands, found {archived_count}\n"
            f"Archived files: {[f.name for f in md_files]}\n"
            "Expected breakdown:\n"
            "  - Active (8): auto-implement, align, setup, sync, status, health-check, pipeline-status, test\n"
            "  - Archived (13): All remaining commands\n"
            "Math: 20 total commands - 8 active = 13 archived (excluding pre-existing uninstall.md)"
        )

    def test_individual_agent_commands_archived(self, archive_dir):
        """Test that individual agent commands are archived.

        RED PHASE: Should fail until individual agent commands moved
        EXPECTATION: research, plan, test-feature, implement, review, security-scan,
                     update-docs archived (7 commands)

        RATIONALE: Issue #121 consolidates into /auto-implement and /align commands.
                   Individual agent commands are redundant with unified commands.
        """
        expected_archived = {
            "research.md",
            "plan.md",
            "test-feature.md",
            "implement.md",
            "review.md",
            "security-scan.md",
            "update-docs.md",
        }

        archived_files = {f.name for f in archive_dir.glob("*.md") if f.name != "README.md"}

        missing = expected_archived - archived_files
        assert not missing, (
            f"Some individual agent commands not archived: {missing}\n"
            "Expected these to be moved to archive/:\n"
            f"  {chr(10).join(sorted(expected_archived))}\n"
            "Rationale: Consolidated into /auto-implement and /align commands"
        )

    def test_utility_commands_archived(self, archive_dir):
        """Test that utility commands are archived.

        RED PHASE: Should fail until utility commands moved
        EXPECTATION: create-issue, update-plugin archived (2 commands)
        NOTE: test.md remains active as one of the 8 core commands

        RATIONALE: create-issue and update-plugin are superseded by core workflow commands.
                   test.md remains active as a utility command for running tests.
        """
        expected_archived_utilities = {
            "create-issue.md",
            "update-plugin.md",
        }

        archived_files = {f.name for f in archive_dir.glob("*.md") if f.name != "README.md"}

        missing = expected_archived_utilities - archived_files
        assert not missing, (
            f"Some utility commands not archived: {missing}\n"
            "Expected these to be moved to archive/:\n"
            f"  {chr(10).join(sorted(expected_archived_utilities))}\n"
            "Rationale: Superseded by core workflow commands\n"
            "Note: test.md remains active (not archived)"
        )

    def test_batch_implement_archived(self, archive_dir):
        """Test that batch-implement command is archived.

        RED PHASE: Should fail until batch-implement moved
        EXPECTATION: batch-implement.md in archive/

        RATIONALE: batch-implement functionality consolidated into /auto-implement
                   via --batch flag and context management improvements.
        """
        batch_cmd = archive_dir / "batch-implement.md"
        assert batch_cmd.exists(), (
            f"batch-implement.md not found in archive\n"
            f"Expected: {batch_cmd}\n"
            "Rationale: Consolidated into /auto-implement --batch functionality"
        )

    def test_align_project_retrofit_archived(self, archive_dir):
        """Test that align-project-retrofit is archived.

        RED PHASE: Should fail until align-project-retrofit moved
        EXPECTATION: align-project-retrofit.md in archive/

        RATIONALE: Functionality consolidated into unified /align command
                   with --retrofit flag.
        """
        retrofit_cmd = archive_dir / "align-project-retrofit.md"
        assert retrofit_cmd.exists(), (
            f"align-project-retrofit.md not found in archive\n"
            f"Expected: {retrofit_cmd}\n"
            "Rationale: Consolidated into /align --retrofit functionality"
        )


class TestActiveCommandsCount:
    """Test that exactly 8 active commands remain after simplification."""

    @pytest.fixture
    def commands_dir(self):
        """Get path to commands directory (excluding archive subdirs)."""
        return (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "commands"
        )

    def test_active_commands_count(self, commands_dir):
        """Test that exactly 8 active commands remain.

        RED PHASE: Should fail until non-archived commands = 8
        EXPECTATION: 8 .md files in commands/ (excluding archive/ subdirectory)

        Active commands (8):
        1. auto-implement.md    - Full pipeline automation
        2. align.md              - Unified alignment command (project/claude/retrofit)
        3. setup.md              - Interactive project setup
        4. sync.md               - Smart sync (dev/marketplace/plugin-dev)
        5. status.md             - Project progress tracking
        6. health-check.md       - Plugin integrity validation
        7. pipeline-status.md    - /auto-implement workflow tracking
        """
        # Get .md files in commands/ but NOT in subdirectories
        md_files = list(commands_dir.glob("*.md"))
        active_count = len(md_files)

        assert active_count == 8, (
            f"Expected 8 active commands, found {active_count}\n"
            f"Active files: {sorted([f.name for f in md_files])}\n"
            "Expected active commands (8):\n"
            "  1. auto-implement.md\n"
            "  2. align.md\n"
            "  3. setup.md\n"
            "  4. sync.md\n"
            "  5. status.md\n"
            "  6. health-check.md\n"
            "  7. pipeline-status.md\n"
            f"Math: 20 original - 13 archived = 8 active\n"
            "See docs/COMMAND-SIMPLIFICATION.md for migration guide"
        )

    def test_auto_implement_active(self, commands_dir):
        """Test that auto-implement command is active."""
        cmd = commands_dir / "auto-implement.md"
        assert cmd.exists() and cmd.is_file(), (
            f"auto-implement.md not found or not a file\n"
            f"Expected: {cmd}\n"
            "Role: Full pipeline automation (research → test → implement → review → docs)"
        )

    def test_align_command_active(self, commands_dir):
        """Test that unified align command is active.

        RED PHASE: Should fail until align.md exists
        EXPECTATION: align.md file (unified command replacing align-project, align-claude,
                                    align-project-retrofit)
        """
        cmd = commands_dir / "align.md"
        assert cmd.exists() and cmd.is_file(), (
            f"align.md not found or not a file\n"
            f"Expected: {cmd}\n"
            "Role: Unified alignment command\n"
            "Modes: --project (align PROJECT.md), --claude (fix doc drift), --retrofit (brownfield)"
        )

    def test_setup_command_active(self, commands_dir):
        """Test that setup command is active."""
        cmd = commands_dir / "setup.md"
        assert cmd.exists() and cmd.is_file(), (
            f"setup.md not found or not a file\n"
            f"Expected: {cmd}\n"
            "Role: Interactive project setup wizard"
        )

    def test_sync_command_active(self, commands_dir):
        """Test that sync command is active."""
        cmd = commands_dir / "sync.md"
        assert cmd.exists() and cmd.is_file(), (
            f"sync.md not found or not a file\n"
            f"Expected: {cmd}\n"
            "Role: Smart sync (auto-detection: dev environment, marketplace, or plugin-dev)"
        )

    def test_status_command_active(self, commands_dir):
        """Test that status command is active."""
        cmd = commands_dir / "status.md"
        assert cmd.exists() and cmd.is_file(), (
            f"status.md not found or not a file\n"
            f"Expected: {cmd}\n"
            "Role: Project progress tracking and reporting"
        )

    def test_health_check_command_active(self, commands_dir):
        """Test that health-check command is active."""
        cmd = commands_dir / "health-check.md"
        assert cmd.exists() and cmd.is_file(), (
            f"health-check.md not found or not a file\n"
            f"Expected: {cmd}\n"
            "Role: Plugin integrity validation and marketplace version check"
        )

    def test_pipeline_status_command_active(self, commands_dir):
        """Test that pipeline-status command is active."""
        cmd = commands_dir / "pipeline-status.md"
        assert cmd.exists() and cmd.is_file(), (
            f"pipeline-status.md not found or not a file\n"
            f"Expected: {cmd}\n"
            "Role: Track /auto-implement workflow execution and status"
        )


if __name__ == "__main__":
    # Run with: pytest tests/unit/test_command_archive.py -v
    pytest.main([__file__, "-v"])
