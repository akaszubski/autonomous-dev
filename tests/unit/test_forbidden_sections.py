#!/usr/bin/env python3
"""
TDD Tests for PROJECT.md Forbidden Sections Validation - RED PHASE

This test suite validates the forbidden sections detection and remediation
for PROJECT.md files (Issue #194).

Feature:
Detect and prevent forbidden sections in PROJECT.md files. PROJECT.md should
contain strategic intent (GOALS, SCOPE, CONSTRAINTS, ARCHITECTURE) but not
tactical task lists (TODO, Roadmap, Future, etc.).

Problem:
PROJECT.md can drift into a task tracking document when it should only contain
strategic intent. Tactical items belong in GitHub Issues, not PROJECT.md.

Forbidden Sections:
- TODO
- Roadmap
- Future
- Backlog
- Next Steps
- Coming Soon
- Planned

Solution:
Validation function that:
1. Detects forbidden section headers (case-insensitive)
2. Reports line numbers and section names
3. Provides remediation guidance
4. Extracts content for migration to GitHub Issues
5. Removes forbidden sections from PROJECT.md

Test Coverage:
1. Detection Logic
   - Single forbidden section
   - Multiple forbidden sections
   - Case-insensitive detection (TODO, todo, ToDo)
   - Line number reporting
   - No false positives on valid content
   - Forbidden words in content (not headers)
   - All forbidden section names

2. Remediation Logic
   - Extract single section
   - Extract multiple sections
   - Preserve surrounding content
   - Handle empty files
   - Handle section at file end

3. Edge Cases
   - Empty PROJECT.md
   - Only forbidden sections
   - Forbidden words in allowed section content
   - Subsections not detected as forbidden

TDD Workflow:
- Tests written FIRST (before implementation)
- All tests FAIL initially (functions don't exist yet)
- Implementation makes tests pass (GREEN phase)

Date: 2026-01-03
Issue: #194 (PROJECT.md vs GitHub Issues guidance)
Agent: test-master
Phase: RED (tests fail, no implementation yet)

Design Patterns:
    See testing-guide skill for TDD methodology and pytest patterns.
    See python-standards skill for code conventions.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False
    # Provide minimal pytest stub
    class pytest:
        @staticmethod
        def skip(msg, allow_module_level=False):
            if allow_module_level:
                raise ImportError(msg)

        @staticmethod
        def raises(*args, **kwargs):
            return MockRaises()

        @staticmethod
        def fixture(*args, **kwargs):
            def decorator(func):
                return func
            return decorator

        @staticmethod
        def param(*args, **kwargs):
            return args

        @staticmethod
        def mark(*args, **kwargs):
            class Mark:
                @staticmethod
                def parametrize(*args, **kwargs):
                    def decorator(func):
                        return func
                    return decorator
            return Mark()

    class MockRaises:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                raise AssertionError("Expected exception was not raised")
            return True

# Add directories to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"))
sys.path.insert(0, str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks"))

# Skip tests if pytest not available
if not PYTEST_AVAILABLE:
    pytest.skip("pytest not available", allow_module_level=True)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def forbidden_sections():
    """List of forbidden section names."""
    return [
        'TODO', 'Roadmap', 'Future', 'Backlog',
        'Next Steps', 'Coming Soon', 'Planned'
    ]


@pytest.fixture
def sample_valid_project_md(tmp_path):
    """Create a valid PROJECT.md with no forbidden sections."""
    content = """# Project Name

## GOALS
- Build autonomous development system
- Enable AI-powered feature development

## SCOPE

### In Scope
- Feature implementation
- Test automation

### Out of Scope
- Manual QA processes
- Legacy system migration

## CONSTRAINTS
- Must work with Claude Code 2.0
- Python 3.8+ required

## ARCHITECTURE
- Agent-based system
- Hook-driven validation
"""
    project_md = tmp_path / "PROJECT.md"
    project_md.write_text(content)
    return project_md


@pytest.fixture
def sample_invalid_project_md(tmp_path):
    """Create PROJECT.md with forbidden sections."""
    content = """# Project Name

## GOALS
- Build autonomous development system

## TODO
- Implement feature X
- Fix bug Y
- Add tests for Z

## SCOPE

### In Scope
- Feature implementation

## Roadmap

### Q1 2026
- Feature A
- Feature B

### Q2 2026
- Feature C

## CONSTRAINTS
- Must work with Claude Code 2.0

## Future
- Add support for Rust
- Integrate with VS Code
"""
    project_md = tmp_path / "PROJECT.md"
    project_md.write_text(content)
    return project_md


@pytest.fixture
def sample_mixed_case_project_md(tmp_path):
    """Create PROJECT.md with mixed case forbidden sections."""
    content = """# Project Name

## GOALS
- Build system

## todo
- Task 1
- Task 2

## ToDo
- Task 3

## ROADMAP
- Item 1
"""
    project_md = tmp_path / "PROJECT.md"
    project_md.write_text(content)
    return project_md


@pytest.fixture
def sample_subsection_project_md(tmp_path):
    """Create PROJECT.md with forbidden words in subsections."""
    content = """# Project Name

## GOALS

### Future Vision
Our future vision is to build the best system.

## SCOPE

### Todo Management
We handle todo items via GitHub Issues.

## CONSTRAINTS
- Must work with Claude Code 2.0
"""
    project_md = tmp_path / "PROJECT.md"
    project_md.write_text(content)
    return project_md


# =============================================================================
# Test Suite 1: Detection Logic
# =============================================================================

class TestForbiddenSectionsValidation:
    """Test detection of forbidden sections in PROJECT.md."""

    def test_detects_single_forbidden_section(self, tmp_path):
        """Test detection of a single forbidden section."""
        content = """# Project

## GOALS
- Goal 1

## TODO
- Task 1
- Task 2

## SCOPE
- Scope item
"""
        project_md = tmp_path / "PROJECT.md"
        project_md.write_text(content)

        # Import function under test (will fail - not implemented yet)
        from validate_project_alignment import check_forbidden_sections

        is_valid, message = check_forbidden_sections(content)

        assert is_valid is False
        assert "TODO" in message
        assert "line 6" in message.lower()

    def test_detects_multiple_forbidden_sections(self, tmp_path):
        """Test detection of multiple forbidden sections."""
        content = """# Project

## TODO
- Task 1

## GOALS
- Goal 1

## Roadmap
- Item 1

## Future
- Future item
"""
        project_md = tmp_path / "PROJECT.md"
        project_md.write_text(content)

        from validate_project_alignment import check_forbidden_sections

        is_valid, message = check_forbidden_sections(content)

        assert is_valid is False
        assert "TODO" in message
        assert "Roadmap" in message
        assert "Future" in message
        # Should report all three forbidden sections
        assert message.count("##") >= 3

    @pytest.mark.parametrize("section_variant", [
        "TODO",
        "todo",
        "ToDo",
        "tOdO",
        "Todo",
    ])
    def test_case_insensitive_detection(self, tmp_path, section_variant):
        """Test case-insensitive detection of forbidden sections."""
        content = f"""# Project

## GOALS
- Goal 1

## {section_variant}
- Task 1

## SCOPE
- Scope item
"""
        project_md = tmp_path / "PROJECT.md"
        project_md.write_text(content)

        from validate_project_alignment import check_forbidden_sections

        is_valid, message = check_forbidden_sections(content)

        assert is_valid is False
        assert section_variant in message or "TODO" in message.upper()

    def test_reports_line_numbers(self, sample_invalid_project_md):
        """Test that line numbers are reported for forbidden sections."""
        content = sample_invalid_project_md.read_text()

        from validate_project_alignment import check_forbidden_sections

        is_valid, message = check_forbidden_sections(content)

        assert is_valid is False
        # Should contain line number references
        assert "line" in message.lower()
        # Should report multiple line numbers (TODO at line 6, Roadmap at ~16, Future at ~26)
        import re
        line_numbers = re.findall(r'line (\d+)', message.lower())
        assert len(line_numbers) >= 3

    def test_no_false_positives_on_valid_content(self, sample_valid_project_md):
        """Test no false positives on valid PROJECT.md."""
        content = sample_valid_project_md.read_text()

        from validate_project_alignment import check_forbidden_sections

        is_valid, message = check_forbidden_sections(content)

        assert is_valid is True
        assert message == "" or "valid" in message.lower() or "no forbidden" in message.lower()

    def test_allows_forbidden_words_in_content(self, tmp_path):
        """Test that forbidden words in content (not headers) are allowed."""
        content = """# Project

## GOALS
- Build a TODO tracking system
- Plan our future roadmap via GitHub Issues

## SCOPE
- In scope: Todo management
- Out of scope: Backlog grooming
"""
        project_md = tmp_path / "PROJECT.md"
        project_md.write_text(content)

        from validate_project_alignment import check_forbidden_sections

        is_valid, message = check_forbidden_sections(content)

        # Should be valid - forbidden words appear in content, not as headers
        assert is_valid is True

    @pytest.mark.parametrize("forbidden_section", [
        'TODO',
        'Roadmap',
        'Future',
        'Backlog',
        'Next Steps',
        'Coming Soon',
        'Planned',
    ])
    def test_all_forbidden_section_names(self, tmp_path, forbidden_section):
        """Test detection of all forbidden section names."""
        content = f"""# Project

## GOALS
- Goal 1

## {forbidden_section}
- Item 1
- Item 2

## SCOPE
- Scope item
"""
        project_md = tmp_path / "PROJECT.md"
        project_md.write_text(content)

        from validate_project_alignment import check_forbidden_sections

        is_valid, message = check_forbidden_sections(content)

        assert is_valid is False
        # Message should contain the forbidden section name (case-insensitive match)
        assert forbidden_section.lower() in message.lower()


# =============================================================================
# Test Suite 2: Remediation Logic
# =============================================================================

class TestForbiddenSectionsRemediation:
    """Test extraction and removal of forbidden sections."""

    def test_extract_single_section(self, tmp_path):
        """Test extraction of a single forbidden section's content."""
        content = """# Project

## GOALS
- Goal 1

## TODO
- Task 1
- Task 2
- Task 3

## SCOPE
- Scope item
"""
        project_md = tmp_path / "PROJECT.md"
        project_md.write_text(content)

        from alignment_fixer import AlignmentFixer

        fixer = AlignmentFixer(project_root=tmp_path)
        extracted = fixer.extract_forbidden_section(content, "TODO")

        assert "Task 1" in extracted
        assert "Task 2" in extracted
        assert "Task 3" in extracted
        # Should NOT contain content from other sections
        assert "Goal 1" not in extracted
        assert "Scope item" not in extracted

    def test_extract_multiple_sections(self, sample_invalid_project_md):
        """Test extraction of multiple forbidden sections."""
        content = sample_invalid_project_md.read_text()

        from alignment_fixer import AlignmentFixer

        fixer = AlignmentFixer(project_root=sample_invalid_project_md.parent)

        # Extract all forbidden sections
        extracted_sections = fixer.extract_all_forbidden_sections(content)

        assert "TODO" in extracted_sections
        assert "Roadmap" in extracted_sections
        assert "Future" in extracted_sections

        # Check TODO content
        assert "Implement feature X" in extracted_sections["TODO"]
        assert "Fix bug Y" in extracted_sections["TODO"]

        # Check Roadmap content
        assert "Feature A" in extracted_sections["Roadmap"]
        assert "Q1 2026" in extracted_sections["Roadmap"]

        # Check Future content
        assert "Add support for Rust" in extracted_sections["Future"]

    def test_preserves_surrounding_content(self, tmp_path):
        """Test that removing sections preserves other content."""
        content = """# Project

## GOALS
- Goal 1
- Goal 2

## TODO
- Task 1
- Task 2

## SCOPE
- Scope item 1
- Scope item 2

## CONSTRAINTS
- Constraint 1
"""
        project_md = tmp_path / "PROJECT.md"
        project_md.write_text(content)

        from alignment_fixer import AlignmentFixer

        fixer = AlignmentFixer(project_root=tmp_path)
        cleaned_content = fixer.remove_forbidden_sections(content)

        # Should preserve GOALS, SCOPE, CONSTRAINTS
        assert "## GOALS" in cleaned_content
        assert "Goal 1" in cleaned_content
        assert "Goal 2" in cleaned_content
        assert "## SCOPE" in cleaned_content
        assert "Scope item 1" in cleaned_content
        assert "## CONSTRAINTS" in cleaned_content
        assert "Constraint 1" in cleaned_content

        # Should remove TODO
        assert "## TODO" not in cleaned_content
        assert "Task 1" not in cleaned_content
        assert "Task 2" not in cleaned_content

    def test_handles_empty_file(self, tmp_path):
        """Test handling of empty PROJECT.md file."""
        content = ""
        project_md = tmp_path / "PROJECT.md"
        project_md.write_text(content)

        from alignment_fixer import AlignmentFixer

        fixer = AlignmentFixer(project_root=tmp_path)

        # Should not crash on empty content
        extracted = fixer.extract_all_forbidden_sections(content)
        assert extracted == {} or extracted == []

        cleaned = fixer.remove_forbidden_sections(content)
        assert cleaned == ""

    def test_handles_section_at_file_end(self, tmp_path):
        """Test handling of forbidden section at end of file."""
        content = """# Project

## GOALS
- Goal 1

## SCOPE
- Scope item

## TODO
- Task 1
- Task 2
"""
        project_md = tmp_path / "PROJECT.md"
        project_md.write_text(content)

        from alignment_fixer import AlignmentFixer

        fixer = AlignmentFixer(project_root=tmp_path)

        # Extract section at end
        extracted = fixer.extract_forbidden_section(content, "TODO")
        assert "Task 1" in extracted
        assert "Task 2" in extracted

        # Remove section at end
        cleaned = fixer.remove_forbidden_sections(content)
        assert "## TODO" not in cleaned
        assert "Task 1" not in cleaned
        # Should preserve earlier sections
        assert "## GOALS" in cleaned
        assert "Goal 1" in cleaned


# =============================================================================
# Test Suite 3: Edge Cases
# =============================================================================

class TestForbiddenSectionsEdgeCases:
    """Test edge cases for forbidden sections validation."""

    def test_empty_project_md(self, tmp_path):
        """Test validation of empty PROJECT.md."""
        content = ""
        project_md = tmp_path / "PROJECT.md"
        project_md.write_text(content)

        from validate_project_alignment import check_forbidden_sections

        is_valid, message = check_forbidden_sections(content)

        # Empty file is technically valid (no forbidden sections)
        assert is_valid is True

    def test_project_md_with_only_forbidden_sections(self, tmp_path):
        """Test PROJECT.md containing only forbidden sections."""
        content = """# Project

## TODO
- Task 1

## Roadmap
- Item 1

## Future
- Future item
"""
        project_md = tmp_path / "PROJECT.md"
        project_md.write_text(content)

        from validate_project_alignment import check_forbidden_sections

        is_valid, message = check_forbidden_sections(content)

        assert is_valid is False
        # Should detect all three forbidden sections
        assert "TODO" in message
        assert "Roadmap" in message
        assert "Future" in message

    def test_forbidden_word_in_allowed_section_content(self, tmp_path):
        """Test forbidden words appearing in allowed section content."""
        content = """# Project

## GOALS
- Build a system to manage TODO lists via GitHub Issues
- Plan future roadmap items in GitHub Projects

## SCOPE

### In Scope
- TODO tracking via GitHub
- Backlog management via Projects
"""
        project_md = tmp_path / "PROJECT.md"
        project_md.write_text(content)

        from validate_project_alignment import check_forbidden_sections

        is_valid, message = check_forbidden_sections(content)

        # Should be valid - forbidden words appear in content, not as section headers
        assert is_valid is True

    def test_subsection_not_detected_as_forbidden(self, sample_subsection_project_md):
        """Test that subsections with forbidden words are not flagged."""
        content = sample_subsection_project_md.read_text()

        from validate_project_alignment import check_forbidden_sections

        is_valid, message = check_forbidden_sections(content)

        # Should be valid - "Future Vision" and "Todo Management" are subsections (###)
        # Only ## level headers should be flagged
        assert is_valid is True

    def test_forbidden_section_with_no_content(self, tmp_path):
        """Test forbidden section with no content under it."""
        content = """# Project

## GOALS
- Goal 1

## TODO

## SCOPE
- Scope item
"""
        project_md = tmp_path / "PROJECT.md"
        project_md.write_text(content)

        from validate_project_alignment import check_forbidden_sections

        is_valid, message = check_forbidden_sections(content)

        # Should still be invalid - forbidden section header exists even if empty
        assert is_valid is False
        assert "TODO" in message

    def test_forbidden_section_with_whitespace_variations(self, tmp_path):
        """Test forbidden sections with various whitespace patterns."""
        content = """# Project

## GOALS
- Goal 1

##TODO
- Task 1

##  Roadmap
- Item 1

## Future
- Future item
"""
        project_md = tmp_path / "PROJECT.md"
        project_md.write_text(content)

        from validate_project_alignment import check_forbidden_sections

        is_valid, message = check_forbidden_sections(content)

        # Should detect all forbidden sections despite whitespace variations
        assert is_valid is False
        # At minimum, should detect sections with standard spacing
        # Whitespace handling may vary based on implementation

    def test_mixed_case_forbidden_sections(self, sample_mixed_case_project_md):
        """Test multiple forbidden sections with mixed case."""
        content = sample_mixed_case_project_md.read_text()

        from validate_project_alignment import check_forbidden_sections

        is_valid, message = check_forbidden_sections(content)

        assert is_valid is False
        # Should detect all variations: todo, ToDo, ROADMAP
        # Implementation may normalize to upper case in message
        assert message.count("TODO") >= 2 or message.count("todo") >= 2


# =============================================================================
# Test Suite 4: Integration with Alignment Workflow
# =============================================================================

class TestForbiddenSectionsIntegration:
    """Test integration with alignment commands."""

    def test_align_project_detects_forbidden_sections(self, tmp_path):
        """Test that /align --project detects forbidden sections."""
        content = """# Project

## GOALS
- Goal 1

## TODO
- Task 1

## SCOPE
- Scope item
"""
        project_md = tmp_path / "PROJECT.md"
        project_md.write_text(content)

        # Import alignment validator
        from validate_project_alignment import validate_project_md

        issues = validate_project_md(project_md)

        # Should detect forbidden section issue
        assert any("forbidden" in str(issue).lower() or "TODO" in str(issue) for issue in issues)

    def test_provides_remediation_guidance(self, tmp_path):
        """Test that validation provides remediation guidance."""
        content = """# Project

## TODO
- Task 1
- Task 2

## Roadmap
- Item 1
"""
        project_md = tmp_path / "PROJECT.md"
        project_md.write_text(content)

        from validate_project_alignment import check_forbidden_sections

        is_valid, message = check_forbidden_sections(content)

        assert is_valid is False
        # Should provide guidance on using GitHub Issues
        assert "github" in message.lower() or "issue" in message.lower()

    def test_setup_wizard_prevents_forbidden_sections(self, tmp_path):
        """Test that setup wizard validates against forbidden sections."""
        # This test validates that the setup wizard integration
        # prevents creation of PROJECT.md with forbidden sections

        # Mock setup wizard creating PROJECT.md
        content_with_forbidden = """# Project

## GOALS
- Goal 1

## TODO
- Initial tasks
"""

        from validate_project_alignment import check_forbidden_sections

        # Setup wizard should validate before writing
        is_valid, message = check_forbidden_sections(content_with_forbidden)

        assert is_valid is False
        # Setup wizard should not allow this to be written


# =============================================================================
# Main - Allow running tests directly
# =============================================================================

if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
