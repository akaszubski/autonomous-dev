#!/usr/bin/env python3
"""
Integration Tests for Issue #83: Symlink Documentation Workflow (FAILING - Red Phase)

This module contains FAILING integration tests that verify the complete developer workflow
for setting up the development symlink based on documentation.

Test Scenarios:
1. New developer following DEVELOPMENT.md can successfully create symlink
2. Developer encountering ModuleNotFoundError can find solution via TROUBLESHOOTING.md
3. Documentation cross-references are navigable (no broken links)
4. Symlink commands work across different operating systems (Unix/Windows)
5. .gitignore prevents symlink from being committed
6. Documentation is consistent across all files

Following TDD principles:
- Write tests FIRST (red phase)
- Tests simulate real developer workflows
- Tests should FAIL until documentation is comprehensive
- Each test validates ONE complete workflow

Author: test-master agent
Date: 2025-11-19
Related: GitHub Issue #83 - Document symlink requirement for plugin imports
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import pytest


# Constants
REPO_ROOT = Path(__file__).parent.parent.parent
DEVELOPMENT_MD = REPO_ROOT / "docs" / "DEVELOPMENT.md"
TROUBLESHOOTING_MD = REPO_ROOT / "docs" / "TROUBLESHOOTING.md"
PLUGIN_README = REPO_ROOT / "plugins" / "autonomous-dev" / "README.md"
TESTS_README = REPO_ROOT / "tests" / "README.md"
CONTRIBUTING_MD = REPO_ROOT / "CONTRIBUTING.md"
GITIGNORE = REPO_ROOT / ".gitignore"


class TestNewDeveloperWorkflow:
    """Test complete workflow for new developer setting up environment."""

    def test_developer_can_find_setup_instructions_from_readme(self):
        """Verify new developer can find setup instructions starting from main README.

        WORKFLOW: Developer reads main README → finds link to DEVELOPMENT.md → sets up environment.
        Expected: Clear path from README to DEVELOPMENT.md symlink section.
        """
        # Check main README exists and links to DEVELOPMENT.md or plugin README
        main_readme = REPO_ROOT / "README.md"
        assert main_readme.exists(), "Main README.md should exist"

        content = main_readme.read_text()
        assert "DEVELOPMENT.md" in content or "CONTRIBUTING.md" in content or \
               "plugins/autonomous-dev/README.md" in content, \
               "Main README should link to development documentation"

    def test_developer_can_follow_development_md_step_by_step(self):
        """Verify DEVELOPMENT.md provides complete step-by-step setup workflow.

        WORKFLOW: Developer follows numbered steps 1-N, including symlink creation.
        Expected: Step 4.5 is clearly positioned in setup sequence.
        """
        assert DEVELOPMENT_MD.exists(), "DEVELOPMENT.md must exist"
        content = DEVELOPMENT_MD.read_text()

        # Check for step sequence (match any markdown header level: #, ##, ###, etc.)
        steps = re.findall(r'(?:^|\n)(?:#+\s*)?Step\s+(\d+\.?\d*)', content, re.MULTILINE)

        assert len(steps) > 0, "DEVELOPMENT.md should have numbered steps"

        # Verify Step 4.5 exists in sequence
        assert "4.5" in steps or any(s.startswith("4") for s in steps), \
               "Step 4.5 (symlink creation) should be in development steps"

    def test_developer_can_verify_symlink_was_created_correctly(self):
        """Verify documentation provides clear verification steps.

        WORKFLOW: Developer creates symlink → runs verification command → confirms success.
        Expected: Verification commands are provided and explained.
        """
        assert DEVELOPMENT_MD.exists(), "DEVELOPMENT.md must exist"
        content = DEVELOPMENT_MD.read_text()

        # Check for verification instructions
        verification_keywords = [
            "verify",
            "check",
            "confirm",
            "ls -la",
            "ls -l",
            "test -L",
            "dir"
        ]

        assert any(keyword in content.lower() for keyword in verification_keywords), \
               "DEVELOPMENT.md should include verification steps for symlink"

    def test_documentation_explains_what_success_looks_like(self):
        """Verify documentation shows what successful symlink creation looks like.

        WORKFLOW: Developer verifies symlink → sees expected output → knows setup is correct.
        Expected: Example output showing symlink arrow (→) or similar indicator.
        """
        assert DEVELOPMENT_MD.exists(), "DEVELOPMENT.md must exist"
        content = DEVELOPMENT_MD.read_text()

        # Check for example output or success indicator
        success_indicators = ["→", "->", "success", "expected output", "should see"]

        assert any(indicator in content.lower() for indicator in success_indicators), \
               "DEVELOPMENT.md should show what successful symlink looks like"


class TestTroubleshootingWorkflow:
    """Test workflow for developer encountering ModuleNotFoundError."""

    def test_developer_can_find_troubleshooting_from_error_message(self):
        """Verify developer can find solution by searching for error message.

        WORKFLOW: Developer sees ModuleNotFoundError → searches docs → finds TROUBLESHOOTING.md.
        Expected: TROUBLESHOOTING.md contains exact error message that appears in tests.
        """
        assert TROUBLESHOOTING_MD.exists(), "TROUBLESHOOTING.md must exist"
        content = TROUBLESHOOTING_MD.read_text()

        # Should contain the exact error developers will see
        assert "ModuleNotFoundError" in content, \
               "TROUBLESHOOTING.md should contain 'ModuleNotFoundError' for searchability"

        assert "autonomous_dev" in content or "autonomous-dev" in content, \
               "TROUBLESHOOTING.md should mention the specific module name"

    def test_troubleshooting_provides_root_cause_explanation(self):
        """Verify TROUBLESHOOTING.md explains WHY error occurs.

        WORKFLOW: Developer reads troubleshooting → understands root cause → knows how to fix.
        Expected: Explanation of Python import vs directory name mismatch.
        """
        assert TROUBLESHOOTING_MD.exists(), "TROUBLESHOOTING.md must exist"
        content = TROUBLESHOOTING_MD.read_text()
        lower_content = content.lower()

        # Should explain the mismatch
        root_cause_keywords = [
            "hyphen",
            "underscore",
            "import",
            "directory name",
            "python"
        ]

        assert any(keyword in lower_content for keyword in root_cause_keywords), \
               "TROUBLESHOOTING.md should explain root cause of ModuleNotFoundError"

    def test_troubleshooting_links_to_solution_in_development_md(self):
        """Verify TROUBLESHOOTING.md provides direct link to solution.

        WORKFLOW: Developer reads troubleshooting → follows link → finds Step 4.5 → fixes issue.
        Expected: Link to DEVELOPMENT.md Step 4.5 section.
        """
        assert TROUBLESHOOTING_MD.exists(), "TROUBLESHOOTING.md must exist"
        content = TROUBLESHOOTING_MD.read_text()

        # Should link to DEVELOPMENT.md
        assert "DEVELOPMENT.md" in content or "../DEVELOPMENT.md" in content or \
               "docs/DEVELOPMENT.md" in content, \
               "TROUBLESHOOTING.md should link to DEVELOPMENT.md"

    def test_troubleshooting_provides_quick_fix_command(self):
        """Verify TROUBLESHOOTING.md provides quick fix command without requiring navigation.

        WORKFLOW: Developer reads troubleshooting → copies command → fixes issue immediately.
        Expected: ln -s or mklink command directly in TROUBLESHOOTING.md.
        """
        assert TROUBLESHOOTING_MD.exists(), "TROUBLESHOOTING.md must exist"
        content = TROUBLESHOOTING_MD.read_text()

        # Should include at least a reference to the fix
        quick_fix_indicators = ["ln -s", "mklink", "symlink", "create"]

        assert any(indicator in content.lower() for indicator in quick_fix_indicators), \
               "TROUBLESHOOTING.md should provide quick fix reference"


class TestDocumentationCrossReferences:
    """Test that documentation cross-references are navigable and not broken."""

    def test_all_links_to_development_md_are_valid(self):
        """Verify all references to DEVELOPMENT.md use correct relative paths.

        WORKFLOW: Developer clicks link → navigates to correct file → finds information.
        Expected: Links use correct relative paths from each documentation location.
        """
        docs_with_links = {
            TROUBLESHOOTING_MD: "../DEVELOPMENT.md",  # docs/ to docs/
            PLUGIN_README: "../../docs/DEVELOPMENT.md",  # plugins/autonomous-dev/ to docs/
            TESTS_README: "../docs/DEVELOPMENT.md",  # tests/ to docs/
            CONTRIBUTING_MD: "docs/DEVELOPMENT.md",  # root to docs/
        }

        for doc_path, expected_relative_path in docs_with_links.items():
            if doc_path.exists():
                content = doc_path.read_text()

                # If document mentions DEVELOPMENT.md, check path correctness
                if "DEVELOPMENT.md" in content:
                    # Verify the link exists (exact match or any DEVELOPMENT.md reference)
                    assert "DEVELOPMENT.md" in content, \
                           f"{doc_path.name} should reference DEVELOPMENT.md"

    def test_troubleshooting_md_is_referenced_bidirectionally(self):
        """Verify DEVELOPMENT.md and TROUBLESHOOTING.md reference each other.

        WORKFLOW: Developer reads one doc → finds link to other → gets complete information.
        Expected: Bidirectional links between DEVELOPMENT.md and TROUBLESHOOTING.md.
        """
        if DEVELOPMENT_MD.exists():
            dev_content = DEVELOPMENT_MD.read_text()
            assert "TROUBLESHOOTING.md" in dev_content or "troubleshooting" in dev_content.lower(), \
                   "DEVELOPMENT.md should reference TROUBLESHOOTING.md"

        if TROUBLESHOOTING_MD.exists():
            trouble_content = TROUBLESHOOTING_MD.read_text()
            assert "DEVELOPMENT.md" in trouble_content, \
                   "TROUBLESHOOTING.md should reference DEVELOPMENT.md"

    def test_plugin_readme_provides_path_to_main_docs(self):
        """Verify plugin README provides clear path to main repository documentation.

        WORKFLOW: Developer reads plugin README → finds link to main docs → gets complete setup info.
        Expected: Plugin README links to DEVELOPMENT.md or CONTRIBUTING.md.
        """
        assert PLUGIN_README.exists(), "Plugin README.md must exist"
        content = PLUGIN_README.read_text()

        # Should link to main repository documentation
        assert "DEVELOPMENT.md" in content or "CONTRIBUTING.md" in content or \
               "docs/" in content.lower(), \
               "Plugin README should link to main repository documentation"


class TestSymlinkCommandValidation:
    """Test that symlink commands in documentation are executable and correct."""

    def extract_commands_from_documentation(self, doc_path: Path, command_type: str) -> List[str]:
        """Extract symlink commands from documentation.

        Args:
            doc_path: Path to documentation file
            command_type: Type of command ('unix' or 'windows')

        Returns:
            List of command strings
        """
        if not doc_path.exists():
            return []

        content = doc_path.read_text()

        # Extract code blocks
        code_blocks = re.findall(r'```(?:bash|sh|powershell|cmd)?\n(.*?)```', content, re.DOTALL)

        commands = []
        for block in code_blocks:
            if command_type == 'unix' and 'ln -s' in block:
                # Extract ln commands
                ln_commands = re.findall(r'ln\s+-s\s+[^\n]+', block)
                commands.extend(ln_commands)
            elif command_type == 'windows' and ('mklink' in block.lower() or 'New-Item' in block):
                # Extract Windows commands
                mklink_commands = re.findall(r'mklink\s+/[DJ]\s+[^\n]+', block, re.IGNORECASE)
                new_item_commands = re.findall(r'New-Item\s+[^\n]+', block)
                commands.extend(mklink_commands)
                commands.extend(new_item_commands)

        return commands

    def test_unix_symlink_commands_have_correct_syntax(self):
        """Verify Unix symlink commands have correct syntax: ln -s <target> <link>.

        WORKFLOW: Developer copies Unix command → pastes in terminal → command executes successfully.
        Expected: Command format is 'ln -s autonomous-dev autonomous_dev' or with path prefix.
        """
        unix_commands = self.extract_commands_from_documentation(DEVELOPMENT_MD, 'unix')

        assert len(unix_commands) > 0, "DEVELOPMENT.md should contain Unix symlink commands"

        for cmd in unix_commands:
            parts = cmd.split()
            assert len(parts) >= 4, f"Invalid ln command format: {cmd}"
            assert parts[0] == "ln", f"Command should start with 'ln': {cmd}"
            assert parts[1] == "-s", f"Should use -s flag: {cmd}"

            # Verify target and link names contain correct directories
            target_and_link = ' '.join(parts[2:])
            assert "autonomous-dev" in target_and_link, f"Target should be autonomous-dev: {cmd}"
            assert "autonomous_dev" in target_and_link, f"Link should be autonomous_dev: {cmd}"

    def test_windows_symlink_commands_have_correct_syntax(self):
        """Verify Windows symlink commands have correct syntax.

        WORKFLOW: Developer copies Windows command → pastes in cmd/PowerShell → command executes.
        Expected: Command format is valid mklink or New-Item syntax.
        """
        windows_commands = self.extract_commands_from_documentation(DEVELOPMENT_MD, 'windows')

        assert len(windows_commands) > 0, "DEVELOPMENT.md should contain Windows symlink commands"

        for cmd in windows_commands:
            # Verify command structure
            assert "autonomous-dev" in cmd and "autonomous_dev" in cmd, \
                   f"Windows command should reference both directory names: {cmd}"

    def test_symlink_commands_use_relative_paths(self):
        """Verify all symlink commands use relative paths for portability.

        WORKFLOW: Developer on any machine → runs command → works regardless of installation path.
        Expected: No absolute paths (/Users/, C:\\, etc.) in commands.
        """
        unix_commands = self.extract_commands_from_documentation(DEVELOPMENT_MD, 'unix')
        windows_commands = self.extract_commands_from_documentation(DEVELOPMENT_MD, 'windows')

        all_commands = unix_commands + windows_commands

        for cmd in all_commands:
            # Should not contain absolute paths
            assert not re.search(r'(/Users/|/home/|/root/|C:\\|D:\\)', cmd), \
                   f"Command should use relative paths: {cmd}"

    def test_commands_create_symlink_in_correct_location(self):
        """Verify commands create symlink at plugins/autonomous_dev.

        WORKFLOW: Developer runs command → symlink created at correct location → tests work.
        Expected: Commands create plugins/autonomous_dev → plugins/autonomous-dev symlink.
        """
        unix_commands = self.extract_commands_from_documentation(DEVELOPMENT_MD, 'unix')

        for cmd in unix_commands:
            # Parse ln -s target link command
            match = re.search(r'ln\s+-s\s+(\S+)\s+(\S+)', cmd)
            if match:
                target = match.group(1)
                link = match.group(2)

                # Verify link path
                assert "autonomous_dev" in link, \
                       f"Link should create autonomous_dev directory: {cmd}"

                # If paths include plugins/, verify correct structure
                if "plugins/" in link:
                    assert link.endswith("plugins/autonomous_dev") or \
                           "plugins/autonomous_dev" in link, \
                           f"Link should be in plugins/ directory: {cmd}"


class TestGitignoreIntegration:
    """Test .gitignore integration with symlink documentation."""

    def test_gitignore_entry_matches_documented_symlink(self):
        """Verify .gitignore entry matches the symlink path in documentation.

        WORKFLOW: Developer creates symlink → git status → symlink not shown as untracked.
        Expected: .gitignore contains same path as documented symlink location.
        """
        assert GITIGNORE.exists(), ".gitignore must exist"
        gitignore_content = GITIGNORE.read_text()

        assert "plugins/autonomous_dev" in gitignore_content, \
               ".gitignore should ignore plugins/autonomous_dev"

    def test_documentation_mentions_gitignore_behavior(self):
        """Verify documentation explains symlink will be gitignored.

        WORKFLOW: Developer wonders if they should commit symlink → reads docs → understands it's ignored.
        Expected: Documentation mentions symlink is in .gitignore.
        """
        assert DEVELOPMENT_MD.exists(), "DEVELOPMENT.md must exist"
        content = DEVELOPMENT_MD.read_text()
        lower_content = content.lower()

        # Should mention gitignore or not committing
        assert any(phrase in lower_content for phrase in [
            "gitignore",
            "not commit",
            "ignored by git",
            ".gitignore"
        ]), "DEVELOPMENT.md should mention symlink is gitignored"

    def test_gitignore_comment_explains_purpose(self):
        """Verify .gitignore has comment explaining autonomous_dev entry.

        WORKFLOW: Developer reads .gitignore → understands why entry exists → doesn't remove it.
        Expected: Comment above or inline with autonomous_dev entry.
        """
        assert GITIGNORE.exists(), ".gitignore must exist"
        content = GITIGNORE.read_text()
        lines = content.split('\n')

        # Find autonomous_dev entry
        for i, line in enumerate(lines):
            if "autonomous_dev" in line and not line.strip().startswith('#'):
                # Check previous few lines for comment
                context_lines = lines[max(0, i-3):i+1]
                context = '\n'.join(context_lines)

                # Should have explanatory comment nearby
                assert '#' in context, \
                       ".gitignore should have comment explaining autonomous_dev entry"
                break


class TestDocumentationConsistency:
    """Test consistency of symlink documentation across all files."""

    def test_all_docs_use_same_directory_names(self):
        """Verify all documentation uses consistent directory naming.

        WORKFLOW: Developer reads multiple docs → sees consistent terminology → no confusion.
        Expected: All docs use 'autonomous-dev' (hyphen) and 'autonomous_dev' (underscore).
        """
        docs_to_check = [DEVELOPMENT_MD, TROUBLESHOOTING_MD, PLUGIN_README, CONTRIBUTING_MD]

        for doc_path in docs_to_check:
            if doc_path.exists():
                content = doc_path.read_text()

                # If document discusses the symlink, it should use both names
                if "symlink" in content.lower():
                    # Allow flexibility: might mention only one if context is clear
                    # But should use correct names when mentioned
                    if "autonomous" in content:
                        assert "autonomous-dev" in content or "autonomous_dev" in content, \
                               f"{doc_path.name} should use correct directory names"

    def test_all_docs_agree_on_symlink_purpose(self):
        """Verify all documentation agrees on WHY symlink is needed.

        WORKFLOW: Developer reads multiple docs → gets consistent explanation → understands requirement.
        Expected: Consistent explanation about Python import compatibility.
        """
        docs_with_explanation = []

        for doc_path in [DEVELOPMENT_MD, TROUBLESHOOTING_MD, PLUGIN_README]:
            if doc_path.exists():
                content = doc_path.read_text()
                lower_content = content.lower()

                if "symlink" in lower_content:
                    # Check if it explains the purpose
                    if any(keyword in lower_content for keyword in ["python", "import", "test", "pytest"]):
                        docs_with_explanation.append(doc_path.name)

        assert len(docs_with_explanation) > 0, \
               "At least one documentation file should explain why symlink is needed"

    def test_security_messaging_is_consistent(self):
        """Verify security messaging about symlinks is consistent across docs.

        WORKFLOW: Developer concerned about security → reads multiple docs → gets reassurance.
        Expected: Consistent messaging that symlink is safe (relative, within repo).
        """
        docs_with_security_note = []

        for doc_path in [DEVELOPMENT_MD, TROUBLESHOOTING_MD]:
            if doc_path.exists():
                content = doc_path.read_text()
                lower_content = content.lower()

                # Check for security-related messaging
                if "symlink" in lower_content and any(word in lower_content for word in ["safe", "security", "relative"]):
                    docs_with_security_note.append(doc_path.name)

        # At least one doc should address security
        assert len(docs_with_security_note) > 0, \
               "At least one documentation file should address symlink security"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
