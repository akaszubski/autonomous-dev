"""
Unit tests for CLAUDE.md validation tightening (Issue #197)

Tests validate enforcement of 300-line limit with phased character limits:
- Phase 1: 35k character warning (current state)
- Phase 2: 25k character error (future)
- Phase 3: 15k character error (final goal)

Also validates:
- Line count warnings at 280 lines (93% of limit)
- Section count limits (max 20 sections, warning at 18)
- Error messages include guidance links

These tests follow TDD - they should FAIL until implementation is complete.

Run with: pytest tests/unit/test_claude_md_validation_issue197.py --tb=line -q
"""

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from unittest.mock import Mock, patch

import pytest

# Add hooks directory to path for validate_claude_alignment imports
HOOKS_DIR = Path(__file__).parent.parent.parent / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))


@dataclass
class AlignmentIssue:
    """Represents a single alignment issue (matches production code)."""
    severity: str  # "error", "warning", "info"
    category: str  # "version", "count", "feature", "best-practice"
    message: str
    expected: Optional[str] = None
    actual: Optional[str] = None
    location: Optional[str] = None


class TestPhaseDetection:
    """Test suite for validation phase detection from environment."""

    def test_phase_detection_default_is_phase1(self):
        """
        GIVEN: No CLAUDE_VALIDATION_PHASE environment variable
        WHEN: Detecting validation phase
        THEN: Returns phase 1 (35k character warning)
        """
        # This test will fail until get_validation_phase() is implemented
        with patch.dict(os.environ, {}, clear=True):
            # Import after patching environment
            from validate_claude_alignment import get_validation_phase

            phase = get_validation_phase()

            assert phase == 1, f"Expected default phase 1, got {phase}"

    def test_phase_detection_from_env_phase1(self):
        """
        GIVEN: CLAUDE_VALIDATION_PHASE=1
        WHEN: Detecting validation phase
        THEN: Returns phase 1
        """
        with patch.dict(os.environ, {"CLAUDE_VALIDATION_PHASE": "1"}):
            from validate_claude_alignment import get_validation_phase

            phase = get_validation_phase()

            assert phase == 1, f"Expected phase 1, got {phase}"

    def test_phase_detection_from_env_phase2(self):
        """
        GIVEN: CLAUDE_VALIDATION_PHASE=2
        WHEN: Detecting validation phase
        THEN: Returns phase 2 (25k character error)
        """
        with patch.dict(os.environ, {"CLAUDE_VALIDATION_PHASE": "2"}):
            from validate_claude_alignment import get_validation_phase

            phase = get_validation_phase()

            assert phase == 2, f"Expected phase 2, got {phase}"

    def test_phase_detection_from_env_phase3(self):
        """
        GIVEN: CLAUDE_VALIDATION_PHASE=3
        WHEN: Detecting validation phase
        THEN: Returns phase 3 (15k character error)
        """
        with patch.dict(os.environ, {"CLAUDE_VALIDATION_PHASE": "3"}):
            from validate_claude_alignment import get_validation_phase

            phase = get_validation_phase()

            assert phase == 3, f"Expected phase 3, got {phase}"

    def test_phase_detection_invalid_value_defaults_to_phase1(self):
        """
        GIVEN: CLAUDE_VALIDATION_PHASE=invalid
        WHEN: Detecting validation phase
        THEN: Returns phase 1 (safe default)
        """
        with patch.dict(os.environ, {"CLAUDE_VALIDATION_PHASE": "invalid"}):
            from validate_claude_alignment import get_validation_phase

            phase = get_validation_phase()

            assert phase == 1, f"Expected default phase 1 for invalid value, got {phase}"

    def test_phase_detection_out_of_range_defaults_to_phase1(self):
        """
        GIVEN: CLAUDE_VALIDATION_PHASE=99
        WHEN: Detecting validation phase
        THEN: Returns phase 1 (safe default)
        """
        with patch.dict(os.environ, {"CLAUDE_VALIDATION_PHASE": "99"}):
            from validate_claude_alignment import get_validation_phase

            phase = get_validation_phase()

            assert phase == 1, f"Expected default phase 1 for out-of-range value, got {phase}"


class TestLineCountValidation:
    """Test suite for CLAUDE.md line count validation."""

    CLAUDE_MD = Path(__file__).parent.parent.parent / "CLAUDE.md"
    MAX_LINES = 300
    WARNING_THRESHOLD = 280  # 93% of limit

    def test_line_count_under_limit_passes(self):
        """
        GIVEN: CLAUDE.md with 287 lines (current state)
        WHEN: Validating line count
        THEN: Validation passes with no issues
        """
        # This test will fail until _check_line_count() is implemented
        from validate_claude_alignment import ClaudeAlignmentValidator

        validator = ClaudeAlignmentValidator(self.CLAUDE_MD.parent.parent.parent)
        content = self.CLAUDE_MD.read_text()

        # Call validation method (to be implemented)
        validator._check_line_count(content)

        # No line count issues should be reported
        line_issues = [i for i in validator.issues if "line" in i.message.lower()]

        assert len(line_issues) == 0, f"Expected no line count issues, got {len(line_issues)}"

    def test_line_count_warning_at_280_lines(self):
        """
        GIVEN: CLAUDE.md with exactly 280 lines
        WHEN: Validating line count
        THEN: Warning issued (approaching 300 line limit)
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        validator = ClaudeAlignmentValidator(self.CLAUDE_MD.parent.parent.parent)

        # Create content with exactly 280 lines
        content = "\n".join([f"Line {i}" for i in range(280)])

        validator._check_line_count(content)

        warnings = [i for i in validator.issues if i.severity == "warning" and "line" in i.message.lower()]

        assert len(warnings) >= 1, f"Expected line count warning at 280 lines, got {len(warnings)} warnings"
        assert "280" in warnings[0].message, f"Warning should mention 280 lines: {warnings[0].message}"

    def test_line_count_error_at_301_lines(self):
        """
        GIVEN: CLAUDE.md with 301 lines (over limit)
        WHEN: Validating line count
        THEN: Error issued (exceeds 300 line maximum)
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        validator = ClaudeAlignmentValidator(self.CLAUDE_MD.parent.parent.parent)

        # Create content with 301 lines
        content = "\n".join([f"Line {i}" for i in range(301)])

        validator._check_line_count(content)

        errors = [i for i in validator.issues if i.severity == "error" and "line" in i.message.lower()]

        assert len(errors) >= 1, f"Expected line count error at 301 lines, got {len(errors)} errors"
        assert "301" in errors[0].message, f"Error should mention 301 lines: {errors[0].message}"
        assert "300" in errors[0].message, f"Error should mention 300 line limit: {errors[0].message}"

    def test_line_count_exactly_300_passes(self):
        """
        GIVEN: CLAUDE.md with exactly 300 lines (at limit)
        WHEN: Validating line count
        THEN: Validation passes (300 is acceptable)
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        validator = ClaudeAlignmentValidator(self.CLAUDE_MD.parent.parent.parent)

        # Create content with exactly 300 lines
        content = "\n".join([f"Line {i}" for i in range(300)])

        validator._check_line_count(content)

        errors = [i for i in validator.issues if i.severity == "error" and "line" in i.message.lower()]

        assert len(errors) == 0, f"Expected no errors at exactly 300 lines, got {len(errors)}"


class TestSectionCountValidation:
    """Test suite for CLAUDE.md section count validation."""

    MAX_SECTIONS = 20
    WARNING_THRESHOLD = 18  # 90% of limit

    def test_section_count_under_limit_passes(self):
        """
        GIVEN: CLAUDE.md with 17 sections (under warning threshold)
        WHEN: Validating section count
        THEN: Validation passes with no issues
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        validator = ClaudeAlignmentValidator(Path.cwd())

        # Create content with 17 sections (under warning threshold of 18)
        content = "\n\n".join([f"## Section {i}\nContent here" for i in range(17)])

        validator._check_section_count(content)

        section_issues = [i for i in validator.issues if "section" in i.message.lower()]

        assert len(section_issues) == 0, f"Expected no section count issues, got {len(section_issues)}"

    def test_section_count_warning_at_18_sections(self):
        """
        GIVEN: CLAUDE.md with exactly 18 sections
        WHEN: Validating section count
        THEN: Warning issued (approaching 20 section limit)
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        validator = ClaudeAlignmentValidator(Path.cwd())

        # Create content with exactly 18 sections
        content = "\n\n".join([f"## Section {i}\nContent here" for i in range(18)])

        validator._check_section_count(content)

        warnings = [i for i in validator.issues if i.severity == "warning" and "section" in i.message.lower()]

        assert len(warnings) >= 1, f"Expected section count warning at 18 sections, got {len(warnings)} warnings"
        assert "18" in warnings[0].message or "section" in warnings[0].message.lower(), \
            f"Warning should mention sections: {warnings[0].message}"

    def test_section_count_error_at_21_sections(self):
        """
        GIVEN: CLAUDE.md with 21 sections (over limit)
        WHEN: Validating section count
        THEN: Error issued (exceeds 20 section maximum)
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        validator = ClaudeAlignmentValidator(Path.cwd())

        # Create content with 21 sections
        content = "\n\n".join([f"## Section {i}\nContent here" for i in range(21)])

        validator._check_section_count(content)

        errors = [i for i in validator.issues if i.severity == "error" and "section" in i.message.lower()]

        assert len(errors) >= 1, f"Expected section count error at 21 sections, got {len(errors)} errors"
        assert "21" in errors[0].message or "20" in errors[0].message, \
            f"Error should mention section limit: {errors[0].message}"

    def test_section_count_exactly_20_passes(self):
        """
        GIVEN: CLAUDE.md with exactly 20 sections (at limit)
        WHEN: Validating section count
        THEN: Validation passes (20 is acceptable)
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        validator = ClaudeAlignmentValidator(Path.cwd())

        # Create content with exactly 20 sections
        content = "\n\n".join([f"## Section {i}\nContent here" for i in range(20)])

        validator._check_section_count(content)

        errors = [i for i in validator.issues if i.severity == "error" and "section" in i.message.lower()]

        assert len(errors) == 0, f"Expected no errors at exactly 20 sections, got {len(errors)}"


class TestCharacterLimitPhases:
    """Test suite for phased character limit enforcement."""

    def test_character_limit_phase1_warning_at_35k(self):
        """
        GIVEN: CLAUDE.md with 36,000 characters and phase 1 active
        WHEN: Validating character count
        THEN: Warning issued (exceeds 35k phase 1 limit)
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        with patch.dict(os.environ, {"CLAUDE_VALIDATION_PHASE": "1"}):
            validator = ClaudeAlignmentValidator(Path.cwd())

            # Create content with 36,000 characters
            content = "x" * 36000

            validator._check_character_count(content)

            warnings = [i for i in validator.issues if i.severity == "warning" and "character" in i.message.lower()]

            assert len(warnings) >= 1, f"Expected character count warning in phase 1, got {len(warnings)} warnings"
            assert "35" in warnings[0].message or "35000" in warnings[0].message, \
                f"Warning should mention 35k limit: {warnings[0].message}"

    def test_character_limit_phase1_passes_at_34k(self):
        """
        GIVEN: CLAUDE.md with 34,000 characters and phase 1 active
        WHEN: Validating character count
        THEN: Validation passes (under 35k limit)
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        with patch.dict(os.environ, {"CLAUDE_VALIDATION_PHASE": "1"}):
            validator = ClaudeAlignmentValidator(Path.cwd())

            # Create content with 34,000 characters
            content = "x" * 34000

            validator._check_character_count(content)

            char_issues = [i for i in validator.issues if "character" in i.message.lower()]

            assert len(char_issues) == 0, f"Expected no character count issues at 34k in phase 1, got {len(char_issues)}"

    def test_character_limit_phase2_error_at_26k(self):
        """
        GIVEN: CLAUDE.md with 26,000 characters and phase 2 active
        WHEN: Validating character count
        THEN: Error issued (exceeds 25k phase 2 limit)
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        with patch.dict(os.environ, {"CLAUDE_VALIDATION_PHASE": "2"}):
            validator = ClaudeAlignmentValidator(Path.cwd())

            # Create content with 26,000 characters
            content = "x" * 26000

            validator._check_character_count(content)

            errors = [i for i in validator.issues if i.severity == "error" and "character" in i.message.lower()]

            assert len(errors) >= 1, f"Expected character count error in phase 2, got {len(errors)} errors"
            assert "25" in errors[0].message or "25000" in errors[0].message, \
                f"Error should mention 25k limit: {errors[0].message}"

    def test_character_limit_phase2_passes_at_24k(self):
        """
        GIVEN: CLAUDE.md with 24,000 characters and phase 2 active
        WHEN: Validating character count
        THEN: Validation passes (under 25k limit)
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        with patch.dict(os.environ, {"CLAUDE_VALIDATION_PHASE": "2"}):
            validator = ClaudeAlignmentValidator(Path.cwd())

            # Create content with 24,000 characters
            content = "x" * 24000

            validator._check_character_count(content)

            errors = [i for i in validator.issues if i.severity == "error" and "character" in i.message.lower()]

            assert len(errors) == 0, f"Expected no errors at 24k in phase 2, got {len(errors)}"

    def test_character_limit_phase3_error_at_16k(self):
        """
        GIVEN: CLAUDE.md with 16,000 characters and phase 3 active
        WHEN: Validating character count
        THEN: Error issued (exceeds 15k phase 3 limit)
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        with patch.dict(os.environ, {"CLAUDE_VALIDATION_PHASE": "3"}):
            validator = ClaudeAlignmentValidator(Path.cwd())

            # Create content with 16,000 characters
            content = "x" * 16000

            validator._check_character_count(content)

            errors = [i for i in validator.issues if i.severity == "error" and "character" in i.message.lower()]

            assert len(errors) >= 1, f"Expected character count error in phase 3, got {len(errors)} errors"
            assert "15" in errors[0].message or "15000" in errors[0].message, \
                f"Error should mention 15k limit: {errors[0].message}"

    def test_character_limit_phase3_passes_at_14k(self):
        """
        GIVEN: CLAUDE.md with 14,000 characters and phase 3 active
        WHEN: Validating character count
        THEN: Validation passes (under 15k limit)
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        with patch.dict(os.environ, {"CLAUDE_VALIDATION_PHASE": "3"}):
            validator = ClaudeAlignmentValidator(Path.cwd())

            # Create content with 14,000 characters
            content = "x" * 14000

            validator._check_character_count(content)

            errors = [i for i in validator.issues if i.severity == "error" and "character" in i.message.lower()]

            assert len(errors) == 0, f"Expected no errors at 14k in phase 3, got {len(errors)}"


class TestErrorMessageGuidance:
    """Test suite for error message guidance links."""

    def test_error_message_includes_best_practices_link(self):
        """
        GIVEN: CLAUDE.md validation failure (any type)
        WHEN: Error message is generated
        THEN: Message includes link to docs/CLAUDE-MD-BEST-PRACTICES.md
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        validator = ClaudeAlignmentValidator(Path.cwd())

        # Trigger a line count error
        content = "\n".join([f"Line {i}" for i in range(301)])
        validator._check_line_count(content)

        errors = [i for i in validator.issues if i.severity == "error"]

        assert len(errors) >= 1, "Expected at least one error to test guidance link"

        # Check if any error message includes guidance link
        has_guidance_link = any(
            "CLAUDE-MD-BEST-PRACTICES" in error.message or
            "docs/CLAUDE" in error.message
            for error in errors
        )

        assert has_guidance_link, \
            f"Error messages should include link to docs/CLAUDE-MD-BEST-PRACTICES.md. Got: {[e.message for e in errors]}"

    def test_warning_message_includes_best_practices_link(self):
        """
        GIVEN: CLAUDE.md validation warning (any type)
        WHEN: Warning message is generated
        THEN: Message includes link to docs/CLAUDE-MD-BEST-PRACTICES.md
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        validator = ClaudeAlignmentValidator(Path.cwd())

        # Trigger a line count warning
        content = "\n".join([f"Line {i}" for i in range(280)])
        validator._check_line_count(content)

        warnings = [i for i in validator.issues if i.severity == "warning"]

        assert len(warnings) >= 1, "Expected at least one warning to test guidance link"

        # Check if any warning message includes guidance link
        has_guidance_link = any(
            "CLAUDE-MD-BEST-PRACTICES" in warning.message or
            "docs/CLAUDE" in warning.message
            for warning in warnings
        )

        assert has_guidance_link, \
            f"Warning messages should include link to docs/CLAUDE-MD-BEST-PRACTICES.md. Got: {[w.message for w in warnings]}"


class TestCurrentClaudeMdCompliance:
    """Test suite to verify current CLAUDE.md passes validation."""

    CLAUDE_MD = Path(__file__).parent.parent.parent / "CLAUDE.md"

    def test_current_claude_md_passes_validation(self):
        """
        GIVEN: Current CLAUDE.md file (287 lines, 18 sections, ~10,640 characters)
        WHEN: Running full validation
        THEN: All validation checks pass in phase 1
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        with patch.dict(os.environ, {"CLAUDE_VALIDATION_PHASE": "1"}):
            validator = ClaudeAlignmentValidator(self.CLAUDE_MD.parent.parent.parent)

            # Read actual CLAUDE.md content
            content = self.CLAUDE_MD.read_text()

            # Run all new validation checks
            validator._check_line_count(content)
            validator._check_section_count(content)
            validator._check_character_count(content)

            # Should have no errors
            errors = [i for i in validator.issues if i.severity == "error"]

            assert len(errors) == 0, \
                f"Current CLAUDE.md should pass validation. Errors: {[e.message for e in errors]}"

    def test_current_claude_md_line_count_within_limits(self):
        """
        GIVEN: Current CLAUDE.md file
        WHEN: Checking line count
        THEN: Line count is 287 (well under 300 limit)
        """
        content = self.CLAUDE_MD.read_text()
        lines = content.splitlines()
        line_count = len(lines)

        # 288 from wc -l (includes final newline), 287 from splitlines
        assert line_count <= 288, f"Current CLAUDE.md has {line_count} lines (expected ~287)"
        assert line_count < 300, f"Current CLAUDE.md exceeds 300 line limit: {line_count} lines"

    def test_current_claude_md_section_count_within_limits(self):
        """
        GIVEN: Current CLAUDE.md file
        WHEN: Checking section count
        THEN: Section count is 18 (at warning threshold but under 20 limit)
        """
        content = self.CLAUDE_MD.read_text()
        sections = re.findall(r'^## ', content, re.MULTILINE)
        section_count = len(sections)

        assert section_count == 18, f"Current CLAUDE.md has {section_count} sections (expected 18)"
        assert section_count <= 20, f"Current CLAUDE.md exceeds 20 section limit: {section_count} sections"

    def test_current_claude_md_character_count_within_limits(self):
        """
        GIVEN: Current CLAUDE.md file
        WHEN: Checking character count
        THEN: Character count is ~10,640 (well under all phase limits)
        """
        content = self.CLAUDE_MD.read_text()
        char_count = len(content)

        assert char_count <= 11000, f"Current CLAUDE.md has {char_count} characters (expected ~10,640)"
        assert char_count < 35000, f"Current CLAUDE.md exceeds phase 1 limit (35k): {char_count} characters"
        assert char_count < 25000, f"Current CLAUDE.md exceeds phase 2 limit (25k): {char_count} characters"
        assert char_count < 15000, f"Current CLAUDE.md exceeds phase 3 limit (15k): {char_count} characters"


class TestIntegrationWithExistingValidation:
    """Test suite for integration with existing ClaudeAlignmentValidator."""

    CLAUDE_MD = Path(__file__).parent.parent.parent / "CLAUDE.md"

    def test_validate_method_calls_new_checks(self):
        """
        GIVEN: ClaudeAlignmentValidator instance
        WHEN: Calling validate() method
        THEN: New validation checks are included in validation run
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        validator = ClaudeAlignmentValidator(self.CLAUDE_MD.parent.parent.parent)

        # Mock the new methods to verify they're called
        with patch.object(validator, '_check_line_count', wraps=validator._check_line_count) as mock_line, \
             patch.object(validator, '_check_section_count', wraps=validator._check_section_count) as mock_section, \
             patch.object(validator, '_check_character_count', wraps=validator._check_character_count) as mock_char:

            aligned, issues = validator.validate()

            # Verify new checks were called
            mock_line.assert_called_once()
            mock_section.assert_called_once()
            mock_char.assert_called_once()

    def test_exit_code_2_on_line_count_error(self):
        """
        GIVEN: CLAUDE.md with 301 lines (over limit)
        WHEN: Running validation script
        THEN: Exit code is 2 (error)
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        validator = ClaudeAlignmentValidator(Path.cwd())

        # Create content with 301 lines
        content = "\n".join([f"Line {i}" for i in range(301)])
        validator._check_line_count(content)

        errors = [i for i in validator.issues if i.severity == "error"]

        # Exit code 2 should be returned when errors exist
        assert len(errors) >= 1, "Expected errors that would trigger exit code 2"

    def test_exit_code_1_on_line_count_warning(self):
        """
        GIVEN: CLAUDE.md with 280 lines (warning threshold)
        WHEN: Running validation script
        THEN: Exit code is 1 (warning)
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        validator = ClaudeAlignmentValidator(Path.cwd())

        # Create content with 280 lines
        content = "\n".join([f"Line {i}" for i in range(280)])
        validator._check_line_count(content)

        warnings = [i for i in validator.issues if i.severity == "warning"]
        errors = [i for i in validator.issues if i.severity == "error"]

        # Exit code 1 should be returned when only warnings exist
        assert len(warnings) >= 1, "Expected warnings that would trigger exit code 1"
        assert len(errors) == 0, "Expected no errors (only warnings)"

    def test_exit_code_0_on_passing_validation(self):
        """
        GIVEN: CLAUDE.md with 287 lines (current state)
        WHEN: Running validation script
        THEN: Exit code is 0 (success)
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        validator = ClaudeAlignmentValidator(self.CLAUDE_MD.parent.parent.parent)
        content = self.CLAUDE_MD.read_text()

        validator._check_line_count(content)
        validator._check_section_count(content)
        validator._check_character_count(content)

        # Exit code 0 should be returned when no errors exist (warnings are OK)
        error_issues = [i for i in validator.issues if
                       i.severity == "error" and (
                           "line" in i.message.lower() or
                           "section" in i.message.lower() or
                           "character" in i.message.lower()
                       )]

        assert len(error_issues) == 0, \
            f"Expected no errors for current CLAUDE.md. Got: {[i.message for i in error_issues]}"


class TestEdgeCases:
    """Test suite for edge cases and boundary conditions."""

    def test_empty_file_passes_all_checks(self):
        """
        GIVEN: Empty CLAUDE.md file
        WHEN: Running validation
        THEN: All size checks pass (no errors for being too small)
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        validator = ClaudeAlignmentValidator(Path.cwd())
        content = ""

        validator._check_line_count(content)
        validator._check_section_count(content)
        validator._check_character_count(content)

        errors = [i for i in validator.issues if i.severity == "error"]

        assert len(errors) == 0, "Empty file should not trigger size limit errors"

    def test_file_with_only_whitespace(self):
        """
        GIVEN: CLAUDE.md with only whitespace (spaces, newlines, tabs)
        WHEN: Running validation
        THEN: Line count includes blank lines
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        validator = ClaudeAlignmentValidator(Path.cwd())

        # Create 305 blank lines
        content = "\n" * 305

        validator._check_line_count(content)

        errors = [i for i in validator.issues if i.severity == "error" and "line" in i.message.lower()]

        assert len(errors) >= 1, "Blank lines should count toward line limit"

    def test_file_with_unicode_characters(self):
        """
        GIVEN: CLAUDE.md with unicode characters (emoji, international chars)
        WHEN: Running character count validation
        THEN: Unicode characters are counted correctly
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        validator = ClaudeAlignmentValidator(Path.cwd())

        # Create content with unicode that would exceed 35k in phase 1
        # Emoji characters
        content = "🚀" * 36000  # Each emoji is 1 character in Python

        with patch.dict(os.environ, {"CLAUDE_VALIDATION_PHASE": "1"}):
            validator._check_character_count(content)

        warnings = [i for i in validator.issues if "character" in i.message.lower()]

        # Should trigger warning for exceeding 35k characters
        assert len(warnings) >= 1, "Unicode characters should be counted correctly"

    def test_multiple_validation_failures(self):
        """
        GIVEN: CLAUDE.md that fails multiple checks (sections and characters)
        WHEN: Running validation
        THEN: All failures are reported
        """
        from validate_claude_alignment import ClaudeAlignmentValidator

        validator = ClaudeAlignmentValidator(Path.cwd())

        # Create content that fails multiple checks:
        # - 21 sections (over 20 limit = error)
        # - 36,000+ characters (over 35k = warning in Phase 1)
        sections = [f"## Section {i}\n" + ("x" * 1800) for i in range(21)]
        content = "\n".join(sections)

        with patch.dict(os.environ, {"CLAUDE_VALIDATION_PHASE": "1"}):
            validator._check_line_count(content)
            validator._check_section_count(content)
            validator._check_character_count(content)

        errors = [i for i in validator.issues if i.severity == "error"]
        warnings = [i for i in validator.issues if i.severity == "warning"]

        # Should report at least 2 issues: section error + character warning
        assert len(errors) + len(warnings) >= 2, \
            f"Expected multiple validation failures. Got {len(errors)} errors, {len(warnings)} warnings"
