#!/usr/bin/env python3
"""
TDD Tests for Issue #83: Symlink Documentation (FAILING - Red Phase)

This module contains FAILING tests that verify comprehensive documentation exists
for the development symlink requirement (plugins/autonomous_dev → plugins/autonomous-dev).

Requirements (from Issue #83):
1. DEVELOPMENT.md - "Step 4.5: Create Development Symlink" section with OS-specific commands
2. TROUBLESHOOTING.md - ModuleNotFoundError troubleshooting entry (file needs to be created)
3. Plugin README.md - "Development Setup" section explaining symlink requirement
4. tests/README.md - Reference to DEVELOPMENT.md symlink section
5. CONTRIBUTING.md - Quick reference to symlink setup
6. .gitignore - Includes "plugins/autonomous_dev" to prevent symlink from being committed
7. Cross-references - All documentation files reference each other correctly
8. Security notes - Documentation explains symlink is safe (relative path, within repo)

Test Coverage Target: 100% of documentation requirements

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe what documentation MUST exist
- Tests should FAIL until documentation is created
- Each test validates ONE specific documentation requirement

Author: test-master agent
Date: 2025-11-19
Related: GitHub Issue #83 - Document symlink requirement for plugin imports
"""

import os
import re
from pathlib import Path
from typing import List, Optional

import pytest


# Constants
REPO_ROOT = Path(__file__).parent.parent.parent
DEVELOPMENT_MD = REPO_ROOT / "docs" / "DEVELOPMENT.md"
TROUBLESHOOTING_MD = REPO_ROOT / "docs" / "TROUBLESHOOTING.md"
PLUGIN_README = REPO_ROOT / "plugins" / "autonomous-dev" / "README.md"
TESTS_README = REPO_ROOT / "tests" / "README.md"
CONTRIBUTING_MD = REPO_ROOT / "CONTRIBUTING.md"
GITIGNORE = REPO_ROOT / ".gitignore"


class TestDevelopmentMdSymlinkDocumentation:
    """Test DEVELOPMENT.md contains comprehensive symlink documentation."""

    def test_development_md_exists(self):
        """Verify DEVELOPMENT.md file exists.

        REQUIREMENT: DEVELOPMENT.md must exist before adding symlink section.
        Expected: File exists at docs/DEVELOPMENT.md.
        """
        assert DEVELOPMENT_MD.exists(), f"DEVELOPMENT.md not found at {DEVELOPMENT_MD}"

    def test_development_md_has_symlink_step(self):
        """Verify DEVELOPMENT.md has 'Step 4.5: Create Development Symlink' section.

        REQUIREMENT: Clear step-by-step documentation for creating symlink.
        Expected: Section with exact heading "Step 4.5: Create Development Symlink".
        """
        content = DEVELOPMENT_MD.read_text()

        # Look for the exact step heading
        assert "Step 4.5: Create Development Symlink" in content or \
               "## Step 4.5: Create Development Symlink" in content or \
               "### Step 4.5: Create Development Symlink" in content, \
               "Missing 'Step 4.5: Create Development Symlink' section in DEVELOPMENT.md"

    def test_development_md_explains_why_symlink_needed(self):
        """Verify DEVELOPMENT.md explains WHY symlink is needed.

        REQUIREMENT: Developer understanding of the requirement.
        Expected: Explanation mentions Python import compatibility and test discovery.
        """
        content = DEVELOPMENT_MD.read_text()

        # Check for explanation (case-insensitive)
        lower_content = content.lower()

        # Must explain the purpose
        assert any(phrase in lower_content for phrase in [
            "python import",
            "test discovery",
            "pytest",
            "autonomous_dev",
            "hyphen",
            "underscore"
        ]), "DEVELOPMENT.md should explain why symlink is needed (Python import compatibility)"

    def test_development_md_has_macos_linux_commands(self):
        """Verify DEVELOPMENT.md includes macOS/Linux symlink commands.

        REQUIREMENT: Cross-platform support - Unix-like systems.
        Expected: Commands using 'ln -s' for creating symlink.
        """
        content = DEVELOPMENT_MD.read_text()

        # Check for ln command
        assert "ln -s" in content, "Missing 'ln -s' command for macOS/Linux in DEVELOPMENT.md"

        # Check for the specific symlink creation
        assert "autonomous-dev" in content and "autonomous_dev" in content, \
               "Missing symlink target/destination in DEVELOPMENT.md"

    def test_development_md_has_windows_commands(self):
        """Verify DEVELOPMENT.md includes Windows symlink commands.

        REQUIREMENT: Cross-platform support - Windows systems.
        Expected: Commands using 'mklink' for creating symlink.
        """
        content = DEVELOPMENT_MD.read_text()

        # Check for Windows mklink command
        assert "mklink" in content.lower() or "New-Item" in content, \
               "Missing Windows symlink command (mklink or New-Item) in DEVELOPMENT.md"

    def test_development_md_commands_are_correct(self):
        """Verify symlink commands in DEVELOPMENT.md are syntactically correct.

        REQUIREMENT: Documentation must have working commands.
        Expected: Commands create autonomous_dev → autonomous-dev symlink.
        """
        content = DEVELOPMENT_MD.read_text()

        # Extract code blocks containing symlink commands
        code_blocks = re.findall(r'```(?:bash|sh|powershell)?\n(.*?)```', content, re.DOTALL)

        symlink_commands_found = False
        for block in code_blocks:
            if "ln -s" in block and "autonomous-dev" in block and "autonomous_dev" in block:
                symlink_commands_found = True
                # Verify correct order (target → link)
                ln_match = re.search(r'ln\s+-s\s+(\S+)\s+(\S+)', block)
                if ln_match:
                    target = ln_match.group(1)
                    link_name = ln_match.group(2)
                    assert "autonomous-dev" in target, "Symlink target should be autonomous-dev"
                    assert "autonomous_dev" in link_name, "Symlink name should be autonomous_dev"
                break

        assert symlink_commands_found, "No valid symlink creation commands found in DEVELOPMENT.md"

    def test_development_md_has_verification_steps(self):
        """Verify DEVELOPMENT.md includes steps to verify symlink creation.

        REQUIREMENT: Developer confidence that setup is correct.
        Expected: Commands to verify symlink exists (ls -la, dir, test -L, etc.).
        """
        content = DEVELOPMENT_MD.read_text()

        # Check for verification commands
        assert any(cmd in content for cmd in ["ls -la", "ls -l", "test -L", "dir", "Get-Item"]), \
               "DEVELOPMENT.md should include verification commands to check symlink"

    def test_development_md_has_security_note(self):
        """Verify DEVELOPMENT.md includes security note about symlink safety.

        REQUIREMENT: Address security concerns proactively.
        Expected: Note explaining symlink is relative path within repo (safe).
        """
        content = DEVELOPMENT_MD.read_text()
        lower_content = content.lower()

        # Check for security-related keywords
        assert any(word in lower_content for word in ["safe", "security", "relative"]), \
               "DEVELOPMENT.md should include security note about symlink safety"


class TestTroubleshootingMdSymlinkDocumentation:
    """Test TROUBLESHOOTING.md contains ModuleNotFoundError troubleshooting."""

    def test_troubleshooting_md_exists(self):
        """Verify TROUBLESHOOTING.md file exists.

        REQUIREMENT: Troubleshooting documentation must exist.
        Expected: File exists at docs/TROUBLESHOOTING.md.
        """
        assert TROUBLESHOOTING_MD.exists(), \
               f"TROUBLESHOOTING.md not found at {TROUBLESHOOTING_MD} - file needs to be created"

    def test_troubleshooting_md_has_modulenotfound_section(self):
        """Verify TROUBLESHOOTING.md has ModuleNotFoundError section.

        REQUIREMENT: Help developers fix import errors.
        Expected: Section about ModuleNotFoundError with autonomous_dev.
        """
        content = TROUBLESHOOTING_MD.read_text()

        # Check for ModuleNotFoundError section
        assert "ModuleNotFoundError" in content, \
               "Missing ModuleNotFoundError section in TROUBLESHOOTING.md"

    def test_troubleshooting_md_mentions_symlink_solution(self):
        """Verify TROUBLESHOOTING.md mentions symlink as solution.

        REQUIREMENT: Clear path to resolution.
        Expected: Reference to symlink creation and link to DEVELOPMENT.md.
        """
        content = TROUBLESHOOTING_MD.read_text()
        lower_content = content.lower()

        # Check for symlink mention
        assert "symlink" in lower_content or "symbolic link" in lower_content, \
               "TROUBLESHOOTING.md should mention symlink as solution for ModuleNotFoundError"

    def test_troubleshooting_md_links_to_development_md(self):
        """Verify TROUBLESHOOTING.md links to DEVELOPMENT.md symlink section.

        REQUIREMENT: Cross-reference between documentation files.
        Expected: Markdown link to DEVELOPMENT.md or direct reference.
        """
        content = TROUBLESHOOTING_MD.read_text()

        # Check for link to DEVELOPMENT.md
        assert "DEVELOPMENT.md" in content or "docs/DEVELOPMENT.md" in content, \
               "TROUBLESHOOTING.md should link to DEVELOPMENT.md for symlink setup"

    def test_troubleshooting_md_has_error_example(self):
        """Verify TROUBLESHOOTING.md shows example error message.

        REQUIREMENT: Help developers recognize the issue.
        Expected: Example of actual ModuleNotFoundError message.
        """
        content = TROUBLESHOOTING_MD.read_text()

        # Check for error example
        assert "No module named" in content or "ModuleNotFoundError" in content, \
               "TROUBLESHOOTING.md should show example error message"


class TestPluginReadmeSymlinkDocumentation:
    """Test plugin README.md contains Development Setup section."""

    def test_plugin_readme_exists(self):
        """Verify plugin README.md file exists.

        REQUIREMENT: Plugin documentation must exist.
        Expected: File exists at plugins/autonomous-dev/README.md.
        """
        assert PLUGIN_README.exists(), f"Plugin README.md not found at {PLUGIN_README}"

    def test_plugin_readme_has_development_setup_section(self):
        """Verify plugin README.md has 'Development Setup' section.

        REQUIREMENT: Plugin-specific development instructions.
        Expected: Section titled 'Development Setup' or similar.
        """
        content = PLUGIN_README.read_text()

        # Check for Development Setup section (flexible matching)
        assert any(heading in content for heading in [
            "Development Setup",
            "## Development Setup",
            "### Development Setup",
            "Development Environment",
            "## Development",
            "### Development"
        ]), "Plugin README.md should have 'Development Setup' section"

    def test_plugin_readme_mentions_symlink_requirement(self):
        """Verify plugin README.md mentions symlink requirement.

        REQUIREMENT: Alert developers to setup requirement.
        Expected: Mention of symlink or autonomous_dev directory.
        """
        content = PLUGIN_README.read_text()
        lower_content = content.lower()

        # Check for symlink mention
        assert "symlink" in lower_content or "symbolic link" in lower_content or \
               "autonomous_dev" in content, \
               "Plugin README.md should mention symlink requirement"

    def test_plugin_readme_links_to_development_md(self):
        """Verify plugin README.md links to main DEVELOPMENT.md.

        REQUIREMENT: Cross-reference to comprehensive documentation.
        Expected: Link or reference to ../../docs/DEVELOPMENT.md.
        """
        content = PLUGIN_README.read_text()

        # Check for link to DEVELOPMENT.md (various formats)
        assert "DEVELOPMENT.md" in content or "docs/DEVELOPMENT" in content, \
               "Plugin README.md should link to DEVELOPMENT.md for full setup instructions"


class TestTestsReadmeSymlinkDocumentation:
    """Test tests/README.md references symlink documentation."""

    def test_tests_readme_exists(self):
        """Verify tests/README.md file exists.

        REQUIREMENT: Test documentation must exist.
        Expected: File exists at tests/README.md.
        """
        assert TESTS_README.exists(), f"tests/README.md not found at {TESTS_README}"

    def test_tests_readme_mentions_development_setup(self):
        """Verify tests/README.md mentions development setup requirement.

        REQUIREMENT: Guide test developers to setup instructions.
        Expected: Reference to DEVELOPMENT.md or symlink requirement.
        """
        content = TESTS_README.read_text()
        lower_content = content.lower()

        # Check for development setup reference
        assert "development" in lower_content or "setup" in lower_content or \
               "DEVELOPMENT.md" in content, \
               "tests/README.md should reference development setup"

    def test_tests_readme_links_to_development_md(self):
        """Verify tests/README.md links to DEVELOPMENT.md.

        REQUIREMENT: Direct developers to setup documentation.
        Expected: Link to ../docs/DEVELOPMENT.md or similar.
        """
        content = TESTS_README.read_text()

        # Check for link to DEVELOPMENT.md
        assert "DEVELOPMENT.md" in content or "docs/DEVELOPMENT" in content, \
               "tests/README.md should link to DEVELOPMENT.md"


class TestContributingMdSymlinkDocumentation:
    """Test CONTRIBUTING.md includes symlink quick reference."""

    def test_contributing_md_exists(self):
        """Verify CONTRIBUTING.md file exists.

        REQUIREMENT: Contribution guidelines must exist.
        Expected: File exists at CONTRIBUTING.md.
        """
        assert CONTRIBUTING_MD.exists(), f"CONTRIBUTING.md not found at {CONTRIBUTING_MD}"

    def test_contributing_md_mentions_symlink_setup(self):
        """Verify CONTRIBUTING.md mentions symlink setup requirement.

        REQUIREMENT: Ensure contributors set up environment correctly.
        Expected: Quick reference or link to full setup documentation.
        """
        content = CONTRIBUTING_MD.read_text()
        lower_content = content.lower()

        # Check for symlink or development setup mention
        assert "symlink" in lower_content or "development setup" in lower_content or \
               "DEVELOPMENT.md" in content or "autonomous_dev" in content, \
               "CONTRIBUTING.md should mention symlink setup or link to DEVELOPMENT.md"


class TestGitignoreSymlinkEntry:
    """Test .gitignore includes autonomous_dev entry."""

    def test_gitignore_exists(self):
        """Verify .gitignore file exists.

        REQUIREMENT: Git configuration must exist.
        Expected: File exists at .gitignore.
        """
        assert GITIGNORE.exists(), f".gitignore not found at {GITIGNORE}"

    def test_gitignore_includes_autonomous_dev_directory(self):
        """Verify .gitignore includes 'plugins/autonomous_dev' entry.

        REQUIREMENT: Prevent symlink from being committed to repository.
        Expected: Entry 'plugins/autonomous_dev' (with underscore) in .gitignore.
        """
        content = GITIGNORE.read_text()

        # Check for the symlink directory
        assert "plugins/autonomous_dev" in content, \
               ".gitignore should include 'plugins/autonomous_dev' to prevent symlink from being committed"

    def test_gitignore_entry_is_correctly_formatted(self):
        """Verify .gitignore entry is on its own line and properly formatted.

        REQUIREMENT: Correct gitignore syntax.
        Expected: Entry on dedicated line, not commented out.
        """
        content = GITIGNORE.read_text()
        lines = content.split('\n')

        # Find the line with autonomous_dev
        autonomous_dev_lines = [line for line in lines if "autonomous_dev" in line]

        assert len(autonomous_dev_lines) > 0, "Missing autonomous_dev entry in .gitignore"

        # Verify at least one line is not commented
        uncommented_lines = [line for line in autonomous_dev_lines if not line.strip().startswith('#')]
        assert len(uncommented_lines) > 0, \
               "autonomous_dev entry in .gitignore should not be commented out"


class TestCrossReferenceValidation:
    """Test cross-references between documentation files are valid."""

    def test_development_md_referenced_in_multiple_docs(self):
        """Verify DEVELOPMENT.md is referenced in multiple documentation files.

        REQUIREMENT: Cohesive documentation ecosystem.
        Expected: DEVELOPMENT.md mentioned in at least 3 other docs.
        """
        docs_to_check = [
            TROUBLESHOOTING_MD,
            PLUGIN_README,
            TESTS_README,
            CONTRIBUTING_MD
        ]

        references_found = 0
        for doc_path in docs_to_check:
            if doc_path.exists():
                content = doc_path.read_text()
                if "DEVELOPMENT.md" in content or "docs/DEVELOPMENT" in content:
                    references_found += 1

        assert references_found >= 3, \
               f"DEVELOPMENT.md should be referenced in at least 3 other docs, found {references_found}"

    def test_troubleshooting_linked_from_development(self):
        """Verify DEVELOPMENT.md links to TROUBLESHOOTING.md.

        REQUIREMENT: Bidirectional documentation links.
        Expected: Link from DEVELOPMENT.md to TROUBLESHOOTING.md.
        """
        if DEVELOPMENT_MD.exists():
            content = DEVELOPMENT_MD.read_text()
            assert "TROUBLESHOOTING.md" in content or "troubleshooting" in content.lower(), \
                   "DEVELOPMENT.md should link to TROUBLESHOOTING.md"

    def test_all_symlink_docs_use_consistent_terminology(self):
        """Verify all documentation uses consistent symlink terminology.

        REQUIREMENT: Consistency across documentation.
        Expected: All docs use 'autonomous_dev' (underscore) and 'autonomous-dev' (hyphen) consistently.
        """
        docs_to_check = [
            DEVELOPMENT_MD,
            TROUBLESHOOTING_MD,
            PLUGIN_README,
            TESTS_README,
            CONTRIBUTING_MD
        ]

        for doc_path in docs_to_check:
            if doc_path.exists():
                content = doc_path.read_text()

                # If document mentions symlink, it should use correct terminology
                if "symlink" in content.lower():
                    # Should mention both underscore and hyphen versions
                    assert "autonomous_dev" in content or "autonomous-dev" in content, \
                           f"{doc_path.name} mentions symlink but doesn't use consistent directory names"


class TestSymlinkCommandSyntaxValidation:
    """Test symlink command examples are syntactically correct."""

    def test_unix_symlink_command_syntax(self):
        """Verify Unix symlink command (ln -s) is syntactically correct.

        REQUIREMENT: Working commands for developers.
        Expected: ln -s <target> <link_name> format with correct paths.
        """
        if DEVELOPMENT_MD.exists():
            content = DEVELOPMENT_MD.read_text()

            # Extract ln commands
            ln_commands = re.findall(r'ln\s+-s\s+\S+\s+\S+', content)

            assert len(ln_commands) > 0, "No 'ln -s' commands found in DEVELOPMENT.md"

            for cmd in ln_commands:
                # Verify correct format: ln -s target link
                parts = cmd.split()
                assert len(parts) == 4, f"Invalid ln command format: {cmd}"
                assert parts[0] == "ln", f"Command should start with 'ln': {cmd}"
                assert parts[1] == "-s", f"Should use -s flag: {cmd}"

    def test_windows_symlink_command_syntax(self):
        """Verify Windows symlink command (mklink) is syntactically correct.

        REQUIREMENT: Working commands for Windows developers.
        Expected: mklink /D <link> <target> format with correct paths.
        """
        if DEVELOPMENT_MD.exists():
            content = DEVELOPMENT_MD.read_text()

            # Check for mklink or New-Item commands
            has_mklink = "mklink" in content.lower()
            has_new_item = "New-Item" in content

            assert has_mklink or has_new_item, \
                   "DEVELOPMENT.md should include Windows symlink command (mklink or New-Item)"

            if has_mklink:
                # Verify mklink format
                mklink_commands = re.findall(r'mklink\s+/[DJ]\s+\S+\s+\S+', content, re.IGNORECASE)
                assert len(mklink_commands) > 0, "mklink command should use /D or /J flag"

    def test_symlink_paths_use_relative_not_absolute(self):
        """Verify symlink commands use relative paths, not absolute paths.

        REQUIREMENT: Portability across different environments.
        Expected: No hardcoded absolute paths (/, C:\\, /Users/, etc.) in symlink commands.
        """
        if DEVELOPMENT_MD.exists():
            content = DEVELOPMENT_MD.read_text()

            # Extract code blocks
            code_blocks = re.findall(r'```(?:bash|sh|powershell)?\n(.*?)```', content, re.DOTALL)

            for block in code_blocks:
                if "ln -s" in block or "mklink" in block.lower():
                    # Should not contain absolute paths
                    assert not re.search(r'(/Users/|/home/|C:\\|D:\\)', block), \
                           "Symlink commands should use relative paths, not absolute paths"


class TestSecurityDocumentation:
    """Test security aspects of symlink are documented."""

    def test_documentation_explains_symlink_is_safe(self):
        """Verify documentation explains symlink is safe (relative, within repo).

        REQUIREMENT: Address security concerns proactively.
        Expected: Note explaining symlink safety in DEVELOPMENT.md or TROUBLESHOOTING.md.
        """
        docs_to_check = [DEVELOPMENT_MD, TROUBLESHOOTING_MD]

        security_explained = False
        for doc_path in docs_to_check:
            if doc_path.exists():
                content = doc_path.read_text()
                lower_content = content.lower()

                # Check for security-related keywords
                if any(word in lower_content for word in ["safe", "security", "relative path", "within repo"]):
                    security_explained = True
                    break

        assert security_explained, \
               "Documentation should explain symlink is safe (relative path, within repository)"

    def test_documentation_warns_against_committing_symlink(self):
        """Verify documentation warns against committing symlink to git.

        REQUIREMENT: Prevent common mistakes.
        Expected: Warning about symlink being gitignored and should not be committed.
        """
        if DEVELOPMENT_MD.exists():
            content = DEVELOPMENT_MD.read_text()
            lower_content = content.lower()

            # Check for warning about git/commit
            assert any(word in lower_content for word in ["gitignore", "not commit", "ignored by git"]), \
                   "DEVELOPMENT.md should mention symlink is gitignored"


class TestDocumentationCompleteness:
    """Test overall completeness of symlink documentation."""

    def test_all_required_files_exist(self):
        """Verify all required documentation files exist.

        REQUIREMENT: Complete documentation ecosystem.
        Expected: All 6 documentation files exist.
        """
        required_files = [
            DEVELOPMENT_MD,
            TROUBLESHOOTING_MD,
            PLUGIN_README,
            TESTS_README,
            CONTRIBUTING_MD,
            GITIGNORE
        ]

        missing_files = [f for f in required_files if not f.exists()]

        assert len(missing_files) == 0, \
               f"Missing required documentation files: {[str(f) for f in missing_files]}"

    def test_documentation_provides_complete_workflow(self):
        """Verify documentation provides complete setup workflow.

        REQUIREMENT: Developer can successfully set up environment from docs alone.
        Expected: DEVELOPMENT.md has create → verify → test → troubleshoot workflow.
        """
        if DEVELOPMENT_MD.exists():
            content = DEVELOPMENT_MD.read_text()
            lower_content = content.lower()

            # Check for complete workflow
            has_create = "ln -s" in content or "mklink" in lower_content
            has_verify = any(cmd in content for cmd in ["ls -la", "test -L", "dir"])
            has_test_reference = "pytest" in lower_content or "test" in lower_content
            has_troubleshoot = "troubleshoot" in lower_content or "TROUBLESHOOTING.md" in content

            assert has_create, "DEVELOPMENT.md should include symlink creation commands"
            assert has_verify, "DEVELOPMENT.md should include verification commands"
            assert has_test_reference or has_troubleshoot, \
                   "DEVELOPMENT.md should reference testing or troubleshooting"

    def test_documentation_is_searchable(self):
        """Verify symlink documentation is easy to find via search.

        REQUIREMENT: Discoverability via grep/search.
        Expected: Key terms (symlink, ModuleNotFoundError, autonomous_dev) appear in docs.
        """
        docs_to_check = [DEVELOPMENT_MD, TROUBLESHOOTING_MD, PLUGIN_README]

        keywords = ["symlink", "ModuleNotFoundError", "autonomous_dev"]

        for keyword in keywords:
            found_in_docs = 0
            for doc_path in docs_to_check:
                if doc_path.exists():
                    content = doc_path.read_text()
                    if keyword in content:
                        found_in_docs += 1

            assert found_in_docs >= 1, \
                   f"Keyword '{keyword}' should appear in at least one documentation file"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
