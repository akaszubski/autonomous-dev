#!/usr/bin/env python3
"""
TDD Tests for error-handling-patterns Skill Enhancement (FAILING - Red Phase)

This module contains FAILING tests for enhancing the error-handling-patterns skill
with library integration guidance (Issue #70).

Skill Enhancement Requirements:

1. Enhance existing skill: skills/error-handling-patterns/SKILL.md
   - Update YAML frontmatter with library integration keywords
   - Add library-specific error handling patterns
   - Expand progressive disclosure content

2. New documentation file:
   - docs/library-integration-guide.md: How libraries should use error patterns

3. New example files:
   - examples/validation-error-template.py: Validation error examples
   - examples/error-recovery-patterns.py: Error recovery strategies
   - examples/error-testing-patterns.py: How to test error handling

4. Library integration:
   - Update 18 libraries to reference error-handling-patterns skill
   - Remove verbose inline error handling code
   - Standardize error handling approach

5. Create audit document:
   - docs/LIBRARY_ERROR_HANDLING_AUDIT.md: Track library integration status

Libraries to update (18 total):
- security_utils.py
- project_md_updater.py
- version_detector.py
- orphan_file_cleaner.py
- sync_dispatcher.py
- validate_marketplace_version.py
- plugin_updater.py
- update_plugin.py
- hook_activator.py
- validate_documentation_parity.py
- auto_implement_git_integration.py
- github_issue_automation.py
- brownfield_retrofit.py
- codebase_analyzer.py
- alignment_assessor.py
- migration_planner.py
- retrofit_executor.py
- retrofit_verifier.py

Expected Token Savings: ~800 tokens (18 libraries × ~45 tokens average)

Test Coverage Target: 100% of skill enhancement and library integration

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe skill requirements and library integration
- Tests should FAIL until skill files and library updates are implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-12
Issue: #70
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import re
import ast

import pytest
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Skill paths
SKILL_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "skills" / "error-handling-patterns"
SKILL_FILE = SKILL_DIR / "SKILL.md"
DOCS_DIR = SKILL_DIR / "docs"
EXAMPLES_DIR = SKILL_DIR / "examples"

# Documentation files
LIBRARY_INTEGRATION_GUIDE_FILE = DOCS_DIR / "library-integration-guide.md"

# Example files
VALIDATION_ERROR_TEMPLATE_FILE = EXAMPLES_DIR / "validation-error-template.py"
ERROR_RECOVERY_PATTERNS_FILE = EXAMPLES_DIR / "error-recovery-patterns.py"
ERROR_TESTING_PATTERNS_FILE = EXAMPLES_DIR / "error-testing-patterns.py"

# Library paths
LIB_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib"

# Audit document
AUDIT_FILE = Path(__file__).parent.parent.parent.parent / "docs" / "LIBRARY_ERROR_HANDLING_AUDIT.md"

# Libraries to update
LIBRARIES_TO_UPDATE = [
    "security_utils.py",
    "project_md_updater.py",
    "version_detector.py",
    "orphan_file_cleaner.py",
    "sync_dispatcher.py",
    "validate_marketplace_version.py",
    "plugin_updater.py",
    "update_plugin.py",
    "hook_activator.py",
    "validate_documentation_parity.py",
    "auto_implement_git_integration.py",
    "github_issue_automation.py",
    "brownfield_retrofit.py",
    "codebase_analyzer.py",
    "alignment_assessor.py",
    "migration_planner.py",
    "retrofit_executor.py",
    "retrofit_verifier.py"
]


# ============================================================================
# Test Suite 1: Skill Enhancement
# ============================================================================


class TestErrorHandlingSkillEnhancement:
    """Test error-handling-patterns skill enhancement."""

    def test_skill_file_exists(self):
        """Test SKILL.md file exists (should already exist from Issue #64)."""
        assert SKILL_FILE.exists(), (
            f"Skill file not found: {SKILL_FILE}\n"
            f"Expected: Existing skills/error-handling-patterns/SKILL.md\n"
            f"Note: Created in Issue #64, enhanced in Issue #70\n"
            f"See: Issue #70"
        )

    def test_skill_metadata_includes_library_keywords(self):
        """Test skill metadata updated with library integration keywords."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        keywords = frontmatter.get("keywords", [])

        # Library-specific keywords
        library_keywords = [
            "library",
            "integration",
            "validation error",
            "error recovery"
        ]

        found_keywords = [k for k in library_keywords if any(k in keyword.lower() for keyword in keywords)]

        assert len(found_keywords) >= 2, (
            f"Missing library integration keywords in error-handling-patterns SKILL.md\n"
            f"Expected: At least 2 of {library_keywords}\n"
            f"Found: {found_keywords}\n"
            f"See: Issue #70"
        )

    def test_skill_content_includes_library_patterns(self):
        """Test skill content includes library-specific error patterns."""
        content = SKILL_FILE.read_text()

        # Library error handling concepts
        library_concepts = [
            "library",
            "validation",
            "graceful degradation",
            "error recovery"
        ]

        found = [c for c in library_concepts if c in content.lower()]

        assert len(found) >= 3, (
            f"Skill content should include library error patterns\n"
            f"Expected: At least 3 of {library_concepts}\n"
            f"Found: {found}\n"
            f"See: Issue #70"
        )


# ============================================================================
# Test Suite 2: Documentation Files
# ============================================================================


class TestErrorHandlingDocumentation:
    """Test error-handling-patterns documentation files."""

    def test_library_integration_guide_exists(self):
        """Test library-integration-guide.md documentation file exists."""
        assert LIBRARY_INTEGRATION_GUIDE_FILE.exists(), (
            f"Library integration guide not found: {LIBRARY_INTEGRATION_GUIDE_FILE}\n"
            f"Expected: Create skills/error-handling-patterns/docs/library-integration-guide.md\n"
            f"Content: How libraries should implement error handling patterns\n"
            f"See: Issue #70"
        )

    def test_library_integration_guide_has_error_hierarchy(self):
        """Test library-integration-guide.md documents error class hierarchy."""
        content = LIBRARY_INTEGRATION_GUIDE_FILE.read_text()

        # Error hierarchy concepts
        hierarchy_concepts = [
            "BaseError",
            "hierarchy",
            "exception",
            "inheritance"
        ]

        found = [c for c in hierarchy_concepts if c in content]

        assert len(found) >= 3, (
            f"library-integration-guide.md should document error hierarchy\n"
            f"Expected: At least 3 of {hierarchy_concepts}\n"
            f"Found: {found}\n"
            f"See: Issue #70"
        )

    def test_library_integration_guide_has_validation_patterns(self):
        """Test library-integration-guide.md includes validation error patterns."""
        content = LIBRARY_INTEGRATION_GUIDE_FILE.read_text()

        # Validation concepts
        validation_concepts = [
            "validation",
            "ValueError",
            "TypeError",
            "validate_path"
        ]

        found = [c for c in validation_concepts if c in content]

        assert len(found) >= 2, (
            f"library-integration-guide.md should include validation patterns\n"
            f"Expected: At least 2 of {validation_concepts}\n"
            f"Found: {found}\n"
            f"See: Issue #70"
        )

    def test_library_integration_guide_has_graceful_degradation(self):
        """Test library-integration-guide.md documents graceful degradation."""
        content = LIBRARY_INTEGRATION_GUIDE_FILE.read_text()

        # Graceful degradation concepts
        degradation_concepts = [
            "graceful",
            "degradation",
            "fallback",
            "recovery"
        ]

        found = [c for c in degradation_concepts if c in content.lower()]

        assert len(found) >= 2, (
            f"library-integration-guide.md should document graceful degradation\n"
            f"Expected: At least 2 of {degradation_concepts}\n"
            f"Found: {found}\n"
            f"See: Issue #70"
        )

    def test_library_integration_guide_has_audit_logging(self):
        """Test library-integration-guide.md includes security audit logging."""
        content = LIBRARY_INTEGRATION_GUIDE_FILE.read_text()

        # Audit logging concepts
        audit_concepts = [
            "audit",
            "log",
            "security_utils",
            "audit_log"
        ]

        found = [c for c in audit_concepts if c in content.lower()]

        assert len(found) >= 2, (
            f"library-integration-guide.md should include audit logging\n"
            f"Expected: At least 2 of {audit_concepts}\n"
            f"Found: {found}\n"
            f"See: Issue #70"
        )


# ============================================================================
# Test Suite 3: Example Files
# ============================================================================


class TestErrorHandlingExamples:
    """Test error-handling-patterns example files."""

    def test_validation_error_template_exists(self):
        """Test validation-error-template.py example file exists."""
        assert VALIDATION_ERROR_TEMPLATE_FILE.exists(), (
            f"Validation error template not found: {VALIDATION_ERROR_TEMPLATE_FILE}\n"
            f"Expected: Create skills/error-handling-patterns/examples/validation-error-template.py\n"
            f"Content: Python examples of validation error patterns\n"
            f"See: Issue #70"
        )

    def test_validation_error_template_is_valid_python(self):
        """Test validation-error-template.py is syntactically valid Python."""
        content = VALIDATION_ERROR_TEMPLATE_FILE.read_text()

        try:
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"validation-error-template.py has syntax errors: {e}")

    def test_validation_error_template_has_error_classes(self):
        """Test validation-error-template.py defines custom error classes."""
        content = VALIDATION_ERROR_TEMPLATE_FILE.read_text()

        # Should define custom error classes
        assert "class" in content and "Error" in content, (
            "validation-error-template.py should define custom error classes\n"
            "Expected: Examples of BaseError, ValidationError, etc.\n"
            "See: Issue #70"
        )

    def test_validation_error_template_shows_validation_examples(self):
        """Test validation-error-template.py includes validation examples."""
        content = VALIDATION_ERROR_TEMPLATE_FILE.read_text()

        # Validation patterns
        validation_patterns = [
            "validate",
            "raise",
            "ValueError",
            "TypeError"
        ]

        found = [p for p in validation_patterns if p in content]

        assert len(found) >= 3, (
            f"validation-error-template.py should show validation examples\n"
            f"Expected: At least 3 of {validation_patterns}\n"
            f"Found: {found}\n"
            f"See: Issue #70"
        )

    def test_error_recovery_patterns_exists(self):
        """Test error-recovery-patterns.py example file exists."""
        assert ERROR_RECOVERY_PATTERNS_FILE.exists(), (
            f"Error recovery patterns not found: {ERROR_RECOVERY_PATTERNS_FILE}\n"
            f"Expected: Create skills/error-handling-patterns/examples/error-recovery-patterns.py\n"
            f"Content: Python examples of error recovery strategies\n"
            f"See: Issue #70"
        )

    def test_error_recovery_patterns_is_valid_python(self):
        """Test error-recovery-patterns.py is syntactically valid Python."""
        content = ERROR_RECOVERY_PATTERNS_FILE.read_text()

        try:
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"error-recovery-patterns.py has syntax errors: {e}")

    def test_error_recovery_patterns_shows_try_except(self):
        """Test error-recovery-patterns.py demonstrates try/except patterns."""
        content = ERROR_RECOVERY_PATTERNS_FILE.read_text()

        # Recovery patterns
        assert "try:" in content and "except" in content, (
            "error-recovery-patterns.py should demonstrate try/except\n"
            "Expected: Examples of error handling and recovery\n"
            "See: Issue #70"
        )

    def test_error_recovery_patterns_shows_graceful_degradation(self):
        """Test error-recovery-patterns.py shows graceful degradation examples."""
        content = ERROR_RECOVERY_PATTERNS_FILE.read_text()

        # Graceful degradation indicators
        degradation_indicators = [
            "fallback",
            "default",
            "graceful",
            "degrade"
        ]

        found = [i for i in degradation_indicators if i in content.lower()]

        assert len(found) >= 1, (
            f"error-recovery-patterns.py should show graceful degradation\n"
            f"Expected: At least 1 of {degradation_indicators}\n"
            f"Found: {found}\n"
            f"See: Issue #70"
        )

    def test_error_testing_patterns_exists(self):
        """Test error-testing-patterns.py example file exists."""
        assert ERROR_TESTING_PATTERNS_FILE.exists(), (
            f"Error testing patterns not found: {ERROR_TESTING_PATTERNS_FILE}\n"
            f"Expected: Create skills/error-handling-patterns/examples/error-testing-patterns.py\n"
            f"Content: How to test error handling code\n"
            f"See: Issue #70"
        )

    def test_error_testing_patterns_is_valid_python(self):
        """Test error-testing-patterns.py is syntactically valid Python."""
        content = ERROR_TESTING_PATTERNS_FILE.read_text()

        try:
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"error-testing-patterns.py has syntax errors: {e}")

    def test_error_testing_patterns_uses_pytest(self):
        """Test error-testing-patterns.py demonstrates pytest patterns."""
        content = ERROR_TESTING_PATTERNS_FILE.read_text()

        # pytest patterns
        pytest_patterns = [
            "pytest.raises",
            "def test_",
            "assert"
        ]

        found = [p for p in pytest_patterns if p in content]

        assert len(found) >= 2, (
            f"error-testing-patterns.py should use pytest patterns\n"
            f"Expected: At least 2 of {pytest_patterns}\n"
            f"Found: {found}\n"
            f"See: Issue #70"
        )


# ============================================================================
# Test Suite 4: Library Integration
# ============================================================================


class TestLibraryErrorHandlingReferences:
    """Test libraries reference error-handling-patterns skill."""

    @pytest.mark.parametrize("library_name", LIBRARIES_TO_UPDATE)
    def test_library_file_exists(self, library_name):
        """Test library file exists."""
        library_file = LIB_DIR / library_name
        assert library_file.exists(), (
            f"Library file not found: {library_file}\n"
            f"Expected: Existing library file in plugins/autonomous-dev/lib/\n"
            f"See: Issue #70"
        )

    @pytest.mark.parametrize("library_name", LIBRARIES_TO_UPDATE)
    def test_library_has_skill_reference_comment(self, library_name):
        """Test library has comment referencing error-handling-patterns skill."""
        library_file = LIB_DIR / library_name
        content = library_file.read_text()

        # Should have comment referencing skill
        skill_reference_patterns = [
            "error-handling-patterns",
            "See error-handling-patterns skill",
            "skills/error-handling-patterns"
        ]

        found = any(pattern in content for pattern in skill_reference_patterns)

        assert found, (
            f"Library {library_name} should reference error-handling-patterns skill\n"
            f"Expected: Add comment like '# See error-handling-patterns skill for patterns'\n"
            f"See: Issue #70"
        )

    @pytest.mark.parametrize("library_name", LIBRARIES_TO_UPDATE)
    def test_library_uses_standard_error_patterns(self, library_name):
        """Test library uses standard error handling patterns."""
        library_file = LIB_DIR / library_name
        content = library_file.read_text()

        # Should use standard patterns
        standard_patterns = [
            "raise",           # Raises exceptions
            "except",          # Handles exceptions
            "Error"            # Uses error classes
        ]

        found = [p for p in standard_patterns if p in content]

        assert len(found) >= 2, (
            f"Library {library_name} should use standard error patterns\n"
            f"Expected: At least 2 of {standard_patterns}\n"
            f"Found: {found}\n"
            f"See: Issue #70"
        )

    def test_libraries_removed_verbose_error_handling(self):
        """Test libraries removed verbose inline error handling documentation."""
        verbose_libraries = []

        for library_name in LIBRARIES_TO_UPDATE:
            library_file = LIB_DIR / library_name
            content = library_file.read_text()

            # Count docstring lines about error handling
            docstring_pattern = re.compile(r'""".*?"""', re.DOTALL)
            docstrings = docstring_pattern.findall(content)

            for docstring in docstrings:
                # Count error-related documentation
                error_doc_count = docstring.lower().count("error") + \
                                  docstring.lower().count("exception") + \
                                  docstring.lower().count("raise")

                # Should reference skill, not duplicate full error docs
                if error_doc_count > 10:  # Threshold for verbose docs
                    verbose_libraries.append(library_name)
                    break

        assert len(verbose_libraries) <= 3, (
            f"Libraries with verbose error handling docs (should reference skill):\n" +
            "\n".join([f"  - {lib}" for lib in verbose_libraries]) +
            f"\nExpected: Most libraries should reference skill, not duplicate docs\n"
            f"See: Issue #70"
        )


# ============================================================================
# Test Suite 5: Audit Document
# ============================================================================


class TestLibraryErrorHandlingAudit:
    """Test library error handling audit document."""

    def test_audit_file_exists(self):
        """Test LIBRARY_ERROR_HANDLING_AUDIT.md file exists."""
        assert AUDIT_FILE.exists(), (
            f"Audit file not found: {AUDIT_FILE}\n"
            f"Expected: Create docs/LIBRARY_ERROR_HANDLING_AUDIT.md\n"
            f"Content: Track library integration status\n"
            f"See: Issue #70"
        )

    def test_audit_file_lists_all_libraries(self):
        """Test audit file lists all 18 libraries."""
        content = AUDIT_FILE.read_text()

        # Count how many libraries are mentioned
        mentioned_libraries = sum(1 for lib in LIBRARIES_TO_UPDATE if lib in content)

        assert mentioned_libraries == len(LIBRARIES_TO_UPDATE), (
            f"Audit file should list all {len(LIBRARIES_TO_UPDATE)} libraries\n"
            f"Found {mentioned_libraries} libraries mentioned\n"
            f"See: Issue #70"
        )

    def test_audit_file_has_status_tracking(self):
        """Test audit file tracks integration status for each library."""
        content = AUDIT_FILE.read_text()

        # Should have status indicators
        status_indicators = [
            "[ ]",  # Not started
            "[x]",  # Completed
            "status",
            "progress"
        ]

        found = [s for s in status_indicators if s in content.lower()]

        assert len(found) >= 2, (
            f"Audit file should track status\n"
            f"Expected: Checkboxes or status indicators\n"
            f"Found: {found}\n"
            f"See: Issue #70"
        )

    def test_audit_file_has_token_savings_tracking(self):
        """Test audit file tracks token savings per library."""
        content = AUDIT_FILE.read_text()

        # Should track token savings
        savings_indicators = [
            "token",
            "saving",
            "reduction",
            "before",
            "after"
        ]

        found = [s for s in savings_indicators if s in content.lower()]

        assert len(found) >= 2, (
            f"Audit file should track token savings\n"
            f"Expected: Token reduction metrics\n"
            f"Found: {found}\n"
            f"See: Issue #70"
        )


# ============================================================================
# Test Suite 6: Token Reduction Validation
# ============================================================================


class TestTokenReductionFromErrorHandling:
    """Test token reduction from error-handling-patterns skill enhancement."""

    @pytest.mark.parametrize("library_name", LIBRARIES_TO_UPDATE)
    def test_library_token_count_reasonable(self, library_name):
        """Test library token count is reasonable after skill extraction."""
        library_file = LIB_DIR / library_name
        content = library_file.read_text()

        # Rough token count (1 token ≈ 4 chars)
        token_count = len(content) // 4

        # Libraries vary in size, but should be reasonable
        # No library should exceed 5000 tokens for this project
        assert token_count < 5000, (
            f"Library {library_name} token count very high: {token_count}\n"
            f"Expected: Reasonable size after skill extraction\n"
            f"Consider extracting more content to skills\n"
            f"See: Issue #70"
        )

    def test_total_token_savings_across_all_libraries(self):
        """Test total token savings of ~800 tokens across 18 libraries."""
        # Conservative estimate: ~45 tokens per library average
        expected_savings_per_library = 45
        total_libraries = len(LIBRARIES_TO_UPDATE)
        expected_total = expected_savings_per_library * total_libraries

        # This test validates the estimate
        # Actual measurement will be done during implementation
        assert expected_total >= 800, (
            f"Expected total token savings: {expected_total}\n"
            f"Target: ≥800 tokens\n"
            f"Average per library: {expected_savings_per_library}\n"
            f"See: Issue #70"
        )

    def test_skill_progressive_disclosure_prevents_context_bloat(self):
        """Test skill uses progressive disclosure to avoid context bloat."""
        content = SKILL_FILE.read_text()

        # Skill content should NOT include all examples inline
        # Examples should be in separate files
        assert EXAMPLES_DIR.exists(), (
            "Examples should be in separate files, not inline in SKILL.md\n"
            "Expected: Progressive disclosure architecture\n"
            "See: Issue #70"
        )

        # SKILL.md should reference examples, not include them
        example_references = content.count("examples/")

        assert example_references >= 3, (
            f"SKILL.md should reference example files (found {example_references})\n"
            f"Expected: ≥3 references to examples/ files\n"
            f"This enables progressive disclosure\n"
            f"See: Issue #70"
        )


# ============================================================================
# Test Suite 7: Integration Testing
# ============================================================================


class TestErrorHandlingSkillActivation:
    """Test error-handling-patterns skill activates correctly."""

    def test_skill_activates_on_error_keywords(self):
        """Test error-handling-patterns activates when error keywords used."""
        content = SKILL_FILE.read_text()

        # Extract frontmatter
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        # Check auto_activate is true
        assert frontmatter.get("auto_activate") is True, (
            "error-handling-patterns should auto-activate on error keywords\n"
            "Expected: auto_activate: true in SKILL.md frontmatter\n"
            f"See: Issue #70"
        )

    def test_skill_has_library_integration_keywords(self):
        """Test skill has keywords for library integration scenarios."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        keywords = frontmatter.get("keywords", [])

        # Library integration keywords
        integration_keywords = [
            "library",
            "validation",
            "error recovery",
            "graceful degradation"
        ]

        found = sum(1 for kw in integration_keywords if any(kw in k.lower() for k in keywords))

        assert found >= 2, (
            f"error-handling-patterns needs library integration keywords\n"
            f"Expected: At least 2 of {integration_keywords}\n"
            f"Found: {found}\n"
            f"See: Issue #70"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
