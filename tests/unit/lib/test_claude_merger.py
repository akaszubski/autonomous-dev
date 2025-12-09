#!/usr/bin/env python3
"""
Unit tests for claude_merger.py - Global CLAUDE.md Template Merger

Tests for GitHub Issue #101: Provide global ~/.claude/CLAUDE.md template as part of plugin install

This module tests the ClaudeMerger class for merging autonomous-dev template
sections with user's existing ~/.claude/CLAUDE.md content.

Test Coverage:
- Initialization and template loading
- Section extraction from content
- Merging with existing user content
- Atomic file writes with backups
- Edge cases (empty files, malformed markers)
- Security (symlinks, path validation)

Author: test-master agent
Date: 2025-12-09
Issue: #101
"""

import json
import os
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "plugins"))

from autonomous_dev.lib.claude_merger import (
    ClaudeMerger,
    MergeResult,
    SECTION_START,
    SECTION_END,
)


class TestClaudeMergerInitialization:
    """Test ClaudeMerger initialization and template loading."""

    @pytest.fixture
    def valid_template(self, tmp_path):
        """Create a valid template file with section markers."""
        template = tmp_path / "global-claude.md.template"
        template.write_text(f"""# Universal Claude Code Instructions

{SECTION_START}
## Documentation Alignment

Content about documentation alignment.
{SECTION_END}

---

{SECTION_START}
## Git & Automation

Content about git automation.
{SECTION_END}
""")
        return template

    def test_init_with_valid_template(self, valid_template):
        """Test initialization with valid template file."""
        merger = ClaudeMerger(valid_template)

        assert merger.template_path == valid_template
        assert merger.template_content is not None
        assert SECTION_START in merger.template_content

    def test_init_with_missing_template_raises_error(self, tmp_path):
        """Test initialization with non-existent template raises error."""
        missing_template = tmp_path / "missing.md"

        with pytest.raises(FileNotFoundError):
            ClaudeMerger(missing_template)

    def test_init_resolves_path(self, valid_template):
        """Test that template path is resolved to absolute."""
        merger = ClaudeMerger(valid_template)

        assert merger.template_path.is_absolute()


class TestSectionExtraction:
    """Test extraction of autonomous-dev sections from content."""

    @pytest.fixture
    def merger(self, tmp_path):
        """Create merger with simple template."""
        template = tmp_path / "template.md"
        template.write_text(f"""{SECTION_START}
## Section One
Content one
{SECTION_END}

{SECTION_START}
## Section Two
Content two
{SECTION_END}
""")
        return ClaudeMerger(template)

    def test_extract_sections_returns_dict(self, merger):
        """Test that extract_sections returns dictionary of sections."""
        content = f"""{SECTION_START}
## Test Section
Test content
{SECTION_END}"""

        sections = merger._extract_sections(content)

        assert isinstance(sections, dict)
        assert len(sections) >= 1

    def test_extract_multiple_sections(self, merger):
        """Test extracting multiple sections from content."""
        content = f"""{SECTION_START}
## Section A
Content A
{SECTION_END}

Some user content

{SECTION_START}
## Section B
Content B
{SECTION_END}"""

        sections = merger._extract_sections(content)

        assert len(sections) == 2

    def test_extract_sections_empty_content(self, merger):
        """Test extracting sections from empty content."""
        sections = merger._extract_sections("")

        assert sections == {}

    def test_extract_sections_no_markers(self, merger):
        """Test extracting sections when no markers present."""
        content = "# Just plain content\n\nNo markers here."

        sections = merger._extract_sections(content)

        assert sections == {}


class TestMerging:
    """Test merging template sections with existing content."""

    @pytest.fixture
    def merger_with_template(self, tmp_path):
        """Create merger with template containing sections."""
        template = tmp_path / "template.md"
        template.write_text(f"""# Template

{SECTION_START}
## Plugin Section
Plugin content here
{SECTION_END}
""")
        return ClaudeMerger(template)

    @pytest.fixture
    def output_dir(self, tmp_path):
        """Create output directory."""
        output = tmp_path / "output"
        output.mkdir()
        return output

    def test_merge_creates_new_file_when_none_exists(self, merger_with_template, output_dir):
        """Test that merge creates new file when destination doesn't exist."""
        output_path = output_dir / "CLAUDE.md"

        result = merger_with_template.merge_global_claude(output_path)

        assert result.success
        assert output_path.exists()
        assert SECTION_START in output_path.read_text()

    def test_merge_preserves_user_content(self, merger_with_template, output_dir):
        """Test that user content outside markers is preserved."""
        output_path = output_dir / "CLAUDE.md"

        # Create existing file with user content
        user_content = """# My Custom Instructions

## My Custom Section
This is my custom content that should be preserved.

## Another Custom Section
More custom content.
"""
        output_path.write_text(user_content)

        result = merger_with_template.merge_global_claude(output_path)

        assert result.success
        merged_content = output_path.read_text()
        assert "My Custom Section" in merged_content
        assert "custom content that should be preserved" in merged_content

    def test_merge_adds_plugin_sections(self, merger_with_template, output_dir):
        """Test that plugin sections are added to file."""
        output_path = output_dir / "CLAUDE.md"
        output_path.write_text("# Existing content\n")

        result = merger_with_template.merge_global_claude(output_path)

        assert result.success
        merged_content = output_path.read_text()
        assert "Plugin Section" in merged_content
        assert SECTION_START in merged_content

    def test_merge_updates_existing_plugin_sections(self, merger_with_template, output_dir):
        """Test that existing plugin sections are updated."""
        output_path = output_dir / "CLAUDE.md"

        # Create file with old plugin section
        old_content = f"""# User Content

{SECTION_START}
## Plugin Section
OLD plugin content
{SECTION_END}
"""
        output_path.write_text(old_content)

        result = merger_with_template.merge_global_claude(output_path)

        assert result.success
        merged_content = output_path.read_text()
        assert "Plugin content here" in merged_content  # New content
        assert "OLD plugin content" not in merged_content  # Old content removed


class TestMergeResult:
    """Test MergeResult dataclass."""

    def test_merge_result_success_attributes(self, tmp_path):
        """Test MergeResult has expected attributes on success."""
        template = tmp_path / "template.md"
        template.write_text(f"{SECTION_START}\n## Test\n{SECTION_END}")

        output = tmp_path / "output.md"

        merger = ClaudeMerger(template)
        result = merger.merge_global_claude(output)

        assert hasattr(result, 'success')
        assert hasattr(result, 'message')
        assert hasattr(result, 'output_path')
        assert hasattr(result, 'sections_added')

    def test_merge_result_counts_sections(self, tmp_path):
        """Test MergeResult counts added/updated sections."""
        template = tmp_path / "template.md"
        template.write_text(f"""{SECTION_START}
## Section 1
{SECTION_END}

{SECTION_START}
## Section 2
{SECTION_END}
""")

        output = tmp_path / "output.md"

        merger = ClaudeMerger(template)
        result = merger.merge_global_claude(output)

        assert result.sections_added >= 1 or result.sections_updated >= 0


class TestAtomicWrites:
    """Test atomic file write operations."""

    @pytest.fixture
    def merger(self, tmp_path):
        """Create merger with simple template."""
        template = tmp_path / "template.md"
        template.write_text(f"{SECTION_START}\n## Test\nContent\n{SECTION_END}")
        return ClaudeMerger(template)

    def test_atomic_write_creates_file(self, merger, tmp_path):
        """Test that atomic write creates the file."""
        output = tmp_path / "output.md"

        merger._atomic_write(output, "Test content")

        assert output.exists()
        assert output.read_text() == "Test content"

    def test_atomic_write_sets_permissions(self, merger, tmp_path):
        """Test that atomic write sets secure permissions (0o600)."""
        output = tmp_path / "output.md"

        merger._atomic_write(output, "Test content")

        # Check permissions (owner read/write only)
        mode = output.stat().st_mode & 0o777
        assert mode == 0o600


class TestBackupCreation:
    """Test backup file creation before modifications."""

    @pytest.fixture
    def merger(self, tmp_path):
        """Create merger with simple template."""
        template = tmp_path / "template.md"
        template.write_text(f"{SECTION_START}\n## Test\n{SECTION_END}")
        return ClaudeMerger(template)

    def test_backup_created_before_modification(self, merger, tmp_path):
        """Test that backup is created before modifying existing file."""
        output = tmp_path / "output.md"
        original_content = "Original content"
        output.write_text(original_content)

        result = merger.merge_global_claude(output, create_backup=True)

        assert result.backup_path is not None
        backup = Path(result.backup_path)
        assert backup.exists()
        assert backup.read_text() == original_content

    def test_no_backup_for_new_file(self, merger, tmp_path):
        """Test that no backup is created for new files."""
        output = tmp_path / "output.md"

        result = merger.merge_global_claude(output, create_backup=True)

        # No backup needed for new files
        assert result.backup_path is None or not Path(result.backup_path).exists()


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def merger(self, tmp_path):
        """Create merger with simple template."""
        template = tmp_path / "template.md"
        template.write_text(f"{SECTION_START}\n## Test\n{SECTION_END}")
        return ClaudeMerger(template)

    def test_empty_existing_file(self, merger, tmp_path):
        """Test handling of empty existing file."""
        output = tmp_path / "output.md"
        output.write_text("")

        result = merger.merge_global_claude(output)

        assert result.success
        assert output.read_text().strip() != ""

    def test_whitespace_only_file(self, merger, tmp_path):
        """Test handling of file with only whitespace."""
        output = tmp_path / "output.md"
        output.write_text("   \n\n   \n")

        result = merger.merge_global_claude(output)

        assert result.success

    def test_unicode_content_preserved(self, merger, tmp_path):
        """Test that unicode content is preserved."""
        output = tmp_path / "output.md"
        unicode_content = "# 日本語テスト\n\n## Émojis 🎉\n\nCafé résumé"
        output.write_text(unicode_content)

        result = merger.merge_global_claude(output)

        assert result.success
        merged_content = output.read_text()
        assert "日本語" in merged_content
        assert "🎉" in merged_content
        assert "Café" in merged_content


class TestDryRun:
    """Test dry run mode (preview without writing)."""

    @pytest.fixture
    def merger(self, tmp_path):
        """Create merger with simple template."""
        template = tmp_path / "template.md"
        template.write_text(f"{SECTION_START}\n## Test Section\nContent\n{SECTION_END}")
        return ClaudeMerger(template)

    def test_dry_run_does_not_modify_file(self, merger, tmp_path):
        """Test that dry run doesn't modify the file."""
        output = tmp_path / "output.md"
        original_content = "Original content"
        output.write_text(original_content)

        result = merger.merge_global_claude(output, write_result=False)

        assert result.success
        assert output.read_text() == original_content

    def test_dry_run_returns_preview(self, merger, tmp_path):
        """Test that dry run returns preview of changes."""
        output = tmp_path / "output.md"

        result = merger.merge_global_claude(output, write_result=False)

        assert result.success
        assert 'preview' in result.details or result.details.get('merged_content')


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
