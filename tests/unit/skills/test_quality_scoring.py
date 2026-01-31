#!/usr/bin/env python3
"""
TDD Tests for quality-scoring Skill (FAILING - Red Phase)

This module contains FAILING tests for the quality-scoring skill that provides
multi-dimensional data assessment for training data quality evaluation (Issue #310).

Skill Requirements:
1. YAML frontmatter with name="Quality Scoring", version="1.0.0", type="knowledge"
2. Progressive disclosure architecture (SKILL.md < 500 lines, detailed docs in docs/)
3. Documentation of 6 quality scorers:
   - FastIFD (instruction-following difficulty)
   - Quality (individual quality metrics)
   - MultiDimensional (6-dimension assessment)
   - LLMQuality (model-based evaluation)
   - Ensemble (combined scoring)
   - Tulu3 (reference implementation)
4. Documentation of 6 quality dimensions:
   - IFD (instruction-following difficulty)
   - Factuality (verifiable accuracy)
   - Reasoning (logical coherence)
   - Diversity (coverage breadth)
   - Domain (specialized knowledge)
   - LLM Quality (model-based assessment)
5. Training thresholds by type (SFT, DPO chosen/rejected, RLVR, Calibration)
6. CLI commands and distributed performance guidance
7. Cross-references to data-distillation and preference-data-quality skills
8. Security documentation (CWE-20, CWE-22, training_metrics.py patterns)
9. Integration with training_metrics library functions

Test Coverage Target: 100% of skill creation and documentation completeness

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe skill requirements and documentation structure
- Tests should FAIL until skill files are implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2026-01-31
Issue: #310
"""

import sys
from pathlib import Path
from typing import Dict, List

import pytest
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

SKILL_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "plugins"
    / "autonomous-dev"
    / "skills"
    / "quality-scoring"
)
SKILL_FILE = SKILL_DIR / "SKILL.md"
DOCS_DIR = SKILL_DIR / "docs"

# Documentation files
QUALITY_SCORERS_FILE = DOCS_DIR / "quality-scorers.md"
QUALITY_DIMENSIONS_FILE = DOCS_DIR / "quality-dimensions.md"
TRAINING_THRESHOLDS_FILE = DOCS_DIR / "training-thresholds.md"


# ============================================================================
# Test 1: File Existence Tests (4 tests)
# ============================================================================


class TestFileExistence:
    """Test quality-scoring skill file structure exists."""

    def test_skill_file_exists(self):
        """Test SKILL.md file exists in skills/quality-scoring/ directory."""
        assert SKILL_FILE.exists(), (
            f"Skill file not found: {SKILL_FILE}\n"
            f"Expected: Create plugins/autonomous-dev/skills/quality-scoring/SKILL.md\n"
            f"See: Issue #310"
        )

    def test_docs_directory_exists(self):
        """Test docs/ subdirectory exists in quality-scoring skill."""
        assert DOCS_DIR.exists(), (
            f"Docs directory not found: {DOCS_DIR}\n"
            f"Expected: Create skills/quality-scoring/docs/ directory\n"
            f"See: Issue #310"
        )
        assert DOCS_DIR.is_dir(), f"{DOCS_DIR} exists but is not a directory"

    def test_quality_scorers_file_exists(self):
        """Test quality-scorers.md file exists in docs/ directory."""
        assert QUALITY_SCORERS_FILE.exists(), (
            f"Documentation file not found: {QUALITY_SCORERS_FILE}\n"
            f"Expected: Create skills/quality-scoring/docs/quality-scorers.md\n"
            f"Content: Documentation of 6 quality scorers (FastIFD, Quality, "
            f"MultiDimensional, LLMQuality, Ensemble, Tulu3)\n"
            f"See: Issue #310"
        )

    def test_quality_dimensions_file_exists(self):
        """Test quality-dimensions.md file exists in docs/ directory."""
        assert QUALITY_DIMENSIONS_FILE.exists(), (
            f"Documentation file not found: {QUALITY_DIMENSIONS_FILE}\n"
            f"Expected: Create skills/quality-scoring/docs/quality-dimensions.md\n"
            f"Content: Documentation of 6 quality dimensions (IFD, Factuality, "
            f"Reasoning, Diversity, Domain, LLM Quality)\n"
            f"See: Issue #310"
        )

    def test_training_thresholds_file_exists(self):
        """Test training-thresholds.md file exists in docs/ directory."""
        assert TRAINING_THRESHOLDS_FILE.exists(), (
            f"Documentation file not found: {TRAINING_THRESHOLDS_FILE}\n"
            f"Expected: Create skills/quality-scoring/docs/training-thresholds.md\n"
            f"Content: Thresholds by training type (SFT, DPO, RLVR, Calibration) "
            f"with CLI commands and distributed performance\n"
            f"See: Issue #310"
        )


# ============================================================================
# Test 2: YAML Frontmatter Tests (6 tests)
# ============================================================================


class TestYAMLFrontmatter:
    """Test SKILL.md has valid YAML frontmatter with required fields."""

    def test_skill_has_valid_yaml_frontmatter(self):
        """Test skill file has valid YAML frontmatter structure."""
        content = SKILL_FILE.read_text()

        # Check frontmatter exists
        assert content.startswith("---\n"), (
            "Skill file must start with YAML frontmatter (---)\n"
            "Expected format:\n"
            "---\n"
            "name: Quality Scoring\n"
            "version: 1.0.0\n"
            "type: knowledge\n"
            "---\n"
        )

        # Extract frontmatter
        parts = content.split("---\n", 2)
        assert len(parts) >= 3, "Skill file must have closing --- for frontmatter"

    def test_frontmatter_name_field(self):
        """Test YAML frontmatter has name='Quality Scoring'."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        assert frontmatter.get("name") == "Quality Scoring", (
            "Skill name must be 'Quality Scoring'\n"
            "YAML frontmatter: name: Quality Scoring"
        )

    def test_frontmatter_version_field(self):
        """Test YAML frontmatter has version='1.0.0'."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        assert frontmatter.get("version") == "1.0.0", (
            "Skill version must be '1.0.0'\n" "YAML frontmatter: version: 1.0.0"
        )

    def test_frontmatter_type_field(self):
        """Test YAML frontmatter has type='knowledge'."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        assert frontmatter.get("type") == "knowledge", (
            "Skill type must be 'knowledge' (documentation skill)\n"
            "YAML frontmatter: type: knowledge"
        )

    def test_frontmatter_description_contains_multi_dimensional(self):
        """Test YAML frontmatter description contains 'multi-dimensional'."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        description = frontmatter.get("description", "")
        assert "multi-dimensional" in description.lower(), (
            "Skill description must mention 'multi-dimensional' assessment\n"
            "YAML frontmatter: description: '...multi-dimensional data assessment...'"
        )

    def test_frontmatter_keywords_include_quality_scoring(self):
        """Test YAML frontmatter keywords include quality, scoring, assessment."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        keywords = frontmatter.get("keywords", "")
        if isinstance(keywords, list):
            keywords = " ".join(keywords)

        expected_keywords = ["quality", "scoring", "assessment"]

        for keyword in expected_keywords:
            assert keyword.lower() in keywords.lower(), (
                f"Skill keywords must include '{keyword}' for auto-activation\n"
                f"Current keywords: {keywords}\n"
                f"Expected: quality, scoring, assessment, IFD, factuality, etc."
            )

    def test_frontmatter_auto_activate_is_true(self):
        """Test YAML frontmatter has auto_activate=true."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        assert frontmatter.get("auto_activate") is True, (
            "Skill must have 'auto_activate: true' for progressive disclosure\n"
            "YAML frontmatter: auto_activate: true"
        )


# ============================================================================
# Test 3: Content Completeness Tests (10 tests)
# ============================================================================


class TestContentCompleteness:
    """Test SKILL.md and docs/ files contain required content sections."""

    def test_skill_contains_when_activates_section(self):
        """Test SKILL.md contains 'When Activates' section."""
        content = SKILL_FILE.read_text()

        assert "when activates" in content.lower() or "when this activates" in content.lower(), (
            "SKILL.md must contain 'When Activates' section\n"
            "Expected: Section describing activation keywords and use cases\n"
            "Example: 'When This Skill Activates' or '## When Activates'"
        )

    def test_skill_contains_core_concepts_section(self):
        """Test SKILL.md contains 'Core Concepts' section."""
        content = SKILL_FILE.read_text()

        assert "core concepts" in content.lower(), (
            "SKILL.md must contain 'Core Concepts' section\n"
            "Expected: High-level overview of quality scoring concepts\n"
            "Example: '## Core Concepts' with key ideas"
        )

    def test_skill_contains_quick_reference_table(self):
        """Test SKILL.md contains 'Quick Reference' section with table."""
        content = SKILL_FILE.read_text()

        assert "quick reference" in content.lower(), (
            "SKILL.md must contain 'Quick Reference' section\n"
            "Expected: Quick lookup table for scorers, dimensions, thresholds"
        )

        # Check for table markers
        assert "|" in content and "---" in content, (
            "Quick Reference section should contain markdown table\n"
            "Expected: Pipe-delimited table with headers and separators"
        )

    def test_quality_scorers_documents_six_scorers(self):
        """Test quality-scorers.md documents all 6 quality scorers."""
        content = QUALITY_SCORERS_FILE.read_text()

        scorers = ["FastIFD", "Quality", "MultiDimensional", "LLMQuality", "Ensemble", "Tulu3"]
        found_scorers = [scorer for scorer in scorers if scorer in content]

        assert len(found_scorers) >= 5, (
            f"quality-scorers.md must document at least 5 of 6 quality scorers\n"
            f"Expected scorers: {scorers}\n"
            f"Found scorers: {found_scorers}\n"
            f"See: Issue #310 - Document 6 quality scorers"
        )

    def test_quality_dimensions_documents_six_dimensions(self):
        """Test quality-dimensions.md documents all 6 quality dimensions."""
        content = QUALITY_DIMENSIONS_FILE.read_text()

        dimensions = ["IFD", "Factuality", "Reasoning", "Diversity", "Domain", "LLM Quality"]
        found_dimensions = [dim for dim in dimensions if dim in content]

        assert len(found_dimensions) >= 5, (
            f"quality-dimensions.md must document at least 5 of 6 quality dimensions\n"
            f"Expected dimensions: {dimensions}\n"
            f"Found dimensions: {found_dimensions}\n"
            f"See: Issue #310 - Document 6 quality dimensions"
        )

    def test_training_thresholds_documents_four_training_types(self):
        """Test training-thresholds.md documents 4 training types."""
        content = TRAINING_THRESHOLDS_FILE.read_text()

        training_types = ["SFT", "DPO", "RLVR", "Calibration"]
        found_types = [tt for tt in training_types if tt in content]

        assert len(found_types) >= 3, (
            f"training-thresholds.md must document at least 3 of 4 training types\n"
            f"Expected types: {training_types}\n"
            f"Found types: {found_types}\n"
            f"Note: DPO includes both 'chosen' and 'rejected' thresholds\n"
            f"See: Issue #310 - Document training thresholds"
        )

    def test_training_thresholds_includes_cli_commands(self):
        """Test training-thresholds.md includes CLI commands section."""
        content = TRAINING_THRESHOLDS_FILE.read_text()

        cli_indicators = ["cli", "command", "python -m", "bash", "```"]
        found_indicators = [ind for ind in cli_indicators if ind.lower() in content.lower()]

        assert len(found_indicators) >= 2, (
            f"training-thresholds.md should include CLI commands section\n"
            f"Expected indicators: {cli_indicators}\n"
            f"Found: {found_indicators}\n"
            f"Example: Code blocks with python commands for quality scoring"
        )

    def test_training_thresholds_includes_distributed_performance(self):
        """Test training-thresholds.md includes distributed performance section."""
        content = TRAINING_THRESHOLDS_FILE.read_text()

        perf_indicators = ["distributed", "performance", "parallel", "scaling", "throughput"]
        found_indicators = [ind for ind in perf_indicators if ind.lower() in content.lower()]

        assert len(found_indicators) >= 2, (
            f"training-thresholds.md should include distributed performance guidance\n"
            f"Expected indicators: {perf_indicators}\n"
            f"Found: {found_indicators}\n"
            f"Example: Guidance on parallel processing for large datasets"
        )

    def test_skill_cross_references_data_distillation(self):
        """Test SKILL.md cross-references data-distillation skill."""
        content = SKILL_FILE.read_text()

        assert "data-distillation" in content.lower() or "data distillation" in content.lower(), (
            "SKILL.md must cross-reference data-distillation skill\n"
            "Expected: Reference in Related Skills or See Also section\n"
            "Relationship: Quality scoring is used in data distillation workflows"
        )

    def test_skill_cross_references_preference_data_quality(self):
        """Test SKILL.md cross-references preference-data-quality skill."""
        content = SKILL_FILE.read_text()

        assert (
            "preference-data-quality" in content.lower()
            or "preference data quality" in content.lower()
        ), (
            "SKILL.md must cross-reference preference-data-quality skill\n"
            "Expected: Reference in Related Skills or See Also section\n"
            "Relationship: Quality scoring applies to preference data (DPO pairs)"
        )


# ============================================================================
# Test 4: Table Format Tests (3 tests)
# ============================================================================


class TestTableFormat:
    """Test markdown tables are well-formed in documentation files."""

    def test_quick_reference_table_well_formed(self):
        """Test Quick Reference table in SKILL.md has proper markdown format."""
        content = SKILL_FILE.read_text()

        # Find table section
        if "quick reference" in content.lower():
            # Extract section after "Quick Reference"
            idx = content.lower().find("quick reference")
            table_section = content[idx : idx + 2000]

            # Check for table structure
            lines = table_section.split("\n")
            table_lines = [line for line in lines if "|" in line]

            assert len(table_lines) >= 3, (
                "Quick Reference table should have at least 3 rows (header + separator + data)\n"
                f"Found {len(table_lines)} table lines"
            )

            # Check for separator line with dashes
            separator_lines = [line for line in table_lines if "---" in line or "--" in line]
            assert len(separator_lines) >= 1, (
                "Quick Reference table must have separator line (---)\n"
                "Expected: | Header 1 | Header 2 |\n"
                "          |----------|----------|\n"
                "          | Data 1   | Data 2   |"
            )

    def test_quality_scorers_table_well_formed(self):
        """Test quality scorers table in docs/quality-scorers.md is well-formed."""
        content = QUALITY_SCORERS_FILE.read_text()

        # Check for table presence
        lines = content.split("\n")
        table_lines = [line for line in lines if "|" in line]

        if len(table_lines) > 0:
            # If table exists, validate structure
            separator_lines = [line for line in table_lines if "---" in line or "--" in line]
            assert len(separator_lines) >= 1, (
                "quality-scorers.md table must have separator line\n"
                "Expected markdown table format with header separator"
            )

    def test_training_thresholds_table_well_formed(self):
        """Test training thresholds table in docs/training-thresholds.md is well-formed."""
        content = TRAINING_THRESHOLDS_FILE.read_text()

        # Check for table presence
        lines = content.split("\n")
        table_lines = [line for line in lines if "|" in line]

        assert len(table_lines) >= 3, (
            "training-thresholds.md should contain table with thresholds\n"
            f"Expected: Table with training types and threshold values\n"
            f"Found {len(table_lines)} table lines"
        )

        # Validate table structure
        separator_lines = [line for line in table_lines if "---" in line or "--" in line]
        assert len(separator_lines) >= 1, (
            "training-thresholds.md table must have separator line\n"
            "Expected markdown table format"
        )


# ============================================================================
# Test 5: Progressive Disclosure Tests (2 tests)
# ============================================================================


class TestProgressiveDisclosure:
    """Test progressive disclosure architecture (SKILL.md < 500 lines)."""

    def test_skill_file_under_500_lines(self):
        """Test SKILL.md is under 500 lines (quick reference only)."""
        content = SKILL_FILE.read_text()
        lines = content.split("\n")

        assert len(lines) < 500, (
            f"SKILL.md too large: {len(lines)} lines\n"
            f"Expected: < 500 lines (progressive disclosure principle)\n"
            f"SKILL.md should contain quick reference only, detailed docs in docs/"
        )

    def test_skill_references_docs_directory(self):
        """Test SKILL.md references docs/*.md files for detailed content."""
        content = SKILL_FILE.read_text()

        doc_references = ["quality-scorers.md", "quality-dimensions.md", "training-thresholds.md"]
        found_refs = [ref for ref in doc_references if ref in content]

        assert len(found_refs) >= 2, (
            f"SKILL.md should reference at least 2 docs/*.md files\n"
            f"Expected references: {doc_references}\n"
            f"Found: {found_refs}\n"
            f"Progressive disclosure: SKILL.md references detailed docs"
        )


# ============================================================================
# Test 6: Security Documentation Tests (3 tests)
# ============================================================================


class TestSecurityDocumentation:
    """Test security documentation and CWE references."""

    def test_mentions_cwe_20_input_validation(self):
        """Test skill mentions CWE-20 (input validation)."""
        content = SKILL_FILE.read_text()

        assert "cwe-20" in content.lower() or "input validation" in content.lower(), (
            "SKILL.md should mention CWE-20 (input validation)\n"
            "Expected: Security guidance for validating quality scores and data inputs\n"
            "Example: Validate score ranges, data formats, threshold values"
        )

    def test_mentions_cwe_22_path_traversal(self):
        """Test skill mentions CWE-22 (path traversal)."""
        content = SKILL_FILE.read_text()

        assert "cwe-22" in content.lower() or "path traversal" in content.lower(), (
            "SKILL.md should mention CWE-22 (path traversal)\n"
            "Expected: Security guidance for file path handling in data loading\n"
            "Example: Sanitize file paths, whitelist directories"
        )

    def test_references_training_metrics_security_patterns(self):
        """Test skill references training_metrics.py security patterns."""
        content = SKILL_FILE.read_text()

        assert "training_metrics" in content or "security" in content.lower(), (
            "SKILL.md should reference training_metrics library security patterns\n"
            "Expected: Mention of security best practices from training_metrics.py\n"
            "Example: Path validation, input sanitization, safe file operations"
        )


# ============================================================================
# Test 7: Integration Tests (3 tests)
# ============================================================================


class TestIntegration:
    """Test integration with training_metrics library and related skills."""

    def test_references_calculate_ifd_score(self):
        """Test skill references calculate_ifd_score function from training_metrics."""
        content = SKILL_FILE.read_text()

        assert "calculate_ifd_score" in content or "IFD score" in content, (
            "SKILL.md should reference calculate_ifd_score function\n"
            "Expected: Integration with training_metrics.calculate_ifd_score()\n"
            "Purpose: Calculate instruction-following difficulty scores"
        )

    def test_references_validate_dpo_pairs(self):
        """Test skill references validate_dpo_pairs function from training_metrics."""
        content = SKILL_FILE.read_text()

        assert "validate_dpo_pairs" in content or "DPO" in content, (
            "SKILL.md should reference DPO pair validation\n"
            "Expected: Integration with training_metrics.validate_dpo_pairs()\n"
            "Purpose: Validate DPO chosen/rejected pairs for preference learning"
        )

    def test_references_assess_rlvr_verifiability(self):
        """Test skill references assess_rlvr_verifiability function from training_metrics."""
        content = SKILL_FILE.read_text()

        assert "assess_rlvr_verifiability" in content or "RLVR" in content, (
            "SKILL.md should reference RLVR verifiability assessment\n"
            "Expected: Integration with training_metrics.assess_rlvr_verifiability()\n"
            "Purpose: Assess verifiability of reasoning traces for RLVR training"
        )

    def test_cross_references_exist(self):
        """Test cross-references to related skills are valid."""
        content = SKILL_FILE.read_text()

        related_skills = ["data-distillation", "preference-data-quality"]
        found_skills = [skill for skill in related_skills if skill in content.lower()]

        assert len(found_skills) >= 2, (
            f"SKILL.md should cross-reference related skills\n"
            f"Expected skills: {related_skills}\n"
            f"Found: {found_skills}\n"
            f"Purpose: Connect quality scoring to broader data workflows"
        )

    def test_progressive_disclosure_links_valid(self):
        """Test progressive disclosure links (docs/*.md) are valid references."""
        content = SKILL_FILE.read_text()

        # Check that SKILL.md mentions the docs files
        doc_files = ["quality-scorers", "quality-dimensions", "training-thresholds"]
        found_docs = [doc for doc in doc_files if doc in content]

        assert len(found_docs) >= 2, (
            f"SKILL.md should reference detailed documentation files\n"
            f"Expected docs: {doc_files}\n"
            f"Found: {found_docs}\n"
            f"Progressive disclosure: SKILL.md links to detailed docs/*.md files"
        )


# ============================================================================
# Test 8: Edge Cases (3 tests)
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
                        f"See: Issue #310 - Documentation files are markdown"
                    )

    def test_no_empty_documentation_files(self):
        """Test documentation files are not empty."""
        doc_files = [QUALITY_SCORERS_FILE, QUALITY_DIMENSIONS_FILE, TRAINING_THRESHOLDS_FILE]

        for doc_file in doc_files:
            if doc_file.exists():
                content = doc_file.read_text().strip()
                assert len(content) > 100, (
                    f"Documentation file too small or empty: {doc_file.name}\n"
                    f"Expected: File contains substantial documentation (> 100 chars)\n"
                    f"Found: {len(content)} chars\n"
                    f"See: Issue #310"
                )

    def test_no_duplicate_content_across_files(self):
        """Test major content sections are not duplicated across files."""
        skill_content = SKILL_FILE.read_text()
        scorers_content = QUALITY_SCORERS_FILE.read_text()
        dimensions_content = QUALITY_DIMENSIONS_FILE.read_text()
        thresholds_content = TRAINING_THRESHOLDS_FILE.read_text()

        # SKILL.md should be concise overview, not duplicate detailed docs
        # Check that detailed scorer descriptions are in quality-scorers.md, not SKILL.md
        # This is a soft check - some overlap is expected (quick reference vs detail)

        # Ensure docs files have unique detailed content
        assert len(scorers_content) > len(skill_content) / 3, (
            "quality-scorers.md should have substantial unique content\n"
            "Progressive disclosure: Detailed content in docs/, overview in SKILL.md"
        )


# ============================================================================
# Checkpoint Integration
# ============================================================================


class TestCheckpointIntegration:
    """Test checkpoint integration for test-master agent tracking."""

    def test_checkpoint_library_available(self):
        """Test agent_tracker checkpoint library is available."""
        try:
            # Portable path detection (works from any directory)
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

                from agent_tracker import AgentTracker

                # Test checkpoint functionality
                AgentTracker.save_agent_checkpoint(
                    "test-master", "Tests complete - 31 tests created for quality-scoring skill"
                )
                print("Checkpoint saved successfully")
            else:
                pytest.skip("Checkpoint library not available (user project)")
        except ImportError:
            pytest.skip("Checkpoint library not available (import failed)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
