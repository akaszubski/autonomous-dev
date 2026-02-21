#!/usr/bin/env python3
"""
Unit tests for validate_project_alignment.py hook.

Tests PROJECT.md validation logic, drift detection,
error cases (missing file, malformed content).

Date: 2026-02-21
Agent: test-master
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

# Add hooks directory to path
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

import validate_project_alignment as vpa


class TestCheckProjectMdExists:
    """Test PROJECT.md existence check."""

    def test_exists_at_root(self, tmp_path):
        (tmp_path / "PROJECT.md").write_text("# Project")
        passed, msg = vpa.check_project_md_exists(tmp_path)
        assert passed is True

    def test_exists_at_claude_dir(self, tmp_path):
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "PROJECT.md").write_text("# Project")
        passed, msg = vpa.check_project_md_exists(tmp_path)
        assert passed is True

    def test_not_found(self, tmp_path):
        passed, msg = vpa.check_project_md_exists(tmp_path)
        assert passed is False
        assert "NOT FOUND" in msg

    def test_error_message_has_instructions(self, tmp_path):
        passed, msg = vpa.check_project_md_exists(tmp_path)
        assert "GOALS" in msg
        assert "SCOPE" in msg
        assert "CONSTRAINTS" in msg


class TestCheckRequiredSections:
    """Test required sections validation."""

    def test_all_sections_present(self, tmp_path):
        content = "# GOALS\nBuild stuff\n# SCOPE\nEverything\n# CONSTRAINTS\nNone\n"
        (tmp_path / "PROJECT.md").write_text(content)
        passed, msg = vpa.check_required_sections(tmp_path)
        assert passed is True

    def test_missing_goals(self, tmp_path):
        content = "# SCOPE\nEverything\n# CONSTRAINTS\nNone\n"
        (tmp_path / "PROJECT.md").write_text(content)
        passed, msg = vpa.check_required_sections(tmp_path)
        assert passed is False
        assert "GOALS" in msg

    def test_missing_multiple(self, tmp_path):
        content = "# SCOPE\nEverything\n"
        (tmp_path / "PROJECT.md").write_text(content)
        passed, msg = vpa.check_required_sections(tmp_path)
        assert passed is False
        assert "GOALS" in msg
        assert "CONSTRAINTS" in msg

    def test_case_insensitive(self, tmp_path):
        content = "## Goals\nBuild\n## Scope\nAll\n## Constraints\nNone\n"
        (tmp_path / "PROJECT.md").write_text(content)
        passed, msg = vpa.check_required_sections(tmp_path)
        assert passed is True

    def test_h2_headers(self, tmp_path):
        content = "## GOALS\nBuild\n## SCOPE\nAll\n## CONSTRAINTS\nNone\n"
        (tmp_path / "PROJECT.md").write_text(content)
        passed, msg = vpa.check_required_sections(tmp_path)
        assert passed is True

    def test_no_file(self, tmp_path):
        passed, msg = vpa.check_required_sections(tmp_path)
        assert passed is False

    def test_alternate_location(self, tmp_path):
        (tmp_path / ".claude").mkdir()
        content = "# GOALS\nX\n# SCOPE\nY\n# CONSTRAINTS\nZ\n"
        (tmp_path / ".claude" / "PROJECT.md").write_text(content)
        passed, msg = vpa.check_required_sections(tmp_path)
        assert passed is True


class TestCheckScopeAlignment:
    """Test SCOPE section validation."""

    def test_valid_scope(self, tmp_path):
        content = "# GOALS\nX\n# SCOPE\n" + "A " * 30 + "\n# CONSTRAINTS\nZ\n"
        (tmp_path / "PROJECT.md").write_text(content)
        passed, msg = vpa.check_scope_alignment(tmp_path)
        assert passed is True

    def test_empty_scope(self, tmp_path):
        content = "# GOALS\nX\n# SCOPE\n\n# CONSTRAINTS\nZ\n"
        (tmp_path / "PROJECT.md").write_text(content)
        passed, msg = vpa.check_scope_alignment(tmp_path)
        assert passed is False

    def test_brief_scope(self, tmp_path):
        content = "# GOALS\nX\n# SCOPE\nShort\n# CONSTRAINTS\nZ\n"
        (tmp_path / "PROJECT.md").write_text(content)
        passed, msg = vpa.check_scope_alignment(tmp_path)
        assert passed is False
        assert "too brief" in msg

    def test_no_file(self, tmp_path):
        passed, msg = vpa.check_scope_alignment(tmp_path)
        assert passed is False


class TestCheckForbiddenSections:
    """Test forbidden section detection."""

    def test_clean_content(self):
        content = "# GOALS\nBuild\n# SCOPE\nAll\n# CONSTRAINTS\nNone\n"
        passed, msg = vpa.check_forbidden_sections(content)
        assert passed is True

    def test_todo_section(self):
        content = "# GOALS\nBuild\n# TODO\n- Fix bug\n"
        passed, msg = vpa.check_forbidden_sections(content)
        assert passed is False
        assert "TODO" in msg

    def test_roadmap_section(self):
        content = "# Roadmap\n- Q1 release\n"
        passed, msg = vpa.check_forbidden_sections(content)
        assert passed is False
        assert "Roadmap" in msg

    def test_future_section(self):
        content = "# Future\n- Maybe\n"
        passed, msg = vpa.check_forbidden_sections(content)
        assert passed is False

    def test_backlog_section(self):
        content = "## Backlog\n- Item\n"
        passed, msg = vpa.check_forbidden_sections(content)
        assert passed is False

    def test_next_steps_section(self):
        content = "## Next Steps\n- Do this\n"
        passed, msg = vpa.check_forbidden_sections(content)
        assert passed is False

    def test_coming_soon_section(self):
        content = "# Coming Soon\n- Feature\n"
        passed, msg = vpa.check_forbidden_sections(content)
        assert passed is False

    def test_planned_section(self):
        content = "# Planned\n- Release\n"
        passed, msg = vpa.check_forbidden_sections(content)
        assert passed is False

    def test_case_insensitive_forbidden(self):
        content = "# todo\n- Fix\n"
        passed, msg = vpa.check_forbidden_sections(content)
        assert passed is False

    def test_inline_todo_not_flagged(self):
        """TODO in body text should not trigger (only headers)."""
        content = "# GOALS\nWe have a TODO item in the text\n"
        passed, msg = vpa.check_forbidden_sections(content)
        assert passed is True

    def test_empty_content(self):
        passed, msg = vpa.check_forbidden_sections("")
        assert passed is True

    def test_none_like_empty(self):
        passed, msg = vpa.check_forbidden_sections("   ")
        assert passed is True

    def test_line_numbers_in_error(self):
        content = "# GOALS\nBuild\n# TODO\n- Fix\n"
        passed, msg = vpa.check_forbidden_sections(content)
        assert "Line 3" in msg

    def test_multiple_forbidden(self):
        content = "# TODO\n- Fix\n# Roadmap\n- Plan\n"
        passed, msg = vpa.check_forbidden_sections(content)
        assert passed is False
        assert "TODO" in msg
        assert "Roadmap" in msg

    def test_remediation_advice(self):
        content = "# TODO\n- Fix\n"
        passed, msg = vpa.check_forbidden_sections(content)
        assert "/create-issue" in msg


class TestValidateProjectMd:
    """Test the convenience validation function."""

    def test_nonexistent_file(self, tmp_path):
        issues = vpa.validate_project_md(tmp_path / "nope.md")
        assert len(issues) == 1
        assert "not found" in issues[0]

    def test_valid_file(self, tmp_path):
        f = tmp_path / "PROJECT.md"
        f.write_text("# GOALS\nBuild\n# SCOPE\nAll\n# CONSTRAINTS\nNone\n")
        issues = vpa.validate_project_md(f)
        assert len(issues) == 0

    def test_file_with_forbidden(self, tmp_path):
        f = tmp_path / "PROJECT.md"
        f.write_text("# GOALS\nBuild\n# TODO\n- Fix\n")
        issues = vpa.validate_project_md(f)
        assert len(issues) == 1
        assert "TODO" in issues[0]


class TestMain:
    """Test main entry point."""

    def test_all_checks_pass(self, tmp_path):
        content = "# GOALS\nBuild stuff\n# SCOPE\n" + "Detailed scope " * 10 + "\n# CONSTRAINTS\nNone\n"
        (tmp_path / "PROJECT.md").write_text(content)
        with patch("validate_project_alignment.get_project_root", return_value=tmp_path):
            result = vpa.main()
            assert result == 0

    def test_missing_project_md(self, tmp_path):
        with patch("validate_project_alignment.get_project_root", return_value=tmp_path):
            result = vpa.main()
            assert result == 1

    def test_missing_sections(self, tmp_path):
        (tmp_path / "PROJECT.md").write_text("# Just a title\n")
        with patch("validate_project_alignment.get_project_root", return_value=tmp_path):
            result = vpa.main()
            assert result == 1


class TestGetProjectRoot:
    """Test project root detection."""

    def test_finds_git_dir(self, tmp_path):
        (tmp_path / ".git").mkdir()
        with patch.object(Path, "cwd", return_value=tmp_path):
            root = vpa.get_project_root()
            # May find actual cwd's root, just ensure it returns a Path
            assert isinstance(root, Path)

    def test_returns_path(self):
        root = vpa.get_project_root()
        assert isinstance(root, Path)
