#!/usr/bin/env python3
"""
TDD Tests for /sync Command Format - Issue #202

This module contains FAILING tests (RED phase) for the /sync command format
validation to prevent URL fetching behavior.

Requirements (Issue #202):
1. sync.md contains no URL references (http://, https://)
2. sync.md has `allowed-tools: [Bash]` in frontmatter
3. sync.md bash block contains only python3 command
4. sync.md contains "Do NOT fetch" directive
5. sync.md is under 50 lines (prevents bloat)
6. sync.md has proper frontmatter structure

This test suite follows TDD principles:
- Tests written FIRST before implementation
- Tests SHOULD FAIL until sync.md is properly fixed
- Tests validate command structure and prevent regression

Background:
The /sync command was incorrectly fetching README.md from URLs instead of
executing the sync_dispatcher.py script. These tests ensure the command
file structure prevents this behavior.

Author: test-master agent
Date: 2026-01-08
Issue: #202
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Any

import pytest
import yaml

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


class TestSyncCommandExists:
    """Test that sync command exists and is accessible."""

    @pytest.fixture
    def sync_cmd_path(self):
        """Get path to sync command file."""
        return (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "commands"
            / "sync.md"
        )

    def test_sync_command_file_exists(self, sync_cmd_path):
        """Test that sync.md command file exists.

        RED PHASE: Should fail until sync.md exists
        EXPECTATION: File at plugins/autonomous-dev/commands/sync.md
        """
        assert sync_cmd_path.exists(), (
            f"sync.md command file not found\n"
            f"Expected: {sync_cmd_path}\n"
            "This is the /sync command for plugin synchronization"
        )

    def test_sync_command_is_file(self, sync_cmd_path):
        """Test that sync is a file, not directory.

        RED PHASE: Should fail if sync is a directory
        EXPECTATION: sync.md is a markdown file
        """
        assert sync_cmd_path.is_file(), (
            f"sync path exists but is not a file\n"
            f"Path: {sync_cmd_path}\n"
            f"Is directory: {sync_cmd_path.is_dir()}\n"
            "Expected: sync.md should be a markdown file"
        )

    def test_sync_command_readable(self, sync_cmd_path):
        """Test that sync command is readable.

        RED PHASE: Should fail if file permissions are wrong
        EXPECTATION: File has read permissions
        """
        import os

        assert os.access(sync_cmd_path, os.R_OK), (
            f"sync.md is not readable\n"
            f"Path: {sync_cmd_path}\n"
            "Fix: Check file permissions"
        )


class TestSyncCommandFrontmatter:
    """Test that sync command has proper YAML frontmatter."""

    @pytest.fixture
    def sync_cmd_content(self) -> str:
        """Read sync command file content."""
        sync_path = (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "commands"
            / "sync.md"
        )
        with open(sync_path, "r") as f:
            return f.read()

    @pytest.fixture
    def frontmatter(self, sync_cmd_content) -> Dict[str, Any]:
        """Extract and parse YAML frontmatter from sync.md.

        RED PHASE: Should fail if frontmatter is malformed
        EXPECTATION: Valid YAML between --- delimiters
        """
        # Extract frontmatter between --- delimiters
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', sync_cmd_content, re.DOTALL)
        assert match, (
            "sync.md missing YAML frontmatter\n"
            "Expected: Content between --- delimiters at start of file"
        )

        try:
            return yaml.safe_load(match.group(1))
        except yaml.YAMLError as e:
            pytest.fail(
                f"sync.md frontmatter has invalid YAML: {e}\n"
                "Fix: Ensure valid YAML syntax in frontmatter"
            )

    def test_frontmatter_has_name(self, frontmatter):
        """Test that frontmatter has 'name' field.

        RED PHASE: Should fail if name field missing
        EXPECTATION: frontmatter['name'] = 'sync'
        """
        assert "name" in frontmatter, (
            "sync.md frontmatter missing 'name' field\n"
            "Expected: name: sync"
        )
        assert frontmatter["name"] == "sync", (
            f"sync.md has wrong name: {frontmatter['name']}\n"
            "Expected: name: sync"
        )

    def test_frontmatter_has_description(self, frontmatter):
        """Test that frontmatter has 'description' field.

        RED PHASE: Should fail if description field missing
        EXPECTATION: frontmatter has description
        """
        assert "description" in frontmatter, (
            "sync.md frontmatter missing 'description' field\n"
            "Expected: description: <text>"
        )
        assert len(frontmatter["description"]) > 0, (
            "sync.md has empty description\n"
            "Expected: Non-empty description string"
        )

    def test_frontmatter_has_allowed_tools(self, frontmatter):
        """Test that frontmatter has 'allowed-tools' field.

        RED PHASE: Should fail if allowed-tools field missing
        EXPECTATION: frontmatter['allowed-tools'] = ['Bash']
        """
        assert "allowed-tools" in frontmatter, (
            "sync.md frontmatter missing 'allowed-tools' field\n"
            "Expected: allowed-tools: [Bash]\n"
            "This is CRITICAL to prevent URL fetching behavior"
        )

    def test_frontmatter_allowed_tools_bash_only(self, frontmatter):
        """Test that allowed-tools contains only Bash.

        RED PHASE: Should fail if allowed-tools includes WebFetch or other tools
        EXPECTATION: allowed-tools: [Bash] (no WebFetch, no Read, etc.)
        """
        allowed_tools = frontmatter.get("allowed-tools", [])
        assert allowed_tools == ["Bash"], (
            f"sync.md allowed-tools has wrong value: {allowed_tools}\n"
            "Expected: allowed-tools: [Bash]\n"
            "CRITICAL: Including WebFetch or Read enables URL fetching behavior"
        )


class TestSyncCommandURLPrevention:
    """Test that sync command contains no URL references."""

    @pytest.fixture
    def sync_cmd_content(self) -> str:
        """Read sync command file content."""
        sync_path = (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "commands"
            / "sync.md"
        )
        with open(sync_path, "r") as f:
            return f.read()

    def test_no_http_urls(self, sync_cmd_content):
        """Test that sync.md contains no http:// URLs.

        RED PHASE: Should fail if http:// found in file
        EXPECTATION: No http:// references anywhere
        """
        http_urls = re.findall(r'http://[^\s\)]+', sync_cmd_content)
        assert len(http_urls) == 0, (
            f"sync.md contains http:// URLs: {http_urls}\n"
            "Expected: No http:// references\n"
            "CRITICAL: URLs trigger fetching behavior"
        )

    def test_no_https_urls(self, sync_cmd_content):
        """Test that sync.md contains no https:// URLs.

        RED PHASE: Should fail if https:// found in file
        EXPECTATION: No https:// references anywhere
        """
        https_urls = re.findall(r'https://[^\s\)]+', sync_cmd_content)
        assert len(https_urls) == 0, (
            f"sync.md contains https:// URLs: {https_urls}\n"
            "Expected: No https:// references\n"
            "CRITICAL: URLs trigger fetching behavior"
        )

    def test_no_raw_githubusercontent_urls(self, sync_cmd_content):
        """Test that sync.md contains no raw.githubusercontent.com URLs.

        RED PHASE: Should fail if raw.githubusercontent.com found
        EXPECTATION: No GitHub raw content URLs
        """
        github_raw_urls = re.findall(
            r'raw\.githubusercontent\.com[^\s\)]*',
            sync_cmd_content
        )
        assert len(github_raw_urls) == 0, (
            f"sync.md contains raw.githubusercontent.com URLs: {github_raw_urls}\n"
            "Expected: No GitHub raw content URLs\n"
            "CRITICAL: These URLs trigger README.md fetching"
        )

    def test_no_readme_md_references(self, sync_cmd_content):
        """Test that sync.md contains no README.md references.

        RED PHASE: Should fail if README.md found (case-insensitive)
        EXPECTATION: No README.md references
        """
        readme_refs = re.findall(r'\bREADME\.md\b', sync_cmd_content, re.IGNORECASE)
        assert len(readme_refs) == 0, (
            f"sync.md contains README.md references: {readme_refs}\n"
            "Expected: No README.md references\n"
            "Context: Previous bug was fetching README.md from GitHub"
        )


class TestSyncCommandBashBlock:
    """Test that sync command bash block has correct structure."""

    @pytest.fixture
    def sync_cmd_content(self) -> str:
        """Read sync command file content."""
        sync_path = (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "commands"
            / "sync.md"
        )
        with open(sync_path, "r") as f:
            return f.read()

    @pytest.fixture
    def bash_blocks(self, sync_cmd_content) -> List[str]:
        """Extract bash code blocks from sync.md.

        RED PHASE: Should fail if no bash blocks found
        EXPECTATION: At least one ```bash block
        """
        blocks = re.findall(r'```bash\s*\n(.*?)\n```', sync_cmd_content, re.DOTALL)
        assert len(blocks) > 0, (
            "sync.md contains no ```bash blocks\n"
            "Expected: At least one bash code block"
        )
        return blocks

    def test_bash_block_contains_python3(self, bash_blocks):
        """Test that bash block contains python3 command.

        RED PHASE: Should fail if python3 not found
        EXPECTATION: Command starts with python3
        """
        # Should have exactly one bash block
        assert len(bash_blocks) == 1, (
            f"sync.md has {len(bash_blocks)} bash blocks\n"
            "Expected: Exactly 1 bash block"
        )

        bash_content = bash_blocks[0].strip()
        assert bash_content.startswith("python3 "), (
            f"sync.md bash block doesn't start with python3\n"
            f"Content: {bash_content}\n"
            "Expected: python3 ~/.claude/lib/sync_dispatcher.py"
        )

    def test_bash_block_references_sync_dispatcher(self, bash_blocks):
        """Test that bash block references sync_dispatcher.py.

        RED PHASE: Should fail if sync_dispatcher.py not found
        EXPECTATION: Command calls sync_dispatcher.py
        """
        bash_content = bash_blocks[0].strip()
        assert "sync_dispatcher.py" in bash_content, (
            f"sync.md bash block doesn't reference sync_dispatcher.py\n"
            f"Content: {bash_content}\n"
            "Expected: python3 ~/.claude/lib/sync_dispatcher.py"
        )

    def test_bash_block_uses_correct_path(self, bash_blocks):
        """Test that bash block uses ~/.claude/lib/ path.

        RED PHASE: Should fail if wrong path used
        EXPECTATION: Command uses ~/.claude/lib/sync_dispatcher.py
        """
        bash_content = bash_blocks[0].strip()
        assert "~/.claude/lib/sync_dispatcher.py" in bash_content, (
            f"sync.md bash block uses wrong path\n"
            f"Content: {bash_content}\n"
            "Expected: ~/.claude/lib/sync_dispatcher.py"
        )

    def test_bash_block_passes_arguments(self, bash_blocks):
        """Test that bash block passes $ARGUMENTS.

        RED PHASE: Should fail if $ARGUMENTS not passed
        EXPECTATION: Command passes $ARGUMENTS to script
        """
        bash_content = bash_blocks[0].strip()
        assert "$ARGUMENTS" in bash_content, (
            f"sync.md bash block doesn't pass arguments\n"
            f"Content: {bash_content}\n"
            "Expected: python3 ~/.claude/lib/sync_dispatcher.py $ARGUMENTS"
        )

    def test_bash_block_no_curl_wget(self, bash_blocks):
        """Test that bash block contains no curl or wget commands.

        RED PHASE: Should fail if curl/wget found
        EXPECTATION: No network fetching commands
        """
        bash_content = bash_blocks[0].lower()
        assert "curl" not in bash_content, (
            "sync.md bash block contains 'curl' command\n"
            "CRITICAL: curl triggers URL fetching behavior"
        )
        assert "wget" not in bash_content, (
            "sync.md bash block contains 'wget' command\n"
            "CRITICAL: wget triggers URL fetching behavior"
        )


class TestSyncCommandDirectives:
    """Test that sync command contains explicit directives."""

    @pytest.fixture
    def sync_cmd_content(self) -> str:
        """Read sync command file content."""
        sync_path = (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "commands"
            / "sync.md"
        )
        with open(sync_path, "r") as f:
            return f.read()

    def test_contains_do_not_fetch_directive(self, sync_cmd_content):
        """Test that sync.md contains "Do NOT fetch" directive.

        RED PHASE: Should fail if directive missing
        EXPECTATION: Explicit "Do NOT fetch" instruction
        """
        assert "Do NOT fetch" in sync_cmd_content, (
            "sync.md missing 'Do NOT fetch' directive\n"
            "Expected: Explicit instruction to not fetch URLs\n"
            "Context: This directive prevents Claude from fetching URLs"
        )

    def test_contains_execute_script_directive(self, sync_cmd_content):
        """Test that sync.md contains execution directive.

        RED PHASE: Should fail if directive missing
        EXPECTATION: Instruction to execute the script
        """
        # Look for directive to execute the bash block
        execute_patterns = [
            "Execute the script",
            "execute the script",
            "Run the script",
            "run the script"
        ]

        has_execute_directive = any(
            pattern in sync_cmd_content for pattern in execute_patterns
        )

        assert has_execute_directive, (
            "sync.md missing execution directive\n"
            f"Expected one of: {execute_patterns}\n"
            "Context: Directive ensures script execution instead of URL fetching"
        )


class TestSyncCommandSize:
    """Test that sync command file size is reasonable."""

    @pytest.fixture
    def sync_cmd_path(self):
        """Get path to sync command file."""
        return (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "commands"
            / "sync.md"
        )

    def test_file_under_50_lines(self, sync_cmd_path):
        """Test that sync.md is under 50 lines.

        RED PHASE: Should fail if file is too large
        EXPECTATION: File has less than 50 lines
        """
        with open(sync_cmd_path, "r") as f:
            lines = f.readlines()

        line_count = len(lines)
        assert line_count < 50, (
            f"sync.md is too large: {line_count} lines\n"
            "Expected: Less than 50 lines\n"
            "Context: Command files should be concise and focused"
        )

    def test_file_size_under_2kb(self, sync_cmd_path):
        """Test that sync.md is under 2KB.

        RED PHASE: Should fail if file is too large
        EXPECTATION: File size under 2048 bytes
        """
        file_size = sync_cmd_path.stat().st_size
        assert file_size < 2048, (
            f"sync.md is too large: {file_size} bytes\n"
            "Expected: Less than 2048 bytes (2KB)\n"
            "Context: Large files indicate bloat or unnecessary content"
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
                'Created test_sync_command_format.py - 15 tests for sync.md format validation'
            )
            print("Checkpoint saved")
        except ImportError:
            print("Checkpoint skipped (user project)")

    # Run tests
    pytest.main([__file__, "-v", "--tb=line", "-q"])
