#!/usr/bin/env python3
"""
TDD Tests for realign-dpo-workflow Skill (FAILING - Red Phase)

This module contains FAILING tests for the realign-dpo-workflow skill that will
provide comprehensive guidance for DPO (Direct Preference Optimization) model
realignment workflows.

Skill Requirements:
1. YAML frontmatter with name, type, description, keywords, auto_activate
2. Progressive disclosure: SKILL.md <500 lines with links to docs/*.md
3. 7-stage DPO workflow documentation:
   - SFT Preparation
   - Preference Data Generation
   - Model Initialization
   - Preference Modeling
   - DPO Optimization
   - Iterative Training
   - Evaluation & Monitoring
4. Integration with preference-data-quality skill (cross-references)
5. Quality thresholds: gap ≥0.15, KL ≤0.1, pairs ≥1000, decontamination ≥0.9
6. Templates for checklists and configuration
7. Documentation files in docs/ subdirectory (10 files)
8. Performance optimization documentation (hardware selection, batch sizing, RDMA)
9. Total: 13 files (~5,100 lines)

Test Coverage Target: 100% of skill structure, content, and integration

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe skill requirements and structure
- Tests should FAIL until skill files are implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2026-01-28
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pytest
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

SKILL_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "plugins"
    / "autonomous-dev"
    / "skills"
    / "realign-dpo-workflow"
)
SKILL_FILE = SKILL_DIR / "SKILL.md"
WORKFLOW_FILE = SKILL_DIR / "workflow.md"
TEMPLATES_FILE = SKILL_DIR / "templates.md"
DOCS_DIR = SKILL_DIR / "docs"

# Expected documentation files
EXPECTED_DOC_FILES = [
    "sft-preparation.md",
    "preference-data-generation.md",
    "model-initialization.md",
    "preference-modeling.md",
    "dpo-optimization.md",
    "iterative-training.md",
    "evaluation-monitoring.md",
    "quality-thresholds.md",
    "capability-assessment.md",
    "performance-optimization.md",
]

# Quality thresholds that must be documented consistently
EXPECTED_THRESHOLDS = {
    "preference_gap": 0.15,
    "kl_divergence": 0.1,
    "min_pairs": 1000,
    "decontamination": 0.9,
}


def parse_frontmatter(content: str) -> Tuple[Optional[Dict], str]:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return None, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, content

    try:
        frontmatter = yaml.safe_load(parts[1])
        body = parts[2]
        return frontmatter, body
    except yaml.YAMLError:
        return None, content


def count_lines(file_path: Path) -> int:
    """Count total lines in a file."""
    if not file_path.exists():
        return 0
    with open(file_path, "r", encoding="utf-8") as f:
        return len(f.readlines())


def extract_markdown_links(content: str) -> List[str]:
    """Extract all markdown links from content."""
    # Match [text](path) pattern
    pattern = r"\[([^\]]+)\]\(([^)]+)\)"
    return [match[1] for match in re.findall(pattern, content)]


def extract_stages_from_content(content: str) -> Set[str]:
    """Extract DPO workflow stages mentioned in content."""
    stages = set()
    keywords = [
        "sft preparation",
        "preference data",
        "model init",
        "preference modeling",
        "dpo optimization",
        "iterative training",
        "evaluation",
    ]
    content_lower = content.lower()
    for keyword in keywords:
        if keyword in content_lower:
            stages.add(keyword)
    return stages


class TestSkillStructure:
    """Test realign-dpo-workflow skill file structure and metadata."""

    def test_skill_directory_exists(self):
        """Test skill directory exists."""
        assert SKILL_DIR.exists(), (
            f"Skill directory not found: {SKILL_DIR}\n"
            f"Expected: Create plugins/autonomous-dev/skills/realign-dpo-workflow/\n"
            f"See: Implementation plan for directory structure"
        )

    def test_skill_file_exists(self):
        """Test SKILL.md file exists in realign-dpo-workflow/ directory."""
        assert SKILL_FILE.exists(), (
            f"Skill file not found: {SKILL_FILE}\n"
            f"Expected: Create realign-dpo-workflow/SKILL.md\n"
            f"See: Implementation plan for file structure"
        )

    def test_skill_under_500_lines(self):
        """Test SKILL.md is under 500 lines (progressive disclosure)."""
        line_count = count_lines(SKILL_FILE)
        assert line_count <= 500, (
            f"SKILL.md has {line_count} lines (max 500 for progressive disclosure)\n"
            f"Expected: High-level overview with links to docs/*.md\n"
            f"Move detailed content to docs/ subdirectory"
        )

    def test_skill_has_valid_yaml_frontmatter(self):
        """Test SKILL.md has valid YAML frontmatter with required fields."""
        content = SKILL_FILE.read_text()

        # Check frontmatter exists
        assert content.startswith("---"), (
            "SKILL.md must start with YAML frontmatter (---)\n"
            "Expected format:\n"
            "---\n"
            "name: realign-dpo-workflow\n"
            "type: knowledge\n"
            "...\n"
        )

        # Extract and validate frontmatter
        frontmatter, _ = parse_frontmatter(content)
        assert frontmatter is not None, "Failed to parse YAML frontmatter"

        # Required fields
        required_fields = {
            "name": "realign-dpo-workflow",
            "type": "knowledge",
            "description": str,
            "keywords": list,
            "auto_activate": True,
        }

        for field, expected_value in required_fields.items():
            assert field in frontmatter, f"Missing required field: {field}"

            if expected_value is not str and expected_value is not list:
                actual = frontmatter[field]
                assert actual == expected_value, (
                    f"Field '{field}' mismatch\n"
                    f"Expected: {expected_value}\n"
                    f"Got: {actual}"
                )

    def test_skill_keywords_cover_dpo_terms(self):
        """Test skill keywords include DPO-related terms for auto-activation."""
        content = SKILL_FILE.read_text()
        frontmatter, _ = parse_frontmatter(content)

        assert frontmatter is not None, "No frontmatter found"
        keywords = frontmatter.get("keywords", [])

        # Expected DPO-related keywords
        expected_terms = {"dpo", "preference", "realign", "rlhf"}
        keywords_lower = {str(k).lower() for k in keywords}

        missing = expected_terms - keywords_lower
        assert not missing, (
            f"Missing DPO-related keywords: {missing}\n"
            f"Current keywords: {keywords}\n"
            f"Add keywords for reliable auto-activation"
        )

    def test_workflow_file_exists(self):
        """Test workflow.md exists with 7-stage pipeline documentation."""
        assert WORKFLOW_FILE.exists(), (
            f"Workflow file not found: {WORKFLOW_FILE}\n"
            f"Expected: Create realign-dpo-workflow/workflow.md\n"
            f"Should document 7 DPO workflow stages"
        )

    def test_templates_file_exists(self):
        """Test templates.md exists with checklists and configurations."""
        assert TEMPLATES_FILE.exists(), (
            f"Templates file not found: {TEMPLATES_FILE}\n"
            f"Expected: Create realign-dpo-workflow/templates.md\n"
            f"Should contain workflow checklists and config templates"
        )

    def test_docs_directory_exists(self):
        """Test docs/ subdirectory exists for progressive disclosure."""
        assert DOCS_DIR.exists(), (
            f"Docs directory not found: {DOCS_DIR}\n"
            f"Expected: Create realign-dpo-workflow/docs/\n"
            f"Required for progressive disclosure (SKILL.md <500 lines)"
        )

    def test_all_expected_doc_files_exist(self):
        """Test all 9 expected documentation files exist in docs/."""
        missing_files = []
        for filename in EXPECTED_DOC_FILES:
            doc_file = DOCS_DIR / filename
            if not doc_file.exists():
                missing_files.append(filename)

        assert not missing_files, (
            f"Missing documentation files in docs/:\n"
            f"{chr(10).join(f'  - {f}' for f in missing_files)}\n"
            f"Expected 9 files for 7 stages + quality thresholds + capability assessment"
        )


class TestSkillContent:
    """Test realign-dpo-workflow skill content and documentation."""

    def test_skill_documents_all_7_stages(self):
        """Test SKILL.md references all 7 DPO workflow stages."""
        content = SKILL_FILE.read_text().lower()

        # All 7 stages must be mentioned
        required_stages = [
            "sft preparation",
            "preference data",
            "model init",
            "preference modeling",
            "optimization",
            "iterative training",
            "evaluation",
        ]

        missing_stages = []
        for stage in required_stages:
            if stage not in content:
                missing_stages.append(stage)

        assert not missing_stages, (
            f"SKILL.md missing workflow stages:\n"
            f"{chr(10).join(f'  - {s}' for s in missing_stages)}\n"
            f"All 7 stages must be documented or referenced"
        )

    def test_skill_references_quality_thresholds(self):
        """Test SKILL.md references quality thresholds."""
        content = SKILL_FILE.read_text()

        # Should reference quality thresholds
        threshold_terms = ["threshold", "quality", "metric"]
        has_threshold_ref = any(term in content.lower() for term in threshold_terms)

        assert has_threshold_ref, (
            "SKILL.md must reference quality thresholds\n"
            "Expected: Link to docs/quality-thresholds.md or inline summary\n"
            "Thresholds: gap ≥0.15, KL ≤0.1, pairs ≥1000, decontamination ≥0.9"
        )

    def test_workflow_file_has_stage_sections(self):
        """Test workflow.md has sections for all 7 stages."""
        content = WORKFLOW_FILE.read_text()

        # Check for stage headers (## or ###)
        stage_keywords = [
            "sft",
            "preference data",
            "model init",
            "preference modeling",
            "optimization",
            "iterative",
            "evaluation",
        ]

        content_lower = content.lower()
        missing = [kw for kw in stage_keywords if kw not in content_lower]

        assert not missing, (
            f"workflow.md missing stage sections:\n"
            f"{chr(10).join(f'  - {s}' for s in missing)}\n"
            f"All 7 stages must have dedicated sections"
        )

    def test_templates_file_has_checklists(self):
        """Test templates.md contains actionable checklists."""
        content = TEMPLATES_FILE.read_text()

        # Should have checkbox items (- [ ] or - [x])
        has_checkboxes = re.search(r"- \[[ x]\]", content) is not None

        assert has_checkboxes, (
            "templates.md must contain actionable checklists\n"
            "Expected: Markdown checkboxes (- [ ] Task)\n"
            "Provide workflow checklists for practitioners"
        )

    def test_quality_thresholds_documented(self):
        """Test quality thresholds are documented with specific values."""
        threshold_file = DOCS_DIR / "quality-thresholds.md"
        content = threshold_file.read_text()

        # Check for threshold values
        expected_values = ["0.15", "0.1", "1000", "0.9"]
        missing = [v for v in expected_values if v not in content]

        assert not missing, (
            f"quality-thresholds.md missing expected values:\n"
            f"{chr(10).join(f'  - {v}' for v in missing)}\n"
            f"Expected: gap ≥0.15, KL ≤0.1, pairs ≥1000, decontamination ≥0.9"
        )

    def test_capability_assessment_documented(self):
        """Test capability assessment is documented for regression detection."""
        capability_file = DOCS_DIR / "capability-assessment.md"
        content = capability_file.read_text().lower()

        # Should discuss capability regression
        regression_terms = ["regression", "capability", "degradation", "performance"]
        has_regression_ref = any(term in content for term in regression_terms)

        assert has_regression_ref, (
            "capability-assessment.md must discuss capability regression detection\n"
            "Expected: Guidance on preventing capability degradation during DPO"
        )


class TestSkillIntegration:
    """Test realign-dpo-workflow skill integration with other components."""

    def test_cross_references_preference_data_quality_skill(self):
        """Test skill cross-references preference-data-quality skill."""
        content = SKILL_FILE.read_text()

        # Should reference preference-data-quality skill
        has_reference = "preference-data-quality" in content.lower()

        assert has_reference, (
            "SKILL.md must cross-reference preference-data-quality skill\n"
            "Expected: Link to related skill for DPO metrics\n"
            "Integration: Use preference-data-quality for quality validation"
        )

    def test_references_training_metrics_library(self):
        """Test skill references training_metrics.py library."""
        # Check SKILL.md or docs files
        all_content = SKILL_FILE.read_text()
        for doc_file in EXPECTED_DOC_FILES:
            doc_path = DOCS_DIR / doc_file
            if doc_path.exists():
                all_content += doc_path.read_text()

        has_training_metrics = "training_metrics" in all_content.lower()

        assert has_training_metrics, (
            "Skill must reference training_metrics.py library\n"
            "Expected: Cross-reference to training metrics functions\n"
            "Integration: Use training_metrics for DPO metric calculation"
        )

    def test_skill_links_to_docs_are_valid(self):
        """Test all docs/ links in SKILL.md point to existing files."""
        content = SKILL_FILE.read_text()
        links = extract_markdown_links(content)

        # Filter to docs/ links
        docs_links = [link for link in links if link.startswith("docs/")]

        broken_links = []
        for link in docs_links:
            # Handle anchor links
            file_path = link.split("#")[0]
            full_path = SKILL_DIR / file_path

            if not full_path.exists():
                broken_links.append(link)

        assert not broken_links, (
            f"SKILL.md has broken docs/ links:\n"
            f"{chr(10).join(f'  - {link}' for link in broken_links)}\n"
            f"Create missing files or fix link paths"
        )

    def test_workflow_file_links_are_valid(self):
        """Test all links in workflow.md point to existing files."""
        content = WORKFLOW_FILE.read_text()
        links = extract_markdown_links(content)

        # Filter to relative links (docs/ or same directory)
        relative_links = [
            link for link in links if not link.startswith(("http://", "https://"))
        ]

        broken_links = []
        for link in relative_links:
            # Handle anchor links
            file_path = link.split("#")[0]
            if not file_path:  # Anchor-only link
                continue

            # Resolve relative to workflow.md location
            full_path = SKILL_DIR / file_path
            if not full_path.exists():
                broken_links.append(link)

        assert not broken_links, (
            f"workflow.md has broken links:\n"
            f"{chr(10).join(f'  - {link}' for link in broken_links)}\n"
            f"Create missing files or fix link paths"
        )


class TestSkillConsistency:
    """Test consistency across skill files."""

    def test_threshold_values_consistent(self):
        """Test quality threshold values are consistent across all files."""
        # Collect all content
        all_files = [SKILL_FILE, WORKFLOW_FILE, TEMPLATES_FILE]
        all_files.extend([DOCS_DIR / f for f in EXPECTED_DOC_FILES if (DOCS_DIR / f).exists()])

        threshold_mentions = {}
        for file_path in all_files:
            if not file_path.exists():
                continue

            content = file_path.read_text()

            # Extract threshold values with regex
            # Look for patterns like "≥0.15", ">=0.15", "≥ 0.15"
            gap_matches = re.findall(r"[≥>=]\s*(0\.1[0-9])", content)
            kl_matches = re.findall(r"[≤<=]\s*(0\.1[0-9]?)", content)
            pairs_matches = re.findall(r"[≥>=]\s*(\d{3,4})\s*(?:pairs?|examples?)", content.lower())
            decon_matches = re.findall(r"[≥>=]\s*(0\.9[0-9]?)", content)

            if gap_matches or kl_matches or pairs_matches or decon_matches:
                threshold_mentions[file_path.name] = {
                    "gap": gap_matches,
                    "kl": kl_matches,
                    "pairs": pairs_matches,
                    "decontamination": decon_matches,
                }

        # Verify consistency (at least some thresholds found and consistent)
        if threshold_mentions:
            # Check for common values across files
            all_gaps = [v for mentions in threshold_mentions.values() for v in mentions.get("gap", [])]
            all_kls = [v for mentions in threshold_mentions.values() for v in mentions.get("kl", [])]

            if all_gaps:
                unique_gaps = set(all_gaps)
                assert len(unique_gaps) == 1, (
                    f"Inconsistent preference gap thresholds: {unique_gaps}\n"
                    f"Expected: Single consistent value (0.15)\n"
                    f"Found in: {list(threshold_mentions.keys())}"
                )

            if all_kls:
                unique_kls = set(all_kls)
                assert len(unique_kls) == 1, (
                    f"Inconsistent KL divergence thresholds: {unique_kls}\n"
                    f"Expected: Single consistent value (0.1)\n"
                    f"Found in: {list(threshold_mentions.keys())}"
                )

    def test_terminology_consistent(self):
        """Test DPO terminology is consistent across files."""
        all_files = [SKILL_FILE, WORKFLOW_FILE]

        # Collect all content
        all_content = ""
        for file_path in all_files:
            if file_path.exists():
                all_content += file_path.read_text().lower()

        # Check for consistent terminology
        # Prefer "DPO" over "direct preference optimization" after first mention
        dpo_count = all_content.count("dpo")
        full_term_count = all_content.count("direct preference optimization")

        # If full term used, should define it once then use acronym
        if full_term_count > 0:
            assert dpo_count >= full_term_count, (
                "Use 'DPO' acronym after first definition\n"
                f"Found: {full_term_count} full term uses, {dpo_count} acronym uses\n"
                "Expected: Define once, then use acronym for brevity"
            )


class TestEdgeCases:
    """Test edge cases and error handling in skill documentation."""

    def test_handles_capability_regression_scenario(self):
        """Test skill provides guidance for capability regression detection."""
        capability_file = DOCS_DIR / "capability-assessment.md"
        content = capability_file.read_text().lower()

        # Should discuss how to detect and handle capability loss
        detection_terms = ["detect", "identify", "measure", "monitor"]
        has_detection = any(term in content for term in detection_terms)

        assert has_detection, (
            "capability-assessment.md must provide regression detection guidance\n"
            "Expected: Methods to identify capability degradation during DPO"
        )

    def test_handles_preference_conflict_scenario(self):
        """Test skill addresses conflicting preferences in data."""
        preference_file = DOCS_DIR / "preference-data-generation.md"
        content = preference_file.read_text().lower()

        # Should discuss handling conflicting or inconsistent preferences
        conflict_terms = ["conflict", "inconsistent", "contradict", "disagree"]
        has_conflict_guidance = any(term in content for term in conflict_terms)

        assert has_conflict_guidance, (
            "preference-data-generation.md must address conflicting preferences\n"
            "Expected: Guidance on handling inconsistent preference pairs"
        )

    def test_handles_insufficient_data_scenario(self):
        """Test skill provides guidance for insufficient preference data."""
        preference_file = DOCS_DIR / "preference-data-generation.md"
        threshold_file = DOCS_DIR / "quality-thresholds.md"

        # Check both files for insufficient data handling
        content = ""
        if preference_file.exists():
            content += preference_file.read_text().lower()
        if threshold_file.exists():
            content += threshold_file.read_text().lower()

        # Should discuss minimum data requirements
        data_terms = ["minimum", "insufficient", "not enough", "at least"]
        has_data_guidance = any(term in content for term in data_terms)

        assert has_data_guidance, (
            "Skill must provide guidance for insufficient preference data\n"
            "Expected: Minimum data requirements and handling strategies"
        )

    def test_templates_provide_configuration_examples(self):
        """Test templates.md provides valid configuration examples."""
        content = TEMPLATES_FILE.read_text()

        # Should contain code blocks with configuration
        has_code_blocks = "```" in content

        assert has_code_blocks, (
            "templates.md must provide configuration examples\n"
            "Expected: Code blocks with sample configurations\n"
            "Use ```yaml or ```python for config templates"
        )


class TestDocumentationQuality:
    """Test documentation quality and completeness."""

    def test_each_stage_doc_has_overview(self):
        """Test each stage documentation file has an overview section."""
        stage_files = [
            "sft-preparation.md",
            "preference-data-generation.md",
            "model-initialization.md",
            "preference-modeling.md",
            "dpo-optimization.md",
            "iterative-training.md",
            "evaluation-monitoring.md",
        ]

        missing_overview = []
        for filename in stage_files:
            file_path = DOCS_DIR / filename
            if not file_path.exists():
                continue

            content = file_path.read_text()

            # Should have overview/introduction section
            has_overview = any(
                term in content.lower()
                for term in ["overview", "introduction", "purpose", "goal"]
            )

            if not has_overview:
                missing_overview.append(filename)

        assert not missing_overview, (
            f"Stage docs missing overview sections:\n"
            f"{chr(10).join(f'  - {f}' for f in missing_overview)}\n"
            f"Each stage should explain its purpose and goals"
        )

    def test_skill_has_progressive_disclosure_statement(self):
        """Test SKILL.md includes progressive disclosure statement."""
        content = SKILL_FILE.read_text().lower()

        # Should mention progressive disclosure or point to detailed docs
        disclosure_terms = [
            "progressive disclosure",
            "see docs/",
            "detailed documentation",
            "for details see",
        ]
        has_disclosure = any(term in content for term in disclosure_terms)

        assert has_disclosure, (
            "SKILL.md must include progressive disclosure statement\n"
            "Expected: Direct users to docs/*.md for detailed information\n"
            "Example: 'See docs/*.md for detailed stage documentation'"
        )

    def test_file_count_matches_specification(self):
        """Test total file count matches specification (12 files)."""
        # Count all files in skill directory
        all_files = []
        all_files.append(SKILL_FILE)
        all_files.append(WORKFLOW_FILE)
        all_files.append(TEMPLATES_FILE)

        # Count docs/ files
        if DOCS_DIR.exists():
            doc_files = list(DOCS_DIR.glob("*.md"))
            all_files.extend(doc_files)

        existing_files = [f for f in all_files if f.exists()]

        assert len(existing_files) == 13, (
            f"Expected 13 total files, found {len(existing_files)}\n"
            f"Specification: 1 SKILL.md + 1 workflow.md + 1 templates.md + 10 docs/*.md\n"
            f"Existing files:\n"
            f"{chr(10).join(f'  - {f.name}' for f in existing_files)}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
