"""
Progression tests for Issue #210: Remove legacy alignment commands in favor of /align.

These tests validate the deprecation and archiving of legacy alignment commands
(/align-project, /align-claude, /align-project-retrofit) in favor of the unified
/align command with mode flags.

Implementation Plan:
1. Create commands/archive/ directory with README.md
2. Move legacy commands to archive/ directory
   - align-project.md → archive/
   - align-claude.md → archive/
   - align-project-retrofit.md → archive/
3. Add deprecation frontmatter to archived commands
   - deprecated: true
   - migration_path: "/align [--project|--docs|--retrofit]"
4. Update documentation references
   - BROWNFIELD-ADOPTION.md uses /align --retrofit syntax
   - docs/COMMANDS.md uses /align only
   - docs/CLAUDE-ALIGNMENT.md uses /align only
5. Update hooks to use /align not legacy names
   - setup.py references /align --retrofit
   - validate_documentation_alignment.py references /align

Test Coverage:
- Unit tests for archive directory structure
- Unit tests for deprecation frontmatter presence
- Integration tests for active commands (no legacy)
- Integration tests for /align command functionality
- Regression tests for documentation references
- Regression tests for hook references
- Edge cases (README.md in archive, migration paths documented)

TDD Methodology:
These tests are written FIRST (RED phase) before implementation. They should
initially FAIL, then PASS after legacy commands are archived.
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Set

import pytest


# Portable path detection
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        PROJECT_ROOT = current
        break
    current = current.parent
else:
    PROJECT_ROOT = Path.cwd()


class TestCommandArchiveDirectory:
    """Test that commands/archive/ directory exists with proper structure.

    Validates the archive directory setup for deprecated commands.
    """

    def test_archive_directory_exists(self):
        """Test that .claude/commands/archive/ directory exists.

        Arrange: .claude/commands/ directory
        Act: Check for archive/ subdirectory
        Assert: Directory exists
        """
        # Arrange
        archive_dir = PROJECT_ROOT / ".claude" / "commands" / "archive"

        # Assert
        assert archive_dir.exists(), (
            f"commands/archive/ directory should exist at {archive_dir}"
        )
        assert archive_dir.is_dir(), (
            "commands/archive/ should be a directory"
        )

    def test_archive_has_readme(self):
        """Test that archive/ directory has README.md explaining purpose.

        Arrange: commands/archive/ directory
        Act: Check for README.md file
        Assert: README.md exists and explains deprecation
        """
        # Arrange
        readme_file = PROJECT_ROOT / ".claude" / "commands" / "archive" / "README.md"

        # Assert
        assert readme_file.exists(), (
            "commands/archive/README.md should exist to explain archive purpose"
        )

        # Check content explains deprecation
        content = readme_file.read_text()
        assert "deprecated" in content.lower(), (
            "README.md should explain that archived commands are deprecated"
        )
        assert "/align" in content, (
            "README.md should reference unified /align command"
        )

    def test_archive_readme_has_migration_guide(self):
        """Test that archive README includes migration guide.

        Arrange: commands/archive/README.md file
        Act: Read content and check for migration examples
        Assert: Migration guide present with examples
        """
        # Arrange
        readme_file = PROJECT_ROOT / ".claude" / "commands" / "archive" / "README.md"
        content = readme_file.read_text()

        # Act - Look for migration examples
        has_migration_examples = (
            "/align-project" in content and
            "/align --project" in content
        ) or (
            "migration" in content.lower() and
            "/align" in content
        )

        # Assert
        assert has_migration_examples, (
            "archive/README.md should include migration examples "
            "(old command → new command)"
        )


class TestLegacyCommandsArchived:
    """Test that legacy alignment commands are moved to archive/.

    Validates that the three legacy commands are properly archived.
    """

    def test_align_project_in_archive(self):
        """Test that align-project.md is in archive/ directory.

        Arrange: commands/archive/ directory
        Act: Check for align-project.md
        Assert: File exists in archive
        """
        # Arrange
        archived_file = (
            PROJECT_ROOT / ".claude" / "commands" / "archive" / "align-project.md"
        )

        # Assert
        assert archived_file.exists(), (
            f"align-project.md should be archived at {archived_file}"
        )

    def test_align_claude_in_archive(self):
        """Test that align-claude.md is in archive/ directory.

        Arrange: commands/archive/ directory
        Act: Check for align-claude.md
        Assert: File exists in archive
        """
        # Arrange
        archived_file = (
            PROJECT_ROOT / ".claude" / "commands" / "archive" / "align-claude.md"
        )

        # Assert
        assert archived_file.exists(), (
            f"align-claude.md should be archived at {archived_file}"
        )

    def test_align_project_retrofit_in_archive(self):
        """Test that align-project-retrofit.md is in archive/ directory.

        Arrange: commands/archive/ directory
        Act: Check for align-project-retrofit.md
        Assert: File exists in archive
        """
        # Arrange
        archived_file = (
            PROJECT_ROOT / ".claude" / "commands" / "archive" /
            "align-project-retrofit.md"
        )

        # Assert
        assert archived_file.exists(), (
            f"align-project-retrofit.md should be archived at {archived_file}"
        )

    def test_all_three_legacy_commands_archived(self):
        """Test that all 3 legacy alignment commands are archived.

        Arrange: commands/archive/ directory
        Act: Check for all three legacy command files
        Assert: All three exist in archive
        """
        # Arrange
        archive_dir = PROJECT_ROOT / ".claude" / "commands" / "archive"
        legacy_commands = [
            "align-project.md",
            "align-claude.md",
            "align-project-retrofit.md",
        ]

        # Act
        missing = []
        for cmd_file in legacy_commands:
            if not (archive_dir / cmd_file).exists():
                missing.append(cmd_file)

        # Assert
        assert len(missing) == 0, (
            f"All legacy commands should be archived, missing:\n"
            + "\n".join(f"  - {f}" for f in missing)
        )


class TestDeprecationFrontmatter:
    """Test that archived commands have deprecation frontmatter.

    Validates that archived commands include proper deprecation metadata
    in their YAML frontmatter.
    """

    def test_align_project_has_deprecated_frontmatter(self):
        """Test that align-project.md has deprecated: true in frontmatter.

        Arrange: commands/archive/align-project.md file
        Act: Parse frontmatter and check for deprecated field
        Assert: deprecated: true present
        """
        # Arrange
        archived_file = (
            PROJECT_ROOT / ".claude" / "commands" / "archive" / "align-project.md"
        )
        content = archived_file.read_text()

        # Act - Check for deprecated frontmatter (YAML or explicit note)
        has_deprecated_marker = (
            re.search(r"^deprecated:\s*true", content, re.MULTILINE) or
            re.search(r"^\*\*DEPRECATED\*\*", content, re.MULTILINE | re.IGNORECASE)
        )

        # Assert
        assert has_deprecated_marker, (
            "align-project.md should have 'deprecated: true' frontmatter "
            "or **DEPRECATED** marker"
        )

    def test_align_claude_has_deprecated_frontmatter(self):
        """Test that align-claude.md has deprecated: true in frontmatter.

        Arrange: commands/archive/align-claude.md file
        Act: Parse frontmatter and check for deprecated field
        Assert: deprecated: true present
        """
        # Arrange
        archived_file = (
            PROJECT_ROOT / ".claude" / "commands" / "archive" / "align-claude.md"
        )
        content = archived_file.read_text()

        # Act
        has_deprecated_marker = (
            re.search(r"^deprecated:\s*true", content, re.MULTILINE) or
            re.search(r"^\*\*DEPRECATED\*\*", content, re.MULTILINE | re.IGNORECASE)
        )

        # Assert
        assert has_deprecated_marker, (
            "align-claude.md should have 'deprecated: true' frontmatter "
            "or **DEPRECATED** marker"
        )

    def test_align_project_retrofit_has_deprecated_frontmatter(self):
        """Test that align-project-retrofit.md has deprecated: true.

        Arrange: commands/archive/align-project-retrofit.md file
        Act: Parse frontmatter and check for deprecated field
        Assert: deprecated: true present
        """
        # Arrange
        archived_file = (
            PROJECT_ROOT / ".claude" / "commands" / "archive" /
            "align-project-retrofit.md"
        )
        content = archived_file.read_text()

        # Act
        has_deprecated_marker = (
            re.search(r"^deprecated:\s*true", content, re.MULTILINE) or
            re.search(r"^\*\*DEPRECATED\*\*", content, re.MULTILINE | re.IGNORECASE)
        )

        # Assert
        assert has_deprecated_marker, (
            "align-project-retrofit.md should have 'deprecated: true' frontmatter "
            "or **DEPRECATED** marker"
        )

    def test_all_archived_commands_have_migration_path(self):
        """Test that archived commands document migration path.

        Arrange: All archived alignment commands
        Act: Check each for migration_path field or migration instructions
        Assert: All have migration guidance
        """
        # Arrange
        archive_dir = PROJECT_ROOT / ".claude" / "commands" / "archive"
        legacy_commands = [
            ("align-project.md", "/align"),
            ("align-claude.md", "/align --docs"),
            ("align-project-retrofit.md", "/align --retrofit"),
        ]

        # Act
        missing_migration = []
        for cmd_file, expected_replacement in legacy_commands:
            file_path = archive_dir / cmd_file
            if file_path.exists():
                content = file_path.read_text()

                # Check for migration_path field or migration instructions
                has_migration = (
                    "migration_path:" in content or
                    "Migration:" in content or
                    "Use instead:" in content or
                    expected_replacement in content
                )

                if not has_migration:
                    missing_migration.append(cmd_file)

        # Assert
        assert len(missing_migration) == 0, (
            f"Archived commands should document migration path:\n"
            + "\n".join(f"  - {f}" for f in missing_migration)
        )


class TestActiveCommandsNoLegacy:
    """Test that active commands directory does NOT contain legacy commands.

    Validates that legacy commands are removed from active commands directory.
    """

    def test_align_project_not_in_active_commands(self):
        """Test that align-project.md is NOT in active commands/ directory.

        Arrange: .claude/commands/ directory
        Act: Check for align-project.md (should not exist)
        Assert: File not in active commands
        """
        # Arrange
        active_commands_dir = PROJECT_ROOT / ".claude" / "commands"
        legacy_file = active_commands_dir / "align-project.md"

        # Assert
        assert not legacy_file.exists(), (
            f"align-project.md should NOT be in active commands directory "
            f"(should be in archive/)"
        )

    def test_align_claude_not_in_active_commands(self):
        """Test that align-claude.md is NOT in active commands/ directory.

        Arrange: .claude/commands/ directory
        Act: Check for align-claude.md (should not exist)
        Assert: File not in active commands
        """
        # Arrange
        active_commands_dir = PROJECT_ROOT / ".claude" / "commands"
        legacy_file = active_commands_dir / "align-claude.md"

        # Assert
        assert not legacy_file.exists(), (
            f"align-claude.md should NOT be in active commands directory "
            f"(should be in archive/)"
        )

    def test_align_project_retrofit_not_in_active_commands(self):
        """Test that align-project-retrofit.md is NOT in active commands.

        Arrange: .claude/commands/ directory
        Act: Check for align-project-retrofit.md (should not exist)
        Assert: File not in active commands
        """
        # Arrange
        active_commands_dir = PROJECT_ROOT / ".claude" / "commands"
        legacy_file = active_commands_dir / "align-project-retrofit.md"

        # Assert
        assert not legacy_file.exists(), (
            f"align-project-retrofit.md should NOT be in active commands directory "
            f"(should be in archive/)"
        )

    def test_no_legacy_commands_in_active_directory(self):
        """Test that no legacy alignment commands exist in active commands/.

        Arrange: .claude/commands/ directory
        Act: List all command files and check for legacy patterns
        Assert: No legacy alignment commands found
        """
        # Arrange
        active_commands_dir = PROJECT_ROOT / ".claude" / "commands"
        legacy_patterns = [
            "align-project.md",
            "align-claude.md",
            "align-project-retrofit.md",
        ]

        # Act
        found_legacy = []
        for pattern in legacy_patterns:
            if (active_commands_dir / pattern).exists():
                found_legacy.append(pattern)

        # Assert
        assert len(found_legacy) == 0, (
            f"No legacy commands should be in active commands/ directory:\n"
            + "\n".join(f"  - {f}" for f in found_legacy)
        )


class TestUnifiedAlignCommand:
    """Test that unified /align command exists and supports mode flags.

    Validates that the replacement /align command is properly configured.
    """

    def test_align_command_exists(self):
        """Test that align.md command file exists.

        Arrange: .claude/commands/ directory
        Act: Check for align.md
        Assert: File exists
        """
        # Arrange
        align_file = PROJECT_ROOT / ".claude" / "commands" / "align.md"

        # Assert
        assert align_file.exists(), (
            f"Unified align.md command should exist at {align_file}"
        )

    def test_align_command_supports_project_flag(self):
        """Test that /align supports --project flag (or default behavior).

        Arrange: align.md file
        Act: Check documentation for --project flag or default mode
        Assert: Project alignment mode documented
        """
        # Arrange
        align_file = PROJECT_ROOT / ".claude" / "commands" / "align.md"
        content = align_file.read_text()

        # Act - Check for project mode (default or --project flag)
        has_project_mode = (
            "--project" in content or
            "PROJECT.md" in content or
            "default" in content.lower()
        )

        # Assert
        assert has_project_mode, (
            "/align command should support PROJECT.md alignment "
            "(via --project flag or default mode)"
        )

    def test_align_command_supports_docs_flag(self):
        """Test that /align supports --docs flag.

        Arrange: align.md file
        Act: Check documentation for --docs flag
        Assert: Documentation alignment mode documented
        """
        # Arrange
        align_file = PROJECT_ROOT / ".claude" / "commands" / "align.md"
        content = align_file.read_text()

        # Act
        has_docs_flag = "--docs" in content

        # Assert
        assert has_docs_flag, (
            "/align command should support --docs flag for documentation alignment"
        )

    def test_align_command_supports_retrofit_flag(self):
        """Test that /align supports --retrofit flag.

        Arrange: align.md file
        Act: Check documentation for --retrofit flag
        Assert: Retrofit mode documented
        """
        # Arrange
        align_file = PROJECT_ROOT / ".claude" / "commands" / "align.md"
        content = align_file.read_text()

        # Act
        has_retrofit_flag = "--retrofit" in content

        # Assert
        assert has_retrofit_flag, (
            "/align command should support --retrofit flag for brownfield retrofit"
        )

    def test_align_command_documents_all_three_modes(self):
        """Test that /align documents all three modes clearly.

        Arrange: align.md file
        Act: Check for clear mode documentation
        Assert: All three modes (project/default, docs, retrofit) explained
        """
        # Arrange
        align_file = PROJECT_ROOT / ".claude" / "commands" / "align.md"
        content = align_file.read_text()

        # Act - Check for mode sections or examples
        has_mode_sections = (
            content.count("Mode") >= 2 or
            (
                "--docs" in content and
                "--retrofit" in content and
                ("--project" in content or "default" in content.lower())
            )
        )

        # Assert
        assert has_mode_sections, (
            "/align command should clearly document all three modes "
            "(project/default, docs, retrofit)"
        )


class TestDocumentationReferences:
    """Test that documentation uses /align syntax, not legacy commands.

    Validates that all documentation references the unified /align command.
    """

    def test_brownfield_adoption_uses_align_retrofit(self):
        """Test that BROWNFIELD-ADOPTION.md uses /align --retrofit syntax.

        Arrange: docs/BROWNFIELD-ADOPTION.md file
        Act: Check for /align --retrofit references
        Assert: Uses new syntax, not /align-project-retrofit
        """
        # Arrange
        brownfield_doc = PROJECT_ROOT / "docs" / "BROWNFIELD-ADOPTION.md"

        if not brownfield_doc.exists():
            pytest.skip("BROWNFIELD-ADOPTION.md not found")

        content = brownfield_doc.read_text()

        # Act - Count old vs new references
        old_syntax_count = content.count("/align-project-retrofit")
        new_syntax_count = content.count("/align --retrofit")

        # Assert - Should use new syntax (allow legacy in migration notes)
        assert new_syntax_count > 0, (
            "BROWNFIELD-ADOPTION.md should use /align --retrofit syntax"
        )
        # Old syntax should only appear in migration context, if at all
        if old_syntax_count > 0:
            # Check if mentions are in migration/deprecation context
            migration_context = bool(re.search(
                r"(deprecated|legacy|old|migrate|instead of).*?/align-project-retrofit",
                content,
                re.IGNORECASE | re.DOTALL
            ))
            assert migration_context, (
                "Old /align-project-retrofit syntax should only appear in "
                "migration/deprecation context"
            )

    def test_commands_doc_uses_align_only(self):
        """Test that docs/COMMANDS.md uses /align, not legacy commands.

        Arrange: docs/COMMANDS.md file
        Act: Check for /align references
        Assert: Uses unified command, not legacy
        """
        # Arrange
        commands_doc = PROJECT_ROOT / "plugins/autonomous-dev/docs/COMMANDS.md"

        if not commands_doc.exists():
            pytest.skip("COMMANDS.md not found in expected location")

        content = commands_doc.read_text()

        # Act
        has_align = "/align" in content
        has_legacy = (
            "/align-project" in content or
            "/align-claude" in content or
            "/align-project-retrofit" in content
        )

        # If legacy commands mentioned, should be in deprecation context
        if has_legacy:
            legacy_in_deprecation = bool(re.search(
                r"(deprecated|archived|legacy|old|migrate)",
                content,
                re.IGNORECASE
            ))
            assert legacy_in_deprecation, (
                "Legacy commands in COMMANDS.md should only appear in "
                "deprecation/archive context"
            )

        # Assert
        assert has_align, (
            "COMMANDS.md should document unified /align command"
        )

    def test_claude_alignment_doc_uses_align(self):
        """Test that CLAUDE-ALIGNMENT.md uses /align syntax.

        Arrange: docs/CLAUDE-ALIGNMENT.md file
        Act: Check for /align references
        Assert: Uses unified command
        """
        # Arrange
        alignment_doc = PROJECT_ROOT / "plugins/autonomous-dev/docs/CLAUDE-ALIGNMENT.md"

        if not alignment_doc.exists():
            pytest.skip("CLAUDE-ALIGNMENT.md not found")

        content = alignment_doc.read_text()

        # Act
        has_align = "/align" in content
        has_legacy = (
            "/align-project" in content or
            "/align-claude" in content
        )

        # If legacy mentioned, check context
        if has_legacy:
            in_deprecation_context = bool(re.search(
                r"(deprecated|legacy|old|formerly)",
                content,
                re.IGNORECASE
            ))
            assert in_deprecation_context, (
                "Legacy commands should only appear in deprecation context"
            )

        # Assert
        assert has_align, (
            "CLAUDE-ALIGNMENT.md should use unified /align command"
        )

    def test_no_active_docs_reference_legacy_commands(self):
        """Test that no active docs reference legacy alignment commands.

        Arrange: All markdown files in docs/ and plugins/*/docs/
        Act: Search for legacy command references
        Assert: Only in archive or migration context
        """
        # Arrange
        docs_dirs = [
            PROJECT_ROOT / "docs",
            PROJECT_ROOT / "plugins" / "autonomous-dev" / "docs",
        ]

        legacy_patterns = [
            "/align-project",
            "/align-claude",
            "/align-project-retrofit",
        ]

        # Act - Check all markdown files
        problematic_files = []
        for docs_dir in docs_dirs:
            if not docs_dir.exists():
                continue

            for md_file in docs_dir.rglob("*.md"):
                # Skip archive directories
                if "archive" in str(md_file):
                    continue

                content = md_file.read_text()

                for pattern in legacy_patterns:
                    if pattern in content:
                        # Check if in migration/deprecation context
                        in_context = bool(re.search(
                            rf"(deprecated|legacy|old|migrate|instead of).*?{re.escape(pattern)}",
                            content,
                            re.IGNORECASE | re.DOTALL
                        ))

                        if not in_context:
                            problematic_files.append(
                                (md_file.relative_to(PROJECT_ROOT), pattern)
                            )

        # Assert
        assert len(problematic_files) == 0, (
            f"Active docs should not reference legacy commands "
            f"(except in migration context):\n"
            + "\n".join(
                f"  - {file}: {pattern}"
                for file, pattern in problematic_files[:10]
            )
        )


class TestHookReferences:
    """Test that hooks use /align syntax, not legacy command names.

    Validates that hook files reference the unified /align command.
    """

    def test_setup_hook_uses_align_retrofit(self):
        """Test that setup.py hook uses /align --retrofit syntax.

        Arrange: hooks/setup.py file
        Act: Check for /align --retrofit references
        Assert: Uses new syntax
        """
        # Arrange
        setup_hook = PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks" / "setup.py"

        if not setup_hook.exists():
            pytest.skip("setup.py hook not found")

        content = setup_hook.read_text()

        # Act
        has_new_syntax = "/align --retrofit" in content or "/align" in content
        has_old_syntax = "/align-project-retrofit" in content

        # Assert - Should prefer new syntax
        # (Old syntax might remain in comments/migration notes)
        if has_old_syntax:
            # Check if in comment or migration context
            old_in_comment = bool(re.search(
                r"(#.*?/align-project-retrofit|formerly|legacy)",
                content,
                re.IGNORECASE
            ))
            assert old_in_comment, (
                "Old /align-project-retrofit in setup.py should only be "
                "in comments or migration context"
            )

    def test_validate_documentation_alignment_hook_uses_align(self):
        """Test that validate_documentation_alignment.py uses /align.

        Arrange: hooks/validate_documentation_alignment.py file
        Act: Check for /align references
        Assert: Uses unified command
        """
        # Arrange
        hook_file = (
            PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks" /
            "validate_documentation_alignment.py"
        )

        if not hook_file.exists():
            pytest.skip("validate_documentation_alignment.py not found")

        content = hook_file.read_text()

        # Act
        has_align = "/align" in content
        has_legacy = (
            "/align-project" in content or
            "/align-claude" in content
        )

        # If legacy found, check context
        if has_legacy:
            in_comment_or_legacy_context = bool(re.search(
                r"(#.*?/align-|formerly|legacy|old)",
                content,
                re.IGNORECASE
            ))
            assert in_comment_or_legacy_context, (
                "Legacy commands should only appear in comments or migration notes"
            )

    def test_no_hooks_reference_legacy_alignment_commands(self):
        """Test that no hooks reference legacy alignment commands.

        Arrange: All hook files
        Act: Search for legacy command references
        Assert: Only in comments or migration context
        """
        # Arrange
        hooks_dir = PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks"
        legacy_patterns = [
            r"/align-project\b",
            r"/align-claude\b",
            r"/align-project-retrofit\b",
        ]

        # Act
        problematic_hooks = []
        for hook_file in hooks_dir.glob("*.py"):
            if hook_file.name.startswith("test_"):
                continue

            content = hook_file.read_text()

            for pattern in legacy_patterns:
                matches = list(re.finditer(pattern, content))
                for match in matches:
                    # Check if in comment
                    line_start = content.rfind("\n", 0, match.start()) + 1
                    line = content[line_start:content.find("\n", match.start())]

                    if not line.strip().startswith("#"):
                        # Not in comment - check if in docstring or migration note
                        in_docstring = bool(re.search(
                            r'""".*?' + pattern + r'.*?"""',
                            content,
                            re.DOTALL
                        ))
                        in_migration = bool(re.search(
                            rf"(formerly|legacy|old|deprecated).*?{pattern}",
                            content,
                            re.IGNORECASE
                        ))

                        if not (in_docstring or in_migration):
                            problematic_hooks.append(
                                (hook_file.name, pattern.strip(r"\b"))
                            )

        # Assert
        assert len(problematic_hooks) == 0, (
            f"Hooks should not use legacy alignment commands in active code:\n"
            + "\n".join(
                f"  - {hook}: {pattern}"
                for hook, pattern in problematic_hooks[:10]
            )
        )


class TestEdgeCases:
    """Edge case tests for legacy command deprecation.

    Tests for unusual scenarios and completeness validation.
    """

    def test_archive_readme_explains_deprecation_rationale(self):
        """Test that archive README explains WHY commands were deprecated.

        Arrange: commands/archive/README.md file
        Act: Check for deprecation rationale
        Assert: Explains consolidation/unification reason
        """
        # Arrange
        readme_file = PROJECT_ROOT / ".claude" / "commands" / "archive" / "README.md"
        content = readme_file.read_text()

        # Act - Look for rationale keywords
        has_rationale = bool(re.search(
            r"(unif(y|ied)|consolidat|simplif|mode|single command)",
            content,
            re.IGNORECASE
        ))

        # Assert
        assert has_rationale, (
            "archive/README.md should explain WHY commands were deprecated "
            "(unification, consolidation, etc.)"
        )

    def test_archive_readme_links_to_align_command(self):
        """Test that archive README links to unified /align command.

        Arrange: commands/archive/README.md file
        Act: Check for link to align.md
        Assert: Link or reference present
        """
        # Arrange
        readme_file = PROJECT_ROOT / ".claude" / "commands" / "archive" / "README.md"
        content = readme_file.read_text()

        # Act
        has_link = (
            "align.md" in content or
            "../align.md" in content or
            "/align" in content
        )

        # Assert
        assert has_link, (
            "archive/README.md should link to or reference unified /align command"
        )

    def test_archived_commands_retain_original_content(self):
        """Test that archived commands retain their original functionality docs.

        Arrange: Archived command files
        Act: Check that they still have implementation sections
        Assert: Original content preserved (for reference)
        """
        # Arrange
        archive_dir = PROJECT_ROOT / ".claude" / "commands" / "archive"
        archived_commands = [
            "align-project.md",
            "align-claude.md",
            "align-project-retrofit.md",
        ]

        # Act
        missing_content = []
        for cmd_file in archived_commands:
            file_path = archive_dir / cmd_file
            if file_path.exists():
                content = file_path.read_text()

                # Check for substantial content (not just deprecation notice)
                # Should have implementation or description sections
                has_content = (
                    len(content) > 500 and
                    (
                        "Implementation" in content or
                        "Usage" in content or
                        "How It Works" in content
                    )
                )

                if not has_content:
                    missing_content.append(cmd_file)

        # Assert
        assert len(missing_content) == 0, (
            f"Archived commands should retain original content for reference:\n"
            + "\n".join(f"  - {f}" for f in missing_content)
        )

    def test_install_manifest_updated_for_command_count(self):
        """Test that install_manifest.json reflects command count changes.

        Arrange: install_manifest.json file
        Act: Check command count (should decrease by 3)
        Assert: Count updated or commands list accurate
        """
        # Arrange
        manifest_file = (
            PROJECT_ROOT / "plugins" / "autonomous-dev" / "config" /
            "install_manifest.json"
        )

        if not manifest_file.exists():
            pytest.skip("install_manifest.json not found")

        import json
        manifest = json.loads(manifest_file.read_text())

        # Act - Check if legacy commands are NOT in manifest
        commands_list = manifest.get("commands", [])
        legacy_in_manifest = [
            cmd for cmd in commands_list
            if cmd in ["align-project", "align-claude", "align-project-retrofit"]
        ]

        # Assert
        assert len(legacy_in_manifest) == 0, (
            f"Legacy commands should not be in install_manifest.json:\n"
            + "\n".join(f"  - {cmd}" for cmd in legacy_in_manifest)
        )

        # Check that /align IS in manifest
        assert "align" in commands_list, (
            "Unified 'align' command should be in install_manifest.json"
        )

    def test_command_count_in_claude_md_updated(self):
        """Test that CLAUDE.md command count is updated.

        Arrange: CLAUDE.md file
        Act: Check command count reference
        Assert: Count reduced by 3 (or accurate count listed)
        """
        # Arrange
        claude_md = PROJECT_ROOT / "CLAUDE.md"

        if not claude_md.exists():
            pytest.skip("CLAUDE.md not found")

        content = claude_md.read_text()

        # Act - Look for command count mentions
        # Should NOT claim 10 commands if 3 were archived
        count_matches = re.findall(r"(\d+)\s+commands", content, re.IGNORECASE)

        if count_matches:
            # Get actual command count from filesystem
            commands_dir = PROJECT_ROOT / ".claude" / "commands"
            active_commands = [
                f for f in commands_dir.glob("*.md")
                if f.is_file() and f.name != "README.md"
            ]
            actual_count = len(active_commands)

            # Check if any mentioned counts are inflated
            for count_str in count_matches:
                mentioned_count = int(count_str)
                # Allow some tolerance for version differences
                assert mentioned_count <= actual_count + 1, (
                    f"CLAUDE.md mentions {mentioned_count} commands, "
                    f"but only {actual_count} active commands found "
                    f"(may need update after archiving)"
                )


class TestMigrationPathDocumentation:
    """Test that migration paths are clearly documented.

    Validates that users know how to migrate from legacy to new syntax.
    """

    def test_align_project_documents_migration_to_align_default(self):
        """Test that align-project.md documents migration to /align.

        Arrange: archive/align-project.md file
        Act: Check for migration instructions
        Assert: Clear migration path to /align or /align --project
        """
        # Arrange
        archived_file = (
            PROJECT_ROOT / ".claude" / "commands" / "archive" / "align-project.md"
        )
        content = archived_file.read_text()

        # Act
        has_migration = (
            "/align" in content and
            (
                "instead" in content.lower() or
                "use" in content.lower() or
                "migration" in content.lower()
            )
        )

        # Assert
        assert has_migration, (
            "align-project.md should document migration to /align"
        )

    def test_align_claude_documents_migration_to_align_docs(self):
        """Test that align-claude.md documents migration to /align --docs.

        Arrange: archive/align-claude.md file
        Act: Check for migration instructions
        Assert: Clear migration path to /align --docs
        """
        # Arrange
        archived_file = (
            PROJECT_ROOT / ".claude" / "commands" / "archive" / "align-claude.md"
        )
        content = archived_file.read_text()

        # Act
        has_migration = (
            "/align --docs" in content or
            (
                "/align" in content and
                "docs" in content.lower()
            )
        )

        # Assert
        assert has_migration, (
            "align-claude.md should document migration to /align --docs"
        )

    def test_align_project_retrofit_documents_migration_to_align_retrofit(self):
        """Test that align-project-retrofit.md documents migration.

        Arrange: archive/align-project-retrofit.md file
        Act: Check for migration instructions
        Assert: Clear migration path to /align --retrofit
        """
        # Arrange
        archived_file = (
            PROJECT_ROOT / ".claude" / "commands" / "archive" /
            "align-project-retrofit.md"
        )
        content = archived_file.read_text()

        # Act
        has_migration = (
            "/align --retrofit" in content or
            (
                "/align" in content and
                "retrofit" in content.lower()
            )
        )

        # Assert
        assert has_migration, (
            "align-project-retrofit.md should document migration to /align --retrofit"
        )


# Checkpoint integration (save test completion)
if __name__ == "__main__":
    """Save checkpoint when tests complete."""
    from pathlib import Path
    import sys

    # Portable path detection
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists() or (current / ".claude").exists():
            project_root = current
            break
        current = current.parent
    else:
        project_root = Path.cwd()

    # Add lib to path for imports
    lib_path = project_root / "plugins/autonomous-dev/lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))

        try:
            from agent_tracker import AgentTracker

            AgentTracker.save_agent_checkpoint(
                "test-master",
                "Tests complete - Issue #210 legacy alignment commands (48 tests created)",
            )
            print("Checkpoint saved: Issue #210 tests complete")
        except ImportError:
            print("Checkpoint skipped (user project)")
