#!/usr/bin/env python3
"""
TDD Tests for documentation-guide Skill Phase 8.4 Enhancement (FAILING - Red Phase)

This module contains FAILING tests for extracting documentation standards from
doc-master agent into documentation-guide skill (Issue #66 - Phase 8.4).

Skill Enhancement Requirements:
1. Create 4 new documentation files in skills/documentation-guide/docs/:
   - parity-validation.md (version consistency, count accuracy, cross-references)
   - changelog-format.md (Keep a Changelog standard, categories)
   - readme-structure.md (600-line limit, standard sections)
   - docstring-standards.md (Google style, Args/Returns/Raises)
2. Create 3 template files in skills/documentation-guide/templates/:
   - docstring-template.py (Python examples with Google-style docstrings)
   - readme-template.md (Standard README sections)
   - changelog-template.md (Keep a Changelog format)
3. Update SKILL.md metadata with new keywords and file references
4. Update 9 agents to reference documentation-guide skill instead of inline guidance:
   - doc-master.md (primary - removes parity validation checklist)
   - setup-wizard.md, reviewer.md, issue-creator.md, pr-description-generator.md
   - alignment-analyzer.md, project-bootstrapper.md, project-status-analyzer.md
   - implementer.md

Expected Token Savings: ~280 tokens (4-6% reduction in documentation guidance)

Test Coverage Target: 100% of skill enhancement and agent integration

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe skill requirements and agent integration
- Tests should FAIL until skill files and agent updates are implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-12
Issue: #66 (Phase 8.4)
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

SKILL_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "skills" / "documentation-guide"
DOCS_DIR = SKILL_DIR / "docs"
TEMPLATES_DIR = SKILL_DIR / "templates"
AGENTS_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "agents"

# Documentation files
PARITY_VALIDATION_FILE = DOCS_DIR / "parity-validation.md"
CHANGELOG_FORMAT_FILE = DOCS_DIR / "changelog-format.md"
README_STRUCTURE_FILE = DOCS_DIR / "readme-structure.md"
DOCSTRING_STANDARDS_FILE = DOCS_DIR / "docstring-standards.md"

# Template files
DOCSTRING_TEMPLATE_FILE = TEMPLATES_DIR / "docstring-template.py"
README_TEMPLATE_FILE = TEMPLATES_DIR / "readme-template.md"
CHANGELOG_TEMPLATE_FILE = TEMPLATES_DIR / "changelog-template.md"

# Agents that should reference documentation-guide skill
AGENTS_TO_UPDATE = [
    "doc-master",
    "setup-wizard",
    "reviewer",
    "issue-creator",
    "pr-description-generator",
    "alignment-analyzer",
    "project-bootstrapper",
    "project-status-analyzer",
    "implementer"
]


# ============================================================================
# Test 1: Skill Directory Structure
# ============================================================================


class TestSkillDirectoryStructure:
    """Test documentation-guide skill directory structure exists."""

    def test_docs_directory_exists(self):
        """Test docs/ subdirectory exists in documentation-guide skill."""
        assert DOCS_DIR.exists(), (
            f"Docs directory not found: {DOCS_DIR}\n"
            f"Expected: Create skills/documentation-guide/docs/ directory\n"
            f"See: Issue #66"
        )
        assert DOCS_DIR.is_dir(), (
            f"{DOCS_DIR} exists but is not a directory"
        )

    def test_templates_directory_exists(self):
        """Test templates/ subdirectory exists in documentation-guide skill."""
        assert TEMPLATES_DIR.exists(), (
            f"Templates directory not found: {TEMPLATES_DIR}\n"
            f"Expected: Create skills/documentation-guide/templates/ directory\n"
            f"See: Issue #66"
        )
        assert TEMPLATES_DIR.is_dir(), (
            f"{TEMPLATES_DIR} exists but is not a directory"
        )


# ============================================================================
# Test 2: Documentation Files Exist
# ============================================================================


class TestDocumentationFilesExist:
    """Test all 4 documentation files exist in docs/ directory."""

    def test_parity_validation_file_exists(self):
        """Test parity-validation.md file exists."""
        assert PARITY_VALIDATION_FILE.exists(), (
            f"Documentation file not found: {PARITY_VALIDATION_FILE}\n"
            f"Expected: Create skills/documentation-guide/docs/parity-validation.md\n"
            f"Content: Version consistency, count accuracy, cross-reference validation\n"
            f"Source: doc-master.md lines 44-103 (parity validation checklist)\n"
            f"See: Issue #66"
        )

    def test_changelog_format_file_exists(self):
        """Test changelog-format.md file exists."""
        assert CHANGELOG_FORMAT_FILE.exists(), (
            f"Documentation file not found: {CHANGELOG_FORMAT_FILE}\n"
            f"Expected: Create skills/documentation-guide/docs/changelog-format.md\n"
            f"Content: Keep a Changelog standard, semantic versioning, categories\n"
            f"Source: doc-master.md CHANGELOG Format section\n"
            f"See: Issue #66"
        )

    def test_readme_structure_file_exists(self):
        """Test readme-structure.md file exists."""
        assert README_STRUCTURE_FILE.exists(), (
            f"Documentation file not found: {README_STRUCTURE_FILE}\n"
            f"Expected: Create skills/documentation-guide/docs/readme-structure.md\n"
            f"Content: 600-line limit, standard sections, structure guidelines\n"
            f"Source: doc-master.md Quality Standards section\n"
            f"See: Issue #66"
        )

    def test_docstring_standards_file_exists(self):
        """Test docstring-standards.md file exists."""
        assert DOCSTRING_STANDARDS_FILE.exists(), (
            f"Documentation file not found: {DOCSTRING_STANDARDS_FILE}\n"
            f"Expected: Create skills/documentation-guide/docs/docstring-standards.md\n"
            f"Content: Google style, Args/Returns/Raises patterns\n"
            f"Source: Python best practices from doc-master\n"
            f"See: Issue #66"
        )


# ============================================================================
# Test 3: Template Files Exist
# ============================================================================


class TestTemplateFilesExist:
    """Test all 3 template files exist in templates/ directory."""

    def test_docstring_template_file_exists(self):
        """Test docstring-template.py file exists."""
        assert DOCSTRING_TEMPLATE_FILE.exists(), (
            f"Template file not found: {DOCSTRING_TEMPLATE_FILE}\n"
            f"Expected: Create skills/documentation-guide/templates/docstring-template.py\n"
            f"Content: Python file with Google-style docstring examples\n"
            f"See: Issue #66"
        )

    def test_readme_template_file_exists(self):
        """Test readme-template.md file exists."""
        assert README_TEMPLATE_FILE.exists(), (
            f"Template file not found: {README_TEMPLATE_FILE}\n"
            f"Expected: Create skills/documentation-guide/templates/readme-template.md\n"
            f"Content: Standard README sections and structure\n"
            f"See: Issue #66"
        )

    def test_changelog_template_file_exists(self):
        """Test changelog-template.md file exists."""
        assert CHANGELOG_TEMPLATE_FILE.exists(), (
            f"Template file not found: {CHANGELOG_TEMPLATE_FILE}\n"
            f"Expected: Create skills/documentation-guide/templates/changelog-template.md\n"
            f"Content: Keep a Changelog format template\n"
            f"See: Issue #66"
        )


# ============================================================================
# Test 4: Parity Validation File Content
# ============================================================================


class TestParityValidationContent:
    """Test parity-validation.md contains required content."""

    def test_parity_validation_has_version_consistency_section(self):
        """Test parity-validation.md contains version consistency guidance."""
        content = PARITY_VALIDATION_FILE.read_text()

        assert "version" in content.lower() and "consistency" in content.lower(), (
            "parity-validation.md must contain version consistency section\n"
            "Expected: Guidance on checking CLAUDE.md Last Updated date matches PROJECT.md\n"
            "Source: doc-master.md parity validation checklist step 2"
        )

    def test_parity_validation_has_count_accuracy_section(self):
        """Test parity-validation.md contains count accuracy guidance."""
        content = PARITY_VALIDATION_FILE.read_text()

        count_keywords = ["agent count", "command count", "skill count", "hook count"]
        found_keywords = [kw for kw in count_keywords if kw in content.lower()]

        assert len(found_keywords) >= 2, (
            f"parity-validation.md must contain count accuracy guidance\n"
            f"Expected keywords (found {len(found_keywords)}/4): {count_keywords}\n"
            f"Found: {found_keywords}\n"
            f"Source: doc-master.md parity validation checklist step 3"
        )

    def test_parity_validation_has_cross_reference_section(self):
        """Test parity-validation.md contains cross-reference validation guidance."""
        content = PARITY_VALIDATION_FILE.read_text()

        assert "cross-reference" in content.lower() or "cross reference" in content.lower(), (
            "parity-validation.md must contain cross-reference validation section\n"
            "Expected: Guidance on validating documented features exist as files\n"
            "Source: doc-master.md parity validation checklist step 4"
        )

    def test_parity_validation_references_parity_validator_script(self):
        """Test parity-validation.md references the parity validator Python script."""
        content = PARITY_VALIDATION_FILE.read_text()

        assert "validate_documentation_parity.py" in content, (
            "parity-validation.md must reference validate_documentation_parity.py script\n"
            "Expected: Command to run parity validator\n"
            "Source: doc-master.md parity validation checklist step 1"
        )


# ============================================================================
# Test 5: Changelog Format File Content
# ============================================================================


class TestChangelogFormatContent:
    """Test changelog-format.md contains required content."""

    def test_changelog_format_references_keep_a_changelog(self):
        """Test changelog-format.md references Keep a Changelog standard."""
        content = CHANGELOG_FORMAT_FILE.read_text()

        assert "keep a changelog" in content.lower() or "keepachangelog" in content.lower(), (
            "changelog-format.md must reference Keep a Changelog standard\n"
            "Expected: Link to keepachangelog.com or mention standard\n"
            "Source: doc-master.md CHANGELOG Format section"
        )

    def test_changelog_format_has_category_sections(self):
        """Test changelog-format.md includes standard changelog categories."""
        content = CHANGELOG_FORMAT_FILE.read_text()

        categories = ["Added", "Changed", "Fixed", "Deprecated", "Removed", "Security"]
        found_categories = [cat for cat in categories if cat in content]

        assert len(found_categories) >= 4, (
            f"changelog-format.md must include standard changelog categories\n"
            f"Expected at least 4 of: {categories}\n"
            f"Found: {found_categories}\n"
            f"Source: doc-master.md CHANGELOG Format section"
        )

    def test_changelog_format_has_semantic_versioning(self):
        """Test changelog-format.md references semantic versioning."""
        content = CHANGELOG_FORMAT_FILE.read_text()

        assert "semantic" in content.lower() or "semver" in content.lower(), (
            "changelog-format.md must reference semantic versioning\n"
            "Expected: Mention semantic versioning or semver.org\n"
            "Source: Keep a Changelog standard requires semantic versioning"
        )

    def test_changelog_format_has_unreleased_section(self):
        """Test changelog-format.md includes [Unreleased] section guidance."""
        content = CHANGELOG_FORMAT_FILE.read_text()

        assert "unreleased" in content.lower() or "[unreleased]" in content.lower(), (
            "changelog-format.md must include [Unreleased] section guidance\n"
            "Expected: Explanation of unreleased changes tracking\n"
            "Source: Keep a Changelog standard uses [Unreleased] section"
        )


# ============================================================================
# Test 6: README Structure File Content
# ============================================================================


class TestReadmeStructureContent:
    """Test readme-structure.md contains required content."""

    def test_readme_structure_has_600_line_limit(self):
        """Test readme-structure.md mentions 600-line limit."""
        content = README_STRUCTURE_FILE.read_text()

        assert "600" in content or "600-line" in content, (
            "readme-structure.md must mention 600-line limit\n"
            "Expected: Guidance on keeping README under 600 lines\n"
            "Source: doc-master.md Quality Standards section"
        )

    def test_readme_structure_has_standard_sections(self):
        """Test readme-structure.md lists standard README sections."""
        content = README_STRUCTURE_FILE.read_text()

        standard_sections = ["installation", "usage", "features", "contributing", "license"]
        found_sections = [sec for sec in standard_sections if sec in content.lower()]

        assert len(found_sections) >= 3, (
            f"readme-structure.md must list standard README sections\n"
            f"Expected at least 3 of: {standard_sections}\n"
            f"Found: {found_sections}\n"
            f"Best practice: README should have clear structure"
        )

    def test_readme_structure_has_conciseness_guidance(self):
        """Test readme-structure.md includes conciseness guidance."""
        content = README_STRUCTURE_FILE.read_text()

        conciseness_keywords = ["concise", "brief", "clear", "short"]
        found_keywords = [kw for kw in conciseness_keywords if kw in content.lower()]

        assert len(found_keywords) >= 1, (
            f"readme-structure.md must include conciseness guidance\n"
            f"Expected keywords: {conciseness_keywords}\n"
            f"Found: {found_keywords}\n"
            f"Source: doc-master.md Quality Standards 'Be concise'"
        )


# ============================================================================
# Test 7: Docstring Standards File Content
# ============================================================================


class TestDocstringStandardsContent:
    """Test docstring-standards.md contains required content."""

    def test_docstring_standards_has_google_style(self):
        """Test docstring-standards.md references Google-style docstrings."""
        content = DOCSTRING_STANDARDS_FILE.read_text()

        assert "google" in content.lower(), (
            "docstring-standards.md must reference Google-style docstrings\n"
            "Expected: Mention Google docstring format\n"
            "Best practice: Google style is industry standard for Python"
        )

    def test_docstring_standards_has_args_section(self):
        """Test docstring-standards.md includes Args section guidance."""
        content = DOCSTRING_STANDARDS_FILE.read_text()

        assert "Args:" in content or "Arguments:" in content, (
            "docstring-standards.md must include Args section guidance\n"
            "Expected: Guidance on documenting function arguments\n"
            "Google style: Uses 'Args:' section"
        )

    def test_docstring_standards_has_returns_section(self):
        """Test docstring-standards.md includes Returns section guidance."""
        content = DOCSTRING_STANDARDS_FILE.read_text()

        assert "Returns:" in content or "Return:" in content, (
            "docstring-standards.md must include Returns section guidance\n"
            "Expected: Guidance on documenting return values\n"
            "Google style: Uses 'Returns:' section"
        )

    def test_docstring_standards_has_raises_section(self):
        """Test docstring-standards.md includes Raises section guidance."""
        content = DOCSTRING_STANDARDS_FILE.read_text()

        assert "Raises:" in content or "Exceptions:" in content, (
            "docstring-standards.md must include Raises section guidance\n"
            "Expected: Guidance on documenting exceptions\n"
            "Google style: Uses 'Raises:' section"
        )

    def test_docstring_standards_has_example_section(self):
        """Test docstring-standards.md includes example docstring."""
        content = DOCSTRING_STANDARDS_FILE.read_text()

        # Check for Python code block with docstring
        has_code_block = "```python" in content or "```" in content
        has_triple_quotes = '"""' in content or "'''" in content

        assert has_code_block and has_triple_quotes, (
            "docstring-standards.md must include example docstring\n"
            "Expected: Code block with complete docstring example\n"
            "Best practice: Show concrete example"
        )


# ============================================================================
# Test 8: Template File Validity
# ============================================================================


class TestTemplateFileValidity:
    """Test template files are valid and usable."""

    def test_docstring_template_is_valid_python(self):
        """Test docstring-template.py is valid Python syntax."""
        try:
            import ast
            content = DOCSTRING_TEMPLATE_FILE.read_text()
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(
                f"docstring-template.py has invalid Python syntax: {e}\n"
                f"Template must be syntactically valid Python\n"
                f"See: Issue #66"
            )

    def test_docstring_template_has_function_example(self):
        """Test docstring-template.py contains function with docstring example."""
        content = DOCSTRING_TEMPLATE_FILE.read_text()

        assert "def " in content, (
            "docstring-template.py must contain function definition\n"
            "Expected: Example function with Google-style docstring"
        )

        assert '"""' in content or "'''" in content, (
            "docstring-template.py must contain docstring example\n"
            "Expected: Triple-quoted docstring in function"
        )

    def test_docstring_template_has_class_example(self):
        """Test docstring-template.py contains class with docstring example."""
        content = DOCSTRING_TEMPLATE_FILE.read_text()

        assert "class " in content, (
            "docstring-template.py must contain class definition\n"
            "Expected: Example class with Google-style docstring"
        )

    def test_readme_template_has_standard_sections(self):
        """Test readme-template.md contains standard README sections."""
        content = README_TEMPLATE_FILE.read_text()

        # Check for markdown headers
        assert content.count("#") >= 3, (
            "readme-template.md must contain multiple sections (markdown headers)\n"
            "Expected: Standard README sections with # headers"
        )

        # Check for common sections
        standard_sections = ["# ", "## Installation", "## Usage", "## Features"]
        found_sections = [sec for sec in standard_sections if sec in content]

        assert len(found_sections) >= 2, (
            f"readme-template.md must contain standard sections\n"
            f"Expected headers like: {standard_sections}\n"
            f"Found: {found_sections}"
        )

    def test_changelog_template_follows_keep_a_changelog(self):
        """Test changelog-template.md follows Keep a Changelog format."""
        content = CHANGELOG_TEMPLATE_FILE.read_text()

        # Check for [Unreleased] section
        assert "[Unreleased]" in content, (
            "changelog-template.md must include [Unreleased] section\n"
            "Keep a Changelog standard requires [Unreleased] section"
        )

        # Check for category sections
        categories = ["### Added", "### Changed", "### Fixed"]
        found_categories = [cat for cat in categories if cat in content]

        assert len(found_categories) >= 2, (
            f"changelog-template.md must include standard category sections\n"
            f"Expected: {categories}\n"
            f"Found: {found_categories}"
        )


# ============================================================================
# Test 9: SKILL.md Metadata Updates
# ============================================================================


class TestSkillMetadataUpdates:
    """Test SKILL.md metadata includes new keywords and file references."""

    def test_skill_md_has_updated_keywords(self):
        """Test SKILL.md keywords include new documentation-specific terms."""
        skill_md = SKILL_DIR / "SKILL.md"
        content = skill_md.read_text()

        # Extract keywords from frontmatter
        if "keywords:" in content:
            keywords_line = [line for line in content.split("\n") if "keywords:" in line][0]
            keywords_content = keywords_line.split("keywords:")[1].strip()

            new_keywords = ["parity", "validation", "docstring", "standards"]
            found_keywords = [kw for kw in new_keywords if kw in keywords_content]

            assert len(found_keywords) >= 2, (
                f"SKILL.md keywords should include new documentation terms\n"
                f"Expected keywords: {new_keywords}\n"
                f"Found: {found_keywords}\n"
                f"See: Issue #66 - Update SKILL.md metadata"
            )

    def test_skill_md_references_new_docs_directory(self):
        """Test SKILL.md references the new docs/ directory."""
        skill_md = SKILL_DIR / "SKILL.md"
        content = skill_md.read_text()

        assert "docs/" in content or "parity-validation" in content or "changelog-format" in content, (
            "SKILL.md should reference new docs/ directory or new documentation files\n"
            "Expected: Mention of new skill enhancement files\n"
            "See: Issue #66 - Update SKILL.md with new file references"
        )

    def test_skill_md_references_templates_directory(self):
        """Test SKILL.md references the new templates/ directory."""
        skill_md = SKILL_DIR / "SKILL.md"
        content = skill_md.read_text()

        assert "templates/" in content or "template" in content.lower(), (
            "SKILL.md should reference new templates/ directory\n"
            "Expected: Mention of template files\n"
            "See: Issue #66 - Update SKILL.md with template references"
        )


# ============================================================================
# Test 10: Agent Updates - doc-master
# ============================================================================


class TestDocMasterAgentUpdates:
    """Test doc-master agent references documentation-guide skill."""

    def test_doc_master_references_documentation_guide_skill(self):
        """Test doc-master.md explicitly references documentation-guide skill."""
        doc_master_file = AGENTS_DIR / "doc-master.md"
        content = doc_master_file.read_text()

        assert "documentation-guide" in content, (
            "doc-master.md must reference documentation-guide skill\n"
            "Expected: Mention in Relevant Skills section\n"
            "See: Issue #66 - Update agent to use skill"
        )

    def test_doc_master_removed_inline_parity_validation_checklist(self):
        """Test doc-master.md removed inline parity validation checklist."""
        doc_master_file = AGENTS_DIR / "doc-master.md"
        content = doc_master_file.read_text()

        # The long parity validation checklist should be removed
        checklist_indicators = [
            "## Documentation Parity Validation Checklist",
            "1. **Run Parity Validator**",
            "2. **Check Version Consistency**"
        ]

        found_indicators = [ind for ind in checklist_indicators if ind in content]

        assert len(found_indicators) == 0, (
            f"doc-master.md should have removed inline parity validation checklist\n"
            f"Found checklist indicators: {found_indicators}\n"
            f"Expected: Reference documentation-guide skill instead\n"
            f"Source: doc-master.md lines 44-103 (~58 lines to remove)\n"
            f"See: Issue #66 - Extract to skill"
        )

    def test_doc_master_references_parity_validation_skill_file(self):
        """Test doc-master.md references parity-validation.md from skill."""
        doc_master_file = AGENTS_DIR / "doc-master.md"
        content = doc_master_file.read_text()

        # Should reference the skill file instead of inline checklist
        parity_references = ["parity-validation", "documentation-guide skill", "consult"]

        found_references = [ref for ref in parity_references if ref in content.lower()]

        assert len(found_references) >= 1, (
            f"doc-master.md should reference parity-validation skill file\n"
            f"Expected references: {parity_references}\n"
            f"Found: {found_references}\n"
            f"See: Issue #66 - Reference skill instead of inline content"
        )


# ============================================================================
# Test 11: Agent Updates - Other 8 Agents
# ============================================================================


class TestOtherAgentsUpdates:
    """Test other 8 agents reference documentation-guide skill."""

    @pytest.mark.parametrize("agent_name", [
        "setup-wizard",
        "reviewer",
        "issue-creator",
        "pr-description-generator",
        "alignment-analyzer",
        "project-bootstrapper",
        "project-status-analyzer",
        "implementer"
    ])
    def test_agent_references_documentation_guide_skill(self, agent_name):
        """Test each agent references documentation-guide skill."""
        agent_file = AGENTS_DIR / f"{agent_name}.md"

        assert agent_file.exists(), (
            f"Agent file not found: {agent_file}\n"
            f"Expected: {agent_name}.md exists in agents/ directory"
        )

        content = agent_file.read_text()

        assert "documentation-guide" in content, (
            f"{agent_name}.md must reference documentation-guide skill\n"
            f"Expected: Mention in Relevant Skills section or skill references\n"
            f"See: Issue #66 - Update {agent_name} agent"
        )

    def test_reviewer_references_docstring_standards(self):
        """Test reviewer.md specifically references docstring standards."""
        reviewer_file = AGENTS_DIR / "reviewer.md"
        content = reviewer_file.read_text()

        # Reviewer should care about docstring quality
        docstring_references = ["docstring", "documentation-guide", "google style"]

        found_references = [ref for ref in docstring_references if ref.lower() in content.lower()]

        assert len(found_references) >= 1, (
            f"reviewer.md should reference docstring standards\n"
            f"Expected references: {docstring_references}\n"
            f"Found: {found_references}\n"
            f"See: Issue #66 - Reviewer checks docstring quality"
        )

    def test_implementer_references_docstring_templates(self):
        """Test implementer.md references docstring templates."""
        implementer_file = AGENTS_DIR / "implementer.md"
        content = implementer_file.read_text()

        # Implementer writes code, should reference docstring guidance
        template_references = ["docstring", "documentation-guide", "template"]

        found_references = [ref for ref in template_references if ref.lower() in content.lower()]

        assert len(found_references) >= 1, (
            f"implementer.md should reference docstring templates\n"
            f"Expected references: {template_references}\n"
            f"Found: {found_references}\n"
            f"See: Issue #66 - Implementer writes docstrings"
        )


# ============================================================================
# Test 12: Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_docs_directory_contains_only_markdown_files(self):
        """Test docs/ directory contains only .md files."""
        if DOCS_DIR.exists():
            for file in DOCS_DIR.iterdir():
                if file.is_file():
                    assert file.suffix == ".md", (
                        f"docs/ directory should contain only .md files\n"
                        f"Found: {file.name}\n"
                        f"See: Issue #66 - Documentation files are markdown"
                    )

    def test_templates_directory_has_expected_file_types(self):
        """Test templates/ directory has .py and .md files only."""
        if TEMPLATES_DIR.exists():
            valid_extensions = [".py", ".md"]
            for file in TEMPLATES_DIR.iterdir():
                if file.is_file():
                    assert file.suffix in valid_extensions, (
                        f"templates/ directory should contain only .py and .md files\n"
                        f"Found: {file.name} (extension: {file.suffix})\n"
                        f"Valid extensions: {valid_extensions}"
                    )

    def test_no_empty_documentation_files(self):
        """Test documentation files are not empty."""
        doc_files = [
            PARITY_VALIDATION_FILE,
            CHANGELOG_FORMAT_FILE,
            README_STRUCTURE_FILE,
            DOCSTRING_STANDARDS_FILE
        ]

        for doc_file in doc_files:
            if doc_file.exists():
                content = doc_file.read_text().strip()
                assert len(content) > 0, (
                    f"Documentation file is empty: {doc_file.name}\n"
                    f"Expected: File contains documentation guidance\n"
                    f"See: Issue #66"
                )

    def test_no_empty_template_files(self):
        """Test template files are not empty."""
        template_files = [
            DOCSTRING_TEMPLATE_FILE,
            README_TEMPLATE_FILE,
            CHANGELOG_TEMPLATE_FILE
        ]

        for template_file in template_files:
            if template_file.exists():
                content = template_file.read_text().strip()
                assert len(content) > 0, (
                    f"Template file is empty: {template_file.name}\n"
                    f"Expected: File contains template content\n"
                    f"See: Issue #66"
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
