#!/usr/bin/env python3
"""
TDD Tests for library-design-patterns Skill (FAILING - Red Phase)

This module contains FAILING tests for the library-design-patterns skill that will
extract duplicated library design patterns from 40 library files (Issue #78 Phase 8.8).

Skill Requirements:
1. YAML frontmatter with name, type, description, keywords, auto_activate
2. Progressive disclosure architecture (metadata in frontmatter, content loads on-demand)
3. Standardized library design patterns:
   - Two-tier design (core logic + CLI interface)
   - Progressive enhancement pattern (string → path → whitelist)
   - Non-blocking enhancements
   - Graceful degradation
   - Security-first design (CWE-22, CWE-59, CWE-117)
4. Docstring templates and examples (examples/ directory)
5. Token reduction: ~30-40 tokens per library × 40 libraries = ~1,200-1,600 tokens

Test Coverage Target: 30 tests (SKILL.md format, docstrings, examples, library integration)

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe skill requirements and library integration
- Tests should FAIL until skill file and library updates are implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-16
Issue: #78 Phase 8.8
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import re

import pytest
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

SKILL_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "skills" / "library-design-patterns"
SKILL_FILE = SKILL_DIR / "SKILL.md"
DOCS_DIR = SKILL_DIR / "docs"
EXAMPLES_DIR = SKILL_DIR / "examples"
TEMPLATES_DIR = SKILL_DIR / "templates"
LIB_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib"


class TestSkillCreation:
    """Test library-design-patterns skill file structure and metadata."""

    def test_skill_file_exists(self):
        """Test SKILL.md file exists in skills/library-design-patterns/ directory."""
        assert SKILL_FILE.exists(), (
            f"Skill file not found: {SKILL_FILE}\n"
            f"Expected: Create skills/library-design-patterns/SKILL.md\n"
            f"See: Issue #78 Phase 8.8"
        )

    def test_skill_has_valid_yaml_frontmatter(self):
        """Test skill file has valid YAML frontmatter with required fields."""
        content = SKILL_FILE.read_text()

        # Check frontmatter exists
        assert content.startswith("---\n"), (
            "Skill file must start with YAML frontmatter (---)\n"
            "Expected format:\n"
            "---\n"
            "name: library-design-patterns\n"
            "type: knowledge\n"
            "...\n"
        )

        # Extract frontmatter
        parts = content.split("---\n", 2)
        assert len(parts) >= 3, "Skill file must have closing --- for frontmatter"

        frontmatter = yaml.safe_load(parts[1])

        # Validate required fields
        assert frontmatter.get("name") == "library-design-patterns", (
            "Skill name must be 'library-design-patterns'"
        )
        assert frontmatter.get("type") == "knowledge", (
            "Skill type must be 'knowledge'"
        )
        assert "description" in frontmatter, (
            "Skill must have 'description' field"
        )
        assert "keywords" in frontmatter, (
            "Skill must have 'keywords' field for auto-activation"
        )
        assert frontmatter.get("auto_activate") is True, (
            "Skill must have 'auto_activate: true' for progressive disclosure"
        )

    def test_skill_keywords_cover_library_terms(self):
        """Test skill keywords include library design terms."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        keywords = frontmatter.get("keywords", "")
        if isinstance(keywords, list):
            keywords = " ".join(keywords)

        expected_keywords = [
            "library", "module", "two-tier", "progressive",
            "enhancement", "cli", "docstring", "api"
        ]

        for keyword in expected_keywords:
            assert keyword.lower() in keywords.lower(), (
                f"Skill keywords must include '{keyword}' for auto-activation\n"
                f"Current keywords: {keywords}"
            )

    def test_skill_defines_two_tier_design(self):
        """Test skill defines two-tier design pattern (core logic + CLI)."""
        content = SKILL_FILE.read_text()

        assert "two-tier" in content.lower() or "two tier" in content.lower(), (
            "Skill must define two-tier design pattern\n"
            "Expected: Core logic library + CLI interface script\n"
            "Example: plugin_updater.py (core) + update_plugin.py (CLI)\n"
            "Benefits: Reusability, testability, separation of concerns"
        )

    def test_skill_defines_progressive_enhancement(self):
        """Test skill defines progressive enhancement pattern."""
        content = SKILL_FILE.read_text()

        assert "progressive enhancement" in content.lower(), (
            "Skill must define progressive enhancement pattern\n"
            "Expected: string → path → whitelist validation\n"
            "Example: Start with string paths, upgrade to Path objects, add whitelist\n"
            "Benefits: Graceful degradation, backward compatibility"
        )

    def test_skill_defines_non_blocking_enhancements(self):
        """Test skill defines non-blocking enhancement pattern."""
        content = SKILL_FILE.read_text()

        assert "non-blocking" in content.lower(), (
            "Skill must define non-blocking enhancement pattern\n"
            "Expected: Enhancements that don't block core operations\n"
            "Example: Git automation fails → feature still succeeds, show manual steps\n"
            "Benefits: Reliability, graceful degradation"
        )

    def test_skill_defines_graceful_degradation(self):
        """Test skill defines graceful degradation pattern."""
        content = SKILL_FILE.read_text()

        assert "graceful degradation" in content.lower(), (
            "Skill must define graceful degradation pattern\n"
            "Expected: Fallback to simpler behavior on failure\n"
            "Example: Auto-format fails → continue without formatting, log warning\n"
            "Benefits: Resilience, user experience"
        )

    def test_skill_defines_security_first_design(self):
        """Test skill defines security-first design pattern."""
        content = SKILL_FILE.read_text()

        # Check for security patterns
        security_terms = ["cwe-22", "cwe-59", "cwe-117", "path traversal", "validate_path"]

        found_terms = sum(1 for term in security_terms if term.lower() in content.lower())

        assert found_terms >= 2, (
            "Skill must define security-first design patterns\n"
            f"Expected: References to CWE-22, CWE-59, CWE-117, path validation\n"
            f"Found only {found_terms} of {len(security_terms)} security terms\n"
            "Benefits: Prevent vulnerabilities by design"
        )

    def test_skill_defines_docstring_standards(self):
        """Test skill defines docstring standards for libraries."""
        content = SKILL_FILE.read_text()

        docstring_elements = ["args:", "returns:", "raises:", "example:"]

        found_elements = sum(1 for elem in docstring_elements if elem.lower() in content.lower())

        assert found_elements >= 3, (
            "Skill must define docstring standards\n"
            f"Expected: Google-style docstrings with Args, Returns, Raises, Example\n"
            f"Found only {found_elements} of {len(docstring_elements)} docstring elements\n"
            "Benefits: API documentation, type hints"
        )


class TestSkillDocumentation:
    """Test library-design-patterns skill documentation structure."""

    def test_docs_directory_exists(self):
        """Test docs/ directory exists with detailed pattern documentation."""
        assert DOCS_DIR.exists(), (
            f"Documentation directory not found: {DOCS_DIR}\n"
            f"Expected: Create skills/library-design-patterns/docs/\n"
            f"Purpose: Detailed pattern documentation"
        )

    def test_two_tier_design_doc_exists(self):
        """Test two-tier-design.md documentation exists."""
        doc_file = DOCS_DIR / "two-tier-design.md"
        assert doc_file.exists(), (
            f"Two-tier design doc not found: {doc_file}\n"
            f"Expected: Detailed documentation of core logic + CLI pattern\n"
            f"Should include: Examples, benefits, when to use, anti-patterns"
        )

    def test_progressive_enhancement_doc_exists(self):
        """Test progressive-enhancement.md documentation exists."""
        doc_file = DOCS_DIR / "progressive-enhancement.md"
        assert doc_file.exists(), (
            f"Progressive enhancement doc not found: {doc_file}\n"
            f"Expected: Detailed documentation of string → path → whitelist pattern\n"
            f"Should include: Migration steps, examples, validation strategies"
        )

    def test_security_patterns_doc_exists(self):
        """Test security-patterns.md documentation exists."""
        doc_file = DOCS_DIR / "security-patterns.md"
        assert doc_file.exists(), (
            f"Security patterns doc not found: {doc_file}\n"
            f"Expected: Path validation, audit logging, input sanitization\n"
            f"Should include: CWE references, validation examples"
        )

    def test_docstring_standards_doc_exists(self):
        """Test docstring-standards.md documentation exists."""
        doc_file = DOCS_DIR / "docstring-standards.md"
        assert doc_file.exists(), (
            f"Docstring standards doc not found: {doc_file}\n"
            f"Expected: Google-style docstring templates and examples\n"
            f"Should include: Function, class, module docstrings"
        )


class TestSkillTemplates:
    """Test library-design-patterns skill provides code templates."""

    def test_templates_directory_exists(self):
        """Test templates/ directory exists with reusable templates."""
        assert TEMPLATES_DIR.exists(), (
            f"Templates directory not found: {TEMPLATES_DIR}\n"
            f"Expected: Create skills/library-design-patterns/templates/\n"
            f"Purpose: Reusable library templates"
        )

    def test_library_template_exists(self):
        """Test library-template.py exists with core logic structure."""
        template_file = TEMPLATES_DIR / "library-template.py"
        assert template_file.exists(), (
            f"Library template not found: {template_file}\n"
            f"Expected: Template showing module docstring, classes, functions\n"
            f"Should include: Security validation, error handling, logging"
        )

    def test_cli_template_exists(self):
        """Test cli-template.py exists with CLI interface structure."""
        template_file = TEMPLATES_DIR / "cli-template.py"
        assert template_file.exists(), (
            f"CLI template not found: {template_file}\n"
            f"Expected: Template showing argparse, main() function, error handling\n"
            f"Should include: Help text, argument validation, exit codes"
        )

    def test_docstring_template_exists(self):
        """Test docstring-template.py exists with Google-style examples."""
        template_file = TEMPLATES_DIR / "docstring-template.py"
        assert template_file.exists(), (
            f"Docstring template not found: {template_file}\n"
            f"Expected: Examples of function, class, module docstrings\n"
            f"Should include: Args, Returns, Raises, Examples sections"
        )


class TestSkillExamples:
    """Test library-design-patterns skill provides example implementations."""

    def test_examples_directory_exists(self):
        """Test examples/ directory exists with real-world examples."""
        assert EXAMPLES_DIR.exists(), (
            f"Examples directory not found: {EXAMPLES_DIR}\n"
            f"Expected: Create skills/library-design-patterns/examples/\n"
            f"Purpose: Real-world library examples"
        )

    def test_two_tier_example_exists(self):
        """Test two-tier-example.py shows core + CLI pattern."""
        example_file = EXAMPLES_DIR / "two-tier-example.py"
        assert example_file.exists(), (
            f"Two-tier example not found: {example_file}\n"
            f"Expected: Example showing plugin_updater.py pattern\n"
            f"Should include: CoreLogic class + main() CLI function"
        )

    def test_progressive_enhancement_example_exists(self):
        """Test progressive-enhancement-example.py shows validation evolution."""
        example_file = EXAMPLES_DIR / "progressive-enhancement-example.py"
        assert example_file.exists(), (
            f"Progressive enhancement example not found: {example_file}\n"
            f"Expected: Example showing string → Path → whitelist migration\n"
            f"Should include: Three versions with progressive validation"
        )

    def test_security_validation_example_exists(self):
        """Test security-validation-example.py shows path validation."""
        example_file = EXAMPLES_DIR / "security-validation-example.py"
        assert example_file.exists(), (
            f"Security validation example not found: {example_file}\n"
            f"Expected: Example showing validate_path() usage\n"
            f"Should include: CWE-22, CWE-59 prevention"
        )


class TestLibraryIntegration:
    """Test 40 libraries reference library-design-patterns skill."""

    LIBRARIES_USING_SKILL = [
        # Core libraries (14)
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
        "batch_state_manager.py",
        "math_utils.py",
        # Brownfield retrofit libraries (6)
        "brownfield_retrofit.py",
        "codebase_analyzer.py",
        "alignment_assessor.py",
        "migration_planner.py",
        "retrofit_executor.py",
        "retrofit_verifier.py",
        # Additional libraries (20)
        "agent_invoker.py",
        "artifacts.py",
        "auto_approval_consent.py",
        "checkpoint.py",
        "error_messages.py",
        "feature_completion_detector.py",
        "first_run_warning.py",
        "genai_validate.py",
        "git_operations.py",
        "github_issue_fetcher.py",
        "health_check.py",
        "logging_utils.py",
        "path_validator.py",
        "performance_profiler.py",
        "pytest_format_validator.py",
        "session_tracker.py",
        "subprocess_executor.py",
        "token_counter.py",
        "user_state_manager.py",
        "yaml_parser.py",
    ]

    @pytest.mark.parametrize("library_file", LIBRARIES_USING_SKILL)
    def test_library_has_skill_reference(self, library_file):
        """Test library has comment referencing library-design-patterns skill."""
        library_path = LIB_DIR / library_file

        # Skip if library doesn't exist yet
        if not library_path.exists():
            pytest.skip(f"Library {library_file} not yet created")

        content = library_path.read_text()

        # Check for skill reference in module docstring
        assert "library-design-patterns" in content.lower(), (
            f"Library {library_file} must reference 'library-design-patterns' skill\n"
            f"Expected: Add to module docstring\n"
            f"Format: See library-design-patterns skill for standardized design patterns\n"
            f"See: Issue #78 Phase 8.8"
        )

    def test_total_library_count_using_skill(self):
        """Test 40 libraries use library-design-patterns skill."""
        count = 0
        for library_file in self.LIBRARIES_USING_SKILL:
            library_path = LIB_DIR / library_file
            if library_path.exists():
                content = library_path.read_text()
                if "library-design-patterns" in content.lower():
                    count += 1

        assert count == 40, (
            f"Expected 40 libraries to reference library-design-patterns skill, found {count}\n"
            f"Target: All libraries in lib/ following design patterns\n"
            f"See: Issue #78 Phase 8.8"
        )


class TestTokenSavings:
    """Test token reduction from skill extraction."""

    def test_token_reduction_per_library(self):
        """Test each library saves ~30-40 tokens by using skill reference."""
        # Expected savings calculation:
        # Before: ~60-80 tokens for inline design pattern documentation
        # After: ~20-30 tokens for skill reference
        # Savings: ~30-40 tokens per library

        pytest.skip(
            "Token counting requires implementation\n"
            "Expected: Use tiktoken or similar to count tokens\n"
            "Baseline: Measure tokens before/after skill extraction\n"
            "Target: 30-40 tokens saved per library"
        )

    def test_total_token_reduction(self):
        """Test total token savings across all 40 libraries."""
        # Expected total savings: 35 tokens × 40 libraries = 1,400 tokens

        pytest.skip(
            "Token counting requires implementation\n"
            "Expected: Aggregate token savings across all libraries\n"
            "Target: 1,200-1,600 tokens total reduction (5-8% of library code)\n"
            "See: Issue #78 Phase 8.8"
        )


class TestProgressiveDisclosure:
    """Test progressive disclosure functionality."""

    def test_skill_metadata_small_for_context(self):
        """Test skill metadata (frontmatter) is small enough to keep in context."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = parts[1]

        # Frontmatter should be < 200 tokens (very rough estimate: ~4 chars per token)
        assert len(frontmatter) < 800, (
            f"Skill frontmatter too large: {len(frontmatter)} chars\n"
            f"Expected: < 800 chars (~200 tokens) for efficient context usage\n"
            f"Progressive disclosure keeps metadata small, loads full content on-demand"
        )

    def test_skill_full_content_loads_on_demand(self):
        """Test skill full content (after frontmatter) is available when needed."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)

        assert len(parts) >= 3, "Skill must have content after frontmatter"

        full_content = parts[2]

        # Full content should have detailed library design patterns
        assert len(full_content) > 2000, (
            f"Skill content too small: {len(full_content)} chars\n"
            f"Expected: Detailed design patterns, examples, templates\n"
            f"Progressive disclosure: Metadata always loaded, content loaded when keywords match"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
