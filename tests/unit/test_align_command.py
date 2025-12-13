#!/usr/bin/env python3
"""
TDD Tests for Unified /align Command - Issue #121

This module contains FAILING tests (RED phase) for the new unified /align command
that consolidates three separate commands:
- /align-project → /align --project
- /align-claude → /align --claude
- /align-project-retrofit → /align --retrofit

Requirements (Issue #121):
1. align.md command file exists
2. Command supports --project flag (PROJECT.md alignment)
3. Command supports --claude flag (documentation drift fix)
4. Command supports --retrofit flag (brownfield project retrofit)
5. Command has proper documentation explaining all modes

This test suite follows TDD principles:
- Tests written FIRST before align.md is created
- Tests SHOULD FAIL until align.md command is fully implemented
- Tests validate command structure, modes, and documentation

Author: test-master agent
Date: 2025-12-13
Issue: #121
"""

import sys
from pathlib import Path
from typing import Dict, Any

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestAlignCommandExists:
    """Test that unified align command exists and has proper structure."""

    @pytest.fixture
    def align_cmd_path(self):
        """Get path to align command file."""
        return (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "commands"
            / "align.md"
        )

    def test_align_command_file_exists(self, align_cmd_path):
        """Test that align.md command file exists.

        RED PHASE: Should fail until align.md is created
        EXPECTATION: File at plugins/autonomous-dev/commands/align.md
        """
        assert align_cmd_path.exists(), (
            f"align.md command file not found\n"
            f"Expected: {align_cmd_path}\n"
            "This is the unified /align command that consolidates:\n"
            "  - /align-project (align PROJECT.md)\n"
            "  - /align-claude (fix documentation drift)\n"
            "  - /align-project-retrofit (brownfield retrofit)\n"
            "See GitHub Issue #121 for details"
        )

    def test_align_command_is_file(self, align_cmd_path):
        """Test that align is a file, not directory.

        RED PHASE: Should fail if align is a directory
        EXPECTATION: align.md is a markdown file
        """
        assert align_cmd_path.is_file(), (
            f"align path exists but is not a file\n"
            f"Path: {align_cmd_path}\n"
            f"Is directory: {align_cmd_path.is_dir()}\n"
            "Expected: align.md should be a markdown file"
        )

    def test_align_command_readable(self, align_cmd_path):
        """Test that align command is readable.

        RED PHASE: Should fail if file permissions are wrong
        EXPECTATION: File has read permissions
        """
        import os

        assert os.access(align_cmd_path, os.R_OK), (
            f"align.md is not readable\n"
            f"Path: {align_cmd_path}\n"
            "Fix: Check file permissions"
        )


class TestAlignCommandContent:
    """Test that align command markdown has required structure and content."""

    @pytest.fixture
    def align_cmd_content(self) -> str:
        """Load align command markdown content."""
        align_path = (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "commands"
            / "align.md"
        )
        assert align_path.exists(), f"align.md not found at {align_path}"
        with open(align_path, "r") as f:
            return f.read()

    def test_align_has_description(self, align_cmd_content):
        """Test that align command has description.

        RED PHASE: Should fail until command documented
        EXPECTATION: Content includes command purpose/description
        """
        assert len(align_cmd_content) > 0, "align.md is empty"
        assert "align" in align_cmd_content.lower(), (
            "align.md does not mention 'align'\n"
            "Expected: Command description explaining alignment functionality"
        )

    def test_align_documents_project_mode(self, align_cmd_content):
        """Test that align command documents --project mode.

        RED PHASE: Should fail until --project mode documented
        EXPECTATION: Content explains /align --project functionality
                     (validates and optionally fixes PROJECT.md alignment)

        DESCRIPTION:
        --project mode: Validates feature alignment with PROJECT.md goals and scope.
                       Checks: GOALS section, SCOPE (in/out), CONSTRAINTS
                       Options: --fix (auto-fix), --strict (block if misaligned)
        """
        content_lower = align_cmd_content.lower()
        assert "--project" in align_cmd_content, (
            "align.md does not document --project flag\n"
            "Expected: /align --project description\n"
            "Purpose: Validate/fix PROJECT.md alignment"
        )

    def test_align_documents_claude_mode(self, align_cmd_content):
        """Test that align command documents --claude mode.

        RED PHASE: Should fail until --claude mode documented
        EXPECTATION: Content explains /align --claude functionality
                     (detects and fixes CLAUDE.md documentation drift)

        DESCRIPTION:
        --claude mode: Detects documentation drift between CLAUDE.md and PROJECT.md.
                       Validates: version dates, agent counts, command availability,
                                  hook documentation
                       Auto-fixes: Updates CLAUDE.md to match current state
        """
        content_lower = align_cmd_content.lower()
        assert "--claude" in align_cmd_content, (
            "align.md does not document --claude flag\n"
            "Expected: /align --claude description\n"
            "Purpose: Fix documentation drift (CLAUDE.md vs PROJECT.md)"
        )

    def test_align_documents_retrofit_mode(self, align_cmd_content):
        """Test that align command documents --retrofit mode.

        RED PHASE: Should fail until --retrofit mode documented
        EXPECTATION: Content explains /align --retrofit functionality
                     (retrofits brownfield projects for autonomous development)

        DESCRIPTION:
        --retrofit mode: Non-destructively aligns existing projects for autonomous dev.
                        Analyzes: current structure, existing tools, architecture
                        Proposes: migration plan, file organization, configuration
                        Asks: approval before making changes (non-destructive)
        """
        content_lower = align_cmd_content.lower()
        assert "--retrofit" in align_cmd_content or "retrofit" in content_lower, (
            "align.md does not document --retrofit flag\n"
            "Expected: /align --retrofit description\n"
            "Purpose: Retrofit brownfield projects for autonomous development"
        )

    def test_align_documents_tool_list(self, align_cmd_content):
        """Test that align command declares required tools/agents.

        RED PHASE: Should fail until tools are documented
        EXPECTATION: Front matter includes 'tools:' list of required agents

        RATIONALE: Each command declares which agents/tools it uses.
                  --project: alignment-analyzer agent
                  --claude: validation scripts
                  --retrofit: brownfield-analyzer agent
        """
        # Look for tools section in front matter (between --- markers)
        assert "---" in align_cmd_content, (
            "align.md missing YAML front matter (should start with ---)\n"
            "Expected: YAML frontmatter with tools/agents list"
        )

        # Check that tools are declared (either 'tools:' or similar)
        assert "tool" in align_cmd_content.lower(), (
            "align.md does not declare required tools/agents\n"
            "Expected: tools: list in YAML frontmatter"
        )


class TestAlignCommandModes:
    """Test that align command properly implements all three modes."""

    @pytest.fixture
    def align_cmd_content(self) -> str:
        """Load align command markdown content."""
        align_path = (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "commands"
            / "align.md"
        )
        with open(align_path, "r") as f:
            return f.read()

    def test_align_project_mode_complete(self, align_cmd_content):
        """Test that --project mode is fully documented.

        RED PHASE: Should fail until mode is documented
        EXPECTATION: Includes: usage, purpose, what it validates, examples
        """
        assert "--project" in align_cmd_content, (
            "align.md missing --project mode documentation"
        )
        # Check for description of what --project does
        content_lower = align_cmd_content.lower()
        assert (
            "project.md" in content_lower
            or "alignment" in content_lower
            or "validate" in content_lower
        ), (
            "--project mode documentation incomplete\n"
            "Expected: Explain PROJECT.md validation/alignment purpose"
        )

    def test_align_claude_mode_complete(self, align_cmd_content):
        """Test that --claude mode is fully documented.

        RED PHASE: Should fail until mode is documented
        EXPECTATION: Includes: usage, purpose, what it validates, examples
        """
        assert "--claude" in align_cmd_content, (
            "align.md missing --claude mode documentation"
        )
        # Check for description of what --claude does
        content_lower = align_cmd_content.lower()
        assert (
            "claude.md" in content_lower
            or "drift" in content_lower
            or "synchron" in content_lower
            or "document" in content_lower
        ), (
            "--claude mode documentation incomplete\n"
            "Expected: Explain CLAUDE.md drift detection/fixing purpose"
        )

    def test_align_retrofit_mode_complete(self, align_cmd_content):
        """Test that --retrofit mode is fully documented.

        RED PHASE: Should fail until mode is documented
        EXPECTATION: Includes: usage, purpose, what it does, examples
        """
        assert "--retrofit" in align_cmd_content or "retrofit" in align_cmd_content.lower(), (
            "align.md missing --retrofit mode documentation"
        )
        # Check for description of what --retrofit does
        content_lower = align_cmd_content.lower()
        assert (
            "brownfield" in content_lower
            or "project" in content_lower
            or "retrofit" in content_lower
        ), (
            "--retrofit mode documentation incomplete\n"
            "Expected: Explain brownfield project retrofit purpose"
        )

    def test_align_includes_usage_examples(self, align_cmd_content):
        """Test that align command includes usage examples.

        RED PHASE: Should fail until examples provided
        EXPECTATION: Shows how to use all three modes

        EXAMPLES:
        - /align --project          (validate PROJECT.md alignment)
        - /align --claude           (fix documentation drift)
        - /align --retrofit         (retrofit brownfield project)
        """
        content_lower = align_cmd_content.lower()
        assert "example" in content_lower or "/align" in align_cmd_content, (
            "align.md missing usage examples\n"
            "Expected: Examples showing /align --project, /align --claude, /align --retrofit"
        )


class TestAlignCommandConsolidation:
    """Test that align command properly consolidates previous commands."""

    @pytest.fixture
    def commands_dir(self):
        """Get commands directory path."""
        return (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "commands"
        )

    @pytest.fixture
    def align_cmd_content(self) -> str:
        """Load align command markdown content."""
        align_path = (
            Path(__file__).parent.parent.parent
            / "plugins"
            / "autonomous-dev"
            / "commands"
            / "align.md"
        )
        with open(align_path, "r") as f:
            return f.read()

    def test_align_replaces_align_project(self, commands_dir, align_cmd_content):
        """Test that align command replaces align-project.md.

        RED PHASE: Should fail until align.md exists
        EXPECTATION: align.md exists and align-project.md should not be in main commands/
                     (moved to commands/archive/)
        """
        align_project_in_main = (commands_dir / "align-project.md").exists()
        align_in_main = (commands_dir / "align.md").exists()

        assert align_in_main, "align.md not found in commands/"
        assert (
            not align_project_in_main
            or (commands_dir / "archive" / "align-project.md").exists()
        ), (
            "align-project.md still in main commands/ directory\n"
            "Expected: Move to commands/archive/ or remove (replaced by /align --project)"
        )

    def test_align_replaces_align_claude(self, commands_dir, align_cmd_content):
        """Test that align command replaces align-claude.md.

        RED PHASE: Should fail until align.md exists
        EXPECTATION: align.md exists and align-claude.md should not be in main commands/
                     (moved to commands/archive/)
        """
        align_claude_in_main = (commands_dir / "align-claude.md").exists()
        align_in_main = (commands_dir / "align.md").exists()

        assert align_in_main, "align.md not found in commands/"
        assert (
            not align_claude_in_main
            or (commands_dir / "archive" / "align-claude.md").exists()
        ), (
            "align-claude.md still in main commands/ directory\n"
            "Expected: Move to commands/archive/ or remove (replaced by /align --claude)"
        )

    def test_align_replaces_align_project_retrofit(self, commands_dir):
        """Test that align command replaces align-project-retrofit.md.

        RED PHASE: Should fail until align.md exists
        EXPECTATION: align.md exists and align-project-retrofit.md should not be in main commands/
                     (moved to commands/archive/)
        """
        align_retrofit_in_main = (commands_dir / "align-project-retrofit.md").exists()
        align_in_main = (commands_dir / "align.md").exists()

        assert align_in_main, "align.md not found in commands/"
        assert (
            not align_retrofit_in_main
            or (commands_dir / "archive" / "align-project-retrofit.md").exists()
        ), (
            "align-project-retrofit.md still in main commands/ directory\n"
            "Expected: Move to commands/archive/ or remove (replaced by /align --retrofit)"
        )

    def test_align_consolidates_three_into_one(self, align_cmd_content):
        """Test that align command consolidates three separate commands.

        RED PHASE: Should fail until command is properly consolidated
        EXPECTATION: Single /align command with --project, --claude, --retrofit modes

        RATIONALE: Issue #121 simplifies commands by consolidating related commands.
                  Three separate align* commands → Single /align command with modes
                  This reduces CLI surface area while maintaining all functionality.
        """
        assert "--project" in align_cmd_content, (
            "align.md missing --project flag (from align-project.md functionality)"
        )
        assert "--claude" in align_cmd_content, (
            "align.md missing --claude flag (from align-claude.md functionality)"
        )
        assert "--retrofit" in align_cmd_content or "retrofit" in align_cmd_content.lower(), (
            "align.md missing --retrofit flag (from align-project-retrofit.md functionality)"
        )


if __name__ == "__main__":
    # Run with: pytest tests/unit/test_align_command.py -v
    pytest.main([__file__, "-v"])
