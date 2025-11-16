#!/usr/bin/env python3
"""
Integration Tests for Phase 8.8 Library-Skill Pattern Extraction (FAILING - Red Phase)

This module contains FAILING integration tests that validate the complete
library-skill integration workflow for Phase 8.8 (Issue #78).

Integration Coverage:
1. All 3 skills properly reference each other and existing skills
2. Libraries correctly reference appropriate skills
3. Token reduction meets 5-8% target (1,200-1,920 tokens)
4. Backward compatibility maintained
5. Progressive disclosure functions correctly
6. Documentation parity validation

Test Coverage Target: 15 integration tests covering cross-skill validation,
token measurement, backward compatibility, and workflow integration

Following TDD principles:
- Write tests FIRST (red phase)
- Tests validate complete integration workflow
- Tests should FAIL until skills and library updates are implemented
- Each test validates ONE integration requirement

Author: test-master agent
Date: 2025-11-16
Issue: #78 Phase 8.8
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import re
import json

import pytest
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

SKILLS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "skills"
LIB_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "lib"

# New skills created in Phase 8.8
NEW_SKILLS = [
    "library-design-patterns",
    "state-management-patterns",
    "api-integration-patterns",
]

# Existing skills that should be referenced
EXISTING_SKILLS = [
    "error-handling-patterns",
    "security-patterns",
    "python-standards",
]


class TestSkillCreation:
    """Test all 3 new skills are created with proper structure."""

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_skill_directory_exists(self, skill_name):
        """Test skill directory exists with all required components."""
        skill_dir = SKILLS_DIR / skill_name
        assert skill_dir.exists(), (
            f"Skill directory not found: {skill_dir}\n"
            f"Expected: Create skills/{skill_name}/ directory\n"
            f"See: Issue #78 Phase 8.8"
        )

        # Check required subdirectories
        required_dirs = ["docs", "examples", "templates"]
        for subdir in required_dirs:
            subdir_path = skill_dir / subdir
            assert subdir_path.exists(), (
                f"Required subdirectory not found: {subdir_path}\n"
                f"Expected: Create {skill_name}/{subdir}/ directory"
            )

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_skill_file_has_valid_structure(self, skill_name):
        """Test skill SKILL.md file has valid frontmatter and content."""
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill_file.read_text()

        # Validate frontmatter
        parts = content.split("---\n", 2)
        assert len(parts) >= 3, f"Skill {skill_name} must have YAML frontmatter"

        frontmatter = yaml.safe_load(parts[1])
        assert frontmatter.get("name") == skill_name
        assert frontmatter.get("type") == "knowledge"
        assert frontmatter.get("auto_activate") is True
        assert "keywords" in frontmatter
        assert "description" in frontmatter

        # Validate content exists
        full_content = parts[2]
        assert len(full_content) > 1000, (
            f"Skill {skill_name} content too small: {len(full_content)} chars\n"
            f"Expected: Detailed pattern documentation > 1000 chars"
        )


class TestSkillCrossReferences:
    """Test skills properly reference each other and existing skills."""

    def test_library_design_patterns_references_security(self):
        """Test library-design-patterns skill references security-patterns skill."""
        skill_file = SKILLS_DIR / "library-design-patterns" / "SKILL.md"
        content = skill_file.read_text()

        assert "security-patterns" in content.lower(), (
            "library-design-patterns must reference security-patterns skill\n"
            "Expected: Cross-reference for CWE-22, CWE-59, CWE-117 prevention\n"
            "Benefits: Consistent security guidance across skills"
        )

    def test_state_management_references_error_handling(self):
        """Test state-management-patterns skill references error-handling-patterns skill."""
        skill_file = SKILLS_DIR / "state-management-patterns" / "SKILL.md"
        content = skill_file.read_text()

        assert "error-handling-patterns" in content.lower(), (
            "state-management-patterns must reference error-handling-patterns skill\n"
            "Expected: Cross-reference for state validation errors\n"
            "Benefits: Consistent error handling across state operations"
        )

    def test_api_integration_references_error_handling(self):
        """Test api-integration-patterns skill references error-handling-patterns skill."""
        skill_file = SKILLS_DIR / "api-integration-patterns" / "SKILL.md"
        content = skill_file.read_text()

        assert "error-handling-patterns" in content.lower(), (
            "api-integration-patterns must reference error-handling-patterns skill\n"
            "Expected: Cross-reference for API error handling\n"
            "Benefits: Consistent error handling for API failures"
        )

    def test_api_integration_references_security(self):
        """Test api-integration-patterns skill references security-patterns skill."""
        skill_file = SKILLS_DIR / "api-integration-patterns" / "SKILL.md"
        content = skill_file.read_text()

        assert "security-patterns" in content.lower(), (
            "api-integration-patterns must reference security-patterns skill\n"
            "Expected: Cross-reference for CWE-78 (command injection) prevention\n"
            "Benefits: Consistent security guidance for subprocess calls"
        )


class TestLibrarySkillReferences:
    """Test libraries correctly reference appropriate skills."""

    def test_security_utils_references_library_design(self):
        """Test security_utils.py references library-design-patterns skill."""
        lib_file = LIB_DIR / "security_utils.py"
        content = lib_file.read_text()

        assert "library-design-patterns" in content.lower(), (
            "security_utils.py should reference library-design-patterns skill\n"
            "Expected: Module docstring reference\n"
            "Reason: Core library following two-tier design pattern"
        )

    def test_batch_state_manager_references_state_patterns(self):
        """Test batch_state_manager.py references state-management-patterns skill."""
        lib_file = LIB_DIR / "batch_state_manager.py"
        content = lib_file.read_text()

        assert "state-management-patterns" in content.lower(), (
            "batch_state_manager.py must reference state-management-patterns skill\n"
            "Expected: Module docstring reference\n"
            "Reason: Library with JSON persistence and crash recovery"
        )

    def test_github_issue_automation_references_api_patterns(self):
        """Test github_issue_automation.py references api-integration-patterns skill."""
        lib_file = LIB_DIR / "github_issue_automation.py"

        # Skip if library doesn't exist
        if not lib_file.exists():
            pytest.skip("github_issue_automation.py not yet created")

        content = lib_file.read_text()

        assert "api-integration-patterns" in content.lower(), (
            "github_issue_automation.py must reference api-integration-patterns skill\n"
            "Expected: Module docstring reference\n"
            "Reason: Library using gh CLI for API integration"
        )

    def test_libraries_dont_duplicate_skill_content(self):
        """Test libraries reference skills instead of duplicating pattern documentation."""
        # Sample libraries that should reference skills
        libraries_to_check = [
            ("plugin_updater.py", "library-design-patterns"),
            ("user_state_manager.py", "state-management-patterns"),
            ("git_operations.py", "api-integration-patterns"),
        ]

        for lib_file, expected_skill in libraries_to_check:
            lib_path = LIB_DIR / lib_file

            # Skip if library doesn't exist
            if not lib_path.exists():
                continue

            content = lib_path.read_text()

            # Check skill is referenced
            assert expected_skill in content.lower(), (
                f"{lib_file} must reference {expected_skill} skill\n"
                f"Expected: Skill reference in module docstring or class docstring\n"
                f"See: Issue #78 Phase 8.8"
            )

            # Library shouldn't duplicate verbose pattern documentation
            # (This is a heuristic - check for common verbose phrases)
            verbose_phrases = [
                "two-tier design pattern involves",
                "progressive enhancement means",
                "atomic writes are achieved by",
                "exponential backoff algorithm",
            ]

            duplicates_found = sum(1 for phrase in verbose_phrases if phrase.lower() in content.lower())

            assert duplicates_found == 0, (
                f"{lib_file} appears to duplicate skill content\n"
                f"Found {duplicates_found} verbose pattern explanations\n"
                f"Expected: Brief skill reference, not detailed pattern documentation\n"
                f"Pattern documentation should live in skills/{expected_skill}/"
            )


class TestTokenReduction:
    """Test token reduction meets 5-8% target."""

    def test_measure_total_library_tokens_before(self):
        """Test baseline token count for all 40 libraries (before skill extraction)."""
        pytest.skip(
            "Baseline token measurement requires historical data\n"
            "Expected: Measure tokens in libraries before skill references added\n"
            "Approach: Use git to checkout previous version, count tokens\n"
            "Tool: tiktoken or similar tokenization library\n"
            "See: Issue #78 Phase 8.8"
        )

    def test_measure_total_library_tokens_after(self):
        """Test token count for all 40 libraries after skill extraction."""
        pytest.skip(
            "Token measurement requires implementation\n"
            "Expected: Measure tokens in all 40 libraries after skill references\n"
            "Tool: tiktoken or similar tokenization library\n"
            "Target: Reduction from baseline\n"
            "See: Issue #78 Phase 8.8"
        )

    def test_token_reduction_meets_target(self):
        """Test total token reduction meets 5-8% target (1,200-1,920 tokens)."""
        pytest.skip(
            "Token reduction calculation requires before/after measurements\n"
            "Expected: (baseline_tokens - current_tokens) >= 1,200\n"
            "Target range: 1,200-1,920 tokens (5-8% reduction)\n"
            "Breakdown:\n"
            "  - library-design-patterns: ~1,400 tokens (40 libs × 35 tokens)\n"
            "  - state-management-patterns: ~450 tokens (10 libs × 45 tokens)\n"
            "  - api-integration-patterns: ~360 tokens (8 libs × 45 tokens)\n"
            "  - Total: ~2,210 tokens (conservative estimate)\n"
            "See: Issue #78 Phase 8.8"
        )


class TestBackwardCompatibility:
    """Test backward compatibility is maintained."""

    def test_library_apis_unchanged(self):
        """Test library public APIs remain unchanged after skill extraction."""
        # This test validates that adding skill references doesn't break existing APIs
        pytest.skip(
            "API compatibility test requires library imports\n"
            "Expected: Import all libraries, verify public APIs exist\n"
            "Approach: Check __all__ exports, function signatures\n"
            "Benefits: Ensure refactoring doesn't break existing code"
        )

    def test_library_behavior_unchanged(self):
        """Test library behavior unchanged after adding skill references."""
        pytest.skip(
            "Behavioral test requires integration tests\n"
            "Expected: Run existing library tests, verify all pass\n"
            "Approach: pytest tests/unit/lib/ -v\n"
            "Benefits: Ensure documentation changes don't affect logic"
        )


class TestProgressiveDisclosure:
    """Test progressive disclosure works correctly for new skills."""

    def test_skill_keywords_trigger_loading(self):
        """Test skill auto-activates when keywords match task description."""
        pytest.skip(
            "Progressive disclosure test requires Claude Code 2.0+ runtime\n"
            "Expected: Test that keywords trigger skill loading\n"
            "Approach: Use Claude Code API to submit prompt with keywords\n"
            "Validation: Verify skill content loaded in context\n"
            "Benefits: Confirm on-demand loading works"
        )

    def test_skill_metadata_stays_in_context(self):
        """Test skill frontmatter (metadata) stays in context while content loads on-demand."""
        for skill_name in NEW_SKILLS:
            skill_file = SKILLS_DIR / skill_name / "SKILL.md"
            content = skill_file.read_text()
            parts = content.split("---\n", 2)
            frontmatter = parts[1]

            # Frontmatter should be small enough to keep in context
            assert len(frontmatter) < 800, (
                f"Skill {skill_name} frontmatter too large: {len(frontmatter)} chars\n"
                f"Expected: < 800 chars (~200 tokens) for efficient context usage\n"
                f"Progressive disclosure requires small metadata overhead"
            )

    def test_combined_skills_context_efficient(self):
        """Test all 3 new skills combined have small context overhead."""
        total_frontmatter_size = 0

        for skill_name in NEW_SKILLS:
            skill_file = SKILLS_DIR / skill_name / "SKILL.md"
            content = skill_file.read_text()
            parts = content.split("---\n", 2)
            frontmatter = parts[1]
            total_frontmatter_size += len(frontmatter)

        # All 3 skills combined should be < 2,400 chars (~600 tokens)
        assert total_frontmatter_size < 2400, (
            f"Combined frontmatter too large: {total_frontmatter_size} chars\n"
            f"Expected: < 2,400 chars (~600 tokens) for 3 skills\n"
            f"Average per skill: {total_frontmatter_size / 3:.0f} chars\n"
            f"Progressive disclosure benefits degraded if metadata too large"
        )


class TestDocumentationParity:
    """Test documentation stays in sync with implementation."""

    def test_claude_md_updated_with_new_skills(self):
        """Test CLAUDE.md documents 3 new skills added in Phase 8.8."""
        claude_file = Path(__file__).parent.parent.parent / "CLAUDE.md"
        content = claude_file.read_text()

        # Check for skill count update
        # After Phase 8.8, should have 22 + 3 = 25 active skills
        assert "25 active" in content.lower() or "25 skills" in content.lower(), (
            "CLAUDE.md must document updated skill count\n"
            "Expected: 25 active skills (22 existing + 3 new)\n"
            "Update: Skills (25 Active - Progressive Disclosure + Agent Integration)\n"
            "See: Issue #78 Phase 8.8"
        )

        # Check for new skills listed
        for skill_name in NEW_SKILLS:
            assert skill_name in content.lower(), (
                f"CLAUDE.md must document new skill: {skill_name}\n"
                f"Expected: Add to skills list with description\n"
                f"See: Issue #78 Phase 8.8"
            )

    def test_skills_agents_integration_doc_updated(self):
        """Test SKILLS-AGENTS-INTEGRATION.md documents new skills."""
        doc_file = Path(__file__).parent.parent.parent / "docs" / "SKILLS-AGENTS-INTEGRATION.md"

        # Skip if doc doesn't exist yet
        if not doc_file.exists():
            pytest.skip("SKILLS-AGENTS-INTEGRATION.md not yet created")

        content = doc_file.read_text()

        # Check for new skills documented
        for skill_name in NEW_SKILLS:
            assert skill_name in content.lower(), (
                f"SKILLS-AGENTS-INTEGRATION.md must document skill: {skill_name}\n"
                f"Expected: Add to skills table with description and use cases\n"
                f"See: Issue #78 Phase 8.8"
            )

    def test_libraries_md_updated_with_skill_references(self):
        """Test LIBRARIES.md documents skill references in library APIs."""
        doc_file = Path(__file__).parent.parent.parent / "docs" / "LIBRARIES.md"

        # Skip if doc doesn't exist yet
        if not doc_file.exists():
            pytest.skip("LIBRARIES.md not yet created")

        content = doc_file.read_text()

        # Check for skill references documented
        skill_reference_terms = [
            "library-design-patterns",
            "state-management-patterns",
            "api-integration-patterns",
        ]

        for term in skill_reference_terms:
            assert term in content.lower(), (
                f"LIBRARIES.md must document {term} skill\n"
                f"Expected: Document which libraries reference this skill\n"
                f"See: Issue #78 Phase 8.8"
            )


class TestSkillQuality:
    """Test skill quality and completeness."""

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_skill_has_examples(self, skill_name):
        """Test skill has at least 3 example files."""
        examples_dir = SKILLS_DIR / skill_name / "examples"
        example_files = list(examples_dir.glob("*.py"))

        assert len(example_files) >= 3, (
            f"Skill {skill_name} must have at least 3 example files\n"
            f"Found: {len(example_files)} examples\n"
            f"Expected: Real-world examples of patterns in action\n"
            f"See: Issue #78 Phase 8.8"
        )

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_skill_has_templates(self, skill_name):
        """Test skill has at least 2 template files."""
        templates_dir = SKILLS_DIR / skill_name / "templates"
        template_files = list(templates_dir.glob("*.py"))

        assert len(template_files) >= 2, (
            f"Skill {skill_name} must have at least 2 template files\n"
            f"Found: {len(template_files)} templates\n"
            f"Expected: Reusable templates for common patterns\n"
            f"See: Issue #78 Phase 8.8"
        )

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_skill_has_documentation(self, skill_name):
        """Test skill has at least 3 documentation files."""
        docs_dir = SKILLS_DIR / skill_name / "docs"
        doc_files = list(docs_dir.glob("*.md"))

        assert len(doc_files) >= 3, (
            f"Skill {skill_name} must have at least 3 documentation files\n"
            f"Found: {len(doc_files)} docs\n"
            f"Expected: Detailed pattern documentation for major concepts\n"
            f"See: Issue #78 Phase 8.8"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
