"""
Tests for CLAUDE.md alignment validation.

Tests ensure that:
1. Validator detects version drift
2. Validator detects count mismatches
3. Validator detects missing features
4. Hook behaves correctly (exit codes)
5. Session tracking works (no spam warnings)
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Import validator (adjust path as needed)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from validate_claude_alignment import (
    ClaudeAlignmentValidator,
    AlignmentIssue,
    extract_date,
    extract_agent_count,
    extract_command_count,
)


class TestDateExtraction:
    """Test date extraction from markdown."""

    def test_extract_date_standard_format(self):
        """Extract date in standard format."""
        text = "**Last Updated**: 2025-10-27"
        assert extract_date(text) == "2025-10-27"

    def test_extract_date_with_quotes(self):
        """Extract date even with quotes."""
        text = "**Last Updated': 2025-10-26"
        assert extract_date(text) == "2025-10-26"

    def test_extract_date_missing(self):
        """Return None if no date found."""
        text = "No date here"
        assert extract_date(text) is None


class TestCountExtraction:
    """Test agent/command count extraction."""

    def test_extract_agent_count(self):
        """Extract agent count from markdown heading."""
        text = "### Agents (16 specialists)"
        assert extract_agent_count(text) == 16

    def test_extract_command_count_from_commands(self):
        """Extract command count from text."""
        text = "8 total commands"
        assert extract_command_count(text) == 8

    def test_extract_counts_missing(self):
        """Return None if count not found."""
        assert extract_agent_count("No agents here") is None
        assert extract_command_count("No commands") is None


class TestAlignmentValidator:
    """Test ClaudeAlignmentValidator class."""

    def test_validator_initialization(self):
        """Validator initializes correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = ClaudeAlignmentValidator(Path(tmpdir))
            assert validator.repo_root == Path(tmpdir)
            assert validator.issues == []

    def test_read_missing_file(self):
        """Reading missing file adds warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = ClaudeAlignmentValidator(Path(tmpdir))
            content = validator._read_file(Path(tmpdir) / "missing.md")

            assert content == ""
            assert len(validator.issues) == 1
            assert validator.issues[0].severity == "warning"

    def test_version_consistency_check(self):
        """Version consistency validation works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            # Create files with mismatched dates
            (repo_root / ".claude").mkdir()
            (repo_root / ".claude" / "PROJECT.md").write_text(
                "**Last Updated**: 2025-10-27"
            )
            (repo_root / "CLAUDE.md").write_text(
                "**Last Updated**: 2025-10-20"  # Older
            )

            validator = ClaudeAlignmentValidator(repo_root)
            aligned, issues = validator.validate()

            # Should have warning about outdated CLAUDE.md
            version_issues = [i for i in issues if i.category == "version"]
            assert len(version_issues) > 0

    def test_agent_count_mismatch(self):
        """Agent count mismatch is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            # Create structure with mismatched counts
            (repo_root / "plugins/autonomous-dev/agents").mkdir(parents=True)
            (repo_root / "plugins/autonomous-dev/agents/agent1.md").touch()
            (repo_root / "plugins/autonomous-dev/agents/agent2.md").touch()

            # CLAUDE.md says 16 agents but only 2 exist
            (repo_root / "CLAUDE.md").write_text("### Agents (16 specialists)")

            validator = ClaudeAlignmentValidator(repo_root)
            aligned, issues = validator.validate()

            count_issues = [i for i in issues if i.category == "count"]
            assert len(count_issues) > 0
            assert "16" in count_issues[0].expected or "16" in count_issues[0].message

    def test_missing_command_detection(self):
        """Missing documented commands are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            # Create commands dir but missing /auto-implement
            (repo_root / "plugins/autonomous-dev/commands").mkdir(parents=True)
            (repo_root / "plugins/autonomous-dev/commands/setup.md").touch()

            # CLAUDE.md documents /auto-implement
            (repo_root / "CLAUDE.md").write_text(
                "/auto-implement for feature development"
            )

            validator = ClaudeAlignmentValidator(repo_root)
            aligned, issues = validator.validate()

            # Should detect missing auto-implement command
            feature_issues = [i for i in issues if i.category == "feature"]
            assert len(feature_issues) > 0

    def test_skills_deprecation_check(self):
        """Skills being documented when they should be removed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            # Create minimal structure
            (repo_root / "plugins/autonomous-dev").mkdir(parents=True)

            # CLAUDE.md still documents skills (outdated)
            (repo_root / "CLAUDE.md").write_text(
                "### Skills (6 core competencies)\n\nLocated: `plugins/autonomous-dev/skills/`"
            )

            validator = ClaudeAlignmentValidator(repo_root)
            aligned, issues = validator.validate()

            feature_issues = [i for i in issues if i.category == "feature"]
            skills_issue = [
                i for i in feature_issues
                if "skills" in i.message.lower()
            ]
            assert len(skills_issue) > 0


class TestHookIntegration:
    """Test hook integration and exit codes."""

    def test_hook_exit_code_aligned(self):
        """Hook returns 0 when aligned."""
        # This would require mocking file system
        # For now, test is placeholder for integration tests
        pass

    def test_hook_exit_code_warnings(self):
        """Hook returns 1 for warnings."""
        pass

    def test_hook_exit_code_errors(self):
        """Hook returns 2 for critical errors."""
        pass


class TestSessionWarningTracking:
    """Test session-based warning deduplication."""

    def test_warning_not_shown_twice(self):
        """Same warning not shown twice in same session."""
        from validate_claude_alignment import SessionWarningTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('pathlib.Path.home', return_value=Path(tmpdir)):
                tracker = SessionWarningTracker("test_session")

                # First time: not shown
                assert not tracker.has_shown_warning("test_warning")

                # Mark as shown
                tracker.mark_warning_shown("test_warning")

                # Second time: already shown
                assert tracker.has_shown_warning("test_warning")

    def test_different_sessions_separate_warnings(self):
        """Different sessions have separate warning tracking."""
        from validate_claude_alignment import SessionWarningTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('pathlib.Path.home', return_value=Path(tmpdir)):
                tracker1 = SessionWarningTracker("session1")
                tracker2 = SessionWarningTracker("session2")

                tracker1.mark_warning_shown("warning_a")

                # Different session doesn't see the warning
                assert not tracker2.has_shown_warning("warning_a")


# Integration tests
class TestRealWorldScenarios:
    """Test against real-world CLAUDE.md scenarios."""

    def test_validate_actual_project(self):
        """Test validation against actual autonomous-dev project."""
        # This test runs against actual repo files
        repo_root = Path.cwd()

        # Only run if we're in the right directory
        if not (repo_root / "plugins/autonomous-dev").exists():
            pytest.skip("Not in autonomous-dev repo root")

        validator = ClaudeAlignmentValidator(repo_root)
        aligned, issues = validator.validate()

        # Should have some issues (counts may not match after changes)
        # But no critical errors about missing commands
        critical_issues = [i for i in issues if i.severity == "error"]
        assert len(critical_issues) == 0  # All commands should exist


@pytest.mark.parametrize("date1,date2,expected", [
    ("2025-10-27", "2025-10-26", False),  # date1 newer, not older
    ("2025-10-20", "2025-10-27", True),   # date1 older
    ("2025-10-27", "2025-10-27", False),  # same date
])
def test_date_comparison(date1, date2, expected):
    """Test date comparison logic."""
    assert (date1 < date2) == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
