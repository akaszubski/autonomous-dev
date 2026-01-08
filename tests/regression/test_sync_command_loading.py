#!/usr/bin/env python3
"""
Regression Tests for /sync Command Loading - Issue #202

This module contains FAILING regression tests (RED phase) to prevent the
URL fetching behavior that occurred in the original bug.

Requirements (Issue #202):
1. Command file loads without attempting URL fetches
2. Bash block is executable and contains valid command
3. No WebFetch tool references in command file
4. sync_dispatcher.py path is correct and accessible
5. Command executes sync_dispatcher.py instead of fetching URLs

This test suite follows TDD principles:
- Tests written FIRST before fix is implemented
- Tests SHOULD FAIL until URL fetching behavior is prevented
- Tests provide regression protection

Background:
Original bug: /sync command was fetching README.md from GitHub URLs instead
of executing sync_dispatcher.py. These tests ensure this never happens again.

Author: test-master agent
Date: 2026-01-08
Issue: #202
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any

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


class TestSyncCommandNoWebFetch:
    """Regression test: Ensure no WebFetch tool usage."""

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

    def test_no_webfetch_tool_reference(self, sync_cmd_content):
        """Test that sync.md contains no WebFetch tool references.

        RED PHASE: Should fail if WebFetch found
        EXPECTATION: No WebFetch, WebRead, or similar tool references

        REGRESSION CONTEXT:
        Original bug allowed WebFetch tool, which enabled URL fetching behavior.
        """
        webfetch_patterns = [
            r'\bWebFetch\b',
            r'\bWebRead\b',
            r'\bFetchURL\b',
            r'\bHTTPFetch\b',
        ]

        for pattern in webfetch_patterns:
            matches = re.findall(pattern, sync_cmd_content, re.IGNORECASE)
            assert len(matches) == 0, (
                f"sync.md contains {pattern} reference: {matches}\n"
                "Expected: No web fetching tool references\n"
                "REGRESSION: This enables URL fetching behavior"
            )

    def test_allowed_tools_excludes_webfetch(self, sync_cmd_content):
        """Test that allowed-tools frontmatter excludes WebFetch.

        RED PHASE: Should fail if WebFetch in allowed-tools
        EXPECTATION: allowed-tools: [Bash] only

        REGRESSION CONTEXT:
        Allowing WebFetch enables Claude to fetch URLs instead of running script.
        """
        # Extract allowed-tools value
        match = re.search(r'allowed-tools:\s*\[(.*?)\]', sync_cmd_content)
        assert match, "No allowed-tools found in frontmatter"

        allowed_tools = match.group(1).strip()

        # Should be Bash only
        assert "WebFetch" not in allowed_tools, (
            f"allowed-tools includes WebFetch: [{allowed_tools}]\n"
            "Expected: [Bash] only\n"
            "REGRESSION: WebFetch enables URL fetching"
        )
        assert "WebRead" not in allowed_tools, (
            f"allowed-tools includes WebRead: [{allowed_tools}]\n"
            "Expected: [Bash] only\n"
            "REGRESSION: WebRead enables URL fetching"
        )

    def test_no_read_tool_for_urls(self, sync_cmd_content):
        """Test that Read tool is not allowed (could fetch URLs).

        RED PHASE: Should fail if Read tool found
        EXPECTATION: allowed-tools: [Bash] only (no Read)

        REGRESSION CONTEXT:
        Read tool can be used to fetch file-like URLs.
        """
        match = re.search(r'allowed-tools:\s*\[(.*?)\]', sync_cmd_content)
        assert match, "No allowed-tools found in frontmatter"

        allowed_tools = match.group(1).strip()

        # Read tool should not be allowed
        assert "Read" not in allowed_tools or allowed_tools == "Bash", (
            f"allowed-tools includes Read: [{allowed_tools}]\n"
            "Expected: [Bash] only\n"
            "REGRESSION: Read tool can fetch URLs"
        )


class TestSyncCommandNoURLInstructions:
    """Regression test: Ensure no URL fetch instructions."""

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

    def test_no_fetch_instruction(self, sync_cmd_content):
        """Test that sync.md contains no fetch instructions.

        RED PHASE: Should fail if fetch instruction found
        EXPECTATION: No "fetch", "download", "retrieve" instructions

        REGRESSION CONTEXT:
        Instructions like "fetch README.md" trigger URL fetching behavior.
        """
        fetch_instructions = [
            r'\bfetch\s+(?:from|the)\b',
            r'\bdownload\s+(?:from|the)\b',
            r'\bretrieve\s+(?:from|the)\b',
            r'\bget\s+(?:from|the)\s+URL\b',
        ]

        for pattern in fetch_instructions:
            matches = re.findall(pattern, sync_cmd_content, re.IGNORECASE)
            # Allow "Do NOT fetch" directive
            if matches:
                for match in matches:
                    assert "Do NOT" in match or "Do not" in match, (
                        f"sync.md contains fetch instruction: {match}\n"
                        "Expected: No fetch/download/retrieve instructions\n"
                        "REGRESSION: Fetch instructions trigger URL fetching"
                    )

    def test_no_github_references(self, sync_cmd_content):
        """Test that sync.md contains no GitHub URL references.

        RED PHASE: Should fail if github.com found
        EXPECTATION: No github.com or raw.githubusercontent.com

        REGRESSION CONTEXT:
        Original bug fetched from raw.githubusercontent.com URLs.
        """
        github_patterns = [
            r'github\.com',
            r'raw\.githubusercontent\.com',
        ]

        for pattern in github_patterns:
            matches = re.findall(pattern, sync_cmd_content)
            assert len(matches) == 0, (
                f"sync.md contains GitHub reference: {pattern}\n"
                "Expected: No GitHub URLs\n"
                "REGRESSION: Original bug fetched from GitHub raw URLs"
            )

    def test_explicit_no_fetch_directive(self, sync_cmd_content):
        """Test that sync.md has explicit "Do NOT fetch" directive.

        RED PHASE: Should fail if directive missing
        EXPECTATION: Contains "Do NOT fetch" instruction

        REGRESSION CONTEXT:
        Explicit directive prevents Claude from interpreting command as fetch request.
        """
        assert "Do NOT fetch" in sync_cmd_content, (
            "sync.md missing 'Do NOT fetch' directive\n"
            "Expected: Explicit 'Do NOT fetch any URLs' instruction\n"
            "REGRESSION: Missing directive allows URL fetching interpretation"
        )


class TestSyncDispatcherPath:
    """Regression test: Ensure sync_dispatcher.py path is correct."""

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
    def sync_dispatcher_path(self):
        """Get expected path to sync_dispatcher.py."""
        # Check both installed location and source location
        installed_path = Path.home() / ".claude" / "lib" / "sync_dispatcher.py"
        source_path = (
            project_root
            / "plugins"
            / "autonomous-dev"
            / "lib"
            / "sync_dispatcher.py"
        )

        # Return whichever exists
        if installed_path.exists():
            return installed_path
        elif source_path.exists():
            return source_path
        else:
            pytest.fail(
                "sync_dispatcher.py not found\n"
                f"Checked: {installed_path}\n"
                f"Checked: {source_path}\n"
                "Fix: Install plugin or check file location"
            )

    def test_sync_dispatcher_exists(self, sync_dispatcher_path):
        """Test that sync_dispatcher.py exists.

        RED PHASE: Should fail if sync_dispatcher.py not found
        EXPECTATION: File exists at ~/.claude/lib/sync_dispatcher.py

        REGRESSION CONTEXT:
        If sync_dispatcher.py doesn't exist, command will fail or fetch URLs.
        """
        assert sync_dispatcher_path.exists(), (
            f"sync_dispatcher.py not found at {sync_dispatcher_path}\n"
            "Expected: ~/.claude/lib/sync_dispatcher.py\n"
            "Fix: Run plugin installation"
        )

    def test_sync_dispatcher_is_python(self, sync_dispatcher_path):
        """Test that sync_dispatcher.py is a Python file.

        RED PHASE: Should fail if not a .py file
        EXPECTATION: File has .py extension
        """
        assert sync_dispatcher_path.suffix == ".py", (
            f"sync_dispatcher path is not a Python file: {sync_dispatcher_path}\n"
            "Expected: .py extension"
        )

    def test_command_references_correct_path(self, sync_cmd_content):
        """Test that command references correct sync_dispatcher.py path.

        RED PHASE: Should fail if path is wrong
        EXPECTATION: Command uses ~/.claude/lib/sync_dispatcher.py

        REGRESSION CONTEXT:
        Wrong path causes command to fail, potentially falling back to URL fetch.
        """
        assert "~/.claude/lib/sync_dispatcher.py" in sync_cmd_content, (
            "sync.md doesn't reference correct path\n"
            "Expected: ~/.claude/lib/sync_dispatcher.py\n"
            "REGRESSION: Wrong path can cause fallback to URL fetching"
        )

    def test_sync_dispatcher_executable_syntax(self, sync_dispatcher_path):
        """Test that sync_dispatcher.py has valid Python syntax.

        RED PHASE: Should fail if syntax errors found
        EXPECTATION: File compiles without syntax errors

        REGRESSION CONTEXT:
        Syntax errors prevent script execution, may cause fallback behavior.
        """
        try:
            with open(sync_dispatcher_path, "r") as f:
                compile(f.read(), str(sync_dispatcher_path), "exec")
        except SyntaxError as e:
            pytest.fail(
                f"sync_dispatcher.py has syntax error: {e}\n"
                f"File: {sync_dispatcher_path}\n"
                "REGRESSION: Syntax errors prevent script execution"
            )


class TestSyncCommandExecution:
    """Regression test: Ensure command executes script, not URLs."""

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
    def bash_command(self, sync_cmd_content) -> str:
        """Extract bash command from sync.md.

        RED PHASE: Should fail if no bash command found
        EXPECTATION: Command in ```bash block
        """
        match = re.search(r'```bash\s*\n(.*?)\n```', sync_cmd_content, re.DOTALL)
        assert match, (
            "No bash code block found in sync.md\n"
            "Expected: ```bash block with command"
        )

        return match.group(1).strip()

    def test_command_starts_with_python3(self, bash_command):
        """Test that bash command starts with python3.

        RED PHASE: Should fail if command doesn't start with python3
        EXPECTATION: Command is python3 <script>

        REGRESSION CONTEXT:
        Commands starting with other tools (curl, wget) indicate URL fetching.
        """
        assert bash_command.startswith("python3 "), (
            f"Bash command doesn't start with python3\n"
            f"Command: {bash_command}\n"
            "Expected: python3 ~/.claude/lib/sync_dispatcher.py\n"
            "REGRESSION: Non-python commands may fetch URLs"
        )

    def test_command_no_curl_wget(self, bash_command):
        """Test that bash command doesn't use curl or wget.

        RED PHASE: Should fail if curl/wget found
        EXPECTATION: No network fetching commands

        REGRESSION CONTEXT:
        Original bug may have used curl/wget to fetch URLs.
        """
        assert "curl" not in bash_command.lower(), (
            f"Bash command contains curl\n"
            f"Command: {bash_command}\n"
            "REGRESSION: curl indicates URL fetching behavior"
        )
        assert "wget" not in bash_command.lower(), (
            f"Bash command contains wget\n"
            f"Command: {bash_command}\n"
            "REGRESSION: wget indicates URL fetching behavior"
        )

    def test_command_no_pipes_to_bash(self, bash_command):
        """Test that command doesn't pipe to bash (common in URL scripts).

        RED PHASE: Should fail if | bash found
        EXPECTATION: No piped execution pattern

        REGRESSION CONTEXT:
        Pattern "curl URL | bash" is common for fetched scripts.
        """
        assert "| bash" not in bash_command, (
            f"Bash command pipes to bash\n"
            f"Command: {bash_command}\n"
            "REGRESSION: Piping to bash indicates fetched script execution"
        )
        assert "| sh" not in bash_command, (
            f"Bash command pipes to sh\n"
            f"Command: {bash_command}\n"
            "REGRESSION: Piping to sh indicates fetched script execution"
        )

    def test_command_arguments_passed(self, bash_command):
        """Test that command passes $ARGUMENTS to script.

        RED PHASE: Should fail if $ARGUMENTS missing
        EXPECTATION: Script receives command arguments

        REGRESSION CONTEXT:
        Missing argument passing breaks command functionality.
        """
        assert "$ARGUMENTS" in bash_command, (
            f"Bash command doesn't pass arguments\n"
            f"Command: {bash_command}\n"
            "Expected: python3 ~/.claude/lib/sync_dispatcher.py $ARGUMENTS\n"
            "REGRESSION: Missing arguments breaks command modes"
        )


class TestSyncCommandDocumentation:
    """Regression test: Ensure command has clear documentation."""

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

    def test_frontmatter_has_description(self, sync_cmd_content):
        """Test that frontmatter has description field.

        RED PHASE: Should fail if description missing
        EXPECTATION: Frontmatter includes description

        REGRESSION CONTEXT:
        Missing description may cause Claude to infer behavior (like URL fetching).
        """
        match = re.search(r'description:\s*"([^"]+)"', sync_cmd_content)
        assert match, (
            "sync.md frontmatter missing description\n"
            "Expected: description field in frontmatter\n"
            "REGRESSION: Missing description allows behavior inference"
        )

    def test_description_mentions_plugin(self, sync_cmd_content):
        """Test that description mentions plugin synchronization.

        RED PHASE: Should fail if description unclear
        EXPECTATION: Description indicates plugin sync purpose

        REGRESSION CONTEXT:
        Unclear description may cause Claude to interpret as URL fetch command.
        """
        match = re.search(r'description:\s*"([^"]+)"', sync_cmd_content)
        if match:
            description = match.group(1).lower()
            assert "plugin" in description or "sync" in description, (
                f"Description unclear about plugin sync: {match.group(1)}\n"
                "Expected: Mention 'plugin' or 'sync'\n"
                "REGRESSION: Unclear description causes wrong interpretation"
            )

    def test_no_readme_in_description(self, sync_cmd_content):
        """Test that description doesn't mention README.

        RED PHASE: Should fail if README mentioned
        EXPECTATION: No README reference in description

        REGRESSION CONTEXT:
        Mentioning README may trigger fetching behavior.
        """
        match = re.search(r'description:\s*"([^"]+)"', sync_cmd_content)
        if match:
            description = match.group(1).lower()
            assert "readme" not in description, (
                f"Description mentions README: {match.group(1)}\n"
                "REGRESSION: README reference may trigger fetching"
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
                'Created test_sync_command_loading.py - 15 regression tests for URL fetch prevention'
            )
            print("Checkpoint saved")
        except ImportError:
            print("Checkpoint skipped (user project)")

    # Run tests
    pytest.main([__file__, "-v", "--tb=line", "-q"])
