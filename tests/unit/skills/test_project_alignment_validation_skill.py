#!/usr/bin/env python3
"""
TDD Tests for project-alignment-validation Skill (FAILING - Red Phase)

This module contains FAILING tests for the project-alignment-validation skill that will
extract PROJECT.md alignment validation patterns from 12 files (Issue #76 Phase 8.7).

Skill Requirements:
1. YAML frontmatter with name, type, description, keywords, auto_activate
2. Progressive disclosure architecture (metadata in frontmatter, content loads on-demand)
3. Standardized alignment validation patterns:
   - GOALS/SCOPE/CONSTRAINTS/ARCHITECTURE validation
   - Semantic validation approach (intent > literal text)
   - Gap assessment methodology
   - Alignment checklist templates
   - Misalignment detection patterns
4. Documentation files (4):
   - alignment-checklist.md: Standard validation steps
   - semantic-validation-approach.md: Semantic vs literal validation
   - gap-assessment-methodology.md: Identify and prioritize gaps
   - conflict-resolution-patterns.md: Resolve alignment conflicts
5. Template files (3):
   - alignment-report-template.md: Standard report structure
   - gap-assessment-template.md: Gap documentation template
   - conflict-resolution-template.md: Conflict resolution workflow
6. Example files (3):
   - alignment-scenarios.md: Common scenarios and fixes
   - misalignment-examples.md: Real-world misalignment cases
   - project-md-structure-example.md: Well-structured PROJECT.md
7. Token reduction: 12 files × ~100 tokens = ~1,200 tokens (2-4% reduction)

Files to Update:
- Agents (3): alignment-validator, alignment-analyzer, project-progress-tracker
- Hooks (5): validate_project_alignment.py, auto_update_project_progress.py,
             enforce_pipeline_complete.py, detect_feature_request.py,
             validate_documentation_alignment.py
- Libraries (4): alignment_assessor.py, project_md_updater.py,
                 brownfield_retrofit.py, migration_planner.py

Test Coverage Target: 18 tests (8 unit + 7 integration + 3 token validation)

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe skill requirements and file integration
- Tests should FAIL until skill file and file updates are implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-16
Issue: #76 Phase 8.7
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

# Skill paths
SKILL_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "skills" / "project-alignment-validation"
SKILL_FILE = SKILL_DIR / "SKILL.md"
DOCS_DIR = SKILL_DIR / "docs"
TEMPLATES_DIR = SKILL_DIR / "templates"
EXAMPLES_DIR = SKILL_DIR / "examples"

# Documentation files
ALIGNMENT_CHECKLIST_DOC = DOCS_DIR / "alignment-checklist.md"
SEMANTIC_VALIDATION_DOC = DOCS_DIR / "semantic-validation-approach.md"
GAP_ASSESSMENT_DOC = DOCS_DIR / "gap-assessment-methodology.md"
CONFLICT_RESOLUTION_DOC = DOCS_DIR / "conflict-resolution-patterns.md"

# Template files
ALIGNMENT_REPORT_TEMPLATE = TEMPLATES_DIR / "alignment-report-template.md"
GAP_ASSESSMENT_TEMPLATE = TEMPLATES_DIR / "gap-assessment-template.md"
CONFLICT_RESOLUTION_TEMPLATE = TEMPLATES_DIR / "conflict-resolution-template.md"

# Example files
ALIGNMENT_SCENARIOS_EXAMPLE = EXAMPLES_DIR / "alignment-scenarios.md"
MISALIGNMENT_EXAMPLES = EXAMPLES_DIR / "misalignment-examples.md"
PROJECT_MD_STRUCTURE_EXAMPLE = EXAMPLES_DIR / "project-md-structure-example.md"

# Agent paths
AGENTS_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "agents"

# Hook paths
HOOKS_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "hooks"

# Library paths
LIB_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib"

# Files that use project alignment validation
ALIGNMENT_AGENTS = [
    "alignment-validator",
    "alignment-analyzer",
    "project-progress-tracker"
]

ALIGNMENT_HOOKS = [
    "validate_project_alignment.py",
    "auto_update_project_progress.py",
    "enforce_pipeline_complete.py",
    "detect_feature_request.py",
    "validate_documentation_alignment.py"
]

ALIGNMENT_LIBRARIES = [
    "alignment_assessor.py",
    "project_md_updater.py",
    "brownfield_retrofit.py",
    "migration_planner.py"
]


# ==============================================================================
# Test Suite 1: Skill File Structure (8 unit tests)
# ==============================================================================


class TestProjectAlignmentValidationSkillStructure:
    """Test project-alignment-validation skill file structure and metadata."""

    def test_skill_directory_exists(self):
        """Test skills/project-alignment-validation/ directory exists."""
        assert SKILL_DIR.exists(), (
            f"Skill directory not found: {SKILL_DIR}\n"
            f"Expected: Create skills/project-alignment-validation/ directory\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_skill_file_exists(self):
        """Test SKILL.md file exists in project-alignment-validation directory."""
        assert SKILL_FILE.exists(), (
            f"Skill file not found: {SKILL_FILE}\n"
            f"Expected: Create skills/project-alignment-validation/SKILL.md\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_skill_has_valid_yaml_frontmatter(self):
        """Test skill file has valid YAML frontmatter with required fields."""
        content = SKILL_FILE.read_text()

        # Check frontmatter exists
        assert content.startswith("---\n"), (
            "Skill file must start with YAML frontmatter (---)\n"
            "Expected format:\n"
            "---\n"
            "name: project-alignment-validation\n"
            "type: knowledge\n"
            "...\n"
        )

        # Extract frontmatter
        parts = content.split("---\n", 2)
        assert len(parts) >= 3, "Skill file must have closing --- for frontmatter"

        frontmatter = yaml.safe_load(parts[1])

        # Validate required fields
        assert frontmatter.get("name") == "project-alignment-validation", (
            "Skill name must be 'project-alignment-validation'\n"
            f"Got: {frontmatter.get('name')}"
        )

        assert frontmatter.get("type") == "knowledge", (
            "Skill type must be 'knowledge'\n"
            f"Got: {frontmatter.get('type')}"
        )

        assert "description" in frontmatter, "Missing description field"
        assert "keywords" in frontmatter, "Missing keywords field"
        assert "auto_activate" in frontmatter, "Missing auto_activate field"

    def test_skill_keywords_comprehensive(self):
        """Test skill keywords include alignment validation terms."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        keywords = frontmatter.get("keywords", [])
        if isinstance(keywords, list):
            keywords = " ".join(keywords)

        # Required keywords for skill activation
        expected_keywords = [
            "alignment",
            "PROJECT.md",
            "validation",
            "GOALS",
            "SCOPE",
            "CONSTRAINTS",
            "semantic",
            "gap"
        ]

        found_keywords = [k for k in expected_keywords if k in keywords]

        assert len(found_keywords) >= 6, (
            f"Missing alignment validation keywords in SKILL.md\n"
            f"Expected: At least 6 of {expected_keywords}\n"
            f"Found: {found_keywords}\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_docs_directory_exists_with_4_files(self):
        """Test docs/ directory exists with 4 documentation files."""
        assert DOCS_DIR.exists(), (
            f"Documentation directory not found: {DOCS_DIR}\n"
            f"Expected: Create skills/project-alignment-validation/docs/\n"
            f"See: Issue #76 Phase 8.7"
        )

        required_docs = [
            ALIGNMENT_CHECKLIST_DOC,
            SEMANTIC_VALIDATION_DOC,
            GAP_ASSESSMENT_DOC,
            CONFLICT_RESOLUTION_DOC
        ]

        for doc_file in required_docs:
            assert doc_file.exists(), (
                f"Documentation file not found: {doc_file}\n"
                f"Expected: Create all 4 documentation files\n"
                f"See: Issue #76 Phase 8.7"
            )

    def test_templates_directory_exists_with_3_files(self):
        """Test templates/ directory exists with 3 template files."""
        assert TEMPLATES_DIR.exists(), (
            f"Templates directory not found: {TEMPLATES_DIR}\n"
            f"Expected: Create skills/project-alignment-validation/templates/\n"
            f"See: Issue #76 Phase 8.7"
        )

        required_templates = [
            ALIGNMENT_REPORT_TEMPLATE,
            GAP_ASSESSMENT_TEMPLATE,
            CONFLICT_RESOLUTION_TEMPLATE
        ]

        for template_file in required_templates:
            assert template_file.exists(), (
                f"Template file not found: {template_file}\n"
                f"Expected: Create all 3 template files\n"
                f"See: Issue #76 Phase 8.7"
            )

    def test_examples_directory_exists_with_3_files(self):
        """Test examples/ directory exists with 3 example files."""
        assert EXAMPLES_DIR.exists(), (
            f"Examples directory not found: {EXAMPLES_DIR}\n"
            f"Expected: Create skills/project-alignment-validation/examples/\n"
            f"See: Issue #76 Phase 8.7"
        )

        required_examples = [
            ALIGNMENT_SCENARIOS_EXAMPLE,
            MISALIGNMENT_EXAMPLES,
            PROJECT_MD_STRUCTURE_EXAMPLE
        ]

        for example_file in required_examples:
            assert example_file.exists(), (
                f"Example file not found: {example_file}\n"
                f"Expected: Create all 3 example files\n"
                f"See: Issue #76 Phase 8.7"
            )

    def test_skill_content_defines_semantic_validation(self):
        """Test skill content defines semantic validation approach."""
        content = SKILL_FILE.read_text()

        # Semantic validation concepts
        validation_concepts = [
            "semantic",
            "intent",
            "purpose",
            "literal"
        ]

        found = [c for c in validation_concepts if c.lower() in content.lower()]

        assert len(found) >= 3, (
            f"Skill content should describe semantic validation\n"
            f"Expected: At least 3 of {validation_concepts}\n"
            f"Found: {found}\n"
            f"See: Issue #76 Phase 8.7"
        )


# ==============================================================================
# Test Suite 2: Documentation Files Completeness (part of 8 unit tests)
# ==============================================================================


class TestProjectAlignmentValidationDocumentation:
    """Test documentation files have comprehensive content."""

    def test_alignment_checklist_has_standard_checks(self):
        """Test alignment-checklist.md includes standard validation steps."""
        content = ALIGNMENT_CHECKLIST_DOC.read_text()

        # Standard PROJECT.md sections to validate
        required_checks = [
            "GOALS",
            "SCOPE",
            "CONSTRAINTS",
            "ARCHITECTURE"
        ]

        for check in required_checks:
            assert check in content, (
                f"Missing '{check}' validation in alignment-checklist.md\n"
                f"Expected: Include checks for all PROJECT.md sections\n"
                f"See: Issue #76 Phase 8.7"
            )

    def test_semantic_validation_doc_contrasts_approaches(self):
        """Test semantic-validation-approach.md contrasts semantic vs literal validation."""
        content = SEMANTIC_VALIDATION_DOC.read_text()

        # Should contrast semantic vs literal approaches
        concepts = [
            "semantic",
            "literal",
            "intent",
            "meaning"
        ]

        found = [c for c in concepts if c.lower() in content.lower()]

        assert len(found) >= 3, (
            f"semantic-validation-approach.md should contrast approaches\n"
            f"Expected: At least 3 of {concepts}\n"
            f"Found: {found}\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_gap_assessment_doc_defines_methodology(self):
        """Test gap-assessment-methodology.md defines clear methodology."""
        content = GAP_ASSESSMENT_DOC.read_text()

        # Gap assessment steps
        methodology_concepts = [
            "identify",
            "document",
            "prioritize",
            "gap"
        ]

        found = [c for c in methodology_concepts if c.lower() in content.lower()]

        assert len(found) >= 3, (
            f"gap-assessment-methodology.md should define methodology\n"
            f"Expected: At least 3 of {methodology_concepts}\n"
            f"Found: {found}\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_conflict_resolution_doc_defines_patterns(self):
        """Test conflict-resolution-patterns.md defines resolution strategies."""
        content = CONFLICT_RESOLUTION_DOC.read_text()

        # Conflict resolution strategies
        strategies = [
            "conflict",
            "resolution",
            "merge",
            "strategy"
        ]

        found = [c for c in strategies if c.lower() in content.lower()]

        assert len(found) >= 3, (
            f"conflict-resolution-patterns.md should define strategies\n"
            f"Expected: At least 3 of {strategies}\n"
            f"Found: {found}\n"
            f"See: Issue #76 Phase 8.7"
        )


# ==============================================================================
# Test Suite 3: Agent Integration (3 integration tests)
# ==============================================================================


class TestAgentProjectAlignmentValidationReferences:
    """Test agents reference project-alignment-validation skill."""

    @pytest.mark.parametrize("agent_name", ALIGNMENT_AGENTS)
    def test_agent_references_skill(self, agent_name):
        """Test agent references project-alignment-validation skill."""
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        content = agent_file.read_text()

        assert "project-alignment-validation" in content.lower(), (
            f"Agent {agent_name} should reference project-alignment-validation skill\n"
            f"Expected: Add 'project-alignment-validation' to Relevant Skills section\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_alignment_validator_agent_streamlined(self):
        """Test alignment-validator agent removes inline alignment patterns."""
        agent_file = AGENTS_DIR / "alignment-validator.md"
        content = agent_file.read_text()

        # Should reference skill instead of inline patterns
        assert "project-alignment-validation" in content.lower(), (
            "alignment-validator must reference project-alignment-validation skill\n"
            "See: Issue #76 Phase 8.7"
        )

        # Should not have verbose inline checklist (allow mentions, but not full guidance)
        checklist_pattern = re.compile(r'- \[[ x]\]')
        checkboxes = checklist_pattern.findall(content)

        assert len(checkboxes) <= 5, (
            f"alignment-validator has too many inline checklist items: {len(checkboxes)}\n"
            f"Expected: Reference skill for detailed checklist (≤5 inline checkboxes)\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_alignment_analyzer_agent_streamlined(self):
        """Test alignment-analyzer agent removes inline gap assessment."""
        agent_file = AGENTS_DIR / "alignment-analyzer.md"
        content = agent_file.read_text()

        # Should reference skill
        assert "project-alignment-validation" in content.lower(), (
            "alignment-analyzer must reference project-alignment-validation skill\n"
            "See: Issue #76 Phase 8.7"
        )

        # Should not have verbose gap assessment methodology inline
        gap_mentions = content.lower().count("gap assessment")

        assert gap_mentions <= 3, (
            f"alignment-analyzer has too many 'gap assessment' mentions: {gap_mentions}\n"
            f"Expected: Reference skill for methodology (≤3 mentions)\n"
            f"See: Issue #76 Phase 8.7"
        )


# ==============================================================================
# Test Suite 4: Hook Integration (3 integration tests)
# ==============================================================================


class TestHookProjectAlignmentValidationReferences:
    """Test hooks reference project-alignment-validation skill."""

    @pytest.mark.parametrize("hook_file", ALIGNMENT_HOOKS)
    def test_hook_references_skill(self, hook_file):
        """Test hook references project-alignment-validation skill."""
        hook_path = HOOKS_DIR / hook_file
        content = hook_path.read_text()

        assert "project-alignment-validation" in content.lower(), (
            f"Hook {hook_file} should reference project-alignment-validation skill\n"
            f"Expected: Add to module docstring or comments\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_validate_project_alignment_hook_streamlined(self):
        """Test validate_project_alignment.py hook references skill."""
        hook_path = HOOKS_DIR / "validate_project_alignment.py"
        content = hook_path.read_text()

        # Should reference skill
        assert "project-alignment-validation" in content.lower(), (
            "validate_project_alignment.py must reference project-alignment-validation skill\n"
            "See: Issue #76 Phase 8.7"
        )

        # Should not duplicate validation logic inline (allow 1-2 mentions)
        validation_mentions = content.lower().count("validation")

        # Allow reasonable mentions (imports, function names, comments)
        # but not full duplicated validation logic
        assert validation_mentions <= 15, (
            f"validate_project_alignment.py has too many 'validation' mentions: {validation_mentions}\n"
            f"Expected: Reference skill for validation patterns (≤15 mentions)\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_auto_update_project_progress_hook_streamlined(self):
        """Test auto_update_project_progress.py hook references skill."""
        hook_path = HOOKS_DIR / "auto_update_project_progress.py"
        content = hook_path.read_text()

        # Should reference skill
        assert "project-alignment-validation" in content.lower(), (
            "auto_update_project_progress.py must reference project-alignment-validation skill\n"
            "See: Issue #76 Phase 8.7"
        )


# ==============================================================================
# Test Suite 5: Library Integration (1 integration test)
# ==============================================================================


class TestLibraryProjectAlignmentValidationReferences:
    """Test libraries reference project-alignment-validation skill."""

    @pytest.mark.parametrize("library_file", ALIGNMENT_LIBRARIES)
    def test_library_references_skill(self, library_file):
        """Test library references project-alignment-validation skill."""
        library_path = LIB_DIR / library_file
        content = library_path.read_text()

        assert "project-alignment-validation" in content.lower(), (
            f"Library {library_file} should reference project-alignment-validation skill\n"
            f"Expected: Add to module docstring or comments\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_alignment_assessor_library_streamlined(self):
        """Test alignment_assessor.py library references skill."""
        library_path = LIB_DIR / "alignment_assessor.py"
        content = library_path.read_text()

        # Should reference skill
        assert "project-alignment-validation" in content.lower(), (
            "alignment_assessor.py must reference project-alignment-validation skill\n"
            "See: Issue #76 Phase 8.7"
        )

        # Should not duplicate assessment methodology inline
        assessment_mentions = content.lower().count("assessment")

        # Allow reasonable mentions but not duplicated methodology
        assert assessment_mentions <= 20, (
            f"alignment_assessor.py has too many 'assessment' mentions: {assessment_mentions}\n"
            f"Expected: Reference skill for methodology (≤20 mentions)\n"
            f"See: Issue #76 Phase 8.7"
        )


# ==============================================================================
# Test Suite 6: Token Reduction Validation (3 token tests)
# ==============================================================================


class TestTokenReductionFromProjectAlignmentValidation:
    """Test token reduction from project-alignment-validation skill extraction."""

    def test_agent_token_reduction_meets_target(self):
        """Test agent token reduction meets 2-4% target."""
        total_agent_tokens = 0

        for agent_name in ALIGNMENT_AGENTS:
            agent_file = AGENTS_DIR / f"{agent_name}.md"
            content = agent_file.read_text()
            # Rough token count (1 token ≈ 4 chars)
            tokens = len(content) // 4
            total_agent_tokens += tokens

        # Expected token reduction: ~100 tokens per agent × 3 agents = ~300 tokens
        # Before: ~9,000-10,000 tokens total
        # After: ~8,700-9,700 tokens total
        # Reduction: 2-4%
        expected_max_tokens = 9700

        assert total_agent_tokens <= expected_max_tokens, (
            f"Agent total tokens too high: {total_agent_tokens}\n"
            f"Expected: ≤{expected_max_tokens} tokens (2-4% reduction)\n"
            f"Target: ~300 tokens saved across 3 agents\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_overall_token_reduction_meets_target(self):
        """Test overall token reduction of 800-1,200 tokens across 12 files."""
        total_tokens = 0

        # Count tokens in all files
        for agent_name in ALIGNMENT_AGENTS:
            agent_file = AGENTS_DIR / f"{agent_name}.md"
            content = agent_file.read_text()
            total_tokens += len(content) // 4

        for hook_file in ALIGNMENT_HOOKS:
            hook_path = HOOKS_DIR / hook_file
            content = hook_path.read_text()
            total_tokens += len(content) // 4

        for library_file in ALIGNMENT_LIBRARIES:
            library_path = LIB_DIR / library_file
            content = library_path.read_text()
            total_tokens += len(content) // 4

        # Expected: 12 files × ~100 tokens saved = ~1,200 tokens
        # Before: ~20,000-25,000 tokens total
        # After: ~18,800-23,800 tokens total
        expected_max_tokens = 23800

        assert total_tokens <= expected_max_tokens, (
            f"Overall total tokens too high: {total_tokens}\n"
            f"Expected: ≤{expected_max_tokens} tokens (800-1,200 token reduction)\n"
            f"Target: ~1,200 tokens saved across 12 files\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_progressive_disclosure_overhead_minimal(self):
        """Test progressive disclosure overhead is minimal (<100 tokens)."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = parts[1]

        # Frontmatter should be < 100 tokens (rough estimate: ~4 chars per token)
        frontmatter_tokens = len(frontmatter) // 4

        assert frontmatter_tokens < 100, (
            f"Skill frontmatter too large: {frontmatter_tokens} tokens\n"
            f"Expected: < 100 tokens for efficient progressive disclosure\n"
            f"Overhead: {frontmatter_tokens} tokens always in context\n"
            f"See: Issue #76 Phase 8.7"
        )


# ==============================================================================
# Test Suite 7: Skill Content Quality
# ==============================================================================


class TestProjectAlignmentValidationSkillContent:
    """Test skill content quality and completeness."""

    def test_skill_defines_goals_validation(self):
        """Test skill defines GOALS section validation."""
        content = SKILL_FILE.read_text()

        # Should explain GOALS validation
        assert "GOALS" in content, (
            "Skill must define GOALS validation\n"
            "Expected: Guidance for validating project goals alignment\n"
            "See: Issue #76 Phase 8.7"
        )

    def test_skill_defines_scope_validation(self):
        """Test skill defines SCOPE section validation."""
        content = SKILL_FILE.read_text()

        # Should explain SCOPE validation
        assert "SCOPE" in content, (
            "Skill must define SCOPE validation\n"
            "Expected: Guidance for validating project scope boundaries\n"
            "See: Issue #76 Phase 8.7"
        )

    def test_skill_defines_constraints_validation(self):
        """Test skill defines CONSTRAINTS section validation."""
        content = SKILL_FILE.read_text()

        # Should explain CONSTRAINTS validation
        assert "CONSTRAINTS" in content, (
            "Skill must define CONSTRAINTS validation\n"
            "Expected: Guidance for validating project constraints\n"
            "See: Issue #76 Phase 8.7"
        )

    def test_skill_defines_architecture_validation(self):
        """Test skill defines ARCHITECTURE section validation."""
        content = SKILL_FILE.read_text()

        # Should explain ARCHITECTURE validation
        assert "ARCHITECTURE" in content, (
            "Skill must define ARCHITECTURE validation\n"
            "Expected: Guidance for validating architecture alignment\n"
            "See: Issue #76 Phase 8.7"
        )


# ==============================================================================
# Test Suite 8: Template Quality
# ==============================================================================


class TestTemplateQuality:
    """Test template files have proper structure."""

    def test_alignment_report_template_has_sections(self):
        """Test alignment-report-template.md has standard sections."""
        content = ALIGNMENT_REPORT_TEMPLATE.read_text()

        required_sections = [
            "Summary",
            "Findings",
            "Recommendations"
        ]

        for section in required_sections:
            assert section in content, (
                f"Missing '{section}' in alignment-report-template.md\n"
                f"Expected: Complete template with all standard sections\n"
                f"See: Issue #76 Phase 8.7"
            )

    def test_gap_assessment_template_has_structure(self):
        """Test gap-assessment-template.md has proper structure."""
        content = GAP_ASSESSMENT_TEMPLATE.read_text()

        required_elements = [
            "Gap",
            "Priority",
            "Impact"
        ]

        for element in required_elements:
            assert element in content, (
                f"Missing '{element}' in gap-assessment-template.md\n"
                f"Expected: Structured template for gap documentation\n"
                f"See: Issue #76 Phase 8.7"
            )

    def test_conflict_resolution_template_has_workflow(self):
        """Test conflict-resolution-template.md has resolution workflow."""
        content = CONFLICT_RESOLUTION_TEMPLATE.read_text()

        workflow_elements = [
            "Conflict",
            "Resolution",
            "Action"
        ]

        for element in workflow_elements:
            assert element in content, (
                f"Missing '{element}' in conflict-resolution-template.md\n"
                f"Expected: Workflow template for conflict resolution\n"
                f"See: Issue #76 Phase 8.7"
            )


# ==============================================================================
# Test Suite 9: Example Quality
# ==============================================================================


class TestExampleQuality:
    """Test example files provide useful guidance."""

    def test_alignment_scenarios_has_multiple_scenarios(self):
        """Test alignment-scenarios.md includes multiple real-world scenarios."""
        content = ALIGNMENT_SCENARIOS_EXAMPLE.read_text()

        # Count scenarios (sections starting with ##)
        scenario_pattern = re.compile(r'^## ', re.MULTILINE)
        scenarios = scenario_pattern.findall(content)

        assert len(scenarios) >= 5, (
            f"alignment-scenarios.md should have ≥5 scenarios\n"
            f"Found {len(scenarios)} scenarios\n"
            f"Expected: Cover common alignment scenarios\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_misalignment_examples_shows_before_after(self):
        """Test misalignment-examples.md shows before/after examples."""
        content = MISALIGNMENT_EXAMPLES.read_text()

        # Should show before and after states
        indicators = ["before", "after", "fixed", "corrected"]
        found = [i for i in indicators if i.lower() in content.lower()]

        assert len(found) >= 2, (
            f"misalignment-examples.md should show before/after\n"
            f"Expected: Demonstrate fixes for misalignment\n"
            f"Found: {found}\n"
            f"See: Issue #76 Phase 8.7"
        )

    def test_project_md_structure_example_complete(self):
        """Test project-md-structure-example.md shows complete structure."""
        content = PROJECT_MD_STRUCTURE_EXAMPLE.read_text()

        required_sections = [
            "## GOALS",
            "## SCOPE",
            "## CONSTRAINTS",
            "## ARCHITECTURE"
        ]

        for section in required_sections:
            assert section in content, (
                f"Missing '{section}' in project-md-structure-example.md\n"
                f"Expected: Complete PROJECT.md example\n"
                f"See: Issue #76 Phase 8.7"
            )


# ==============================================================================
# Test Suite 10: Backward Compatibility
# ==============================================================================


class TestBackwardCompatibility:
    """Test skill integration doesn't break existing alignment validation."""

    def test_agents_still_validate_alignment(self):
        """Test agents still perform alignment validation after skill integration."""
        # Placeholder - would require running agents
        pytest.skip(
            "Integration test requires agent execution\n"
            "Expected: Validate alignment-validator, alignment-analyzer still work\n"
            "See: tests/integration/test_alignment_validation.py"
        )

    def test_hooks_still_trigger_on_misalignment(self):
        """Test hooks still trigger on misalignment after skill integration."""
        # Placeholder - would require git hooks execution
        pytest.skip(
            "Integration test requires hook execution\n"
            "Expected: Validate validate_project_alignment.py still blocks commits\n"
            "See: tests/integration/test_alignment_hooks.py"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
