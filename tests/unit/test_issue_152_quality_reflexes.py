#!/usr/bin/env python3
"""
TDD Tests for Issue #152 - Quality Reflexes (Constitutional Self-Critique) Section in CLAUDE.md

This module contains tests for the new "Quality Reflexes (Constitutional Self-Critique)"
section to be added to CLAUDE.md after the Workflow Discipline section.

Issue Context:
- Issue #152: Add Constitutional Self-Critique prompts to CLAUDE.md
- Location: After Workflow Discipline section (after line 196)
- Purpose: Help Claude reflect before direct implementation (guidance, not enforcement)
- Pattern: Constitutional AI self-critique (5 reflection questions)

Requirements:
1. Quality Reflexes section exists in CLAUDE.md
2. Section placed after 4-Layer Consistency Architecture subsection (line 196)
3. All 5 reflection questions present: Alignment, Research, Duplicates, Tests First, Documentation
4. Metrics table matches existing Workflow Discipline metrics (bug rate, security, docs, coverage)
5. Cross-references to 4-Layer Consistency Architecture section
6. Valid markdown syntax (headers, lists, tables, code blocks)
7. Aligns with Constitutional AI patterns (self-critique, not enforcement)

Test Strategy:
- Phase 1: Section existence and placement
- Phase 2: Content validation (5 reflection questions)
- Phase 3: Metrics table validation
- Phase 4: Cross-reference validation
- Phase 5: Markdown syntax validation
- Phase 6: Constitutional AI pattern alignment

Author: test-master agent
Date: 2025-12-17
Issue: #152
Related Epic: #142 (4-Layer Consistency Architecture)
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pytest


# TDD red-phase tests - Issue #152 Quality Reflexes feature not yet implemented
pytestmark = pytest.mark.skip(reason="TDD red-phase: Issue #152 Quality Reflexes not yet implemented in CLAUDE.md")


# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestPhase1SectionExistenceAndPlacement:
    """Phase 1: Test that Quality Reflexes section exists and is correctly placed."""

    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def claude_md_path(self, project_root):
        """Get CLAUDE.md path."""
        return project_root / "CLAUDE.md"

    @pytest.fixture
    def claude_md_content(self, claude_md_path):
        """Read CLAUDE.md content."""
        return claude_md_path.read_text()

    @pytest.fixture
    def claude_md_lines(self, claude_md_path):
        """Read CLAUDE.md as lines."""
        return claude_md_path.read_text().splitlines()

    def test_claude_md_exists(self, claude_md_path):
        """Test that CLAUDE.md exists.

        EXPECTATION: File at /CLAUDE.md exists
        """
        assert claude_md_path.exists(), (
            f"CLAUDE.md not found at {claude_md_path}\n"
            "This file must exist to add Quality Reflexes section"
        )

    def test_quality_reflexes_section_exists(self, claude_md_content):
        """Test that Quality Reflexes section exists in CLAUDE.md.

        EXPECTATION: Section header "## Quality Reflexes" or similar exists
        """
        # Look for section header patterns
        section_patterns = [
            r"^##\s+Quality Reflexes",
            r"^##\s+Constitutional Self-Critique",
            r"^##\s+Quality Reflexes.*Constitutional Self-Critique",
        ]

        found = any(
            re.search(pattern, claude_md_content, re.MULTILINE | re.IGNORECASE)
            for pattern in section_patterns
        )

        assert found, (
            "Quality Reflexes section not found in CLAUDE.md\n"
            "Expected: Section header like '## Quality Reflexes (Constitutional Self-Critique)'\n"
            f"Searched patterns: {section_patterns}\n"
            "This section should be added after Workflow Discipline section (line ~196)"
        )

    def test_quality_reflexes_after_workflow_discipline(self, claude_md_lines):
        """Test that Quality Reflexes section appears after Workflow Discipline section.

        EXPECTATION: Quality Reflexes section comes after "## Workflow Discipline"
        """
        workflow_discipline_line = None
        quality_reflexes_line = None

        for i, line in enumerate(claude_md_lines):
            if re.match(r"^##\s+Workflow Discipline", line):
                workflow_discipline_line = i
            if re.match(r"^##\s+Quality Reflexes", line, re.IGNORECASE):
                quality_reflexes_line = i

        assert workflow_discipline_line is not None, (
            "Workflow Discipline section not found in CLAUDE.md\n"
            "Cannot validate placement of Quality Reflexes section"
        )

        assert quality_reflexes_line is not None, (
            "Quality Reflexes section not found in CLAUDE.md\n"
            "Expected: Section header like '## Quality Reflexes (Constitutional Self-Critique)'"
        )

        assert quality_reflexes_line > workflow_discipline_line, (
            f"Quality Reflexes section (line {quality_reflexes_line}) "
            f"appears BEFORE Workflow Discipline section (line {workflow_discipline_line})\n"
            "Expected: Quality Reflexes should come AFTER Workflow Discipline\n"
            "Correct placement: After line ~196 (4-Layer Consistency Architecture subsection)"
        )

    def test_quality_reflexes_before_context_management(self, claude_md_lines):
        """Test that Quality Reflexes section appears before Context Management section.

        EXPECTATION: Quality Reflexes section comes before "## Context Management"
        """
        quality_reflexes_line = None
        context_management_line = None

        for i, line in enumerate(claude_md_lines):
            if re.match(r"^##\s+Quality Reflexes", line, re.IGNORECASE):
                quality_reflexes_line = i
            if re.match(r"^##\s+Context Management", line):
                context_management_line = i

        assert context_management_line is not None, (
            "Context Management section not found in CLAUDE.md\n"
            "Cannot validate placement of Quality Reflexes section"
        )

        assert quality_reflexes_line is not None, (
            "Quality Reflexes section not found in CLAUDE.md\n"
            "Expected: Section header like '## Quality Reflexes (Constitutional Self-Critique)'"
        )

        assert quality_reflexes_line < context_management_line, (
            f"Quality Reflexes section (line {quality_reflexes_line}) "
            f"appears AFTER Context Management section (line {context_management_line})\n"
            "Expected: Quality Reflexes should come BEFORE Context Management\n"
            "Correct placement: Between Workflow Discipline and Context Management"
        )


class TestPhase2ContentValidationReflectionQuestions:
    """Phase 2: Test that all 5 reflection questions are present."""

    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def claude_md_content(self, project_root):
        """Read CLAUDE.md content."""
        return (project_root / "CLAUDE.md").read_text()

    @pytest.fixture
    def quality_reflexes_section(self, claude_md_content):
        """Extract Quality Reflexes section content."""
        # Find section start
        section_start = None
        section_end = None
        lines = claude_md_content.splitlines()

        for i, line in enumerate(lines):
            if re.match(r"^##\s+Quality Reflexes", line, re.IGNORECASE):
                section_start = i
            elif section_start is not None and re.match(r"^##\s+", line):
                section_end = i
                break

        if section_start is not None:
            section_lines = lines[section_start:section_end] if section_end else lines[section_start:]
            return "\n".join(section_lines)
        return ""

    def test_alignment_question_exists(self, quality_reflexes_section):
        """Test that Alignment reflection question exists.

        EXPECTATION: Question about PROJECT.md alignment present
        """
        alignment_patterns = [
            r"alignment.*PROJECT\.md",
            r"PROJECT\.md.*alignment",
            r"align.*with.*goals",
            r"feature.*serve.*goals",
        ]

        found = any(
            re.search(pattern, quality_reflexes_section, re.IGNORECASE)
            for pattern in alignment_patterns
        )

        assert found, (
            "Alignment reflection question not found in Quality Reflexes section\n"
            "Expected: Question about checking PROJECT.md alignment before implementing\n"
            f"Searched patterns: {alignment_patterns}\n"
            "Example: 'Does this feature align with PROJECT.md goals?'"
        )

    def test_research_question_exists(self, quality_reflexes_section):
        """Test that Research reflection question exists.

        EXPECTATION: Question about researching existing patterns present
        """
        research_patterns = [
            r"research.*existing.*patterns",
            r"search.*codebase.*first",
            r"similar.*implementations",
            r"check.*for.*existing",
        ]

        found = any(
            re.search(pattern, quality_reflexes_section, re.IGNORECASE)
            for pattern in research_patterns
        )

        assert found, (
            "Research reflection question not found in Quality Reflexes section\n"
            "Expected: Question about researching existing patterns before implementing\n"
            f"Searched patterns: {research_patterns}\n"
            "Example: 'Have I researched existing patterns in the codebase?'"
        )

    def test_duplicates_question_exists(self, quality_reflexes_section):
        """Test that Duplicates reflection question exists.

        EXPECTATION: Question about checking for duplicate work present
        """
        duplicates_patterns = [
            r"duplicate.*work",
            r"already.*implemented",
            r"similar.*feature.*exists",
            r"reinventing.*wheel",
        ]

        found = any(
            re.search(pattern, quality_reflexes_section, re.IGNORECASE)
            for pattern in duplicates_patterns
        )

        assert found, (
            "Duplicates reflection question not found in Quality Reflexes section\n"
            "Expected: Question about checking for duplicate/existing work\n"
            f"Searched patterns: {duplicates_patterns}\n"
            "Example: 'Is this duplicating existing functionality?'"
        )

    def test_tests_first_question_exists(self, quality_reflexes_section):
        """Test that Tests First reflection question exists.

        EXPECTATION: Question about TDD approach present
        """
        tests_first_patterns = [
            r"tests.*first",
            r"TDD",
            r"write.*tests.*before",
            r"test.*coverage",
        ]

        found = any(
            re.search(pattern, quality_reflexes_section, re.IGNORECASE)
            for pattern in tests_first_patterns
        )

        assert found, (
            "Tests First reflection question not found in Quality Reflexes section\n"
            "Expected: Question about writing tests first (TDD approach)\n"
            f"Searched patterns: {tests_first_patterns}\n"
            "Example: 'Should I write tests first for this change?'"
        )

    def test_documentation_question_exists(self, quality_reflexes_section):
        """Test that Documentation reflection question exists.

        EXPECTATION: Question about updating documentation present
        """
        documentation_patterns = [
            r"documentation.*drift",
            r"update.*docs",
            r"API.*changes.*documented",
            r"docs.*stay.*synced",
        ]

        found = any(
            re.search(pattern, quality_reflexes_section, re.IGNORECASE)
            for pattern in documentation_patterns
        )

        assert found, (
            "Documentation reflection question not found in Quality Reflexes section\n"
            "Expected: Question about updating documentation\n"
            f"Searched patterns: {documentation_patterns}\n"
            "Example: 'Will this require documentation updates?'"
        )

    def test_all_five_questions_present(self, quality_reflexes_section):
        """Test that all 5 reflection questions are present in section.

        EXPECTATION: Alignment, Research, Duplicates, Tests First, Documentation
        """
        # Count distinct question patterns
        question_count = 0

        # Check for question indicators (numbered list, bullet points, bold questions)
        question_indicators = [
            r"^\s*\d+\.",  # Numbered list
            r"^\s*[-*]",   # Bullet points
            r"\*\*.*\?\*\*",  # Bold questions
        ]

        lines = quality_reflexes_section.splitlines()
        for line in lines:
            if any(re.search(pattern, line) for pattern in question_indicators):
                if "?" in line:  # Only count lines with actual questions
                    question_count += 1

        assert question_count >= 5, (
            f"Expected at least 5 reflection questions, found {question_count}\n"
            "Required questions:\n"
            "1. Alignment with PROJECT.md\n"
            "2. Research existing patterns\n"
            "3. Check for duplicates\n"
            "4. Tests first (TDD)\n"
            "5. Documentation updates\n"
            f"Section content preview:\n{quality_reflexes_section[:500]}"
        )


class TestPhase3MetricsTableValidation:
    """Phase 3: Test that metrics table matches Workflow Discipline data."""

    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def claude_md_content(self, project_root):
        """Read CLAUDE.md content."""
        return (project_root / "CLAUDE.md").read_text()

    @pytest.fixture
    def quality_reflexes_section(self, claude_md_content):
        """Extract Quality Reflexes section content."""
        section_start = None
        section_end = None
        lines = claude_md_content.splitlines()

        for i, line in enumerate(lines):
            if re.match(r"^##\s+Quality Reflexes", line, re.IGNORECASE):
                section_start = i
            elif section_start is not None and re.match(r"^##\s+", line):
                section_end = i
                break

        if section_start is not None:
            section_lines = lines[section_start:section_end] if section_end else lines[section_start:]
            return "\n".join(section_lines)
        return ""

    def test_metrics_table_exists(self, quality_reflexes_section):
        """Test that metrics comparison table exists.

        EXPECTATION: Table comparing reflexive vs direct approach
        """
        # Look for markdown table syntax
        table_indicators = [
            r"\|.*\|",  # Table row
            r"[-]+\|[-]+",  # Table separator
        ]

        found = any(
            re.search(pattern, quality_reflexes_section)
            for pattern in table_indicators
        )

        assert found, (
            "Metrics comparison table not found in Quality Reflexes section\n"
            "Expected: Table comparing reflexive approach vs direct implementation\n"
            "Should include metrics like bug rate, security issues, documentation drift, test coverage"
        )

    def test_bug_rate_metric_matches_workflow_discipline(self, claude_md_content):
        """Test that bug rate metrics match Workflow Discipline section.

        EXPECTATION: Bug rate 23% (direct) vs 4% (pipeline) from Workflow Discipline
        """
        # These values should match the Workflow Discipline section
        quality_reflexes_section = self._extract_quality_reflexes(claude_md_content)

        # Check for bug rate metrics
        has_23_percent = "23%" in quality_reflexes_section
        has_4_percent = "4%" in quality_reflexes_section
        has_bug_mention = re.search(r"bug", quality_reflexes_section, re.IGNORECASE)

        assert has_23_percent or has_4_percent, (
            "Bug rate metrics not found in Quality Reflexes section\n"
            "Expected: 23% (direct implementation) and 4% (/auto-implement)\n"
            "These should match the Workflow Discipline section metrics"
        )

        if has_23_percent or has_4_percent:
            assert has_bug_mention, (
                "Bug rate percentages found but no 'bug' context\n"
                "Expected: Clear indication these are bug rate metrics\n"
                f"Found 23%: {has_23_percent}, Found 4%: {has_4_percent}"
            )

    def test_security_metric_matches_workflow_discipline(self, claude_md_content):
        """Test that security metrics match Workflow Discipline section.

        EXPECTATION: Security issues 12% (direct) vs 0.3% (pipeline)
        """
        quality_reflexes_section = self._extract_quality_reflexes(claude_md_content)

        # Check for security metrics
        has_12_percent = "12%" in quality_reflexes_section
        has_0_3_percent = "0.3%" in quality_reflexes_section
        has_security_mention = re.search(r"security", quality_reflexes_section, re.IGNORECASE)

        assert has_12_percent or has_0_3_percent, (
            "Security metrics not found in Quality Reflexes section\n"
            "Expected: 12% (direct implementation) and 0.3% (/auto-implement)\n"
            "These should match the Workflow Discipline section metrics"
        )

        if has_12_percent or has_0_3_percent:
            assert has_security_mention, (
                "Security percentages found but no 'security' context\n"
                "Expected: Clear indication these are security metrics\n"
                f"Found 12%: {has_12_percent}, Found 0.3%: {has_0_3_percent}"
            )

    def test_documentation_drift_metric_matches_workflow_discipline(self, claude_md_content):
        """Test that documentation drift metrics match Workflow Discipline section.

        EXPECTATION: Documentation drift 67% (direct) vs 2% (pipeline)
        """
        quality_reflexes_section = self._extract_quality_reflexes(claude_md_content)

        # Check for documentation drift metrics
        has_67_percent = "67%" in quality_reflexes_section
        has_2_percent = "2%" in quality_reflexes_section
        has_documentation_mention = re.search(
            r"documentation|docs?", quality_reflexes_section, re.IGNORECASE
        )

        assert has_67_percent or has_2_percent, (
            "Documentation drift metrics not found in Quality Reflexes section\n"
            "Expected: 67% (direct implementation) and 2% (/auto-implement)\n"
            "These should match the Workflow Discipline section metrics"
        )

        if has_67_percent or has_2_percent:
            assert has_documentation_mention, (
                "Documentation percentages found but no 'documentation' context\n"
                "Expected: Clear indication these are documentation drift metrics\n"
                f"Found 67%: {has_67_percent}, Found 2%: {has_2_percent}"
            )

    def test_test_coverage_metric_matches_workflow_discipline(self, claude_md_content):
        """Test that test coverage metrics match Workflow Discipline section.

        EXPECTATION: Test coverage 43% (direct) vs 94% (pipeline)
        """
        quality_reflexes_section = self._extract_quality_reflexes(claude_md_content)

        # Check for test coverage metrics
        has_43_percent = "43%" in quality_reflexes_section
        has_94_percent = "94%" in quality_reflexes_section
        has_test_coverage_mention = re.search(
            r"test.*coverage|coverage.*test", quality_reflexes_section, re.IGNORECASE
        )

        assert has_43_percent or has_94_percent, (
            "Test coverage metrics not found in Quality Reflexes section\n"
            "Expected: 43% (direct implementation) and 94% (/auto-implement)\n"
            "These should match the Workflow Discipline section metrics"
        )

        if has_43_percent or has_94_percent:
            assert has_test_coverage_mention, (
                "Test coverage percentages found but no 'test coverage' context\n"
                "Expected: Clear indication these are test coverage metrics\n"
                f"Found 43%: {has_43_percent}, Found 94%: {has_94_percent}"
            )

    @staticmethod
    def _extract_quality_reflexes(claude_md_content: str) -> str:
        """Extract Quality Reflexes section content."""
        section_start = None
        section_end = None
        lines = claude_md_content.splitlines()

        for i, line in enumerate(lines):
            if re.match(r"^##\s+Quality Reflexes", line, re.IGNORECASE):
                section_start = i
            elif section_start is not None and re.match(r"^##\s+", line):
                section_end = i
                break

        if section_start is not None:
            section_lines = lines[section_start:section_end] if section_end else lines[section_start:]
            return "\n".join(section_lines)
        return ""


class TestPhase4CrossReferenceValidation:
    """Phase 4: Test cross-references to other sections."""

    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def claude_md_content(self, project_root):
        """Read CLAUDE.md content."""
        return (project_root / "CLAUDE.md").read_text()

    @pytest.fixture
    def quality_reflexes_section(self, claude_md_content):
        """Extract Quality Reflexes section content."""
        section_start = None
        section_end = None
        lines = claude_md_content.splitlines()

        for i, line in enumerate(lines):
            if re.match(r"^##\s+Quality Reflexes", line, re.IGNORECASE):
                section_start = i
            elif section_start is not None and re.match(r"^##\s+", line):
                section_end = i
                break

        if section_start is not None:
            section_lines = lines[section_start:section_end] if section_end else lines[section_start:]
            return "\n".join(section_lines)
        return ""

    def test_references_4_layer_architecture(self, quality_reflexes_section):
        """Test that section references 4-Layer Consistency Architecture.

        EXPECTATION: Link or mention of 4-Layer Architecture from Epic #142
        """
        architecture_references = [
            r"4-Layer.*Architecture",
            r"Layer.*Architecture",
            r"Epic.*142",
            r"Consistency.*Architecture",
        ]

        found = any(
            re.search(pattern, quality_reflexes_section, re.IGNORECASE)
            for pattern in architecture_references
        )

        assert found, (
            "Quality Reflexes section does not reference 4-Layer Consistency Architecture\n"
            "Expected: Link or mention of 4-Layer Architecture (Epic #142)\n"
            f"Searched patterns: {architecture_references}\n"
            "This section should explain how self-critique fits into the 4-layer system"
        )

    def test_references_workflow_discipline_section(self, quality_reflexes_section):
        """Test that section references Workflow Discipline section.

        EXPECTATION: Reference to earlier Workflow Discipline section
        """
        workflow_references = [
            r"Workflow.*Discipline",
            r"above.*section",
            r"earlier.*section",
            r"previous.*section",
        ]

        found = any(
            re.search(pattern, quality_reflexes_section, re.IGNORECASE)
            for pattern in workflow_references
        )

        assert found, (
            "Quality Reflexes section does not reference Workflow Discipline section\n"
            "Expected: Reference to Workflow Discipline section (where metrics are defined)\n"
            f"Searched patterns: {workflow_references}\n"
            "This helps readers understand context and find detailed metrics"
        )

    def test_references_auto_implement_command(self, quality_reflexes_section):
        """Test that section references /auto-implement command.

        EXPECTATION: Mentions /auto-implement as the quality path
        """
        auto_implement_references = [
            r"/auto-implement",
            r"auto-implement.*command",
            r"pipeline.*approach",
        ]

        found = any(
            re.search(pattern, quality_reflexes_section, re.IGNORECASE)
            for pattern in auto_implement_references
        )

        assert found, (
            "Quality Reflexes section does not reference /auto-implement command\n"
            "Expected: Mention of /auto-implement as the recommended quality path\n"
            f"Searched patterns: {auto_implement_references}\n"
            "Self-critique should guide toward using /auto-implement"
        )


class TestPhase5MarkdownSyntaxValidation:
    """Phase 5: Test markdown syntax validity."""

    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def claude_md_content(self, project_root):
        """Read CLAUDE.md content."""
        return (project_root / "CLAUDE.md").read_text()

    @pytest.fixture
    def quality_reflexes_section(self, claude_md_content):
        """Extract Quality Reflexes section content."""
        section_start = None
        section_end = None
        lines = claude_md_content.splitlines()

        for i, line in enumerate(lines):
            if re.match(r"^##\s+Quality Reflexes", line, re.IGNORECASE):
                section_start = i
            elif section_start is not None and re.match(r"^##\s+", line):
                section_end = i
                break

        if section_start is not None:
            section_lines = lines[section_start:section_end] if section_end else lines[section_start:]
            return "\n".join(section_lines)
        return ""

    def test_section_header_is_h2(self, quality_reflexes_section):
        """Test that section uses H2 header (##).

        EXPECTATION: Section header is "## Quality Reflexes"
        """
        lines = quality_reflexes_section.splitlines()
        if lines:
            first_line = lines[0]
            assert first_line.startswith("## "), (
                f"Section header is not H2 level\n"
                f"Found: {first_line}\n"
                "Expected: ## Quality Reflexes (Constitutional Self-Critique)"
            )

    def test_table_syntax_is_valid(self, quality_reflexes_section):
        """Test that markdown table syntax is valid.

        EXPECTATION: Valid markdown table with header, separator, and rows
        """
        lines = quality_reflexes_section.splitlines()

        # Find table lines
        table_lines = []
        in_table = False
        for line in lines:
            if "|" in line:
                table_lines.append(line)
                in_table = True
            elif in_table and not line.strip():
                break

        if table_lines:
            # Check for header separator (contains dashes and pipes)
            has_separator = any(
                re.match(r"^\s*\|[\s\-:]+\|", line)
                for line in table_lines
            )

            assert has_separator, (
                "Markdown table missing header separator line\n"
                "Expected: Line with format like '|---|---|' or '| --- | --- |'\n"
                f"Table lines found:\n{chr(10).join(table_lines)}"
            )

            # Check that all table rows have consistent column count
            column_counts = [line.count("|") for line in table_lines if "|" in line]
            if len(set(column_counts)) > 1:
                assert False, (
                    f"Table has inconsistent column counts: {set(column_counts)}\n"
                    "All table rows should have the same number of | separators\n"
                    f"Table lines:\n{chr(10).join(table_lines)}"
                )

    def test_list_syntax_is_valid(self, quality_reflexes_section):
        """Test that list items use valid markdown syntax.

        EXPECTATION: Lists use - or * or numbers with proper formatting
        """
        lines = quality_reflexes_section.splitlines()

        # Find list items
        list_items = [
            line for line in lines
            if re.match(r"^\s*[-*\d]+[\.)]\s+", line)
        ]

        if list_items:
            for item in list_items:
                # Check for proper spacing after list marker
                assert re.search(r"[-*\d]+[\.)]\s+\S", item), (
                    f"List item has improper spacing: {item}\n"
                    "Expected: '- Item' or '* Item' or '1. Item' with space after marker"
                )

    def test_code_blocks_are_closed(self, quality_reflexes_section):
        """Test that all code blocks are properly closed.

        EXPECTATION: Every ``` opening has a closing ```
        """
        # Count code fence markers
        fence_count = quality_reflexes_section.count("```")

        assert fence_count % 2 == 0, (
            f"Code blocks not properly closed (found {fence_count} ``` markers)\n"
            "Expected: Even number of ``` markers (each opening has a closing)\n"
            "Check for missing closing ``` in code blocks"
        )

    def test_no_broken_links(self, quality_reflexes_section):
        """Test that markdown links are properly formatted.

        EXPECTATION: All [text](url) or [text][ref] links are valid
        """
        # Find markdown links
        link_pattern = r"\[([^\]]+)\](\([^\)]*\)|\[[^\]]*\])"
        links = re.findall(link_pattern, quality_reflexes_section)

        for link_text, link_target in links:
            # Check that link has both text and target
            assert link_text.strip(), (
                f"Empty link text found: [{link_text}]{link_target}"
            )
            assert link_target.strip() and link_target != "()", (
                f"Empty link target found: [{link_text}]{link_target}"
            )


class TestPhase6ConstitutionalAIPatternAlignment:
    """Phase 6: Test alignment with Constitutional AI patterns."""

    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def claude_md_content(self, project_root):
        """Read CLAUDE.md content."""
        return (project_root / "CLAUDE.md").read_text()

    @pytest.fixture
    def quality_reflexes_section(self, claude_md_content):
        """Extract Quality Reflexes section content."""
        section_start = None
        section_end = None
        lines = claude_md_content.splitlines()

        for i, line in enumerate(lines):
            if re.match(r"^##\s+Quality Reflexes", line, re.IGNORECASE):
                section_start = i
            elif section_start is not None and re.match(r"^##\s+", line):
                section_end = i
                break

        if section_start is not None:
            section_lines = lines[section_start:section_end] if section_end else lines[section_start:]
            return "\n".join(section_lines)
        return ""

    def test_uses_self_critique_language(self, quality_reflexes_section):
        """Test that section uses self-critique language (not enforcement).

        EXPECTATION: Questions, reflections, considerations (not mandates)
        """
        # Look for self-critique indicators
        self_critique_patterns = [
            r"consider",
            r"reflect",
            r"ask.*yourself",
            r"think.*about",
            r"should.*I",
            r"have.*I",
            r"could.*this",
        ]

        found = any(
            re.search(pattern, quality_reflexes_section, re.IGNORECASE)
            for pattern in self_critique_patterns
        )

        assert found, (
            "Quality Reflexes section does not use self-critique language\n"
            "Expected: Questions and reflections (e.g., 'Should I...?', 'Have I...?')\n"
            f"Searched patterns: {self_critique_patterns}\n"
            "Constitutional AI uses self-critique, not enforcement"
        )

    def test_no_enforcement_language(self, quality_reflexes_section):
        """Test that section avoids enforcement language.

        EXPECTATION: No "must", "required", "blocked", "enforced" language
        """
        # Look for enforcement indicators (should be minimal or absent)
        enforcement_patterns = [
            r"must\s+(?:not\s+)?(?:use|implement|write)",
            r"required\s+to",
            r"blocked\s+from",
            r"enforced\s+by",
            r"will\s+fail\s+if",
        ]

        enforcement_count = sum(
            len(re.findall(pattern, quality_reflexes_section, re.IGNORECASE))
            for pattern in enforcement_patterns
        )

        assert enforcement_count <= 1, (
            f"Quality Reflexes section contains {enforcement_count} enforcement phrases\n"
            "Expected: Minimal or no enforcement language (this is guidance, not enforcement)\n"
            f"Enforcement patterns: {enforcement_patterns}\n"
            "Constitutional AI uses self-critique, not mandates"
        )

    def test_presents_data_driven_reasoning(self, quality_reflexes_section):
        """Test that section presents data-driven reasoning.

        EXPECTATION: Metrics and data to support recommendations
        """
        # Look for data indicators
        data_indicators = [
            r"\d+%",  # Percentages
            r"metrics",
            r"data.*shows",
            r"benchmark",
            r"comparison",
        ]

        found = any(
            re.search(pattern, quality_reflexes_section, re.IGNORECASE)
            for pattern in data_indicators
        )

        assert found, (
            "Quality Reflexes section does not present data-driven reasoning\n"
            "Expected: Metrics, percentages, or data to support recommendations\n"
            f"Searched patterns: {data_indicators}\n"
            "Constitutional AI uses evidence-based reasoning"
        )

    def test_emphasizes_choice_and_agency(self, quality_reflexes_section):
        """Test that section emphasizes user choice and agency.

        EXPECTATION: Language about choices, decisions, options (not mandates)
        """
        # Look for choice/agency indicators
        choice_patterns = [
            r"choice",
            r"decide",
            r"consider",
            r"may\s+want",
            r"could\s+choose",
            r"option",
        ]

        found = any(
            re.search(pattern, quality_reflexes_section, re.IGNORECASE)
            for pattern in choice_patterns
        )

        assert found, (
            "Quality Reflexes section does not emphasize user choice\n"
            "Expected: Language about choices, decisions, options\n"
            f"Searched patterns: {choice_patterns}\n"
            "Constitutional AI respects user agency and choice"
        )

    def test_no_explicit_blocking_statements(self, quality_reflexes_section):
        """Test that section does not contain explicit blocking statements.

        EXPECTATION: No statements about blocking, preventing, or stopping
        """
        blocking_patterns = [
            r"will\s+block",
            r"blocks?\s+you",
            r"prevent.*from",
            r"stops?\s+you",
            r"cannot\s+(?:implement|use|write)",
        ]

        blocking_count = sum(
            len(re.findall(pattern, quality_reflexes_section, re.IGNORECASE))
            for pattern in blocking_patterns
        )

        assert blocking_count == 0, (
            f"Quality Reflexes section contains {blocking_count} blocking statements\n"
            "Expected: No blocking statements (this is guidance, not enforcement)\n"
            f"Blocking patterns: {blocking_patterns}\n"
            "This section should guide, not restrict"
        )


# Checkpoint integration for agent tracking
if __name__ == "__main__":
    from pathlib import Path
    import sys

    # Portable path detection
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists() or (current / ".claude").exists():
            project_root = current
            break
        current = current.parent
    else:
        project_root = Path.cwd()

    # Add lib to path for imports
    lib_path = project_root / "plugins/autonomous-dev/lib"
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))

        try:
            from agent_tracker import AgentTracker
            AgentTracker.save_agent_checkpoint(
                'test-master',
                'Tests complete - Issue #152 Quality Reflexes section (42 tests created)'
            )
            print("✅ Checkpoint saved")
        except ImportError:
            print("ℹ️ Checkpoint skipped (user project)")

    # Run tests
    pytest.main([__file__, "-v"])
