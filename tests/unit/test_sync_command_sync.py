#!/usr/bin/env python3
"""
TDD Tests for /sync Command File Synchronization - Issue #202

This module contains FAILING tests (RED phase) to verify that the sync.md
command file is properly synchronized between source and installed locations.

Requirements (Issue #202):
1. Source file (plugins/autonomous-dev/commands/sync.md) exists
2. Installed file (.claude/commands/sync.md) exists after installation
3. Both files have identical content (byte-for-byte match)
4. Install manifest includes sync.md in commands list
5. Sync command is properly listed in command registry

This test suite follows TDD principles:
- Tests written FIRST before implementation
- Tests SHOULD FAIL until sync.md is properly synchronized
- Tests validate installation integrity

Background:
The /sync command file must be synchronized between the plugin directory
and the installed location. These tests ensure the installation process
correctly handles the sync command.

Author: test-master agent
Date: 2026-01-08
Issue: #202
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

import pytest

# Portable path detection (works from any directory)
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


class TestSyncCommandSourceFile:
    """Test that sync command source file exists and is valid."""

    @pytest.fixture
    def source_sync_path(self):
        """Get path to source sync.md file."""
        return (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "commands"
            / "sync.md"
        )

    def test_source_sync_exists(self, source_sync_path):
        """Test that source sync.md exists.

        RED PHASE: Should fail if source file not found
        EXPECTATION: File at plugins/autonomous-dev/commands/sync.md
        """
        assert source_sync_path.exists(), (
            f"Source sync.md not found\n"
            f"Expected: {source_sync_path}\n"
            "This is the canonical sync command file"
        )

    def test_source_sync_is_file(self, source_sync_path):
        """Test that source sync is a file.

        RED PHASE: Should fail if sync is a directory
        EXPECTATION: sync.md is a regular file
        """
        assert source_sync_path.is_file(), (
            f"Source sync path is not a file\n"
            f"Path: {source_sync_path}\n"
            "Expected: Regular markdown file"
        )

    def test_source_sync_not_empty(self, source_sync_path):
        """Test that source sync is not empty.

        RED PHASE: Should fail if file is empty
        EXPECTATION: File has content (size > 0)
        """
        file_size = source_sync_path.stat().st_size
        assert file_size > 0, (
            f"Source sync.md is empty\n"
            f"Path: {source_sync_path}\n"
            "Expected: Non-empty file"
        )


class TestSyncCommandInstalledFile:
    """Test that sync command is installed to .claude/commands/."""

    @pytest.fixture
    def installed_sync_path(self):
        """Get path to installed sync.md file."""
        return project_root / ".claude" / "commands" / "sync.md"

    @pytest.fixture
    def claude_commands_dir(self):
        """Get path to .claude/commands directory."""
        return project_root / ".claude" / "commands"

    def test_claude_commands_dir_exists(self, claude_commands_dir):
        """Test that .claude/commands directory exists.

        RED PHASE: Should fail if directory not found
        EXPECTATION: Directory at .claude/commands/
        """
        assert claude_commands_dir.exists(), (
            f".claude/commands directory not found\n"
            f"Expected: {claude_commands_dir}\n"
            "Context: Plugin installation should create this directory"
        )

    def test_installed_sync_exists(self, installed_sync_path):
        """Test that installed sync.md exists.

        RED PHASE: Should fail if installed file not found
        EXPECTATION: File at .claude/commands/sync.md
        """
        assert installed_sync_path.exists(), (
            f"Installed sync.md not found\n"
            f"Expected: {installed_sync_path}\n"
            "Context: sync.md should be installed during plugin installation"
        )

    def test_installed_sync_is_file(self, installed_sync_path):
        """Test that installed sync is a file.

        RED PHASE: Should fail if sync is a directory
        EXPECTATION: sync.md is a regular file
        """
        if installed_sync_path.exists():
            assert installed_sync_path.is_file(), (
                f"Installed sync path is not a file\n"
                f"Path: {installed_sync_path}\n"
                "Expected: Regular markdown file"
            )

    def test_installed_sync_not_empty(self, installed_sync_path):
        """Test that installed sync is not empty.

        RED PHASE: Should fail if file is empty
        EXPECTATION: File has content (size > 0)
        """
        if installed_sync_path.exists():
            file_size = installed_sync_path.stat().st_size
            assert file_size > 0, (
                f"Installed sync.md is empty\n"
                f"Path: {installed_sync_path}\n"
                "Expected: Non-empty file"
            )


class TestSyncCommandContentMatch:
    """Test that source and installed sync files have identical content."""

    @pytest.fixture
    def source_sync_path(self):
        """Get path to source sync.md file."""
        return (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "commands"
            / "sync.md"
        )

    @pytest.fixture
    def installed_sync_path(self):
        """Get path to installed sync.md file."""
        return project_root / ".claude" / "commands" / "sync.md"

    @pytest.fixture
    def source_content(self, source_sync_path):
        """Read source sync.md content."""
        with open(source_sync_path, "r") as f:
            return f.read()

    @pytest.fixture
    def installed_content(self, installed_sync_path):
        """Read installed sync.md content."""
        if not installed_sync_path.exists():
            pytest.skip("Installed sync.md not found (run installation first)")

        with open(installed_sync_path, "r") as f:
            return f.read()

    def test_content_identical(self, source_content, installed_content):
        """Test that source and installed files have identical content.

        RED PHASE: Should fail if content doesn't match
        EXPECTATION: Byte-for-byte identical content
        """
        assert source_content == installed_content, (
            "Source and installed sync.md content differs\n"
            "Expected: Identical content\n"
            "Fix: Re-run installation or sync command"
        )

    def test_same_file_size(self, source_sync_path, installed_sync_path):
        """Test that source and installed files have same size.

        RED PHASE: Should fail if file sizes differ
        EXPECTATION: Same file size in bytes
        """
        if not installed_sync_path.exists():
            pytest.skip("Installed sync.md not found (run installation first)")

        source_size = source_sync_path.stat().st_size
        installed_size = installed_sync_path.stat().st_size

        assert source_size == installed_size, (
            f"File sizes differ\n"
            f"Source: {source_size} bytes\n"
            f"Installed: {installed_size} bytes\n"
            "Expected: Same file size"
        )

    def test_same_line_count(self, source_content, installed_content):
        """Test that source and installed files have same line count.

        RED PHASE: Should fail if line counts differ
        EXPECTATION: Same number of lines
        """
        source_lines = source_content.splitlines()
        installed_lines = installed_content.splitlines()

        assert len(source_lines) == len(installed_lines), (
            f"Line counts differ\n"
            f"Source: {len(source_lines)} lines\n"
            f"Installed: {len(installed_lines)} lines\n"
            "Expected: Same line count"
        )


class TestSyncCommandManifestEntry:
    """Test that sync command is listed in install manifest."""

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

    @pytest.fixture
    def command_files(self, manifest_data) -> List[str]:
        """Extract command files list from manifest.

        RED PHASE: Should fail if commands section malformed
        EXPECTATION: manifest['components']['commands']['files'] exists
        """
        components = manifest_data.get("components", {})
        commands = components.get("commands", {})
        files = commands.get("files", [])

        assert isinstance(files, list), (
            f"Command files is not a list: {type(files)}\n"
            "Expected: Array of command file paths"
        )

        return files

    def test_manifest_includes_sync_command(self, command_files):
        """Test that manifest includes sync.md in commands list.

        RED PHASE: Should fail if sync.md not in manifest
        EXPECTATION: 'sync.md' in command files list
        """
        # Look for sync.md in any form (with or without path)
        sync_entries = [
            f for f in command_files
            if "sync.md" in f
        ]

        assert len(sync_entries) > 0, (
            f"sync.md not found in install manifest\n"
            f"Command files: {command_files}\n"
            "Expected: sync.md in manifest['components']['commands']['files']"
        )

    def test_sync_command_path_correct(self, command_files):
        """Test that sync.md has correct path in manifest.

        RED PHASE: Should fail if path is wrong
        EXPECTATION: Path is 'plugins/autonomous-dev/commands/sync.md'
        """
        sync_entries = [
            f for f in command_files
            if "sync.md" in f
        ]

        # Should be the full path format used by all commands
        assert "plugins/autonomous-dev/commands/sync.md" in sync_entries, (
            f"sync.md has wrong path in manifest\n"
            f"Found: {sync_entries}\n"
            "Expected: 'plugins/autonomous-dev/commands/sync.md' (full path format)"
        )


class TestSyncCommandRegistry:
    """Test that sync command is recognized in command registry."""

    @pytest.fixture
    def commands_dir(self):
        """Get path to commands directory."""
        return (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "commands"
        )

    @pytest.fixture
    def command_list(self, commands_dir) -> List[str]:
        """Get list of all command files."""
        return [f.name for f in commands_dir.glob("*.md")]

    def test_sync_in_command_list(self, command_list):
        """Test that sync.md is in commands directory.

        RED PHASE: Should fail if sync.md not found
        EXPECTATION: 'sync.md' in command file list
        """
        assert "sync.md" in command_list, (
            f"sync.md not found in commands directory\n"
            f"Available commands: {sorted(command_list)}\n"
            "Expected: sync.md in plugins/autonomous-dev/commands/"
        )

    def test_only_one_sync_command(self, command_list):
        """Test that there's only one sync command file.

        RED PHASE: Should fail if multiple sync files found
        EXPECTATION: Exactly one sync.md file
        """
        sync_files = [f for f in command_list if f.startswith("sync")]

        assert len(sync_files) == 1, (
            f"Multiple sync command files found: {sync_files}\n"
            "Expected: Only sync.md (no sync-*.md variants)"
        )


# Checkpoint integration
if __name__ == "__main__":
    # Save checkpoint after test creation
    lib_path = project_root / "plugins/autonomous-dev/lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))
        try:
            from agent_tracker import AgentTracker
            AgentTracker.save_agent_checkpoint(
                'test-master',
                'Created test_sync_command_sync.py - 13 tests for sync.md file synchronization'
            )
            print("Checkpoint saved")
        except ImportError:
            print("Checkpoint skipped (user project)")

    # Run tests
    pytest.main([__file__, "-v", "--tb=line", "-q"])
