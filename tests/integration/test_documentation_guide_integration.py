#!/usr/bin/env python3
"""
Integration Tests for documentation-guide Skill Phase 8.4 (FAILING - Red Phase)

This module contains FAILING integration tests for documentation-guide skill
enhancement and progressive disclosure (Issue #66 - Phase 8.4).

Integration Test Coverage:
1. Skill progressive disclosure activates on documentation keywords
2. Skill content loads on-demand (not all at once)
3. doc-master workflow completes with skill references
4. reviewer workflow completes with skill references
5. End-to-end documentation update workflow

Test Strategy:
- Mock Claude Code 2.0+ progressive disclosure behavior
- Verify skill activation triggers
- Test agent workflows use skill content
- Validate context budget stays manageable

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe integration requirements
- Tests should FAIL until implementation is complete
- Each test validates ONE integration scenario

Author: test-master agent
Date: 2025-11-12
Issue: #66 (Phase 8.4)
"""

import re
import sys
from pathlib import Path
from typing import List, Set
from unittest.mock import Mock, patch, MagicMock

import pytest


class TestDocumentationGuideSkillActivation:
    """Integration tests for documentation-guide skill activation."""

    AGENTS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents"
    SKILLS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "skills"
    SKILL_DIR = SKILLS_DIR / "documentation-guide"

    def test_skill_directory_exists(self):
        """
        GIVEN: documentation-guide skill enhanced with Phase 8.4 files
        WHEN: Checking skill directory structure
        THEN: All required directories and files exist
        """
        assert self.SKILL_DIR.exists(), (
            "documentation-guide skill directory not found"
        )

        # Check subdirectories
        docs_dir = self.SKILL_DIR / "docs"
        templates_dir = self.SKILL_DIR / "templates"

        assert docs_dir.exists(), "docs/ subdirectory not found"
        assert templates_dir.exists(), "templates/ subdirectory not found"

    def test_skill_metadata_exists(self):
        """
        GIVEN: documentation-guide skill directory
        WHEN: Checking for SKILL.md metadata file
        THEN: SKILL.md exists with proper frontmatter
        """
        skill_md = self.SKILL_DIR / "SKILL.md"
        assert skill_md.exists(), "SKILL.md metadata file not found"

        content = skill_md.read_text()

        # Check frontmatter exists
        assert "---" in content, "SKILL.md missing YAML frontmatter"
        assert "name: documentation-guide" in content, "SKILL.md missing skill name"
        assert "keywords:" in content, "SKILL.md missing keywords for progressive disclosure"

    def test_doc_master_loads_documentation_guide_skill(self):
        """
        GIVEN: doc-master agent with documentation-guide skill reference
        WHEN: Agent processes documentation update task
        THEN: documentation-guide skill is accessible
        """
        doc_master_file = self.AGENTS_DIR / "doc-master.md"
        assert doc_master_file.exists(), "doc-master agent file not found"

        content = doc_master_file.read_text()

        # Check that documentation-guide is listed
        assert (
            "documentation-guide" in content
        ), "doc-master missing documentation-guide skill reference"

    def test_reviewer_loads_documentation_guide_skill(self):
        """
        GIVEN: reviewer agent with documentation-guide skill reference
        WHEN: Agent processes code review with documentation checks
        THEN: documentation-guide skill is accessible
        """
        reviewer_file = self.AGENTS_DIR / "reviewer.md"
        assert reviewer_file.exists(), "reviewer agent file not found"

        content = reviewer_file.read_text()

        # Check that documentation-guide is listed
        assert (
            "documentation-guide" in content
        ), "reviewer missing documentation-guide skill reference"

    def test_implementer_loads_documentation_guide_skill(self):
        """
        GIVEN: implementer agent with documentation-guide skill reference
        WHEN: Agent writes code with docstrings
        THEN: documentation-guide skill is accessible for docstring templates
        """
        implementer_file = self.AGENTS_DIR / "implementer.md"
        assert implementer_file.exists(), "implementer agent file not found"

        content = implementer_file.read_text()

        # Check that documentation-guide is listed
        assert (
            "documentation-guide" in content
        ), "implementer missing documentation-guide skill reference"


class TestProgressiveDisclosure:
    """Test progressive disclosure behavior for documentation-guide skill."""

    SKILL_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "skills" / "documentation-guide"

    def test_skill_keywords_trigger_activation(self):
        """
        GIVEN: documentation-guide SKILL.md with keywords
        WHEN: Task contains documentation-related keywords
        THEN: Skill should activate via progressive disclosure
        """
        skill_md = self.SKILL_DIR / "SKILL.md"
        content = skill_md.read_text()

        # Extract keywords from frontmatter
        if "keywords:" in content:
            keywords_line = [line for line in content.split("\n") if "keywords:" in line][0]
            keywords = keywords_line.split("keywords:")[1].strip()

            # Check for documentation-related keywords
            doc_keywords = ["documentation", "docs", "readme", "changelog", "parity", "docstring"]
            found_keywords = [kw for kw in doc_keywords if kw in keywords.lower()]

            assert len(found_keywords) >= 3, (
                f"SKILL.md should have documentation-related keywords for progressive disclosure\n"
                f"Expected keywords: {doc_keywords}\n"
                f"Found: {found_keywords}\n"
                f"Progressive disclosure: Skills activate based on keywords in task description"
            )

    def test_skill_auto_activate_enabled(self):
        """
        GIVEN: documentation-guide SKILL.md
        WHEN: Checking auto_activate setting
        THEN: auto_activate should be true for progressive disclosure
        """
        skill_md = self.SKILL_DIR / "SKILL.md"
        content = skill_md.read_text()

        # Check for auto_activate in frontmatter
        assert "auto_activate:" in content, (
            "SKILL.md should have auto_activate setting in frontmatter\n"
            "Progressive disclosure: auto_activate enables automatic skill loading"
        )

        # Extract auto_activate value
        auto_activate_line = [line for line in content.split("\n") if "auto_activate:" in line][0]
        assert "true" in auto_activate_line.lower(), (
            "auto_activate should be true for progressive disclosure\n"
            "Expected: auto_activate: true"
        )

    def test_metadata_small_full_content_larger(self):
        """
        GIVEN: documentation-guide skill with SKILL.md metadata and docs/templates
        WHEN: Comparing metadata size to full content size
        THEN: Metadata should be significantly smaller (progressive disclosure benefit)
        """
        skill_md = self.SKILL_DIR / "SKILL.md"
        docs_dir = self.SKILL_DIR / "docs"
        templates_dir = self.SKILL_DIR / "templates"

        # Calculate metadata size (just SKILL.md frontmatter + brief description)
        skill_content = skill_md.read_text()
        # Frontmatter is between first two --- markers
        frontmatter = skill_content.split("---")[1] if "---" in skill_content else skill_content
        metadata_size = len(frontmatter)

        # Calculate full content size (all docs + templates)
        full_content_size = 0
        if docs_dir.exists():
            for doc_file in docs_dir.glob("*.md"):
                full_content_size += len(doc_file.read_text())
        if templates_dir.exists():
            for template_file in templates_dir.glob("*"):
                if template_file.is_file():
                    full_content_size += len(template_file.read_text())

        # Progressive disclosure benefit: metadata should be < 10% of full content
        assert metadata_size < full_content_size * 0.1, (
            f"Progressive disclosure benefit not achieved\n"
            f"Metadata size: {metadata_size} bytes\n"
            f"Full content size: {full_content_size} bytes\n"
            f"Metadata is {metadata_size / full_content_size * 100:.1f}% of full content\n"
            f"Expected: Metadata < 10% of full content for efficient progressive disclosure"
        )


class TestDocMasterWorkflow:
    """Test doc-master agent workflow with documentation-guide skill."""

    AGENTS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents"

    def test_doc_master_references_parity_validation_skill(self):
        """
        GIVEN: doc-master agent updated to reference parity-validation skill file
        WHEN: Agent needs to validate documentation parity
        THEN: Agent should reference skill instead of inline checklist
        """
        doc_master_file = self.AGENTS_DIR / "doc-master.md"
        content = doc_master_file.read_text()

        # Should NOT have the long inline checklist anymore
        inline_checklist_indicators = [
            "## Documentation Parity Validation Checklist",
            "1. **Run Parity Validator**",
            "2. **Check Version Consistency**",
            "3. **Verify Count Accuracy**"
        ]

        # Count how many inline checklist indicators are present
        found_inline = sum(1 for indicator in inline_checklist_indicators if indicator in content)

        assert found_inline == 0, (
            f"doc-master should NOT have inline parity validation checklist\n"
            f"Found {found_inline} inline checklist indicators\n"
            f"Expected: Reference documentation-guide skill instead\n"
            f"Progressive disclosure: Checklist moved to skill file"
        )

        # Should reference the skill
        skill_references = ["documentation-guide", "parity-validation", "consult"]
        found_references = [ref for ref in skill_references if ref in content.lower()]

        assert len(found_references) >= 1, (
            f"doc-master should reference documentation-guide skill for parity validation\n"
            f"Expected references: {skill_references}\n"
            f"Found: {found_references}"
        )

    def test_doc_master_references_changelog_format_skill(self):
        """
        GIVEN: doc-master agent updated to reference changelog-format skill file
        WHEN: Agent needs to update CHANGELOG
        THEN: Agent should reference skill for format guidance
        """
        doc_master_file = self.AGENTS_DIR / "doc-master.md"
        content = doc_master_file.read_text()

        # Should reference changelog guidance from skill
        changelog_references = ["changelog-format", "documentation-guide", "keep a changelog"]
        found_references = [ref for ref in changelog_references if ref.lower() in content.lower()]

        assert len(found_references) >= 1, (
            f"doc-master should reference documentation-guide skill for changelog format\n"
            f"Expected references: {changelog_references}\n"
            f"Found: {found_references}"
        )


class TestReviewerWorkflow:
    """Test reviewer agent workflow with documentation-guide skill."""

    AGENTS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents"

    def test_reviewer_checks_docstring_quality(self):
        """
        GIVEN: reviewer agent with documentation-guide skill reference
        WHEN: Agent reviews code with docstrings
        THEN: Agent should reference docstring standards from skill
        """
        reviewer_file = self.AGENTS_DIR / "reviewer.md"
        content = reviewer_file.read_text()

        # Should reference documentation-guide for docstring standards
        docstring_references = ["documentation-guide", "docstring"]
        found_references = [ref for ref in docstring_references if ref.lower() in content.lower()]

        assert len(found_references) >= 1, (
            f"reviewer should reference documentation-guide skill for docstring checks\n"
            f"Expected references: {docstring_references}\n"
            f"Found: {found_references}"
        )


class TestImplementerWorkflow:
    """Test implementer agent workflow with documentation-guide skill."""

    AGENTS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents"

    def test_implementer_writes_docstrings_with_skill_guidance(self):
        """
        GIVEN: implementer agent with documentation-guide skill reference
        WHEN: Agent writes code with docstrings
        THEN: Agent should reference docstring templates from skill
        """
        implementer_file = self.AGENTS_DIR / "implementer.md"
        content = implementer_file.read_text()

        # Should reference documentation-guide for docstring templates
        template_references = ["documentation-guide", "docstring"]
        found_references = [ref for ref in template_references if ref.lower() in content.lower()]

        assert len(found_references) >= 1, (
            f"implementer should reference documentation-guide skill for docstring templates\n"
            f"Expected references: {template_references}\n"
            f"Found: {found_references}"
        )


class TestEndToEndDocumentationWorkflow:
    """Test end-to-end documentation update workflow with skill integration."""

    AGENTS_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "agents"
    SKILL_DIR = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "skills" / "documentation-guide"

    def test_all_documentation_agents_reference_skill(self):
        """
        GIVEN: 9 agents that deal with documentation
        WHEN: Checking agent prompts for documentation-guide skill references
        THEN: All 9 agents should reference the skill
        """
        documentation_agents = [
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

        missing_references = []

        for agent_name in documentation_agents:
            agent_file = self.AGENTS_DIR / f"{agent_name}.md"
            if not agent_file.exists():
                missing_references.append(f"{agent_name}.md (file not found)")
                continue

            content = agent_file.read_text()
            if "documentation-guide" not in content:
                missing_references.append(f"{agent_name}.md (no skill reference)")

        assert len(missing_references) == 0, (
            f"Some documentation agents missing documentation-guide skill reference:\n"
            f"{chr(10).join(missing_references)}\n"
            f"Expected: All 9 documentation agents reference the skill"
        )

    def test_skill_files_provide_comprehensive_guidance(self):
        """
        GIVEN: documentation-guide skill with 4 docs files and 3 template files
        WHEN: Checking file count and content
        THEN: All 7 files should exist and contain guidance
        """
        docs_dir = self.SKILL_DIR / "docs"
        templates_dir = self.SKILL_DIR / "templates"

        # Check docs files exist
        expected_docs = [
            "parity-validation.md",
            "changelog-format.md",
            "readme-structure.md",
            "docstring-standards.md"
        ]

        missing_docs = []
        for doc_file in expected_docs:
            if not (docs_dir / doc_file).exists():
                missing_docs.append(doc_file)

        assert len(missing_docs) == 0, (
            f"Missing documentation files in docs/:\n"
            f"{chr(10).join(missing_docs)}\n"
            f"Expected: All 4 docs files exist"
        )

        # Check template files exist
        expected_templates = [
            "docstring-template.py",
            "readme-template.md",
            "changelog-template.md"
        ]

        missing_templates = []
        for template_file in expected_templates:
            if not (templates_dir / template_file).exists():
                missing_templates.append(template_file)

        assert len(missing_templates) == 0, (
            f"Missing template files in templates/:\n"
            f"{chr(10).join(missing_templates)}\n"
            f"Expected: All 3 template files exist"
        )

    def test_context_budget_stays_manageable(self):
        """
        GIVEN: documentation-guide skill with progressive disclosure
        WHEN: Calculating total skill content size
        THEN: Metadata should be < 1000 bytes, full content can be larger
        """
        skill_md = self.SKILL_DIR / "SKILL.md"

        # Metadata (what loads initially) should be small
        skill_content = skill_md.read_text()
        frontmatter_end = skill_content.find("---", 3)  # Find second ---
        metadata = skill_content[:frontmatter_end + 3] if frontmatter_end > 0 else skill_content

        metadata_size = len(metadata)

        assert metadata_size < 1000, (
            f"Skill metadata too large for efficient progressive disclosure\n"
            f"Metadata size: {metadata_size} bytes\n"
            f"Expected: < 1000 bytes (only metadata loads initially)\n"
            f"Progressive disclosure: Full content loads on-demand"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
